from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.start import app

client = TestClient(app)


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    Path("./test-active-profile.json").unlink(missing_ok=True)


def create_profile(*, credit_mode: str = "percentage", percentage: int = 50) -> str:
    response = client.post(
        "/api/v1/profiles",
        json={
            "display_name": "Activity Example",
            "starting_weight_kg": 80,
            "goal_weight_kg": 75,
            "daily_calorie_target": 1800,
            "weekly_exercise_minutes_target": 150,
            "hydration_target_ml": 2000,
            "exercise_credit_mode": credit_mode,
            "exercise_credit_percentage": percentage,
            "nutrition_display_mode": "balanced",
            "nutrition_display_fields": ["calories", "sugar"],
            "timezone": "Australia/Melbourne",
            "measurement_units": "metric",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["nutrition_display_fields"] == ["calories", "sugar"]
    return payload["id"]


def create_food() -> str:
    response = client.post(
        "/api/v1/foods",
        json={
            "name": "Activity Test Meal",
            "kind": "food",
            "serving_name": "1 serve",
            "calories": 600,
            "protein_g": 30,
            "carbohydrates_g": 60,
            "fat_g": 20,
            "sugar_g": 12,
            "favourite": False,
            "source": "test",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_exercise_hydration_and_sugar_flow_into_daily_summary() -> None:
    profile_id = create_profile()
    food_id = create_food()
    diary = client.post(
        f"/api/v1/profiles/{profile_id}/diary",
        json={
            "food_id": food_id,
            "meal_period": "lunch",
            "consumed_at": "2026-08-13T12:00:00+10:00",
            "servings": 2,
        },
    )
    assert diary.status_code == 201
    assert diary.json()["sugar_g"] == 24

    exercise = client.post(
        f"/api/v1/profiles/{profile_id}/exercise",
        json={
            "activity_name": "Brisk walk",
            "duration_minutes": 40,
            "calories_burned": 300,
            "completed_at": "2026-08-13T17:30:00+10:00",
        },
    )
    assert exercise.status_code == 201

    water = client.post(
        f"/api/v1/profiles/{profile_id}/water",
        json={"amount_ml": 500, "consumed_at": "2026-08-13T14:00:00+10:00"},
    )
    assert water.status_code == 201

    summary = client.get(f"/api/v1/profiles/{profile_id}/daily-summary?day=2026-08-13")
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["consumed_calories"] == 1200
    assert payload["completed_exercise_calories"] == 300
    assert payload["credited_exercise_calories"] == 150
    assert payload["exercise_minutes"] == 40
    assert payload["remaining_calories"] == 750
    assert payload["hydration_ml"] == 500
    assert payload["hydration_target_ml"] == 2000
    assert payload["sugar_g"] == 24


def test_no_credit_mode_does_not_add_exercise_calories() -> None:
    profile_id = create_profile(credit_mode="none", percentage=0)
    client.post(
        f"/api/v1/profiles/{profile_id}/exercise",
        json={
            "activity_name": "Cycling",
            "duration_minutes": 30,
            "calories_burned": 250,
            "completed_at": "2026-08-13T07:00:00+10:00",
        },
    )
    summary = client.get(f"/api/v1/profiles/{profile_id}/daily-summary?day=2026-08-13")
    assert summary.status_code == 200
    assert summary.json()["credited_exercise_calories"] == 0
    assert summary.json()["remaining_calories"] == 1800


def test_weight_and_progress_summary() -> None:
    profile_id = create_profile()
    first = client.post(
        f"/api/v1/profiles/{profile_id}/weights",
        json={"weight_kg": 79.5, "measured_at": "2026-08-10T07:30:00+10:00"},
    )
    second = client.post(
        f"/api/v1/profiles/{profile_id}/weights",
        json={"weight_kg": 78.8, "measured_at": "2026-08-12T07:30:00+10:00"},
    )
    assert first.status_code == 201
    assert second.status_code == 201

    progress = client.get(f"/api/v1/profiles/{profile_id}/progress?days=730")
    assert progress.status_code == 200
    payload = progress.json()
    assert payload["latest_weight_kg"] == 78.8
    assert payload["starting_weight_kg"] == 80
    assert payload["goal_weight_kg"] == 75
    assert payload["change_from_start_kg"] == -1.2
    assert payload["hydration_target_ml"] == 2000
    assert len(payload["weight_entries"]) == 2


def test_water_crud_and_timestamp_validation() -> None:
    profile_id = create_profile()
    invalid = client.post(
        f"/api/v1/profiles/{profile_id}/water",
        json={"amount_ml": 250, "consumed_at": "2026-08-13T08:00:00"},
    )
    assert invalid.status_code == 422

    created = client.post(
        f"/api/v1/profiles/{profile_id}/water",
        json={"amount_ml": 250, "consumed_at": "2026-08-13T08:00:00+10:00"},
    )
    assert created.status_code == 201
    entry_id = created.json()["id"]
    listed = client.get(f"/api/v1/profiles/{profile_id}/water?day=2026-08-13")
    assert listed.status_code == 200
    assert listed.json()[0]["amount_ml"] == 250
    deleted = client.delete(f"/api/v1/profiles/{profile_id}/water/{entry_id}")
    assert deleted.status_code == 204


def test_activity_timestamps_require_timezone() -> None:
    profile_id = create_profile()
    exercise = client.post(
        f"/api/v1/profiles/{profile_id}/exercise",
        json={"activity_name": "Walk", "duration_minutes": 20, "calories_burned": 100, "completed_at": "2026-08-13T18:00:00"},
    )
    weight = client.post(
        f"/api/v1/profiles/{profile_id}/weights",
        json={"weight_kg": 79, "measured_at": "2026-08-13T08:00:00"},
    )
    assert exercise.status_code == 422
    assert weight.status_code == 422
