from __future__ import annotations

import io

from openpyxl import Workbook

from app.food_library import parse_tsv
from app.import_files import parse_csv_bytes, parse_xlsx_bytes
from app.main import valid_barcode
from app.nutrition_capture import parse_nutrition_text


def test_csv_utf8_bom_and_aliases() -> None:
    data = "\ufeffProduct,Brand,Serving Size,Unit,kcal,Protein (g)\nExample,Brand,40,g,100,4\n".encode()
    parsed = parse_csv_bytes(data, "foods.csv")
    assert parsed.rows[0]["name"] == "Example"
    assert parsed.rows[0]["protein_g"] == 4.0
    assert parsed.rows[0]["_valid"] is True


def test_csv_detects_semicolon_delimiter() -> None:
    parsed = parse_csv_bytes(b"name;calories\nApple;52\n")
    assert parsed.rows[0]["name"] == "Apple"
    assert parsed.rows[0]["calories"] == 52.0


def test_xlsx_selects_non_empty_worksheet() -> None:
    workbook = Workbook()
    workbook.active.title = "Empty"
    foods = workbook.create_sheet("Foods")
    foods.append(["name", "calories"])
    foods.append(["Apple", 52])
    buffer = io.BytesIO(); workbook.save(buffer)
    parsed = parse_xlsx_bytes(buffer.getvalue(), "foods.xlsx", sheet_name="Foods")
    assert parsed.sheet_names == ["Foods"]
    assert parsed.selected_sheet == "Foods"
    assert parsed.rows[0]["name"] == "Apple"


def test_tsv_canonical_basis_defaults() -> None:
    text = "name\tnutrition_basis\tcalories\nCereal\tper_100g\t370\n"
    _, _, rows = parse_tsv(text)
    assert rows[0]["canonical_quantity"] == 100.0
    assert rows[0]["canonical_unit"] == "g"


def test_ocr_parses_australian_panel_and_warns() -> None:
    extraction = parse_nutrition_text("""
Nutrition Information
Serving size 40 g
Servings per package 10
Energy 620 kJ
Protein 4.0 g
Total Fat 3.0 g
Saturated 1.0 g
Carbohydrate 25.0 g
Sugars 8.0 g
Dietary Fibre 3.0 g
Sodium 180 mg
""")
    assert extraction.values["serving_size"] == 40.0
    assert extraction.values["energy_kj"] == 620.0
    assert extraction.values["protein_g"] == 4.0
    assert extraction.values["sodium_mg"] == 180.0


def test_ocr_less_than_and_bad_relationship_warning() -> None:
    extraction = parse_nutrition_text("Total Fat <1 g\nSaturated Fat 2 g\nCarbohydrate 3 g\nSugars 5 g")
    assert extraction.values["fat_g"] == 0.5
    assert "Saturated fat exceeds total fat" in extraction.warnings
    assert "Sugars exceed total carbohydrate" in extraction.warnings


def test_valid_ean13_and_invalid_checksum() -> None:
    assert valid_barcode("9300675010781") is True
    assert valid_barcode("9300675010782") is False
