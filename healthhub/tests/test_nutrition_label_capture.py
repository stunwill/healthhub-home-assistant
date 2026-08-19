from __future__ import annotations

import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.database import Base, engine
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    capture_dir = Path("./test-captures")
    if capture_dir.exists():
        for path in capture_dir.iterdir():
            path.unlink()


def valid_png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_label_upload_requires_review_before_food_save() -> None:
    uploaded = client.post(
        "/api/v1/capture/nutrition-label",
        files={"image": ("label.png", valid_png_bytes(), "image/png")},
    )
    assert uploaded.status_code == 202
    payload = uploaded.json()
    assert payload["review_required"] is True
    assert isinstance(payload["extraction"], dict)
    assert payload["status"] == "awaiting_review"

    rejected = client.post(
        "/api/v1/capture/nutrition-label/review",
        json={
            "upload_id": payload["upload_id"],
            "name": "Example Cereal",
            "serving_name": "40 g serve",
            "serving_grams": 40,
            "energy_kj": 620,
            "calories": 148,
            "protein_g": 4,
            "carbohydrates_g": 27,
            "fat_g": 2,
            "reviewed": False,
        },
    )
    assert rejected.status_code == 422

    saved = client.post(
        "/api/v1/capture/nutrition-label/review",
        json={
            "upload_id": payload["upload_id"],
            "name": "Example Cereal",
            "brand": "Fixture Foods",
            "kind": "food",
            "serving_name": "40 g serve",
            "serving_grams": 40,
            "energy_kj": 620,
            "calories": 148,
            "protein_g": 4,
            "carbohydrates_g": 27,
            "fat_g": 2,
            "reviewed": True,
        },
    )
    assert saved.status_code == 201
    assert saved.json()["source"] == "packaging_label"
    assert saved.json()["verification_status"] == "verified"
    assert saved.json()["calories"] == 148


def test_label_upload_rejects_invalid_image_bytes() -> None:
    response = client.post(
        "/api/v1/capture/nutrition-label",
        files={"image": ("label.png", b"not-an-image", "image/png")},
    )
    assert response.status_code == 422


def test_label_upload_rejects_unsupported_file_type() -> None:
    response = client.post(
        "/api/v1/capture/nutrition-label",
        files={"image": ("label.txt", b"not-an-image", "text/plain")},
    )
    assert response.status_code == 415
