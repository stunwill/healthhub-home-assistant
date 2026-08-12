from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def create_profile() -> str:
    response = client.post(
        "/api/v1/profiles",
        json={
            "display_name": "Alex Example",
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


def create_food() -> str:
    response = client.post(
        "/api/v1/foods",
        json={
            "name": "Example Yoghurt",
            "brand": "Fixture Foods",
            "kind": "food",
            "serving_name": "170 g tub",
            "serving_grams": 170,
            "energy_kj": 420,
            "calories": 100,
            "protein_g": 12,
            "carbohydrates_g": 8,
            "fat_g": 2,
            "source": "manual",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_food_search_and_diary_summary() -> None:
    profile_id = create_profile()
    food_id = create_food()

    search = client.get("/api/v1/quick-add/search", params={"q": "yoghurt"})
    assert search.status_code == 200
    local_result = next(item for item in search.json() if item["source"] == "healthhub")
    assert local_result["id"] == food_id
    assert local_result["calories"] == 100

    logged = client.post(
        f"/api/v1/profiles/{profile_id}/diary",
        json={
            "food_id": food_id,
            "meal_period": "breakfast",
            "consumed_at": datetime.now(timezone.utc).isoformat(),
            "servings": 1.5,
        },
    )
    assert logged.status_code == 201
    assert logged.json()["calories"] == 150
    assert logged.json()["protein_g"] == 18

    summary = client.get(f"/api/v1/profiles/{profile_id}/daily-summary")
    assert summary.status_code == 200
    assert summary.json()["consumed_calories"] == 150
    assert summary.json()["remaining_calories"] == 1650
    assert summary.json()["protein_g"] == 18
    assert summary.json()["entry_count"] == 1

    deleted = client.delete(f"/api/v1/profiles/{profile_id}/diary/{logged.json()['id']}")
    assert deleted.status_code == 204


def test_diary_rejects_archived_food() -> None:
    profile_id = create_profile()
    food_id = create_food()
    archived = client.post(f"/api/v1/foods/{food_id}/archive")
    assert archived.status_code == 200

    response = client.post(
        f"/api/v1/profiles/{profile_id}/diary",
        json={
            "food_id": food_id,
            "meal_period": "snack",
            "consumed_at": datetime.now(timezone.utc).isoformat(),
            "servings": 1,
        },
    )
    assert response.status_code == 409
