from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class EvaluationTaskType(StrEnum):
    RETRIEVAL = "retrieval"
    CITATION = "citation"
    CONFLICT = "conflict"
    SCHEMA = "schema"
    ADOPTION = "adoption"


class AnnotationStatus(StrEnum):
    CURATED_DEMO = "curated_demo"
    EXPERT_VERIFIED = "expert_verified"


class EvaluationRunStatus(StrEnum):
    COMPLETED = "completed"


class QualityGateStatus(StrEnum):
    PASSED = "passed"
    NEEDS_ATTENTION = "needs_attention"


class ProductionValidationStatus(StrEnum):
    PENDING_DOMAIN_EXPERT = "pending_domain_expert"
    EXPERT_VERIFIED = "expert_verified"


class EvaluationPrediction(BaseModel):
    ranked_labels: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)
    valid_json: bool | None = None
    adopted: bool | None = None
    latency_ms: int = Field(ge=0)


class EvaluationCase(BaseModel):
    id: str
    task_type: EvaluationTaskType
    title: str
    input_text: str
    gold_labels: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    baseline: EvaluationPrediction
    candidate: EvaluationPrediction
    annotation_status: AnnotationStatus = AnnotationStatus.CURATED_DEMO
    tags: list[str] = Field(default_factory=list)


class EvaluationDatasetSummary(BaseModel):
    dataset_version: str
    dataset_hash: str
    case_count: int
    task_counts: dict[EvaluationTaskType, int]
    annotation_mode: str
    production_validation_status: ProductionValidationStatus
    verified_count: int
    pending_count: int
    source_note: str


class EvaluationCaseList(BaseModel):
    items: list[EvaluationCase]
    total: int


class EvaluationRunCreate(BaseModel):
    requested_by: str = Field(min_length=2, max_length=80)


class EvaluationMetric(BaseModel):
    key: str
    label: str
    unit: str
    higher_is_better: bool
    baseline: float
    candidate: float
    delta: float
    target: float
    passed: bool


class EvaluationTaskSummary(BaseModel):
    task_type: EvaluationTaskType
    case_count: int
    baseline_score: float
    candidate_score: float
    delta: float
    metric_keys: list[str]


class EvaluationQualityGate(BaseModel):
    status: QualityGateStatus
    passed_count: int
    total_count: int
    production_validation_status: ProductionValidationStatus
    message: str


class EvaluationRun(BaseModel):
    id: uuid.UUID
    dataset_version: str
    dataset_hash: str
    status: EvaluationRunStatus
    requested_by: str
    baseline_name: str
    candidate_name: str
    case_count: int
    metrics: list[EvaluationMetric]
    task_summaries: list[EvaluationTaskSummary]
    quality_gate: EvaluationQualityGate
    started_at: datetime
    completed_at: datetime
    created_at: datetime


class EvaluationRunList(BaseModel):
    items: list[EvaluationRun]
    total: int
