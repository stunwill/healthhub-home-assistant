from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class NutritionExtraction:
    values: dict[str, float | str | None] = field(default_factory=dict)
    confidence: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    raw_text: str = ""


def _clean(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("–", "-").replace("—", "-")
    text = re.sub(r"(?<=\d)[Oo](?=\d|\s*(?:g|mg|kj|kcal))", "0", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=\d)[lI](?=\d|[.,])", "1", text)
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    return re.sub(r"[ \t]+", " ", text)


def _number(value: str) -> float:
    if re.match(r"^(?:<|less\s+than)\s*1", value, flags=re.IGNORECASE):
        return 0.5
    return float(re.sub(r"[^0-9.]", "", value))


def _extract_value(lines: Iterable[str], labels: tuple[str, ...], unit: str) -> tuple[float | None, str]:
    label_pattern = "|".join(re.escape(label) for label in labels)
    pattern = re.compile(rf"(?:{label_pattern})[^0-9<]*(<\s*1|less\s+than\s+1|\d+(?:\.\d+)?)\s*{unit}\b", re.IGNORECASE)
    for line in lines:
        match = pattern.search(line)
        if match:
            return _number(match.group(1)), "high"
    return None, "unknown"


def parse_nutrition_text(text: str) -> NutritionExtraction:
    cleaned = _clean(text)
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    extraction = NutritionExtraction(raw_text=text)

    serving_match = re.search(r"serving\s+size[^0-9]*(\d+(?:\.\d+)?)\s*(g|ml)\b", cleaned, flags=re.IGNORECASE)
    if serving_match:
        extraction.values["serving_size"] = float(serving_match.group(1))
        extraction.values["serving_unit"] = serving_match.group(2).lower()
        extraction.confidence["serving_size"] = "high"

    servings_match = re.search(r"servings?\s+per\s+(?:package|pack)[^0-9]*(\d+(?:\.\d+)?)", cleaned, flags=re.IGNORECASE)
    if servings_match:
        extraction.values["servings_per_package"] = float(servings_match.group(1))
        extraction.confidence["servings_per_package"] = "high"

    fields = {
        "protein_g": (("protein",), "g"),
        "fat_g": (("total fat", "fat"), "g"),
        "saturated_fat_g": (("saturated", "saturated fat"), "g"),
        "carbohydrates_g": (("carbohydrate", "carbohydrates", "total carbohydrate"), "g"),
        "sugar_g": (("sugars", "sugar"), "g"),
        "fibre_g": (("dietary fibre", "dietary fiber", "fibre", "fiber"), "g"),
        "sodium_mg": (("sodium",), "mg"),
        "calcium_mg": (("calcium",), "mg"),
        "iron_mg": (("iron",), "mg"),
        "potassium_mg": (("potassium",), "mg"),
        "cholesterol_mg": (("cholesterol",), "mg"),
        "caffeine_mg": (("caffeine",), "mg"),
        "alcohol_g": (("alcohol",), "g"),
    }
    for field_name, (labels, unit) in fields.items():
        value, confidence = _extract_value(lines, labels, unit)
        extraction.values[field_name] = value
        extraction.confidence[field_name] = confidence

    energy_kj, kj_confidence = _extract_value(lines, ("energy",), "kj")
    calories, kcal_confidence = _extract_value(lines, ("energy", "calories"), "kcal")
    extraction.values["energy_kj"] = energy_kj
    extraction.values["calories"] = calories if calories is not None else (round(energy_kj / 4.184, 1) if energy_kj is not None else None)
    extraction.confidence["energy_kj"] = kj_confidence
    extraction.confidence["calories"] = kcal_confidence if calories is not None else ("needs_review" if energy_kj is not None else "unknown")

    lower = cleaned.lower()
    extraction.values["nutrition_basis"] = "per_100ml" if "per 100 ml" in lower or "per 100ml" in lower else "per_100g" if "per 100 g" in lower or "per 100g" in lower else "per_serving"

    fat = extraction.values.get("fat_g")
    saturated = extraction.values.get("saturated_fat_g")
    carbs = extraction.values.get("carbohydrates_g")
    sugar = extraction.values.get("sugar_g")
    if isinstance(fat, float) and isinstance(saturated, float) and saturated > fat:
        extraction.warnings.append("Saturated fat exceeds total fat")
    if isinstance(carbs, float) and isinstance(sugar, float) and sugar > carbs:
        extraction.warnings.append("Sugars exceed total carbohydrate")
    calories_value = extraction.values.get("calories")
    if energy_kj is not None and isinstance(calories_value, float):
        expected = energy_kj / 4.184
        if expected and abs(calories_value - expected) / expected > 0.12:
            extraction.warnings.append("kJ and kcal values do not reconcile closely")
    sodium_value = extraction.values.get("sodium_mg")
    if isinstance(sodium_value, float) and sodium_value > 50000:
        extraction.warnings.append("Sodium value is unusually high; verify mg/g units")
    return extraction


def validate_nutrition_consistency(values: dict[str, float | None]) -> list[str]:
    warnings: list[str] = []
    saturated = values.get("saturated_fat_g")
    fat = values.get("fat_g")
    sugar = values.get("sugar_g")
    carbohydrates = values.get("carbohydrates_g")
    if saturated is not None and fat is not None and saturated > fat:
        warnings.append("Saturated fat exceeds total fat")
    if sugar is not None and carbohydrates is not None and sugar > carbohydrates:
        warnings.append("Sugars exceed total carbohydrate")
    kj = values.get("energy_kj")
    kcal = values.get("calories")
    if kj and kcal and abs(kcal - (kj / 4.184)) / max(kcal, 1) > 0.12:
        warnings.append("kJ and kcal values differ more than expected")
    return warnings
