import logging
import uuid
from typing import Optional
from fastapi import Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.settings import settings
from app.middlewares.auth import get_current_user
from app.helpers.exceptions import (
    AIConfigException,
    AgentTimeoutException,
    AgentCancelledException,
)
from app.models.schemas.agent import AgentChatRequest, AgentSSEEvent
from app.models.user import User
from app.services import agent_service

logger = logging.getLogger(__name__)


async def agent_chat_handler(
    business_id: int,
    data: AgentChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Handle agent chat requests.
    Returns StreamingResponse with SSE content type (text/event-stream).
    """
    # Guard: check AI configuration if not in testing environment
    if not settings.AMD_API_KEY and settings.APP_ENV not in ("testing", "test"):
        raise AIConfigException(message="AI service is not configured. Please configure AMD_API_KEY.")

    conversation_id = data.conversation_id or str(uuid.uuid4())

    async def sse_generator():
        try:
            async for event in agent_service.stream_agent_chat(
                db=db,
                business_id=business_id,
                user_id=current_user.id,
                message=data.message,
                conversation_id=conversation_id,
                request=request,
            ):
                if await request.is_disconnected():
                    break
                yield f"data: {event.model_dump_json()}\n\n"
        except AgentTimeoutException:
            yield f"data: {AgentSSEEvent.create_error('ERR-AGT-408', 'Request timed out', conversation_id=conversation_id).model_dump_json()}\n\n"
        except AgentCancelledException:
            return
        except Exception as e:
            logger.error(f"Unexpected error in agent stream generator: {e}", exc_info=True)
            yield f"data: {AgentSSEEvent.create_error('ERR-AGT-500', 'An error occurred while processing your request.', conversation_id=conversation_id).model_dump_json()}\n\n"
        finally:
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
