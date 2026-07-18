import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

DEMO_TENANT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
DEMO_OWNER_ID = uuid.UUID("22222222-2222-4222-8222-222222222221")
DEMO_REVIEWER_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
DEMO_EDITOR_ID = uuid.UUID("22222222-2222-4222-8222-222222222223")
DEMO_VIEWER_ID = uuid.UUID("22222222-2222-4222-8222-222222222224")


class TenantRole(StrEnum):
    OWNER = "owner"
    REVIEWER = "reviewer"
    EDITOR = "editor"
    VIEWER = "viewer"


class Permission(StrEnum):
    READ = "read"
    WRITE = "write"
    REVIEW = "review"
    ADMIN = "admin"


ROLE_PERMISSIONS: dict[TenantRole, tuple[Permission, ...]] = {
    TenantRole.OWNER: (
        Permission.READ,
        Permission.WRITE,
        Permission.REVIEW,
        Permission.ADMIN,
    ),
    TenantRole.REVIEWER: (
        Permission.READ,
        Permission.WRITE,
        Permission.REVIEW,
    ),
    TenantRole.EDITOR: (Permission.READ, Permission.WRITE),
    TenantRole.VIEWER: (Permission.READ,),
}


class ActorContext(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    user_id: uuid.UUID
    user_name: str
    email: str
    role: TenantRole
    permissions: tuple[Permission, ...]


class TenantMemberRead(BaseModel):
    user_id: uuid.UUID
    display_name: str
    email: str
    role: TenantRole
    status: str
    joined_at: datetime


class SecurityWorkspace(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    current_actor: ActorContext
    members: list[TenantMemberRead]
    audit_event_count: int
    boundary_note: str


class AuditEventCreate(BaseModel):
    tenant_id: uuid.UUID
    actor_user_id: uuid.UUID
    actor_name: str
    actor_role: TenantRole
    action: str = Field(min_length=3, max_length=96)
    resource_type: str = Field(min_length=2, max_length=64)
    resource_id: str | None = Field(default=None, max_length=128)
    request_method: str = Field(min_length=3, max_length=12)
    request_path: str = Field(min_length=1, max_length=500)
    outcome: str = Field(default="success", max_length=24)
    status_code: int = Field(default=200, ge=100, le=599)
    request_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    detail: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class AuditEventRead(AuditEventCreate):
    id: uuid.UUID


class AuditEventList(BaseModel):
    items: list[AuditEventRead]
    total: int
