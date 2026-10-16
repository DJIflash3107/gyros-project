from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.configs.database import get_db
from app.models.schemas.business_membership import BusinessMembershipCreate, BusinessMembershipUpdate
from app.models.schemas.pagination import PaginationParams
from app.middlewares.auth import require_business_membership
from app.handlers import business_membership_handler

router = APIRouter(
    prefix="/api/v1/businesses/{business_id}/memberships",
    tags=["Business Memberships"],
)


@router.post("", status_code=201, dependencies=[Depends(require_business_membership(["owner", "admin"]))])
def create_membership(
    business_id: int,
    data: BusinessMembershipCreate,
    db: Session = Depends(get_db),
):
    return business_membership_handler.create_membership_handler(business_id, data, db)


@router.get("", dependencies=[Depends(require_business_membership())])
def list_memberships(
    business_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    params = PaginationParams(page=page, page_size=page_size)
    return business_membership_handler.list_memberships_handler(business_id, params, db)


@router.get("/{membership_id}", dependencies=[Depends(require_business_membership())])
def get_membership(
    business_id: int,
    membership_id: int,
    db: Session = Depends(get_db),
):
    return business_membership_handler.get_membership_handler(business_id, membership_id, db)


@router.patch("/{membership_id}", dependencies=[Depends(require_business_membership(["owner", "admin"]))])
def update_membership(
    business_id: int,
    membership_id: int,
    data: BusinessMembershipUpdate,
    db: Session = Depends(get_db),
):
    return business_membership_handler.update_membership_handler(business_id, membership_id, data, db)


@router.delete("/{membership_id}", dependencies=[Depends(require_business_membership(["owner", "admin"]))])
def delete_membership(
    business_id: int,
    membership_id: int,
    db: Session = Depends(get_db),
):
    return business_membership_handler.delete_membership_handler(business_id, membership_id, db)
