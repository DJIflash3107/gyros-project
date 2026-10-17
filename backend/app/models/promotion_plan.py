from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Any, List, Dict
from sqlalchemy import String, Numeric, Text, JSON, ForeignKey, Index, CheckConstraint, func, Boolean, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.configs.database import Base
from app.models.types import BigIntId, DateTime6


class PromotionPlan(Base):
    __tablename__ = "promotion_plans"

    id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        BigIntId, ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    promotion_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)

    branch_id: Mapped[Optional[int]] = mapped_column(
        BigIntId, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True
    )

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    items: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)

    total_original_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    total_discounted_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    total_estimated_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    total_estimated_margin: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    avg_margin_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    is_financially_validated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    min_margin_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)

    warnings: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    assumptions: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    missing_data: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    risks: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_actions: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigIntId, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigIntId, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigIntId, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime6, nullable=True)
    rejected_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime6, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_pp_biz_status", "business_id", "status"),
        Index("idx_pp_biz_dates", "business_id", "start_date", "end_date"),
        CheckConstraint("end_date > start_date", name="chk_pp_dates"),
        CheckConstraint("status IN ('draft', 'approved', 'rejected', 'archived')", name="chk_pp_status"),
    )

    # Relationships
    business = relationship("Business")
    branch = relationship("Branch")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
    updated_by_user = relationship("User", foreign_keys=[updated_by_user_id])
    approved_by_user = relationship("User", foreign_keys=[approved_by_user_id])
