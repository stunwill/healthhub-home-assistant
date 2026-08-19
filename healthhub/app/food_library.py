from __future__ import annotations

import csv
import io
import re
from typing import Any

IMPORT_FIELDS = [
    "name", "brand", "category", "serving_size", "serving_unit", "calories", "protein_g", "carbs_g",
    "fat_g", "saturated_fat_g", "sugar_g", "fibre_g", "sodium_mg", "calcium_mg", "iron_mg",
    "potassium_mg", "alcohol_g", "caffeine_mg", "notes",
]
ALIASES = {
    "name": {"name", "food", "food name", "product", "product name"},
    "brand": {"brand", "manufacturer"},
    "category": {"category", "type"},
    "serving_size": {"serving size", "servingsize", "serve size", "quantity"},
    "serving_unit": {"serving unit", "unit", "measure"},
    "calories": {"calories", "cal", "kcal", "energy kcal", "energy"},
    "protein_g": {"protein", "protein g", "protein (g)"},
    "carbs_g": {"carbs", "carbohydrate", "carbohydrates", "carbs g", "carbohydrates (g)"},
    "fat_g": {"fat", "total fat", "fat g", "fat (g)"},
    "saturated_fat_g": {"saturated fat", "sat fat", "saturated fat g"},
    "sugar_g": {"sugar", "sugars", "sugar g", "sugars (g)"},
    "fibre_g": {"fibre", "fiber", "fibre g", "fiber g"},
    "sodium_mg": {"sodium", "sodium mg", "salt"},
    "calcium_mg": {"calcium", "calcium mg"},
    "iron_mg": {"iron", "iron mg"},
    "potassium_mg": {"potassium", "potassium mg"},
    "alcohol_g": {"alcohol", "alcohol g"},
    "caffeine_mg": {"caffeine", "caffeine mg"},
    "notes": {"notes", "note", "description"},
}
NUMERIC_FIELDS = set(IMPORT_FIELDS[5:-1])


def normalise_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower().replace("_", " "))


def detect_mappings(headers: list[str]) -> dict[str, str | None]:
    normalised = {normalise_header(header): header for header in headers}
    return {field: next((normalised[alias] for alias in aliases if alias in normalised), None) for field, aliases in ALIASES.items()}


def parse_tsv(text: str, mappings: dict[str, str] | None = None) -> tuple[list[str], dict[str, str | None], list[dict[str, Any]]]:
    reader = csv.DictReader(io.StringIO(text), dialect="excel-tab")
    headers = list(reader.fieldnames or [])
    detected = detect_mappings(headers)
    if mappings:
        detected.update({field: header for field, header in mappings.items() if field in IMPORT_FIELDS})
    rows: list[dict[str, Any]] = []
    for raw in reader:
        if not any(str(value or "").strip() for value in raw.values()):
            continue
        row: dict[str, Any] = {"_valid": True, "_warnings": [], "_errors": []}
        for field, source_header in detected.items():
            row[field] = (raw.get(source_header or "") or "").strip()
        if not row.get("name"):
            row["_valid"] = False
            row["_errors"].append("Food name is required")
        if not row.get("serving_size"):
            row["_warnings"].append("Serving size is missing")
        for field in NUMERIC_FIELDS:
            value = row.get(field, "")
            if value == "":
                row[field] = None
                continue
            try:
                number = float(str(value).replace(",", ""))
                if number < 0:
                    raise ValueError
                row[field] = number
            except ValueError:
                row["_valid"] = False
                row["_errors"].append(f"{field} must be a non-negative number")
        row["_duplicate"] = False
        rows.append(row)
    return headers, detected, rows


def nutrition_from_components(components: list[tuple[dict[str, float | None], float]]) -> dict[str, float | None]:
    values: dict[str, float | None] = {}
    fields = ["calories", "protein_g", "carbohydrates_g", "fat_g", "saturated_fat_g", "sugar_g", "fibre_g", "sodium_mg", "calcium_mg", "iron_mg", "potassium_mg", "cholesterol_mg", "alcohol_g", "caffeine_mg"]
    for field in fields:
        present = [data.get(field) for data, _ in components if data.get(field) is not None]
        values[field] = round(sum(float(value) * quantity for (data, quantity), value in zip(components, [data.get(field) for data, _ in components]) if value is not None), 2) if present else None
    return values
