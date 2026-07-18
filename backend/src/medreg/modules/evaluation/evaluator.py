from __future__ import annotations

import math
from dataclasses import dataclass

from medreg.modules.evaluation.schemas import (
    EvaluationCase,
    EvaluationMetric,
    EvaluationQualityGate,
    EvaluationTaskSummary,
    EvaluationTaskType,
    ProductionValidationStatus,
    QualityGateStatus,
)


@dataclass(frozen=True)
class EvaluationResult:
    metrics: list[EvaluationMetric]
    task_summaries: list[EvaluationTaskSummary]
    quality_gate: EvaluationQualityGate


class MedRegEvaluator:
    BASELINE_NAME = "lexical-rules-v0"
    CANDIDATE_NAME = "hybrid-controlled-agent-v2"

    def evaluate(
        self,
        cases: list[EvaluationCase],
        production_validation_status: ProductionValidationStatus,
    ) -> EvaluationResult:
        grouped = {
            task_type: [item for item in cases if item.task_type == task_type]
            for task_type in EvaluationTaskType
        }
        metrics = [
            *self._retrieval_metrics(grouped[EvaluationTaskType.RETRIEVAL]),
            *self._citation_metrics(grouped[EvaluationTaskType.CITATION]),
            *self._conflict_metrics(grouped[EvaluationTaskType.CONFLICT]),
            self._schema_metric(grouped[EvaluationTaskType.SCHEMA]),
            self._adoption_metric(grouped[EvaluationTaskType.ADOPTION]),
            self._latency_metric(cases),
        ]
        metric_by_key = {item.key: item for item in metrics}
        task_metric_keys = {
            EvaluationTaskType.RETRIEVAL: ["retrieval_recall_at_5", "retrieval_mrr_at_10"],
            EvaluationTaskType.CITATION: ["citation_precision", "citation_coverage"],
            EvaluationTaskType.CONFLICT: [
                "conflict_precision",
                "conflict_recall",
                "conflict_f1",
            ],
            EvaluationTaskType.SCHEMA: ["schema_pass_rate"],
            EvaluationTaskType.ADOPTION: ["adoption_rate"],
        }
        summaries = []
        for task_type, keys in task_metric_keys.items():
            selected = [metric_by_key[key] for key in keys]
            baseline = self._mean([item.baseline for item in selected])
            candidate = self._mean([item.candidate for item in selected])
            summaries.append(
                EvaluationTaskSummary(
                    task_type=task_type,
                    case_count=len(grouped[task_type]),
                    baseline_score=baseline,
                    candidate_score=candidate,
                    delta=round(candidate - baseline, 4),
                    metric_keys=keys,
                )
            )
        passed_count = sum(item.passed for item in metrics)
        gate_status = (
            QualityGateStatus.PASSED
            if passed_count == len(metrics)
            else QualityGateStatus.NEEDS_ATTENTION
        )
        return EvaluationResult(
            metrics=metrics,
            task_summaries=summaries,
            quality_gate=EvaluationQualityGate(
                status=gate_status,
                passed_count=passed_count,
                total_count=len(metrics),
                production_validation_status=production_validation_status,
                message=(
                    "演示质量门禁已通过；进入真实业务前仍需医疗器械法规专家复核标注集。"
                    if gate_status == QualityGateStatus.PASSED
                    else "部分演示质量指标未达到门禁，需要定位失败样本后重新评测。"
                ),
            ),
        )

    def _retrieval_metrics(self, cases: list[EvaluationCase]) -> list[EvaluationMetric]:
        baseline_recall, baseline_mrr = self._rank_scores(cases, "baseline")
        candidate_recall, candidate_mrr = self._rank_scores(cases, "candidate")
        return [
            self._percentage_metric(
                "retrieval_recall_at_5",
                "法规检索 Recall@5",
                baseline_recall,
                candidate_recall,
                0.85,
            ),
            self._percentage_metric(
                "retrieval_mrr_at_10",
                "法规检索 MRR@10",
                baseline_mrr,
                candidate_mrr,
                0.75,
            ),
        ]

    def _citation_metrics(self, cases: list[EvaluationCase]) -> list[EvaluationMetric]:
        baseline_precision, baseline_coverage = self._set_scores(cases, "baseline")
        candidate_precision, candidate_coverage = self._set_scores(cases, "candidate")
        return [
            self._percentage_metric(
                "citation_precision",
                "引用正确率",
                baseline_precision,
                candidate_precision,
                0.90,
            ),
            self._percentage_metric(
                "citation_coverage",
                "引用覆盖率",
                baseline_coverage,
                candidate_coverage,
                0.85,
            ),
        ]

    def _conflict_metrics(self, cases: list[EvaluationCase]) -> list[EvaluationMetric]:
        baseline = self._classification_scores(cases, "baseline")
        candidate = self._classification_scores(cases, "candidate")
        return [
            self._percentage_metric(
                "conflict_precision",
                "冲突识别 Precision",
                baseline[0],
                candidate[0],
                0.85,
            ),
            self._percentage_metric(
                "conflict_recall",
                "冲突识别 Recall",
                baseline[1],
                candidate[1],
                0.85,
            ),
            self._percentage_metric(
                "conflict_f1",
                "冲突识别 F1",
                baseline[2],
                candidate[2],
                0.85,
            ),
        ]

    def _schema_metric(self, cases: list[EvaluationCase]) -> EvaluationMetric:
        def score(system: str) -> float:
            passed = 0
            for case in cases:
                prediction = getattr(case, system)
                if prediction.valid_json and set(case.required_fields).issubset(
                    prediction.fields
                ):
                    passed += 1
            return passed / len(cases) if cases else 0.0

        return self._percentage_metric(
            "schema_pass_rate",
            "结构化输出 Schema 通过率",
            score("baseline"),
            score("candidate"),
            0.90,
        )

    def _adoption_metric(self, cases: list[EvaluationCase]) -> EvaluationMetric:
        def score(system: str) -> float:
            decisions = [getattr(item, system).adopted for item in cases]
            adopted = sum(decision is True for decision in decisions)
            return adopted / len(decisions) if decisions else 0.0

        return self._percentage_metric(
            "adoption_rate",
            "Agent 建议演示采纳率",
            score("baseline"),
            score("candidate"),
            0.75,
        )

    def _latency_metric(self, cases: list[EvaluationCase]) -> EvaluationMetric:
        baseline = float(self._percentile([item.baseline.latency_ms for item in cases], 0.95))
        candidate = float(
            self._percentile([item.candidate.latency_ms for item in cases], 0.95)
        )
        target = round(baseline * 0.8, 2)
        return EvaluationMetric(
            key="latency_p95_ms",
            label="端到端耗时 P95",
            unit="ms",
            higher_is_better=False,
            baseline=baseline,
            candidate=candidate,
            delta=round(candidate - baseline, 2),
            target=target,
            passed=candidate <= target,
        )

    @staticmethod
    def _rank_scores(cases: list[EvaluationCase], system: str) -> tuple[float, float]:
        recalls: list[float] = []
        reciprocal_ranks: list[float] = []
        for case in cases:
            ranked = getattr(case, system).ranked_labels[:10]
            relevant = set(case.gold_labels)
            recalls.append(float(bool(relevant.intersection(ranked[:5]))))
            rank = next(
                (index for index, item in enumerate(ranked, start=1) if item in relevant),
                None,
            )
            reciprocal_ranks.append(1 / rank if rank else 0.0)
        return MedRegEvaluator._mean(recalls), MedRegEvaluator._mean(reciprocal_ranks)

    @staticmethod
    def _set_scores(cases: list[EvaluationCase], system: str) -> tuple[float, float]:
        true_positive = predicted_total = gold_total = 0
        for case in cases:
            predicted = set(getattr(case, system).labels)
            gold = set(case.gold_labels)
            true_positive += len(predicted.intersection(gold))
            predicted_total += len(predicted)
            gold_total += len(gold)
        precision = true_positive / predicted_total if predicted_total else 0.0
        coverage = true_positive / gold_total if gold_total else 0.0
        return round(precision, 4), round(coverage, 4)

    @staticmethod
    def _classification_scores(
        cases: list[EvaluationCase],
        system: str,
    ) -> tuple[float, float, float]:
        precision, recall = MedRegEvaluator._set_scores(cases, system)
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return precision, recall, round(f1, 4)

    @staticmethod
    def _percentage_metric(
        key: str,
        label: str,
        baseline: float,
        candidate: float,
        target: float,
    ) -> EvaluationMetric:
        return EvaluationMetric(
            key=key,
            label=label,
            unit="ratio",
            higher_is_better=True,
            baseline=round(baseline, 4),
            candidate=round(candidate, 4),
            delta=round(candidate - baseline, 4),
            target=target,
            passed=candidate >= target,
        )

    @staticmethod
    def _mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    @staticmethod
    def _percentile(values: list[int], percentile: float) -> int:
        if not values:
            return 0
        ordered = sorted(values)
        index = max(math.ceil(percentile * len(ordered)) - 1, 0)
        return ordered[index]
