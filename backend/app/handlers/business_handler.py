from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.schemas.business import BusinessCreate, BusinessUpdate, BusinessResponse
from app.models.schemas.pagination import PaginationParams
from app.services import business_service
from app.helpers.response import success_response, paginated_response


def create_business_handler(data: BusinessCreate, current_user: User, db: Session) -> JSONResponse:
    business = business_service.create_business(db, data, current_user)
    return success_response(
        message="Business created successfully",
        data={"business": BusinessResponse.model_validate(business).model_dump()},
        status_code=201,
    )


def list_businesses_handler(params: PaginationParams, current_user: User, db: Session) -> JSONResponse:
    items, pagination = business_service.list_businesses(db, current_user, params.page, params.page_size)
    response_items = [BusinessResponse.model_validate(b).model_dump() for b in items]
    return paginated_response(
        message="Businesses retrieved successfully",
        items=response_items,
        resource_key="businesses",
        pagination=pagination,
    )


def get_business_handler(business_id: int, db: Session) -> JSONResponse:
    business = business_service.get_business(db, business_id)
    return success_response(
        message="Business retrieved successfully",
        data={"business": BusinessResponse.model_validate(business).model_dump()},
    )


def update_business_handler(business_id: int, data: BusinessUpdate, db: Session) -> JSONResponse:
    business = business_service.update_business(db, business_id, data)
    return success_response(
        message="Business updated successfully",
        data={"business": BusinessResponse.model_validate(business).model_dump()},
    )


def delete_business_handler(business_id: int, db: Session) -> JSONResponse:
    business_service.delete_business(db, business_id)
    return success_response(
        message="Business deleted successfully",
        data={},
    )
