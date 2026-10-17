"""add promotion_plans table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-17 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add promotion_plans table."""
    op.create_table(
        "promotion_plans",
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
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("promotion_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column(
            "branch_id",
            sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"),
            nullable=True,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("total_original_revenue", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("total_discounted_revenue", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("total_estimated_cost", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("total_estimated_margin", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("avg_margin_pct", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("is_financially_validated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("min_margin_pct", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("assumptions", sa.JSON(), nullable=True),
        sa.Column("missing_data", sa.JSON(), nullable=True),
        sa.Column("risks", sa.JSON(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("recommended_actions", sa.JSON(), nullable=True),
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
            "approved_by_user_id",
            sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"),
            nullable=True,
        ),
        sa.Column(
            "approved_at",
            sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"),
            nullable=True,
        ),
        sa.Column("rejected_reason", sa.String(length=500), nullable=True),
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
            ["business_id"], ["businesses.id"], name="fk_pp_business", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"], name="fk_pp_branch", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], name="fk_pp_created_by", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["users.id"], name="fk_pp_updated_by", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"], ["users.id"], name="fk_pp_approved_by", ondelete="SET NULL"
        ),
        sa.CheckConstraint("end_date > start_date", name="chk_pp_dates"),
        sa.CheckConstraint("status IN ('draft', 'approved', 'rejected', 'archived')", name="chk_pp_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_pp_biz_id", "promotion_plans", ["business_id"])
    op.create_index("idx_pp_branch_id", "promotion_plans", ["branch_id"])
    op.create_index("idx_pp_status", "promotion_plans", ["status"])
    op.create_index("idx_pp_biz_status", "promotion_plans", ["business_id", "status"])
    op.create_index("idx_pp_biz_dates", "promotion_plans", ["business_id", "start_date", "end_date"])


def downgrade() -> None:
    """Downgrade schema to remove promotion_plans table."""
    op.drop_index("idx_pp_biz_dates", table_name="promotion_plans")
    op.drop_index("idx_pp_biz_status", table_name="promotion_plans")
    op.drop_index("idx_pp_status", table_name="promotion_plans")
    op.drop_index("idx_pp_branch_id", table_name="promotion_plans")
    op.drop_index("idx_pp_biz_id", table_name="promotion_plans")
    op.drop_table("promotion_plans")
