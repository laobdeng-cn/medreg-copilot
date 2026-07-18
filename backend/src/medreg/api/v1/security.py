from typing import Annotated

from fastapi import APIRouter, Query

from medreg.api.dependencies import (
    ReaderActor,
    ReviewerActor,
    SecurityServiceDependency,
)
from medreg.modules.security.schemas import AuditEventList, SecurityWorkspace

router = APIRouter(tags=["tenant security and audit"])


@router.get("/security/workspace", response_model=SecurityWorkspace)
async def get_security_workspace(
    actor: ReaderActor,
    service: SecurityServiceDependency,
) -> SecurityWorkspace:
    return await service.get_workspace(actor)


@router.get("/audit-events", response_model=AuditEventList)
async def list_audit_events(
    actor: ReviewerActor,
    service: SecurityServiceDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    action: Annotated[str | None, Query(max_length=96)] = None,
    outcome: Annotated[str | None, Query(max_length=24)] = None,
) -> AuditEventList:
    return await service.list_audit_events(
        actor,
        limit=limit,
        action=action,
        outcome=outcome,
    )
