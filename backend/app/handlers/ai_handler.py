from typing import Optional
from fastapi.responses import JSONResponse, StreamingResponse
from app.helpers.response import success_response
from app.models.schemas.ai import ChatCompletionRequest
from app.services import ai_service


async def list_models_handler() -> JSONResponse:
    """Handle listing available AI models."""
    models = await ai_service.list_models()
    model_dicts = [m.model_dump() for m in models]
    return success_response(
        message="AI models retrieved successfully",
        data={
            "models": model_dicts,
            "total": len(model_dicts),
        },
    )


async def health_check_handler() -> JSONResponse:
    """Handle checking AI service health and connectivity."""
    health = await ai_service.check_health()
    status_code = 200 if health.status in ("healthy", "unconfigured") else 503
    return success_response(
        message="AI health status retrieved successfully",
        data={"health": health.model_dump()},
        status_code=status_code,
    )


async def chat_completion_handler(data: ChatCompletionRequest) -> JSONResponse:
    """Handle non-streaming chat completion."""
    messages = [m.model_dump() for m in data.messages]
    result = await ai_service.chat_completion(
        messages=messages,
        model=data.model,
        temperature=data.temperature,
        top_p=data.top_p,
        max_tokens=data.max_tokens,
        presence_penalty=data.presence_penalty,
        frequency_penalty=data.frequency_penalty,
        response_format=data.response_format,
        tools=data.tools,
        tool_choice=data.tool_choice,
        parallel_tool_calls=data.parallel_tool_calls,
        reasoning_effort=data.reasoning_effort,
    )
    return success_response(
        message="Chat completion generated successfully",
        data={"completion": result},
    )


async def chat_completion_stream_handler(data: ChatCompletionRequest) -> StreamingResponse:
    """Handle streaming chat completion via Server-Sent Events."""
    messages = [m.model_dump() for m in data.messages]

    async def sse_generator():
        async for chunk in ai_service.chat_completion_stream(
            messages=messages,
            model=data.model,
            temperature=data.temperature,
            top_p=data.top_p,
            max_tokens=data.max_tokens,
            presence_penalty=data.presence_penalty,
            frequency_penalty=data.frequency_penalty,
            response_format=data.response_format,
            tools=data.tools,
            tool_choice=data.tool_choice,
            parallel_tool_calls=data.parallel_tool_calls,
            reasoning_effort=data.reasoning_effort,
        ):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
