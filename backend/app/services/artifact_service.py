from datetime import datetime, timezone
import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from app.configs.settings import settings
from app.models.artifact import Artifact
from app.models.schemas.artifact import (
    GenerateReportRequest,
    GeneratePlanArtifactRequest,
    GenerateImageRequest,
    ArtifactFilterParams,
    ArtifactResponse,
    DownloadUrlResponse,
)
from app.services.artifact_storage import get_storage_service, ArtifactStorageService
from app.services.report_generator import ReportGeneratorService
from app.services.image_generator import ImageGeneratorService
from app.helpers.exceptions import ArtifactNotFoundException, AppException
from app.helpers.error_codes import ErrorCodeRegistry
from app.helpers.logging import logger


class ArtifactService:
    """
    Core service coordinating business report generation, plan export, image generation,
    file storage, metadata persistence, access control, and retrieval.
    """

    def __init__(
        self,
        storage_service: Optional[ArtifactStorageService] = None,
        report_generator: Optional[ReportGeneratorService] = None,
        image_generator: Optional[ImageGeneratorService] = None,
    ):
        self.storage = storage_service or get_storage_service()
        self.report_gen = report_generator or ReportGeneratorService()
        self.image_gen = image_generator or ImageGeneratorService()

    def _enrich_response(self, artifact: Artifact) -> ArtifactResponse:
        """Convert ORM Artifact to ArtifactResponse and attach download URL."""
        resp = ArtifactResponse.model_validate(artifact)
        try:
            file_name = Path(artifact.storage_path).name
            resp.download_url = self.storage.get_download_url(
                artifact.id,
                artifact.business_id,
                file_name,
                expires_in=settings.ARTIFACT_DOWNLOAD_URL_EXPIRY_SECONDS,
            )
        except Exception as e:
            logger.warning(f"Failed to generate download URL for artifact #{artifact.id}: {e}")
            resp.download_url = None
        return resp

    def generate_report(
        self,
        db: Session,
        business_id: int,
        request: GenerateReportRequest,
        user_id: Optional[int] = None,
    ) -> ArtifactResponse:
        """
        Generate business report from validated DB data and persist to storage and database.
        """
        file_bytes, file_name, mime_type, metadata = self.report_gen.generate_report(
            db, business_id, request
        )

        storage_path, file_size, sha256 = self.storage.save(
            business_id=business_id,
            file_data=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
        )

        title = request.title or f"{request.report_type.replace('_', ' ').title()} ({request.file_format.upper()})"

        artifact = Artifact(
            business_id=business_id,
            title=title,
            artifact_type="report",
            file_format=request.file_format,
            storage_backend=settings.ARTIFACT_STORAGE_BACKEND,
            storage_path=storage_path,
            file_size_bytes=file_size,
            mime_type=mime_type,
            sha256_hash=sha256,
            purpose=request.report_type,
            source_entity_type="sales_report" if "sales" in request.report_type else request.report_type,
            generation_params=request.model_dump(mode="json"),
            metadata_json=metadata,
            status="ready",
            created_by_user_id=user_id,
        )

        db.add(artifact)
        db.commit()
        db.refresh(artifact)

        return self._enrich_response(artifact)

    def generate_plan_artifact(
        self,
        db: Session,
        business_id: int,
        request: GeneratePlanArtifactRequest,
        user_id: Optional[int] = None,
    ) -> ArtifactResponse:
        """
        Export a PromotionPlan or structured business plan to file.
        """
        file_bytes, file_name, mime_type, metadata = self.report_gen.generate_plan_artifact(
            db, business_id, request
        )

        storage_path, file_size, sha256 = self.storage.save(
            business_id=business_id,
            file_data=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
        )

        title = request.title or f"Promotion Plan #{request.source_plan_id} Export ({request.file_format.upper()})"

        artifact = Artifact(
            business_id=business_id,
            title=title,
            artifact_type="plan",
            file_format=request.file_format,
            storage_backend=settings.ARTIFACT_STORAGE_BACKEND,
            storage_path=storage_path,
            file_size_bytes=file_size,
            mime_type=mime_type,
            sha256_hash=sha256,
            purpose="promotion_plan_export",
            source_entity_type="promotion_plan",
            source_entity_id=request.source_plan_id,
            generation_params=request.model_dump(mode="json"),
            metadata_json=metadata,
            status="ready",
            created_by_user_id=user_id,
        )

        db.add(artifact)
        db.commit()
        db.refresh(artifact)

        return self._enrich_response(artifact)

    async def generate_image(
        self,
        db: Session,
        business_id: int,
        request: GenerateImageRequest,
        user_id: Optional[int] = None,
    ) -> ArtifactResponse:
        """
        Generate image for validated F&B business purpose and persist.
        Never creates placeholder files on failure.
        """
        file_bytes, file_name, mime_type, metadata = await self.image_gen.generate_image(
            request, business_id
        )

        storage_path, file_size, sha256 = self.storage.save(
            business_id=business_id,
            file_data=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
        )

        title = request.title or f"{request.purpose.replace('_', ' ').title()}"

        source_type = None
        source_id = None
        if request.promotion_plan_id:
            source_type = "promotion_plan"
            source_id = request.promotion_plan_id
        elif request.product_id:
            source_type = "product"
            source_id = request.product_id

        artifact = Artifact(
            business_id=business_id,
            title=title,
            artifact_type="image",
            file_format="png",
            storage_backend=settings.ARTIFACT_STORAGE_BACKEND,
            storage_path=storage_path,
            file_size_bytes=file_size,
            mime_type=mime_type,
            sha256_hash=sha256,
            purpose=request.purpose,
            source_entity_type=source_type,
            source_entity_id=source_id,
            generation_params=request.model_dump(mode="json"),
            metadata_json=metadata,
            status="ready",
            created_by_user_id=user_id,
        )

        db.add(artifact)
        db.commit()
        db.refresh(artifact)

        return self._enrich_response(artifact)

    def list_artifacts(
        self,
        db: Session,
        business_id: int,
        filters: ArtifactFilterParams,
    ) -> Tuple[List[ArtifactResponse], int]:
        """List artifacts with tenant isolation and optional filtering."""
        query = select(Artifact).where(Artifact.business_id == business_id)

        if filters.artifact_type:
            query = query.where(Artifact.artifact_type == filters.artifact_type)
        if filters.file_format:
            query = query.where(Artifact.file_format == filters.file_format)
        if filters.purpose:
            query = query.where(Artifact.purpose == filters.purpose)
        if filters.status:
            query = query.where(Artifact.status == filters.status)

        count_query = select(func.count()).select_from(query.subquery())
        total = db.execute(count_query).scalar_one()

        offset = (filters.page - 1) * filters.per_page
        query = query.order_by(desc(Artifact.created_at)).offset(offset).limit(filters.per_page)

        records = db.execute(query).scalars().all()
        return [self._enrich_response(r) for r in records], total

    def get_artifact(
        self,
        db: Session,
        business_id: int,
        artifact_id: int,
    ) -> ArtifactResponse:
        """Get artifact metadata with tenant isolation."""
        artifact = db.execute(
            select(Artifact).where(
                Artifact.id == artifact_id,
                Artifact.business_id == business_id,
            )
        ).scalar_one_or_none()

        if not artifact:
            raise ArtifactNotFoundException(
                message=f"Artifact #{artifact_id} not found for this business",
                errors={"artifact_id": f"Artifact #{artifact_id} not found"},
            )

        return self._enrich_response(artifact)

    def get_download_data(
        self,
        db: Session,
        business_id: int,
        artifact_id: int,
    ) -> Tuple[bytes, str, str]:
        """
        Load file bytes and record download event with tenant isolation.
        Returns (file_bytes, file_name, mime_type).
        """
        artifact = db.execute(
            select(Artifact).where(
                Artifact.id == artifact_id,
                Artifact.business_id == business_id,
            )
        ).scalar_one_or_none()

        if not artifact:
            raise ArtifactNotFoundException(
                message=f"Artifact #{artifact_id} not found for this business",
                errors={"artifact_id": f"Artifact #{artifact_id} not found"},
            )

        file_bytes = self.storage.load(artifact.storage_path)

        # Track download count
        artifact.download_count = (artifact.download_count or 0) + 1
        artifact.last_downloaded_at = datetime.now()
        db.commit()

        file_name = Path(artifact.storage_path).name
        # Remove UUID prefix for clean user download name
        clean_name = file_name.split("_", 1)[1] if "_" in file_name else file_name

        return file_bytes, clean_name, artifact.mime_type

    def get_download_url_info(
        self,
        db: Session,
        business_id: int,
        artifact_id: int,
        expires_in: int = 3600,
    ) -> DownloadUrlResponse:
        """Return authorized download URL details."""
        artifact = db.execute(
            select(Artifact).where(
                Artifact.id == artifact_id,
                Artifact.business_id == business_id,
            )
        ).scalar_one_or_none()

        if not artifact:
            raise ArtifactNotFoundException(
                message=f"Artifact #{artifact_id} not found",
                errors={"artifact_id": f"Artifact #{artifact_id} not found"},
            )

        file_name = Path(artifact.storage_path).name
        clean_name = file_name.split("_", 1)[1] if "_" in file_name else file_name

        download_url = self.storage.get_download_url(
            artifact.id,
            business_id,
            clean_name,
            expires_in=expires_in,
        )

        return DownloadUrlResponse(
            artifact_id=artifact.id,
            download_url=download_url,
            expires_in_seconds=expires_in,
            file_name=clean_name,
            mime_type=artifact.mime_type,
            file_size_bytes=artifact.file_size_bytes,
        )

    def delete_artifact(
        self,
        db: Session,
        business_id: int,
        artifact_id: int,
    ) -> bool:
        """Delete artifact record and stored file."""
        artifact = db.execute(
            select(Artifact).where(
                Artifact.id == artifact_id,
                Artifact.business_id == business_id,
            )
        ).scalar_one_or_none()

        if not artifact:
            raise ArtifactNotFoundException(
                message=f"Artifact #{artifact_id} not found",
                errors={"artifact_id": f"Artifact #{artifact_id} not found"},
            )

        self.storage.delete(artifact.storage_path)
        db.delete(artifact)
        db.commit()
        return True
