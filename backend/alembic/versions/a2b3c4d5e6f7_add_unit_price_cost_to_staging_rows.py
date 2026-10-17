"""add unit_price and unit_cost to sales_report_staging_rows

Revision ID: a2b3c4d5e6f7
Revises: f6a7b8c9d0e1
Create Date: 2026-10-17 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unit_price and unit_cost columns to sales_report_staging_rows."""
    op.add_column(
        "sales_report_staging_rows",
        sa.Column("unit_price", sa.Numeric(precision=14, scale=2), nullable=True),
    )
    op.add_column(
        "sales_report_staging_rows",
        sa.Column("unit_cost", sa.Numeric(precision=14, scale=2), nullable=True),
    )


def downgrade() -> None:
    """Remove unit_price and unit_cost columns from sales_report_staging_rows."""
    op.drop_column("sales_report_staging_rows", "unit_cost")
    op.drop_column("sales_report_staging_rows", "unit_price")
