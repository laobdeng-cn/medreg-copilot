"""Create regulation source and version tables.

Revision ID: 20260716_0003
Revises: 20260716_0002
Create Date: 2026-07-16 11:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260716_0003"
down_revision: str | None = "20260716_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "regulation_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("issuing_authority", sa.String(length=160), nullable=False),
        sa.Column("jurisdiction", sa.String(length=32), nullable=False),
        sa.Column("regulation_type", sa.String(length=48), nullable=False),
        sa.Column("scope_summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_regulation_sources_code"), "regulation_sources", ["code"], unique=True)
    op.create_index(op.f("ix_regulation_sources_created_at"), "regulation_sources", ["created_at"], unique=False)
    op.create_index(op.f("ix_regulation_sources_issuing_authority"), "regulation_sources", ["issuing_authority"], unique=False)
    op.create_index(op.f("ix_regulation_sources_jurisdiction"), "regulation_sources", ["jurisdiction"], unique=False)
    op.create_index(op.f("ix_regulation_sources_regulation_type"), "regulation_sources", ["regulation_type"], unique=False)

    op.create_table(
        "regulation_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("version_label", sa.String(length=80), nullable=False),
        sa.Column("document_number", sa.String(length=120), nullable=False),
        sa.Column("official_url", sa.Text(), nullable=False),
        sa.Column("published_on", sa.Date(), nullable=False),
        sa.Column("effective_on", sa.Date(), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("reviewed_by", sa.String(length=80), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["regulation_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_regulation_versions_created_at"), "regulation_versions", ["created_at"], unique=False)
    op.create_index(op.f("ix_regulation_versions_document_number"), "regulation_versions", ["document_number"], unique=False)
    op.create_index(op.f("ix_regulation_versions_effective_on"), "regulation_versions", ["effective_on"], unique=False)
    op.create_index(op.f("ix_regulation_versions_review_status"), "regulation_versions", ["review_status"], unique=False)
    op.create_index(op.f("ix_regulation_versions_source_id"), "regulation_versions", ["source_id"], unique=False)
    op.create_index("ix_regulation_versions_source_label", "regulation_versions", ["source_id", "version_label"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_regulation_versions_source_label", table_name="regulation_versions")
    op.drop_index(op.f("ix_regulation_versions_source_id"), table_name="regulation_versions")
    op.drop_index(op.f("ix_regulation_versions_review_status"), table_name="regulation_versions")
    op.drop_index(op.f("ix_regulation_versions_effective_on"), table_name="regulation_versions")
    op.drop_index(op.f("ix_regulation_versions_document_number"), table_name="regulation_versions")
    op.drop_index(op.f("ix_regulation_versions_created_at"), table_name="regulation_versions")
    op.drop_table("regulation_versions")
    op.drop_index(op.f("ix_regulation_sources_regulation_type"), table_name="regulation_sources")
    op.drop_index(op.f("ix_regulation_sources_jurisdiction"), table_name="regulation_sources")
    op.drop_index(op.f("ix_regulation_sources_issuing_authority"), table_name="regulation_sources")
    op.drop_index(op.f("ix_regulation_sources_created_at"), table_name="regulation_sources")
    op.drop_index(op.f("ix_regulation_sources_code"), table_name="regulation_sources")
    op.drop_table("regulation_sources")
