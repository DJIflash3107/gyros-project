from datetime import datetime
from sqlalchemy import String, CHAR, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.configs.database import Base
from app.models.types import BigIntId, DateTime6


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, default="IDR")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Jakarta")
    created_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    memberships = relationship("BusinessMembership", back_populates="business", cascade="all, delete-orphan")
    branches = relationship("Branch", back_populates="business")
    products = relationship("Product", back_populates="business")
    sales_submissions = relationship("SalesReportSubmission", back_populates="business")
    expenses = relationship("Expense", back_populates="business")
