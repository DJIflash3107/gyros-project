from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.configs.database import get_db
from app.models.user import User
from app.models.schemas.sales_report_observation import (
    SalesReportObservationCreate,
    SalesReportObservationUpdate,
)
from app.models.schemas.pagination import PaginationParams
from app.middlewares.auth import get_current_user, require_business_membership
from app.handlers import sales_report_observation_handler

router = APIRouter(
    prefix="/api/v1/businesses/{business_id}/sales_report_observations",
    tags=["Sales Report Observations"],
)


@router.post("", status_code=201, dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def create_observation(
    business_id: int,
    data: SalesReportObservationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return sales_report_observation_handler.create_observation_handler(business_id, data, current_user, db)


@router.get("", dependencies=[Depends(require_business_membership())])
def list_observations(
    business_id: int,
    branch_id: Optional[int] = None,
    product_id: Optional[int] = None,
    record_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    params = PaginationParams(page=page, page_size=page_size)
    return sales_report_observation_handler.list_observations_handler(
        business_id, branch_id, product_id, record_status, params, db
    )


@router.get("/{observation_id}", dependencies=[Depends(require_business_membership())])
def get_observation(
    business_id: int,
    observation_id: int,
    db: Session = Depends(get_db),
):
    return sales_report_observation_handler.get_observation_handler(business_id, observation_id, db)


@router.patch("/{observation_id}", dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def update_observation(
    business_id: int,
    observation_id: int,
    data: SalesReportObservationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return sales_report_observation_handler.update_observation_handler(
        business_id, observation_id, data, current_user, db
    )


@router.delete("/{observation_id}", dependencies=[Depends(require_business_membership(["owner", "admin"]))])
def delete_observation(
    business_id: int,
    observation_id: int,
    db: Session = Depends(get_db),
):
    return sales_report_observation_handler.delete_observation_handler(business_id, observation_id, db)
