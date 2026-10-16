from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import String, Date, Numeric, Boolean, ForeignKey, ForeignKeyConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.configs.database import Base
from app.models.types import BigIntId, IntUnsigned, DateTime6


class ForecastRun(Base):
    __tablename__ = "forecast_runs"

    id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(BigIntId, nullable=False, index=True)
    branch_id: Mapped[int] = mapped_column(BigIntId, nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(BigIntId, nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(40), nullable=False)
    horizon_days: Mapped[int] = mapped_column(IntUnsigned, nullable=False)
    window_size: Mapped[int] = mapped_column(IntUnsigned, nullable=False)
    training_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    training_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    observations_used: Mapped[int] = mapped_column(IntUnsigned, nullable=False, default=0)
    is_reliable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reliability_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Evaluation metrics (populated during backtesting or evaluation)
    mae: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    wape: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    forecast_bias: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)

    created_by_user_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now())

    # Constraints & Indexes
    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            ondelete="RESTRICT",
            name="fk_fc_runs_business",
        ),
        ForeignKeyConstraint(
            ["business_id", "branch_id"],
            ["branches.business_id", "branches.id"],
            ondelete="RESTRICT",
            name="fk_fc_runs_branch_business",
        ),
        ForeignKeyConstraint(
            ["business_id", "product_id"],
            ["products.business_id", "products.id"],
            ondelete="RESTRICT",
            name="fk_fc_runs_product_business",
        ),
        Index("idx_fc_runs_biz", "business_id"),
        Index("idx_fc_runs_branch_prod", "branch_id", "product_id"),
    )

    # Relationships
    predictions: Mapped[List["ForecastResult"]] = relationship(
        "ForecastResult",
        back_populates="forecast_run",
        cascade="all, delete-orphan",
        order_by="ForecastResult.forecast_date",
    )
    business = relationship("Business", foreign_keys=[business_id])
    branch = relationship("Branch", foreign_keys=[business_id, branch_id], overlaps="business")
    product = relationship("Product", foreign_keys=[business_id, product_id], overlaps="branch,business")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
