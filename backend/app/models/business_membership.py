from datetime import datetime
from sqlalchemy import String, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.configs.database import Base
from app.models.types import BigIntId, DateTime6


class BusinessMembership(Base):
    __tablename__ = "business_memberships"

    id: Mapped[int] = mapped_column(BigIntId, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime6, nullable=False, server_default=func.now())

    # Constraints
    __table_args__ = (
        UniqueConstraint("business_id", "user_id", name="uq_business_membership_business_user"),
    )

    # Relationships
    business = relationship("Business", back_populates="memberships")
    user = relationship("User", back_populates="memberships")
