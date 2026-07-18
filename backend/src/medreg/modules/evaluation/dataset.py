from __future__ import annotations

import hashlib
import json
from pathlib import Path

from medreg.modules.evaluation.schemas import (
    AnnotationStatus,
    EvaluationCase,
    EvaluationDatasetSummary,
    EvaluationTaskType,
    ProductionValidationStatus,
)

DATASET_VERSION = "medreg-eval-v1-60"
ANNOTATION_MODE = "synthetic_regulatory_demo_with_expert_review_workflow"
SOURCE_NOTE = (
    "60 条合成医疗器械注册业务样本，用于可重复工程评测；"
    "未冒充真实监管案例或已完成医疗器械专家签署。"
)


class VersionedEvaluationDataset:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(__file__).with_name("dataset_v1.json")
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("dataset_version") != DATASET_VERSION:
            raise ValueError("Unexpected evaluation dataset version")
        self.cases = [EvaluationCase.model_validate(item) for item in payload["cases"]]
        if len(self.cases) != 60:
            raise ValueError("The M5 evaluation dataset must contain exactly 60 cases")
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.dataset_hash = hashlib.sha256(canonical.encode()).hexdigest()

    def summary(self) -> EvaluationDatasetSummary:
        task_counts = {
            task_type: sum(item.task_type == task_type for item in self.cases)
            for task_type in EvaluationTaskType
        }
        verified_count = sum(
            item.annotation_status == AnnotationStatus.EXPERT_VERIFIED
            for item in self.cases
        )
        return EvaluationDatasetSummary(
            dataset_version=DATASET_VERSION,
            dataset_hash=self.dataset_hash,
            case_count=len(self.cases),
            task_counts=task_counts,
            annotation_mode=ANNOTATION_MODE,
            production_validation_status=(
                ProductionValidationStatus.EXPERT_VERIFIED
                if verified_count == len(self.cases)
                else ProductionValidationStatus.PENDING_DOMAIN_EXPERT
            ),
            verified_count=verified_count,
            pending_count=len(self.cases) - verified_count,
            source_note=SOURCE_NOTE,
        )

    def list_cases(
        self,
        task_type: EvaluationTaskType | None = None,
        limit: int = 20,
    ) -> list[EvaluationCase]:
        items = [
            item for item in self.cases if task_type is None or item.task_type == task_type
        ]
        return items[:limit]
