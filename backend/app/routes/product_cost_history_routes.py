from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.configs.database import get_db
from app.models.user import User
from app.models.schemas.product_cost_history import (
    ProductCostHistoryCreate,
    ProductCostHistoryUpdate,
)
from app.models.schemas.pagination import PaginationParams
from app.middlewares.auth import get_current_user, require_business_membership
from app.handlers import product_cost_history_handler

router = APIRouter(
    prefix="/api/v1/businesses/{business_id}/product_cost_history",
    tags=["Product Cost History"],
)


@router.post("", status_code=201, dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def create_cost_history(
    business_id: int,
    data: ProductCostHistoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return product_cost_history_handler.create_cost_history_handler(business_id, data, current_user, db)


@router.get("", dependencies=[Depends(require_business_membership())])
def list_cost_history(
    business_id: int,
    product_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    params = PaginationParams(page=page, page_size=page_size)
    return product_cost_history_handler.list_cost_history_handler(business_id, product_id, params, db)


@router.get("/{cost_id}", dependencies=[Depends(require_business_membership())])
def get_cost_history(
    business_id: int,
    cost_id: int,
    db: Session = Depends(get_db),
):
    return product_cost_history_handler.get_cost_history_handler(business_id, cost_id, db)


@router.patch("/{cost_id}", dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def update_cost_history(
    business_id: int,
    cost_id: int,
    data: ProductCostHistoryUpdate,
    db: Session = Depends(get_db),
):
    return product_cost_history_handler.update_cost_history_handler(business_id, cost_id, data, db)


@router.delete("/{cost_id}", dependencies=[Depends(require_business_membership(["owner", "admin"]))])
def delete_cost_history(
    business_id: int,
    cost_id: int,
    db: Session = Depends(get_db),
):
    return product_cost_history_handler.delete_cost_history_handler(business_id, cost_id, db)
