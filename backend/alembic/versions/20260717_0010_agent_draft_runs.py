"""Add auditable agent drafting runs and approval state.

Revision ID: 20260717_0010
Revises: 20260717_0009
Create Date: 2026-07-17 20:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_0010"
down_revision: str | None = "20260717_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_draft_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_version", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("target_section", sa.String(length=64), nullable=False),
        sa.Column("requested_by", sa.String(length=80), nullable=False),
        sa.Column("input_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("prompt_version", sa.String(length=48), nullable=False),
        sa.Column("prompt_snapshot", sa.Text(), nullable=False),
        sa.Column("model_provider", sa.String(length=48), nullable=False),
        sa.Column("model_name", sa.String(length=80), nullable=False),
        sa.Column("model_mode", sa.String(length=24), nullable=False),
        sa.Column("model_error", sa.Text(), nullable=True),
        sa.Column("draft_title", sa.String(length=200), nullable=False),
        sa.Column("draft_content", sa.Text(), nullable=False),
        sa.Column("reviewer_summary", sa.Text(), nullable=False),
        sa.Column("node_traces", sa.JSON(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column(
            "approval_status",
            sa.String(length=24),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("reviewed_by", sa.String(length=80), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["registration_applications.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_draft_runs_application_id"),
        "agent_draft_runs",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        "ix_agent_draft_runs_application_created",
        "agent_draft_runs",
        ["application_id", "created_at"],
        unique=False,
    )
    for column in (
        "approval_status",
        "created_at",
        "input_snapshot_hash",
        "model_mode",
        "status",
        "target_section",
    ):
        op.create_index(
            op.f(f"ix_agent_draft_runs_{column}"),
            "agent_draft_runs",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in (
        "target_section",
        "status",
        "model_mode",
        "input_snapshot_hash",
        "created_at",
        "approval_status",
    ):
        op.drop_index(
            op.f(f"ix_agent_draft_runs_{column}"),
            table_name="agent_draft_runs",
        )
    op.drop_index(
        "ix_agent_draft_runs_application_created",
        table_name="agent_draft_runs",
    )
    op.drop_index(
        op.f("ix_agent_draft_runs_application_id"),
        table_name="agent_draft_runs",
    )
    op.drop_table("agent_draft_runs")
