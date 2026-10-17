from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.configs.database import get_db
from app.models.schemas.product import ProductCreate, ProductUpdate, ProductActivate
from app.models.schemas.pagination import PaginationParams
from app.middlewares.auth import require_business_membership
from app.handlers import product_handler

router = APIRouter(
    prefix="/api/v1/businesses/{business_id}/products",
    tags=["Products"],
)


@router.post("", status_code=201, dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def create_product(
    business_id: int,
    data: ProductCreate,
    db: Session = Depends(get_db),
):
    return product_handler.create_product_handler(business_id, data, db)


@router.get("", dependencies=[Depends(require_business_membership())])
def list_products(
    business_id: int,
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    params = PaginationParams(page=page, page_size=page_size)
    return product_handler.list_products_handler(business_id, category, is_active, status, params, db)


@router.post("/{product_id}/activate", dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def activate_product(
    business_id: int,
    product_id: int,
    data: ProductActivate,
    db: Session = Depends(get_db),
):
    return product_handler.activate_product_handler(business_id, product_id, data, db)


@router.get("/{product_id}", dependencies=[Depends(require_business_membership())])
def get_product(
    business_id: int,
    product_id: int,
    db: Session = Depends(get_db),
):
    return product_handler.get_product_handler(business_id, product_id, db)


@router.patch("/{product_id}", dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def update_product(
    business_id: int,
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
):
    return product_handler.update_product_handler(business_id, product_id, data, db)


@router.delete("/{product_id}", dependencies=[Depends(require_business_membership(["owner", "admin"]))])
def delete_product(
    business_id: int,
    product_id: int,
    db: Session = Depends(get_db),
):
    return product_handler.delete_product_handler(business_id, product_id, db)
