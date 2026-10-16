from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, CHAR, Date, Numeric, ForeignKey, ForeignKeyConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.configs.database import Base
from app.models.types import BigIntId, IntUnsigned, DateTime6


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=False, index=True)
    branch_id: Mapped[Optional[int]] = mapped_column(BigIntId, nullable=True, index=True)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, default="IDR")
    source_submission_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("sales_report_submissions.id", ondelete="SET NULL"), nullable=True)
    source_row_number: Mapped[Optional[int]] = mapped_column(IntUnsigned, nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now(), onupdate=func.now())

    # Constraints and Indexes
    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "branch_id"],
            ["branches.business_id", "branches.id"],
            ondelete="RESTRICT",
            name="fk_expenses_branch_business",
        ),
        Index("ix_expenses_biz_date_branch", "business_id", "expense_date", "branch_id"),
    )

    # Relationships
    business = relationship("Business", back_populates="expenses")
    branch = relationship("Branch", foreign_keys=[business_id, branch_id], overlaps="business,expenses")
    source_submission = relationship("SalesReportSubmission")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
