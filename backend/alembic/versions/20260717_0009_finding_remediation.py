"""Add remediation workflow state to precheck findings.

Revision ID: 20260717_0009
Revises: 20260717_0008
Create Date: 2026-07-17 16:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_0009"
down_revision: str | None = "20260717_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "precheck_findings",
        sa.Column(
            "remediation_status",
            sa.String(length=24),
            server_default="open",
            nullable=False,
        ),
    )
    op.add_column(
        "precheck_findings",
        sa.Column("assignee", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "precheck_findings",
        sa.Column("resolution_note", sa.Text(), nullable=True),
    )
    op.add_column(
        "precheck_findings",
        sa.Column("updated_by", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "precheck_findings",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "precheck_findings",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_precheck_findings_remediation_status"),
        "precheck_findings",
        ["remediation_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_precheck_findings_remediation_status"),
        table_name="precheck_findings",
    )
    op.drop_column("precheck_findings", "updated_at")
    op.drop_column("precheck_findings", "resolved_at")
    op.drop_column("precheck_findings", "updated_by")
    op.drop_column("precheck_findings", "resolution_note")
    op.drop_column("precheck_findings", "assignee")
    op.drop_column("precheck_findings", "remediation_status")
