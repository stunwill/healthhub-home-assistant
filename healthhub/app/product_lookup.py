from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class ProductLookupResult:
    provider: str
    provider_id: str | None
    name: str
    brand: str | None
    barcode: str | None
    package_size: str | None
    serving_size: float | None
    serving_unit: str | None
    nutrition_basis: str | None
    energy_kj: float | None
    calories: float | None
    protein_g: float | None
    carbohydrates_g: float | None
    fat_g: float | None
    saturated_fat_g: float | None
    sugar_g: float | None
    fibre_g: float | None
    sodium_mg: float | None
    source_url: str | None
    confidence: str
    completeness: str
    image_url: str | None = None


class ProductLookupProvider(Protocol):
    name: str

    async def lookup_barcode(self, barcode: str) -> ProductLookupResult | None: ...

    async def search(self, query: str, limit: int = 10) -> list[ProductLookupResult]: ...


class OpenFoodFactsProvider:
    name = "open_food_facts"

    def __init__(self, base_url: str = "https://world.openfoodfacts.org", timeout_seconds: float = 4.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout_seconds)
        self.headers = {"User-Agent": "HealthHub/0.7.0 (Home Assistant nutrition companion)"}

    @staticmethod
    def _number(mapping: dict, key: str) -> float | None:
        value = mapping.get(key)
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _normalise(self, product: dict) -> ProductLookupResult | None:
        name = str(product.get("product_name") or product.get("generic_name") or "").strip()
        if not name:
            return None
        nutriments = product.get("nutriments") or {}
        populated = sum(
            value is not None
            for value in (
                self._number(nutriments, "energy-kcal_100g"),
                self._number(nutriments, "proteins_100g"),
                self._number(nutriments, "carbohydrates_100g"),
                self._number(nutriments, "fat_100g"),
                self._number(nutriments, "sugars_100g"),
            )
        )
        return ProductLookupResult(
            provider=self.name,
            provider_id=str(product.get("code") or "") or None,
            name=name,
            brand=str(product.get("brands") or "").split(",")[0].strip() or None,
            barcode=str(product.get("code") or "") or None,
            package_size=str(product.get("quantity") or "").strip() or None,
            serving_size=None,
            serving_unit=None,
            nutrition_basis="per_100g",
            energy_kj=self._number(nutriments, "energy-kj_100g"),
            calories=self._number(nutriments, "energy-kcal_100g"),
            protein_g=self._number(nutriments, "proteins_100g"),
            carbohydrates_g=self._number(nutriments, "carbohydrates_100g"),
            fat_g=self._number(nutriments, "fat_100g"),
            saturated_fat_g=self._number(nutriments, "saturated-fat_100g"),
            sugar_g=self._number(nutriments, "sugars_100g"),
            fibre_g=self._number(nutriments, "fiber_100g"),
            sodium_mg=(self._number(nutriments, "sodium_100g") or 0) * 1000 if nutriments.get("sodium_100g") is not None else None,
            source_url=f"{self.base_url}/product/{product.get('code')}" if product.get("code") else None,
            confidence="high" if product.get("data_quality_errors_tags") in (None, []) and populated >= 4 else "needs_review",
            completeness="complete" if populated >= 5 else "partial",
            image_url=product.get("image_front_small_url") or product.get("image_front_url"),
        )

    async def lookup_barcode(self, barcode: str) -> ProductLookupResult | None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False, headers=self.headers) as client:
                response = await client.get(f"{self.base_url}/api/v2/product/{barcode}.json")
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        if payload.get("status") != 1:
            return None
        return self._normalise(payload.get("product") or {})

    async def search(self, query: str, limit: int = 10) -> list[ProductLookupResult]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False, headers=self.headers) as client:
                response = await client.get(
                    f"{self.base_url}/cgi/search.pl",
                    params={"search_terms": query, "search_simple": 1, "action": "process", "json": 1, "page_size": limit},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            return []
        results: list[ProductLookupResult] = []
        for item in payload.get("products", []) if isinstance(payload, dict) else []:
            normalised = self._normalise(item)
            if normalised:
                results.append(normalised)
        return results[:limit]
