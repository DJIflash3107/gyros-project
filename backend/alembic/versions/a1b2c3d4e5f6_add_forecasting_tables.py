"""add forecasting tables

Revision ID: a1b2c3d4e5f6
Revises: 08602c33d914
Create Date: 2026-10-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "08602c33d914"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add forecast_runs and forecast_results tables."""
    op.create_table(
        "forecast_runs",
        sa.Column("id", sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"), nullable=False),
        sa.Column("branch_id", sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"), nullable=False),
        sa.Column("product_id", sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"), nullable=False),
        sa.Column("method", sa.String(length=40), nullable=False),
        sa.Column("horizon_days", sa.Integer().with_variant(mysql.INTEGER(unsigned=True), "mysql"), nullable=False),
        sa.Column("window_size", sa.Integer().with_variant(mysql.INTEGER(unsigned=True), "mysql"), nullable=False),
        sa.Column("training_start", sa.Date(), nullable=True),
        sa.Column("training_end", sa.Date(), nullable=True),
        sa.Column("observations_used", sa.Integer().with_variant(mysql.INTEGER(unsigned=True), "mysql"), nullable=False, server_default="0"),
        sa.Column("is_reliable", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("reliability_note", sa.String(length=500), nullable=True),
        sa.Column("mae", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("wape", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("forecast_bias", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"), nullable=True),
        sa.Column("created_at", sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], name="fk_fc_runs_business", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["business_id", "branch_id"], ["branches.business_id", "branches.id"], name="fk_fc_runs_branch_business", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["business_id", "product_id"], ["products.business_id", "products.id"], name="fk_fc_runs_product_business", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_fc_runs_user", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_fc_runs_biz", "forecast_runs", ["business_id"])
    op.create_index("idx_fc_runs_branch_prod", "forecast_runs", ["branch_id", "product_id"])

    op.create_table(
        "forecast_results",
        sa.Column("id", sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"), autoincrement=True, nullable=False),
        sa.Column("forecast_run_id", sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"), nullable=False),
        sa.Column("forecast_date", sa.Date(), nullable=False),
        sa.Column("predicted_qty", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("weekday", sa.Integer().with_variant(mysql.INTEGER(unsigned=True), "mysql"), nullable=True),
        sa.Column("created_at", sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["forecast_run_id"], ["forecast_runs.id"], name="fk_fc_results_run", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_fc_results_run", "forecast_results", ["forecast_run_id"])
    op.create_index("idx_fc_results_date", "forecast_results", ["forecast_date"])


def downgrade() -> None:
    """Downgrade schema to remove forecast_results and forecast_runs tables."""
    op.drop_index("idx_fc_results_date", table_name="forecast_results")
    op.drop_index("idx_fc_results_run", table_name="forecast_results")
    op.drop_table("forecast_results")
    op.drop_index("idx_fc_runs_branch_prod", table_name="forecast_runs")
    op.drop_index("idx_fc_runs_biz", table_name="forecast_runs")
    op.drop_table("forecast_runs")
