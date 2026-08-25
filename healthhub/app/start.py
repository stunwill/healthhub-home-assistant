from __future__ import annotations

import os
from contextlib import asynccontextmanager

from . import main as main_module
from .activity import router as activity_router
from .main import app
from .planning import router as planning_router
from .v08 import close_foodhub_client, router as v08_router

RUNTIME_VERSION = os.getenv("HEALTHHUB_VERSION", "0.8.0")
main_module.APP_VERSION = RUNTIME_VERSION
app.version = RUNTIME_VERSION

# Extension routers must be registered before the SPA catch-all. v0.3 also
# replaces the v0.2 daily summary with its exercise-aware implementation.
for route in list(app.router.routes):
    if getattr(route, "path", None) == "/api/v1/profiles/{profile_id}/daily-summary":
        app.router.routes.remove(route)

frontend_fallback = next(
    (
        route
        for route in app.router.routes
        if getattr(route, "path", None) == "/{full_path:path}"
    ),
    None,
)
if frontend_fallback is not None:
    app.router.routes.remove(frontend_fallback)

app.include_router(activity_router)
app.include_router(planning_router)
app.include_router(v08_router)

if frontend_fallback is not None:
    app.router.routes.append(frontend_fallback)

_original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def healthhub_lifespan(application):  # type: ignore[no-untyped-def]
    async with _original_lifespan(application) as state:
        try:
            yield state
        finally:
            await close_foodhub_client()


app.router.lifespan_context = healthhub_lifespan
