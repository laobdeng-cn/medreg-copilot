import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  FileWarning,
  LoaderCircle,
  RotateCcw,
  ShieldCheck,
  Upload,
  X,
} from "lucide-react";
import { applicationsApi } from "../api/client";
import type {
  DossierCategory,
  RegistrationApplication,
  RequirementStatus,
} from "../types";

interface ApplicationDetailProps {
  application: RegistrationApplication;
  onClose: () => void;
  onUpdated: (application: RegistrationApplication) => void;
}

const REQUIREMENT_STATUS_LABELS: Record<RequirementStatus, string> = {
  missing: "待上传",
  uploaded: "待审核",
  needs_review: "需整改",
  accepted: "已接受",
  not_applicable: "不适用",
};

function formatRunTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function ApplicationDetail({
  application,
  onClose,
  onUpdated,
}: ApplicationDetailProps) {
  const [busyCategory, setBusyCategory] = useState<DossierCategory | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const prechecks = useQuery({
    queryKey: ["registration-prechecks", application.id],
    queryFn: () => applicationsApi.listPrechecks(application.id),
  });

  async function refreshApplication() {
    const updated = await applicationsApi.get(application.id);
    onUpdated(updated);
  }

  const uploadEvidence = useMutation({
    mutationFn: ({
      categoryKey,
      file,
    }: {
      categoryKey: DossierCategory;
      file: File;
    }) =>
      applicationsApi.uploadEvidence(
        application.id,
        categoryKey,
        file,
        "刘凯旗",
      ),
    onMutate: ({ categoryKey }) => {
      setBusyCategory(categoryKey);
      setActionError(null);
    },
    onSuccess: refreshApplication,
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
      applicationsApi.reviewRequirement(
        application.id,
        categoryKey,
        decision,
      ),
    onMutate: ({ categoryKey }) => {
      setBusyCategory(categoryKey);
      setActionError(null);
    },
    onSuccess: onUpdated,
    onError: (error) => setActionError(error.message),
    onSettled: () => setBusyCategory(null),
  });

  const runPrecheck = useMutation({
    mutationFn: () => applicationsApi.runPrecheck(application.id),
    onMutate: () => setActionError(null),
    onSuccess: async () => {
      await Promise.all([prechecks.refetch(), refreshApplication()]);
    },
    onError: (error) => setActionError(error.message),
  });

  const latestRun = prechecks.data?.items[0];
  const acceptedCount = application.requirements.filter(
    (item) => item.status === "accepted",
  ).length;

  return (
    <div className="drawer-backdrop" role="presentation" onMouseDown={onClose}>
      <aside
        className="detail-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="detail-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="drawer-header">
          <div>
            <span className="eyebrow">{application.code}</span>
            <h2 id="detail-title">{application.name}</h2>
            <p>{application.product_name}</p>
          </div>
          <button
            className="icon-button"
            type="button"
            title="关闭"
            aria-label="关闭项目详情"
            onClick={onClose}
          >
            <X size={19} />
          </button>
        </div>

        <dl className="detail-facts">
          <div>
            <dt>注册申请人</dt>
            <dd>{application.applicant_name}</dd>
          </div>
          <div>
            <dt>管理类别</dt>
            <dd>境内 {application.device_class} 类</dd>
          </div>
          <div>
            <dt>法规基准日期</dt>
            <dd>{application.regulation_effective_on}</dd>
          </div>
          <div>
            <dt>资料完成率</dt>
            <dd>{application.completion_rate.toFixed(1)}%</dd>
          </div>
        </dl>

        <section className="precheck-section">
          <div className="section-heading compact-heading">
            <div>
              <span className="eyebrow">确定性规则集</span>
              <h3>资料完整性预审</h3>
            </div>
            <button
              className="button primary compact-button"
              type="button"
              disabled={runPrecheck.isPending}
              onClick={() => runPrecheck.mutate()}
            >
              {runPrecheck.isPending ? (
                <LoaderCircle className="spin" size={15} />
              ) : (
                <ShieldCheck size={15} />
              )}
              执行预审
            </button>
          </div>

          {prechecks.isLoading && (
            <div className="precheck-empty">正在读取预审记录…</div>
          )}
          {!prechecks.isLoading && !latestRun && (
            <div className="precheck-empty">
              上传资料并完成审核后执行预审，系统会保留每一次问题快照。
            </div>
          )}
          {latestRun && (
            <>
              <div className="precheck-summary">
                <div className="blocker">
                  <strong>{latestRun.blocker_count}</strong>
                  <span>阻断项</span>
                </div>
                <div className="warning">
                  <strong>{latestRun.warning_count}</strong>
                  <span>警告项</span>
                </div>
                <div className="passed">
                  <strong>{latestRun.pass_count}</strong>
                  <span>已通过</span>
                </div>
                <small>
                  {formatRunTime(latestRun.completed_at)} · {latestRun.initiated_by}
                </small>
              </div>
              {latestRun.findings.length > 0 ? (
                <div className="finding-list">
                  {latestRun.findings.map((finding) => (
                    <article
                      className={"finding-row " + finding.severity}
                      key={finding.id}
                    >
                      <div className="finding-heading">
                        <span>
                          {finding.severity === "blocker" ? "阻断" : "警告"}
                        </span>
                        <strong>{finding.title}</strong>
                      </div>
                      <p>{finding.description}</p>
                      <small>{finding.regulatory_basis}</small>
                      <div className="finding-remediation">
                        <b>整改：</b>{finding.remediation}
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="precheck-passed">
                  <CheckCircle2 size={18} />
                  <span>七类法定资料均已归档并完成审核。</span>
                </div>
              )}
            </>
          )}
        </section>

        <section className="requirements-section">
          <div className="section-heading compact-heading">
            <div>
              <span className="eyebrow">法定资料类别</span>
              <h3>申报资料清单</h3>
            </div>
            <span className="requirement-count">
              {acceptedCount} / {application.requirements.length}
            </span>
          </div>

          {actionError && (
            <div className="inline-error" role="alert">
              <AlertCircle size={15} />
              <span>{actionError}</span>
            </div>
          )}

          <div className="requirement-list">
            {application.requirements.map((requirement, index) => {
              const complete = requirement.status === "accepted";
              const busy = busyCategory === requirement.key;
              return (
                <article
                  key={requirement.key}
                  className="requirement-row"
                  data-category={requirement.key}
                >
                  <div
                    className={
                      "requirement-icon " + (complete ? "complete" : "missing")
                    }
                  >
                    {complete ? (
                      <CheckCircle2 size={18} aria-hidden="true" />
                    ) : (
                      <FileWarning size={18} aria-hidden="true" />
                    )}
                  </div>
                  <div>
                    <div className="requirement-title">
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      <strong>{requirement.title}</strong>
                      <span
                        className={
                          "requirement-status status-" + requirement.status
                        }
                      >
                        {REQUIREMENT_STATUS_LABELS[requirement.status]}
                      </span>
                    </div>
                    <p>{requirement.description}</p>
                    <small>{requirement.regulatory_basis}</small>
                    <div className="requirement-meta">
                      <span>{requirement.evidence_count} 份证据</span>
                      <div className="requirement-actions">
                        <label
                          className={
                            "button secondary compact-button upload-action" +
                            (busy ? " disabled" : "")
                          }
                          title="上传该类别的申报资料"
                        >
                          {busy && uploadEvidence.isPending ? (
                            <LoaderCircle className="spin" size={13} />
                          ) : (
                            <Upload size={13} />
                          )}
                          上传
                          <input
                            type="file"
                            aria-label={"上传" + requirement.title}
                            accept=".pdf,.docx,.txt,.md,.html,.htm"
                            disabled={busy}
                            onChange={(event) => {
                              const file = event.target.files?.[0];
                              if (file) {
                                uploadEvidence.mutate({
                                  categoryKey: requirement.key,
                                  file,
                                });
                              }
                              event.target.value = "";
                            }}
                          />
                        </label>
                        {requirement.evidence_count > 0 && !complete && (
                          <button
                            className="button secondary compact-button"
                            type="button"
                            disabled={busy}
                            onClick={() =>
                              reviewRequirement.mutate({
                                categoryKey: requirement.key,
                                decision: "accepted",
                              })
                            }
                          >
                            <CheckCircle2 size={13} />
                            接受
                          </button>
                        )}
                        {complete && (
                          <button
                            className="icon-button subtle"
                            type="button"
                            title="退回整改"
                            aria-label={"退回" + requirement.title}
                            disabled={busy}
                            onClick={() =>
                              reviewRequirement.mutate({
                                categoryKey: requirement.key,
                                decision: "needs_review",
                              })
                            }
                          >
                            <RotateCcw size={14} />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        <div className="drawer-note">
          完整性规则只检查资料是否归档并通过人工审核；不替代法规人员对内容真实性、适用性和充分性的专业判断。
        </div>
      </aside>
    </div>
  );
}
