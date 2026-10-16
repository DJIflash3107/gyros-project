from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.configs.database import Base
from app.models.types import BigIntId, DateTime6


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    memberships = relationship("BusinessMembership", back_populates="user", cascade="all, delete-orphan")
    submitted_sales_reports = relationship("SalesReportSubmission", back_populates="submitted_by_user")
