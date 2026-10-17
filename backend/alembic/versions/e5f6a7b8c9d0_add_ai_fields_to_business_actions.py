"""add ai fields to business_actions

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-17 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add rule_label and ai_generated columns to business_actions."""
    op.add_column(
        "business_actions",
        sa.Column("rule_label", sa.String(length=50), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "business_actions",
        sa.Column("ai_generated", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    """Remove rule_label and ai_generated columns from business_actions."""
    op.drop_column("business_actions", "ai_generated")
    op.drop_column("business_actions", "rule_label")
