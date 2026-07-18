export type DeviceClass = "II" | "III";

export type ApplicationStatus =
  | "draft"
  | "intake"
  | "precheck"
  | "in_review"
  | "needs_action"
  | "ready_for_submission"
  | "archived";

export type RequirementStatus =
  | "missing"
  | "uploaded"
  | "needs_review"
  | "accepted"
  | "not_applicable";

export type DossierCategory =
  | "risk_analysis"
  | "technical_requirements"
  | "test_report"
  | "clinical_evaluation"
  | "ifu_and_label"
  | "qms_documents"
  | "other_evidence";

export interface DossierRequirement {
  key: DossierCategory;
  title: string;
  description: string;
  regulatory_basis: string;
  required: boolean;
  status: RequirementStatus;
  evidence_count: number;
}

export interface RegistrationApplication {
  id: string;
  code: string;
  name: string;
  product_name: string;
  applicant_name: string;
  jurisdiction: "CN_NMPA";
  device_class: DeviceClass;
  application_type: "initial_registration";
  regulation_effective_on: string;
  owner_name: string;
  status: ApplicationStatus;
  requirements: DossierRequirement[];
  completion_rate: number;
  created_at: string;
  updated_at: string;
}

export interface RegistrationApplicationList {
  items: RegistrationApplication[];
  total: number;
}

export interface RegistrationApplicationCreate {
  name: string;
  product_name: string;
  applicant_name: string;
  jurisdiction: "CN_NMPA";
  device_class: DeviceClass;
  application_type: "initial_registration";
  regulation_effective_on: string;
  owner_name: string;
}

export interface DossierEvidence {
  id: string;
  application_id: string;
  category_key: DossierCategory;
  file_name: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  bucket_name: string;
  object_key: string;
  uploaded_by: string;
  created_at: string;
}

export interface DossierEvidenceList {
  items: DossierEvidence[];
  total: number;
}

export type FindingSeverity = "blocker" | "warning";
export type FindingRemediationStatus =
  | "open"
  | "in_progress"
  | "resolved"
  | "waived";

export interface PrecheckFinding {
  id: string;
  category_key: DossierCategory;
  rule_code: string;
  severity: FindingSeverity;
  title: string;
  description: string;
  regulatory_basis: string;
  remediation: string;
  remediation_status: FindingRemediationStatus;
  assignee: string | null;
  resolution_note: string | null;
  updated_by: string | null;
  resolved_at: string | null;
  position: number;
  created_at: string;
  updated_at: string;
}

export interface PrecheckRun {
  id: string;
  application_id: string;
  status: "completed";
  rule_set_version: string;
  application_status: ApplicationStatus;
  blocker_count: number;
  warning_count: number;
  pass_count: number;
  initiated_by: string;
  started_at: string;
  completed_at: string;
  created_at: string;
  findings: PrecheckFinding[];
}

export interface PrecheckRunList {
  items: PrecheckRun[];
  total: number;
}

export interface EvidenceMatrixRow {
  category_key: DossierCategory;
  title: string;
  regulatory_basis: string;
  requirement_status: RequirementStatus;
  evidence_count: number;
  evidence: DossierEvidence[];
  findings: PrecheckFinding[];
}

export interface EvidenceMatrix {
  application_id: string;
  application_code: string;
  application_name: string;
  completion_rate: number;
  latest_precheck_id: string | null;
  latest_precheck_at: string | null;
  blocker_count: number;
  warning_count: number;
  open_finding_count: number;
  rows: EvidenceMatrixRow[];
}

export type ConsistencyField =
  | "product_name"
  | "model_specification"
  | "intended_use"
  | "performance"
  | "warnings";
export type ConsistencyStatus = "pass" | "mismatch" | "insufficient";

export interface ConsistencyOccurrence {
  source_label: string;
  category_key: DossierCategory | null;
  evidence_id: string | null;
  file_name: string | null;
  value: string;
}

export interface ConsistencyCheck {
  field: ConsistencyField;
  label: string;
  status: ConsistencyStatus;
  severity: FindingSeverity | null;
  threshold: number;
  occurrence_count: number;
  distinct_value_count: number;
  message: string;
  occurrences: ConsistencyOccurrence[];
}

export interface UnreadableEvidence {
  evidence_id: string;
  category_key: DossierCategory;
  file_name: string;
  reason: string;
}

export interface DossierConsistencyReport {
  application_id: string;
  application_code: string;
  generated_at: string;
  parser_version: string;
  check_count: number;
  pass_count: number;
  mismatch_count: number;
  insufficient_count: number;
  unreadable_evidence: UnreadableEvidence[];
  checks: ConsistencyCheck[];
}

export interface PrecheckReportEvidence {
  evidence_id: string;
  category_key: DossierCategory;
  category_title: string;
  requirement_status: RequirementStatus;
  file_name: string;
  size_bytes: number;
  sha256: string;
  uploaded_by: string;
  created_at: string;
}

export interface InternalPrecheckReport {
  report_id: string;
  report_code: string;
  generated_at: string;
  generated_by: string;
  is_stale: boolean;
  stale_reason: string | null;
  application: RegistrationApplication;
  precheck: PrecheckRun;
  evidence_count: number;
  accepted_category_count: number;
  open_finding_count: number;
  evidence_manifest: PrecheckReportEvidence[];
  consistency: DossierConsistencyReport;
}

export type DraftSection =
  | "product_overview"
  | "risk_management_summary"
  | "technical_requirements_summary"
  | "ifu_label_summary";
export type AgentNodeStatus = "completed" | "degraded";
export type AgentModelMode = "live" | "deterministic" | "fallback";
export type AgentApprovalStatus = "pending" | "approved" | "rejected";
export type DraftLanguageMode = "zh_cn" | "bilingual";
export type BilingualCheckStatus =
  | "pass"
  | "missing"
  | "mismatch"
  | "not_applicable";

export interface AgentRuntimeStatus {
  workflow_version: string;
  provider: string;
  model: string;
  mode: AgentModelMode;
  configured: boolean;
}

export interface AgentNodeTrace {
  node_key: string;
  label: string;
  status: AgentNodeStatus;
  summary: string;
  started_at: string;
  completed_at: string;
  duration_ms: number;
  input_refs: string[];
  output_count: number;
}

export interface AgentCitation {
  citation_index: number;
  chunk_id: string;
  document_id: string;
  regulation_version_id: string;
  source_title: string;
  document_number: string;
  version_label: string;
  citation_label: string;
  content: string;
  char_start: number;
  char_end: number;
  score: number;
}

export interface AgentContextSegment {
  evidence_id: string;
  category_key: DossierCategory;
  file_name: string;
  segment_index: number;
  char_start: number;
  char_end: number;
  content: string;
  content_hash: string;
  score: number;
  matched_terms: string[];
}

export interface AgentContextReport {
  algorithm_version: string;
  source_count: number;
  original_chars: number;
  selected_chars: number;
  max_chars: number;
  compression_ratio: number;
  omitted_source_count: number;
  segments: AgentContextSegment[];
}

export interface StructuredDraftSection {
  heading: string;
  content: string;
  evidence_markers: string[];
}

export interface StructuredDraftClaim {
  statement: string;
  evidence_markers: string[];
  confidence: number;
}

export interface BilingualTerm {
  zh: string;
  en: string;
}

export interface StructuredAgentDraft {
  title: string;
  summary: string;
  sections: StructuredDraftSection[];
  claims: StructuredDraftClaim[];
  bilingual_terms: BilingualTerm[];
}

export interface BilingualTermCheck {
  zh: string;
  expected_en: string;
  actual_en: string | null;
  status: BilingualCheckStatus;
  message: string;
}

export interface BilingualConsistencyReport {
  glossary_version: string;
  language_mode: DraftLanguageMode;
  status: BilingualCheckStatus;
  pass_count: number;
  missing_count: number;
  mismatch_count: number;
  checks: BilingualTermCheck[];
}

export interface AgentDraftRun {
  id: string;
  application_id: string;
  workflow_version: string;
  status: "completed" | "failed";
  target_section: DraftSection;
  language_mode: DraftLanguageMode;
  requested_by: string;
  input_snapshot_hash: string;
  input_snapshot: Record<string, unknown>;
  prompt_version: string;
  prompt_snapshot: string;
  model_provider: string;
  model_name: string;
  model_mode: AgentModelMode;
  model_error: string | null;
  draft_title: string;
  draft_content: string;
  reviewer_summary: string;
  context_report: AgentContextReport | null;
  structured_output: StructuredAgentDraft | null;
  bilingual_report: BilingualConsistencyReport | null;
  node_traces: AgentNodeTrace[];
  citations: AgentCitation[];
  approval_status: AgentApprovalStatus;
  reviewed_by: string | null;
  review_note: string | null;
  reviewed_at: string | null;
  started_at: string;
  completed_at: string;
  created_at: string;
  updated_at: string;
}

export interface AgentDraftRunList {
  items: AgentDraftRun[];
  total: number;
}

export type EvaluationTaskType =
  | "retrieval"
  | "citation"
  | "conflict"
  | "schema"
  | "adoption";
export type EvaluationAnnotationStatus = "curated_demo" | "expert_verified";
export type ProductionValidationStatus =
  | "pending_domain_expert"
  | "expert_verified";

export interface EvaluationPrediction {
  ranked_labels: string[];
  labels: string[];
  fields: string[];
  valid_json: boolean | null;
  adopted: boolean | null;
  latency_ms: number;
}

export interface EvaluationCase {
  id: string;
  task_type: EvaluationTaskType;
  title: string;
  input_text: string;
  gold_labels: string[];
  required_fields: string[];
  baseline: EvaluationPrediction;
  candidate: EvaluationPrediction;
  annotation_status: EvaluationAnnotationStatus;
  tags: string[];
}

export interface EvaluationDatasetSummary {
  dataset_version: string;
  dataset_hash: string;
  case_count: number;
  task_counts: Record<EvaluationTaskType, number>;
  annotation_mode: string;
  production_validation_status: ProductionValidationStatus;
  verified_count: number;
  pending_count: number;
  source_note: string;
}

export interface EvaluationCaseList {
  items: EvaluationCase[];
  total: number;
}

export interface EvaluationMetric {
  key: string;
  label: string;
  unit: "ratio" | "ms";
  higher_is_better: boolean;
  baseline: number;
  candidate: number;
  delta: number;
  target: number;
  passed: boolean;
}

export interface EvaluationTaskSummary {
  task_type: EvaluationTaskType;
  case_count: number;
  baseline_score: number;
  candidate_score: number;
  delta: number;
  metric_keys: string[];
}

export interface EvaluationQualityGate {
  status: "passed" | "needs_attention";
  passed_count: number;
  total_count: number;
  production_validation_status: ProductionValidationStatus;
  message: string;
}

export interface EvaluationRun {
  id: string;
  dataset_version: string;
  dataset_hash: string;
  status: "completed";
  requested_by: string;
  baseline_name: string;
  candidate_name: string;
  case_count: number;
  metrics: EvaluationMetric[];
  task_summaries: EvaluationTaskSummary[];
  quality_gate: EvaluationQualityGate;
  started_at: string;
  completed_at: string;
  created_at: string;
}

export interface EvaluationRunList {
  items: EvaluationRun[];
  total: number;
}

export type RegulationType =
  | "regulation"
  | "guidance"
  | "notice"
  | "standard"
  | "technical_guideline";

export type RegulationReviewStatus = "pending_review" | "verified" | "rejected";
export type RegulationLifecycleStatus = "unknown" | "upcoming" | "effective" | "expired";

export interface RegulationVersion {
  id: string;
  version_label: string;
  document_number: string;
  official_url: string;
  published_on: string;
  effective_on: string;
  expires_on: string | null;
  review_status: RegulationReviewStatus;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  lifecycle_status: RegulationLifecycleStatus;
  created_at: string;
  updated_at: string;
}

export interface RegulationSource {
  id: string;
  code: string;
  title: string;
  issuing_authority: string;
  jurisdiction: string;
  regulation_type: RegulationType;
  scope_summary: string;
  versions: RegulationVersion[];
  applicable_version: RegulationVersion | null;
  created_at: string;
  updated_at: string;
}

export interface RegulationSourceList {
  items: RegulationSource[];
  total: number;
  as_of: string;
}

export type KnowledgeGraphNodeType =
  | "regulation_source"
  | "regulation_version"
  | "device_scope"
  | "dossier_requirement"
  | "legal_chunk";

export type KnowledgeGraphRelationshipType =
  | "has_version"
  | "supersedes"
  | "cites"
  | "applies_to"
  | "requires"
  | "supported_by";

export interface KnowledgeGraphNode {
  id: string;
  node_type: KnowledgeGraphNodeType;
  label: string;
  summary: string;
  metadata: Record<string, string | number | boolean | null>;
}

export interface KnowledgeGraphRelationship {
  id: string;
  relationship_type: KnowledgeGraphRelationshipType;
  source_id: string;
  target_id: string;
  label: string;
  basis: string;
  evidence_label: string | null;
  evidence_excerpt: string | null;
  verified: boolean;
}

export interface KnowledgeGraphProjection {
  source_id: string;
  projection_version: string;
  generated_at: string;
  node_count: number;
  relationship_count: number;
  nodes: KnowledgeGraphNode[];
  relationships: KnowledgeGraphRelationship[];
}

export interface KnowledgeGraphSyncResult {
  source_id: string;
  projection_version: string;
  nodes_written: number;
  relationships_written: number;
  synced_at: string;
}

export interface RegulationSourceCreate {
  title: string;
  issuing_authority: string;
  jurisdiction: string;
  regulation_type: RegulationType;
  scope_summary: string;
  initial_version: {
    version_label: string;
    document_number: string;
    official_url: string;
    published_on: string;
    effective_on: string;
    expires_on: string | null;
  };
}

export interface RegulationVersionCreate {
  version_label: string;
  document_number: string;
  official_url: string;
  published_on: string;
  effective_on: string;
  expires_on: string | null;
}

export type DocumentStorageStatus = "archived";
export type DocumentParseStatus =
  | "pending"
  | "queued"
  | "processing"
  | "completed"
  | "failed";

export interface RegulationDocument {
  id: string;
  code: string;
  regulation_version_id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  security_status: "legacy" | "passed";
  security_engine: string;
  detected_type: string;
  security_findings: string[];
  bucket_name: string;
  object_key: string;
  storage_status: DocumentStorageStatus;
  parse_status: DocumentParseStatus;
  parse_attempts: number;
  parse_task_id: string | null;
  parser_version: string | null;
  segmenter_version: string | null;
  section_count: number;
  chunk_count: number;
  table_count: number;
  extracted_char_count: number;
  parse_error: string | null;
  uploaded_by: string;
  queued_at: string | null;
  processing_started_at: string | null;
  parsed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface RegulationDocumentList {
  items: RegulationDocument[];
  total: number;
}

export interface DocumentSection {
  id: string;
  document_id: string;
  parent_id: string | null;
  kind: "chapter" | "section" | "article" | "body";
  ordinal: number;
  heading: string;
  citation_path: string;
  content: string;
  char_start: number;
  char_end: number;
  content_hash: string;
  created_at: string;
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  section_id: string;
  ordinal: number;
  section_chunk_index: number;
  citation_label: string;
  content: string;
  char_start: number;
  char_end: number;
  char_count: number;
  token_estimate: number;
  content_hash: string;
  created_at: string;
}

export interface DocumentStructure {
  document_id: string;
  parser_version: string | null;
  segmenter_version: string | null;
  section_count: number;
  chunk_count: number;
  table_count: number;
  sections: DocumentSection[];
  chunks: DocumentChunk[];
  tables: DocumentTable[];
}

export interface DocumentTable {
  id: string;
  document_id: string;
  ordinal: number;
  title: string;
  sheet_name: string | null;
  row_count: number;
  column_count: number;
  headers: string[];
  rows: string[][];
  source_locator: string;
  content_hash: string;
  created_at: string;
}

export type DocumentFetchStatus =
  | "pending_approval"
  | "queued"
  | "fetching"
  | "completed"
  | "failed"
  | "rejected";

export interface DocumentFetchRequest {
  id: string;
  regulation_version_id: string;
  official_url: string;
  status: DocumentFetchStatus;
  requested_by: string;
  request_reason: string;
  reviewed_by: string | null;
  review_note: string | null;
  reviewed_at: string | null;
  task_id: string | null;
  resulting_document_id: string | null;
  fetch_error: string | null;
  queued_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentFetchRequestList {
  items: DocumentFetchRequest[];
  total: number;
}

export type VectorIndexStatus =
  | "pending"
  | "queued"
  | "processing"
  | "completed"
  | "failed"
  | "stale";

export interface VectorIndex {
  document_id: string;
  status: VectorIndexStatus;
  attempts: number;
  task_id: string | null;
  collection_name: string;
  dense_model: string;
  sparse_model: string;
  content_fingerprint: string;
  indexed_chunk_count: number;
  index_error: string | null;
  queued_at: string | null;
  processing_started_at: string | null;
  indexed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvidenceHit {
  chunk_id: string;
  document_id: string;
  regulation_version_id: string;
  source_id: string;
  source_title: string;
  document_number: string;
  version_label: string;
  citation_label: string;
  content: string;
  char_start: number;
  char_end: number;
  retrieval_score: number;
  rerank_score: number;
  matched_terms: string[];
}

export interface HybridSearchResponse {
  query: string;
  strategy: string;
  dense_model: string;
  sparse_model: string;
  elapsed_ms: number;
  total: number;
  items: EvidenceHit[];
}

export type TenantRole = "owner" | "reviewer" | "editor" | "viewer";
export type SecurityPermission = "read" | "write" | "review" | "admin";

export interface ActorContext {
  tenant_id: string;
  tenant_name: string;
  user_id: string;
  user_name: string;
  email: string;
  role: TenantRole;
  permissions: SecurityPermission[];
}

export interface TenantMember {
  user_id: string;
  display_name: string;
  email: string;
  role: TenantRole;
  status: "active";
  joined_at: string;
}

export interface SecurityWorkspace {
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  current_actor: ActorContext;
  members: TenantMember[];
  audit_event_count: number;
  boundary_note: string;
}

export interface AuditEvent {
  id: string;
  tenant_id: string;
  actor_user_id: string;
  actor_name: string;
  actor_role: TenantRole;
  action: string;
  resource_type: string;
  resource_id: string | null;
  request_method: string;
  request_path: string;
  outcome: "success" | "failed";
  status_code: number;
  request_id: string;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface AuditEventList {
  items: AuditEvent[];
  total: number;
}
