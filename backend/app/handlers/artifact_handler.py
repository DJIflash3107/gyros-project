import math
from typing import Optional
from fastapi import Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.schemas.artifact import (
    GenerateReportRequest,
    GeneratePlanArtifactRequest,
    GenerateImageRequest,
    ArtifactFilterParams,
)
from app.services.artifact_service import ArtifactService
from app.helpers.response import success_response, paginated_response


_service = ArtifactService()


def generate_report_handler(
    business_id: int,
    request: GenerateReportRequest,
    current_user: User,
    db: Session,
) -> JSONResponse:
    result = _service.generate_report(
        db=db,
        business_id=business_id,
        request=request,
        user_id=current_user.id,
    )
    return success_response(
        message="Report generated successfully",
        data=result.model_dump(mode="json"),
        status_code=201,
    )


def generate_plan_artifact_handler(
    business_id: int,
    request: GeneratePlanArtifactRequest,
    current_user: User,
    db: Session,
) -> JSONResponse:
    result = _service.generate_plan_artifact(
        db=db,
        business_id=business_id,
        request=request,
        user_id=current_user.id,
    )
    return success_response(
        message="Plan artifact generated successfully",
        data=result.model_dump(mode="json"),
        status_code=201,
    )


async def generate_image_handler(
    business_id: int,
    request: GenerateImageRequest,
    current_user: User,
    db: Session,
) -> JSONResponse:
    result = await _service.generate_image(
        db=db,
        business_id=business_id,
        request=request,
        user_id=current_user.id,
    )
    return success_response(
        message="Image generated successfully",
        data=result.model_dump(mode="json"),
        status_code=201,
    )


def list_artifacts_handler(
    business_id: int,
    filters: ArtifactFilterParams,
    db: Session,
) -> JSONResponse:
    items, total = _service.list_artifacts(
        db=db,
        business_id=business_id,
        filters=filters,
    )
    total_pages = max(1, math.ceil(total / filters.per_page))
    pagination = {
        "current_page": filters.page,
        "per_page": filters.per_page,
        "total_records": total,
        "total_pages": total_pages,
    }
    return paginated_response(
        message="Artifacts retrieved successfully",
        items=[item.model_dump(mode="json") for item in items],
        resource_key="artifacts",
        pagination=pagination,
    )


def get_artifact_handler(
    business_id: int,
    artifact_id: int,
    db: Session,
) -> JSONResponse:
    result = _service.get_artifact(
        db=db,
        business_id=business_id,
        artifact_id=artifact_id,
    )
    return success_response(
        message="Artifact retrieved successfully",
        data=result.model_dump(mode="json"),
        status_code=200,
    )


def get_download_url_handler(
    business_id: int,
    artifact_id: int,
    expires_in: int,
    db: Session,
) -> JSONResponse:
    result = _service.get_download_url_info(
        db=db,
        business_id=business_id,
        artifact_id=artifact_id,
        expires_in=expires_in,
    )
    return success_response(
        message="Download URL generated successfully",
        data=result.model_dump(mode="json"),
        status_code=200,
    )


def download_artifact_handler(
    business_id: int,
    artifact_id: int,
    db: Session,
) -> Response:
    file_bytes, file_name, mime_type = _service.get_download_data(
        db=db,
        business_id=business_id,
        artifact_id=artifact_id,
    )
    return Response(
        content=file_bytes,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Content-Length": str(len(file_bytes)),
        },
    )


def delete_artifact_handler(
    business_id: int,
    artifact_id: int,
    db: Session,
) -> JSONResponse:
    _service.delete_artifact(
        db=db,
        business_id=business_id,
        artifact_id=artifact_id,
    )
    return success_response(
        message="Artifact deleted successfully",
        data={"id": artifact_id},
        status_code=200,
    )
