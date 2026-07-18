"""Add dossier evidence and deterministic precheck records.

Revision ID: 20260717_0008
Revises: 20260716_0007
Create Date: 2026-07-17 10:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_0008"
down_revision: str | None = "20260716_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dossier_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("category_key", sa.String(length=48), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("bucket_name", sa.String(length=80), nullable=False),
        sa.Column("object_key", sa.String(length=600), nullable=False),
        sa.Column("uploaded_by", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["registration_applications.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index(
        op.f("ix_dossier_evidence_application_id"),
        "dossier_evidence",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dossier_evidence_category_key"),
        "dossier_evidence",
        ["category_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dossier_evidence_created_at"),
        "dossier_evidence",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dossier_evidence_sha256"),
        "dossier_evidence",
        ["sha256"],
        unique=False,
    )
    op.create_index(
        "ix_dossier_evidence_application_category_sha256",
        "dossier_evidence",
        ["application_id", "category_key", "sha256"],
        unique=True,
    )

    op.create_table(
        "precheck_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rule_set_version", sa.String(length=48), nullable=False),
        sa.Column("application_status", sa.String(length=32), nullable=False),
        sa.Column("blocker_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("warning_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("pass_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("initiated_by", sa.String(length=80), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["registration_applications.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_precheck_runs_application_id"),
        "precheck_runs",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_precheck_runs_created_at"),
        "precheck_runs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_precheck_runs_status"),
        "precheck_runs",
        ["status"],
        unique=False,
    )

    op.create_table(
        "precheck_findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("category_key", sa.String(length=48), nullable=False),
        sa.Column("rule_code", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("regulatory_basis", sa.Text(), nullable=False),
        sa.Column("remediation", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["precheck_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_precheck_findings_category_key"),
        "precheck_findings",
        ["category_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_precheck_findings_rule_code"),
        "precheck_findings",
        ["rule_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_precheck_findings_run_id"),
        "precheck_findings",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_precheck_findings_severity"),
        "precheck_findings",
        ["severity"],
        unique=False,
    )
    op.create_index(
        "ix_precheck_findings_run_rule_category",
        "precheck_findings",
        ["run_id", "rule_code", "category_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_precheck_findings_run_rule_category",
        table_name="precheck_findings",
    )
    op.drop_index(
        op.f("ix_precheck_findings_severity"),
        table_name="precheck_findings",
    )
    op.drop_index(
        op.f("ix_precheck_findings_run_id"),
        table_name="precheck_findings",
    )
    op.drop_index(
        op.f("ix_precheck_findings_rule_code"),
        table_name="precheck_findings",
    )
    op.drop_index(
        op.f("ix_precheck_findings_category_key"),
        table_name="precheck_findings",
    )
    op.drop_table("precheck_findings")

    op.drop_index(op.f("ix_precheck_runs_status"), table_name="precheck_runs")
    op.drop_index(op.f("ix_precheck_runs_created_at"), table_name="precheck_runs")
    op.drop_index(
        op.f("ix_precheck_runs_application_id"),
        table_name="precheck_runs",
    )
    op.drop_table("precheck_runs")

    op.drop_index(
        "ix_dossier_evidence_application_category_sha256",
        table_name="dossier_evidence",
    )
    op.drop_index(
        op.f("ix_dossier_evidence_sha256"),
        table_name="dossier_evidence",
    )
    op.drop_index(
        op.f("ix_dossier_evidence_created_at"),
        table_name="dossier_evidence",
    )
    op.drop_index(
        op.f("ix_dossier_evidence_category_key"),
        table_name="dossier_evidence",
    )
    op.drop_index(
        op.f("ix_dossier_evidence_application_id"),
        table_name="dossier_evidence",
    )
    op.drop_table("dossier_evidence")
