from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.configs.database import Base
from app.models.types import BigIntId, DateTime6


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    sku: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    base_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    auto_created_from: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now(), onupdate=func.now())

    # Constraints
    __table_args__ = (
        UniqueConstraint("business_id", "name", name="uq_products_business_name"),
        UniqueConstraint("business_id", "sku", name="uq_products_business_sku"),
        UniqueConstraint("business_id", "id", name="uq_products_business_id"),
    )

    # Relationships
    business = relationship("Business", back_populates="products")
    aliases = relationship("ProductAlias", back_populates="product", cascade="all, delete-orphan")
    observations = relationship("SalesReportObservation", back_populates="product", overlaps="observations,branch")
    cost_history = relationship("ProductCostHistory", back_populates="product", cascade="all, delete-orphan")
    price_history = relationship("ProductPriceHistory", back_populates="product", cascade="all, delete-orphan")
