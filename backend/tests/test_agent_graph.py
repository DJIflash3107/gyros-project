import pytest
from langchain_core.messages import HumanMessage, AIMessage

from app.configs.settings import settings
from app.agent.graph import (
    build_agent_graph_workflow,
    create_agent_graph,
    route_request_node,
    execute_tools_node,
    generate_response_node,
    handle_error_node,
    should_use_tools,
    check_continue,
)
from app.agent.state import AgentState


def test_graph_compiles():
    """StateGraph compiles into a runnable graph without errors."""
    workflow = build_agent_graph_workflow()
    compiled_app = workflow.compile()
    assert compiled_app is not None
    assert hasattr(compiled_app, "ainvoke")
    assert hasattr(compiled_app, "astream_events")


@pytest.mark.asyncio
async def test_route_node_classifies_intent():
    """Given a sales question, route_request_node identifies sales_analytics."""
    class MockSalesLLM:
        async def ainvoke(self, messages):
            return AIMessage(
                content="",
                tool_calls=[{"name": "sales_analytics", "args": {"period": "2026-10"}, "id": "call_s1"}],
            )
        def bind_tools(self, tools):
            return self

    state: AgentState = {
        "messages": [HumanMessage(content="What were our sales for October 2026?")],
        "business_id": 1,
        "turn_count": 0,
    }

    result = await route_request_node(state, llm=MockSalesLLM())
    assert result["intent"] == "sales_analytics"
    assert "sales_analytics" in result["selected_tools"]
    assert result["turn_count"] == 1
    assert result["should_continue"] is True


def test_max_turns_enforced():
    """After AGENT_MAX_TURNS is reached, control transitions directly to generate_response."""
    # When turn_count equals or exceeds AGENT_MAX_TURNS, check_continue terminates tool loop
    state_max_turns: AgentState = {
        "turn_count": settings.AGENT_MAX_TURNS,
        "should_continue": True,
        "selected_tools": ["sales_analytics"],
    }
    assert check_continue(state_max_turns) == "generate_response"

    # should_use_tools also prevents additional tool cycles when max turns reached
    state_over_limit: AgentState = {
        "turn_count": settings.AGENT_MAX_TURNS + 1,
        "selected_tools": ["sales_analytics"],
    }
    assert should_use_tools(state_over_limit) == "generate_response"

    # Within turn limits and should_continue is True -> loop back to route_request
    state_within_limit: AgentState = {
        "turn_count": 1,
        "should_continue": True,
        "selected_tools": ["sales_analytics"],
    }
    assert check_continue(state_within_limit) == "route_request"


@pytest.mark.asyncio
async def test_error_node_produces_safe_event():
    """handle_error_node returns safe user-facing message without leaking SQL or tracebacks."""
    state_with_raw_sql_error: AgentState = {
        "error": "OperationalError: (sqlite3.OperationalError) near 'SYNTAX': syntax error [SQL: SELECT * FROM secrets WHERE id=1]",
    }

    result = await handle_error_node(state_with_raw_sql_error)
    error_msg = result.get("error", "")

    assert "SELECT" not in error_msg
    assert "secrets" not in error_msg
    assert "syntax error" not in error_msg
    assert "Please try again" in error_msg

    assert len(result["messages"]) == 1
    assert "Please try again" in result["messages"][0].content


@pytest.mark.asyncio
async def test_state_shape_preserved():
    """Full execution preserves and populates all expected keys in AgentState."""
    class DeterministicMockLLM:
        async def ainvoke(self, messages):
            return AIMessage(content="Your business is performing well.")
        def bind_tools(self, tools):
            return self

    app = create_agent_graph(llm=DeterministicMockLLM())

    initial_state: AgentState = {
        "messages": [HumanMessage(content="Give me a business update.")],
        "business_id": 42,
        "user_id": 7,
        "conversation_id": "test-conv-uuid",
        "turn_count": 0,
        "selected_tools": [],
        "tool_results": [],
        "should_continue": True,
    }

    final_state = await app.ainvoke(initial_state)

    assert "messages" in final_state
    assert "business_id" in final_state
    assert final_state["business_id"] == 42
    assert "user_id" in final_state
    assert final_state["user_id"] == 7
    assert "conversation_id" in final_state
    assert final_state["conversation_id"] == "test-conv-uuid"
    assert "turn_count" in final_state
    assert "selected_tools" in final_state
    assert "tool_results" in final_state
    assert len(final_state["messages"]) >= 2
    assert isinstance(final_state["messages"][-1], AIMessage)
    assert final_state["messages"][-1].content == "Your business is performing well."
