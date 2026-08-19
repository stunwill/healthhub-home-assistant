from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_tsv_preview_maps_aliases_and_ignores_empty_rows() -> None:
    response = client.post("/api/v1/foods/import/preview", json={"tsv": "Product\tkcal\tProtein (g)\tServing Unit\nTim Tam\t95\t1.2\tbiscuit\n\t\t\t\n"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_rows"] == 1
    assert payload["valid_rows"] == 1
    assert payload["mappings"]["name"] == "Product"
    assert payload["mappings"]["calories"] == "kcal"


def test_import_allows_valid_rows_when_another_row_is_invalid() -> None:
    response = client.post("/api/v1/foods/import/preview", json={"tsv": "name\tserving_size\tserving_unit\tcalories\nValid food\t1\titem\t10\nBroken food\t1\titem\tnope"})
    assert response.status_code == 200
    preview = response.json()
    assert preview["valid_rows"] == 1
    assert preview["invalid_rows"] == 1
    committed = client.post("/api/v1/foods/import/commit", json={"rows": preview["rows"], "duplicate_action": "skip"})
    assert committed.status_code == 200
    assert committed.json()["created"] == 1
    assert committed.json()["rejected"] == 1


def test_composite_food_calculates_component_nutrition() -> None:
    first = client.post("/api/v1/foods", json={"name": "Bread", "serving_name": "1 slice", "serving_unit": "slice", "calories": 90, "source": "manual"})
    second = client.post("/api/v1/foods", json={"name": "Honey", "serving_name": "10 g", "serving_unit": "g", "calories": 30, "source": "manual"})
    response = client.post("/api/v1/foods/composite", json={"name": "Toast with honey", "components": [{"food_id": first.json()["id"], "quantity": 1, "unit": "slice"}, {"food_id": second.json()["id"], "quantity": 1, "unit": "serving"}]})
    assert response.status_code == 201
    assert response.json()["calories"] == 120
