import asyncio
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional
from fastapi import Request
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, AIMessage

from app.configs.settings import settings
from app.helpers.exceptions import AgentTimeoutException, AgentCancelledException
from app.models.schemas.agent import AgentSSEEvent
from app.agent.state import AgentState
from app.agent.prompts import sanitize_response
from app.agent.graph import create_agent_graph

logger = logging.getLogger(__name__)


async def stream_agent_chat(
    db: Session,
    business_id: int,
    user_id: int,
    message: str,
    conversation_id: str,
    request: Optional[Request] = None,
    llm: Optional[Any] = None,
    timeout_seconds: Optional[float] = None,
) -> AsyncIterator[AgentSSEEvent]:
    """
    Execute the agent graph and yield structured SSE events.
    Uses LangGraph's astream_events() for genuine streaming.
    """
    start_time = time.time()
    tools_used: List[str] = []
    total_tokens: int = 0
    has_error: bool = False
    streamed_any_chunk: bool = False
    final_response_content: Optional[str] = None

    # Step 1: Initial status event
    yield AgentSSEEvent.create_status(
        status="routing",
        message="Analyzing your question...",
        conversation_id=conversation_id,
    )

    try:
        app = create_agent_graph(db=db, business_id=business_id, llm=llm)

        initial_state: AgentState = {
            "messages": [HumanMessage(content=message)],
            "business_id": business_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "turn_count": 0,
            "selected_tools": [],
            "tool_results": [],
            "should_continue": True,
        }

        effective_timeout = timeout_seconds if timeout_seconds is not None else float(settings.AGENT_REQUEST_TIMEOUT)

        event_generator = app.astream_events(initial_state, version="v2")

        # Helper to get next event with timeout
        async def _iterate_events():
            async for event in event_generator:
                yield event

        async def _process_stream():
            nonlocal total_tokens, streamed_any_chunk, has_error, final_response_content

            async for event in _iterate_events():
                # Check for client disconnect
                if request is not None and await request.is_disconnected():
                    logger.info(f"Client disconnected during agent processing: conversation {conversation_id}")
                    raise AgentCancelledException()

                event_type = event.get("event")
                event_name = event.get("name", "")
                event_data = event.get("data", {})

                if event_type == "on_chain_start":
                    if event_name == "execute_tools":
                        yield AgentSSEEvent.create_status(
                            status="executing_tools",
                            message="Running business tools...",
                            conversation_id=conversation_id,
                        )
                    elif event_name == "generate_response":
                        yield AgentSSEEvent.create_status(
                            status="generating_response",
                            message="Preparing your answer...",
                            conversation_id=conversation_id,
                        )

                elif event_type == "on_tool_start":
                    tool_name = event_name
                    if tool_name not in tools_used:
                        tools_used.append(tool_name)
                    tool_input = event_data.get("input", {})
                    # Sanitize tool input - never expose credentials or raw tokens
                    safe_input = (
                        {k: v for k, v in tool_input.items() if k not in ["password", "token", "api_key", "secret"]}
                        if isinstance(tool_input, dict)
                        else {}
                    )
                    yield AgentSSEEvent.create_tool_start(
                        tool_name=tool_name,
                        tool_input=safe_input,
                        conversation_id=conversation_id,
                    )

                elif event_type == "on_tool_end":
                    tool_name = event_name
                    output = event_data.get("output", {})
                    if isinstance(output, dict):
                        summary = output.get("summary", f"Completed {tool_name}")
                        data = output.get("data")
                    else:
                        summary = str(output)
                        data = None
                    yield AgentSSEEvent.create_tool_result(
                        tool_name=tool_name,
                        summary=summary,
                        data=data,
                        conversation_id=conversation_id,
                    )

                elif event_type == "on_chat_model_stream":
                    chunk = event_data.get("chunk")
                    if chunk:
                        raw_chunk = getattr(chunk, "content", "")
                        if isinstance(raw_chunk, str) and raw_chunk:
                            clean_chunk = sanitize_response(raw_chunk)
                            if clean_chunk:
                                streamed_any_chunk = True
                                total_tokens += 1
                                yield AgentSSEEvent.create_message_delta(
                                    content=clean_chunk,
                                    conversation_id=conversation_id,
                                )

                elif event_type == "on_chain_end":
                    if event_name == "generate_response":
                        node_output = event_data.get("output", {})
                        if isinstance(node_output, dict):
                            out_messages = node_output.get("messages", [])
                            if out_messages:
                                last_msg = out_messages[-1]
                                content = getattr(last_msg, "content", "")
                                if isinstance(content, str):
                                    final_response_content = sanitize_response(content)
                    elif event_name == "handle_error":
                        has_error = True
                        yield AgentSSEEvent.create_error(
                            error_code="ERR-AGT-500",
                            message="An error occurred while processing your request. Please try again.",
                            conversation_id=conversation_id,
                        )

        # Wrap stream consumption with timeout
        try:
            # We iterate while tracking elapsed time
            deadline = time.time() + effective_timeout
            generator = _process_stream()

            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise asyncio.TimeoutError()

                try:
                    event = await asyncio.wait_for(generator.__anext__(), timeout=remaining)
                    yield event
                except StopAsyncIteration:
                    break

        except (asyncio.TimeoutError, TimeoutError):
            logger.warning(f"Agent request timed out after {effective_timeout}s for conversation {conversation_id}")
            yield AgentSSEEvent.create_error(
                error_code="ERR-AGT-408",
                message="Request timed out",
                conversation_id=conversation_id,
            )
            return

        # If LLM didn't stream incrementally (e.g. non-streaming mock or fast single return),
        # emit the final response content captured in generate_response_node
        if not has_error and not streamed_any_chunk and final_response_content:
            yield AgentSSEEvent.create_message_delta(
                content=final_response_content,
                conversation_id=conversation_id,
            )
            total_tokens += len(final_response_content.split())

        # Final message delta stop indicator
        if not has_error:
            yield AgentSSEEvent.create_message_delta(
                content="",
                finish_reason="stop",
                conversation_id=conversation_id,
            )

            duration_ms = round((time.time() - start_time) * 1000, 2)
            yield AgentSSEEvent.create_complete(
                tools_used=tools_used,
                duration_ms=duration_ms,
                total_tokens=total_tokens,
                conversation_id=conversation_id,
            )

    except AgentCancelledException:
        logger.info(f"Agent stream cancelled gracefully: {conversation_id}")
        return
    except Exception as e:
        logger.error(f"Unhandled error in agent service: {type(e).__name__} - {e}", exc_info=True)
        yield AgentSSEEvent.create_error(
            error_code="ERR-AGT-500",
            message="An error occurred while processing your request.",
            conversation_id=conversation_id,
        )
