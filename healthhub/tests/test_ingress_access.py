from pathlib import Path

from fastapi.testclient import TestClient

from app.start import app


def test_runtime_does_not_enable_custom_ingress_ip_filter() -> None:
    script = Path("run.sh").read_text(encoding="utf-8")
    assert "HEALTHHUB_ENFORCE_INGRESS" not in script


def test_forwarded_lan_client_is_allowed_through_home_assistant_ingress(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("HEALTHHUB_ENFORCE_INGRESS", raising=False)
    client = TestClient(app, client=("192.168.0.50", 12345))
    response = client.get("/api/v1/health")
    assert response.status_code == 200
