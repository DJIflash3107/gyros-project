from datetime import datetime
from typing import Optional, Any, Dict
from sqlalchemy import String, Text, JSON, ForeignKey, Index, CheckConstraint, func, BigInteger, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.configs.database import Base
from app.models.types import BigIntId, DateTime6


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        BigIntId, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    file_format: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(20), nullable=False, default="local")
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    sha256_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    purpose: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    source_entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_entity_id: Mapped[Optional[int]] = mapped_column(BigIntId, nullable=True)

    generation_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ready", index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigIntId, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime6, nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_downloaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime6, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime6, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    business = relationship("Business", foreign_keys=[business_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'generating', 'ready', 'failed')",
            name="chk_artifacts_status",
        ),
        CheckConstraint(
            "artifact_type IN ('report', 'plan', 'file', 'image')",
            name="chk_artifacts_type",
        ),
        Index("ix_artifacts_business_type", "business_id", "artifact_type"),
        Index("ix_artifacts_business_created", "business_id", "created_at"),
    )
