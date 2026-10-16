from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.schemas.import_issue import (
    ImportIssueCreate,
    ImportIssueUpdate,
    ImportIssueResponse,
)
from app.models.schemas.pagination import PaginationParams
from app.services import import_issue_service
from app.helpers.response import success_response, paginated_response


def create_issue_handler(
    submission_id: int,
    data: ImportIssueCreate,
    db: Session,
) -> JSONResponse:
    issue = import_issue_service.create_issue(db, submission_id, data)
    return success_response(
        message="Import issue created successfully",
        data={"issue": ImportIssueResponse.model_validate(issue).model_dump()},
        status_code=201,
    )


def list_issues_handler(
    submission_id: int,
    resolution_status: Optional[str],
    severity: Optional[str],
    params: PaginationParams,
    db: Session,
) -> JSONResponse:
    items, pagination = import_issue_service.list_issues(db, submission_id, resolution_status, severity, params.page, params.page_size)
    response_items = [ImportIssueResponse.model_validate(i).model_dump() for i in items]
    return paginated_response(
        message="Import issues retrieved successfully",
        items=response_items,
        resource_key="issues",
        pagination=pagination,
    )


def get_issue_handler(submission_id: int, issue_id: int, db: Session) -> JSONResponse:
    issue = import_issue_service.get_issue(db, submission_id, issue_id)
    return success_response(
        message="Import issue retrieved successfully",
        data={"issue": ImportIssueResponse.model_validate(issue).model_dump()},
    )


def update_issue_handler(
    submission_id: int,
    issue_id: int,
    data: ImportIssueUpdate,
    current_user: User,
    db: Session,
) -> JSONResponse:
    issue = import_issue_service.update_issue(db, submission_id, issue_id, data, current_user)
    return success_response(
        message="Import issue updated successfully",
        data={"issue": ImportIssueResponse.model_validate(issue).model_dump()},
    )


def delete_issue_handler(submission_id: int, issue_id: int, db: Session) -> JSONResponse:
    import_issue_service.delete_issue(db, submission_id, issue_id)
    return success_response(
        message="Import issue deleted successfully",
        data={},
    )
