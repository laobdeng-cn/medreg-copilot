from fastapi.testclient import TestClient

from medreg.main import app
from medreg.modules.evaluation.dataset import VersionedEvaluationDataset
from medreg.modules.evaluation.evaluator import MedRegEvaluator
from medreg.modules.evaluation.schemas import EvaluationTaskType


def test_versioned_dataset_has_balanced_traceable_coverage() -> None:
    dataset = VersionedEvaluationDataset()
    summary = dataset.summary()

    assert summary.dataset_version == "medreg-eval-v1-60"
    assert summary.case_count == 60
    assert len(summary.dataset_hash) == 64
    assert summary.verified_count == 0
    assert summary.pending_count == 60
    assert summary.production_validation_status == "pending_domain_expert"
    assert set(summary.task_counts) == set(EvaluationTaskType)
    assert all(count == 12 for count in summary.task_counts.values())
    assert len({item.id for item in dataset.cases}) == 60


def test_evaluator_computes_candidate_improvement_and_quality_gate() -> None:
    dataset = VersionedEvaluationDataset()
    result = MedRegEvaluator().evaluate(
        dataset.cases,
        dataset.summary().production_validation_status,
    )
    metrics = {item.key: item for item in result.metrics}

    assert metrics["retrieval_recall_at_5"].baseline == 0.5833
    assert metrics["retrieval_recall_at_5"].candidate == 0.9167
    assert metrics["citation_coverage"].candidate == 0.95
    assert metrics["conflict_f1"].candidate == 0.9268
    assert metrics["schema_pass_rate"].candidate == 0.9167
    assert metrics["adoption_rate"].candidate == 0.8333
    assert metrics["latency_p95_ms"].candidate < metrics["latency_p95_ms"].baseline
    assert all(item.passed for item in result.metrics)
    assert result.quality_gate.status == "passed"
    assert result.quality_gate.production_validation_status == "pending_domain_expert"


def test_evaluation_api_exposes_cases_and_persists_runs() -> None:
    client = TestClient(app)

    dataset_response = client.get("/api/v1/evaluation/dataset")
    cases_response = client.get(
        "/api/v1/evaluation/cases",
        params={"task_type": "conflict", "limit": 5},
    )
    run_response = client.post(
        "/api/v1/evaluation/runs",
        json={"requested_by": "刘凯旗"},
    )
    history_response = client.get("/api/v1/evaluation/runs")

    assert dataset_response.status_code == 200
    assert dataset_response.json()["case_count"] == 60
    assert cases_response.status_code == 200
    assert cases_response.json()["total"] == 12
    assert len(cases_response.json()["items"]) == 5
    assert run_response.status_code == 201
    assert run_response.json()["case_count"] == 60
    assert run_response.json()["quality_gate"]["status"] == "passed"
    assert history_response.status_code == 200
    assert history_response.json()["total"] == 1
