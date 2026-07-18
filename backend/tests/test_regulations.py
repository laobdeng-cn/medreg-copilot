from datetime import date

from fastapi.testclient import TestClient

from medreg.main import app

client = TestClient(app)


def source_payload() -> dict:
    return {
        "title": "医疗器械注册与备案管理办法",
        "issuing_authority": "国家市场监督管理总局",
        "jurisdiction": "CN",
        "regulation_type": "regulation",
        "scope_summary": "境内医疗器械注册与备案管理通用规章。",
        "initial_version": {
            "version_label": "2021版",
            "document_number": "国家市场监督管理总局令第47号",
            "official_url": "https://www.samr.gov.cn/example",
            "published_on": "2021-08-31",
            "effective_on": "2021-10-01",
            "expires_on": None,
        },
    }


def test_registered_version_requires_review_before_applying() -> None:
    response = client.post("/api/v1/regulation-sources", json=source_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["code"].startswith(f"REG-{date.today().year}-")
    assert body["versions"][0]["review_status"] == "pending_review"
    assert body["versions"][0]["lifecycle_status"] == "effective"
    assert body["applicable_version"] is None

    review_response = client.post(
        f"/api/v1/regulation-sources/{body['id']}/versions/{body['versions'][0]['id']}/review",
        json={
            "decision": "verified",
            "reviewed_by": "刘凯旗",
            "note": "已对照官方发布页面核验。",
        },
    )

    assert review_response.status_code == 200
    reviewed = review_response.json()
    assert reviewed["versions"][0]["review_status"] == "verified"
    assert reviewed["applicable_version"]["id"] == body["versions"][0]["id"]


def test_as_of_date_excludes_future_version() -> None:
    response = client.post("/api/v1/regulation-sources", json=source_payload())
    body = response.json()
    client.post(
        f"/api/v1/regulation-sources/{body['id']}/versions/{body['versions'][0]['id']}/review",
        json={
            "decision": "verified",
            "reviewed_by": "刘凯旗",
            "note": "已核验官方来源。",
        },
    )

    list_response = client.get("/api/v1/regulation-sources?as_of=2021-09-30")

    assert list_response.status_code == 200
    item = list_response.json()["items"][0]
    assert item["versions"][0]["lifecycle_status"] == "upcoming"
    assert item["applicable_version"] is None


def test_new_version_stays_pending_until_reviewed() -> None:
    created = client.post("/api/v1/regulation-sources", json=source_payload()).json()

    response = client.post(
        f"/api/v1/regulation-sources/{created['id']}/versions?as_of=2027-01-01",
        json={
            "version_label": "2026修订版",
            "document_number": "国家市场监督管理总局令第99号",
            "official_url": "https://www.samr.gov.cn/example-2026",
            "published_on": "2026-08-01",
            "effective_on": "2026-10-01",
            "expires_on": None,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert len(body["versions"]) == 2
    assert body["versions"][0]["version_label"] == "2026修订版"
    assert body["versions"][0]["review_status"] == "pending_review"
    assert body["applicable_version"] is None

    duplicate = client.post(
        f"/api/v1/regulation-sources/{created['id']}/versions",
        json={
            "version_label": "2026修订版",
            "document_number": "国家市场监督管理总局令第100号",
            "official_url": "https://www.samr.gov.cn/example-duplicate",
            "published_on": "2026-09-01",
            "effective_on": "2026-11-01",
            "expires_on": None,
        },
    )
    assert duplicate.status_code == 409


def test_invalid_version_date_range_is_rejected() -> None:
    payload = source_payload()
    payload["initial_version"]["expires_on"] = "2021-09-01"

    response = client.post("/api/v1/regulation-sources", json=payload)

    assert response.status_code == 422
