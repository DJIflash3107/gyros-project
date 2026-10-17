from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.schemas.branch import BranchCreate, BranchUpdate, BranchResponse, BranchActivate
from app.models.schemas.pagination import PaginationParams
from app.services import branch_service
from app.helpers.response import success_response, paginated_response


def create_branch_handler(business_id: int, data: BranchCreate, db: Session) -> JSONResponse:
    branch = branch_service.create_branch(db, business_id, data)
    return success_response(
        message="Branch created successfully",
        data={"branch": BranchResponse.model_validate(branch).model_dump()},
        status_code=201,
    )


def list_branches_handler(
    business_id: int,
    is_active: Optional[bool],
    status: Optional[str],
    params: PaginationParams,
    db: Session,
) -> JSONResponse:
    items, pagination = branch_service.list_branches(db, business_id, is_active, status, params.page, params.page_size)
    response_items = [BranchResponse.model_validate(b).model_dump() for b in items]
    return paginated_response(
        message="Branches retrieved successfully",
        items=response_items,
        resource_key="branches",
        pagination=pagination,
    )


def activate_branch_handler(
    business_id: int,
    branch_id: int,
    data: BranchActivate,
    db: Session,
) -> JSONResponse:
    branch = branch_service.activate_draft_branch(db, business_id, branch_id, data)
    return success_response(
        message="Branch activated successfully",
        data={"branch": BranchResponse.model_validate(branch).model_dump()},
    )


def get_branch_handler(business_id: int, branch_id: int, db: Session) -> JSONResponse:
    branch = branch_service.get_branch(db, business_id, branch_id)
    return success_response(
        message="Branch retrieved successfully",
        data={"branch": BranchResponse.model_validate(branch).model_dump()},
    )


def update_branch_handler(business_id: int, branch_id: int, data: BranchUpdate, db: Session) -> JSONResponse:
    branch = branch_service.update_branch(db, business_id, branch_id, data)
    return success_response(
        message="Branch updated successfully",
        data={"branch": BranchResponse.model_validate(branch).model_dump()},
    )


def delete_branch_handler(business_id: int, branch_id: int, db: Session) -> JSONResponse:
    branch_service.delete_branch(db, business_id, branch_id)
    return success_response(
        message="Branch deleted successfully",
        data={},
    )
