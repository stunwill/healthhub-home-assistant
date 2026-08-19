from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class FoodHubStatus:
    available: bool
    compatible: bool
    version: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class FoodHubRecipeResult:
    id: str
    name: str
    image_url: str | None
    nutrition_available: bool
    calories_per_serving: float | None


class FoodHubClient:
    def __init__(self, base_url: str, timeout_seconds: float = 2.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout_seconds)

    async def status(self) -> FoodHubStatus:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.get(f"{self.base_url}/api/v1/capabilities")
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return FoodHubStatus(False, False, message=f"FoodHub unavailable: {exc.__class__.__name__}")

        api_versions = payload.get("api_versions", [])
        compatible = "v1" in api_versions
        return FoodHubStatus(
            available=True,
            compatible=compatible,
            version=payload.get("application_version"),
            message=None if compatible else "FoodHub is reachable but does not advertise API v1",
        )

    async def search_recipes(self, query: str, limit: int = 8) -> list[FoodHubRecipeResult]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/recipes/search",
                    params={"q": query, "limit": limit},
                )
                if response.status_code in {404, 405}:
                    return []
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            return []

        results: list[FoodHubRecipeResult] = []
        for item in payload if isinstance(payload, list) else []:
            nutrition = item.get("nutrition") or {}
            results.append(
                FoodHubRecipeResult(
                    id=str(item.get("id")),
                    name=str(item.get("name", "FoodHub recipe")),
                    image_url=item.get("image_url"),
                    nutrition_available=bool(nutrition.get("available", False)),
                    calories_per_serving=nutrition.get("calories_per_serving"),
                )
            )
        return results
