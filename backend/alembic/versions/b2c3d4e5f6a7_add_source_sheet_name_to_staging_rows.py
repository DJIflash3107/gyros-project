"""add source_sheet_name to staging rows

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-17 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add source_sheet_name column to sales_report_staging_rows table."""
    op.add_column(
        "sales_report_staging_rows",
        sa.Column("source_sheet_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema to remove source_sheet_name column from sales_report_staging_rows table."""
    op.drop_column("sales_report_staging_rows", "source_sheet_name")
