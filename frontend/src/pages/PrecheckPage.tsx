import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Download,
  FileCheck2,
  FileText,
  FileWarning,
  GitCompareArrows,
  LoaderCircle,
  LockKeyhole,
  MinusCircle,
  Play,
  RotateCcw,
  ShieldCheck,
  Upload,
  X,
} from "lucide-react";
import { applicationsApi } from "../api/client";
import type {
  ConsistencyStatus,
  DossierCategory,
  DossierConsistencyReport,
  EvidenceMatrix,
  FindingRemediationStatus,
  InternalPrecheckReport,
  PrecheckFinding,
  RequirementStatus,
} from "../types";

const REQUIREMENT_LABELS: Record<RequirementStatus, string> = {
  missing: "待上传",
  uploaded: "待审核",
  needs_review: "需整改",
  accepted: "已接受",
  not_applicable: "不适用",
};

const REMEDIATION_LABELS: Record<FindingRemediationStatus, string> = {
  open: "待处理",
  in_progress: "整改中",
  resolved: "已处理",
  waived: "已豁免",
};

const CONSISTENCY_LABELS: Record<ConsistencyStatus, string> = {
  pass: "一致",
  mismatch: "存在冲突",
  insufficient: "样本不足",
};

function formatDateTime(value: string | null) {
  if (!value) return "尚未执行";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatBytes(value: number) {
  if (value < 1024) return value + " B";
  if (value < 1024 * 1024) return (value / 1024).toFixed(1) + " KB";
  return (value / 1024 / 1024).toFixed(1) + " MB";
}

interface ResolutionDialogProps {
  finding: PrecheckFinding;
  isPending: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (note: string) => void;
}

function ResolutionDialog({
  finding,
  isPending,
  error,
  onClose,
  onSubmit,
}: ResolutionDialogProps) {
  const [note, setNote] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (note.trim()) onSubmit(note.trim());
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="create-dialog resolution-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="resolution-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="dialog-header">
          <div>
            <span className="eyebrow">整改结论</span>
            <h2 id="resolution-title">标记问题已处理</h2>
            <p>{finding.title}</p>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="关闭整改结论"
            title="关闭"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </div>
        <form onSubmit={submit}>
          <label className="field field-wide">
            <span>处理说明</span>
            <textarea
              value={note}
              rows={5}
              maxLength={1000}
              placeholder="说明补充了哪些资料、完成了哪些复核，以及仍需关注的事项"
              onChange={(event) => setNote(event.target.value)}
              autoFocus
            />
            <small>{note.length} / 1000</small>
          </label>
          {error && (
            <div className="inline-error" role="alert">
              <AlertCircle size={15} />
              <span>{error}</span>
            </div>
          )}
          <div className="dialog-actions">
            <button className="button secondary" type="button" onClick={onClose}>
              取消
            </button>
            <button
              className="button primary"
              type="submit"
              disabled={isPending || !note.trim()}
            >
              {isPending ? (
                <LoaderCircle className="spin" size={15} />
              ) : (
                <CheckCircle2 size={15} />
              )}
              确认已处理
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export function PrecheckPage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState("");
  const [busyCategory, setBusyCategory] = useState<DossierCategory | null>(null);
  const [resolutionFinding, setResolutionFinding] =
    useState<PrecheckFinding | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const applications = useQuery({
    queryKey: ["registration-applications"],
    queryFn: applicationsApi.list,
  });

  useEffect(() => {
    const firstId = applications.data?.items[0]?.id;
    if (!selectedId && firstId) setSelectedId(firstId);
  }, [applications.data, selectedId]);

  const matrix = useQuery({
    queryKey: ["evidence-matrix", selectedId],
    queryFn: () => applicationsApi.getEvidenceMatrix(selectedId),
    enabled: Boolean(selectedId),
  });

  const consistency = useQuery({
    queryKey: ["consistency-report", selectedId],
    queryFn: () => applicationsApi.getConsistencyReport(selectedId),
    enabled: Boolean(selectedId),
  });

  const precheckReport = useQuery({
    queryKey: [
      "precheck-report",
      selectedId,
      matrix.data?.latest_precheck_id,
    ],
    queryFn: () => applicationsApi.getPrecheckReport(selectedId),
    enabled: Boolean(selectedId && matrix.data?.latest_precheck_id),
  });

  async function refreshWorkspace() {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: ["evidence-matrix", selectedId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["registration-applications"],
      }),
      queryClient.invalidateQueries({
        queryKey: ["registration-prechecks", selectedId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["consistency-report", selectedId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["precheck-report", selectedId],
      }),
    ]);
  }

  const runPrecheck = useMutation({
    mutationFn: () => applicationsApi.runPrecheck(selectedId),
    onMutate: () => setActionError(null),
    onSuccess: refreshWorkspace,
    onError: (error) => setActionError(error.message),
  });

  const uploadEvidence = useMutation({
    mutationFn: ({
      categoryKey,
      file,
    }: {
      categoryKey: DossierCategory;
      file: File;
    }) =>
      applicationsApi.uploadEvidence(
        selectedId,
        categoryKey,
        file,
        "刘凯旗",
      ),
    onMutate: ({ categoryKey }) => {
      setBusyCategory(categoryKey);
      setActionError(null);
    },
    onSuccess: refreshWorkspace,
    onError: (error) => setActionError(error.message),
    onSettled: () => setBusyCategory(null),
  });

  const reviewRequirement = useMutation({
    mutationFn: ({
      categoryKey,
      decision,
    }: {
      categoryKey: DossierCategory;
      decision: "accepted" | "needs_review";
    }) =>
      applicationsApi.reviewRequirement(selectedId, categoryKey, decision),
    onMutate: ({ categoryKey }) => {
      setBusyCategory(categoryKey);
      setActionError(null);
    },
    onSuccess: refreshWorkspace,
    onError: (error) => setActionError(error.message),
    onSettled: () => setBusyCategory(null),
  });

  const updateFinding = useMutation({
    mutationFn: ({
      finding,
      status,
      note,
    }: {
      finding: PrecheckFinding;
      status: FindingRemediationStatus;
      note?: string;
    }) =>
      applicationsApi.updateFinding(finding.id, {
        status,
        assignee: status === "open" ? undefined : "刘凯旗",
        note,
        updated_by: "刘凯旗",
      }),
    onMutate: () => setActionError(null),
    onSuccess: async () => {
      setResolutionFinding(null);
      await refreshWorkspace();
    },
    onError: (error) => setActionError(error.message),
  });

  const downloadReport = useMutation({
    mutationFn: () => applicationsApi.downloadPrecheckReport(selectedId),
    onMutate: () => setActionError(null),
    onError: (error) => setActionError(error.message),
  });

  const selectedApplication = applications.data?.items.find(
    (item) => item.id === selectedId,
  );

  return (
    <div className="page precheck-page">
      <div className="page-header">
        <div>
          <span className="eyebrow">证据覆盖与问题闭环</span>
          <h1>资料预审</h1>
          <p>围绕法定资料类别组织证据、审核结论和整改责任。</p>
        </div>
        <button
          className="button primary"
          type="button"
          disabled={!selectedId || runPrecheck.isPending}
          onClick={() => runPrecheck.mutate()}
        >
          {runPrecheck.isPending ? (
            <LoaderCircle className="spin" size={16} />
          ) : (
            <Play size={16} />
          )}
          执行新一轮预审
        </button>
      </div>

      <section className="precheck-project-bar">
        <label className="project-select-field">
          <span>申报项目</span>
          <select
            aria-label="选择预审项目"
            value={selectedId}
            onChange={(event) => {
              setSelectedId(event.target.value);
              setActionError(null);
            }}
          >
            {(applications.data?.items ?? []).map((application) => (
              <option value={application.id} key={application.id}>
                {application.code} · {application.name}
              </option>
            ))}
          </select>
        </label>
        {selectedApplication && (
          <div className="project-context">
            <span>{selectedApplication.product_name}</span>
            <span>境内 {selectedApplication.device_class} 类</span>
            <span>法规基准 {selectedApplication.regulation_effective_on}</span>
          </div>
        )}
      </section>

      {actionError && (
        <div className="inline-error workspace-error" role="alert">
          <AlertCircle size={16} />
          <span>{actionError}</span>
        </div>
      )}

      {applications.isLoading && (
        <div className="state-message">正在读取申报项目…</div>
      )}
      {!applications.isLoading && applications.data?.total === 0 && (
        <div className="empty-state large-empty">
          <FileWarning size={26} />
          <div>
            <strong>还没有可预审的申报项目</strong>
            <span>先在申报项目页面建立产品资料基线。</span>
          </div>
        </div>
      )}
      {matrix.isLoading && selectedId && (
        <div className="state-message">正在生成证据矩阵…</div>
      )}
      {matrix.isError && (
        <div className="state-message error-state">
          <AlertCircle size={19} />
          <div>
            <strong>证据矩阵读取失败</strong>
            <span>{matrix.error.message}</span>
          </div>
        </div>
      )}
      {matrix.data && (
        <EvidenceMatrixWorkspace
          matrix={matrix.data}
          consistency={consistency.data ?? null}
          consistencyLoading={consistency.isLoading}
          consistencyError={consistency.error?.message ?? null}
          report={precheckReport.data ?? null}
          reportLoading={precheckReport.isLoading}
          reportError={precheckReport.error?.message ?? null}
          isReportDownloading={downloadReport.isPending}
          onDownloadReport={() => downloadReport.mutate()}
          busyCategory={busyCategory}
          isFindingPending={updateFinding.isPending}
          onUpload={(categoryKey, file) =>
            uploadEvidence.mutate({ categoryKey, file })
          }
          onReview={(categoryKey, decision) =>
            reviewRequirement.mutate({ categoryKey, decision })
          }
          onStart={(finding) =>
            updateFinding.mutate({ finding, status: "in_progress" })
          }
          onResolve={setResolutionFinding}
          onReopen={(finding) =>
            updateFinding.mutate({
              finding,
              status: "open",
              note: "复核后重新打开问题。",
            })
          }
        />
      )}

      {resolutionFinding && (
        <ResolutionDialog
          finding={resolutionFinding}
          isPending={updateFinding.isPending}
          error={updateFinding.error?.message ?? null}
          onClose={() => {
            setResolutionFinding(null);
            updateFinding.reset();
          }}
          onSubmit={(note) =>
            updateFinding.mutate({
              finding: resolutionFinding,
              status: "resolved",
              note,
            })
          }
        />
      )}
    </div>
  );
}

interface ConsistencyWorkspaceProps {
  report: DossierConsistencyReport | null;
  isLoading: boolean;
  error: string | null;
}

function ConsistencyWorkspace({
  report,
  isLoading,
  error,
}: ConsistencyWorkspaceProps) {
  return (
    <section className="data-section consistency-section">
      <div className="section-heading matrix-heading">
        <div>
          <span className="eyebrow">结构化字段比对</span>
          <h2>跨文档一致性</h2>
        </div>
        {report && (
          <span className="result-count">
            {report.pass_count} 通过 · {report.mismatch_count} 冲突
          </span>
        )}
      </div>

      {isLoading && (
        <div className="consistency-state">
          <LoaderCircle className="spin" size={16} />
          正在提取可比字段…
        </div>
      )}
      {error && (
        <div className="consistency-state error-state">
          <AlertCircle size={16} />
          {error}
        </div>
      )}
      {report && (
        <>
          <div className="consistency-metrics">
            <div>
              <span>检查字段</span>
              <strong>{report.check_count}</strong>
            </div>
            <div className="passed">
              <span>一致</span>
              <strong>{report.pass_count}</strong>
            </div>
            <div className="mismatch">
              <span>冲突</span>
              <strong>{report.mismatch_count}</strong>
            </div>
            <div>
              <span>样本不足</span>
              <strong>{report.insufficient_count}</strong>
            </div>
          </div>

          {report.unreadable_evidence.length > 0 && (
            <div className="consistency-unreadable">
              <FileWarning size={16} />
              <span>
                {report.unreadable_evidence.map((item) => item.file_name).join("、")}
                无法提取文本
              </span>
            </div>
          )}

          <div className="consistency-table-scroll">
            <table className="consistency-table">
              <thead>
                <tr>
                  <th>检查字段</th>
                  <th>判定</th>
                  <th>来源表述</th>
                  <th>结果说明</th>
                </tr>
              </thead>
              <tbody>
                {report.checks.map((check) => (
                  <tr key={check.field}>
                    <td className="consistency-field">
                      <GitCompareArrows size={15} />
                      <strong>{check.label}</strong>
                      <small>{check.occurrence_count} 个取值</small>
                    </td>
                    <td>
                      <span className={"consistency-status " + check.status}>
                        {check.status === "pass" && <CheckCircle2 size={13} />}
                        {check.status === "mismatch" && (
                          <AlertTriangle size={13} />
                        )}
                        {check.status === "insufficient" && (
                          <MinusCircle size={13} />
                        )}
                        {CONSISTENCY_LABELS[check.status]}
                      </span>
                    </td>
                    <td>
                      {check.occurrences.length > 0 ? (
                        <div className="consistency-values">
                          {check.occurrences.slice(0, 3).map((occurrence, index) => (
                            <div
                              key={`${occurrence.source_label}-${index}`}
                              title={occurrence.value}
                            >
                              <span>{occurrence.source_label}</span>
                              <strong>{occurrence.value}</strong>
                            </div>
                          ))}
                          {check.occurrences.length > 3 && (
                            <small>另有 {check.occurrences.length - 3} 个来源</small>
                          )}
                        </div>
                      ) : (
                        <span className="matrix-empty-value">未提取到字段</span>
                      )}
                    </td>
                    <td className="consistency-message">
                      <span>{check.message}</span>
                      <small>判定阈值 {Math.round(check.threshold * 100)}%</small>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="consistency-foot">
            <span>解析器 {report.parser_version}</span>
            <span>生成于 {formatDateTime(report.generated_at)}</span>
          </div>
        </>
      )}
    </section>
  );
}

interface InternalReportWorkspaceProps {
  report: InternalPrecheckReport | null;
  isLoading: boolean;
  error: string | null;
  isDownloading: boolean;
  onDownload: () => void;
}

function InternalReportWorkspace({
  report,
  isLoading,
  error,
  isDownloading,
  onDownload,
}: InternalReportWorkspaceProps) {
  const closedFindingCount = report
    ? report.precheck.findings.length - report.open_finding_count
    : 0;

  return (
    <section className="data-section internal-report-section">
      <div className="section-heading matrix-heading report-heading">
        <div>
          <span className="eyebrow">受控快照与审计追踪</span>
          <h2>内部预审报告</h2>
        </div>
        <button
          className="button secondary"
          type="button"
          disabled={!report || report.is_stale || isDownloading}
          title={report?.is_stale ? "重新执行预审后方可导出" : "下载 PDF 报告"}
          onClick={onDownload}
        >
          {isDownloading ? (
            <LoaderCircle className="spin" size={15} />
          ) : (
            <Download size={15} />
          )}
          导出 PDF
        </button>
      </div>

      {isLoading && (
        <div className="report-empty-state">
          <LoaderCircle className="spin" size={17} />
          正在聚合报告快照…
        </div>
      )}
      {error && (
        <div className="report-empty-state error-state">
          <AlertCircle size={17} />
          {error}
        </div>
      )}
      {!isLoading && !error && !report && (
        <div className="report-empty-state">
          <FileText size={17} />
          执行预审后生成受控报告。
        </div>
      )}
      {report && (
        <>
          {report.is_stale && (
            <div className="report-stale-callout">
              <AlertTriangle size={16} />
              <span>{report.stale_reason}</span>
            </div>
          )}
          <div className="report-summary-band">
            <div className="report-code-cell">
              <span>报告编号</span>
              <strong>{report.report_code}</strong>
            </div>
            <div>
              <span>证据指纹</span>
              <strong>{report.evidence_count}</strong>
            </div>
            <div>
              <span>一致性冲突</span>
              <strong>{report.consistency.mismatch_count}</strong>
            </div>
            <div>
              <span>整改闭环</span>
              <strong>
                {closedFindingCount}/{report.precheck.findings.length}
              </strong>
            </div>
            <div>
              <span>报告状态</span>
              <strong className={report.is_stale ? "stale" : "current"}>
                {report.is_stale ? "已过期" : "有效"}
              </strong>
            </div>
          </div>

          <div className="report-audit-grid">
            <div>
              <LockKeyhole size={15} />
              <span>预审运行 ID</span>
              <strong>{report.precheck.id}</strong>
            </div>
            <div>
              <FileText size={15} />
              <span>规则集</span>
              <strong>{report.precheck.rule_set_version}</strong>
            </div>
            <div>
              <span>生成责任人</span>
              <strong>{report.generated_by}</strong>
              <small>{formatDateTime(report.generated_at)}</small>
            </div>
          </div>

          <div className="report-fingerprint-list">
            <div className="report-fingerprint-head">
              <span>证据文件</span>
              <span>资料类别</span>
              <span>SHA-256</span>
            </div>
            {report.evidence_manifest.map((evidence) => (
              <div key={evidence.evidence_id}>
                <strong title={evidence.file_name}>{evidence.file_name}</strong>
                <span>{evidence.category_title}</span>
                <code title={evidence.sha256}>{evidence.sha256}</code>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

interface EvidenceMatrixWorkspaceProps {
  matrix: EvidenceMatrix;
  consistency: DossierConsistencyReport | null;
  consistencyLoading: boolean;
  consistencyError: string | null;
  report: InternalPrecheckReport | null;
  reportLoading: boolean;
  reportError: string | null;
  isReportDownloading: boolean;
  onDownloadReport: () => void;
  busyCategory: DossierCategory | null;
  isFindingPending: boolean;
  onUpload: (categoryKey: DossierCategory, file: File) => void;
  onReview: (
    categoryKey: DossierCategory,
    decision: "accepted" | "needs_review",
  ) => void;
  onStart: (finding: PrecheckFinding) => void;
  onResolve: (finding: PrecheckFinding) => void;
  onReopen: (finding: PrecheckFinding) => void;
}

function EvidenceMatrixWorkspace({
  matrix,
  consistency,
  consistencyLoading,
  consistencyError,
  report,
  reportLoading,
  reportError,
  isReportDownloading,
  onDownloadReport,
  busyCategory,
  isFindingPending,
  onUpload,
  onReview,
  onStart,
  onResolve,
  onReopen,
}: EvidenceMatrixWorkspaceProps) {
  const evidenceTotal = matrix.rows.reduce(
    (total, row) => total + row.evidence_count,
    0,
  );

  return (
    <>
      <section className="matrix-summary-band">
        <div>
          <span>资料完成率</span>
          <strong>{matrix.completion_rate.toFixed(1)}%</strong>
        </div>
        <div>
          <span>已归档证据</span>
          <strong>{evidenceTotal}</strong>
        </div>
        <div className="danger-metric">
          <span>阻断项</span>
          <strong>{matrix.blocker_count}</strong>
        </div>
        <div className="warning-metric">
          <span>警告项</span>
          <strong>{matrix.warning_count}</strong>
        </div>
        <div>
          <span>待整改</span>
          <strong>{matrix.open_finding_count}</strong>
        </div>
        <small>最近预审：{formatDateTime(matrix.latest_precheck_at)}</small>
      </section>

      <ConsistencyWorkspace
        report={consistency}
        isLoading={consistencyLoading}
        error={consistencyError}
      />

      <InternalReportWorkspace
        report={report}
        isLoading={reportLoading}
        error={reportError}
        isDownloading={isReportDownloading}
        onDownload={onDownloadReport}
      />

      <section className="data-section evidence-matrix-section">
        <div className="section-heading matrix-heading">
          <div>
            <span className="eyebrow">最新预审快照</span>
            <h2>证据矩阵</h2>
          </div>
          <span className="result-count">{matrix.rows.length} 类资料</span>
        </div>

        {!matrix.latest_precheck_id && (
          <div className="matrix-callout">
            <ShieldCheck size={17} />
            <span>当前尚无预审快照，执行预审后会生成问题和整改任务。</span>
          </div>
        )}

        <div className="matrix-table-scroll">
          <table className="matrix-table">
            <thead>
              <tr>
                <th>资料类别</th>
                <th>归档证据</th>
                <th>人工审核</th>
                <th>最新问题</th>
                <th>整改状态</th>
              </tr>
            </thead>
            <tbody>
              {matrix.rows.map((row) => {
                const findings = row.findings;
                const busy = busyCategory === row.category_key;
                return (
                  <tr key={row.category_key} data-category={row.category_key}>
                    <td className="matrix-category">
                      <strong>{row.title}</strong>
                      <small>{row.regulatory_basis}</small>
                    </td>
                    <td>
                      <div className="matrix-evidence-cell">
                        {row.evidence.length > 0 ? (
                          <div className="evidence-file-list">
                            {row.evidence.slice(0, 2).map((evidence) => (
                              <span title={evidence.file_name} key={evidence.id}>
                                <FileCheck2 size={12} />
                                {evidence.file_name}
                                <small>{formatBytes(evidence.size_bytes)}</small>
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="matrix-empty-value">尚无文件</span>
                        )}
                        <label
                          className={
                            "icon-button subtle matrix-upload" +
                            (busy ? " disabled" : "")
                          }
                          title={"上传" + row.title}
                        >
                          {busy ? (
                            <LoaderCircle className="spin" size={14} />
                          ) : (
                            <Upload size={14} />
                          )}
                          <input
                            type="file"
                            aria-label={"上传" + row.title}
                            accept=".pdf,.docx,.txt,.md,.html,.htm"
                            disabled={busy}
                            onChange={(event) => {
                              const file = event.target.files?.[0];
                              if (file) onUpload(row.category_key, file);
                              event.target.value = "";
                            }}
                          />
                        </label>
                      </div>
                    </td>
                    <td>
                      <div className="matrix-review-cell">
                        <span
                          className={
                            "matrix-status requirement-" + row.requirement_status
                          }
                        >
                          {REQUIREMENT_LABELS[row.requirement_status]}
                        </span>
                        {row.evidence_count > 0 &&
                          row.requirement_status !== "accepted" && (
                            <button
                              className="icon-button subtle"
                              type="button"
                              title="接受资料"
                              aria-label={"接受" + row.title}
                              disabled={busy}
                              onClick={() =>
                                onReview(row.category_key, "accepted")
                              }
                            >
                              <CheckCircle2 size={14} />
                            </button>
                          )}
                        {row.requirement_status === "accepted" && (
                          <button
                            className="icon-button subtle"
                            type="button"
                            title="退回整改"
                            aria-label={"退回" + row.title}
                            disabled={busy}
                            onClick={() =>
                              onReview(row.category_key, "needs_review")
                            }
                          >
                            <RotateCcw size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="matrix-finding-cell">
                      {findings.length > 0 ? (
                        <div className="matrix-finding-list">
                          {findings.map((finding) => (
                            <div className="matrix-finding-item" key={finding.id}>
                              <span
                                className={"finding-severity " + finding.severity}
                              >
                                {finding.severity === "blocker" ? "阻断" : "警告"}
                              </span>
                              <strong>{finding.title}</strong>
                              <small>{finding.remediation}</small>
                            </div>
                          ))}
                        </div>
                      ) : matrix.latest_precheck_id ? (
                        <span className="matrix-pass">
                          <CheckCircle2 size={13} />
                          本轮通过
                        </span>
                      ) : (
                        <span className="matrix-empty-value">等待预审</span>
                      )}
                    </td>
                    <td>
                      {findings.length > 0 ? (
                        <div className="remediation-list">
                          {findings.map((finding) => (
                            <div className="remediation-item" key={finding.id}>
                              <div className="remediation-cell">
                                <span
                                  className={
                                    "remediation-status " +
                                    finding.remediation_status
                                  }
                                >
                                  {REMEDIATION_LABELS[finding.remediation_status]}
                                </span>
                                {finding.assignee && <small>{finding.assignee}</small>}
                              </div>
                              {finding.remediation_status === "open" && (
                                <button
                                  className="button secondary compact-button"
                                  type="button"
                                  disabled={isFindingPending}
                                  onClick={() => onStart(finding)}
                                >
                                  开始整改
                                </button>
                              )}
                              {finding.remediation_status === "in_progress" && (
                                <button
                                  className="button secondary compact-button"
                                  type="button"
                                  disabled={isFindingPending}
                                  onClick={() => onResolve(finding)}
                                >
                                  标记已处理
                                </button>
                              )}
                              {finding.remediation_status === "resolved" && (
                                <button
                                  className="icon-button subtle"
                                  type="button"
                                  title="重新打开"
                                  aria-label={"重新打开" + finding.title}
                                  disabled={isFindingPending}
                                  onClick={() => onReopen(finding)}
                                >
                                  <RotateCcw size={14} />
                                </button>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <span className="matrix-empty-value">无需整改</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
