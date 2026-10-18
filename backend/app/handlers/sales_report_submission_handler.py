import hashlib
from datetime import date
from typing import Optional, Union, List, Tuple
from fastapi import UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.schemas.sales_report_submission import (
    SalesReportSubmissionCreate,
    SalesReportSubmissionUpdate,
    SalesReportSubmissionResponse,
)
from app.models.schemas.sales_report_processing import (
    ManualFormBatchCreate,
    ProcessingResultResponse,
)
from app.models.schemas.pagination import PaginationParams
from app.services import (
    sales_report_submission_service,
    sales_report_processing_service,
)
from app.helpers.response import success_response, paginated_response
from app.helpers.exceptions import ValidationException, AIConfigException
from app.helpers.error_codes import ErrorCodeRegistry
from app.configs.settings import settings
from app.configs.amd_client import get_amd_client
from app.services.ai_service import list_models


def create_submission_handler(
    business_id: int,
    data: SalesReportSubmissionCreate,
    current_user: User,
    db: Session,
) -> JSONResponse:
    submission = sales_report_submission_service.create_submission(
        db, business_id, data, current_user
    )
    return success_response(
        message="Sales report submission created successfully",
        data={
            "submission": SalesReportSubmissionResponse.model_validate(
                submission
            ).model_dump()
        },
        status_code=201,
    )


def list_submissions_handler(
    business_id: int,
    status: Optional[str],
    params: PaginationParams,
    db: Session,
) -> JSONResponse:
    items, pagination = sales_report_submission_service.list_submissions(
        db, business_id, status, params.page, params.page_size
    )
    response_items = [
        SalesReportSubmissionResponse.model_validate(s).model_dump() for s in items
    ]
    return paginated_response(
        message="Sales report submissions retrieved successfully",
        items=response_items,
        resource_key="submissions",
        pagination=pagination,
    )


def get_submission_handler(
    business_id: int, submission_id: int, db: Session
) -> JSONResponse:
    submission = sales_report_submission_service.get_submission(
        db, business_id, submission_id
    )
    return success_response(
        message="Sales report submission retrieved successfully",
        data={
            "submission": SalesReportSubmissionResponse.model_validate(
                submission
            ).model_dump()
        },
    )


def update_submission_handler(
    business_id: int,
    submission_id: int,
    data: SalesReportSubmissionUpdate,
    db: Session,
) -> JSONResponse:
    submission = sales_report_submission_service.update_submission(
        db, business_id, submission_id, data
    )
    return success_response(
        message="Sales report submission updated successfully",
        data={
            "submission": SalesReportSubmissionResponse.model_validate(
                submission
            ).model_dump()
        },
    )


def delete_submission_handler(
    business_id: int, submission_id: int, db: Session
) -> JSONResponse:
    sales_report_submission_service.delete_submission(db, business_id, submission_id)
    return success_response(
        message="Sales report submission deleted successfully",
        data={},
    )


def confirm_submission_handler(business_id: int, submission_id: int, current_user: User, db: Session) -> JSONResponse:
    from app.services.background_job_service import enqueue_job
    job = enqueue_job(db, business_id, current_user.id, "sales_report_confirm", {"submission_id": submission_id})
    return success_response("Sales report confirmation queued", {
        "job_id": job['id'],
        "status": job["status"],
        "status_url": f"/api/v1/businesses/{business_id}/jobs/{job['id']}",
    }, status_code=202)

async def process_submission_handler(
    business_id: int,
    files: List[UploadFile],
    input_method: str,
    report_period_type: str,
    coverage_start: date,
    coverage_end: date,
    branch_id: Optional[int],
    current_user: User,
    db: Session,
    stream: Optional[bool] = None,
) -> JSONResponse:
    from app.services.background_job_service import enqueue_job
    from app.services.background_job_worker import delete_upload, store_upload

    if coverage_end < coverage_start:
        raise ValidationException(
            errors={
                "coverage_end": "coverage_end must be greater than or equal to coverage_start"
            },
            message="Request validation failed",
        )
    if input_method not in ("spreadsheet", "photo"):
        raise ValidationException(
            errors={"input_method": "Supported values: spreadsheet, photo"},
            message="Invalid input method",
        )
    if not files:
        raise ValidationException(errors={"file": "At least one file is required"}, message="No upload file provided")
    if input_method == "spreadsheet" and len(files) != 1:
        raise ValidationException(errors={"files": "Spreadsheet processing accepts one file"}, message="Invalid file count")
    if input_method == "photo" and len(files) > settings.VISION_MAX_IMAGES_PER_SUBMISSION:
        raise ValidationException(
            errors={"files": f"Maximum {settings.VISION_MAX_IMAGES_PER_SUBMISSION} images per submission"},
            message="Too many images",
        )

    stored = []
    try:
        for index, upload in enumerate(files, start=1):
            content = await upload.read()
            filename = upload.filename or f"upload_{index}"
            mime_type = upload.content_type or "application/octet-stream"
            if input_method == "spreadsheet" and len(content) > sales_report_processing_service.MAX_SPREADSHEET_BYTES:
                raise ValidationException(errors={"file": "Spreadsheet exceeds maximum size limit of 10MB"}, message="File exceeds size limit")
            if input_method == "photo" and len(content) > settings.VISION_MAX_IMAGE_SIZE_MB * 1024 * 1024:
                raise ValidationException(errors={"file": f"Image '{filename}' exceeds maximum size limit"}, message="Image exceeds size limit")
            storage_key = store_upload(business_id, filename, content)
            stored.append({"storage_key": storage_key, "filename": filename, "mime_type": mime_type})
        job = enqueue_job(db, business_id, current_user.id, "sales_report_process", {
            "files": stored,
            "input_method": input_method,
            "report_period_type": report_period_type,
            "coverage_start": coverage_start.isoformat(),
            "coverage_end": coverage_end.isoformat(),
            "branch_id": branch_id,
        })
    except Exception:
        for item in stored:
            delete_upload(item["storage_key"])
        raise
    return success_response("Sales report processing queued", {
        "job_id": job['id'],
        "status": job["status"],
        "status_url": f"/api/v1/businesses/{business_id}/jobs/{job['id']}",
    }, status_code=202)


def batch_form_handler(
    business_id: int,
    data: ManualFormBatchCreate,
    current_user: User,
    db: Session,
) -> JSONResponse:
    from app.services.background_job_service import enqueue_job
    job = enqueue_job(db, business_id, current_user.id, "sales_report_batch_form", {"data": data.model_dump(mode="json")})
    return success_response("Sales report batch queued", {
        "job_id": job['id'],
        "status": job["status"],
        "status_url": f"/api/v1/businesses/{business_id}/jobs/{job['id']}",
    }, status_code=202)
