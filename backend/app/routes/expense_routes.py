from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, File, Form, UploadFile
from sqlalchemy.orm import Session
from app.configs.database import get_db
from app.models.user import User
from app.models.schemas.expense import (
    ExpenseCreate,
    ExpenseBatchCreate,
    ExpenseUpdate,
    ExpenseReviewRequest,
)
from app.models.schemas.pagination import PaginationParams
from app.middlewares.auth import get_current_user, require_business_membership
from app.handlers import expense_handler
from app.helpers.exceptions import ValidationException

router = APIRouter(
    prefix="/api/v1/businesses/{business_id}/expenses",
    tags=["Expenses"],
)


@router.post("/import", status_code=202, dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
async def import_expenses(
    business_id: int,
    files: Optional[List[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
    input_method: str = Form("spreadsheet"),
    branch_id: Optional[int] = Form(None),
    default_date: Optional[date] = Form(None),
    source_submission_id: Optional[int] = Form(None),
    persist: Optional[bool] = Form(None),
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

    return await expense_handler.import_expenses_handler(
        business_id=business_id,
        files=upload_files,
        input_method=input_method,
        branch_id=branch_id,
        default_date=default_date,
        current_user=current_user,
        db=db,
        source_submission_id=source_submission_id,
    )


@router.post("/approve", status_code=200, dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def approve_expenses(
    business_id: int,
    data: ExpenseReviewRequest,
    db: Session = Depends(get_db),
):
    return expense_handler.approve_expenses_handler(business_id, data, db)


@router.post("/discard", status_code=200, dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def discard_expenses(
    business_id: int,
    data: ExpenseReviewRequest,
    db: Session = Depends(get_db),
):
    return expense_handler.discard_expenses_handler(business_id, data, db)


@router.post("/batch", status_code=202, dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def create_expenses_batch(
    business_id: int,
    data: ExpenseBatchCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Save multiple expense records in a single atomic batch transaction.
    Ideal for saving or committing expenses after inspecting and correcting previewed import data.
    """
    return expense_handler.create_expenses_batch_handler(business_id, data, current_user, db)


@router.post("", status_code=201, dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def create_expense(
    business_id: int,
    data: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return expense_handler.create_expense_handler(business_id, data, current_user, db)


@router.get("", dependencies=[Depends(require_business_membership())])
def list_expenses(
    business_id: int,
    branch_id: Optional[int] = None,
    category: Optional[str] = None,
    status: Optional[str] = Query(None, description="Filter by status: draft, ready, active, or all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    params = PaginationParams(page=page, page_size=page_size)
    return expense_handler.list_expenses_handler(business_id, branch_id, category, status, params, db)


@router.get("/{expense_id}", dependencies=[Depends(require_business_membership())])
def get_expense(
    business_id: int,
    expense_id: int,
    db: Session = Depends(get_db),
):
    return expense_handler.get_expense_handler(business_id, expense_id, db)


@router.patch("/{expense_id}", dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def update_expense(
    business_id: int,
    expense_id: int,
    data: ExpenseUpdate,
    db: Session = Depends(get_db),
):
    return expense_handler.update_expense_handler(business_id, expense_id, data, db)


@router.delete("/{expense_id}", dependencies=[Depends(require_business_membership(["owner", "admin"]))])
def delete_expense(
    business_id: int,
    expense_id: int,
    db: Session = Depends(get_db),
):
    return expense_handler.delete_expense_handler(business_id, expense_id, db)

