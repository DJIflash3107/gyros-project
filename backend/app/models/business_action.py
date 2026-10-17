from datetime import datetime
from decimal import Decimal
from typing import Optional, Any, List, Dict
from sqlalchemy import String, Numeric, Text, JSON, ForeignKey, Index, func, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.configs.database import Base
from app.models.types import BigIntId, DateTime6


class BusinessAction(Base):
    __tablename__ = "business_actions"

    id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        BigIntId, ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    rule_label: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    urgency: Mapped[str] = mapped_column(String(20), nullable=False)
    expected_impact: Mapped[str] = mapped_column(String(20), nullable=False)
    priority_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    evidence_quality: Mapped[str] = mapped_column(String(20), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    recommended_steps: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    risks: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    success_metrics: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    limitations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dismissed_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    branch_id: Mapped[Optional[int]] = mapped_column(
        BigIntId, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    product_id: Mapped[Optional[int]] = mapped_column(
        BigIntId, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    forecast_run_id: Mapped[Optional[int]] = mapped_column(
        BigIntId, ForeignKey("forecast_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )

    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigIntId, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigIntId, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime6, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_ba_biz_status", "business_id", "status"),
        Index("idx_ba_biz_priority", "business_id", "priority_score"),
        Index("idx_ba_biz_category", "business_id", "category"),
    )

    # Relationships
    business = relationship("Business")
    branch = relationship("Branch")
    product = relationship("Product")
    forecast_run = relationship("ForecastRun")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
    updated_by_user = relationship("User", foreign_keys=[updated_by_user_id])
