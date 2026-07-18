from datetime import date

from fastapi.testclient import TestClient

from medreg.main import app
from medreg.modules.security.schemas import (
    DEMO_TENANT_ID,
    DEMO_VIEWER_ID,
)

client = TestClient(app)


def application_payload() -> dict[str, str]:
    return {
        "name": "租户权限边界测试项目",
        "product_name": "权限测试医疗器械",
        "applicant_name": "深圳示例医疗科技有限公司",
        "jurisdiction": "CN_NMPA",
        "device_class": "II",
        "application_type": "initial_registration",
        "regulation_effective_on": date.today().isoformat(),
        "owner_name": "刘凯旗",
    }


def test_security_workspace_exposes_membership_and_role_permissions() -> None:
    response = client.get("/api/v1/security/workspace")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == str(DEMO_TENANT_ID)
    assert body["current_actor"]["role"] == "owner"
    assert body["current_actor"]["permissions"] == [
        "read",
        "write",
        "review",
        "admin",
    ]
    assert len(body["members"]) == 4


def test_viewer_can_read_but_cannot_create_application() -> None:
    headers = {
        "X-Tenant-ID": str(DEMO_TENANT_ID),
        "X-Actor-ID": str(DEMO_VIEWER_ID),
    }

    list_response = client.get("/api/v1/registration-applications", headers=headers)
    create_response = client.post(
        "/api/v1/registration-applications",
        headers=headers,
        json=application_payload(),
    )

    assert list_response.status_code == 200
    assert create_response.status_code == 403
    assert "lacks 'write' permission" in create_response.json()["detail"]


def test_successful_write_is_available_in_immutable_audit_feed() -> None:
    create_response = client.post(
        "/api/v1/registration-applications",
        json=application_payload(),
    )
    audit_response = client.get("/api/v1/audit-events")

    assert create_response.status_code == 201
    assert audit_response.status_code == 200
    body = audit_response.json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "application.created"
    assert body["items"][0]["resource_id"] == create_response.json()["id"]
    assert body["items"][0]["actor_name"] == "刘凯旗"


def test_unknown_tenant_membership_is_rejected() -> None:
    response = client.get(
        "/api/v1/security/workspace",
        headers={"X-Tenant-ID": "99999999-9999-4999-8999-999999999999"},
    )

    assert response.status_code == 401
