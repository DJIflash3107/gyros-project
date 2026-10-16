from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.configs.database import Base
from app.models.types import BigIntId, IntUnsigned, DateTime6


class ImportIssue(Base):
    __tablename__ = "import_issues"

    id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("sales_report_submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    staging_row_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("sales_report_staging_rows.id", ondelete="CASCADE"), nullable=True, index=True)
    source_row_number: Mapped[Optional[int]] = mapped_column(IntUnsigned, nullable=True)
    field_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    issue_code: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    raw_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    resolved_by_user_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime6, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now())

    # Indexes
    __table_args__ = (
        Index("ix_import_issues_sub_res_sev", "submission_id", "resolution_status", "severity"),
    )

    # Relationships
    submission = relationship("SalesReportSubmission", back_populates="issues")
    staging_row = relationship("SalesReportStagingRow", back_populates="issues")
    resolved_by_user = relationship("User", foreign_keys=[resolved_by_user_id])
