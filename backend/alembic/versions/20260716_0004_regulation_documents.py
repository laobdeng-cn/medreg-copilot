"""Create controlled regulation document archive.

Revision ID: 20260716_0004
Revises: 20260716_0003
Create Date: 2026-07-16 19:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0004"
down_revision: str | None = "20260716_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "regulation_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("regulation_version_id", sa.Uuid(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("bucket_name", sa.String(length=80), nullable=False),
        sa.Column("object_key", sa.String(length=600), nullable=False),
        sa.Column("storage_status", sa.String(length=32), nullable=False),
        sa.Column("parse_status", sa.String(length=32), nullable=False),
        sa.Column("parse_attempts", sa.Integer(), nullable=False),
        sa.Column("parser_version", sa.String(length=80), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extracted_char_count", sa.Integer(), nullable=False),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("uploaded_by", sa.String(length=80), nullable=False),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["regulation_version_id"],
            ["regulation_versions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_regulation_documents_code"),
        "regulation_documents",
        ["code"],
        unique=True,
    )
    op.create_index(
        op.f("ix_regulation_documents_created_at"),
        "regulation_documents",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_regulation_documents_parse_status"),
        "regulation_documents",
        ["parse_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_regulation_documents_regulation_version_id"),
        "regulation_documents",
        ["regulation_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_regulation_documents_sha256"),
        "regulation_documents",
        ["sha256"],
        unique=False,
    )
    op.create_index(
        op.f("ix_regulation_documents_storage_status"),
        "regulation_documents",
        ["storage_status"],
        unique=False,
    )
    op.create_index(
        "ix_regulation_documents_version_sha256",
        "regulation_documents",
        ["regulation_version_id", "sha256"],
        unique=True,
    )
    op.create_unique_constraint(
        "uq_regulation_documents_object_key",
        "regulation_documents",
        ["object_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_regulation_documents_object_key",
        "regulation_documents",
        type_="unique",
    )
    op.drop_index(
        "ix_regulation_documents_version_sha256",
        table_name="regulation_documents",
    )
    op.drop_index(
        op.f("ix_regulation_documents_storage_status"),
        table_name="regulation_documents",
    )
    op.drop_index(
        op.f("ix_regulation_documents_sha256"),
        table_name="regulation_documents",
    )
    op.drop_index(
        op.f("ix_regulation_documents_regulation_version_id"),
        table_name="regulation_documents",
    )
    op.drop_index(
        op.f("ix_regulation_documents_parse_status"),
        table_name="regulation_documents",
    )
    op.drop_index(
        op.f("ix_regulation_documents_created_at"),
        table_name="regulation_documents",
    )
    op.drop_index(
        op.f("ix_regulation_documents_code"),
        table_name="regulation_documents",
    )
    op.drop_table("regulation_documents")
