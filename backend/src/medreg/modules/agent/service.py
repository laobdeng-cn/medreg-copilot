import hashlib
import json
import uuid
from datetime import UTC, datetime

from medreg.modules.agent.model import DraftModel
from medreg.modules.agent.repository import AgentRepository
from medreg.modules.agent.schemas import (
    AgentApprovalCreate,
    AgentDraftRun,
    AgentDraftRunCreate,
    AgentDraftRunList,
    AgentRunStatus,
    AgentRuntimeStatus,
    ApprovalStatus,
)
from medreg.modules.agent.workflow import (
    PROMPT_VERSION,
    WORKFLOW_VERSION,
    AgentDraftWorkflow,
)
from medreg.modules.applications.service import ApplicationService
from medreg.modules.retrieval.service import RetrievalService


class AgentRunNotFoundError(LookupError):
    pass


class AgentApprovalStateError(ValueError):
    pass


class AgentService:
    def __init__(
        self,
        repository: AgentRepository,
        application_service: ApplicationService,
        retrieval_service: RetrievalService,
        model: DraftModel,
    ) -> None:
        self.repository = repository
        self.model = model
        self.workflow = AgentDraftWorkflow(
            application_service=application_service,
            retrieval_service=retrieval_service,
            model=model,
        )

    def runtime_status(self) -> AgentRuntimeStatus:
        return AgentRuntimeStatus(
            workflow_version=WORKFLOW_VERSION,
            provider=self.model.provider,
            model=self.model.model,
            mode=("live" if self.model.configured else "deterministic"),
            configured=self.model.configured,
        )

    async def create_run(
        self,
        application_id: uuid.UUID,
        payload: AgentDraftRunCreate,
    ) -> AgentDraftRun:
        started_at = datetime.now(UTC)
        state = await self.workflow.run(
            application_id=application_id,
            target_section=payload.target_section,
            language_mode=payload.language_mode,
            requested_by=payload.requested_by,
        )
        completed_at = datetime.now(UTC)
        snapshot_json = json.dumps(
            state["input_snapshot"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        run = AgentDraftRun(
            id=uuid.uuid4(),
            application_id=application_id,
            workflow_version=WORKFLOW_VERSION,
            status=AgentRunStatus.COMPLETED,
            target_section=payload.target_section,
            language_mode=payload.language_mode,
            requested_by=payload.requested_by,
            input_snapshot_hash=hashlib.sha256(snapshot_json.encode()).hexdigest(),
            input_snapshot=state["input_snapshot"],
            prompt_version=PROMPT_VERSION,
            prompt_snapshot=state["prompt_snapshot"],
            model_provider=state["model_provider"],
            model_name=state["model_name"],
            model_mode=state["model_mode"],
            model_error=state.get("model_error"),
            draft_title=state["draft_title"],
            draft_content=state["draft_content"],
            reviewer_summary=state["reviewer_summary"],
            context_report=state["context_report"],
            structured_output=state["structured_output"],
            bilingual_report=state["bilingual_report"],
            node_traces=state["traces"],
            citations=state["citations"],
            approval_status=ApprovalStatus.PENDING,
            reviewed_by=None,
            review_note=None,
            reviewed_at=None,
            started_at=started_at,
            completed_at=completed_at,
            created_at=started_at,
            updated_at=completed_at,
        )
        return await self.repository.add(run)

    async def list_runs(
        self, application_id: uuid.UUID | None = None
    ) -> AgentDraftRunList:
        items = await self.repository.list(application_id)
        return AgentDraftRunList(items=items, total=len(items))

    async def get_run(self, run_id: uuid.UUID) -> AgentDraftRun:
        run = await self.repository.get(run_id)
        if run is None:
            raise AgentRunNotFoundError(str(run_id))
        return run

    async def review_run(
        self,
        run_id: uuid.UUID,
        payload: AgentApprovalCreate,
    ) -> AgentDraftRun:
        run = await self.get_run(run_id)
        if run.approval_status != ApprovalStatus.PENDING:
            raise AgentApprovalStateError(
                "This draft already has a final human review decision"
            )
        reviewed_at = datetime.now(UTC)
        updated = await self.repository.update_approval(
            run_id=run_id,
            status=ApprovalStatus(payload.decision.value),
            reviewed_by=payload.reviewed_by,
            review_note=payload.note.strip(),
            reviewed_at=reviewed_at,
        )
        if updated is None:
            raise AgentRunNotFoundError(str(run_id))
        return updated
