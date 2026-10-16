from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.sales_report_submission import SalesReportSubmission
from app.models.import_issue import ImportIssue
from app.models.user import User
from app.models.schemas.import_issue import ImportIssueCreate, ImportIssueUpdate
from app.helpers.exceptions import NotFoundException
from app.helpers.pagination import paginate_query


def create_issue(
    db: Session,
    submission_id: int,
    data: ImportIssueCreate,
) -> ImportIssue:
    submission = db.query(SalesReportSubmission).filter(
        SalesReportSubmission.id == submission_id
    ).first()
    if not submission:
        raise NotFoundException(
            message="Submission not found",
            errors={"submission_id": f"Submission with ID {submission_id} does not exist"},
        )

    issue = ImportIssue(
        submission_id=submission_id,
        staging_row_id=data.staging_row_id,
        source_row_number=data.source_row_number,
        field_name=data.field_name,
        issue_code=data.issue_code,
        severity=data.severity,
        message=data.message,
        raw_value=data.raw_value,
        resolution_status=data.resolution_status,
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue


def list_issues(
    db: Session,
    submission_id: int,
    resolution_status: Optional[str] = None,
    severity: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[list[ImportIssue], dict]:
    query = db.query(ImportIssue).filter(ImportIssue.submission_id == submission_id)
    if resolution_status:
        query = query.filter(ImportIssue.resolution_status == resolution_status)
    if severity:
        query = query.filter(ImportIssue.severity == severity)
    query = query.order_by(ImportIssue.id.asc())
    return paginate_query(query, page, page_size)


def get_issue(db: Session, submission_id: int, issue_id: int) -> ImportIssue:
    issue = db.query(ImportIssue).filter(
        ImportIssue.id == issue_id,
        ImportIssue.submission_id == submission_id,
    ).first()
    if not issue:
        raise NotFoundException(
            message="Issue not found",
            errors={"issue": f"Issue with ID {issue_id} does not exist in this submission"},
        )
    return issue


def update_issue(
    db: Session,
    submission_id: int,
    issue_id: int,
    data: ImportIssueUpdate,
    current_user: User,
) -> ImportIssue:
    issue = get_issue(db, submission_id, issue_id)
    update_data = data.model_dump(exclude_unset=True)

    if "resolution_status" in update_data:
        issue.resolution_status = update_data["resolution_status"]
        if issue.resolution_status == "resolved":
            issue.resolved_by_user_id = current_user.id
            issue.resolved_at = datetime.now(timezone.utc)
        elif issue.resolution_status == "open":
            issue.resolved_by_user_id = None
            issue.resolved_at = None

    db.commit()
    db.refresh(issue)
    return issue


def delete_issue(db: Session, submission_id: int, issue_id: int) -> None:
    issue = get_issue(db, submission_id, issue_id)
    db.delete(issue)
    db.commit()
