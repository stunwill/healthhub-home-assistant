from pathlib import Path

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    Path("./test-active-profile.json").unlink(missing_ok=True)


def profile_payload() -> dict:
    return {
        "display_name": "Alex Example",
        "daily_calorie_target": 1800,
        "weekly_exercise_minutes_target": 150,
        "exercise_credit_mode": "percentage",
        "exercise_credit_percentage": 50,
        "nutrition_display_mode": "balanced",
        "timezone": "Australia/Melbourne",
        "measurement_units": "metric",
    }


def test_profile_crud_and_active_selection() -> None:
    created = client.post("/api/v1/profiles", json=profile_payload())
    assert created.status_code == 201
    profile_id = created.json()["id"]

    listed = client.get("/api/v1/profiles")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = client.patch(f"/api/v1/profiles/{profile_id}", json={"daily_calorie_target": 1900})
    assert updated.status_code == 200
    assert updated.json()["daily_calorie_target"] == 1900

    selected = client.put("/api/v1/active-profile", json={"profile_id": profile_id})
    assert selected.status_code == 200
    assert selected.json()["profile_id"] == profile_id

    archived = client.post(f"/api/v1/profiles/{profile_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["archived"] is True


def test_rejects_invalid_credit_settings() -> None:
    payload = profile_payload()
    payload["exercise_credit_mode"] = "none"
    payload["exercise_credit_percentage"] = 50
    response = client.post("/api/v1/profiles", json=payload)
    assert response.status_code == 422
