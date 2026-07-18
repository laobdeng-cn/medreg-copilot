"""Add persisted evaluation runs.

Revision ID: 20260718_0012
Revises: 20260718_0011
Create Date: 2026-07-18 11:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0012"
down_revision: str | None = "20260718_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version", sa.String(length=64), nullable=False),
        sa.Column("dataset_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("requested_by", sa.String(length=80), nullable=False),
        sa.Column("baseline_name", sa.String(length=80), nullable=False),
        sa.Column("candidate_name", sa.String(length=80), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("task_summaries", sa.JSON(), nullable=False),
        sa.Column("quality_gate", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_evaluation_runs_created_at"),
        "evaluation_runs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_runs_dataset_hash"),
        "evaluation_runs",
        ["dataset_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_runs_dataset_version"),
        "evaluation_runs",
        ["dataset_version"],
        unique=False,
    )
    op.create_index(
        "ix_evaluation_runs_dataset_created",
        "evaluation_runs",
        ["dataset_version", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_runs_status"),
        "evaluation_runs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_evaluation_runs_status"), table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_dataset_created", table_name="evaluation_runs")
    op.drop_index(
        op.f("ix_evaluation_runs_dataset_version"),
        table_name="evaluation_runs",
    )
    op.drop_index(
        op.f("ix_evaluation_runs_dataset_hash"),
        table_name="evaluation_runs",
    )
    op.drop_index(op.f("ix_evaluation_runs_created_at"), table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
