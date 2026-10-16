from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, CHAR, Date, ForeignKey, Index, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.configs.database import Base
from app.models.types import BigIntId, IntUnsigned, DateTime6


class SalesReportSubmission(Base):
    __tablename__ = "sales_report_submissions"

    id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=False, index=True)
    submitted_by_user_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    branch_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    input_method: Mapped[str] = mapped_column(String(20), nullable=False)
    report_period_type: Mapped[str] = mapped_column(String(20), nullable=False)
    coverage_start: Mapped[date] = mapped_column(Date, nullable=False)
    coverage_end: Mapped[date] = mapped_column(Date, nullable=False)
    source_file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    source_sha256: Mapped[Optional[str]] = mapped_column(CHAR(64), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    total_rows: Mapped[int] = mapped_column(IntUnsigned, nullable=False, default=0)
    accepted_rows: Mapped[int] = mapped_column(IntUnsigned, nullable=False, default=0)
    rejected_rows: Mapped[int] = mapped_column(IntUnsigned, nullable=False, default=0)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime6, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime6, nullable=True)

    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("coverage_end >= coverage_start", name="chk_submissions_coverage_dates"),
        Index("ix_submissions_biz_status_dates", "business_id", "status", "coverage_start", "coverage_end"),
    )

    # Relationships
    business = relationship("Business", back_populates="sales_submissions")
    submitted_by_user = relationship("User", back_populates="submitted_sales_reports")
    branch = relationship("Branch")
    staging_rows = relationship("SalesReportStagingRow", back_populates="submission", cascade="all, delete-orphan")
    observations = relationship("SalesReportObservation", back_populates="submission")
    issues = relationship("ImportIssue", back_populates="submission", cascade="all, delete-orphan")
