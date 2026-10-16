from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Any
from sqlalchemy import String, Date, Numeric, JSON, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.configs.database import Base
from app.models.types import BigIntId, IntUnsigned, DateTime6


class SalesReportStagingRow(Base):
    __tablename__ = "sales_report_staging_rows"

    id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("sales_report_submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    source_row_number: Mapped[Optional[int]] = mapped_column(IntUnsigned, nullable=True)
    raw_payload_json: Mapped[Any] = mapped_column(JSON, nullable=False)
    raw_product_name: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    branch_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    product_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    granularity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Quantities DECIMAL(12, 3)
    prepared_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    opening_stock_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    received_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    available_stock_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    sold_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    leftover_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    spoiled_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    damaged_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    staff_meals_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    donated_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    other_disposition_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)

    # Revenue DECIMAL(14, 2)
    recorded_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)

    extraction_confidence_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    review_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending_review")
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    submission = relationship("SalesReportSubmission", back_populates="staging_rows")
    branch = relationship("Branch")
    product = relationship("Product")
    issues = relationship("ImportIssue", back_populates="staging_row")
