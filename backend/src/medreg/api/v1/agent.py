import uuid

from fastapi import APIRouter, HTTPException, status

from medreg.api.dependencies import (
    AgentServiceDependency,
    ReviewerActor,
    SecurityServiceDependency,
    WriterActor,
)
from medreg.modules.agent.schemas import (
    AgentApprovalCreate,
    AgentDraftRun,
    AgentDraftRunCreate,
    AgentDraftRunList,
    AgentRuntimeStatus,
)
from medreg.modules.agent.service import (
    AgentApprovalStateError,
    AgentRunNotFoundError,
)
from medreg.modules.agent.workflow import AgentPrecheckRequiredError
from medreg.modules.applications.service import ApplicationNotFoundError

router = APIRouter(tags=["agent"])


@router.get("/agent/runtime", response_model=AgentRuntimeStatus)
async def get_agent_runtime(
    service: AgentServiceDependency,
) -> AgentRuntimeStatus:
    return service.runtime_status()


@router.post(
    "/registration-applications/{application_id}/agent-runs",
    response_model=AgentDraftRun,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_run(
    application_id: uuid.UUID,
    payload: AgentDraftRunCreate,
    service: AgentServiceDependency,
    actor: WriterActor,
    security: SecurityServiceDependency,
) -> AgentDraftRun:
    try:
        run = await service.create_run(application_id, payload)
        await security.record(
            actor,
            action="agent_run.created",
            resource_type="agent_draft_run",
            resource_id=run.id,
            request_method="POST",
            request_path=f"/registration-applications/{application_id}/agent-runs",
            status_code=status.HTTP_201_CREATED,
            detail={
                "application_id": str(application_id),
                "target_section": run.target_section.value,
                "model_mode": run.model_mode.value,
            },
        )
        return run
    except ApplicationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registration application not found",
        ) from exc
    except AgentPrecheckRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get("/agent-runs", response_model=AgentDraftRunList)
async def list_agent_runs(
    service: AgentServiceDependency,
    application_id: uuid.UUID | None = None,
) -> AgentDraftRunList:
    return await service.list_runs(application_id)


@router.get("/agent-runs/{run_id}", response_model=AgentDraftRun)
async def get_agent_run(
    run_id: uuid.UUID,
    service: AgentServiceDependency,
) -> AgentDraftRun:
    try:
        return await service.get_run(run_id)
    except AgentRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent draft run not found",
        ) from exc


@router.post("/agent-runs/{run_id}/review", response_model=AgentDraftRun)
async def review_agent_run(
    run_id: uuid.UUID,
    payload: AgentApprovalCreate,
    service: AgentServiceDependency,
    actor: ReviewerActor,
    security: SecurityServiceDependency,
) -> AgentDraftRun:
    try:
        run = await service.review_run(run_id, payload)
        await security.record(
            actor,
            action="agent_run.reviewed",
            resource_type="agent_draft_run",
            resource_id=run.id,
            request_method="POST",
            request_path=f"/agent-runs/{run_id}/review",
            status_code=status.HTTP_200_OK,
            detail={"decision": run.approval_status.value},
        )
        return run
    except AgentRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent draft run not found",
        ) from exc
    except AgentApprovalStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
