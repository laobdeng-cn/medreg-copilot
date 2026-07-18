from __future__ import annotations

import uuid
from datetime import UTC, datetime

from medreg.modules.evaluation.dataset import (
    DATASET_VERSION,
    VersionedEvaluationDataset,
)
from medreg.modules.evaluation.evaluator import MedRegEvaluator
from medreg.modules.evaluation.repository import EvaluationRepository
from medreg.modules.evaluation.schemas import (
    EvaluationCaseList,
    EvaluationDatasetSummary,
    EvaluationRun,
    EvaluationRunCreate,
    EvaluationRunList,
    EvaluationRunStatus,
    EvaluationTaskType,
)


class EvaluationService:
    def __init__(
        self,
        repository: EvaluationRepository,
        dataset: VersionedEvaluationDataset | None = None,
        evaluator: MedRegEvaluator | None = None,
    ) -> None:
        self.repository = repository
        self.dataset = dataset or VersionedEvaluationDataset()
        self.evaluator = evaluator or MedRegEvaluator()

    def dataset_summary(self) -> EvaluationDatasetSummary:
        return self.dataset.summary()

    def list_cases(
        self,
        task_type: EvaluationTaskType | None,
        limit: int,
    ) -> EvaluationCaseList:
        all_matching = [
            item
            for item in self.dataset.cases
            if task_type is None or item.task_type == task_type
        ]
        return EvaluationCaseList(items=all_matching[:limit], total=len(all_matching))

    async def create_run(self, payload: EvaluationRunCreate) -> EvaluationRun:
        started_at = datetime.now(UTC)
        summary = self.dataset.summary()
        result = self.evaluator.evaluate(
            self.dataset.cases,
            summary.production_validation_status,
        )
        completed_at = datetime.now(UTC)
        run = EvaluationRun(
            id=uuid.uuid4(),
            dataset_version=DATASET_VERSION,
            dataset_hash=self.dataset.dataset_hash,
            status=EvaluationRunStatus.COMPLETED,
            requested_by=payload.requested_by,
            baseline_name=self.evaluator.BASELINE_NAME,
            candidate_name=self.evaluator.CANDIDATE_NAME,
            case_count=len(self.dataset.cases),
            metrics=result.metrics,
            task_summaries=result.task_summaries,
            quality_gate=result.quality_gate,
            started_at=started_at,
            completed_at=completed_at,
            created_at=started_at,
        )
        return await self.repository.add(run)

    async def list_runs(self) -> EvaluationRunList:
        items = await self.repository.list()
        return EvaluationRunList(items=items, total=len(items))
