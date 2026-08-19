from __future__ import annotations

import csv
import io
import re
from typing import Any, Iterable, Mapping

IMPORT_FIELDS = [
    "name", "brand", "category", "serving_size", "serving_unit", "nutrition_basis", "canonical_quantity", "canonical_unit",
    "calories", "protein_g", "carbs_g", "fat_g", "saturated_fat_g", "sugar_g", "fibre_g", "sodium_mg", "calcium_mg",
    "iron_mg", "potassium_mg", "alcohol_g", "caffeine_mg", "notes",
]
ALIASES = {
    "name": {"name", "food", "food name", "product", "product name"},
    "brand": {"brand", "manufacturer"},
    "category": {"category", "type"},
    "serving_size": {"serving size", "servingsize", "serve size", "quantity"},
    "serving_unit": {"serving unit", "unit", "measure"},
    "nutrition_basis": {"nutrition basis", "basis", "nutrition_basis"},
    "canonical_quantity": {"canonical quantity", "basis quantity", "per quantity"},
    "canonical_unit": {"canonical unit", "basis unit", "per unit"},
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
NUMERIC_FIELDS = {"serving_size", "canonical_quantity", "calories", "protein_g", "carbs_g", "fat_g", "saturated_fat_g", "sugar_g", "fibre_g", "sodium_mg", "calcium_mg", "iron_mg", "potassium_mg", "alcohol_g", "caffeine_mg"}
VALID_BASES = {"per_serving", "per_100g", "per_100ml"}


def normalise_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower().replace("_", " "))


def detect_mappings(headers: list[str]) -> dict[str, str | None]:
    normalised = {normalise_header(header): header for header in headers}
    return {field: next((normalised[alias] for alias in aliases if alias in normalised), None) for field, aliases in ALIASES.items()}


def parse_rows(raw_rows: Iterable[Mapping[str, object]], detected: dict[str, str | None]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        if not any(str(value or "").strip() for value in raw.values()):
            continue
        row: dict[str, Any] = {"_valid": True, "_warnings": [], "_errors": []}
        for field, source_header in detected.items():
            value = raw.get(source_header or "") if source_header else ""
            row[field] = str(value).strip() if value is not None else ""
        if not row.get("name"):
            row["_valid"] = False
            row["_errors"].append("Food name is required")
        if not row.get("serving_size"):
            row["_warnings"].append("Serving size is missing")
        basis = str(row.get("nutrition_basis") or "per_serving").strip().lower().replace(" ", "_")
        if basis not in VALID_BASES:
            row["_valid"] = False
            row["_errors"].append("nutrition_basis must be per_serving, per_100g or per_100ml")
        row["nutrition_basis"] = basis
        if basis == "per_100g":
            row["canonical_quantity"] = row.get("canonical_quantity") or "100"
            row["canonical_unit"] = row.get("canonical_unit") or "g"
        elif basis == "per_100ml":
            row["canonical_quantity"] = row.get("canonical_quantity") or "100"
            row["canonical_unit"] = row.get("canonical_unit") or "mL"
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
        fat = row.get("fat_g")
        saturated = row.get("saturated_fat_g")
        carbs = row.get("carbs_g")
        sugar = row.get("sugar_g")
        if isinstance(fat, float) and isinstance(saturated, float) and saturated > fat:
            row["_warnings"].append("Saturated fat exceeds total fat")
        if isinstance(carbs, float) and isinstance(sugar, float) and sugar > carbs:
            row["_warnings"].append("Sugars exceed total carbohydrate")
        row["_duplicate"] = False
        rows.append(row)
    return rows


def parse_tsv(text: str, mappings: dict[str, str] | None = None) -> tuple[list[str], dict[str, str | None], list[dict[str, Any]]]:
    reader = csv.DictReader(io.StringIO(text), dialect="excel-tab")
    headers = list(reader.fieldnames or [])
    detected = detect_mappings(headers)
    if mappings:
        detected.update({field: header for field, header in mappings.items() if field in IMPORT_FIELDS})
    return headers, detected, parse_rows(reader, detected)


def nutrition_from_components(components: list[tuple[dict[str, float | None], float]]) -> dict[str, float | None]:
    values: dict[str, float | None] = {}
    fields = ["calories", "protein_g", "carbohydrates_g", "fat_g", "saturated_fat_g", "sugar_g", "fibre_g", "sodium_mg", "calcium_mg", "iron_mg", "potassium_mg", "cholesterol_mg", "alcohol_g", "caffeine_mg"]
    for field in fields:
        present = [data.get(field) for data, _ in components if data.get(field) is not None]
        values[field] = round(sum(float(value) * quantity for (data, quantity), value in zip(components, [data.get(field) for data, _ in components]) if value is not None), 2) if present else None
    return values
