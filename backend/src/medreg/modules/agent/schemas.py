from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from medreg.modules.applications.schemas import DossierCategory


class DraftSection(StrEnum):
    PRODUCT_OVERVIEW = "product_overview"
    RISK_MANAGEMENT_SUMMARY = "risk_management_summary"
    TECHNICAL_REQUIREMENTS_SUMMARY = "technical_requirements_summary"
    IFU_LABEL_SUMMARY = "ifu_label_summary"


class DraftLanguageMode(StrEnum):
    ZH_CN = "zh_cn"
    BILINGUAL = "bilingual"


class AgentRunStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class AgentNodeStatus(StrEnum):
    COMPLETED = "completed"
    DEGRADED = "degraded"


class ModelMode(StrEnum):
    LIVE = "live"
    DETERMINISTIC = "deterministic"
    FALLBACK = "fallback"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AgentApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class AgentDraftRunCreate(BaseModel):
    target_section: DraftSection
    language_mode: DraftLanguageMode = DraftLanguageMode.ZH_CN
    requested_by: str = Field(min_length=2, max_length=80)


class AgentApprovalCreate(BaseModel):
    decision: AgentApprovalDecision
    reviewed_by: str = Field(min_length=2, max_length=80)
    note: str = Field(min_length=2, max_length=1000)


class AgentNodeTrace(BaseModel):
    node_key: str
    label: str
    status: AgentNodeStatus
    summary: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    input_refs: list[str] = Field(default_factory=list)
    output_count: int = 0


class AgentCitation(BaseModel):
    citation_index: int
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    regulation_version_id: uuid.UUID
    source_title: str
    document_number: str
    version_label: str
    citation_label: str
    content: str
    char_start: int
    char_end: int
    score: float


class ContextSegment(BaseModel):
    evidence_id: uuid.UUID
    category_key: DossierCategory
    file_name: str
    segment_index: int
    char_start: int
    char_end: int
    content: str
    content_hash: str
    score: float
    matched_terms: list[str]


class ContextCompressionReport(BaseModel):
    algorithm_version: str
    source_count: int
    original_chars: int
    selected_chars: int
    max_chars: int
    compression_ratio: float
    omitted_source_count: int
    segments: list[ContextSegment]


class StructuredDraftSection(BaseModel):
    heading: str = Field(min_length=2, max_length=120)
    content: str = Field(min_length=2, max_length=6000)
    evidence_markers: list[str] = Field(default_factory=list, max_length=20)


class StructuredDraftClaim(BaseModel):
    statement: str = Field(min_length=2, max_length=1000)
    evidence_markers: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0, le=1)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_model_confidence(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        normalized = value.strip().lower()
        labels = {
            "high": 0.9,
            "medium": 0.6,
            "low": 0.3,
            "高": 0.9,
            "中": 0.6,
            "低": 0.3,
        }
        if normalized in labels:
            return labels[normalized]
        if normalized.endswith("%"):
            return float(normalized[:-1]) / 100
        return value


class BilingualTerm(BaseModel):
    zh: str = Field(min_length=1, max_length=120)
    en: str = Field(min_length=1, max_length=240)


class BilingualCheckStatus(StrEnum):
    PASS = "pass"
    MISSING = "missing"
    MISMATCH = "mismatch"
    NOT_APPLICABLE = "not_applicable"


class BilingualTermCheck(BaseModel):
    zh: str
    expected_en: str
    actual_en: str | None
    status: BilingualCheckStatus
    message: str


class BilingualConsistencyReport(BaseModel):
    glossary_version: str
    language_mode: DraftLanguageMode
    status: BilingualCheckStatus
    pass_count: int
    missing_count: int
    mismatch_count: int
    checks: list[BilingualTermCheck]


class ModelDraft(BaseModel):
    title: str
    summary: str = Field(min_length=2, max_length=1200)
    sections: list[StructuredDraftSection] = Field(min_length=1, max_length=10)
    claims: list[StructuredDraftClaim] = Field(default_factory=list, max_length=20)
    bilingual_terms: list[BilingualTerm] = Field(default_factory=list, max_length=30)


class AgentDraftRun(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    workflow_version: str
    status: AgentRunStatus
    target_section: DraftSection
    language_mode: DraftLanguageMode
    requested_by: str
    input_snapshot_hash: str
    input_snapshot: dict[str, Any]
    prompt_version: str
    prompt_snapshot: str
    model_provider: str
    model_name: str
    model_mode: ModelMode
    model_error: str | None
    draft_title: str
    draft_content: str
    reviewer_summary: str
    context_report: ContextCompressionReport | None
    structured_output: ModelDraft | None
    bilingual_report: BilingualConsistencyReport | None
    node_traces: list[AgentNodeTrace]
    citations: list[AgentCitation]
    approval_status: ApprovalStatus
    reviewed_by: str | None
    review_note: str | None
    reviewed_at: datetime | None
    started_at: datetime
    completed_at: datetime
    created_at: datetime
    updated_at: datetime


class AgentDraftRunList(BaseModel):
    items: list[AgentDraftRun]
    total: int


class AgentRuntimeStatus(BaseModel):
    workflow_version: str
    provider: str
    model: str
    mode: ModelMode
    configured: bool
