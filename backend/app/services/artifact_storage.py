from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import re
from typing import Tuple, Optional, Dict, Any
import uuid

import jwt

from app.configs.settings import settings
from app.helpers.error_codes import ErrorCodeRegistry
from app.helpers.exceptions import (
    AppException,
    ArtifactNotFoundException,
    ValidationException,
    AuthenticationException,
)


def create_download_token(artifact_id: int, business_id: int, expires_in: int = 3600) -> str:
    """Generate a signed, short-lived download token for an artifact."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(seconds=expires_in)
    payload: Dict[str, Any] = {
        "sub": f"artifact_download:{artifact_id}",
        "art_id": artifact_id,
        "biz_id": business_id,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "artifact_download",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_download_token(token: str, artifact_id: int) -> int:
    """Verify download token and return business_id. Raises AuthenticationException on failure."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
        if payload.get("type") != "artifact_download":
            raise AuthenticationException(
                message="Invalid download token type",
                errors={"token": "Invalid download token"},
            )
        if payload.get("art_id") != artifact_id:
            raise AuthenticationException(
                message="Download token does not match requested artifact",
                errors={"token": "Artifact mismatch"},
            )
        return int(payload["biz_id"])
    except jwt.ExpiredSignatureError:
        raise AuthenticationException(
            message="Download link has expired",
            errors={"token": "Download token expired"},
            error_code=ErrorCodeRegistry.ART_EXPIRED,
        )
    except jwt.InvalidTokenError:
        raise AuthenticationException(
            message="Invalid download token",
            errors={"token": "Invalid download token"},
        )


class ArtifactStorageService(ABC):
    """Abstract interface for artifact storage services."""

    @abstractmethod
    def save(
        self,
        business_id: int,
        file_data: bytes,
        file_name: str,
        mime_type: str,
    ) -> Tuple[str, int, str]:
        """
        Save file data and return (storage_path, file_size_bytes, sha256_hash).
        """
        pass

    @abstractmethod
    def load(self, storage_path: str) -> bytes:
        """Load file bytes from storage_path."""
        pass

    @abstractmethod
    def delete(self, storage_path: str) -> bool:
        """Delete file at storage_path. Return True if deleted, False if not found."""
        pass

    @abstractmethod
    def exists(self, storage_path: str) -> bool:
        """Check if file exists at storage_path."""
        pass

    @abstractmethod
    def get_download_url(
        self,
        artifact_id: int,
        business_id: int,
        file_name: str,
        expires_in: int = 3600,
    ) -> str:
        """Return a controlled/authorized download URL."""
        pass


class LocalStorageService(ArtifactStorageService):
    """Local filesystem storage with path traversal protection."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or settings.ARTIFACT_STORAGE_LOCAL_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, file_name: str) -> str:
        # Keep alphanumeric, dot, underscore, dash
        clean_name = re.sub(r"[^\w\.-]", "_", file_name)
        # Avoid leading dots
        clean_name = clean_name.lstrip(".")
        return clean_name or "artifact"

    def _resolve_safe_path(self, storage_path: str) -> Path:
        resolved = (self.base_dir / storage_path).resolve()
        try:
            resolved.relative_to(self.base_dir)
        except ValueError:
            raise ValidationException(
                errors={"storage_path": "Path traversal detected"},
                message="Invalid storage path",
                error_code=ErrorCodeRegistry.ART_STORAGE_ERROR,
            )
        return resolved

    def save(
        self,
        business_id: int,
        file_data: bytes,
        file_name: str,
        mime_type: str,
    ) -> Tuple[str, int, str]:
        max_bytes = settings.ARTIFACT_MAX_FILE_SIZE_MB * 1024 * 1024
        file_size = len(file_data)
        if file_size > max_bytes:
            raise AppException(
                status_code=413,
                message=f"File size exceeds maximum allowed of {settings.ARTIFACT_MAX_FILE_SIZE_MB}MB",
                errors={"file": f"File size {file_size} exceeds {max_bytes} bytes"},
                error_code=ErrorCodeRegistry.ART_FILE_TOO_LARGE,
            )

        sanitized_name = self._sanitize_filename(file_name)
        unique_prefix = uuid.uuid4().hex[:12]
        relative_path = f"business_{business_id}/{unique_prefix}_{sanitized_name}"

        full_path = self._resolve_safe_path(relative_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)

        sha256 = hashlib.sha256(file_data).hexdigest()

        with open(full_path, "wb") as f:
            f.write(file_data)

        return relative_path, file_size, sha256

    def load(self, storage_path: str) -> bytes:
        full_path = self._resolve_safe_path(storage_path)
        if not full_path.is_file():
            raise ArtifactNotFoundException(
                message=f"Artifact file not found in storage: {storage_path}",
                errors={"storage_path": "File not found on disk"},
            )
        with open(full_path, "rb") as f:
            return f.read()

    def delete(self, storage_path: str) -> bool:
        try:
            full_path = self._resolve_safe_path(storage_path)
            if full_path.is_file():
                os.remove(full_path)
                return True
            return False
        except Exception:
            return False

    def exists(self, storage_path: str) -> bool:
        try:
            full_path = self._resolve_safe_path(storage_path)
            return full_path.is_file()
        except Exception:
            return False

    def get_download_url(
        self,
        artifact_id: int,
        business_id: int,
        file_name: str,
        expires_in: int = 3600,
    ) -> str:
        token = create_download_token(artifact_id, business_id, expires_in)
        return f"/api/v1/artifacts/{artifact_id}/download?token={token}"


class S3StorageService(ArtifactStorageService):
    """S3 / Object storage implementation."""

    def __init__(self):
        self.bucket = settings.ARTIFACT_STORAGE_S3_BUCKET
        self.region = settings.ARTIFACT_STORAGE_S3_REGION
        self.endpoint = settings.ARTIFACT_STORAGE_S3_ENDPOINT
        self.access_key = settings.ARTIFACT_STORAGE_S3_ACCESS_KEY
        self.secret_key = settings.ARTIFACT_STORAGE_S3_SECRET_KEY

    def save(
        self,
        business_id: int,
        file_data: bytes,
        file_name: str,
        mime_type: str,
    ) -> Tuple[str, int, str]:
        # If boto3 is available and configured, upload. Otherwise raise.
        try:
            import boto3  # type: ignore
        except ImportError:
            raise AppException(
                status_code=500,
                message="S3 storage backend is configured but 'boto3' is not installed",
                errors={"storage": "boto3 required for S3 storage"},
                error_code=ErrorCodeRegistry.ART_STORAGE_ERROR,
            )

        if not self.bucket or not self.access_key or not self.secret_key:
            raise AppException(
                status_code=500,
                message="S3 storage credentials are not properly configured",
                errors={"storage": "Missing S3 bucket or credentials"},
                error_code=ErrorCodeRegistry.ART_STORAGE_ERROR,
            )

        unique_prefix = uuid.uuid4().hex[:12]
        key = f"businesses/{business_id}/artifacts/{unique_prefix}_{file_name}"
        sha256 = hashlib.sha256(file_data).hexdigest()

        s3_client = boto3.client(
            "s3",
            region_name=self.region,
            endpoint_url=self.endpoint or None,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )
        s3_client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=file_data,
            ContentType=mime_type,
        )
        return key, len(file_data), sha256

    def load(self, storage_path: str) -> bytes:
        try:
            import boto3  # type: ignore
        except ImportError:
            raise AppException(
                status_code=500,
                message="S3 storage backend requires boto3",
                error_code=ErrorCodeRegistry.ART_STORAGE_ERROR,
            )
        s3_client = boto3.client(
            "s3",
            region_name=self.region,
            endpoint_url=self.endpoint or None,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )
        resp = s3_client.get_object(Bucket=self.bucket, Key=storage_path)
        return resp["Body"].read()

    def delete(self, storage_path: str) -> bool:
        try:
            import boto3  # type: ignore
            s3_client = boto3.client(
                "s3",
                region_name=self.region,
                endpoint_url=self.endpoint or None,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            )
            s3_client.delete_object(Bucket=self.bucket, Key=storage_path)
            return True
        except Exception:
            return False

    def exists(self, storage_path: str) -> bool:
        try:
            import boto3  # type: ignore
            s3_client = boto3.client(
                "s3",
                region_name=self.region,
                endpoint_url=self.endpoint or None,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            )
            s3_client.head_object(Bucket=self.bucket, Key=storage_path)
            return True
        except Exception:
            return False

    def get_download_url(
        self,
        artifact_id: int,
        business_id: int,
        file_name: str,
        expires_in: int = 3600,
    ) -> str:
        try:
            import boto3  # type: ignore
            s3_client = boto3.client(
                "s3",
                region_name=self.region,
                endpoint_url=self.endpoint or None,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            )
            # Find key
            return s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": file_name},
                ExpiresIn=expires_in,
            )
        except Exception:
            # Fallback to local token endpoint
            token = create_download_token(artifact_id, business_id, expires_in)
            return f"/api/v1/artifacts/{artifact_id}/download?token={token}"


_storage_instance: Optional[ArtifactStorageService] = None


def get_storage_service() -> ArtifactStorageService:
    """Return configured storage service singleton."""
    global _storage_instance
    if _storage_instance is None:
        backend = (settings.ARTIFACT_STORAGE_BACKEND or "local").lower()
        if backend == "s3":
            _storage_instance = S3StorageService()
        else:
            _storage_instance = LocalStorageService()
    return _storage_instance
