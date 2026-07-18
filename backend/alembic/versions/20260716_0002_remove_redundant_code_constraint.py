"""Remove redundant registration code constraint.

Revision ID: 20260716_0002
Revises: 20260716_0001
Create Date: 2026-07-16 09:30:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260716_0002"
down_revision: str | None = "20260716_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "registration_applications_code_key",
        "registration_applications",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "registration_applications_code_key",
        "registration_applications",
        ["code"],
    )
