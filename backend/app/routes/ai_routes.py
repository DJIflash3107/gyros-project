from fastapi import APIRouter
from app.handlers import ai_handler
from app.models.schemas.ai import ChatCompletionRequest

router = APIRouter(
    prefix="/api/v1/ai",
    tags=["AI"],
)


@router.get("/models")
async def list_ai_models():
    """Discover available AI models from AMD Token Factory catalog."""
    return await ai_handler.list_models_handler()


@router.get("/health")
async def get_ai_health():
    """Check connectivity and operational health of AMD Token Factory."""
    return await ai_handler.health_check_handler()


@router.post("/chat/completions")
async def chat_completion(data: ChatCompletionRequest):
    """
    Generate chat completion via AMD Token Factory.
    Supports streaming if `stream=True` in request body.
    """
    if data.stream:
        return await ai_handler.chat_completion_stream_handler(data)
    return await ai_handler.chat_completion_handler(data)
