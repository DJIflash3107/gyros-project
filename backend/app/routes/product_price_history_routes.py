from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.configs.database import get_db
from app.models.user import User
from app.models.schemas.product_price_history import (
    ProductPriceHistoryCreate,
    ProductPriceHistoryUpdate,
)
from app.models.schemas.pagination import PaginationParams
from app.middlewares.auth import get_current_user, require_business_membership
from app.handlers import product_price_history_handler

router = APIRouter(
    prefix="/api/v1/businesses/{business_id}/product_price_history",
    tags=["Product Price History"],
)


@router.post("", status_code=201, dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def create_price_history(
    business_id: int,
    data: ProductPriceHistoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return product_price_history_handler.create_price_history_handler(business_id, data, current_user, db)


@router.get("", dependencies=[Depends(require_business_membership())])
def list_price_history(
    business_id: int,
    product_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    params = PaginationParams(page=page, page_size=page_size)
    return product_price_history_handler.list_price_history_handler(business_id, product_id, params, db)


@router.get("/{price_id}", dependencies=[Depends(require_business_membership())])
def get_price_history(
    business_id: int,
    price_id: int,
    db: Session = Depends(get_db),
):
    return product_price_history_handler.get_price_history_handler(business_id, price_id, db)


@router.patch("/{price_id}", dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def update_price_history(
    business_id: int,
    price_id: int,
    data: ProductPriceHistoryUpdate,
    db: Session = Depends(get_db),
):
    return product_price_history_handler.update_price_history_handler(business_id, price_id, data, db)


@router.delete("/{price_id}", dependencies=[Depends(require_business_membership(["owner", "admin"]))])
def delete_price_history(
    business_id: int,
    price_id: int,
    db: Session = Depends(get_db),
):
    return product_price_history_handler.delete_price_history_handler(business_id, price_id, db)
