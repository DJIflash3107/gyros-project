from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.configs.database import get_db
from app.models.user import User
from app.models.schemas.product_alias import ProductAliasCreate, ProductAliasUpdate
from app.models.schemas.pagination import PaginationParams
from app.middlewares.auth import get_current_user, require_business_membership
from app.handlers import product_alias_handler

router = APIRouter(
    prefix="/api/v1/businesses/{business_id}/product_aliases",
    tags=["Product Aliases"],
)


@router.post("", status_code=201, dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def create_alias(
    business_id: int,
    data: ProductAliasCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return product_alias_handler.create_alias_handler(business_id, data, current_user, db)


@router.get("", dependencies=[Depends(require_business_membership())])
def list_aliases(
    business_id: int,
    product_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    params = PaginationParams(page=page, page_size=page_size)
    return product_alias_handler.list_aliases_handler(business_id, product_id, params, db)


@router.get("/{alias_id}", dependencies=[Depends(require_business_membership())])
def get_alias(
    business_id: int,
    alias_id: int,
    db: Session = Depends(get_db),
):
    return product_alias_handler.get_alias_handler(business_id, alias_id, db)


@router.patch("/{alias_id}", dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def update_alias(
    business_id: int,
    alias_id: int,
    data: ProductAliasUpdate,
    db: Session = Depends(get_db),
):
    return product_alias_handler.update_alias_handler(business_id, alias_id, data, db)


@router.delete("/{alias_id}", dependencies=[Depends(require_business_membership(["owner", "admin"]))])
def delete_alias(
    business_id: int,
    alias_id: int,
    db: Session = Depends(get_db),
):
    return product_alias_handler.delete_alias_handler(business_id, alias_id, db)
