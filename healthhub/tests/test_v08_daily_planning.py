from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.start import app

client = TestClient(app)


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def create_profile(name: str = "Alex Example") -> str:
    response = client.post(
        "/api/v1/profiles",
        json={
            "display_name": name,
            "daily_calorie_target": 1800,
            "weekly_exercise_minutes_target": 150,
            "exercise_credit_mode": "none",
            "exercise_credit_percentage": 0,
            "nutrition_display_mode": "detailed",
            "timezone": "Australia/Melbourne",
            "measurement_units": "metric",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_food(name: str = "Example Yoghurt", calories: float = 100) -> str:
    response = client.post(
        "/api/v1/foods",
        json={
            "name": name,
            "brand": "Fixture Foods",
            "kind": "food",
            "serving_name": "170 g tub",
            "serving_grams": 170,
            "energy_kj": 420,
            "calories": calories,
            "protein_g": 12,
            "carbohydrates_g": 8,
            "fat_g": 2,
            "sugar_g": 6,
            "source": "manual",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_daily_plan_separates_consumed_and_planned() -> None:
    profile_id = create_profile()
    food_id = create_food()
    client.post(
        f"/api/v1/profiles/{profile_id}/diary",
        json={"food_id": food_id, "meal_period": "breakfast", "consumed_at": "2026-08-25T08:00:00+10:00", "servings": 1},
    )
    client.post(
        f"/api/v1/profiles/{profile_id}/planned",
        json={"food_id": food_id, "meal_period": "afternoon_snack", "planned_for": "2026-08-25T15:00:00+10:00", "servings": 2},
    )
    response = client.get(f"/api/v1/profiles/{profile_id}/day-plan?day=2026-08-25")
    assert response.status_code == 200
    payload = response.json()
    assert payload["consumed_calories"] == 100
    assert payload["planned_calories"] == 200
    assert payload["remaining_after_planned"] == 1500
    assert len(payload["consumed"]) == 1
    assert len(payload["planned"]) == 1


def test_planned_serving_edit_scales_snapshot() -> None:
    profile_id = create_profile()
    food_id = create_food()
    planned = client.post(
        f"/api/v1/profiles/{profile_id}/planned",
        json={"food_id": food_id, "meal_period": "lunch", "planned_for": "2026-08-25T12:00:00+10:00", "servings": 1},
    ).json()
    updated = client.patch(f"/api/v1/profiles/{profile_id}/planned/{planned['id']}", json={"servings": 1.5, "meal_period": "dinner"})
    assert updated.status_code == 200
    assert updated.json()["calories"] == 150
    assert updated.json()["protein_g"] == 18
    assert updated.json()["meal_period"] == "dinner"


def test_copy_day_creates_planned_snapshots_for_future_date() -> None:
    profile_id = create_profile()
    food_id = create_food()
    client.post(
        f"/api/v1/profiles/{profile_id}/diary",
        json={"food_id": food_id, "meal_period": "breakfast", "consumed_at": "2026-08-25T08:00:00+10:00", "servings": 1},
    )
    copied = client.post(f"/api/v1/profiles/{profile_id}/copy-day", json={"source_date": "2026-08-25", "target_date": "2026-08-27"})
    assert copied.status_code == 201
    assert len(copied.json()) == 1
    assert copied.json()[0]["status"] == "planned"
    assert copied.json()[0]["food_name"] == "Example Yoghurt"


def test_saved_meal_is_profile_scoped_and_plans_items() -> None:
    profile_id = create_profile()
    other_profile = create_profile("Second profile")
    yoghurt = create_food()
    toast = create_food("Toast", 220)
    created = client.post(
        f"/api/v1/profiles/{profile_id}/saved-meals",
        json={"name": "Usual Breakfast", "default_meal_period": "breakfast", "items": [{"food_id": yoghurt, "servings": 1}, {"food_id": toast, "servings": 2}]},
    )
    assert created.status_code == 201
    assert len(created.json()["items"]) == 2
    assert client.get(f"/api/v1/profiles/{other_profile}/saved-meals").json() == []
    planned = client.post(
        f"/api/v1/profiles/{profile_id}/saved-meals/{created.json()['id']}/plan",
        json={"food_id": yoghurt, "meal_period": "breakfast", "planned_for": "2026-08-26T08:00:00+10:00", "servings": 1},
    )
    assert planned.status_code == 201
    assert sorted(item["calories"] for item in planned.json()) == [100, 440]


def test_historical_diary_snapshot_is_not_rewritten_by_food_edit() -> None:
    profile_id = create_profile()
    food_id = create_food()
    logged = client.post(
        f"/api/v1/profiles/{profile_id}/diary",
        json={"food_id": food_id, "meal_period": "breakfast", "consumed_at": datetime.now(timezone.utc).isoformat(), "servings": 1},
    )
    assert logged.status_code == 201
    client.patch(f"/api/v1/foods/{food_id}", json={"calories": 999})
    day = datetime.now(ZoneInfo("Australia/Melbourne")).date().isoformat()
    diary = client.get(f"/api/v1/profiles/{profile_id}/diary?day={day}")
    assert diary.status_code == 200
    assert diary.json()[0]["calories"] == 100
