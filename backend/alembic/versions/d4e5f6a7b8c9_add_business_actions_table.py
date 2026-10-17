"""add business_actions table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-17 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add business_actions table."""
    op.create_table(
        "business_actions",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "business_id",
            sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("urgency", sa.String(length=20), nullable=False),
        sa.Column("expected_impact", sa.String(length=20), nullable=False),
        sa.Column("priority_score", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("evidence_quality", sa.String(length=20), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("supporting_data", sa.JSON(), nullable=True),
        sa.Column("recommended_steps", sa.JSON(), nullable=True),
        sa.Column("risks", sa.JSON(), nullable=True),
        sa.Column("success_metrics", sa.JSON(), nullable=True),
        sa.Column("limitations", sa.Text(), nullable=True),
        sa.Column("dismissed_reason", sa.String(length=255), nullable=True),
        sa.Column(
            "branch_id",
            sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"),
            nullable=True,
        ),
        sa.Column(
            "product_id",
            sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"),
            nullable=True,
        ),
        sa.Column(
            "forecast_run_id",
            sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_user_id",
            sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["business_id"], ["businesses.id"], name="fk_ba_business", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"], name="fk_ba_branch", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name="fk_ba_product", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["forecast_run_id"],
            ["forecast_runs.id"],
            name="fk_ba_forecast_run",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], name="fk_ba_created_by", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["users.id"], name="fk_ba_updated_by", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ba_biz_id", "business_actions", ["business_id"])
    op.create_index("idx_ba_action_type", "business_actions", ["action_type"])
    op.create_index("idx_ba_category", "business_actions", ["category"])
    op.create_index("idx_ba_status", "business_actions", ["status"])
    op.create_index("idx_ba_priority", "business_actions", ["priority_score"])
    op.create_index("idx_ba_branch_id", "business_actions", ["branch_id"])
    op.create_index("idx_ba_product_id", "business_actions", ["product_id"])
    op.create_index("idx_ba_forecast_run_id", "business_actions", ["forecast_run_id"])
    op.create_index("idx_ba_biz_status", "business_actions", ["business_id", "status"])
    op.create_index("idx_ba_biz_priority", "business_actions", ["business_id", "priority_score"])
    op.create_index("idx_ba_biz_category", "business_actions", ["business_id", "category"])


def downgrade() -> None:
    """Downgrade schema to remove business_actions table."""
    op.drop_index("idx_ba_biz_category", table_name="business_actions")
    op.drop_index("idx_ba_biz_priority", table_name="business_actions")
    op.drop_index("idx_ba_biz_status", table_name="business_actions")
    op.drop_index("idx_ba_forecast_run_id", table_name="business_actions")
    op.drop_index("idx_ba_product_id", table_name="business_actions")
    op.drop_index("idx_ba_branch_id", table_name="business_actions")
    op.drop_index("idx_ba_priority", table_name="business_actions")
    op.drop_index("idx_ba_status", table_name="business_actions")
    op.drop_index("idx_ba_category", table_name="business_actions")
    op.drop_index("idx_ba_action_type", table_name="business_actions")
    op.drop_index("idx_ba_biz_id", table_name="business_actions")
    op.drop_table("business_actions")
