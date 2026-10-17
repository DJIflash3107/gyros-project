from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.configs.database import get_db
from app.models.schemas.branch import BranchCreate, BranchUpdate, BranchActivate
from app.models.schemas.pagination import PaginationParams
from app.middlewares.auth import require_business_membership
from app.handlers import branch_handler

router = APIRouter(
    prefix="/api/v1/businesses/{business_id}/branches",
    tags=["Branches"],
)


@router.post("", status_code=201, dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def create_branch(
    business_id: int,
    data: BranchCreate,
    db: Session = Depends(get_db),
):
    return branch_handler.create_branch_handler(business_id, data, db)


@router.get("", dependencies=[Depends(require_business_membership())])
def list_branches(
    business_id: int,
    is_active: Optional[bool] = None,
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    params = PaginationParams(page=page, page_size=page_size)
    return branch_handler.list_branches_handler(business_id, is_active, status, params, db)


@router.post("/{branch_id}/activate", dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def activate_branch(
    business_id: int,
    branch_id: int,
    data: BranchActivate,
    db: Session = Depends(get_db),
):
    return branch_handler.activate_branch_handler(business_id, branch_id, data, db)


@router.get("/{branch_id}", dependencies=[Depends(require_business_membership())])
def get_branch(
    business_id: int,
    branch_id: int,
    db: Session = Depends(get_db),
):
    return branch_handler.get_branch_handler(business_id, branch_id, db)


@router.patch("/{branch_id}", dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def update_branch(
    business_id: int,
    branch_id: int,
    data: BranchUpdate,
    db: Session = Depends(get_db),
):
    return branch_handler.update_branch_handler(business_id, branch_id, data, db)


@router.delete("/{branch_id}", dependencies=[Depends(require_business_membership(["owner", "admin"]))])
def delete_branch(
    business_id: int,
    branch_id: int,
    db: Session = Depends(get_db),
):
    return branch_handler.delete_branch_handler(business_id, branch_id, db)
