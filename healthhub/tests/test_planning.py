from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.start import app

client = TestClient(app)


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    Path("./test-active-profile.json").unlink(missing_ok=True)


def create_profile() -> str:
    response = client.post(
        "/api/v1/profiles",
        json={
            "display_name": "Planning Example",
            "daily_calorie_target": 1800,
            "weekly_exercise_minutes_target": 150,
            "exercise_credit_mode": "none",
            "exercise_credit_percentage": 0,
            "nutrition_display_mode": "balanced",
            "timezone": "Australia/Melbourne",
            "measurement_units": "metric",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_food() -> str:
    response = client.post(
        "/api/v1/foods",
        json={
            "name": "Planning Toast",
            "kind": "food",
            "serving_name": "2 slices",
            "calories": 220,
            "protein_g": 8,
            "carbohydrates_g": 35,
            "fat_g": 5,
            "favourite": False,
            "source": "test",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_plan_then_consume_creates_diary_snapshot() -> None:
    profile_id = create_profile()
    food_id = create_food()

    planned = client.post(
        f"/api/v1/profiles/{profile_id}/planned",
        json={
            "food_id": food_id,
            "meal_period": "breakfast",
            "planned_for": "2026-08-13T08:00:00+10:00",
            "servings": 1.5,
        },
    )
    assert planned.status_code == 201
    assert planned.json()["status"] == "planned"
    assert planned.json()["calories"] == 330

    entry_id = planned.json()["id"]
    consumed = client.post(f"/api/v1/profiles/{profile_id}/planned/{entry_id}/consume")
    assert consumed.status_code == 200
    assert consumed.json()["status"] == "consumed"
    assert consumed.json()["consumed_diary_entry_id"]

    diary = client.get(f"/api/v1/profiles/{profile_id}/diary?day=2026-08-13")
    assert diary.status_code == 200
    assert len(diary.json()) == 1
    assert diary.json()[0]["food_name"] == "Planning Toast"
    assert diary.json()[0]["calories"] == 330


def test_skip_planned_entry_does_not_create_diary_entry() -> None:
    profile_id = create_profile()
    food_id = create_food()
    planned = client.post(
        f"/api/v1/profiles/{profile_id}/planned",
        json={
            "food_id": food_id,
            "meal_period": "lunch",
            "planned_for": "2026-08-14T12:00:00+10:00",
            "servings": 1,
        },
    )
    entry_id = planned.json()["id"]
    skipped = client.post(f"/api/v1/profiles/{profile_id}/planned/{entry_id}/skip")
    assert skipped.status_code == 200
    assert skipped.json()["status"] == "skipped"

    diary = client.get(f"/api/v1/profiles/{profile_id}/diary?day=2026-08-14")
    assert diary.status_code == 200
    assert diary.json() == []


def test_weekday_recurrence_materialises_only_weekdays() -> None:
    profile_id = create_profile()
    food_id = create_food()
    response = client.post(
        f"/api/v1/profiles/{profile_id}/recurrence",
        json={
            "food_id": food_id,
            "frequency": "weekdays",
            "meal_period": "breakfast",
            "servings": 1,
            "start_date": "2026-08-10",
            "end_date": "2026-08-16",
            "local_time": "07:30",
        },
    )
    assert response.status_code == 201

    planned = client.get(
        f"/api/v1/profiles/{profile_id}/planned?start=2026-08-10&days=7&include_completed=false"
    )
    assert planned.status_code == 200
    assert len(planned.json()) == 5


def test_weekly_plan_summarises_planned_and_consumed() -> None:
    profile_id = create_profile()
    food_id = create_food()
    client.post(
        f"/api/v1/profiles/{profile_id}/planned",
        json={
            "food_id": food_id,
            "meal_period": "dinner",
            "planned_for": "2026-08-12T18:00:00+10:00",
            "servings": 1,
        },
    )
    client.post(
        f"/api/v1/profiles/{profile_id}/diary",
        json={
            "food_id": food_id,
            "meal_period": "lunch",
            "consumed_at": "2026-08-11T12:00:00+10:00",
            "servings": 1,
        },
    )

    summary = client.get(f"/api/v1/profiles/{profile_id}/weekly-plan?start=2026-08-12")
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["start_date"] == str(date(2026, 8, 10))
    assert payload["end_date"] == str(date(2026, 8, 16))
    assert payload["planned_calories"] == 220
    assert payload["consumed_calories"] == 220


def test_planned_datetime_requires_timezone() -> None:
    profile_id = create_profile()
    food_id = create_food()
    response = client.post(
        f"/api/v1/profiles/{profile_id}/planned",
        json={
            "food_id": food_id,
            "meal_period": "snack",
            "planned_for": datetime(2026, 8, 15, 10, 0).isoformat(),
            "servings": 1,
        },
    )
    assert response.status_code == 422
