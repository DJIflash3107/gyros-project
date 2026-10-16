from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Date, Numeric, ForeignKey, ForeignKeyConstraint, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.configs.database import Base
from app.models.types import BigIntId, DateTime6


class SalesReportObservation(Base):
    __tablename__ = "sales_report_observations"

    id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(BigIntId, nullable=False, index=True)
    branch_id: Mapped[int] = mapped_column(BigIntId, nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(BigIntId, nullable=False, index=True)
    source_submission_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("sales_report_submissions.id", ondelete="RESTRICT"), nullable=False, index=True)
    source_staging_row_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("sales_report_staging_rows.id", ondelete="SET NULL"), nullable=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    granularity: Mapped[str] = mapped_column(String(20), nullable=False)

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

    record_status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_by_user_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now(), onupdate=func.now())

    # Constraints
    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "branch_id"],
            ["branches.business_id", "branches.id"],
            ondelete="RESTRICT",
            name="fk_observations_branch_business",
        ),
        ForeignKeyConstraint(
            ["business_id", "product_id"],
            ["products.business_id", "products.id"],
            ondelete="RESTRICT",
            name="fk_observations_product_business",
        ),
        UniqueConstraint(
            "business_id", "branch_id", "product_id", "period_start", "period_end",
            name="uq_observations_biz_branch_prod_period",
        ),
    )

    # Relationships
    branch = relationship("Branch", back_populates="observations", foreign_keys=[business_id, branch_id], overlaps="observations")
    product = relationship("Product", back_populates="observations", foreign_keys=[business_id, product_id], overlaps="branch,observations")
    submission = relationship("SalesReportSubmission", back_populates="observations")
    staging_row = relationship("SalesReportStagingRow")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
    updated_by_user = relationship("User", foreign_keys=[updated_by_user_id])
