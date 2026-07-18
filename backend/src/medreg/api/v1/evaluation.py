from fastapi import APIRouter, Query, status

from medreg.api.dependencies import (
    EvaluationServiceDependency,
    SecurityServiceDependency,
    WriterActor,
)
from medreg.modules.evaluation.schemas import (
    EvaluationCaseList,
    EvaluationDatasetSummary,
    EvaluationRun,
    EvaluationRunCreate,
    EvaluationRunList,
    EvaluationTaskType,
)

router = APIRouter(tags=["evaluation"])


@router.get("/evaluation/dataset", response_model=EvaluationDatasetSummary)
async def get_evaluation_dataset(
    service: EvaluationServiceDependency,
) -> EvaluationDatasetSummary:
    return service.dataset_summary()


@router.get("/evaluation/cases", response_model=EvaluationCaseList)
async def list_evaluation_cases(
    service: EvaluationServiceDependency,
    task_type: EvaluationTaskType | None = None,
    limit: int = Query(default=20, ge=1, le=60),
) -> EvaluationCaseList:
    return service.list_cases(task_type, limit)


@router.post(
    "/evaluation/runs",
    response_model=EvaluationRun,
    status_code=status.HTTP_201_CREATED,
)
async def create_evaluation_run(
    payload: EvaluationRunCreate,
    service: EvaluationServiceDependency,
    actor: WriterActor,
    security: SecurityServiceDependency,
) -> EvaluationRun:
    run = await service.create_run(payload)
    await security.record(
        actor,
        action="evaluation.completed",
        resource_type="evaluation_run",
        resource_id=run.id,
        request_method="POST",
        request_path="/evaluation/runs",
        status_code=status.HTTP_201_CREATED,
        detail={
            "dataset_version": run.dataset_version,
            "case_count": run.case_count,
            "quality_gate_status": run.quality_gate.status.value,
        },
    )
    return run


@router.get("/evaluation/runs", response_model=EvaluationRunList)
async def list_evaluation_runs(
    service: EvaluationServiceDependency,
) -> EvaluationRunList:
    return await service.list_runs()
