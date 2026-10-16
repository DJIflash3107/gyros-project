from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.configs.database import get_db
from app.models.user import User
from app.models.schemas.sales_report_submission import (
    SalesReportSubmissionCreate,
    SalesReportSubmissionUpdate,
)
from app.models.schemas.pagination import PaginationParams
from app.middlewares.auth import get_current_user, require_business_membership
from app.handlers import sales_report_submission_handler

router = APIRouter(
    prefix="/api/v1/businesses/{business_id}/sales_report_submissions",
    tags=["Sales Report Submissions"],
)


@router.post("", status_code=201, dependencies=[Depends(require_business_membership())])
def create_submission(
    business_id: int,
    data: SalesReportSubmissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return sales_report_submission_handler.create_submission_handler(business_id, data, current_user, db)


@router.get("", dependencies=[Depends(require_business_membership())])
def list_submissions(
    business_id: int,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    params = PaginationParams(page=page, page_size=page_size)
    return sales_report_submission_handler.list_submissions_handler(business_id, status, params, db)


@router.get("/{submission_id}", dependencies=[Depends(require_business_membership())])
def get_submission(
    business_id: int,
    submission_id: int,
    db: Session = Depends(get_db),
):
    return sales_report_submission_handler.get_submission_handler(business_id, submission_id, db)


@router.patch("/{submission_id}", dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def update_submission(
    business_id: int,
    submission_id: int,
    data: SalesReportSubmissionUpdate,
    db: Session = Depends(get_db),
):
    return sales_report_submission_handler.update_submission_handler(business_id, submission_id, data, db)


@router.delete("/{submission_id}", dependencies=[Depends(require_business_membership(["owner", "admin"]))])
def delete_submission(
    business_id: int,
    submission_id: int,
    db: Session = Depends(get_db),
):
    return sales_report_submission_handler.delete_submission_handler(business_id, submission_id, db)


@router.post("/{submission_id}/confirm", dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def confirm_submission(
    business_id: int,
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return sales_report_submission_handler.confirm_submission_handler(business_id, submission_id, current_user, db)
