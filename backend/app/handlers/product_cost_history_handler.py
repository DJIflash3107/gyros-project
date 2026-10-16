from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.schemas.product_cost_history import (
    ProductCostHistoryCreate,
    ProductCostHistoryUpdate,
    ProductCostHistoryResponse,
)
from app.models.schemas.pagination import PaginationParams
from app.services import product_cost_history_service
from app.helpers.response import success_response, paginated_response


def create_cost_history_handler(
    business_id: int,
    data: ProductCostHistoryCreate,
    current_user: User,
    db: Session,
) -> JSONResponse:
    cost = product_cost_history_service.create_cost_history(db, business_id, data, current_user)
    return success_response(
        message="Product cost history created successfully",
        data={"cost_history": ProductCostHistoryResponse.model_validate(cost).model_dump()},
        status_code=201,
    )


def list_cost_history_handler(
    business_id: int,
    product_id: Optional[int],
    params: PaginationParams,
    db: Session,
) -> JSONResponse:
    items, pagination = product_cost_history_service.list_cost_history(db, business_id, product_id, params.page, params.page_size)
    response_items = [ProductCostHistoryResponse.model_validate(c).model_dump() for c in items]
    return paginated_response(
        message="Product cost histories retrieved successfully",
        items=response_items,
        resource_key="cost_histories",
        pagination=pagination,
    )


def get_cost_history_handler(business_id: int, cost_id: int, db: Session) -> JSONResponse:
    cost = product_cost_history_service.get_cost_history(db, business_id, cost_id)
    return success_response(
        message="Product cost history retrieved successfully",
        data={"cost_history": ProductCostHistoryResponse.model_validate(cost).model_dump()},
    )


def update_cost_history_handler(
    business_id: int,
    cost_id: int,
    data: ProductCostHistoryUpdate,
    db: Session,
) -> JSONResponse:
    cost = product_cost_history_service.update_cost_history(db, business_id, cost_id, data)
    return success_response(
        message="Product cost history updated successfully",
        data={"cost_history": ProductCostHistoryResponse.model_validate(cost).model_dump()},
    )


def delete_cost_history_handler(business_id: int, cost_id: int, db: Session) -> JSONResponse:
    product_cost_history_service.delete_cost_history(db, business_id, cost_id)
    return success_response(
        message="Product cost history deleted successfully",
        data={},
    )
