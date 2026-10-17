from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.schemas.product import ProductCreate, ProductUpdate, ProductResponse, ProductActivate
from app.models.schemas.pagination import PaginationParams
from app.services import product_service
from app.helpers.response import success_response, paginated_response


def create_product_handler(business_id: int, data: ProductCreate, db: Session) -> JSONResponse:
    product = product_service.create_product(db, business_id, data)
    return success_response(
        message="Product created successfully",
        data={"product": ProductResponse.model_validate(product).model_dump()},
        status_code=201,
    )


def list_products_handler(
    business_id: int,
    category: Optional[str],
    is_active: Optional[bool],
    status: Optional[str],
    params: PaginationParams,
    db: Session,
) -> JSONResponse:
    items, pagination = product_service.list_products(db, business_id, category, is_active, status, params.page, params.page_size)
    response_items = [ProductResponse.model_validate(p).model_dump() for p in items]
    return paginated_response(
        message="Products retrieved successfully",
        items=response_items,
        resource_key="products",
        pagination=pagination,
    )


def activate_product_handler(
    business_id: int,
    product_id: int,
    data: ProductActivate,
    db: Session,
) -> JSONResponse:
    product = product_service.activate_draft_product(db, business_id, product_id, data)
    return success_response(
        message="Product activated successfully",
        data={"product": ProductResponse.model_validate(product).model_dump()},
    )


def get_product_handler(business_id: int, product_id: int, db: Session) -> JSONResponse:
    product = product_service.get_product(db, business_id, product_id)
    return success_response(
        message="Product retrieved successfully",
        data={"product": ProductResponse.model_validate(product).model_dump()},
    )


def update_product_handler(business_id: int, product_id: int, data: ProductUpdate, db: Session) -> JSONResponse:
    product = product_service.update_product(db, business_id, product_id, data)
    return success_response(
        message="Product updated successfully",
        data={"product": ProductResponse.model_validate(product).model_dump()},
    )


def delete_product_handler(business_id: int, product_id: int, db: Session) -> JSONResponse:
    product_service.delete_product(db, business_id, product_id)
    return success_response(
        message="Product deleted successfully",
        data={},
    )
