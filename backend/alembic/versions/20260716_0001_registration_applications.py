"""Create registration application tables.

Revision ID: 20260716_0001
Revises:
Create Date: 2026-07-16 09:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260716_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "registration_applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("product_name", sa.String(length=160), nullable=False),
        sa.Column("applicant_name", sa.String(length=160), nullable=False),
        sa.Column("jurisdiction", sa.String(length=32), nullable=False),
        sa.Column("device_class", sa.String(length=8), nullable=False),
        sa.Column("application_type", sa.String(length=48), nullable=False),
        sa.Column("regulation_effective_on", sa.Date(), nullable=False),
        sa.Column("owner_name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("completion_rate", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(
        op.f("ix_registration_applications_code"),
        "registration_applications",
        ["code"],
        unique=True,
    )
    op.create_index(
        op.f("ix_registration_applications_created_at"),
        "registration_applications",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_registration_applications_status"),
        "registration_applications",
        ["status"],
        unique=False,
    )

    op.create_table(
        "dossier_requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("category_key", sa.String(length=48), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("regulatory_basis", sa.Text(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["registration_applications.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dossier_requirements_application_key",
        "dossier_requirements",
        ["application_id", "category_key"],
        unique=True,
    )
    op.create_index(
        op.f("ix_dossier_requirements_application_id"),
        "dossier_requirements",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dossier_requirements_status"),
        "dossier_requirements",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_dossier_requirements_status"),
        table_name="dossier_requirements",
    )
    op.drop_index(
        op.f("ix_dossier_requirements_application_id"),
        table_name="dossier_requirements",
    )
    op.drop_index(
        "ix_dossier_requirements_application_key",
        table_name="dossier_requirements",
    )
    op.drop_table("dossier_requirements")
    op.drop_index(
        op.f("ix_registration_applications_status"),
        table_name="registration_applications",
    )
    op.drop_index(
        op.f("ix_registration_applications_created_at"),
        table_name="registration_applications",
    )
    op.drop_index(
        op.f("ix_registration_applications_code"),
        table_name="registration_applications",
    )
    op.drop_table("registration_applications")
