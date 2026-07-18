import uuid
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Jurisdiction(StrEnum):
    CN_NMPA = "CN_NMPA"


class DeviceClass(StrEnum):
    CLASS_II = "II"
    CLASS_III = "III"


class ApplicationType(StrEnum):
    INITIAL_REGISTRATION = "initial_registration"


class ApplicationStatus(StrEnum):
    DRAFT = "draft"
    INTAKE = "intake"
    PRECHECK = "precheck"
    IN_REVIEW = "in_review"
    NEEDS_ACTION = "needs_action"
    READY_FOR_SUBMISSION = "ready_for_submission"
    ARCHIVED = "archived"


class RequirementStatus(StrEnum):
    MISSING = "missing"
    UPLOADED = "uploaded"
    NEEDS_REVIEW = "needs_review"
    ACCEPTED = "accepted"
    NOT_APPLICABLE = "not_applicable"


class RequirementReviewDecision(StrEnum):
    ACCEPTED = "accepted"
    NEEDS_REVIEW = "needs_review"


class PrecheckStatus(StrEnum):
    COMPLETED = "completed"


class FindingSeverity(StrEnum):
    BLOCKER = "blocker"
    WARNING = "warning"


class FindingRemediationStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    WAIVED = "waived"


class ConsistencyField(StrEnum):
    PRODUCT_NAME = "product_name"
    MODEL_SPECIFICATION = "model_specification"
    INTENDED_USE = "intended_use"
    PERFORMANCE = "performance"
    WARNINGS = "warnings"


class ConsistencyStatus(StrEnum):
    PASS = "pass"
    MISMATCH = "mismatch"
    INSUFFICIENT = "insufficient"


class DossierCategory(StrEnum):
    RISK_ANALYSIS = "risk_analysis"
    TECHNICAL_REQUIREMENTS = "technical_requirements"
    TEST_REPORT = "test_report"
    CLINICAL_EVALUATION = "clinical_evaluation"
    IFU_AND_LABEL = "ifu_and_label"
    QMS_DOCUMENTS = "qms_documents"
    OTHER_EVIDENCE = "other_evidence"


class DossierCategoryDefinition(BaseModel):
    key: DossierCategory
    title: str
    description: str
    regulatory_basis: str


DOSSIER_CATEGORY_DEFINITIONS = (
    DossierCategoryDefinition(
        key=DossierCategory.RISK_ANALYSIS,
        title="产品风险分析资料",
        description="识别危害、风险评价、风险控制及剩余风险评价。",
        regulatory_basis="《医疗器械注册与备案管理办法》第五十二条（一）",
    ),
    DossierCategoryDefinition(
        key=DossierCategory.TECHNICAL_REQUIREMENTS,
        title="产品技术要求",
        description="产品性能指标、检验方法和适用的技术要求。",
        regulatory_basis="《医疗器械注册与备案管理办法》第五十二条（二）",
    ),
    DossierCategoryDefinition(
        key=DossierCategory.TEST_REPORT,
        title="产品检验报告",
        description="支持产品安全性和有效性的检验记录与报告。",
        regulatory_basis="《医疗器械注册与备案管理办法》第五十二条（三）",
    ),
    DossierCategoryDefinition(
        key=DossierCategory.CLINICAL_EVALUATION,
        title="临床评价资料",
        description="临床评价路径、临床数据、分析与结论。",
        regulatory_basis="《医疗器械注册与备案管理办法》第五十二条（四）",
    ),
    DossierCategoryDefinition(
        key=DossierCategory.IFU_AND_LABEL,
        title="产品说明书和标签样稿",
        description="说明书、标签及其受控版本和一致性证据。",
        regulatory_basis="《医疗器械注册与备案管理办法》第五十二条（五）",
    ),
    DossierCategoryDefinition(
        key=DossierCategory.QMS_DOCUMENTS,
        title="质量管理体系文件",
        description="与产品研制、生产和质量控制有关的体系文件。",
        regulatory_basis="《医疗器械注册与备案管理办法》第五十二条（六）",
    ),
    DossierCategoryDefinition(
        key=DossierCategory.OTHER_EVIDENCE,
        title="其他安全有效性证明资料",
        description="证明产品安全、有效所需的其他材料。",
        regulatory_basis="《医疗器械注册与备案管理办法》第五十二条（七）",
    ),
)


class DossierRequirement(BaseModel):
    key: DossierCategory
    title: str
    description: str
    regulatory_basis: str
    required: bool = True
    status: RequirementStatus = RequirementStatus.MISSING
    evidence_count: int = 0


class RegistrationApplicationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    product_name: str = Field(min_length=2, max_length=160)
    applicant_name: str = Field(min_length=2, max_length=160)
    jurisdiction: Jurisdiction = Jurisdiction.CN_NMPA
    device_class: DeviceClass
    application_type: ApplicationType = ApplicationType.INITIAL_REGISTRATION
    regulation_effective_on: date
    owner_name: str = Field(default="未分配", min_length=2, max_length=80)


class RegistrationApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    product_name: str
    applicant_name: str
    jurisdiction: Jurisdiction
    device_class: DeviceClass
    application_type: ApplicationType
    regulation_effective_on: date
    owner_name: str
    status: ApplicationStatus
    requirements: list[DossierRequirement]
    completion_rate: float
    created_at: datetime
    updated_at: datetime


class RegistrationApplicationList(BaseModel):
    items: list[RegistrationApplicationRead]
    total: int


class RequirementReviewCreate(BaseModel):
    decision: RequirementReviewDecision
    reviewed_by: str = Field(min_length=2, max_length=80)


class DossierEvidenceRead(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    category_key: DossierCategory
    file_name: str
    content_type: str
    size_bytes: int
    sha256: str
    bucket_name: str
    object_key: str
    uploaded_by: str
    created_at: datetime


class DossierEvidenceList(BaseModel):
    items: list[DossierEvidenceRead]
    total: int


class PrecheckCreate(BaseModel):
    initiated_by: str = Field(default="法规专员", min_length=2, max_length=80)


class PrecheckFinding(BaseModel):
    id: uuid.UUID
    category_key: DossierCategory
    rule_code: str
    severity: FindingSeverity
    title: str
    description: str
    regulatory_basis: str
    remediation: str
    remediation_status: FindingRemediationStatus = FindingRemediationStatus.OPEN
    assignee: str | None = None
    resolution_note: str | None = None
    updated_by: str | None = None
    resolved_at: datetime | None = None
    position: int
    created_at: datetime
    updated_at: datetime


class FindingRemediationUpdate(BaseModel):
    status: FindingRemediationStatus
    assignee: str | None = Field(default=None, min_length=2, max_length=80)
    note: str | None = Field(default=None, max_length=1000)
    updated_by: str = Field(min_length=2, max_length=80)


class PrecheckRun(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    status: PrecheckStatus
    rule_set_version: str
    application_status: ApplicationStatus
    blocker_count: int
    warning_count: int
    pass_count: int
    initiated_by: str
    started_at: datetime
    completed_at: datetime
    created_at: datetime
    findings: list[PrecheckFinding]


class PrecheckRunList(BaseModel):
    items: list[PrecheckRun]
    total: int


class EvidenceMatrixRow(BaseModel):
    category_key: DossierCategory
    title: str
    regulatory_basis: str
    requirement_status: RequirementStatus
    evidence_count: int
    evidence: list[DossierEvidenceRead]
    findings: list[PrecheckFinding]


class EvidenceMatrix(BaseModel):
    application_id: uuid.UUID
    application_code: str
    application_name: str
    completion_rate: float
    latest_precheck_id: uuid.UUID | None
    latest_precheck_at: datetime | None
    blocker_count: int
    warning_count: int
    open_finding_count: int
    rows: list[EvidenceMatrixRow]


class ConsistencyOccurrence(BaseModel):
    source_label: str
    category_key: DossierCategory | None = None
    evidence_id: uuid.UUID | None = None
    file_name: str | None = None
    value: str


class ConsistencyCheck(BaseModel):
    field: ConsistencyField
    label: str
    status: ConsistencyStatus
    severity: FindingSeverity | None = None
    threshold: float
    occurrence_count: int
    distinct_value_count: int
    message: str
    occurrences: list[ConsistencyOccurrence]


class UnreadableEvidence(BaseModel):
    evidence_id: uuid.UUID
    category_key: DossierCategory
    file_name: str
    reason: str


class DossierConsistencyReport(BaseModel):
    application_id: uuid.UUID
    application_code: str
    generated_at: datetime
    parser_version: str
    check_count: int
    pass_count: int
    mismatch_count: int
    insufficient_count: int
    unreadable_evidence: list[UnreadableEvidence]
    checks: list[ConsistencyCheck]


class PrecheckReportEvidence(BaseModel):
    evidence_id: uuid.UUID
    category_key: DossierCategory
    category_title: str
    requirement_status: RequirementStatus
    file_name: str
    size_bytes: int
    sha256: str
    uploaded_by: str
    created_at: datetime


class InternalPrecheckReport(BaseModel):
    report_id: uuid.UUID
    report_code: str
    generated_at: datetime
    generated_by: str
    is_stale: bool
    stale_reason: str | None
    application: RegistrationApplicationRead
    precheck: PrecheckRun
    evidence_count: int
    accepted_category_count: int
    open_finding_count: int
    evidence_manifest: list[PrecheckReportEvidence]
    consistency: DossierConsistencyReport
