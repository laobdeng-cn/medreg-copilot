"""Add asynchronous parse jobs and controlled fetch requests.

Revision ID: 20260716_0005
Revises: 20260716_0004
Create Date: 2026-07-16 21:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0005"
down_revision: str | None = "20260716_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "regulation_documents",
        sa.Column("parse_task_id", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "regulation_documents",
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "regulation_documents",
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_regulation_documents_parse_task_id"),
        "regulation_documents",
        ["parse_task_id"],
        unique=False,
    )

    op.create_table(
        "document_fetch_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("regulation_version_id", sa.Uuid(), nullable=False),
        sa.Column("official_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_by", sa.String(length=80), nullable=False),
        sa.Column("request_reason", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.String(length=80), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("task_id", sa.String(length=50), nullable=True),
        sa.Column("resulting_document_id", sa.Uuid(), nullable=True),
        sa.Column("fetch_error", sa.Text(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["regulation_version_id"],
            ["regulation_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resulting_document_id"],
            ["regulation_documents.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_document_fetch_requests_created_at"),
        "document_fetch_requests",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_fetch_requests_regulation_version_id"),
        "document_fetch_requests",
        ["regulation_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_fetch_requests_status"),
        "document_fetch_requests",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_fetch_requests_task_id"),
        "document_fetch_requests",
        ["task_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_document_fetch_requests_task_id"),
        table_name="document_fetch_requests",
    )
    op.drop_index(
        op.f("ix_document_fetch_requests_status"),
        table_name="document_fetch_requests",
    )
    op.drop_index(
        op.f("ix_document_fetch_requests_regulation_version_id"),
        table_name="document_fetch_requests",
    )
    op.drop_index(
        op.f("ix_document_fetch_requests_created_at"),
        table_name="document_fetch_requests",
    )
    op.drop_table("document_fetch_requests")
    op.drop_index(
        op.f("ix_regulation_documents_parse_task_id"),
        table_name="regulation_documents",
    )
    op.drop_column("regulation_documents", "processing_started_at")
    op.drop_column("regulation_documents", "queued_at")
    op.drop_column("regulation_documents", "parse_task_id")
