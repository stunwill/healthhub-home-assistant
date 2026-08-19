from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx


@dataclass(frozen=True)
class FoodHubStatus:
    available: bool
    compatible: bool
    version: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class FoodHubNutrition:
    available: bool
    authoritative: bool
    completeness: str
    basis: str
    source: str | None
    values: dict[str, float | None]
    updated_at: datetime | None


@dataclass(frozen=True)
class FoodHubRecipeResult:
    id: str
    name: str
    image_url: str | None
    serving_count: float | None
    updated_at: datetime | None
    nutrition: FoodHubNutrition

    @property
    def nutrition_available(self) -> bool:
        return self.nutrition.available

    @property
    def calories_per_serving(self) -> float | None:
        return self.nutrition.values.get("calories_kcal")


class FoodHubClient:
    def __init__(self, base_url: str, timeout_seconds: float = 2.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout_seconds)

    async def _json(self, path: str, params: dict | None = None) -> object | None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.get(f"{self.base_url}{path}", params=params)
                if response.status_code in {404, 405}:
                    return None
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError):
            return None

    @staticmethod
    def _nutrition(payload: dict | None) -> FoodHubNutrition:
        payload = payload or {}
        values = payload.get("values") or {}
        updated_at = payload.get("updated_at")
        parsed_at: datetime | None = None
        if updated_at:
            try:
                parsed_at = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
            except ValueError:
                parsed_at = None
        return FoodHubNutrition(
            available=bool(payload.get("available", False)),
            authoritative=bool(payload.get("authoritative", False)),
            completeness=str(payload.get("completeness") or "unavailable"),
            basis=str(payload.get("basis") or "per_serving"),
            source=payload.get("source"),
            values={key: (float(value) if value is not None else None) for key, value in values.items()},
            updated_at=parsed_at,
        )

    async def status(self) -> FoodHubStatus:
        payload = await self._json("/api/v1/capabilities")
        if not isinstance(payload, dict):
            return FoodHubStatus(False, False, message="FoodHub unavailable")
        api_version = payload.get("api_version")
        compatible = api_version == "v1" or "v1" in payload.get("api_versions", [])
        return FoodHubStatus(True, compatible, version=payload.get("application_version"), message=None if compatible else "FoodHub is reachable but does not advertise API v1")

    async def search_recipes(self, query: str, limit: int = 8) -> list[FoodHubRecipeResult]:
        payload = await self._json("/api/v1/recipes/search", {"q": query, "limit": limit})
        results: list[FoodHubRecipeResult] = []
        for item in payload if isinstance(payload, list) else []:
            updated_at = item.get("updated_at")
            parsed_at = None
            if updated_at:
                try:
                    parsed_at = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
                except ValueError:
                    pass
            results.append(FoodHubRecipeResult(id=str(item.get("id")), name=str(item.get("name", "FoodHub recipe")), image_url=item.get("image_url") or item.get("image_ref"), serving_count=item.get("serving_count"), updated_at=parsed_at, nutrition=self._nutrition(item.get("nutrition"))))
        return results

    async def recipe_summary(self, recipe_id: str) -> FoodHubRecipeResult | None:
        payload = await self._json(f"/api/v1/recipes/{recipe_id}/summary")
        if not isinstance(payload, dict):
            return None
        updated_at = payload.get("updated_at")
        parsed_at = None
        if updated_at:
            try:
                parsed_at = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
            except ValueError:
                pass
        return FoodHubRecipeResult(id=str(payload.get("id", recipe_id)), name=str(payload.get("name", "FoodHub recipe")), image_url=payload.get("image_ref"), serving_count=payload.get("serving_count"), updated_at=parsed_at, nutrition=self._nutrition(payload.get("nutrition")))
