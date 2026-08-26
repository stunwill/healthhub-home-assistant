from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from app.database import Base, engine
from app.start import app

client = TestClient(app)


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    capture_dir = Path("./test-captures")
    if capture_dir.exists():
        for path in capture_dir.iterdir():
            path.unlink()


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def create_profile(name: str = "Image Capture User") -> str:
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


def capture_images(count: int = 1) -> dict:
    with patch(
        "app.v081_capture.pytesseract.image_to_string",
        return_value="Energy 420 kJ\nProtein 10 g\n",
    ), patch(
        "app.v081_capture.pytesseract.image_to_data",
        return_value={"conf": ["90"]},
    ):
        response = client.post(
            "/api/v1/capture/nutrition-labels",
            files=[
                ("images", (f"label-{index}.png", png_bytes(), "image/png"))
                for index in range(count)
            ],
        )
    assert response.status_code == 202
    return response.json()


def test_multi_image_capture_merges_independent_ocr_results() -> None:
    with patch(
        "app.v081_capture.pytesseract.image_to_string",
        side_effect=[
            "Serving size 40 g\nEnergy 620 kJ\nProtein 4 g\n",
            "Carbohydrate 27 g\nSugars 8 g\nFat 2 g\n",
        ],
    ), patch(
        "app.v081_capture.pytesseract.image_to_data",
        return_value={"conf": ["90", "91", "92"]},
    ):
        response = client.post(
            "/api/v1/capture/nutrition-labels",
            files=[
                ("images", ("front.png", png_bytes(), "image/png")),
                ("images", ("nutrition.png", png_bytes(), "image/png")),
            ],
        )
    assert response.status_code == 202
    payload = response.json()
    assert len(payload["images"]) == 2
    assert payload["extraction"]["serving_size"] == 40
    assert payload["extraction"]["protein_g"] == 4
    assert payload["extraction"]["carbohydrates_g"] == 27
    assert payload["extraction"]["sugar_g"] == 8
    assert payload["review_required"] is True


def test_multi_image_capture_rejects_invalid_image() -> None:
    response = client.post(
        "/api/v1/capture/nutrition-labels",
        files=[("images", ("bad.png", b"not-an-image", "image/png"))],
    )
    assert response.status_code == 422


def test_multi_image_capture_rejects_unsupported_type() -> None:
    response = client.post(
        "/api/v1/capture/nutrition-labels",
        files=[("images", ("label.txt", b"plain text", "text/plain"))],
    )
    assert response.status_code == 415


def test_review_and_add_preserves_selected_meal_context() -> None:
    profile_id = create_profile()
    upload_id = capture_images()["images"][0]["upload_id"]
    response = client.post(
        f"/api/v1/capture/nutrition-label/review-and-add?profile_id={profile_id}&day=2026-08-26&meal_period=lunch&mode=eaten&servings=1",
        json={
            "upload_id": upload_id,
            "name": "Captured Lunch",
            "kind": "food",
            "serving_name": "1 serve",
            "serving_unit": "serving",
            "nutrition_basis": "per_serving",
            "energy_kj": 420,
            "calories": 100,
            "protein_g": 10,
            "reviewed": True,
        },
    )
    assert response.status_code == 201
    day = client.get(f"/api/v1/profiles/{profile_id}/day-plan?day=2026-08-26").json()
    assert len(day["consumed"]) == 1
    assert day["consumed"][0]["meal_period"] == "lunch"
    assert day["consumed"][0]["food_name"] == "Captured Lunch"


def test_future_review_and_add_can_create_planned_entry() -> None:
    profile_id = create_profile()
    upload_id = capture_images()["images"][0]["upload_id"]
    response = client.post(
        f"/api/v1/capture/nutrition-label/review-and-add?profile_id={profile_id}&day=2026-08-28&meal_period=dinner&mode=planned&servings=1.5",
        json={
            "upload_id": upload_id,
            "name": "Captured Dinner",
            "kind": "food",
            "serving_name": "1 serve",
            "serving_unit": "serving",
            "nutrition_basis": "per_serving",
            "energy_kj": 420,
            "calories": 100,
            "reviewed": True,
        },
    )
    assert response.status_code == 201
    day = client.get(f"/api/v1/profiles/{profile_id}/day-plan?day=2026-08-28").json()
    assert len(day["planned"]) == 1
    assert day["planned"][0]["meal_period"] == "dinner"
    assert day["planned"][0]["calories"] == 150


def test_multi_image_files_are_removed_after_verified_save() -> None:
    profile_id = create_profile()
    capture = capture_images(2)
    first, second = [item["upload_id"] for item in capture["images"]]
    response = client.post(
        f"/api/v1/capture/nutrition-label/review-and-add?profile_id={profile_id}&day=2026-08-26&meal_period=breakfast&mode=eaten&upload_ids={second}",
        json={
            "upload_id": first,
            "name": "Captured Breakfast",
            "kind": "food",
            "serving_name": "1 serve",
            "serving_unit": "serving",
            "nutrition_basis": "per_serving",
            "calories": 100,
            "reviewed": True,
        },
    )
    assert response.status_code == 201
    assert client.get(f"/api/v1/capture/{first}/image").status_code == 404
    assert client.get(f"/api/v1/capture/{second}/image").status_code == 404


def test_captured_food_is_isolated_to_selected_profile_diary() -> None:
    first_profile = create_profile("First Profile")
    second_profile = create_profile("Second Profile")
    upload_id = capture_images()["images"][0]["upload_id"]
    response = client.post(
        f"/api/v1/capture/nutrition-label/review-and-add?profile_id={first_profile}&day=2026-08-26&meal_period=breakfast&mode=eaten",
        json={
            "upload_id": upload_id,
            "name": "Profile Food",
            "kind": "food",
            "serving_name": "1 serve",
            "serving_unit": "serving",
            "nutrition_basis": "per_serving",
            "calories": 100,
            "reviewed": True,
        },
    )
    assert response.status_code == 201
    first_day = client.get(f"/api/v1/profiles/{first_profile}/day-plan?day=2026-08-26").json()
    second_day = client.get(f"/api/v1/profiles/{second_profile}/day-plan?day=2026-08-26").json()
    assert len(first_day["consumed"]) == 1
    assert second_day["consumed"] == []
