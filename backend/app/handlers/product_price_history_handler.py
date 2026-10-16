from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.schemas.product_price_history import (
    ProductPriceHistoryCreate,
    ProductPriceHistoryUpdate,
    ProductPriceHistoryResponse,
)
from app.models.schemas.pagination import PaginationParams
from app.services import product_price_history_service
from app.helpers.response import success_response, paginated_response


def create_price_history_handler(
    business_id: int,
    data: ProductPriceHistoryCreate,
    current_user: User,
    db: Session,
) -> JSONResponse:
    price = product_price_history_service.create_price_history(db, business_id, data, current_user)
    return success_response(
        message="Product price history created successfully",
        data={"price_history": ProductPriceHistoryResponse.model_validate(price).model_dump()},
        status_code=201,
    )


def list_price_history_handler(
    business_id: int,
    product_id: Optional[int],
    params: PaginationParams,
    db: Session,
) -> JSONResponse:
    items, pagination = product_price_history_service.list_price_history(db, business_id, product_id, params.page, params.page_size)
    response_items = [ProductPriceHistoryResponse.model_validate(p).model_dump() for p in items]
    return paginated_response(
        message="Product price histories retrieved successfully",
        items=response_items,
        resource_key="price_histories",
        pagination=pagination,
    )


def get_price_history_handler(business_id: int, price_id: int, db: Session) -> JSONResponse:
    price = product_price_history_service.get_price_history(db, business_id, price_id)
    return success_response(
        message="Product price history retrieved successfully",
        data={"price_history": ProductPriceHistoryResponse.model_validate(price).model_dump()},
    )


def update_price_history_handler(
    business_id: int,
    price_id: int,
    data: ProductPriceHistoryUpdate,
    db: Session,
) -> JSONResponse:
    price = product_price_history_service.update_price_history(db, business_id, price_id, data)
    return success_response(
        message="Product price history updated successfully",
        data={"price_history": ProductPriceHistoryResponse.model_validate(price).model_dump()},
    )


def delete_price_history_handler(business_id: int, price_id: int, db: Session) -> JSONResponse:
    product_price_history_service.delete_price_history(db, business_id, price_id)
    return success_response(
        message="Product price history deleted successfully",
        data={},
    )
