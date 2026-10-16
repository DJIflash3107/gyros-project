import time
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class AgentEventType(str, Enum):
    AGENT_STATUS = "agent_status"
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    MESSAGE_DELTA = "message_delta"
    APPROVAL_REQUIRED = "approval_required"
    AGENT_ERROR = "agent_error"
    AGENT_COMPLETE = "agent_complete"


class AgentStatusEvent(BaseModel):
    status: str = Field(..., description="Current status: e.g. routing, executing_tools, generating_response")
    message: str = Field(..., description="Human-readable status description")

    model_config = ConfigDict(extra="ignore")


class ToolStartEvent(BaseModel):
    tool_name: str
    tool_input: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class ToolResultEvent(BaseModel):
    tool_name: str
    summary: str
    data: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="ignore")


class MessageDeltaEvent(BaseModel):
    content: str = ""
    finish_reason: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class ApprovalRequiredEvent(BaseModel):
    action: str
    description: str
    approval_id: str

    model_config = ConfigDict(extra="ignore")


class AgentErrorEvent(BaseModel):
    error_code: str
    message: str

    model_config = ConfigDict(extra="ignore")


class AgentCompleteEvent(BaseModel):
    total_tokens: Optional[int] = None
    tools_used: List[str] = Field(default_factory=list)
    duration_ms: float = 0.0

    model_config = ConfigDict(extra="ignore")


class AgentSSEEvent(BaseModel):
    """Root SSE event wrapper. Serialized as `data: {json}` in SSE stream."""
    event: AgentEventType
    data: Dict[str, Any]
    timestamp: float = Field(default_factory=lambda: time.time())
    conversation_id: Optional[str] = None

    model_config = ConfigDict(extra="ignore")

    @classmethod
    def create_status(cls, status: str, message: str, conversation_id: Optional[str] = None) -> "AgentSSEEvent":
        return cls(
            event=AgentEventType.AGENT_STATUS,
            data=AgentStatusEvent(status=status, message=message).model_dump(),
            conversation_id=conversation_id,
        )

    @classmethod
    def create_tool_start(cls, tool_name: str, tool_input: Optional[Dict[str, Any]] = None, conversation_id: Optional[str] = None) -> "AgentSSEEvent":
        return cls(
            event=AgentEventType.TOOL_START,
            data=ToolStartEvent(tool_name=tool_name, tool_input=tool_input or {}).model_dump(),
            conversation_id=conversation_id,
        )

    @classmethod
    def create_tool_result(cls, tool_name: str, summary: str, data: Optional[Dict[str, Any]] = None, conversation_id: Optional[str] = None) -> "AgentSSEEvent":
        return cls(
            event=AgentEventType.TOOL_RESULT,
            data=ToolResultEvent(tool_name=tool_name, summary=summary, data=data).model_dump(),
            conversation_id=conversation_id,
        )

    @classmethod
    def create_message_delta(cls, content: str, finish_reason: Optional[str] = None, conversation_id: Optional[str] = None) -> "AgentSSEEvent":
        return cls(
            event=AgentEventType.MESSAGE_DELTA,
            data=MessageDeltaEvent(content=content, finish_reason=finish_reason).model_dump(),
            conversation_id=conversation_id,
        )

    @classmethod
    def create_approval_required(cls, action: str, description: str, approval_id: str, conversation_id: Optional[str] = None) -> "AgentSSEEvent":
        return cls(
            event=AgentEventType.APPROVAL_REQUIRED,
            data=ApprovalRequiredEvent(action=action, description=description, approval_id=approval_id).model_dump(),
            conversation_id=conversation_id,
        )

    @classmethod
    def create_error(cls, error_code: str, message: str, conversation_id: Optional[str] = None) -> "AgentSSEEvent":
        return cls(
            event=AgentEventType.AGENT_ERROR,
            data=AgentErrorEvent(error_code=error_code, message=message).model_dump(),
            conversation_id=conversation_id,
        )

    @classmethod
    def create_complete(cls, tools_used: List[str], duration_ms: float, total_tokens: Optional[int] = None, conversation_id: Optional[str] = None) -> "AgentSSEEvent":
        return cls(
            event=AgentEventType.AGENT_COMPLETE,
            data=AgentCompleteEvent(tools_used=tools_used, duration_ms=duration_ms, total_tokens=total_tokens).model_dump(),
            conversation_id=conversation_id,
        )


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[str] = Field(default=None, description="Resume existing conversation")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional client-side context hints")

    model_config = ConfigDict(extra="ignore")
