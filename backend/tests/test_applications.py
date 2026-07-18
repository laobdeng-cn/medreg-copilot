from datetime import date
from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfReader

from medreg.main import app

client = TestClient(app)


def application_payload() -> dict[str, str]:
    return {
        "name": "二类器械首次注册演示项目",
        "product_name": "示例无源医疗器械",
        "applicant_name": "深圳示例医疗科技有限公司",
        "jurisdiction": "CN_NMPA",
        "device_class": "II",
        "application_type": "initial_registration",
        "regulation_effective_on": date.today().isoformat(),
        "owner_name": "刘凯旗",
    }


def test_create_application_initializes_seven_required_categories() -> None:
    response = client.post("/api/v1/registration-applications", json=application_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["code"].startswith(f"MR-{date.today().year}-")
    assert body["status"] == "draft"
    assert body["completion_rate"] == 0.0
    assert len(body["requirements"]) == 7
    assert {item["status"] for item in body["requirements"]} == {"missing"}

    list_response = client.get("/api/v1/registration-applications")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["items"][0]["id"] == body["id"]


def test_get_missing_application_returns_404() -> None:
    response = client.get("/api/v1/registration-applications/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404
    assert response.json()["detail"] == "Registration application not found"


def test_create_application_rejects_unsupported_device_class() -> None:
    payload = application_payload()
    payload["device_class"] = "I"

    response = client.post("/api/v1/registration-applications", json=payload)

    assert response.status_code == 422


def test_precheck_reports_missing_required_dossier_categories() -> None:
    created = client.post(
        "/api/v1/registration-applications", json=application_payload()
    ).json()

    response = client.post(
        f"/api/v1/registration-applications/{created['id']}/prechecks",
        json={"initiated_by": "刘凯旗"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["application_status"] == "needs_action"
    assert body["blocker_count"] == 7
    assert body["warning_count"] == 0
    assert body["pass_count"] == 0
    assert len(body["findings"]) == 7
    assert {item["rule_code"] for item in body["findings"]} == {
        "DOSSIER_REQUIRED_MISSING"
    }


def test_evidence_upload_review_and_precheck_form_a_persisted_workflow() -> None:
    created = client.post(
        "/api/v1/registration-applications", json=application_payload()
    ).json()
    application_id = created["id"]
    evidence_url = (
        f"/api/v1/registration-applications/{application_id}"
        "/requirements/risk_analysis/evidence"
    )

    upload = client.post(
        evidence_url,
        files={"file": ("risk-analysis.txt", b"risk evidence", "text/plain")},
        data={"uploaded_by": "刘凯旗"},
    )

    assert upload.status_code == 201
    assert upload.json()["category_key"] == "risk_analysis"
    evidence = client.get(evidence_url)
    assert evidence.status_code == 200
    assert evidence.json()["total"] == 1

    after_upload = client.get(
        f"/api/v1/registration-applications/{application_id}"
    ).json()
    risk_requirement = next(
        item
        for item in after_upload["requirements"]
        if item["key"] == "risk_analysis"
    )
    assert risk_requirement["status"] == "uploaded"
    assert risk_requirement["evidence_count"] == 1

    review = client.patch(
        (
            f"/api/v1/registration-applications/{application_id}"
            "/requirements/risk_analysis/review"
        ),
        json={"decision": "accepted", "reviewed_by": "法规负责人"},
    )

    assert review.status_code == 200
    assert review.json()["completion_rate"] == 14.3
    assert next(
        item
        for item in review.json()["requirements"]
        if item["key"] == "risk_analysis"
    )["status"] == "accepted"

    precheck = client.post(
        f"/api/v1/registration-applications/{application_id}/prechecks",
        json={"initiated_by": "刘凯旗"},
    )

    assert precheck.status_code == 201
    assert precheck.json()["blocker_count"] == 6
    assert precheck.json()["warning_count"] == 0
    assert precheck.json()["pass_count"] == 1

    history = client.get(
        f"/api/v1/registration-applications/{application_id}/prechecks"
    )
    assert history.status_code == 200
    assert history.json()["total"] == 1


def test_review_rejects_requirement_without_evidence() -> None:
    created = client.post(
        "/api/v1/registration-applications", json=application_payload()
    ).json()

    response = client.patch(
        (
            f"/api/v1/registration-applications/{created['id']}"
            "/requirements/test_report/review"
        ),
        json={"decision": "accepted", "reviewed_by": "法规负责人"},
    )

    assert response.status_code == 409
    assert "Evidence must be uploaded" in response.json()["detail"]


def test_evidence_matrix_tracks_finding_remediation_lifecycle() -> None:
    created = client.post(
        "/api/v1/registration-applications", json=application_payload()
    ).json()
    application_id = created["id"]
    run = client.post(
        f"/api/v1/registration-applications/{application_id}/prechecks",
        json={"initiated_by": "刘凯旗"},
    ).json()
    finding_id = run["findings"][0]["id"]

    matrix = client.get(
        f"/api/v1/registration-applications/{application_id}/evidence-matrix"
    )
    assert matrix.status_code == 200
    assert len(matrix.json()["rows"]) == 7
    assert matrix.json()["open_finding_count"] == 7
    assert matrix.json()["rows"][0]["findings"][0]["remediation_status"] == "open"

    started = client.patch(
        f"/api/v1/precheck-findings/{finding_id}/remediation",
        json={
            "status": "in_progress",
            "assignee": "刘凯旗",
            "updated_by": "法规负责人",
        },
    )
    assert started.status_code == 200
    assert started.json()["remediation_status"] == "in_progress"
    assert started.json()["assignee"] == "刘凯旗"

    invalid_close = client.patch(
        f"/api/v1/precheck-findings/{finding_id}/remediation",
        json={"status": "resolved", "updated_by": "法规负责人"},
    )
    assert invalid_close.status_code == 409

    resolved = client.patch(
        f"/api/v1/precheck-findings/{finding_id}/remediation",
        json={
            "status": "resolved",
            "assignee": "刘凯旗",
            "note": "已补齐风险分析资料并完成内部复核。",
            "updated_by": "法规负责人",
        },
    )
    assert resolved.status_code == 200
    assert resolved.json()["remediation_status"] == "resolved"
    assert resolved.json()["resolved_at"] is not None

    updated_matrix = client.get(
        f"/api/v1/registration-applications/{application_id}/evidence-matrix"
    ).json()
    assert updated_matrix["open_finding_count"] == 6
    assert updated_matrix["rows"][0]["findings"][0]["resolution_note"] == (
        "已补齐风险分析资料并完成内部复核。"
    )


def test_consistency_report_turns_cross_document_conflicts_into_findings() -> None:
    created = client.post(
        "/api/v1/registration-applications", json=application_payload()
    ).json()
    application_id = created["id"]
    technical_text = """产品名称：示例无源医疗器械
型号规格：MD-100、MD-200
预期用途：用于医疗机构采集成人生理信号
性能指标：测量范围 30-240 bpm
警示语：不得用于生命支持监护
"""
    ifu_text = """产品名称：动态血压监测仪
规格型号：MD-200/MD-100
适用范围：用于儿童血压连续监测
主要性能：测量范围30—240 bpm
注意事项：不得用于生命支持监护
"""

    for category, file_name, content in (
        ("technical_requirements", "technical.txt", technical_text),
        ("ifu_and_label", "ifu.txt", ifu_text),
    ):
        evidence_url = (
            f"/api/v1/registration-applications/{application_id}"
            f"/requirements/{category}/evidence"
        )
        upload = client.post(
            evidence_url,
            files={"file": (file_name, content.encode(), "text/plain")},
            data={"uploaded_by": "刘凯旗"},
        )
        assert upload.status_code == 201
        review = client.patch(
            (
                f"/api/v1/registration-applications/{application_id}"
                f"/requirements/{category}/review"
            ),
            json={"decision": "accepted", "reviewed_by": "法规负责人"},
        )
        assert review.status_code == 200

    report = client.get(
        f"/api/v1/registration-applications/{application_id}/consistency-report"
    )
    assert report.status_code == 200
    assert report.json()["mismatch_count"] == 2
    assert report.json()["pass_count"] == 3
    assert report.json()["unreadable_evidence"] == []

    precheck = client.post(
        f"/api/v1/registration-applications/{application_id}/prechecks",
        json={"initiated_by": "刘凯旗"},
    )
    rule_codes = {item["rule_code"] for item in precheck.json()["findings"]}
    assert "CONSISTENCY_PRODUCT_NAME_MISMATCH" in rule_codes
    assert "CONSISTENCY_INTENDED_USE_MISMATCH" in rule_codes
    assert precheck.json()["rule_set_version"] == "nmpa-dossier-precheck-v2"


def test_internal_precheck_report_contains_traceability_and_downloadable_pdf() -> None:
    created = client.post(
        "/api/v1/registration-applications", json=application_payload()
    ).json()
    application_id = created["id"]
    evidence_url = (
        f"/api/v1/registration-applications/{application_id}"
        "/requirements/risk_analysis/evidence"
    )
    upload = client.post(
        evidence_url,
        files={
            "file": (
                "risk-analysis.txt",
                "产品名称：示例无源医疗器械".encode(),
                "text/plain",
            )
        },
        data={"uploaded_by": "刘凯旗"},
    )
    assert upload.status_code == 201
    client.patch(
        (
            f"/api/v1/registration-applications/{application_id}"
            "/requirements/risk_analysis/review"
        ),
        json={"decision": "accepted", "reviewed_by": "法规负责人"},
    )
    precheck = client.post(
        f"/api/v1/registration-applications/{application_id}/prechecks",
        json={"initiated_by": "刘凯旗"},
    ).json()

    report = client.get(
        f"/api/v1/registration-applications/{application_id}/precheck-report"
    )
    assert report.status_code == 200
    body = report.json()
    assert body["precheck"]["id"] == precheck["id"]
    assert body["report_code"].startswith(created["code"] + "-PR-")
    assert body["is_stale"] is False
    assert body["evidence_count"] == 1
    assert body["evidence_manifest"][0]["sha256"] == upload.json()["sha256"]

    pdf = client.get(
        f"/api/v1/registration-applications/{application_id}/precheck-report.pdf"
    )
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["x-medreg-precheck-run"] == precheck["id"]
    assert pdf.content.startswith(b"%PDF-")
    assert len(PdfReader(BytesIO(pdf.content)).pages) >= 2


def test_internal_precheck_report_blocks_stale_pdf_export() -> None:
    created = client.post(
        "/api/v1/registration-applications", json=application_payload()
    ).json()
    application_id = created["id"]
    client.post(
        f"/api/v1/registration-applications/{application_id}/prechecks",
        json={"initiated_by": "刘凯旗"},
    )
    client.post(
        (
            f"/api/v1/registration-applications/{application_id}"
            "/requirements/test_report/evidence"
        ),
        files={"file": ("test-report.txt", b"new evidence", "text/plain")},
        data={"uploaded_by": "刘凯旗"},
    )

    report = client.get(
        f"/api/v1/registration-applications/{application_id}/precheck-report"
    )
    assert report.status_code == 200
    assert report.json()["is_stale"] is True

    pdf = client.get(
        f"/api/v1/registration-applications/{application_id}/precheck-report.pdf"
    )
    assert pdf.status_code == 409
    assert "重新执行预审" in pdf.json()["detail"]
