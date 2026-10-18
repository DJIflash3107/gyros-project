from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.schemas.sales_report_staging_row import (
    SalesReportStagingRowCreate,
    SalesReportStagingRowUpdate,
    SalesReportStagingRowBulkUpdate,
    SalesReportStagingRowResponse,
)
from app.models.schemas.pagination import PaginationParams
from app.services import sales_report_staging_row_service
from app.helpers.response import success_response, paginated_response


def create_staging_row_handler(
    submission_id: int,
    data: SalesReportStagingRowCreate,
    db: Session,
) -> JSONResponse:
    row = sales_report_staging_row_service.create_staging_row(db, submission_id, data)
    return success_response(
        message="Staging row created successfully",
        data={"staging_row": SalesReportStagingRowResponse.model_validate(row).model_dump()},
        status_code=201,
    )


def list_staging_rows_handler(
    submission_id: int,
    review_status: Optional[str],
    params: PaginationParams,
    db: Session,
) -> JSONResponse:
    items, pagination = sales_report_staging_row_service.list_staging_rows(db, submission_id, review_status, params.page, params.page_size)
    response_items = [SalesReportStagingRowResponse.model_validate(r).model_dump() for r in items]
    return paginated_response(
        message="Staging rows retrieved successfully",
        items=response_items,
        resource_key="staging_rows",
        pagination=pagination,
    )


def get_staging_row_handler(submission_id: int, row_id: int, db: Session) -> JSONResponse:
    row = sales_report_staging_row_service.get_staging_row(db, submission_id, row_id)
    return success_response(
        message="Staging row retrieved successfully",
        data={"staging_row": SalesReportStagingRowResponse.model_validate(row).model_dump()},
    )


def update_staging_row_handler(
    submission_id: int,
    row_id: int,
    data: SalesReportStagingRowUpdate,
    db: Session,
) -> JSONResponse:
    row = sales_report_staging_row_service.update_staging_row(db, submission_id, row_id, data)
    return success_response(
        message="Staging row updated successfully",
        data={"staging_row": SalesReportStagingRowResponse.model_validate(row).model_dump()},
    )


def delete_staging_row_handler(submission_id: int, row_id: int, db: Session) -> JSONResponse:
    sales_report_staging_row_service.delete_staging_row(db, submission_id, row_id)
    return success_response(
        message="Staging row deleted successfully",
        data={},
    )


def bulk_update_staging_rows_handler(submission_id: int, data: SalesReportStagingRowBulkUpdate, db: Session, current_user_id: int) -> JSONResponse:
    from app.models.business_membership import BusinessMembership
    from app.models.sales_report_submission import SalesReportSubmission
    from app.helpers.exceptions import AuthorizationException, NotFoundException
    from app.services.background_job_service import enqueue_job

    submission = db.query(SalesReportSubmission).filter(SalesReportSubmission.id == submission_id).first()
    if submission is None:
        raise NotFoundException(message="Submission not found", errors={"submission_id": "Submission not found"})
    membership = db.query(BusinessMembership).filter(
        BusinessMembership.business_id == submission.business_id,
        BusinessMembership.user_id == current_user_id,
    ).first()
    if membership is None:
        raise AuthorizationException(message="Access denied", errors={"authorization": "You are not a member of this business"})
    job = enqueue_job(db, submission.business_id, current_user_id, "sales_report_staging_bulk_update", {
        "submission_id": submission_id,
        "data": data.model_dump(mode="json"),
    })
    return success_response("Staging row bulk update queued", {
        "job_id": job['id'],
        "status": job["status"],
        "status_url": f"/api/v1/businesses/{submission.business_id}/jobs/{job['id']}",
    }, status_code=202)
