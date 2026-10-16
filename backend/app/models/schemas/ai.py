from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict


class AIModelInfo(BaseModel):
    id: str
    object: Optional[str] = "model"
    owned_by: Optional[str] = None
    created: Optional[int] = None
    context_length: Optional[int] = None
    supports_streaming: bool = True
    supports_tools: bool = True
    supports_vision: bool = False
    supports_reasoning: bool = False
    raw: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="ignore")


class AIHealthResponse(BaseModel):
    status: str
    key_configured: bool
    base_url: str
    default_model: str
    latency_ms: Optional[float] = None
    models_count: Optional[int] = None
    usage: Optional[Dict[str, Any]] = None
    rate_limits: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="ignore")


class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the message sender: system, user, or assistant")
    content: Union[str, List[Dict[str, Any]]] = Field(..., description="Content of the message (text or multimodal list)")

    model_config = ConfigDict(extra="ignore")


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = Field(default=None, description="Model ID to use, defaults to configured AMD_DEFAULT_MODEL")
    messages: List[ChatMessage] = Field(..., min_length=1, description="List of conversation messages")
    stream: bool = Field(default=False, description="Whether to stream back partial progress")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    response_format: Optional[Dict[str, Any]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    parallel_tool_calls: Optional[bool] = None
    reasoning_effort: Optional[str] = None

    model_config = ConfigDict(extra="ignore")
