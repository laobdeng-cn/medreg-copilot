from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from medreg.modules.agent.bilingual import BilingualConsistencyChecker
from medreg.modules.agent.context import EvidenceContextCompressor
from medreg.modules.agent.model import DraftModel
from medreg.modules.agent.schemas import (
    AgentCitation,
    AgentNodeStatus,
    AgentNodeTrace,
    BilingualConsistencyReport,
    BilingualTerm,
    ContextCompressionReport,
    DraftLanguageMode,
    DraftSection,
    ModelDraft,
    ModelMode,
    StructuredDraftClaim,
    StructuredDraftSection,
)
from medreg.modules.applications.schemas import (
    DossierConsistencyReport,
    FindingRemediationStatus,
    PrecheckRun,
    RegistrationApplicationRead,
)
from medreg.modules.applications.service import ApplicationService
from medreg.modules.retrieval.schemas import HybridSearchRequest
from medreg.modules.retrieval.service import RetrievalService

WORKFLOW_VERSION = "medreg-drafting-graph-v2"
PROMPT_VERSION = "controlled-structured-dossier-draft-v2"

SECTION_LABELS = {
    DraftSection.PRODUCT_OVERVIEW: "产品概述",
    DraftSection.RISK_MANAGEMENT_SUMMARY: "风险管理摘要",
    DraftSection.TECHNICAL_REQUIREMENTS_SUMMARY: "产品技术要求摘要",
    DraftSection.IFU_LABEL_SUMMARY: "说明书与标签一致性摘要",
}

SECTION_QUERIES = {
    DraftSection.PRODUCT_OVERVIEW: "产品描述 申报资料 产品基本信息 预期用途",
    DraftSection.RISK_MANAGEMENT_SUMMARY: "风险分析 风险管理 风险控制 剩余风险 注册资料",
    DraftSection.TECHNICAL_REQUIREMENTS_SUMMARY: "产品技术要求 性能指标 检验方法 注册资料",
    DraftSection.IFU_LABEL_SUMMARY: "说明书 标签 预期用途 警示语 注册资料",
}


class AgentPrecheckRequiredError(ValueError):
    pass


class AgentGraphState(TypedDict, total=False):
    application_id: uuid.UUID
    target_section: DraftSection
    language_mode: DraftLanguageMode
    requested_by: str
    application: RegistrationApplicationRead
    precheck: PrecheckRun
    consistency: DossierConsistencyReport
    context_report: ContextCompressionReport
    search_query: str
    citations: list[AgentCitation]
    input_snapshot: dict
    prompt_snapshot: str
    draft_title: str
    draft_content: str
    structured_output: ModelDraft
    bilingual_report: BilingualConsistencyReport
    model_provider: str
    model_name: str
    model_mode: ModelMode
    model_error: str | None
    reviewer_summary: str
    traces: list[AgentNodeTrace]


class AgentDraftWorkflow:
    def __init__(
        self,
        application_service: ApplicationService,
        retrieval_service: RetrievalService,
        model: DraftModel,
    ) -> None:
        self.application_service = application_service
        self.retrieval_service = retrieval_service
        self.model = model
        self.context_compressor = EvidenceContextCompressor()
        self.bilingual_checker = BilingualConsistencyChecker()
        graph = StateGraph(AgentGraphState)
        graph.add_node("intake", self._intake)
        graph.add_node("regulation", self._regulation)
        graph.add_node("retrieval", self._retrieval)
        graph.add_node("consistency", self._consistency)
        graph.add_node("drafting", self._drafting)
        graph.add_node("reviewer", self._reviewer)
        graph.add_edge(START, "intake")
        graph.add_edge("intake", "regulation")
        graph.add_edge("regulation", "retrieval")
        graph.add_edge("retrieval", "consistency")
        graph.add_edge("consistency", "drafting")
        graph.add_edge("drafting", "reviewer")
        graph.add_edge("reviewer", END)
        self.graph = graph.compile()

    async def run(
        self,
        application_id: uuid.UUID,
        target_section: DraftSection,
        language_mode: DraftLanguageMode,
        requested_by: str,
    ) -> AgentGraphState:
        return await self.graph.ainvoke(
            {
                "application_id": application_id,
                "target_section": target_section,
                "language_mode": language_mode,
                "requested_by": requested_by,
                "traces": [],
                "citations": [],
            }
        )

    async def _intake(self, state: AgentGraphState) -> AgentGraphState:
        started_at, timer = self._start()
        application = await self.application_service.get(state["application_id"])
        prechecks = await self.application_service.list_prechecks(application.id)
        if not prechecks.items:
            raise AgentPrecheckRequiredError(
                "Run a dossier precheck before starting an agent draft"
            )
        precheck = prechecks.items[0]
        documents = await self.application_service.get_drafting_evidence_texts(
            application.id
        )
        context_report = self.context_compressor.compress(
            documents,
            state["target_section"],
        )
        input_snapshot = {
            "application": application.model_dump(mode="json"),
            "precheck": precheck.model_dump(mode="json"),
            "target_section": state["target_section"].value,
            "language_mode": state["language_mode"].value,
            "context_report": context_report.model_dump(mode="json"),
        }
        trace = self._finish(
            "intake",
            "Intake",
            started_at,
            timer,
            AgentNodeStatus.COMPLETED,
            (
                f"锁定项目 {application.code} 与预审 {str(precheck.id)[:8]}；"
                f"从 {context_report.source_count} 份已接受资料中将上下文由 "
                f"{context_report.original_chars} 字压缩至 "
                f"{context_report.selected_chars} 字。"
            ),
            [str(application.id), str(precheck.id), context_report.algorithm_version],
            len(context_report.segments),
        )
        return {
            "application": application,
            "precheck": precheck,
            "context_report": context_report,
            "input_snapshot": input_snapshot,
            "traces": [*state["traces"], trace],
        }

    async def _regulation(self, state: AgentGraphState) -> AgentGraphState:
        started_at, timer = self._start()
        application = state["application"]
        query = (
            f"{application.product_name} {application.device_class.value}类医疗器械 "
            f"{SECTION_QUERIES[state['target_section']]}"
        )
        trace = self._finish(
            "regulation",
            "Regulation",
            started_at,
            timer,
            AgentNodeStatus.COMPLETED,
            (
                f"依据 {application.regulation_effective_on.isoformat()} 法规基准日，"
                f"生成“{SECTION_LABELS[state['target_section']]}”检索意图。"
            ),
            [application.jurisdiction.value, application.regulation_effective_on.isoformat()],
            1,
        )
        return {"search_query": query, "traces": [*state["traces"], trace]}

    async def _retrieval(self, state: AgentGraphState) -> AgentGraphState:
        started_at, timer = self._start()
        status = AgentNodeStatus.COMPLETED
        citations: list[AgentCitation] = []
        try:
            result = await self.retrieval_service.search(
                HybridSearchRequest(query=state["search_query"], limit=5, rerank=True)
            )
            citations = [
                AgentCitation(
                    citation_index=index,
                    chunk_id=hit.chunk_id,
                    document_id=hit.document_id,
                    regulation_version_id=hit.regulation_version_id,
                    source_title=hit.source_title,
                    document_number=hit.document_number,
                    version_label=hit.version_label,
                    citation_label=hit.citation_label,
                    content=hit.content,
                    char_start=hit.char_start,
                    char_end=hit.char_end,
                    score=hit.rerank_score,
                )
                for index, hit in enumerate(result.items, start=1)
            ]
            summary = (
                f"使用 {result.strategy} 召回 {len(citations)} 条法规证据，"
                f"耗时 {result.elapsed_ms} ms。"
            )
            if not citations:
                status = AgentNodeStatus.DEGRADED
                summary = "检索链路可用，但当前查询未召回可引用法规证据。"
        except Exception as exc:
            status = AgentNodeStatus.DEGRADED
            summary = f"法规检索暂不可用，草稿将明确标记证据缺口：{exc}"[:500]
        trace = self._finish(
            "retrieval",
            "Retrieval",
            started_at,
            timer,
            status,
            summary,
            [state["search_query"]],
            len(citations),
        )
        return {"citations": citations, "traces": [*state["traces"], trace]}

    async def _consistency(self, state: AgentGraphState) -> AgentGraphState:
        started_at, timer = self._start()
        consistency = await self.application_service.get_consistency_report(
            state["application_id"]
        )
        mismatches = [item for item in consistency.checks if item.status.value == "mismatch"]
        state["input_snapshot"]["consistency"] = consistency.model_dump(mode="json")
        trace = self._finish(
            "consistency",
            "Consistency",
            started_at,
            timer,
            AgentNodeStatus.COMPLETED,
            (
                f"复用确定性一致性引擎完成 {consistency.check_count} 项核对，"
                f"发现 {len(mismatches)} 项冲突。"
            ),
            [consistency.parser_version],
            len(mismatches),
        )
        return {
            "consistency": consistency,
            "input_snapshot": state["input_snapshot"],
            "traces": [*state["traces"], trace],
        }

    async def _drafting(self, state: AgentGraphState) -> AgentGraphState:
        started_at, timer = self._start()
        expected_terms = self.bilingual_checker.expected_terms(
            state["application"].product_name,
            state["target_section"],
        )
        system_prompt, user_prompt = self._prompts(state, expected_terms)
        prompt_snapshot = f"SYSTEM\n{system_prompt}\n\nUSER\n{user_prompt}"
        generation = await self.model.generate(
            system_prompt,
            user_prompt,
            self._fallback_draft(state, expected_terms),
        )
        bilingual_report = self.bilingual_checker.check(
            state["language_mode"],
            expected_terms,
            generation.draft.bilingual_terms,
        )
        draft_content = self._render_draft(generation.draft)
        node_status = (
            AgentNodeStatus.DEGRADED
            if generation.mode == ModelMode.FALLBACK
            else AgentNodeStatus.COMPLETED
        )
        mode_label = {
            ModelMode.LIVE: "DeepSeek 实时生成",
            ModelMode.DETERMINISTIC: "确定性受控模板",
            ModelMode.FALLBACK: "模型失败后确定性降级",
        }[generation.mode]
        trace = self._finish(
            "drafting",
            "Drafting",
            started_at,
            timer,
            node_status,
            (
                f"使用{mode_label}形成 {len(generation.draft.sections)} 个结构化章节、"
                f"{len(generation.draft.claims)} 条可审计主张；草稿不会自动成为受控文件。"
            ),
            [PROMPT_VERSION, generation.model],
            len(generation.draft.sections) + len(generation.draft.claims),
        )
        return {
            "prompt_snapshot": prompt_snapshot,
            "draft_title": generation.draft.title,
            "draft_content": draft_content,
            "structured_output": generation.draft,
            "bilingual_report": bilingual_report,
            "model_provider": generation.provider,
            "model_name": generation.model,
            "model_mode": generation.mode,
            "model_error": generation.error,
            "traces": [*state["traces"], trace],
        }

    async def _reviewer(self, state: AgentGraphState) -> AgentGraphState:
        started_at, timer = self._start()
        precheck = state["precheck"]
        open_findings = [
            finding
            for finding in precheck.findings
            if finding.remediation_status
            in {FindingRemediationStatus.OPEN, FindingRemediationStatus.IN_PROGRESS}
        ]
        mismatch_count = state["consistency"].mismatch_count
        cited_markers = sum(
            f"【证据{item.citation_index}】" in state["draft_content"]
            for item in state["citations"]
        )
        unsupported_claims = sum(
            not claim.evidence_markers for claim in state["structured_output"].claims
        )
        bilingual_issues = (
            state["bilingual_report"].missing_count
            + state["bilingual_report"].mismatch_count
        )
        reviewer_summary = (
            f"自动复核完成：压缩上下文含 {len(state['context_report'].segments)} 个片段；"
            f"草稿含 {len(state['structured_output'].sections)} 个章节和 "
            f"{len(state['structured_output'].claims)} 条主张，其中 "
            f"{unsupported_claims} 条缺少证据标记；关联 {len(state['citations'])} 条"
            f"法规证据并使用 {cited_markers} 个引用标记；双语术语问题 "
            f"{bilingual_issues} 项。当前仍有 {len(open_findings)} 项未关闭整改和 "
            f"{mismatch_count} 项一致性冲突。仅可作为内部草稿，须由法规负责人"
            "逐条核对后批准或驳回。"
        )
        review_issue_count = (
            len(open_findings)
            + mismatch_count
            + unsupported_claims
            + bilingual_issues
        )
        trace = self._finish(
            "reviewer",
            "Reviewer",
            started_at,
            timer,
            (
                AgentNodeStatus.DEGRADED
                if unsupported_claims or bilingual_issues
                else AgentNodeStatus.COMPLETED
            ),
            reviewer_summary,
            [str(precheck.id), state["consistency"].parser_version],
            review_issue_count,
        )
        return {
            "reviewer_summary": reviewer_summary,
            "traces": [*state["traces"], trace],
        }

    @staticmethod
    def _prompts(
        state: AgentGraphState,
        expected_terms: list[BilingualTerm],
    ) -> tuple[str, str]:
        system_prompt = (
            "你是医疗器械注册资料编制助手。只能使用提供的项目快照、压缩后的项目"
            "证据和法规证据；不得补造标准、试验结果、临床数据或审批结论。每条事实"
            "主张必须带 evidence_markers；无法由输入支持的内容必须进入待确认事项。"
            "法规引用使用【证据N】，项目资料引用使用【项目证据N】，项目主数据使用"
            "【项目快照】。输出必须是严格 JSON 对象，不得输出 Markdown 代码围栏。"
            "JSON 必须且只能包含 title、summary、sections、claims、bilingual_terms；"
            "sections 元素包含 heading、content、evidence_markers，claims 元素包含 "
            "statement、evidence_markers、confidence，其中 confidence 必须是 0 到 1 "
            "之间的 JSON 数字（例如 0.9），不得使用 high、medium、low 等文字；"
            "bilingual_terms 元素包含 zh、en。"
        )
        application = state["application"]
        precheck = state["precheck"]
        consistency = state["consistency"]
        context = {
            "target_section": SECTION_LABELS[state["target_section"]],
            "language_mode": state["language_mode"].value,
            "application_snapshot": {
                "marker": "【项目快照】",
                "code": application.code,
                "product_name": application.product_name,
                "applicant_name": application.applicant_name,
                "device_class": application.device_class.value,
                "jurisdiction": application.jurisdiction.value,
                "regulation_effective_on": application.regulation_effective_on.isoformat(),
                "accepted_requirements": [
                    item.title
                    for item in application.requirements
                    if item.status.value == "accepted"
                ],
            },
            "precheck_summary": {
                "id": str(precheck.id),
                "blocker_count": precheck.blocker_count,
                "warning_count": precheck.warning_count,
                "open_findings": [
                    {
                        "title": item.title,
                        "severity": item.severity.value,
                        "remediation": item.remediation,
                    }
                    for item in precheck.findings
                    if item.remediation_status
                    in {
                        FindingRemediationStatus.OPEN,
                        FindingRemediationStatus.IN_PROGRESS,
                    }
                ][:12],
            },
            "consistency_summary": {
                "parser_version": consistency.parser_version,
                "check_count": consistency.check_count,
                "mismatch_count": consistency.mismatch_count,
                "mismatches": [
                    {
                        "label": item.label,
                        "message": item.message,
                    }
                    for item in consistency.checks
                    if item.status.value == "mismatch"
                ],
            },
            "compressed_project_evidence": [
                {
                    "marker": f"【项目证据{index}】",
                    "evidence_id": str(item.evidence_id),
                    "category": item.category_key.value,
                    "file_name": item.file_name,
                    "char_range": [item.char_start, item.char_end],
                    "content_hash": item.content_hash,
                    "content": item.content,
                }
                for index, item in enumerate(state["context_report"].segments, start=1)
            ],
            "regulatory_evidence": [
                {
                    "marker": f"【证据{item.citation_index}】",
                    "source": item.source_title,
                    "document_number": item.document_number,
                    "citation_label": item.citation_label,
                    "content": item.content,
                }
                for item in state["citations"]
            ],
            "controlled_bilingual_terms": [
                item.model_dump(mode="json") for item in expected_terms
            ],
            "output_rules": {
                "language": (
                    "中文正文并完整输出受控中英文术语"
                    if state["language_mode"] == DraftLanguageMode.BILINGUAL
                    else "简体中文正文，bilingual_terms 输出空数组"
                ),
                "minimum_sections": 4,
                "human_review_required": True,
            },
        }
        return system_prompt, json.dumps(context, ensure_ascii=False, indent=2)

    @staticmethod
    def _fallback_draft(
        state: AgentGraphState,
        expected_terms: list[BilingualTerm],
    ) -> ModelDraft:
        application = state["application"]
        precheck = state["precheck"]
        consistency = state["consistency"]
        section_label = SECTION_LABELS[state["target_section"]]
        accepted = [
            item.title for item in application.requirements if item.status.value == "accepted"
        ]
        open_findings = [
            finding.title
            for finding in precheck.findings
            if finding.remediation_status
            in {FindingRemediationStatus.OPEN, FindingRemediationStatus.IN_PROGRESS}
        ]
        project_markers = [
            f"【项目证据{index}】"
            for index, _ in enumerate(state["context_report"].segments, start=1)
        ]
        regulatory_markers = [
            f"【证据{item.citation_index}】" for item in state["citations"]
        ]
        evidence_lines = [
            (
                f"【项目证据{index}】{item.file_name}（{item.category_key.value}，"
                f"字符 {item.char_start}-{item.char_end}）："
                f"{AgentDraftWorkflow._compact(item.content, 260)}"
            )
            for index, item in enumerate(state["context_report"].segments, start=1)
        ]
        regulation_lines = [
            f"【证据{item.citation_index}】{item.source_title}（{item.document_number}），"
            f"{item.citation_label}。"
            for item in state["citations"]
        ]
        sections = [
            StructuredDraftSection(
                heading="编制范围",
                content=(
                    f"本节为“{application.product_name}”{section_label}的内部工作草稿，"
                    f"项目编号为 {application.code}，适用法规基准日为 "
                    f"{application.regulation_effective_on.isoformat()}。"
                ),
                evidence_markers=["【项目快照】"],
            ),
            StructuredDraftSection(
                heading="受控输入",
                content=(
                    f"已接受资料类别：{'、'.join(accepted) if accepted else '无'}。"
                    f"最新预审包含 {precheck.blocker_count} 个阻断项、"
                    f"{precheck.warning_count} 个警告项；一致性检查发现 "
                    f"{consistency.mismatch_count} 项冲突。"
                ),
                evidence_markers=["【项目快照】", *project_markers],
            ),
            StructuredDraftSection(
                heading="项目证据摘要",
                content=(
                    "\n".join(evidence_lines)
                    if evidence_lines
                    else "当前没有已审核通过且可解析的项目证据，需补充受控资料。"
                ),
                evidence_markers=project_markers,
            ),
            StructuredDraftSection(
                heading="法规依据",
                content=(
                    "\n".join(regulation_lines)
                    if regulation_lines
                    else "当前未召回可引用法规条款，需由法规人员补充检索。"
                ),
                evidence_markers=regulatory_markers,
            ),
            StructuredDraftSection(
                heading="待确认事项",
                content=(
                    "\n".join(f"- {item}" for item in open_findings[:8])
                    if open_findings
                    else "当前预审没有未关闭整改项，仍需人工核验事实和引用。"
                ),
                evidence_markers=["【项目快照】"],
            ),
            StructuredDraftSection(
                heading="使用限制",
                content=(
                    "本草稿未替代原始证据、法规原文或专业审核结论。在整改项关闭、"
                    "引用逐条核验并由法规负责人批准前，不得作为受控申报文件。"
                ),
                evidence_markers=["【项目快照】"],
            ),
        ]
        claims = [
            StructuredDraftClaim(
                statement=(
                    f"本草稿对应项目 {application.code} 的“{application.product_name}”"
                    f"{section_label}。"
                ),
                evidence_markers=["【项目快照】"],
                confidence=1.0,
            ),
            StructuredDraftClaim(
                statement=(
                    f"最新预审存在 {precheck.blocker_count} 个阻断项和 "
                    f"{precheck.warning_count} 个警告项。"
                ),
                evidence_markers=["【项目快照】"],
                confidence=1.0,
            ),
            *[
                StructuredDraftClaim(
                    statement=(
                        f"法规检索结果包含 {item.source_title} 的"
                        f"{item.citation_label}。"
                    ),
                    evidence_markers=[f"【证据{item.citation_index}】"],
                    confidence=round(item.score, 3),
                )
                for item in state["citations"]
            ],
        ]
        return ModelDraft(
            title=f"{application.product_name}{section_label}（内部草稿）",
            summary=(
                f"基于 {len(state['context_report'].segments)} 个项目证据片段、"
                f"{len(state['citations'])} 条法规证据和最新预审快照生成的"
                "结构化内部草稿。"
            ),
            sections=sections,
            claims=claims,
            bilingual_terms=(
                expected_terms
                if state["language_mode"] == DraftLanguageMode.BILINGUAL
                else []
            ),
        )

    @staticmethod
    def _render_draft(draft: ModelDraft) -> str:
        chunks = [draft.summary]
        for section in draft.sections:
            markers = " ".join(section.evidence_markers)
            chunks.append(
                f"## {section.heading}\n\n{section.content}"
                + (f"\n\n证据标记：{markers}" if markers else "")
            )
        if draft.bilingual_terms:
            terms = "\n".join(
                f"- {item.zh}：{item.en}" for item in draft.bilingual_terms
            )
            chunks.append(f"## 中英文受控术语\n\n{terms}")
        return "\n\n".join(chunks)

    @staticmethod
    def _compact(content: str, max_chars: int) -> str:
        compacted = " ".join(content.split())
        return compacted if len(compacted) <= max_chars else f"{compacted[:max_chars]}…"

    @staticmethod
    def _start() -> tuple[datetime, float]:
        return datetime.now(UTC), time.perf_counter()

    @staticmethod
    def _finish(
        node_key: str,
        label: str,
        started_at: datetime,
        timer: float,
        status: AgentNodeStatus,
        summary: str,
        input_refs: list[str],
        output_count: int,
    ) -> AgentNodeTrace:
        completed_at = datetime.now(UTC)
        return AgentNodeTrace(
            node_key=node_key,
            label=label,
            status=status,
            summary=summary,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=max(round((time.perf_counter() - timer) * 1000), 0),
            input_refs=input_refs,
            output_count=output_count,
        )
