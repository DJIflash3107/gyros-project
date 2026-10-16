import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI

from app.configs.settings import settings
from app.agent.state import AgentState
from app.agent.prompts import SYSTEM_PROMPT, sanitize_response
from app.agent.tools import get_agent_tools, execute_tool_by_name
from app.services import business_service

logger = logging.getLogger(__name__)


def get_agent_llm(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    streaming: bool = True,
) -> ChatOpenAI:
    """Create ChatOpenAI configured for AMD Token Factory."""
    resolved_key = api_key or settings.AMD_API_KEY
    if not resolved_key:
        resolved_key = "dummy-key-for-init"

    return ChatOpenAI(
        base_url=base_url or settings.AMD_API_BASE_URL,
        api_key=resolved_key,
        model=model or settings.AMD_DEFAULT_MODEL,
        temperature=temperature if temperature is not None else settings.AGENT_TEMPERATURE,
        max_tokens=max_tokens if max_tokens is not None else settings.AGENT_MAX_TOKENS,
        streaming=streaming,
    )


def should_use_tools(state: AgentState) -> str:
    """Conditional edge after route_request."""
    if state.get("error"):
        return "handle_error"
    selected = state.get("selected_tools", [])
    if selected and state.get("turn_count", 0) <= settings.AGENT_MAX_TURNS:
        return "execute_tools"
    return "generate_response"


def check_continue(state: AgentState) -> str:
    """Conditional edge after execute_tools."""
    if state.get("error"):
        return "handle_error"
    if state.get("turn_count", 0) >= settings.AGENT_MAX_TURNS:
        return "generate_response"
    if state.get("should_continue", False):
        return "route_request"
    return "generate_response"


async def route_request_node(
    state: AgentState,
    llm: Optional[Any] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Route user request: analyze intent and select tools if needed."""
    try:
        business_id = state.get("business_id", 0)
        messages = list(state.get("messages", []))
        turn_count = state.get("turn_count", 0)

        # Build system message
        business_name = f"Business #{business_id}"
        if db:
            try:
                biz = business_service.get_business(db, business_id)
                if biz and biz.name:
                    business_name = biz.name
            except Exception:
                pass

        sys_msg = SystemMessage(
            content=SYSTEM_PROMPT.format(business_name=business_name, business_id=business_id)
        )

        active_llm = llm or get_agent_llm()
        tools = get_agent_tools(db, business_id) if db else []

        if tools and hasattr(active_llm, "bind_tools"):
            model_with_tools = active_llm.bind_tools(tools)
        else:
            model_with_tools = active_llm

        full_prompt = [sys_msg] + messages
        response = await model_with_tools.ainvoke(full_prompt)

        tool_calls = getattr(response, "tool_calls", None) or []
        selected_tools = [tc["name"] for tc in tool_calls if "name" in tc]

        intent = selected_tools[0] if selected_tools else "general_query"

        # Heuristic intent classification fallback if no tool_calls were emitted by LLM
        if not selected_tools and messages:
            last_msg = messages[-1]
            last_text = getattr(last_msg, "content", "")
            if isinstance(last_text, str):
                lower_text = last_text.lower()
                if any(w in lower_text for w in ["sale", "revenue", "sold", "observation"]):
                    intent = "sales_analytics"
                    selected_tools = ["sales_analytics"]
                elif any(w in lower_text for w in ["expense", "spend", "cost"]):
                    intent = "expense_summary"
                    selected_tools = ["expense_summary"]
                elif any(w in lower_text for w in ["product", "catalog", "item", "sku"]):
                    intent = "product_catalog"
                    selected_tools = ["product_catalog"]
                elif any(w in lower_text for w in ["summary", "branch", "member", "business"]):
                    intent = "business_summary"
                    selected_tools = ["business_summary"]

        return {
            "messages": [response],
            "intent": intent,
            "selected_tools": selected_tools,
            "turn_count": turn_count + 1,
            "should_continue": bool(selected_tools),
        }
    except Exception as e:
        logger.warning(f"Error in route_request_node: {type(e).__name__} - {e}")
        return {"error": "Failed to analyze request."}


async def execute_tools_node(
    state: AgentState,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Execute selected tools in read-only mode and collect results."""
    try:
        business_id = state.get("business_id", 0)
        messages = list(state.get("messages", []))
        last_message = messages[-1] if messages else None

        tool_calls = getattr(last_message, "tool_calls", None) or []
        selected_tools = state.get("selected_tools", [])

        tools = get_agent_tools(db, business_id) if db is not None else get_agent_tools(None, business_id)
        tool_map = {t.name: t for t in tools}

        tool_messages: List[ToolMessage] = []
        new_results: List[Dict[str, Any]] = []

        if tool_calls:
            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("args", {})
                call_id = tc.get("id", str(uuid.uuid4()))

                if name in tool_map:
                    result = await tool_map[name].ainvoke(args)
                else:
                    result = execute_tool_by_name(name, args, db, business_id)

                new_results.append(result)
                tool_messages.append(
                    ToolMessage(
                        content=json.dumps(result),
                        tool_call_id=call_id,
                        name=name,
                    )
                )
        elif selected_tools:
            # Direct invocation fallback if selected_tools was set directly
            for tool_name in selected_tools:
                call_id = f"call_{tool_name}_{uuid.uuid4().hex[:6]}"
                if tool_name in tool_map:
                    result = await tool_map[tool_name].ainvoke({})
                else:
                    result = execute_tool_by_name(tool_name, {}, db, business_id)

                new_results.append(result)
                tool_messages.append(
                    ToolMessage(
                        content=json.dumps(result),
                        tool_call_id=call_id,
                        name=tool_name,
                    )
                )

        accumulated_results = list(state.get("tool_results") or []) + new_results

        return {
            "messages": tool_messages,
            "tool_results": accumulated_results,
            "should_continue": False,
        }
    except Exception as e:
        logger.warning(f"Error in execute_tools_node: {type(e).__name__} - {e}")
        return {"error": "Failed to execute tools."}


async def generate_response_node(
    state: AgentState,
    llm: Optional[Any] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Generate final sanitized answer for the user."""
    try:
        business_id = state.get("business_id", 0)
        messages = list(state.get("messages", []))

        business_name = f"Business #{business_id}"
        if db:
            try:
                biz = business_service.get_business(db, business_id)
                if biz and biz.name:
                    business_name = biz.name
            except Exception:
                pass

        sys_msg = SystemMessage(
            content=SYSTEM_PROMPT.format(business_name=business_name, business_id=business_id)
        )

        active_llm = llm or get_agent_llm()
        full_prompt = [sys_msg] + messages
        response = await active_llm.ainvoke(full_prompt)

        raw_content = getattr(response, "content", "")
        if isinstance(raw_content, str):
            sanitized_content = sanitize_response(raw_content)
        else:
            sanitized_content = str(raw_content)

        final_msg = AIMessage(content=sanitized_content)
        return {
            "messages": [final_msg],
            "should_continue": False,
        }
    except Exception as e:
        logger.warning(f"Error in generate_response_node: {type(e).__name__} - {e}")
        return {"error": "Failed to generate final response."}


async def handle_error_node(state: AgentState) -> Dict[str, Any]:
    """Safe error handling node: never leaks SQL or internal traces."""
    err_raw = state.get("error") or "An internal agent error occurred."
    safe_message = "An error occurred while processing your request. Please try again."

    logger.warning(f"Agent error node caught: {err_raw}")
    return {
        "messages": [AIMessage(content=safe_message)],
        "error": safe_message,
        "should_continue": False,
    }


def build_agent_graph_workflow(
    db: Optional[Session] = None,
    business_id: Optional[int] = None,
    llm: Optional[Any] = None,
) -> StateGraph:
    """Build the LangGraph StateGraph instance."""
    workflow = StateGraph(AgentState)

    async def _route(state: AgentState):
        return await route_request_node(state, llm=llm, db=db)

    async def _tools(state: AgentState):
        return await execute_tools_node(state, db=db)

    async def _respond(state: AgentState):
        return await generate_response_node(state, llm=llm, db=db)

    async def _error(state: AgentState):
        return await handle_error_node(state)

    workflow.add_node("route_request", _route)
    workflow.add_node("execute_tools", _tools)
    workflow.add_node("generate_response", _respond)
    workflow.add_node("handle_error", _error)

    workflow.add_edge(START, "route_request")
    workflow.add_conditional_edges(
        "route_request",
        should_use_tools,
        {
            "execute_tools": "execute_tools",
            "generate_response": "generate_response",
            "handle_error": "handle_error",
        },
    )
    workflow.add_conditional_edges(
        "execute_tools",
        check_continue,
        {
            "route_request": "route_request",
            "generate_response": "generate_response",
            "handle_error": "handle_error",
        },
    )
    workflow.add_edge("generate_response", END)
    workflow.add_edge("handle_error", END)

    return workflow


def create_agent_graph(
    db: Optional[Session] = None,
    business_id: Optional[int] = None,
    llm: Optional[Any] = None,
):
    """Compile and return the runnable LangGraph agent."""
    workflow = build_agent_graph_workflow(db=db, business_id=business_id, llm=llm)
    return workflow.compile()
