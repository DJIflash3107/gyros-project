from typing import Dict, Any
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.schemas.promotion import (
    GeneratePromotionRequest,
    UpdatePromotionStatusRequest,
    EvaluatePromotionRequest,
    PromotionPlanResponse,
)
from app.services import promotion_service
from app.helpers.response import success_response, paginated_response


async def generate_plan_handler(
    business_id: int,
    data: GeneratePromotionRequest,
    current_user: User,
    db: Session,
) -> JSONResponse:
    result = await promotion_service.generate_plan(
        db=db,
        business_id=business_id,
        request=data,
        user_id=current_user.id,
    )
    return success_response(
        message="Promotion plan generated successfully",
        data=result.model_dump(mode="json"),
        status_code=200,
    )


def list_plans_handler(
    business_id: int,
    filter_params: Dict[str, Any],
    db: Session,
) -> JSONResponse:
    items, pagination = promotion_service.list_plans(
        db=db,
        business_id=business_id,
        filter_params=filter_params,
    )
    return paginated_response(
        message="Promotion plans retrieved successfully",
        items=[PromotionPlanResponse.model_validate(p).model_dump(mode="json") for p in items],
        resource_key="plans",
        pagination=pagination,
    )


def get_plan_handler(
    business_id: int,
    plan_id: int,
    db: Session,
) -> JSONResponse:
    plan = promotion_service.get_plan(
        db=db,
        business_id=business_id,
        plan_id=plan_id,
    )
    return success_response(
        message="Promotion plan retrieved successfully",
        data={"plan": PromotionPlanResponse.model_validate(plan).model_dump(mode="json")},
        status_code=200,
    )


def update_plan_status_handler(
    business_id: int,
    plan_id: int,
    data: UpdatePromotionStatusRequest,
    current_user: User,
    db: Session,
) -> JSONResponse:
    plan = promotion_service.update_plan_status(
        db=db,
        business_id=business_id,
        plan_id=plan_id,
        request=data,
        user_id=current_user.id,
    )
    return success_response(
        message=f"Promotion plan status updated to {plan.status}",
        data={"plan": PromotionPlanResponse.model_validate(plan).model_dump(mode="json")},
        status_code=200,
    )


def evaluate_plan_handler(
    business_id: int,
    plan_id: int,
    data: EvaluatePromotionRequest,
    current_user: User,
    db: Session,
) -> JSONResponse:
    result = promotion_service.evaluate_plan(
        db=db,
        business_id=business_id,
        plan_id=plan_id,
        request=data,
        user_id=current_user.id,
    )
    return success_response(
        message="Promotion plan evaluated successfully",
        data=result.model_dump(mode="json"),
        status_code=200,
    )
