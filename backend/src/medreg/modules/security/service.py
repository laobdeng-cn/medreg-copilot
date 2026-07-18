import uuid
from datetime import UTC, datetime

from medreg.modules.security.repository import SecurityRepository
from medreg.modules.security.schemas import (
    DEMO_OWNER_ID,
    DEMO_TENANT_ID,
    ActorContext,
    AuditEventCreate,
    AuditEventList,
    AuditEventRead,
    Permission,
    SecurityWorkspace,
)


class SecurityIdentityError(LookupError):
    pass


class PermissionDeniedError(PermissionError):
    pass


class SecurityService:
    def __init__(self, repository: SecurityRepository) -> None:
        self.repository = repository

    async def resolve_actor(
        self,
        tenant_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> ActorContext:
        actor = await self.repository.resolve_actor(
            tenant_id or DEMO_TENANT_ID,
            user_id or DEMO_OWNER_ID,
        )
        if actor is None:
            raise SecurityIdentityError("Active tenant membership not found")
        return actor

    @staticmethod
    def require(actor: ActorContext, permission: Permission) -> ActorContext:
        if permission not in actor.permissions:
            raise PermissionDeniedError(
                f"Role '{actor.role.value}' lacks '{permission.value}' permission"
            )
        return actor

    async def get_workspace(self, actor: ActorContext) -> SecurityWorkspace:
        tenant = await self.repository.get_tenant(actor.tenant_id)
        if tenant is None:
            raise SecurityIdentityError("Tenant not found")
        return SecurityWorkspace(
            tenant_id=actor.tenant_id,
            tenant_name=tenant[0],
            tenant_slug=tenant[1],
            current_actor=actor,
            members=await self.repository.list_members(actor.tenant_id),
            audit_event_count=await self.repository.count_audit_events(actor.tenant_id),
            boundary_note=(
                "申报资料与 Agent 运行按租户隔离；公开法规知识作为受控共享域。"
            ),
        )

    async def record(
        self,
        actor: ActorContext,
        *,
        action: str,
        resource_type: str,
        resource_id: str | uuid.UUID | None,
        request_method: str,
        request_path: str,
        status_code: int,
        detail: dict[str, object] | None = None,
    ) -> AuditEventRead:
        return await self.repository.add_audit_event(
            AuditEventCreate(
                tenant_id=actor.tenant_id,
                actor_user_id=actor.user_id,
                actor_name=actor.user_name,
                actor_role=actor.role,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                request_method=request_method,
                request_path=request_path,
                status_code=status_code,
                detail=detail or {},
                created_at=datetime.now(UTC),
            )
        )

    async def list_audit_events(
        self,
        actor: ActorContext,
        *,
        limit: int = 50,
        action: str | None = None,
        outcome: str | None = None,
    ) -> AuditEventList:
        self.require(actor, Permission.REVIEW)
        items = await self.repository.list_audit_events(
            actor.tenant_id,
            limit=limit,
            action=action,
            outcome=outcome,
        )
        return AuditEventList(
            items=items,
            total=await self.repository.count_audit_events(actor.tenant_id),
        )
