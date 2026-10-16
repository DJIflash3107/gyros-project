import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from langchain_core.messages import AIMessage

from app.configs.settings import settings
from app.models.schemas.agent import AgentSSEEvent, AgentEventType
from app.services.agent_service import stream_agent_chat


@pytest.fixture
def auth_business(client, auth_user):
    """Fixture that creates a business owned by the authenticated user."""
    biz_resp = client.post(
        "/api/v1/businesses",
        json={"name": "Streaming Test Business"},
        headers=auth_user["headers"],
    )
    assert biz_resp.status_code == 201
    return biz_resp.json()["data"]["business"]["id"]


class MultiStepMockLLM:
    """Mock LLM that first invokes sales_analytics tool, then synthesizes final answer."""
    def __init__(self, answer="Total sales for October reached $600."):
        self.call_count = 0
        self.answer = answer

    async def ainvoke(self, messages):
        self.call_count += 1
        if self.call_count == 1:
            return AIMessage(
                content="",
                tool_calls=[{"name": "sales_analytics", "args": {"period": "2026-10"}, "id": "call_stream_1"}],
            )
        return AIMessage(content=self.answer)

    def bind_tools(self, tools):
        return self


def parse_sse_stream(response_text: str):
    """Parse raw SSE text into list of (raw_data_str, parsed_json_or_str)."""
    events = []
    for line in response_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("data: "):
            payload = line[len("data: "):]
            if payload == "[DONE]":
                events.append(("[DONE]", "[DONE]"))
            else:
                events.append((payload, json.loads(payload)))
    return events


def test_stream_event_order(client, auth_user, auth_business):
    """Stream events arrive in correct lifecycle order ending with [DONE]."""
    mock_llm = MultiStepMockLLM()
    with patch("app.agent.graph.get_agent_llm", return_value=mock_llm):
        resp = client.post(
            f"/api/v1/agent/businesses/{auth_business}/chat",
            json={"message": "What were our sales?"},
            headers=auth_user["headers"],
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        events = parse_sse_stream(resp.text)
        assert len(events) >= 4

        # First event is agent_status
        assert events[0][1]["event"] == AgentEventType.AGENT_STATUS

        # Terminal lines
        assert events[-1][0] == "[DONE]"
        assert events[-2][1]["event"] == AgentEventType.AGENT_COMPLETE


def test_stream_message_delta(client, auth_user, auth_business):
    """message_delta events contain streamed text tokens."""
    mock_llm = MultiStepMockLLM(answer="October revenue was strong.")
    with patch("app.agent.graph.get_agent_llm", return_value=mock_llm):
        resp = client.post(
            f"/api/v1/agent/businesses/{auth_business}/chat",
            json={"message": "Give me sales update"},
            headers=auth_user["headers"],
        )
        assert resp.status_code == 200

        events = parse_sse_stream(resp.text)
        delta_events = [e[1] for e in events if isinstance(e[1], dict) and e[1].get("event") == AgentEventType.MESSAGE_DELTA]
        assert len(delta_events) >= 1

        contents = [d["data"].get("content", "") for d in delta_events]
        combined = "".join(contents)
        assert "October revenue was strong." in combined


def test_stream_tool_events(client, auth_user, auth_business):
    """tool_start is always followed by tool_result for the same tool name."""
    mock_llm = MultiStepMockLLM()
    with patch("app.agent.graph.get_agent_llm", return_value=mock_llm):
        resp = client.post(
            f"/api/v1/agent/businesses/{auth_business}/chat",
            json={"message": "Check our sales please"},
            headers=auth_user["headers"],
        )
        assert resp.status_code == 200

        events = parse_sse_stream(resp.text)
        tool_starts = [e[1] for e in events if isinstance(e[1], dict) and e[1].get("event") == AgentEventType.TOOL_START]
        tool_results = [e[1] for e in events if isinstance(e[1], dict) and e[1].get("event") == AgentEventType.TOOL_RESULT]

        assert len(tool_starts) >= 1
        assert len(tool_results) >= 1
        assert tool_starts[0]["data"]["tool_name"] == "sales_analytics"
        assert tool_results[0]["data"]["tool_name"] == "sales_analytics"
        assert "summary" in tool_results[0]["data"]


def test_stream_all_events_valid_json(client, auth_user, auth_business):
    """Every data: payload (except [DONE]) strictly conforms to AgentSSEEvent schema."""
    mock_llm = MultiStepMockLLM()
    with patch("app.agent.graph.get_agent_llm", return_value=mock_llm):
        resp = client.post(
            f"/api/v1/agent/businesses/{auth_business}/chat",
            json={"message": "Summary please"},
            headers=auth_user["headers"],
        )
        assert resp.status_code == 200

        for line in resp.text.split("\n"):
            line = line.strip()
            if line.startswith("data: "):
                payload = line[len("data: "):]
                if payload == "[DONE]":
                    continue
                # Validate with Pydantic model
                event_obj = AgentSSEEvent.model_validate_json(payload)
                assert event_obj.event in list(AgentEventType)
                assert isinstance(event_obj.data, dict)
                assert event_obj.timestamp > 0


def test_stream_error_event(client, auth_user, auth_business):
    """Provider failure produces safe agent_error event without stack trace or raw SQL."""
    class FailingLLM:
        async def ainvoke(self, messages):
            raise RuntimeError("AMD Token Factory provider connection reset 502 with SQL SELECT")
        def bind_tools(self, tools):
            return self

    with patch("app.agent.graph.get_agent_llm", return_value=FailingLLM()):
        resp = client.post(
            f"/api/v1/agent/businesses/{auth_business}/chat",
            json={"message": "Query data"},
            headers=auth_user["headers"],
        )
        assert resp.status_code == 200

        events = parse_sse_stream(resp.text)
        error_events = [e[1] for e in events if isinstance(e[1], dict) and e[1].get("event") == AgentEventType.AGENT_ERROR]
        assert len(error_events) >= 1

        err_data = error_events[0]["data"]
        assert err_data["error_code"] == "ERR-AGT-500"
        # No internal stack trace or raw SQL exposed
        assert "SELECT" not in err_data["message"]
        assert "RuntimeError" not in err_data["message"]
        assert events[-1][0] == "[DONE]"


@pytest.mark.asyncio
async def test_stream_timeout(db_session):
    """Slow LLM exceeding timeout emits ERR-AGT-408 agent_error event."""
    class HangingLLM:
        async def ainvoke(self, messages):
            await asyncio.sleep(2.0)
            return AIMessage(content="Delayed reply")
        def bind_tools(self, tools):
            return self

    events = []
    async for event in stream_agent_chat(
        db=db_session,
        business_id=1,
        user_id=1,
        message="Calculate complex statistics",
        conversation_id="conv-timeout",
        llm=HangingLLM(),
        timeout_seconds=0.05,
    ):
        events.append(event)

    error_events = [e for e in events if e.event == AgentEventType.AGENT_ERROR]
    assert len(error_events) >= 1
    assert error_events[0].data["error_code"] == "ERR-AGT-408"
    assert "timed out" in error_events[0].data["message"].lower()


@pytest.mark.asyncio
async def test_stream_disconnect(db_session):
    """Client disconnect mid-stream terminates processing gracefully without server crash."""
    mock_request = MagicMock()
    # Simulate client disconnect after 1st event
    is_disconnected_calls = [False, True]
    async def fake_is_disconnected():
        if is_disconnected_calls:
            return is_disconnected_calls.pop(0)
        return True

    mock_request.is_disconnected = fake_is_disconnected

    class NormalLLM:
        async def ainvoke(self, messages):
            return AIMessage(content="Finished answer")
        def bind_tools(self, tools):
            return self

    events = []
    async for event in stream_agent_chat(
        db=db_session,
        business_id=1,
        user_id=1,
        message="Quick question",
        conversation_id="conv-disconnect",
        request=mock_request,
        llm=NormalLLM(),
    ):
        events.append(event)

    # Stream should exit gracefully when disconnect is detected
    assert len(events) >= 1


def test_no_chain_of_thought_leaked(client, auth_user, auth_business):
    """<think> and reasoning blocks are stripped and never appear in message_delta events."""
    dirty_answer = "<think>\nLet's check the database table sales_report_observations...\nUser wants monthly sales.\n</think>Your total sales are $15,000 across 3 branches."
    mock_llm = MultiStepMockLLM(answer=dirty_answer)

    with patch("app.agent.graph.get_agent_llm", return_value=mock_llm):
        resp = client.post(
            f"/api/v1/agent/businesses/{auth_business}/chat",
            json={"message": "Show sales breakdown"},
            headers=auth_user["headers"],
        )
        assert resp.status_code == 200

        events = parse_sse_stream(resp.text)
        delta_events = [e[1] for e in events if isinstance(e[1], dict) and e[1].get("event") == AgentEventType.MESSAGE_DELTA]

        all_content = " ".join(d["data"].get("content", "") for d in delta_events)
        assert "<think>" not in all_content
        assert "</think>" not in all_content
        assert "database table" not in all_content
        assert "sales_report_observations" not in all_content
        assert "Your total sales are $15,000" in all_content
