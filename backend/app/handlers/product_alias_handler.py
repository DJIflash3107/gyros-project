from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.schemas.product_alias import ProductAliasCreate, ProductAliasUpdate, ProductAliasResponse
from app.models.schemas.pagination import PaginationParams
from app.services import product_alias_service
from app.helpers.response import success_response, paginated_response


def create_alias_handler(
    business_id: int,
    data: ProductAliasCreate,
    current_user: User,
    db: Session,
) -> JSONResponse:
    alias = product_alias_service.create_alias(db, business_id, data, current_user)
    return success_response(
        message="Product alias created successfully",
        data={"alias": ProductAliasResponse.model_validate(alias).model_dump()},
        status_code=201,
    )


def list_aliases_handler(
    business_id: int,
    product_id: Optional[int],
    params: PaginationParams,
    db: Session,
) -> JSONResponse:
    items, pagination = product_alias_service.list_aliases(db, business_id, product_id, params.page, params.page_size)
    response_items = [ProductAliasResponse.model_validate(a).model_dump() for a in items]
    return paginated_response(
        message="Product aliases retrieved successfully",
        items=response_items,
        resource_key="aliases",
        pagination=pagination,
    )


def get_alias_handler(business_id: int, alias_id: int, db: Session) -> JSONResponse:
    alias = product_alias_service.get_alias(db, business_id, alias_id)
    return success_response(
        message="Product alias retrieved successfully",
        data={"alias": ProductAliasResponse.model_validate(alias).model_dump()},
    )


def update_alias_handler(
    business_id: int,
    alias_id: int,
    data: ProductAliasUpdate,
    db: Session,
) -> JSONResponse:
    alias = product_alias_service.update_alias(db, business_id, alias_id, data)
    return success_response(
        message="Product alias updated successfully",
        data={"alias": ProductAliasResponse.model_validate(alias).model_dump()},
    )


def delete_alias_handler(business_id: int, alias_id: int, db: Session) -> JSONResponse:
    product_alias_service.delete_alias(db, business_id, alias_id)
    return success_response(
        message="Product alias deleted successfully",
        data={},
    )
