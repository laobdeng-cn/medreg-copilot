from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from medreg.modules.security.models import (
    AuditEventModel,
    TenantMembershipModel,
    TenantModel,
    UserModel,
)
from medreg.modules.security.schemas import (
    DEMO_EDITOR_ID,
    DEMO_OWNER_ID,
    DEMO_REVIEWER_ID,
    DEMO_TENANT_ID,
    DEMO_VIEWER_ID,
    ROLE_PERMISSIONS,
    ActorContext,
    AuditEventCreate,
    AuditEventRead,
    TenantMemberRead,
    TenantRole,
)


class SecurityRepository(Protocol):
    async def resolve_actor(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID
    ) -> ActorContext | None: ...

    async def list_members(self, tenant_id: uuid.UUID) -> list[TenantMemberRead]: ...

    async def get_tenant(self, tenant_id: uuid.UUID) -> tuple[str, str] | None: ...

    async def add_audit_event(self, event: AuditEventCreate) -> AuditEventRead: ...

    async def list_audit_events(
        self,
        tenant_id: uuid.UUID,
        limit: int,
        action: str | None = None,
        outcome: str | None = None,
    ) -> list[AuditEventRead]: ...

    async def count_audit_events(self, tenant_id: uuid.UUID) -> int: ...


class InMemorySecurityRepository:
    def __init__(self) -> None:
        self._tenant = ("深圳示例医疗科技有限公司", "shenzhen-demo-medtech")
        joined_at = datetime.now(UTC)
        members = (
            (DEMO_OWNER_ID, "刘凯旗", "liukaiqi@demo.medreg.cn", TenantRole.OWNER),
            (DEMO_REVIEWER_ID, "张法规", "reviewer@demo.medreg.cn", TenantRole.REVIEWER),
            (DEMO_EDITOR_ID, "陈工程师", "engineer@demo.medreg.cn", TenantRole.EDITOR),
            (DEMO_VIEWER_ID, "王观察员", "viewer@demo.medreg.cn", TenantRole.VIEWER),
        )
        self._members = [
            TenantMemberRead(
                user_id=user_id,
                display_name=name,
                email=email,
                role=role,
                status="active",
                joined_at=joined_at,
            )
            for user_id, name, email, role in members
        ]
        self._events: list[AuditEventRead] = []
        self._lock = asyncio.Lock()

    async def resolve_actor(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID
    ) -> ActorContext | None:
        if tenant_id != DEMO_TENANT_ID:
            return None
        member = next((item for item in self._members if item.user_id == user_id), None)
        if member is None:
            return None
        return ActorContext(
            tenant_id=tenant_id,
            tenant_name=self._tenant[0],
            user_id=member.user_id,
            user_name=member.display_name,
            email=member.email,
            role=member.role,
            permissions=ROLE_PERMISSIONS[member.role],
        )

    async def list_members(self, tenant_id: uuid.UUID) -> list[TenantMemberRead]:
        if tenant_id != DEMO_TENANT_ID:
            return []
        return [item.model_copy(deep=True) for item in self._members]

    async def get_tenant(self, tenant_id: uuid.UUID) -> tuple[str, str] | None:
        return self._tenant if tenant_id == DEMO_TENANT_ID else None

    async def add_audit_event(self, event: AuditEventCreate) -> AuditEventRead:
        item = AuditEventRead(id=uuid.uuid4(), **event.model_dump())
        async with self._lock:
            self._events.append(item)
        return item.model_copy(deep=True)

    async def list_audit_events(
        self,
        tenant_id: uuid.UUID,
        limit: int,
        action: str | None = None,
        outcome: str | None = None,
    ) -> list[AuditEventRead]:
        async with self._lock:
            items = [
                item.model_copy(deep=True)
                for item in self._events
                if item.tenant_id == tenant_id
                and (action is None or item.action == action)
                and (outcome is None or item.outcome == outcome)
            ]
        return sorted(items, key=lambda item: item.created_at, reverse=True)[:limit]

    async def count_audit_events(self, tenant_id: uuid.UUID) -> int:
        async with self._lock:
            return sum(item.tenant_id == tenant_id for item in self._events)

    async def clear(self) -> None:
        async with self._lock:
            self._events.clear()


class SQLAlchemySecurityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve_actor(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID
    ) -> ActorContext | None:
        row = (
            await self.session.execute(
                select(TenantMembershipModel, UserModel, TenantModel)
                .join(UserModel, UserModel.id == TenantMembershipModel.user_id)
                .join(TenantModel, TenantModel.id == TenantMembershipModel.tenant_id)
                .where(
                    TenantMembershipModel.tenant_id == tenant_id,
                    TenantMembershipModel.user_id == user_id,
                    TenantMembershipModel.status == "active",
                    UserModel.status == "active",
                    TenantModel.status == "active",
                )
            )
        ).first()
        if row is None:
            return None
        membership, user, tenant = row
        role = TenantRole(membership.role)
        return ActorContext(
            tenant_id=tenant.id,
            tenant_name=tenant.name,
            user_id=user.id,
            user_name=user.display_name,
            email=user.email,
            role=role,
            permissions=ROLE_PERMISSIONS[role],
        )

    async def list_members(self, tenant_id: uuid.UUID) -> list[TenantMemberRead]:
        rows = await self.session.execute(
            select(TenantMembershipModel, UserModel)
            .join(UserModel, UserModel.id == TenantMembershipModel.user_id)
            .where(TenantMembershipModel.tenant_id == tenant_id)
            .order_by(TenantMembershipModel.joined_at.asc())
        )
        return [
            TenantMemberRead(
                user_id=user.id,
                display_name=user.display_name,
                email=user.email,
                role=membership.role,
                status=membership.status,
                joined_at=membership.joined_at,
            )
            for membership, user in rows.all()
        ]

    async def get_tenant(self, tenant_id: uuid.UUID) -> tuple[str, str] | None:
        tenant = await self.session.get(TenantModel, tenant_id)
        return (tenant.name, tenant.slug) if tenant else None

    async def add_audit_event(self, event: AuditEventCreate) -> AuditEventRead:
        model = AuditEventModel(id=uuid.uuid4(), **event.model_dump(mode="python"))
        self.session.add(model)
        await self.session.commit()
        return self._to_audit_read(model)

    async def list_audit_events(
        self,
        tenant_id: uuid.UUID,
        limit: int,
        action: str | None = None,
        outcome: str | None = None,
    ) -> list[AuditEventRead]:
        statement = select(AuditEventModel).where(
            AuditEventModel.tenant_id == tenant_id
        )
        if action is not None:
            statement = statement.where(AuditEventModel.action == action)
        if outcome is not None:
            statement = statement.where(AuditEventModel.outcome == outcome)
        models = await self.session.scalars(
            statement.order_by(AuditEventModel.created_at.desc()).limit(limit)
        )
        return [self._to_audit_read(model) for model in models.all()]

    async def count_audit_events(self, tenant_id: uuid.UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count(AuditEventModel.id)).where(
                    AuditEventModel.tenant_id == tenant_id
                )
            )
            or 0
        )

    @staticmethod
    def _to_audit_read(model: AuditEventModel) -> AuditEventRead:
        return AuditEventRead(
            id=model.id,
            tenant_id=model.tenant_id,
            actor_user_id=model.actor_user_id,
            actor_name=model.actor_name,
            actor_role=model.actor_role,
            action=model.action,
            resource_type=model.resource_type,
            resource_id=model.resource_id,
            request_method=model.request_method,
            request_path=model.request_path,
            outcome=model.outcome,
            status_code=model.status_code,
            request_id=model.request_id,
            detail=model.detail,
            created_at=model.created_at,
        )
