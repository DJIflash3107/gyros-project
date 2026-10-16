from datetime import date
from typing import Optional, Union
from fastapi import UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
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
from app.services import sales_report_submission_service, sales_report_processing_service
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


async def process_submission_handler(
    business_id: int,
    file: UploadFile,
    input_method: str,
    report_period_type: str,
    coverage_start: date,
    coverage_end: date,
    branch_id: Optional[int],
    current_user: User,
    db: Session,
    stream: Optional[bool] = None,
) -> Union[JSONResponse, StreamingResponse]:
    if coverage_end < coverage_start:
        raise ValidationException(
            errors={"coverage_end": "coverage_end must be greater than or equal to coverage_start"},
            message="Request validation failed",
        )

    file_bytes = await file.read()
    file_name = file.filename or "upload"
    mime_type = file.content_type or "application/octet-stream"

    if input_method == "spreadsheet":
        result = sales_report_processing_service.process_file_submission(
            db=db,
            business_id=business_id,
            current_user=current_user,
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            input_method="spreadsheet",
            report_period_type=report_period_type,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            branch_id=branch_id,
        )
        return success_response(
            message="Spreadsheet processed and staged successfully",
            data=result.model_dump(),
            status_code=201,
        )

    elif input_method == "photo":
        # Pre-validate vision requirements before streaming
        max_img_bytes = settings.VISION_MAX_IMAGE_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_img_bytes:
            raise ValidationException(
                errors={
                    "file": f"Image exceeds maximum size limit of {settings.VISION_MAX_IMAGE_SIZE_MB}MB",
                    "error_code": ErrorCodeRegistry.RPT_IMAGE_TOO_LARGE,
                },
                message="Image exceeds size limit",
                error_code=ErrorCodeRegistry.RPT_IMAGE_TOO_LARGE,
            )

        if not (mime_type.startswith("image/") or any(file_name.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp"))):
            raise ValidationException(
                errors={
                    "file": "Photo input method requires an image file (JPEG, PNG, WEBP)",
                    "error_code": ErrorCodeRegistry.RPT_UNSUPPORTED_FORMAT,
                },
                message="Unsupported file format",
                error_code=ErrorCodeRegistry.RPT_UNSUPPORTED_FORMAT,
            )

        # Check AI configuration and vision model availability
        if not settings.AMD_API_KEY and settings.APP_ENV not in ("testing", "test"):
            raise AIConfigException(
                errors={
                    "vision": "AI service is not configured. Please configure AMD_API_KEY.",
                    "error_code": ErrorCodeRegistry.RPT_VISION_UNAVAILABLE,
                },
                message="Vision model is unavailable",
                error_code=ErrorCodeRegistry.RPT_VISION_UNAVAILABLE,
            )

        if not settings.VISION_MODEL_OVERRIDE:
            try:
                client = get_amd_client()
                models = await list_models(client)
                has_vision = any(getattr(m, "supports_vision", False) for m in models)
            except Exception as e:
                raise AIConfigException(
                    errors={
                        "vision": f"Failed to discover vision models: {str(e)}",
                        "error_code": ErrorCodeRegistry.RPT_VISION_UNAVAILABLE,
                    },
                    message="Vision model is unavailable",
                    error_code=ErrorCodeRegistry.RPT_VISION_UNAVAILABLE,
                )
            if not has_vision:
                raise AIConfigException(
                    errors={
                        "vision": "No vision-capable model is available in the configured AI catalog",
                        "error_code": ErrorCodeRegistry.RPT_VISION_UNAVAILABLE,
                    },
                    message="No vision-capable model is available",
                    error_code=ErrorCodeRegistry.RPT_VISION_UNAVAILABLE,
                )

        # Check duplicate file before streaming
        sha256_hex = sales_report_processing_service.compute_sha256(file_bytes)
        sales_report_processing_service.check_duplicate_submission(db, business_id, sha256_hex)

        # If stream is explicitly False, process synchronously and return JSON
        if stream is False:
            result = sales_report_processing_service.process_file_submission(
                db=db,
                business_id=business_id,
                current_user=current_user,
                file_bytes=file_bytes,
                file_name=file_name,
                mime_type=mime_type,
                input_method="photo",
                report_period_type=report_period_type,
                coverage_start=coverage_start,
                coverage_end=coverage_end,
                branch_id=branch_id,
            )
            return success_response(
                message="Photo processed and staged successfully",
                data=result.model_dump(),
                status_code=201,
            )

        # Otherwise, stream SSE progress
        generator = sales_report_processing_service.process_photo_submission_stream(
            db=db,
            business_id=business_id,
            current_user=current_user,
            image_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            report_period_type=report_period_type,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            branch_id=branch_id,
        )
        return StreamingResponse(generator, media_type="text/event-stream")

    else:
        raise ValidationException(
            errors={
                "input_method": f"Invalid input_method '{input_method}'. Supported: spreadsheet, photo",
                "error_code": ErrorCodeRegistry.RPT_UNSUPPORTED_FORMAT,
            },
            message="Invalid input method",
            error_code=ErrorCodeRegistry.RPT_UNSUPPORTED_FORMAT,
        )


def batch_form_handler(
    business_id: int,
    data: ManualFormBatchCreate,
    current_user: User,
    db: Session,
) -> JSONResponse:
    result = sales_report_processing_service.process_manual_form_batch(
        db=db,
        business_id=business_id,
        current_user=current_user,
        batch_data=data,
    )
    return success_response(
        message="Batch manual form submission processed and staged successfully",
        data=result.model_dump(),
        status_code=201,
    )
