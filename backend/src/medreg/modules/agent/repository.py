from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medreg.modules.agent.models import AgentDraftRunModel
from medreg.modules.agent.schemas import (
    AgentCitation,
    AgentDraftRun,
    AgentNodeTrace,
    ApprovalStatus,
    BilingualConsistencyReport,
    ContextCompressionReport,
    ModelDraft,
)
from medreg.modules.applications.models import RegistrationApplicationModel
from medreg.modules.security.schemas import DEMO_TENANT_ID


class AgentRepository(Protocol):
    async def add(self, run: AgentDraftRun) -> AgentDraftRun: ...

    async def list(
        self, application_id: uuid.UUID | None = None
    ) -> list[AgentDraftRun]: ...

    async def get(self, run_id: uuid.UUID) -> AgentDraftRun | None: ...

    async def update_approval(
        self,
        run_id: uuid.UUID,
        status: ApprovalStatus,
        reviewed_by: str,
        review_note: str,
        reviewed_at: datetime,
    ) -> AgentDraftRun | None: ...


class InMemoryAgentRepository:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, AgentDraftRun] = {}
        self._lock = asyncio.Lock()

    async def add(self, run: AgentDraftRun) -> AgentDraftRun:
        async with self._lock:
            self._items[run.id] = run.model_copy(deep=True)
        return run.model_copy(deep=True)

    async def list(
        self, application_id: uuid.UUID | None = None
    ) -> list[AgentDraftRun]:
        async with self._lock:
            items = [
                item.model_copy(deep=True)
                for item in self._items.values()
                if application_id is None or item.application_id == application_id
            ]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    async def get(self, run_id: uuid.UUID) -> AgentDraftRun | None:
        async with self._lock:
            item = self._items.get(run_id)
        return item.model_copy(deep=True) if item else None

    async def update_approval(
        self,
        run_id: uuid.UUID,
        status: ApprovalStatus,
        reviewed_by: str,
        review_note: str,
        reviewed_at: datetime,
    ) -> AgentDraftRun | None:
        async with self._lock:
            item = self._items.get(run_id)
            if item is None:
                return None
            updated = item.model_copy(
                update={
                    "approval_status": status,
                    "reviewed_by": reviewed_by,
                    "review_note": review_note,
                    "reviewed_at": reviewed_at,
                    "updated_at": reviewed_at,
                },
                deep=True,
            )
            self._items[run_id] = updated
        return updated.model_copy(deep=True)

    async def clear(self) -> None:
        async with self._lock:
            self._items.clear()


class SQLAlchemyAgentRepository:
    def __init__(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID = DEMO_TENANT_ID,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def add(self, run: AgentDraftRun) -> AgentDraftRun:
        model = AgentDraftRunModel(
            id=run.id,
            application_id=run.application_id,
            workflow_version=run.workflow_version,
            status=run.status.value,
            target_section=run.target_section.value,
            language_mode=run.language_mode.value,
            requested_by=run.requested_by,
            input_snapshot_hash=run.input_snapshot_hash,
            input_snapshot=run.input_snapshot,
            prompt_version=run.prompt_version,
            prompt_snapshot=run.prompt_snapshot,
            model_provider=run.model_provider,
            model_name=run.model_name,
            model_mode=run.model_mode.value,
            model_error=run.model_error,
            draft_title=run.draft_title,
            draft_content=run.draft_content,
            reviewer_summary=run.reviewer_summary,
            context_report=(
                run.context_report.model_dump(mode="json")
                if run.context_report
                else None
            ),
            structured_output=(
                run.structured_output.model_dump(mode="json")
                if run.structured_output
                else None
            ),
            bilingual_report=(
                run.bilingual_report.model_dump(mode="json")
                if run.bilingual_report
                else None
            ),
            node_traces=[item.model_dump(mode="json") for item in run.node_traces],
            citations=[item.model_dump(mode="json") for item in run.citations],
            approval_status=run.approval_status.value,
            reviewed_by=run.reviewed_by,
            review_note=run.review_note,
            reviewed_at=run.reviewed_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )
        self.session.add(model)
        await self.session.commit()
        return self._to_read(model)

    async def list(
        self, application_id: uuid.UUID | None = None
    ) -> list[AgentDraftRun]:
        statement = (
            select(AgentDraftRunModel)
            .join(
                RegistrationApplicationModel,
                RegistrationApplicationModel.id == AgentDraftRunModel.application_id,
            )
            .where(RegistrationApplicationModel.tenant_id == self.tenant_id)
        )
        if application_id is not None:
            statement = statement.where(
                AgentDraftRunModel.application_id == application_id
            )
        models = await self.session.scalars(
            statement.order_by(AgentDraftRunModel.created_at.desc())
        )
        return [self._to_read(model) for model in models.all()]

    async def get(self, run_id: uuid.UUID) -> AgentDraftRun | None:
        model = await self.session.scalar(
            select(AgentDraftRunModel)
            .join(
                RegistrationApplicationModel,
                RegistrationApplicationModel.id == AgentDraftRunModel.application_id,
            )
            .where(
                AgentDraftRunModel.id == run_id,
                RegistrationApplicationModel.tenant_id == self.tenant_id,
            )
        )
        return self._to_read(model) if model else None

    async def update_approval(
        self,
        run_id: uuid.UUID,
        status: ApprovalStatus,
        reviewed_by: str,
        review_note: str,
        reviewed_at: datetime,
    ) -> AgentDraftRun | None:
        model = await self.session.scalar(
            select(AgentDraftRunModel)
            .join(
                RegistrationApplicationModel,
                RegistrationApplicationModel.id == AgentDraftRunModel.application_id,
            )
            .where(
                AgentDraftRunModel.id == run_id,
                RegistrationApplicationModel.tenant_id == self.tenant_id,
            )
        )
        if model is None:
            return None
        model.approval_status = status.value
        model.reviewed_by = reviewed_by
        model.review_note = review_note
        model.reviewed_at = reviewed_at
        model.updated_at = reviewed_at
        await self.session.commit()
        return self._to_read(model)

    @staticmethod
    def _to_read(model: AgentDraftRunModel) -> AgentDraftRun:
        return AgentDraftRun(
            id=model.id,
            application_id=model.application_id,
            workflow_version=model.workflow_version,
            status=model.status,
            target_section=model.target_section,
            language_mode=model.language_mode,
            requested_by=model.requested_by,
            input_snapshot_hash=model.input_snapshot_hash,
            input_snapshot=model.input_snapshot,
            prompt_version=model.prompt_version,
            prompt_snapshot=model.prompt_snapshot,
            model_provider=model.model_provider,
            model_name=model.model_name,
            model_mode=model.model_mode,
            model_error=model.model_error,
            draft_title=model.draft_title,
            draft_content=model.draft_content,
            reviewer_summary=model.reviewer_summary,
            context_report=(
                ContextCompressionReport.model_validate(model.context_report)
                if model.context_report
                else None
            ),
            structured_output=(
                ModelDraft.model_validate(model.structured_output)
                if model.structured_output
                else None
            ),
            bilingual_report=(
                BilingualConsistencyReport.model_validate(model.bilingual_report)
                if model.bilingual_report
                else None
            ),
            node_traces=[AgentNodeTrace.model_validate(item) for item in model.node_traces],
            citations=[AgentCitation.model_validate(item) for item in model.citations],
            approval_status=model.approval_status,
            reviewed_by=model.reviewed_by,
            review_note=model.review_note,
            reviewed_at=model.reviewed_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
