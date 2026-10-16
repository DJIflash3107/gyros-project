from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.middlewares.auth import get_current_user, require_business_membership
from app.models.schemas.agent import AgentChatRequest
from app.models.user import User
from app.handlers.agent_handler import agent_chat_handler

router = APIRouter(
    prefix="/api/v1/agent/businesses/{business_id}",
    tags=["Agent"],
)


@router.post(
    "/chat",
    summary="Agent Chat Stream",
    description="Stream structured SSE events for Business Operations Agent conversations.",
    dependencies=[
        Depends(get_current_user),
        Depends(require_business_membership()),
    ],
)
async def chat(
    business_id: int,
    data: AgentChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await agent_chat_handler(
        business_id=business_id,
        data=data,
        request=request,
        db=db,
        current_user=current_user,
    )
