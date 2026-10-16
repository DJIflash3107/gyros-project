from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Date, Numeric, ForeignKey, ForeignKeyConstraint, UniqueConstraint, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.configs.database import Base
from app.models.types import BigIntId, DateTime6


class ProductCostHistory(Base):
    __tablename__ = "product_cost_history"

    id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(BigIntId, nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(BigIntId, nullable=False, index=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    cost_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    source_submission_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("sales_report_submissions.id", ondelete="SET NULL"), nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now())

    # Constraints
    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "product_id"],
            ["products.business_id", "products.id"],
            ondelete="CASCADE",
            name="fk_product_cost_history_product_business",
        ),
        UniqueConstraint("business_id", "product_id", "effective_from", name="uq_product_cost_history_effective_from"),
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="chk_product_cost_history_dates"),
    )

    # Relationships
    product = relationship("Product", back_populates="cost_history", foreign_keys=[business_id, product_id])
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
    source_submission = relationship("SalesReportSubmission")
