import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Bot,
  Braces,
  CheckCircle2,
  Clock3,
  Database,
  FileText,
  Languages,
  LoaderCircle,
  Play,
  Quote,
  Scissors,
  ShieldCheck,
  Workflow,
  XCircle,
} from "lucide-react";
import { agentApi, applicationsApi } from "../api/client";
import type {
  AgentApprovalStatus,
  AgentDraftRun,
  AgentModelMode,
  DraftLanguageMode,
  DraftSection,
} from "../types";

const SECTION_LABELS: Record<DraftSection, string> = {
  product_overview: "产品概述",
  risk_management_summary: "风险管理摘要",
  technical_requirements_summary: "产品技术要求摘要",
  ifu_label_summary: "说明书与标签一致性摘要",
};

const MODEL_MODE_LABELS: Record<AgentModelMode, string> = {
  live: "DeepSeek 实时生成",
  deterministic: "确定性演示模式",
  fallback: "模型异常，已受控降级",
};

const APPROVAL_LABELS: Record<AgentApprovalStatus, string> = {
  pending: "待人工审批",
  approved: "已批准",
  rejected: "已驳回",
};

const LANGUAGE_LABELS: Record<DraftLanguageMode, string> = {
  zh_cn: "简体中文",
  bilingual: "中英术语受控",
};

const BILINGUAL_STATUS_LABELS = {
  pass: "全部一致",
  missing: "存在缺失",
  mismatch: "存在错译",
  not_applicable: "不适用",
};

function formatDateTime(value: string | null) {
  if (!value) return "尚未审批";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function DraftPreview({ content }: { content: string }) {
  return (
    <div className="agent-draft-content">
      {content.split("\n").map((line, index) => {
        const key = `${index}-${line.slice(0, 12)}`;
        if (line.startsWith("## ")) return <h3 key={key}>{line.slice(3)}</h3>;
        if (line.startsWith("- ")) {
          return (
            <p className="draft-bullet" key={key}>
              {line.slice(2)}
            </p>
          );
        }
        if (!line.trim()) return <span className="draft-space" key={key} />;
        return <p key={key}>{line}</p>;
      })}
    </div>
  );
}

function RunHistoryItem({
  run,
  selected,
  onSelect,
}: {
  run: AgentDraftRun;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      className={`agent-run-item${selected ? " selected" : ""}`}
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
    >
      <span className="agent-run-item-title">{SECTION_LABELS[run.target_section]}</span>
      <span className={`approval-dot ${run.approval_status}`}>
        {APPROVAL_LABELS[run.approval_status]}
      </span>
      <small>{formatDateTime(run.created_at)}</small>
      <code>{LANGUAGE_LABELS[run.language_mode]} · {run.id.slice(0, 8)}</code>
    </button>
  );
}

function GovernanceDetails({ run }: { run: AgentDraftRun }) {
  const context = run.context_report;
  const structured = run.structured_output;
  const bilingual = run.bilingual_report;

  return (
    <div className="agent-governance-grid">
      <section className="agent-governance-section">
        <div className="section-heading compact-heading">
          <div>
            <span className="eyebrow">证据预算</span>
            <h2>上下文压缩</h2>
          </div>
          <Scissors size={18} />
        </div>
        {context ? (
          <>
            <div className="agent-mini-metrics">
              <div>
                <span>原始字符</span>
                <strong>{context.original_chars.toLocaleString()}</strong>
              </div>
              <div>
                <span>入模字符</span>
                <strong>{context.selected_chars.toLocaleString()}</strong>
              </div>
              <div>
                <span>保留比例</span>
                <strong>{Math.round(context.compression_ratio * 100)}%</strong>
              </div>
            </div>
            <div className="agent-context-list">
              {context.segments.map((segment, index) => (
                <div key={`${segment.evidence_id}-${segment.segment_index}`}>
                  <span>项目证据 {index + 1}</span>
                  <strong>{segment.file_name}</strong>
                  <small>
                    字符 {segment.char_start}–{segment.char_end} · 分数 {segment.score.toFixed(2)}
                  </small>
                  <code>{segment.content_hash.slice(0, 12)}</code>
                </div>
              ))}
              {!context.segments.length && (
                <div className="agent-governance-empty">没有可用于编制的已接受项目证据</div>
              )}
            </div>
          </>
        ) : (
          <div className="agent-governance-empty">该历史运行未生成上下文压缩报告</div>
        )}
      </section>

      <section className="agent-governance-section">
        <div className="section-heading compact-heading">
          <div>
            <span className="eyebrow">{bilingual?.glossary_version ?? "术语审计"}</span>
            <h2>中英文一致性</h2>
          </div>
          <Languages size={18} />
        </div>
        {bilingual ? (
          <>
            <div className={`agent-language-summary ${bilingual.status}`}>
              <strong>{BILINGUAL_STATUS_LABELS[bilingual.status]}</strong>
              <span>
                通过 {bilingual.pass_count} · 缺失 {bilingual.missing_count} · 错译{" "}
                {bilingual.mismatch_count}
              </span>
            </div>
            <div className="agent-term-list">
              {bilingual.checks.map((check) => (
                <div key={check.zh}>
                  <span className={`term-status ${check.status}`}>
                    {BILINGUAL_STATUS_LABELS[check.status]}
                  </span>
                  <strong>{check.zh}</strong>
                  <span>{check.actual_en ?? "未输出"}</span>
                </div>
              ))}
              {!bilingual.checks.length && (
                <div className="agent-governance-empty">本次运行无需中英文术语核对</div>
              )}
            </div>
          </>
        ) : (
          <div className="agent-governance-empty">该历史运行未生成中英文一致性报告</div>
        )}
      </section>

      <section className="agent-governance-section agent-claims-section">
        <div className="section-heading compact-heading">
          <div>
            <span className="eyebrow">机器可审计输出</span>
            <h2>结构化事实主张</h2>
          </div>
          <span>{structured?.claims.length ?? 0} 条</span>
        </div>
        {structured ? (
          <div className="agent-claim-list">
            {structured.claims.map((claim, index) => (
              <div key={`${index}-${claim.statement.slice(0, 16)}`}>
                <span>{index + 1}</span>
                <p>{claim.statement}</p>
                <code>{claim.evidence_markers.join(" ") || "无证据标记"}</code>
                <strong>{Math.round(claim.confidence * 100)}%</strong>
              </div>
            ))}
            {!structured.claims.length && (
              <div className="agent-governance-empty">本次输出没有事实主张</div>
            )}
          </div>
        ) : (
          <div className="agent-governance-empty">该历史运行未生成结构化输出</div>
        )}
      </section>
    </div>
  );
}

export function AgentPage() {
  const queryClient = useQueryClient();
  const [selectedApplicationId, setSelectedApplicationId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [targetSection, setTargetSection] =
    useState<DraftSection>("risk_management_summary");
  const [languageMode, setLanguageMode] =
    useState<DraftLanguageMode>("bilingual");
  const [reviewNote, setReviewNote] = useState("");

  const applications = useQuery({
    queryKey: ["registration-applications"],
    queryFn: applicationsApi.list,
  });
  const runtime = useQuery({
    queryKey: ["agent-runtime"],
    queryFn: agentApi.runtime,
  });

  useEffect(() => {
    const first = applications.data?.items[0]?.id;
    if (!selectedApplicationId && first) setSelectedApplicationId(first);
  }, [applications.data, selectedApplicationId]);

  const runs = useQuery({
    queryKey: ["agent-runs", selectedApplicationId],
    queryFn: () => agentApi.listRuns(selectedApplicationId),
    enabled: Boolean(selectedApplicationId),
  });

  useEffect(() => {
    const items = runs.data?.items ?? [];
    if (!items.length) {
      setSelectedRunId("");
      return;
    }
    if (!items.some((item) => item.id === selectedRunId)) {
      setSelectedRunId(items[0].id);
    }
  }, [runs.data, selectedRunId]);

  const createRun = useMutation({
    mutationFn: () =>
      agentApi.createRun(selectedApplicationId, {
        target_section: targetSection,
        language_mode: languageMode,
        requested_by: "刘凯旗",
      }),
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({
        queryKey: ["agent-runs", selectedApplicationId],
      });
      setSelectedRunId(created.id);
      setReviewNote("");
    },
  });

  const reviewRun = useMutation({
    mutationFn: ({
      runId,
      decision,
    }: {
      runId: string;
      decision: "approved" | "rejected";
    }) =>
      agentApi.reviewRun(runId, {
        decision,
        reviewed_by: "法规负责人",
        note: reviewNote.trim(),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["agent-runs", selectedApplicationId],
      });
      setReviewNote("");
    },
  });

  const selectedRun = (runs.data?.items ?? []).find(
    (item) => item.id === selectedRunId,
  );
  const selectedApplication = applications.data?.items.find(
    (item) => item.id === selectedApplicationId,
  );
  const actionError = createRun.error?.message ?? reviewRun.error?.message;

  return (
    <div className="page agent-page">
      <div className="page-header agent-page-header">
        <div>
          <span className="eyebrow">受控证据驱动的人机协同</span>
          <h1>Agent 编制</h1>
          <p>运行可追踪的六节点工作流，形成带法规引用、等待人工决定的内部草稿。</p>
        </div>
        <div className={`agent-runtime ${runtime.data?.configured ? "live" : "demo"}`}>
          <Bot size={17} />
          <div>
            <strong>
              {runtime.data?.configured ? "模型已连接" : "确定性演示模式"}
            </strong>
            <span>{runtime.data?.model ?? "正在读取运行环境"}</span>
          </div>
        </div>
      </div>

      <section className="agent-control-band" aria-label="编制运行控制">
        <label>
          <span>申报项目</span>
          <select
            value={selectedApplicationId}
            onChange={(event) => {
              setSelectedApplicationId(event.target.value);
              setSelectedRunId("");
            }}
          >
            {(applications.data?.items ?? []).map((item) => (
              <option key={item.id} value={item.id}>
                {item.code} · {item.product_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>目标章节</span>
          <select
            value={targetSection}
            onChange={(event) => setTargetSection(event.target.value as DraftSection)}
          >
            {Object.entries(SECTION_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>输出语言</span>
          <select
            value={languageMode}
            onChange={(event) =>
              setLanguageMode(event.target.value as DraftLanguageMode)
            }
          >
            {Object.entries(LANGUAGE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <div className="agent-control-context">
          <span>当前资料基线</span>
          <strong>{selectedApplication?.completion_rate ?? 0}% 已接受</strong>
          <small>{selectedApplication?.status ?? "未选择项目"}</small>
        </div>
        <button
          className="button primary"
          type="button"
          disabled={!selectedApplicationId || createRun.isPending}
          onClick={() => createRun.mutate()}
        >
          {createRun.isPending ? (
            <LoaderCircle className="spin" size={16} />
          ) : (
            <Play size={16} />
          )}
          {createRun.isPending ? "正在运行六个节点" : "开始编制"}
        </button>
      </section>

      {actionError && (
        <div className="inline-error agent-action-error" role="alert">
          <AlertTriangle size={16} />
          <span>{actionError}</span>
        </div>
      )}

      <div className="agent-layout">
        <aside className="agent-run-rail">
          <div className="section-heading compact-heading">
            <div>
              <span className="eyebrow">运行记录</span>
              <h2>编制历史</h2>
            </div>
            <span>{runs.data?.total ?? 0}</span>
          </div>
          {runs.isLoading && <div className="state-message">正在读取运行记录…</div>}
          {!runs.isLoading && !(runs.data?.items.length ?? 0) && (
            <div className="agent-empty-small">
              <Clock3 size={20} />
              <span>该项目还没有编制运行</span>
            </div>
          )}
          <div className="agent-run-list">
            {(runs.data?.items ?? []).map((run) => (
              <RunHistoryItem
                key={run.id}
                run={run}
                selected={run.id === selectedRunId}
                onSelect={() => {
                  setSelectedRunId(run.id);
                  setReviewNote("");
                }}
              />
            ))}
          </div>
        </aside>

        <section className="agent-workspace">
          {!selectedRun && (
            <div className="empty-state agent-empty-workspace">
              <Workflow size={28} />
              <div>
                <strong>选择章节并启动第一条编制链</strong>
                <span>系统会先锁定预审快照，再执行检索、一致性检查和草拟。</span>
              </div>
            </div>
          )}

          {selectedRun && (
            <>
              <header className="agent-run-header">
                <div>
                  <span className="eyebrow">运行 {selectedRun.id.slice(0, 8)}</span>
                  <h2>{selectedRun.draft_title}</h2>
                  <p>{selectedRun.reviewer_summary}</p>
                </div>
                <span className={`approval-status ${selectedRun.approval_status}`}>
                  {APPROVAL_LABELS[selectedRun.approval_status]}
                </span>
              </header>

              <section className="agent-node-section" aria-labelledby="agent-node-title">
                <div className="section-heading compact-heading">
                  <div>
                    <span className="eyebrow">LangGraph 运行轨迹</span>
                    <h2 id="agent-node-title">六节点执行链</h2>
                  </div>
                  <span>{selectedRun.workflow_version}</span>
                </div>
                <ol className="agent-node-grid">
                  {selectedRun.node_traces.map((trace, index) => (
                    <li className={trace.status} key={trace.node_key}>
                      <span className="agent-node-index">{index + 1}</span>
                      <div>
                        <strong>{trace.label}</strong>
                        <p>{trace.summary}</p>
                        <small>{trace.duration_ms} ms · 输出 {trace.output_count}</small>
                      </div>
                    </li>
                  ))}
                </ol>
              </section>

              <div className="agent-audit-strip">
                <div>
                  <Bot size={15} />
                  <span>生成模式</span>
                  <strong>{MODEL_MODE_LABELS[selectedRun.model_mode]}</strong>
                </div>
                <div>
                  <Scissors size={15} />
                  <span>证据上下文</span>
                  <strong>
                    {selectedRun.context_report
                      ? `${selectedRun.context_report.original_chars} → ${selectedRun.context_report.selected_chars}`
                      : "历史版本"}
                  </strong>
                </div>
                <div>
                  <Braces size={15} />
                  <span>结构化输出</span>
                  <strong>
                    {selectedRun.structured_output
                      ? `${selectedRun.structured_output.sections.length} 节 / ${selectedRun.structured_output.claims.length} 主张`
                      : "历史版本"}
                  </strong>
                </div>
                <div>
                  <Languages size={15} />
                  <span>输出语言</span>
                  <strong>{LANGUAGE_LABELS[selectedRun.language_mode]}</strong>
                </div>
                <div>
                  <Quote size={15} />
                  <span>法规引用</span>
                  <strong>{selectedRun.citations.length} 条</strong>
                </div>
                <div>
                  <Database size={15} />
                  <span>输入快照</span>
                  <code>{selectedRun.input_snapshot_hash.slice(0, 12)}</code>
                </div>
              </div>

              {selectedRun.model_error && (
                <div className="agent-degraded-note">
                  <AlertTriangle size={16} />
                  <div>
                    <strong>模型调用已受控降级</strong>
                    <span>{selectedRun.model_error}</span>
                  </div>
                </div>
              )}

              <GovernanceDetails run={selectedRun} />

              <div className="agent-detail-grid">
                <div className="agent-document-column">
                  <section className="agent-draft-section">
                    <div className="section-heading compact-heading">
                      <div>
                        <span className="eyebrow">非受控输出</span>
                        <h2>草稿正文</h2>
                      </div>
                      <FileText size={18} />
                    </div>
                    <DraftPreview content={selectedRun.draft_content} />
                  </section>

                  <section className="agent-citation-section">
                    <div className="section-heading compact-heading">
                      <div>
                        <span className="eyebrow">原文可回溯</span>
                        <h2>法规证据</h2>
                      </div>
                      <span>{selectedRun.citations.length} 条</span>
                    </div>
                    <div className="agent-citation-list">
                      {selectedRun.citations.map((citation) => (
                        <article key={citation.chunk_id}>
                          <span className="citation-marker">
                            证据 {citation.citation_index}
                          </span>
                          <div>
                            <strong>{citation.source_title}</strong>
                            <span>
                              {citation.document_number} · {citation.version_label}
                            </span>
                            <em>{citation.citation_label}</em>
                            <p>{citation.content}</p>
                            <small>
                              字符 {citation.char_start}–{citation.char_end} · 重排分数{" "}
                              {citation.score.toFixed(3)}
                            </small>
                          </div>
                        </article>
                      ))}
                    </div>
                  </section>
                </div>

                <aside className="agent-review-panel">
                  <div className="review-panel-heading">
                    <ShieldCheck size={20} />
                    <div>
                      <span>Human-in-the-loop</span>
                      <h2>人工决定</h2>
                    </div>
                  </div>
                  {selectedRun.approval_status === "pending" ? (
                    <>
                      <p>
                        批准仅表示该草稿可进入下一步受控编制，不代表注册结论或监管认可。
                      </p>
                      <label>
                        <span>审核意见</span>
                        <textarea
                          rows={7}
                          maxLength={1000}
                          value={reviewNote}
                          placeholder="记录引用核对、事实修订和后续使用限制"
                          onChange={(event) => setReviewNote(event.target.value)}
                        />
                        <small>{reviewNote.length} / 1000</small>
                      </label>
                      <div className="agent-review-actions">
                        <button
                          className="button secondary danger-button"
                          type="button"
                          disabled={reviewNote.trim().length < 2 || reviewRun.isPending}
                          onClick={() =>
                            reviewRun.mutate({
                              runId: selectedRun.id,
                              decision: "rejected",
                            })
                          }
                        >
                          <XCircle size={15} />
                          驳回
                        </button>
                        <button
                          className="button primary"
                          type="button"
                          disabled={reviewNote.trim().length < 2 || reviewRun.isPending}
                          onClick={() =>
                            reviewRun.mutate({
                              runId: selectedRun.id,
                              decision: "approved",
                            })
                          }
                        >
                          {reviewRun.isPending ? (
                            <LoaderCircle className="spin" size={15} />
                          ) : (
                            <CheckCircle2 size={15} />
                          )}
                          批准草稿
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className={`review-decision ${selectedRun.approval_status}`}>
                      {selectedRun.approval_status === "approved" ? (
                        <CheckCircle2 size={20} />
                      ) : (
                        <XCircle size={20} />
                      )}
                      <strong>{APPROVAL_LABELS[selectedRun.approval_status]}</strong>
                      <span>{selectedRun.review_note}</span>
                      <small>
                        {selectedRun.reviewed_by} · {formatDateTime(selectedRun.reviewed_at)}
                      </small>
                    </div>
                  )}
                </aside>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
