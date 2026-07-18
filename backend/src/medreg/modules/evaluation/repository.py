from __future__ import annotations

import asyncio
import uuid
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medreg.modules.evaluation.models import EvaluationRunModel
from medreg.modules.evaluation.schemas import (
    EvaluationMetric,
    EvaluationQualityGate,
    EvaluationRun,
    EvaluationTaskSummary,
)


class EvaluationRepository(Protocol):
    async def add(self, run: EvaluationRun) -> EvaluationRun: ...

    async def list(self) -> list[EvaluationRun]: ...


class InMemoryEvaluationRepository:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, EvaluationRun] = {}
        self._lock = asyncio.Lock()

    async def add(self, run: EvaluationRun) -> EvaluationRun:
        async with self._lock:
            self._items[run.id] = run.model_copy(deep=True)
        return run.model_copy(deep=True)

    async def list(self) -> list[EvaluationRun]:
        async with self._lock:
            items = [item.model_copy(deep=True) for item in self._items.values()]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    async def clear(self) -> None:
        async with self._lock:
            self._items.clear()


class SQLAlchemyEvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, run: EvaluationRun) -> EvaluationRun:
        model = EvaluationRunModel(
            id=run.id,
            dataset_version=run.dataset_version,
            dataset_hash=run.dataset_hash,
            status=run.status.value,
            requested_by=run.requested_by,
            baseline_name=run.baseline_name,
            candidate_name=run.candidate_name,
            case_count=run.case_count,
            metrics=[item.model_dump(mode="json") for item in run.metrics],
            task_summaries=[
                item.model_dump(mode="json") for item in run.task_summaries
            ],
            quality_gate=run.quality_gate.model_dump(mode="json"),
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
        )
        self.session.add(model)
        await self.session.commit()
        return self._to_read(model)

    async def list(self) -> list[EvaluationRun]:
        models = await self.session.scalars(
            select(EvaluationRunModel).order_by(EvaluationRunModel.created_at.desc())
        )
        return [self._to_read(model) for model in models.all()]

    @staticmethod
    def _to_read(model: EvaluationRunModel) -> EvaluationRun:
        return EvaluationRun(
            id=model.id,
            dataset_version=model.dataset_version,
            dataset_hash=model.dataset_hash,
            status=model.status,
            requested_by=model.requested_by,
            baseline_name=model.baseline_name,
            candidate_name=model.candidate_name,
            case_count=model.case_count,
            metrics=[EvaluationMetric.model_validate(item) for item in model.metrics],
            task_summaries=[
                EvaluationTaskSummary.model_validate(item)
                for item in model.task_summaries
            ],
            quality_gate=EvaluationQualityGate.model_validate(model.quality_gate),
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
        )
