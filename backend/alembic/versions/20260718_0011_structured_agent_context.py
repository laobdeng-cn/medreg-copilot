"""Add structured context and bilingual reports to agent runs.

Revision ID: 20260718_0011
Revises: 20260717_0010
Create Date: 2026-07-18 09:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260718_0011"
down_revision: str | None = "20260717_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_draft_runs",
        sa.Column(
            "language_mode",
            sa.String(length=24),
            server_default="zh_cn",
            nullable=False,
        ),
    )
    op.add_column(
        "agent_draft_runs",
        sa.Column("context_report", sa.JSON(), nullable=True),
    )
    op.add_column(
        "agent_draft_runs",
        sa.Column("structured_output", sa.JSON(), nullable=True),
    )
    op.add_column(
        "agent_draft_runs",
        sa.Column("bilingual_report", sa.JSON(), nullable=True),
    )
    op.create_index(
        op.f("ix_agent_draft_runs_language_mode"),
        "agent_draft_runs",
        ["language_mode"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_agent_draft_runs_language_mode"),
        table_name="agent_draft_runs",
    )
    op.drop_column("agent_draft_runs", "bilingual_report")
    op.drop_column("agent_draft_runs", "structured_output")
    op.drop_column("agent_draft_runs", "context_report")
    op.drop_column("agent_draft_runs", "language_mode")
