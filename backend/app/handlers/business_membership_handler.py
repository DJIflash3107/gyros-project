from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.schemas.business_membership import (
    BusinessMembershipCreate,
    BusinessMembershipUpdate,
    BusinessMembershipResponse,
)
from app.models.schemas.pagination import PaginationParams
from app.services import business_membership_service
from app.helpers.response import success_response, paginated_response


def create_membership_handler(business_id: int, data: BusinessMembershipCreate, db: Session) -> JSONResponse:
    membership = business_membership_service.create_membership(db, business_id, data)
    return success_response(
        message="Business membership created successfully",
        data={"membership": BusinessMembershipResponse.model_validate(membership).model_dump()},
        status_code=201,
    )


def list_memberships_handler(business_id: int, params: PaginationParams, db: Session) -> JSONResponse:
    items, pagination = business_membership_service.list_memberships(db, business_id, params.page, params.page_size)
    response_items = [BusinessMembershipResponse.model_validate(m).model_dump() for m in items]
    return paginated_response(
        message="Business memberships retrieved successfully",
        items=response_items,
        resource_key="memberships",
        pagination=pagination,
    )


def get_membership_handler(business_id: int, membership_id: int, db: Session) -> JSONResponse:
    membership = business_membership_service.get_membership(db, business_id, membership_id)
    return success_response(
        message="Business membership retrieved successfully",
        data={"membership": BusinessMembershipResponse.model_validate(membership).model_dump()},
    )


def update_membership_handler(business_id: int, membership_id: int, data: BusinessMembershipUpdate, db: Session) -> JSONResponse:
    membership = business_membership_service.update_membership(db, business_id, membership_id, data)
    return success_response(
        message="Business membership updated successfully",
        data={"membership": BusinessMembershipResponse.model_validate(membership).model_dump()},
    )


def delete_membership_handler(business_id: int, membership_id: int, db: Session) -> JSONResponse:
    business_membership_service.delete_membership(db, business_id, membership_id)
    return success_response(
        message="Business membership deleted successfully",
        data={},
    )
