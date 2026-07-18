import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  FlaskConical,
  Gauge,
  Hash,
  LoaderCircle,
  Play,
  ShieldCheck,
} from "lucide-react";
import { evaluationApi } from "../api/client";
import type {
  EvaluationMetric,
  EvaluationRun,
  EvaluationTaskType,
} from "../types";

const TASK_LABELS: Record<EvaluationTaskType, string> = {
  retrieval: "法规检索",
  citation: "引用追溯",
  conflict: "冲突识别",
  schema: "结构化输出",
  adoption: "人工采纳",
};

const FILTERS: Array<{ value: EvaluationTaskType | "all"; label: string }> = [
  { value: "all", label: "全部" },
  ...Object.entries(TASK_LABELS).map(([value, label]) => ({
    value: value as EvaluationTaskType,
    label,
  })),
];

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatMetric(value: number, unit: EvaluationMetric["unit"]) {
  return unit === "ratio" ? `${(value * 100).toFixed(1)}%` : `${value.toFixed(0)} ms`;
}

function formatDelta(metric: EvaluationMetric) {
  if (metric.unit === "ms") return `${metric.delta > 0 ? "+" : ""}${metric.delta.toFixed(0)} ms`;
  return `${metric.delta > 0 ? "+" : ""}${(metric.delta * 100).toFixed(1)} pp`;
}

function candidateBarWidth(metric: EvaluationMetric) {
  if (metric.unit === "ratio") return `${Math.min(metric.candidate * 100, 100)}%`;
  if (!metric.baseline) return "0%";
  return `${Math.min((metric.candidate / metric.baseline) * 100, 100)}%`;
}

function MetricRow({ metric }: { metric: EvaluationMetric }) {
  return (
    <div className="evaluation-metric-row">
      <div className="evaluation-metric-name">
        <strong>{metric.label}</strong>
        <span>门禁 {formatMetric(metric.target, metric.unit)}</span>
      </div>
      <div className="evaluation-metric-value baseline">
        <span>基线</span>
        <strong>{formatMetric(metric.baseline, metric.unit)}</strong>
      </div>
      <div className="evaluation-metric-value candidate">
        <span>当前管线</span>
        <strong>{formatMetric(metric.candidate, metric.unit)}</strong>
        <div className="metric-track" aria-hidden="true">
          <span style={{ width: candidateBarWidth(metric) }} />
        </div>
      </div>
      <div className={`evaluation-delta ${metric.passed ? "passed" : "failed"}`}>
        {metric.passed ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
        <strong>{formatDelta(metric)}</strong>
      </div>
    </div>
  );
}

function RunButton({
  run,
  selected,
  onClick,
}: {
  run: EvaluationRun;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`evaluation-run-button${selected ? " selected" : ""}`}
      aria-pressed={selected}
      onClick={onClick}
    >
      <span>{formatDateTime(run.created_at)}</span>
      <strong>{run.quality_gate.passed_count}/{run.quality_gate.total_count} 门禁</strong>
      <code>{run.id.slice(0, 8)}</code>
    </button>
  );
}

export function EvaluationPage() {
  const queryClient = useQueryClient();
  const [taskFilter, setTaskFilter] = useState<EvaluationTaskType | "all">("all");
  const [selectedRunId, setSelectedRunId] = useState("");

  const dataset = useQuery({
    queryKey: ["evaluation-dataset"],
    queryFn: evaluationApi.dataset,
  });
  const cases = useQuery({
    queryKey: ["evaluation-cases", taskFilter],
    queryFn: () => evaluationApi.cases(taskFilter === "all" ? undefined : taskFilter),
  });
  const runs = useQuery({
    queryKey: ["evaluation-runs"],
    queryFn: evaluationApi.listRuns,
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
    mutationFn: evaluationApi.createRun,
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["evaluation-runs"] });
      setSelectedRunId(created.id);
    },
  });

  const selectedRun = (runs.data?.items ?? []).find(
    (item) => item.id === selectedRunId,
  );
  const p95 = selectedRun?.metrics.find((item) => item.key === "latency_p95_ms");
  const candidateAverage = selectedRun?.task_summaries.length
    ? selectedRun.task_summaries.reduce((sum, item) => sum + item.candidate_score, 0) /
      selectedRun.task_summaries.length
    : 0;

  return (
    <div className="page evaluation-page">
      <div className="page-header evaluation-page-header">
        <div>
          <span className="eyebrow">版本化回归基准</span>
          <h1>评测中心</h1>
          <p>对照基线与当前受控管线，追踪检索、引用、冲突、Schema、采纳和耗时。</p>
        </div>
        <button
          className="button primary"
          type="button"
          disabled={createRun.isPending || !dataset.data}
          onClick={() => createRun.mutate()}
        >
          {createRun.isPending ? (
            <LoaderCircle className="spin" size={16} />
          ) : (
            <Play size={16} />
          )}
          {createRun.isPending ? "正在计算 60 条样本" : "运行完整评测"}
        </button>
      </div>

      <section className="evaluation-dataset-band" aria-label="评测数据集状态">
        <div>
          <Database size={17} />
          <span>数据集</span>
          <strong>{dataset.data?.dataset_version ?? "读取中"}</strong>
        </div>
        <div>
          <FlaskConical size={17} />
          <span>样本覆盖</span>
          <strong>{dataset.data?.case_count ?? 0} 条 / 5 类任务</strong>
        </div>
        <div>
          <Hash size={17} />
          <span>数据指纹</span>
          <code>{dataset.data?.dataset_hash.slice(0, 12) ?? "-"}</code>
        </div>
        <div className="evaluation-validation-state">
          <AlertTriangle size={17} />
          <span>专家签署</span>
          <strong>待领域专家复核</strong>
        </div>
      </section>

      {dataset.data && (
        <div className="evaluation-boundary-note">
          <ShieldCheck size={17} />
          <span>{dataset.data.source_note}</span>
        </div>
      )}

      {createRun.error && (
        <div className="inline-error" role="alert">
          <AlertTriangle size={16} />
          <span>{createRun.error.message}</span>
        </div>
      )}

      {!selectedRun && !runs.isLoading && (
        <div className="empty-state evaluation-empty">
          <Gauge size={26} />
          <div>
            <strong>还没有持久化评测运行</strong>
            <span>运行完整评测后生成基线对照、门禁结果和样本级追踪记录。</span>
          </div>
        </div>
      )}

      {selectedRun && (
        <>
          <section className="evaluation-summary-strip" aria-label="最新评测摘要">
            <div>
              <span>质量门禁</span>
              <strong>{selectedRun.quality_gate.passed_count}/{selectedRun.quality_gate.total_count}</strong>
              <small>{selectedRun.quality_gate.status === "passed" ? "演示门禁通过" : "需要处理"}</small>
            </div>
            <div>
              <span>任务平均分</span>
              <strong>{(candidateAverage * 100).toFixed(1)}%</strong>
              <small>{selectedRun.candidate_name}</small>
            </div>
            <div>
              <span>端到端 P95</span>
              <strong>{p95 ? `${p95.candidate.toFixed(0)} ms` : "-"}</strong>
              <small>{p95 ? `基线 ${p95.baseline.toFixed(0)} ms` : "-"}</small>
            </div>
            <div>
              <span>运行样本</span>
              <strong>{selectedRun.case_count}</strong>
              <small>{selectedRun.dataset_hash.slice(0, 12)}</small>
            </div>
          </section>

          <div className="evaluation-main-grid">
            <section className="evaluation-metrics-section">
              <div className="section-heading compact-heading">
                <div>
                  <span className="eyebrow">Baseline vs Candidate</span>
                  <h2>质量指标对照</h2>
                </div>
                <span>{selectedRun.metrics.length} 项</span>
              </div>
              <div className="evaluation-metric-list">
                {selectedRun.metrics.map((metric) => (
                  <MetricRow key={metric.key} metric={metric} />
                ))}
              </div>
            </section>

            <aside className="evaluation-run-history">
              <div className="section-heading compact-heading">
                <div>
                  <span className="eyebrow">PostgreSQL</span>
                  <h2>评测运行</h2>
                </div>
                <span>{runs.data?.total ?? 0}</span>
              </div>
              <div className="evaluation-run-list">
                {(runs.data?.items ?? []).map((run) => (
                  <RunButton
                    key={run.id}
                    run={run}
                    selected={run.id === selectedRunId}
                    onClick={() => setSelectedRunId(run.id)}
                  />
                ))}
              </div>
              <div className={`evaluation-gate-note ${selectedRun.quality_gate.status}`}>
                {selectedRun.quality_gate.status === "passed" ? (
                  <CheckCircle2 size={17} />
                ) : (
                  <AlertTriangle size={17} />
                )}
                <span>{selectedRun.quality_gate.message}</span>
              </div>
            </aside>
          </div>

          <section className="evaluation-task-section">
            <div className="section-heading compact-heading">
              <div>
                <span className="eyebrow">任务切片</span>
                <h2>分任务表现</h2>
              </div>
            </div>
            <div className="evaluation-task-table">
              <div className="evaluation-task-head">
                <span>任务</span>
                <span>样本</span>
                <span>基线</span>
                <span>当前管线</span>
                <span>提升</span>
              </div>
              {selectedRun.task_summaries.map((item) => (
                <div className="evaluation-task-row" key={item.task_type}>
                  <strong>{TASK_LABELS[item.task_type]}</strong>
                  <span>{item.case_count}</span>
                  <span>{(item.baseline_score * 100).toFixed(1)}%</span>
                  <span>{(item.candidate_score * 100).toFixed(1)}%</span>
                  <em>+{(item.delta * 100).toFixed(1)} pp</em>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      <section className="evaluation-cases-section">
        <div className="section-heading compact-heading evaluation-cases-heading">
          <div>
            <span className="eyebrow">可审查样本</span>
            <h2>标注集覆盖</h2>
          </div>
          <span>{cases.data?.total ?? 0} 条</span>
        </div>
        <div className="evaluation-filters" aria-label="样本任务筛选">
          {FILTERS.map((filter) => (
            <button
              type="button"
              key={filter.value}
              className={taskFilter === filter.value ? "selected" : ""}
              aria-pressed={taskFilter === filter.value}
              onClick={() => setTaskFilter(filter.value)}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <div className="evaluation-case-list">
          {(cases.data?.items ?? []).map((item) => (
            <article key={item.id}>
              <code>{item.id}</code>
              <div>
                <strong>{item.title}</strong>
                <p>{item.input_text}</p>
              </div>
              <span>{TASK_LABELS[item.task_type]}</span>
              <small>合成演示标注</small>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
