"""add draft status and multi photo columns

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-17 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. products table
    op.add_column(
        "products",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
    )
    op.add_column(
        "products",
        sa.Column("auto_created_from", sa.String(length=255), nullable=True),
    )

    # 2. branches table
    op.add_column(
        "branches",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
    )
    op.add_column(
        "branches",
        sa.Column("auto_created_from", sa.String(length=255), nullable=True),
    )

    # 3. sales_report_staging_rows table
    op.add_column(
        "sales_report_staging_rows",
        sa.Column(
            "source_image_index",
            sa.Integer().with_variant(mysql.INTEGER(unsigned=True), "mysql"),
            nullable=True,
        ),
    )
    op.add_column(
        "sales_report_staging_rows",
        sa.Column("source_image_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    # 3. sales_report_staging_rows table
    op.drop_column("sales_report_staging_rows", "source_image_name")
    op.drop_column("sales_report_staging_rows", "source_image_index")

    # 2. branches table
    op.drop_column("branches", "auto_created_from")
    op.drop_column("branches", "status")

    # 1. products table
    op.drop_column("products", "auto_created_from")
    op.drop_column("products", "status")
