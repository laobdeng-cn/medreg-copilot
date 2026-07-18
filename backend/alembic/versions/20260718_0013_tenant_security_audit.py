"""Add tenant security, role memberships and immutable audit records.

Revision ID: 20260718_0013
Revises: 20260718_0012
Create Date: 2026-07-18 12:30:00
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "20260718_0013"
down_revision: str | None = "20260718_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEMO_TENANT_ID = "11111111-1111-4111-8111-111111111111"
DEMO_USERS = (
    (
        "22222222-2222-4222-8222-222222222221",
        "刘凯旗",
        "liukaiqi@demo.medreg.cn",
        "owner",
    ),
    (
        "22222222-2222-4222-8222-222222222222",
        "张法规",
        "reviewer@demo.medreg.cn",
        "reviewer",
    ),
    (
        "22222222-2222-4222-8222-222222222223",
        "陈工程师",
        "engineer@demo.medreg.cn",
        "editor",
    ),
    (
        "22222222-2222-4222-8222-222222222224",
        "王观察员",
        "viewer@demo.medreg.cn",
        "viewer",
    ),
)


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tenants_slug"), "tenants", ["slug"], unique=True)
    op.create_index(op.f("ix_tenants_status"), "tenants", ["status"], unique=False)
    op.create_index(
        op.f("ix_tenants_created_at"), "tenants", ["created_at"], unique=False
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_status"), "users", ["status"], unique=False)
    op.create_index(
        op.f("ix_users_created_at"), "users", ["created_at"], unique=False
    )

    op.create_table(
        "tenant_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tenant_memberships_tenant_user",
        "tenant_memberships",
        ["tenant_id", "user_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_tenant_memberships_tenant_id"),
        "tenant_memberships",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tenant_memberships_user_id"),
        "tenant_memberships",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tenant_memberships_role"),
        "tenant_memberships",
        ["role"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tenant_memberships_status"),
        "tenant_memberships",
        ["status"],
        unique=False,
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_name", sa.String(length=80), nullable=False),
        sa.Column("actor_role", sa.String(length=24), nullable=False),
        sa.Column("action", sa.String(length=96), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("request_method", sa.String(length=12), nullable=False),
        sa.Column("request_path", sa.String(length=500), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_events_tenant_created",
        "audit_events",
        ["tenant_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_tenant_action",
        "audit_events",
        ["tenant_id", "action"],
        unique=False,
    )
    for column in (
        "tenant_id",
        "actor_user_id",
        "action",
        "resource_type",
        "outcome",
        "created_at",
    ):
        op.create_index(op.f(f"ix_audit_events_{column}"), "audit_events", [column])
    op.create_index(
        op.f("ix_audit_events_request_id"),
        "audit_events",
        ["request_id"],
        unique=True,
    )

    now = datetime.now(UTC)
    tenants = sa.table(
        "tenants",
        sa.column("id", sa.Uuid()),
        sa.column("slug", sa.String()),
        sa.column("name", sa.String()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    users = sa.table(
        "users",
        sa.column("id", sa.Uuid()),
        sa.column("display_name", sa.String()),
        sa.column("email", sa.String()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    memberships = sa.table(
        "tenant_memberships",
        sa.column("id", sa.Uuid()),
        sa.column("tenant_id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("role", sa.String()),
        sa.column("status", sa.String()),
        sa.column("joined_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        tenants,
        [
            {
                "id": DEMO_TENANT_ID,
                "slug": "shenzhen-demo-medtech",
                "name": "深圳示例医疗科技有限公司",
                "status": "active",
                "created_at": now,
            }
        ],
    )
    op.bulk_insert(
        users,
        [
            {
                "id": user_id,
                "display_name": name,
                "email": email,
                "status": "active",
                "created_at": now,
            }
            for user_id, name, email, _ in DEMO_USERS
        ],
    )
    op.bulk_insert(
        memberships,
        [
            {
                "id": f"33333333-3333-4333-8333-33333333333{position}",
                "tenant_id": DEMO_TENANT_ID,
                "user_id": user_id,
                "role": role,
                "status": "active",
                "joined_at": now,
            }
            for position, (user_id, _, _, role) in enumerate(DEMO_USERS, start=1)
        ],
    )

    op.add_column(
        "registration_applications",
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE registration_applications SET tenant_id = :tenant_id "
            "WHERE tenant_id IS NULL"
        ).bindparams(
            sa.bindparam(
                "tenant_id",
                value=uuid.UUID(DEMO_TENANT_ID),
                type_=sa.Uuid(),
            )
        )
    )
    op.alter_column("registration_applications", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_registration_applications_tenant_id_tenants",
        "registration_applications",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_registration_applications_tenant_id"),
        "registration_applications",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_registration_applications_tenant_id"),
        table_name="registration_applications",
    )
    op.drop_constraint(
        "fk_registration_applications_tenant_id_tenants",
        "registration_applications",
        type_="foreignkey",
    )
    op.drop_column("registration_applications", "tenant_id")
    op.drop_table("audit_events")
    op.drop_table("tenant_memberships")
    op.drop_table("users")
    op.drop_table("tenants")
