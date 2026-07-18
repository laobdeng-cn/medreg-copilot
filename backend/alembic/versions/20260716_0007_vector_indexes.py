"""Add asynchronous vector index job state.

Revision ID: 20260716_0007
Revises: 20260716_0006
Create Date: 2026-07-16 23:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0007"
down_revision: str | None = "20260716_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_vector_indexes",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("task_id", sa.String(length=50), nullable=True),
        sa.Column("collection_name", sa.String(length=120), nullable=False),
        sa.Column("dense_model", sa.String(length=160), nullable=False),
        sa.Column("sparse_model", sa.String(length=160), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("indexed_chunk_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("index_error", sa.Text(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["regulation_documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_index(
        op.f("ix_document_vector_indexes_status"),
        "document_vector_indexes",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_vector_indexes_task_id"),
        "document_vector_indexes",
        ["task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_vector_indexes_updated_at"),
        "document_vector_indexes",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_document_vector_indexes_updated_at"),
        table_name="document_vector_indexes",
    )
    op.drop_index(
        op.f("ix_document_vector_indexes_task_id"),
        table_name="document_vector_indexes",
    )
    op.drop_index(
        op.f("ix_document_vector_indexes_status"),
        table_name="document_vector_indexes",
    )
    op.drop_table("document_vector_indexes")
