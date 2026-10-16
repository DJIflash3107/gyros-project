from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.configs.database import get_db
from app.models.user import User
from app.models.schemas.import_issue import ImportIssueCreate, ImportIssueUpdate
from app.models.schemas.pagination import PaginationParams
from app.middlewares.auth import get_current_user
from app.handlers import import_issue_handler

router = APIRouter(
    prefix="/api/v1/sales_report_submissions/{submission_id}/import_issues",
    tags=["Import Issues"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", status_code=201)
def create_issue(
    submission_id: int,
    data: ImportIssueCreate,
    db: Session = Depends(get_db),
):
    return import_issue_handler.create_issue_handler(submission_id, data, db)


@router.get("")
def list_issues(
    submission_id: int,
    resolution_status: Optional[str] = None,
    severity: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    params = PaginationParams(page=page, page_size=page_size)
    return import_issue_handler.list_issues_handler(submission_id, resolution_status, severity, params, db)


@router.get("/{issue_id}")
def get_issue(
    submission_id: int,
    issue_id: int,
    db: Session = Depends(get_db),
):
    return import_issue_handler.get_issue_handler(submission_id, issue_id, db)


@router.patch("/{issue_id}")
def update_issue(
    submission_id: int,
    issue_id: int,
    data: ImportIssueUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return import_issue_handler.update_issue_handler(submission_id, issue_id, data, current_user, db)


@router.delete("/{issue_id}")
def delete_issue(
    submission_id: int,
    issue_id: int,
    db: Session = Depends(get_db),
):
    return import_issue_handler.delete_issue_handler(submission_id, issue_id, db)
