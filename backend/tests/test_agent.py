import uuid
from datetime import date

import httpx
import pytest

from medreg.modules.agent.bilingual import BilingualConsistencyChecker
from medreg.modules.agent.context import EvidenceContextCompressor
from medreg.modules.agent.model import DeepSeekDraftModel, DeterministicDraftModel
from medreg.modules.agent.repository import InMemoryAgentRepository
from medreg.modules.agent.schemas import (
    AgentApprovalCreate,
    AgentDraftRunCreate,
    BilingualTerm,
    DraftLanguageMode,
    DraftSection,
    ModelDraft,
    StructuredDraftClaim,
    StructuredDraftSection,
)
from medreg.modules.agent.service import AgentApprovalStateError, AgentService
from medreg.modules.agent.workflow import AgentPrecheckRequiredError
from medreg.modules.applications.consistency import EvidenceText
from medreg.modules.applications.repository import InMemoryApplicationRepository
from medreg.modules.applications.schemas import (
    DossierCategory,
    PrecheckCreate,
    RegistrationApplicationCreate,
)
from medreg.modules.applications.service import ApplicationService
from medreg.modules.documents.storage import InMemoryObjectStorage
from medreg.modules.retrieval.schemas import (
    EvidenceHit,
    HybridSearchResponse,
)


class FakeRetrievalService:
    async def search(self, payload) -> HybridSearchResponse:
        return HybridSearchResponse(
            query=payload.query,
            strategy="dense + BM25 + RRF + lexical rerank",
            dense_model="test-dense",
            sparse_model="test-sparse",
            elapsed_ms=7,
            total=1,
            items=[
                EvidenceHit(
                    chunk_id=uuid.uuid4(),
                    document_id=uuid.uuid4(),
                    regulation_version_id=uuid.uuid4(),
                    source_id=uuid.uuid4(),
                    source_title="医疗器械注册与备案管理办法",
                    document_number="国家市场监督管理总局令第47号",
                    version_label="2021版",
                    citation_label="第三章 / 第五十二条",
                    content="申请医疗器械注册，应当按照要求提交产品风险分析资料。",
                    char_start=120,
                    char_end=151,
                    retrieval_score=0.88,
                    rerank_score=0.92,
                    matched_terms=["风险分析", "注册"],
                )
            ],
        )


async def make_services() -> tuple[ApplicationService, AgentService, uuid.UUID]:
    application_repository = InMemoryApplicationRepository()
    application_service = ApplicationService(
        repository=application_repository,
        storage=InMemoryObjectStorage(),
    )
    application = await application_service.create(
        RegistrationApplicationCreate(
            name="便携式心电记录仪首次注册",
            product_name="便携式心电记录仪",
            applicant_name="深圳示例医疗科技有限公司",
            device_class="II",
            regulation_effective_on=date(2026, 7, 17),
            owner_name="刘凯旗",
        )
    )
    agent_service = AgentService(
        repository=InMemoryAgentRepository(),
        application_service=application_service,
        retrieval_service=FakeRetrievalService(),  # type: ignore[arg-type]
        model=DeterministicDraftModel(),
    )
    return application_service, agent_service, application.id


async def test_agent_graph_requires_a_precheck_snapshot() -> None:
    _, agent_service, application_id = await make_services()

    with pytest.raises(AgentPrecheckRequiredError):
        await agent_service.create_run(
            application_id,
            AgentDraftRunCreate(
                target_section=DraftSection.RISK_MANAGEMENT_SUMMARY,
                requested_by="刘凯旗",
            ),
        )


async def test_agent_graph_persists_six_nodes_citations_and_controlled_draft() -> None:
    application_service, agent_service, application_id = await make_services()
    await application_service.run_precheck(
        application_id,
        PrecheckCreate(initiated_by="刘凯旗"),
    )

    run = await agent_service.create_run(
        application_id,
        AgentDraftRunCreate(
            target_section=DraftSection.RISK_MANAGEMENT_SUMMARY,
            language_mode=DraftLanguageMode.BILINGUAL,
            requested_by="刘凯旗",
        ),
    )

    assert [trace.node_key for trace in run.node_traces] == [
        "intake",
        "regulation",
        "retrieval",
        "consistency",
        "drafting",
        "reviewer",
    ]
    assert run.model_mode == "deterministic"
    assert run.approval_status == "pending"
    assert len(run.input_snapshot_hash) == 64
    assert len(run.citations) == 1
    assert "【证据1】" in run.draft_content
    assert "不得作为受控申报文件" in run.draft_content
    assert "sections、claims、bilingual_terms" in run.prompt_snapshot
    assert run.context_report is not None
    assert run.structured_output is not None
    assert len(run.structured_output.sections) >= 4
    assert all(claim.evidence_markers for claim in run.structured_output.claims)
    assert run.bilingual_report is not None
    assert run.bilingual_report.status == "pass"
    assert "residual risk" in run.draft_content
    assert "须由法规负责人" in run.reviewer_summary

    history = await agent_service.list_runs(application_id)
    assert history.total == 1
    assert history.items[0].id == run.id


async def test_human_review_is_terminal_and_audited() -> None:
    application_service, agent_service, application_id = await make_services()
    await application_service.run_precheck(
        application_id,
        PrecheckCreate(initiated_by="刘凯旗"),
    )
    run = await agent_service.create_run(
        application_id,
        AgentDraftRunCreate(
            target_section=DraftSection.PRODUCT_OVERVIEW,
            requested_by="刘凯旗",
        ),
    )

    approved = await agent_service.review_run(
        run.id,
        AgentApprovalCreate(
            decision="approved",
            reviewed_by="法规负责人",
            note="已逐条核对引用与项目事实，可进入受控文档编制。",
        ),
    )

    assert approved.approval_status == "approved"
    assert approved.reviewed_by == "法规负责人"
    assert approved.reviewed_at is not None

    with pytest.raises(AgentApprovalStateError):
        await agent_service.review_run(
            run.id,
            AgentApprovalCreate(
                decision="rejected",
                reviewed_by="第二审核人",
                note="重复审批应被拒绝。",
            ),
        )


async def test_deepseek_failure_falls_back_without_exposing_the_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_post(*args, **kwargs):
        raise httpx.ConnectError("upstream unavailable")

    monkeypatch.setattr(httpx.AsyncClient, "post", fail_post)
    model = DeepSeekDraftModel(
        api_key="secret-test-key",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        timeout_seconds=1,
    )
    fallback = ModelDraft(
        title="受控草稿",
        summary="确定性受控草稿摘要",
        sections=[
            StructuredDraftSection(
                heading="编制范围",
                content="确定性内容",
                evidence_markers=["【项目快照】"],
            )
        ],
    )

    result = await model.generate("system", "user", fallback)

    assert result.mode == "fallback"
    assert result.draft == fallback
    assert "ConnectError" in (result.error or "")
    assert "secret-test-key" not in (result.error or "")


@pytest.mark.parametrize(
    ("raw_confidence", "expected"),
    [("high", 0.9), ("medium", 0.6), ("low", 0.3), ("高", 0.9), ("85%", 0.85)],
)
def test_model_claim_normalizes_common_confidence_labels(
    raw_confidence: str,
    expected: float,
) -> None:
    claim = StructuredDraftClaim(
        statement="风险控制措施已有项目证据支持。",
        evidence_markers=["【项目证据1】"],
        confidence=raw_confidence,
    )

    assert claim.confidence == expected


def test_context_compressor_preserves_traceable_relevant_segments() -> None:
    compressor = EvidenceContextCompressor(
        max_chars=1200,
        segment_chars=500,
        overlap_chars=80,
    )
    documents = [
        EvidenceText(
            evidence_id=uuid.uuid4(),
            category_key=DossierCategory.RISK_ANALYSIS,
            file_name="风险管理报告.txt",
            text=("背景信息。" * 300) + "风险控制措施已实施，剩余风险待评估。",
        ),
        EvidenceText(
            evidence_id=uuid.uuid4(),
            category_key=DossierCategory.IFU_AND_LABEL,
            file_name="说明书.txt",
            text=("一般说明。" * 300) + "警示语与剩余风险保持一致。",
        ),
    ]

    report = compressor.compress(
        documents,
        DraftSection.RISK_MANAGEMENT_SUMMARY,
    )

    assert report.original_chars > report.selected_chars
    assert report.selected_chars <= report.max_chars
    assert report.compression_ratio < 0.5
    assert report.source_count == 2
    assert report.segments
    assert all(len(segment.content_hash) == 64 for segment in report.segments)
    assert any(segment.matched_terms for segment in report.segments)


def test_bilingual_checker_reports_pass_missing_and_mismatch() -> None:
    checker = BilingualConsistencyChecker()
    expected = checker.expected_terms(
        "便携式心电记录仪",
        DraftSection.RISK_MANAGEMENT_SUMMARY,
    )
    passed = checker.check(DraftLanguageMode.BILINGUAL, expected, expected)
    altered = [
        BilingualTerm(zh=item.zh, en=("remaining hazard" if item.zh == "剩余风险" else item.en))
        for item in expected
        if item.zh != "风险控制"
    ]
    failed = checker.check(DraftLanguageMode.BILINGUAL, expected, altered)

    assert passed.status == "pass"
    assert passed.pass_count == len(expected)
    assert failed.status == "mismatch"
    assert failed.missing_count == 1
    assert failed.mismatch_count == 1
