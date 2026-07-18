import type {
  AgentDraftRun,
  AgentDraftRunList,
  AgentRuntimeStatus,
  RegistrationApplication,
  RegistrationApplicationCreate,
  RegistrationApplicationList,
  DossierCategory,
  DossierEvidence,
  DossierEvidenceList,
  DossierConsistencyReport,
  EvidenceMatrix,
  EvaluationCaseList,
  EvaluationDatasetSummary,
  EvaluationRun,
  EvaluationRunList,
  DocumentFetchRequest,
  DocumentFetchRequestList,
  DocumentStructure,
  RegulationDocument,
  RegulationDocumentList,
  RegulationSource,
  RegulationSourceCreate,
  RegulationSourceList,
  RegulationVersionCreate,
  HybridSearchResponse,
  KnowledgeGraphProjection,
  KnowledgeGraphSyncResult,
  PrecheckRun,
  PrecheckRunList,
  PrecheckFinding,
  FindingRemediationStatus,
  InternalPrecheckReport,
  AuditEventList,
  SecurityWorkspace,
  VectorIndex,
} from "../types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8200/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { detail?: string | Array<{ msg: string }> }
      | null;
    const detail = Array.isArray(body?.detail)
      ? body.detail.map((item) => item.msg).join("；")
      : body?.detail;
    throw new Error(detail || `请求失败（${response.status}）`);
  }

  return response.json() as Promise<T>;
}

async function uploadRequest<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail || `请求失败（${response.status}）`);
  }
  return response.json() as Promise<T>;
}

async function downloadRequest(path: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail || `下载失败（${response.status}）`);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const fileName = disposition.match(/filename="([^"]+)"/)?.[1] ?? "precheck-report.pdf";
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  return fileName;
}

export const applicationsApi = {
  list: () => request<RegistrationApplicationList>("/registration-applications"),
  get: (applicationId: string) =>
    request<RegistrationApplication>(
      `/registration-applications/${applicationId}`,
    ),
  create: (payload: RegistrationApplicationCreate) =>
    request<RegistrationApplication>("/registration-applications", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  uploadEvidence: (
    applicationId: string,
    categoryKey: DossierCategory,
    file: File,
    uploadedBy: string,
  ) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("uploaded_by", uploadedBy);
    return uploadRequest<DossierEvidence>(
      `/registration-applications/${applicationId}/requirements/${categoryKey}/evidence`,
      formData,
    );
  },
  listEvidence: (applicationId: string, categoryKey: DossierCategory) =>
    request<DossierEvidenceList>(
      `/registration-applications/${applicationId}/requirements/${categoryKey}/evidence`,
    ),
  reviewRequirement: (
    applicationId: string,
    categoryKey: DossierCategory,
    decision: "accepted" | "needs_review",
  ) =>
    request<RegistrationApplication>(
      `/registration-applications/${applicationId}/requirements/${categoryKey}/review`,
      {
        method: "PATCH",
        body: JSON.stringify({ decision, reviewed_by: "法规负责人" }),
      },
    ),
  runPrecheck: (applicationId: string) =>
    request<PrecheckRun>(
      `/registration-applications/${applicationId}/prechecks`,
      {
        method: "POST",
        body: JSON.stringify({ initiated_by: "刘凯旗" }),
      },
    ),
  listPrechecks: (applicationId: string) =>
    request<PrecheckRunList>(
      `/registration-applications/${applicationId}/prechecks`,
    ),
  getEvidenceMatrix: (applicationId: string) =>
    request<EvidenceMatrix>(
      `/registration-applications/${applicationId}/evidence-matrix`,
    ),
  getConsistencyReport: (applicationId: string) =>
    request<DossierConsistencyReport>(
      `/registration-applications/${applicationId}/consistency-report`,
    ),
  getPrecheckReport: (applicationId: string) =>
    request<InternalPrecheckReport>(
      `/registration-applications/${applicationId}/precheck-report`,
    ),
  downloadPrecheckReport: (applicationId: string) =>
    downloadRequest(
      `/registration-applications/${applicationId}/precheck-report.pdf`,
    ),
  updateFinding: (
    findingId: string,
    payload: {
      status: FindingRemediationStatus;
      assignee?: string;
      note?: string;
      updated_by: string;
    },
  ) =>
    request<PrecheckFinding>(
      `/precheck-findings/${findingId}/remediation`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
    ),
};

export const agentApi = {
  runtime: () => request<AgentRuntimeStatus>("/agent/runtime"),
  listRuns: (applicationId: string) =>
    request<AgentDraftRunList>(
      `/agent-runs?application_id=${encodeURIComponent(applicationId)}`,
    ),
  createRun: (
    applicationId: string,
    payload: {
      target_section: import("../types").DraftSection;
      language_mode: import("../types").DraftLanguageMode;
      requested_by: string;
    },
  ) =>
    request<AgentDraftRun>(
      `/registration-applications/${applicationId}/agent-runs`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  reviewRun: (
    runId: string,
    payload: {
      decision: "approved" | "rejected";
      reviewed_by: string;
      note: string;
    },
  ) =>
    request<AgentDraftRun>(`/agent-runs/${runId}/review`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export const evaluationApi = {
  dataset: () => request<EvaluationDatasetSummary>("/evaluation/dataset"),
  cases: (taskType?: import("../types").EvaluationTaskType) =>
    request<EvaluationCaseList>(
      `/evaluation/cases?limit=20${taskType ? `&task_type=${taskType}` : ""}`,
    ),
  listRuns: () => request<EvaluationRunList>("/evaluation/runs"),
  createRun: () =>
    request<EvaluationRun>("/evaluation/runs", {
      method: "POST",
      body: JSON.stringify({ requested_by: "刘凯旗" }),
    }),
};

export const securityApi = {
  workspace: () => request<SecurityWorkspace>("/security/workspace"),
  auditEvents: (action?: string) =>
    request<AuditEventList>(
      `/audit-events?limit=100${action ? `&action=${encodeURIComponent(action)}` : ""}`,
    ),
};

export const regulationsApi = {
  list: (asOf: string) =>
    request<RegulationSourceList>(`/regulation-sources?as_of=${encodeURIComponent(asOf)}`),
  create: (payload: RegulationSourceCreate) =>
    request<RegulationSource>("/regulation-sources", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  addVersion: (
    sourceId: string,
    payload: RegulationVersionCreate,
    asOf: string,
  ) =>
    request<RegulationSource>(
      `/regulation-sources/${sourceId}/versions?as_of=${encodeURIComponent(asOf)}`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  reviewVersion: (
    sourceId: string,
    versionId: string,
    payload: { decision: "verified" | "rejected"; reviewed_by: string; note: string },
    asOf: string,
  ) =>
    request<RegulationSource>(
      `/regulation-sources/${sourceId}/versions/${versionId}/review?as_of=${encodeURIComponent(asOf)}`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  getGraph: (sourceId: string) =>
    request<KnowledgeGraphProjection>(`/regulation-sources/${sourceId}/graph`),
  syncGraph: (sourceId: string) =>
    request<KnowledgeGraphSyncResult>(
      `/regulation-sources/${sourceId}/graph/sync`,
      { method: "POST" },
    ),
};

export const documentsApi = {
  list: (versionId: string) =>
    request<RegulationDocumentList>(`/regulation-versions/${versionId}/documents`),
  upload: (versionId: string, file: File, uploadedBy: string) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("uploaded_by", uploadedBy);
    return uploadRequest<RegulationDocument>(
      `/regulation-versions/${versionId}/documents`,
      formData,
    );
  },
  parse: (documentId: string) =>
    request<RegulationDocument>(`/documents/${documentId}/parse`, { method: "POST" }),
  getStructure: (documentId: string) =>
    request<DocumentStructure>(`/documents/${documentId}/structure`),
  listFetchRequests: (versionId: string) =>
    request<DocumentFetchRequestList>(
      `/regulation-versions/${versionId}/fetch-requests`,
    ),
  createFetchRequest: (versionId: string, officialUrl: string) =>
    request<DocumentFetchRequest>(
      `/regulation-versions/${versionId}/fetch-requests`,
      {
        method: "POST",
        body: JSON.stringify({
          official_url: officialUrl,
          requested_by: "刘凯旗",
          reason: "归档监管机构公开原文并纳入合规知识库",
        }),
      },
    ),
  reviewFetchRequest: (
    requestId: string,
    decision: "approved" | "rejected",
  ) =>
    request<DocumentFetchRequest>(
      `/document-fetch-requests/${requestId}/review`,
      {
        method: "POST",
        body: JSON.stringify({
          decision,
          reviewed_by: "法规负责人",
          note:
            decision === "approved"
              ? "已核验来源域名与法规版本，批准受控抓取"
              : "来源或版本信息不符合本次归档要求",
        }),
      },
    ),
  retryFetchRequest: (requestId: string) =>
    request<DocumentFetchRequest>(
      `/document-fetch-requests/${requestId}/retry`,
      { method: "POST" },
    ),
};

export const retrievalApi = {
  getIndex: (documentId: string) =>
    request<VectorIndex>(`/retrieval/documents/${documentId}/index`),
  index: (documentId: string, force = false) =>
    request<VectorIndex>(
      `/retrieval/documents/${documentId}/index?force=${force}`,
      { method: "POST" },
    ),
  search: (query: string, limit = 6) =>
    request<HybridSearchResponse>("/retrieval/search", {
      method: "POST",
      body: JSON.stringify({ query, limit, rerank: true }),
    }),
};
