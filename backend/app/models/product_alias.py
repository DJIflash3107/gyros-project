from datetime import datetime
from typing import Optional
from sqlalchemy import String, ForeignKey, ForeignKeyConstraint, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.configs.database import Base
from app.models.types import BigIntId, DateTime6


class ProductAlias(Base):
    __tablename__ = "product_aliases"

    id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(BigIntId, nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(BigIntId, nullable=False, index=True)
    alias_name: Mapped[str] = mapped_column(String(150), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(180), nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now())

    # Constraints
    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "product_id"],
            ["products.business_id", "products.id"],
            ondelete="CASCADE",
            name="fk_product_aliases_product_business",
        ),
        UniqueConstraint("business_id", "normalized_alias", name="uq_product_aliases_business_norm_alias"),
    )

    # Relationships
    product = relationship("Product", back_populates="aliases", foreign_keys=[business_id, product_id])
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
