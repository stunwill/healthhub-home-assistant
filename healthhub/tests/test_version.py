from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_version_endpoint_reports_v0_2_api() -> None:
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    assert response.json()["api_versions"] == ["v1"]
