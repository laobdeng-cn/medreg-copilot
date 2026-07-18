#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "backend"
    / "src"
    / "medreg"
    / "modules"
    / "evaluation"
    / "dataset_v1.json"
)

ARTICLE_LABELS = [
    "samr-47-article-13",
    "samr-47-article-24",
    "samr-47-article-52",
    "samr-47-article-61",
    "samr-47-article-62",
]
RETRIEVAL_DISTRACTORS = [
    "samr-47-article-8",
    "samr-47-article-17",
    "samr-47-article-31",
    "samr-47-article-44",
    "samr-47-article-58",
    "samr-47-article-70",
]
CONFLICT_LABELS = [
    "product_name",
    "model_specification",
    "intended_use",
    "performance",
    "warnings",
]
SCHEMA_FIELDS = ["title", "summary", "sections", "claims", "bilingual_terms"]


def prediction(
    *,
    latency_ms: int,
    ranked_labels: list[str] | None = None,
    labels: list[str] | None = None,
    fields: list[str] | None = None,
    valid_json: bool | None = None,
    adopted: bool | None = None,
) -> dict:
    return {
        "ranked_labels": ranked_labels or [],
        "labels": labels or [],
        "fields": fields or [],
        "valid_json": valid_json,
        "adopted": adopted,
        "latency_ms": latency_ms,
    }


def retrieval_cases() -> list[dict]:
    cases = []
    queries = [
        "注册申报资料需要包含哪些文件",
        "医疗器械研制应遵循什么风险原则",
        "附条件批准后如何持续管理风险",
        "注册材料真实性与可追溯要求",
        "产品风险分析资料的提交依据",
        "严重疾病器械附条件批准条件",
        "产品安全有效质量可控的基本要求",
        "上市后受益风险数据如何监测",
        "首次注册申请前需要完成哪些准备",
        "技术要求和检验报告属于什么资料",
        "风险管理原则对应哪一条法规",
        "附条件批准研究资料提交时限",
    ]
    gold = [2, 1, 4, 0, 2, 3, 0, 4, 2, 2, 1, 3]
    for index, query in enumerate(queries):
        relevant = ARTICLE_LABELS[gold[index]]
        distractors = [
            *[item for item in ARTICLE_LABELS if item != relevant],
            *RETRIEVAL_DISTRACTORS,
        ]
        candidate_rank = 7 if index == 10 else (2 if index in {3, 7, 11} else 1)
        candidate_ranked = distractors[: candidate_rank - 1] + [relevant]
        candidate_ranked += [item for item in distractors if item not in candidate_ranked]
        candidate_ranked = candidate_ranked[:10]
        baseline_hit = index not in {1, 4, 7, 9, 10}
        baseline_rank = 3 if baseline_hit and index % 2 else (1 if baseline_hit else 8)
        baseline_ranked = distractors[: baseline_rank - 1] + [relevant]
        baseline_ranked += [item for item in distractors if item not in baseline_ranked]
        baseline_ranked = baseline_ranked[:10]
        cases.append(
            {
                "id": f"EVAL-RET-{index + 1:03d}",
                "task_type": "retrieval",
                "title": f"法规检索样本 {index + 1}",
                "input_text": query,
                "gold_labels": [relevant],
                "required_fields": [],
                "baseline": prediction(
                    ranked_labels=baseline_ranked,
                    latency_ms=410 + index * 17,
                ),
                "candidate": prediction(
                    ranked_labels=candidate_ranked,
                    latency_ms=175 + index * 7,
                ),
                "annotation_status": "curated_demo",
                "tags": ["第47号令", "法规检索"],
            }
        )
    return cases


def citation_cases() -> list[dict]:
    cases = []
    citation_pool = [
        "article-13@1812-1917",
        "article-24@2921-3002",
        "article-52@6474-6681",
        "article-62@8296-8394",
    ]
    for index in range(12):
        gold = citation_pool[: 3 if index % 3 else 4]
        candidate = list(gold)
        if index in {5, 11}:
            candidate = candidate[:-1]
        if index == 8:
            candidate.append("article-61@8182-8295")
        baseline = gold[:1]
        if index % 2:
            baseline.append("article-61@8182-8295")
        cases.append(
            {
                "id": f"EVAL-CIT-{index + 1:03d}",
                "task_type": "citation",
                "title": f"引用完整性样本 {index + 1}",
                "input_text": "核对草稿事实主张是否具有法规原文、条款路径和字符坐标。",
                "gold_labels": gold,
                "required_fields": [],
                "baseline": prediction(labels=baseline, latency_ms=445 + index * 13),
                "candidate": prediction(labels=candidate, latency_ms=190 + index * 6),
                "annotation_status": "curated_demo",
                "tags": ["引用", "字符坐标", "可追溯"],
            }
        )
    return cases


def conflict_cases() -> list[dict]:
    cases = []
    for index in range(12):
        first = CONFLICT_LABELS[index % len(CONFLICT_LABELS)]
        second = CONFLICT_LABELS[(index + 2) % len(CONFLICT_LABELS)]
        gold = [first, second] if index % 4 else [first]
        candidate = list(gold)
        if index in {3, 9} and len(candidate) > 1:
            candidate = candidate[:-1]
        if index == 6:
            candidate.append("unreadable_evidence")
        baseline = [first] if index % 3 else []
        if index in {2, 8}:
            baseline.append("unreadable_evidence")
        cases.append(
            {
                "id": f"EVAL-CON-{index + 1:03d}",
                "task_type": "conflict",
                "title": f"跨文档冲突样本 {index + 1}",
                "input_text": "比较技术要求、风险分析和说明书中的受控字段差异。",
                "gold_labels": gold,
                "required_fields": [],
                "baseline": prediction(labels=baseline, latency_ms=520 + index * 11),
                "candidate": prediction(labels=candidate, latency_ms=215 + index * 8),
                "annotation_status": "curated_demo",
                "tags": ["一致性", *gold],
            }
        )
    return cases


def schema_cases() -> list[dict]:
    cases = []
    for index in range(12):
        baseline_fields = SCHEMA_FIELDS[: 3 + (index % 3)]
        candidate_fields = list(SCHEMA_FIELDS)
        if index == 11:
            candidate_fields.remove("bilingual_terms")
        cases.append(
            {
                "id": f"EVAL-SCH-{index + 1:03d}",
                "task_type": "schema",
                "title": f"结构化输出样本 {index + 1}",
                "input_text": "验证 Agent 输出章节、主张、证据标记和受控术语结构。",
                "gold_labels": [],
                "required_fields": SCHEMA_FIELDS,
                "baseline": prediction(
                    fields=baseline_fields,
                    valid_json=index % 4 != 0,
                    latency_ms=470 + index * 15,
                ),
                "candidate": prediction(
                    fields=candidate_fields,
                    valid_json=True,
                    latency_ms=205 + index * 7,
                ),
                "annotation_status": "curated_demo",
                "tags": ["JSON Schema", "结构化输出"],
            }
        )
    return cases


def adoption_cases() -> list[dict]:
    cases = []
    rejected_candidate = {4, 10}
    for index in range(12):
        cases.append(
            {
                "id": f"EVAL-ADO-{index + 1:03d}",
                "task_type": "adoption",
                "title": f"人工采纳演示样本 {index + 1}",
                "input_text": "演示审阅人根据事实支持、引用完整性和使用限制作出采纳决定。",
                "gold_labels": [],
                "required_fields": [],
                "baseline": prediction(
                    adopted=index % 2 == 0,
                    latency_ms=560 + index * 12,
                ),
                "candidate": prediction(
                    adopted=index not in rejected_candidate,
                    latency_ms=225 + index * 8,
                ),
                "annotation_status": "curated_demo",
                "tags": ["Human-in-the-loop", "演示采纳"],
            }
        )
    return cases


def main() -> None:
    cases = [
        *retrieval_cases(),
        *citation_cases(),
        *conflict_cases(),
        *schema_cases(),
        *adoption_cases(),
    ]
    payload = {
        "dataset_version": "medreg-eval-v1-60",
        "annotation_mode": "synthetic_regulatory_demo_with_expert_review_workflow",
        "cases": cases,
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(cases)} evaluation cases to {OUTPUT}")


if __name__ == "__main__":
    main()
