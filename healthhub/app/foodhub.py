from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class FoodHubStatus:
    available: bool
    compatible: bool
    version: str | None = None
    message: str | None = None


class FoodHubClient:
    def __init__(self, base_url: str, timeout_seconds: float = 2.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout_seconds)

    async def status(self) -> FoodHubStatus:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
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
