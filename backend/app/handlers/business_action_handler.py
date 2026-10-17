from typing import Dict, Any
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.schemas.business_action import (
    GenerateActionsRequest,
    UpdateActionStatusRequest,
    BusinessActionResponse,
)
from app.services import business_action_service
from app.helpers.response import success_response, paginated_response


async def generate_actions_handler(
    business_id: int,
    data: GenerateActionsRequest,
    current_user: User,
    db: Session,
) -> JSONResponse:
    result = await business_action_service.generate_actions(
        db=db,
        business_id=business_id,
        request=data,
        user_id=current_user.id,
    )
    return success_response(
        message="Recommendations generated successfully",
        data=result.model_dump(mode="json"),
        status_code=200,
    )


def list_actions_handler(
    business_id: int,
    filter_params: Dict[str, Any],
    db: Session,
) -> JSONResponse:
    items, pagination = business_action_service.list_actions(
        db=db,
        business_id=business_id,
        filter_params=filter_params,
    )
    return paginated_response(
        message="Business actions retrieved successfully",
        items=[BusinessActionResponse.model_validate(a).model_dump(mode="json") for a in items],
        resource_key="actions",
        pagination=pagination,
    )


def get_action_handler(
    business_id: int,
    action_id: int,
    db: Session,
) -> JSONResponse:
    action = business_action_service.get_action(
        db=db,
        business_id=business_id,
        action_id=action_id,
    )
    return success_response(
        message="Business action retrieved successfully",
        data={"action": BusinessActionResponse.model_validate(action).model_dump(mode="json")},
        status_code=200,
    )


def update_action_status_handler(
    business_id: int,
    action_id: int,
    data: UpdateActionStatusRequest,
    current_user: User,
    db: Session,
) -> JSONResponse:
    action = business_action_service.update_action_status(
        db=db,
        business_id=business_id,
        action_id=action_id,
        request=data,
        user_id=current_user.id,
    )
    return success_response(
        message=f"Action status updated to '{data.status}'",
        data={"action": BusinessActionResponse.model_validate(action).model_dump(mode="json")},
        status_code=200,
    )
