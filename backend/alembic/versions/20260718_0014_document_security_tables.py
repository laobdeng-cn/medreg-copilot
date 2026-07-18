"""Add document security metadata and structured tables.

Revision ID: 20260718_0014
Revises: 20260718_0013
Create Date: 2026-07-18 14:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0014"
down_revision: str | None = "20260718_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "regulation_documents",
        sa.Column(
            "security_status",
            sa.String(length=24),
            nullable=False,
            server_default="legacy",
        ),
    )
    op.add_column(
        "regulation_documents",
        sa.Column(
            "security_engine",
            sa.String(length=80),
            nullable=False,
            server_default="pre-v3-archive",
        ),
    )
    op.add_column(
        "regulation_documents",
        sa.Column(
            "detected_type",
            sa.String(length=24),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column(
        "regulation_documents",
        sa.Column(
            "security_findings",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "regulation_documents",
        sa.Column("table_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        op.f("ix_regulation_documents_security_status"),
        "regulation_documents",
        ["security_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_regulation_documents_detected_type"),
        "regulation_documents",
        ["detected_type"],
        unique=False,
    )

    op.create_table(
        "document_tables",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("sheet_name", sa.String(length=160), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("column_count", sa.Integer(), nullable=False),
        sa.Column("headers", sa.JSON(), nullable=False),
        sa.Column("rows", sa.JSON(), nullable=False),
        sa.Column("source_locator", sa.String(length=300), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["regulation_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_tables_document_ordinal",
        "document_tables",
        ["document_id", "ordinal"],
        unique=True,
    )
    op.create_index(
        op.f("ix_document_tables_document_id"),
        "document_tables",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_tables_content_hash"),
        "document_tables",
        ["content_hash"],
        unique=False,
    )

    for column in (
        "security_status",
        "security_engine",
        "detected_type",
        "security_findings",
        "table_count",
    ):
        op.alter_column("regulation_documents", column, server_default=None)


def downgrade() -> None:
    op.drop_table("document_tables")
    op.drop_index(
        op.f("ix_regulation_documents_detected_type"),
        table_name="regulation_documents",
    )
    op.drop_index(
        op.f("ix_regulation_documents_security_status"),
        table_name="regulation_documents",
    )
    op.drop_column("regulation_documents", "table_count")
    op.drop_column("regulation_documents", "security_findings")
    op.drop_column("regulation_documents", "detected_type")
    op.drop_column("regulation_documents", "security_engine")
    op.drop_column("regulation_documents", "security_status")
