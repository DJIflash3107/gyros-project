from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.models.user import User
from app.configs.database import get_db
from app.models.schemas.sales_report_staging_row import (
    SalesReportStagingRowCreate,
    SalesReportStagingRowUpdate,
    SalesReportStagingRowBulkUpdate,
)
from app.models.schemas.pagination import PaginationParams
from app.middlewares.auth import get_current_user
from app.handlers import sales_report_staging_row_handler

router = APIRouter(
    prefix="/api/v1/sales_report_submissions/{submission_id}/staging_rows",
    tags=["Sales Report Staging Rows"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", status_code=201)
def create_staging_row(
    submission_id: int,
    data: SalesReportStagingRowCreate,
    db: Session = Depends(get_db),
):
    return sales_report_staging_row_handler.create_staging_row_handler(submission_id, data, db)


@router.get("")
def list_staging_rows(
    submission_id: int,
    review_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    params = PaginationParams(page=page, page_size=page_size)
    return sales_report_staging_row_handler.list_staging_rows_handler(submission_id, review_status, params, db)


@router.patch("/bulk", status_code=202)
@router.post("/bulk", status_code=202)
def bulk_update_staging_rows(
    submission_id: int,
    data: SalesReportStagingRowBulkUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return sales_report_staging_row_handler.bulk_update_staging_rows_handler(submission_id, data, db, current_user.id)

@router.get("/{row_id}")
def get_staging_row(
    submission_id: int,
    row_id: int,
    db: Session = Depends(get_db),
):
    return sales_report_staging_row_handler.get_staging_row_handler(submission_id, row_id, db)


@router.patch("/{row_id}")
def update_staging_row(
    submission_id: int,
    row_id: int,
    data: SalesReportStagingRowUpdate,
    db: Session = Depends(get_db),
):
    return sales_report_staging_row_handler.update_staging_row_handler(submission_id, row_id, data, db)


@router.delete("/{row_id}")
def delete_staging_row(
    submission_id: int,
    row_id: int,
    db: Session = Depends(get_db),
):
    return sales_report_staging_row_handler.delete_staging_row_handler(submission_id, row_id, db)





