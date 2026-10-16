from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from sqlalchemy import Date, Numeric, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.configs.database import Base
from app.models.types import BigIntId, IntUnsigned, DateTime6


class ForecastResult(Base):
    __tablename__ = "forecast_results"

    id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    forecast_run_id: Mapped[int] = mapped_column(
        BigIntId,
        ForeignKey("forecast_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    predicted_qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    weekday: Mapped[Optional[int]] = mapped_column(IntUnsigned, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now())

    # Constraints & Indexes
    __table_args__ = (
        Index("idx_fc_results_run", "forecast_run_id"),
        Index("idx_fc_results_date", "forecast_date"),
    )

    # Relationships
    forecast_run = relationship("ForecastRun", back_populates="predictions")
