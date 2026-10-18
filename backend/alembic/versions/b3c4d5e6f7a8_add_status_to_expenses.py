"""add status to expenses

Revision ID: b3c4d5e6f7a8
Revises: f6a7b8c9d0e1
Create Date: 2026-10-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "expenses",
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
    )
    op.create_index(
        "ix_expenses_biz_status",
        "expenses",
        ["business_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_expenses_biz_status", table_name="expenses")
    op.drop_column("expenses", "status")
