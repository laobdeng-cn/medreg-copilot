"""Add legal document sections and citation chunks.

Revision ID: 20260716_0006
Revises: 20260716_0005
Create Date: 2026-07-16 23:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0006"
down_revision: str | None = "20260716_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "regulation_documents",
        sa.Column("segmenter_version", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "regulation_documents",
        sa.Column(
            "section_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "regulation_documents",
        sa.Column(
            "chunk_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )

    op.create_table(
        "document_sections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(length=300), nullable=False),
        sa.Column("citation_path", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["regulation_documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["document_sections.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_sections_document_ordinal",
        "document_sections",
        ["document_id", "ordinal"],
        unique=True,
    )
    op.create_index(
        op.f("ix_document_sections_content_hash"),
        "document_sections",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_sections_document_id"),
        "document_sections",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_sections_kind"),
        "document_sections",
        ["kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_sections_parent_id"),
        "document_sections",
        ["parent_id"],
        unique=False,
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("section_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("section_chunk_index", sa.Integer(), nullable=False),
        sa.Column("citation_label", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["regulation_documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["section_id"],
            ["document_sections.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_chunks_document_ordinal",
        "document_chunks",
        ["document_id", "ordinal"],
        unique=True,
    )
    op.create_index(
        "ix_document_chunks_section_index",
        "document_chunks",
        ["section_id", "section_chunk_index"],
        unique=True,
    )
    op.create_index(
        op.f("ix_document_chunks_content_hash"),
        "document_chunks",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_chunks_document_id"),
        "document_chunks",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_chunks_section_id"),
        "document_chunks",
        ["section_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_document_chunks_section_id"),
        table_name="document_chunks",
    )
    op.drop_index(
        op.f("ix_document_chunks_document_id"),
        table_name="document_chunks",
    )
    op.drop_index(
        op.f("ix_document_chunks_content_hash"),
        table_name="document_chunks",
    )
    op.drop_index(
        "ix_document_chunks_section_index",
        table_name="document_chunks",
    )
    op.drop_index(
        "ix_document_chunks_document_ordinal",
        table_name="document_chunks",
    )
    op.drop_table("document_chunks")

    op.drop_index(
        op.f("ix_document_sections_parent_id"),
        table_name="document_sections",
    )
    op.drop_index(
        op.f("ix_document_sections_kind"),
        table_name="document_sections",
    )
    op.drop_index(
        op.f("ix_document_sections_document_id"),
        table_name="document_sections",
    )
    op.drop_index(
        op.f("ix_document_sections_content_hash"),
        table_name="document_sections",
    )
    op.drop_index(
        "ix_document_sections_document_ordinal",
        table_name="document_sections",
    )
    op.drop_table("document_sections")

    op.drop_column("regulation_documents", "chunk_count")
    op.drop_column("regulation_documents", "section_count")
    op.drop_column("regulation_documents", "segmenter_version")
