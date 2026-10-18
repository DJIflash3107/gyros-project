"""add artifacts table

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-10-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add artifacts table."""
    op.create_table(
        "artifacts",
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
        sa.Column("artifact_type", sa.String(length=50), nullable=False),
        sa.Column("file_format", sa.String(length=20), nullable=False),
        sa.Column("storage_backend", sa.String(length=20), nullable=False, server_default="local"),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=True),
        sa.Column("purpose", sa.String(length=50), nullable=True),
        sa.Column("source_entity_type", sa.String(length=50), nullable=True),
        sa.Column(
            "source_entity_id",
            sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"),
            nullable=True,
        ),
        sa.Column("generation_params", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ready"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"),
            nullable=True,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"),
            nullable=True,
        ),
        sa.Column("download_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "last_downloaded_at",
            sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"),
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
            ["business_id"], ["businesses.id"], name="fk_art_business", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], name="fk_art_created_by", ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'generating', 'ready', 'failed')",
            name="chk_artifacts_status",
        ),
        sa.CheckConstraint(
            "artifact_type IN ('report', 'plan', 'file', 'image')",
            name="chk_artifacts_type",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_artifacts_business_id", "artifacts", ["business_id"])
    op.create_index("ix_artifacts_artifact_type", "artifacts", ["artifact_type"])
    op.create_index("ix_artifacts_purpose", "artifacts", ["purpose"])
    op.create_index("ix_artifacts_status", "artifacts", ["status"])
    op.create_index("ix_artifacts_business_type", "artifacts", ["business_id", "artifact_type"])
    op.create_index("ix_artifacts_business_created", "artifacts", ["business_id", "created_at"])


def downgrade() -> None:
    """Downgrade schema to remove artifacts table."""
    op.drop_index("ix_artifacts_business_created", table_name="artifacts")
    op.drop_index("ix_artifacts_business_type", table_name="artifacts")
    op.drop_index("ix_artifacts_status", table_name="artifacts")
    op.drop_index("ix_artifacts_purpose", table_name="artifacts")
    op.drop_index("ix_artifacts_artifact_type", table_name="artifacts")
    op.drop_index("ix_artifacts_business_id", table_name="artifacts")
    op.drop_table("artifacts")
