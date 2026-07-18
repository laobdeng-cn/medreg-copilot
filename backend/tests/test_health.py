from fastapi.testclient import TestClient

from medreg.main import app


def test_health_reports_current_milestone() -> None:
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "medreg-api",
        "milestone": "M5",
        "storage": "postgresql+minio+redis+qdrant+neo4j",
    }


def test_local_frontend_origin_is_allowed() -> None:
    response = TestClient(app).options(
        "/api/v1/health",
        headers={
            "Origin": "http://127.0.0.1:5273",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5273"
