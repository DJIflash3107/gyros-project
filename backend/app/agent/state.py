from typing import Annotated, Any, Dict, List, Optional, Sequence
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict, total=False):
    # Core conversation
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # Request metadata
    business_id: int
    user_id: int
    conversation_id: str

    # Routing
    intent: Optional[str]
    selected_tools: List[str]

    # Tool execution
    tool_results: List[Dict[str, Any]]

    # Control
    turn_count: int
    should_continue: bool
    error: Optional[str]
