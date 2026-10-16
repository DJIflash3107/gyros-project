from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.configs.database import get_db
from app.models.user import User
from app.models.schemas.business import BusinessCreate, BusinessUpdate
from app.models.schemas.pagination import PaginationParams
from app.middlewares.auth import get_current_user, require_business_membership
from app.handlers import business_handler

router = APIRouter(prefix="/api/v1/businesses", tags=["Businesses"])


@router.post("", status_code=201)
def create_business(
    data: BusinessCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return business_handler.create_business_handler(data, current_user, db)


@router.get("")
def list_businesses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    params = PaginationParams(page=page, page_size=page_size)
    return business_handler.list_businesses_handler(params, current_user, db)


@router.get("/{business_id}", dependencies=[Depends(require_business_membership())])
def get_business(
    business_id: int,
    db: Session = Depends(get_db),
):
    return business_handler.get_business_handler(business_id, db)


@router.patch("/{business_id}", dependencies=[Depends(require_business_membership(["owner", "admin"]))])
def update_business(
    business_id: int,
    data: BusinessUpdate,
    db: Session = Depends(get_db),
):
    return business_handler.update_business_handler(business_id, data, db)


@router.delete("/{business_id}", dependencies=[Depends(require_business_membership(["owner"]))])
def delete_business(
    business_id: int,
    db: Session = Depends(get_db),
):
    return business_handler.delete_business_handler(business_id, db)
