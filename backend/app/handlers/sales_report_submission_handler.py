from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.schemas.sales_report_submission import (
    SalesReportSubmissionCreate,
    SalesReportSubmissionUpdate,
    SalesReportSubmissionResponse,
)
from app.models.schemas.pagination import PaginationParams
from app.services import sales_report_submission_service
from app.helpers.response import success_response, paginated_response


def create_submission_handler(
    business_id: int,
    data: SalesReportSubmissionCreate,
    current_user: User,
    db: Session,
) -> JSONResponse:
    submission = sales_report_submission_service.create_submission(db, business_id, data, current_user)
    return success_response(
        message="Sales report submission created successfully",
        data={"submission": SalesReportSubmissionResponse.model_validate(submission).model_dump()},
        status_code=201,
    )


def list_submissions_handler(
    business_id: int,
    status: Optional[str],
    params: PaginationParams,
    db: Session,
) -> JSONResponse:
    items, pagination = sales_report_submission_service.list_submissions(db, business_id, status, params.page, params.page_size)
    response_items = [SalesReportSubmissionResponse.model_validate(s).model_dump() for s in items]
    return paginated_response(
        message="Sales report submissions retrieved successfully",
        items=response_items,
        resource_key="submissions",
        pagination=pagination,
    )


def get_submission_handler(business_id: int, submission_id: int, db: Session) -> JSONResponse:
    submission = sales_report_submission_service.get_submission(db, business_id, submission_id)
    return success_response(
        message="Sales report submission retrieved successfully",
        data={"submission": SalesReportSubmissionResponse.model_validate(submission).model_dump()},
    )


def update_submission_handler(
    business_id: int,
    submission_id: int,
    data: SalesReportSubmissionUpdate,
    db: Session,
) -> JSONResponse:
    submission = sales_report_submission_service.update_submission(db, business_id, submission_id, data)
    return success_response(
        message="Sales report submission updated successfully",
        data={"submission": SalesReportSubmissionResponse.model_validate(submission).model_dump()},
    )


def delete_submission_handler(business_id: int, submission_id: int, db: Session) -> JSONResponse:
    sales_report_submission_service.delete_submission(db, business_id, submission_id)
    return success_response(
        message="Sales report submission deleted successfully",
        data={},
    )


def confirm_submission_handler(
    business_id: int,
    submission_id: int,
    current_user: User,
    db: Session,
) -> JSONResponse:
    submission = sales_report_submission_service.confirm_submission(db, business_id, submission_id, current_user)
    return success_response(
        message="Sales report submission confirmed and finalized successfully",
        data={"submission": SalesReportSubmissionResponse.model_validate(submission).model_dump()},
    )
