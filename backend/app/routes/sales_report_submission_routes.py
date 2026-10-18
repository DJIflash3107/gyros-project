from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, File, Form, UploadFile
from sqlalchemy.orm import Session
from app.configs.database import get_db
from app.models.user import User
from app.models.schemas.sales_report_submission import (
    SalesReportSubmissionCreate,
    SalesReportSubmissionUpdate,
)
from app.models.schemas.sales_report_processing import ManualFormBatchCreate
from app.models.schemas.pagination import PaginationParams
from app.middlewares.auth import get_current_user, require_business_membership
from app.handlers import sales_report_submission_handler
from app.helpers.exceptions import ValidationException

router = APIRouter(
    prefix="/api/v1/businesses/{business_id}/sales_report_submissions",
    tags=["Sales Report Submissions"],
)


@router.post("/process", status_code=202, dependencies=[Depends(require_business_membership())])
async def process_submission(
    business_id: int,
    files: Optional[List[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
    input_method: str = Form(...),
    report_period_type: str = Form(...),
    coverage_start: date = Form(...),
    coverage_end: date = Form(...),
    branch_id: Optional[int] = Form(None),
    stream: Optional[bool] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    upload_files: List[UploadFile] = []
    if files:
        upload_files.extend(files)
    if file and file.filename:
        upload_files.append(file)
    if not upload_files:
        raise ValidationException(
            message="No upload file provided",
            errors={"file": "At least one file is required"},
        )

    return await sales_report_submission_handler.process_submission_handler(
        business_id=business_id,
        files=upload_files,
        input_method=input_method,
        report_period_type=report_period_type,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        branch_id=branch_id,
        current_user=current_user,
        db=db,
        stream=stream,
    )


@router.post("/batch_form", status_code=202, dependencies=[Depends(require_business_membership())])
def batch_form(
    business_id: int,
    data: ManualFormBatchCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return sales_report_submission_handler.batch_form_handler(business_id, data, current_user, db)


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


@router.post("/{submission_id}/confirm", status_code=202, dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def confirm_submission(
    business_id: int,
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return sales_report_submission_handler.confirm_submission_handler(business_id, submission_id, current_user, db)


