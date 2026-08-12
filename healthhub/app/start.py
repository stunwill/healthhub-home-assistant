from __future__ import annotations

from .activity import router as activity_router
from .main import app
from .planning import router as planning_router

# Extension routers must be registered before the SPA catch-all. v0.3 also
# replaces the v0.2 daily summary with its exercise-aware implementation.
for route in list(app.router.routes):
    if getattr(route, "path", None) == "/api/v1/profiles/{profile_id}/daily-summary":
        app.router.routes.remove(route)

frontend_fallback = next(
    (route for route in app.router.routes if getattr(route, "path", None) == "/{full_path:path}"),
    None,
)
if frontend_fallback is not None:
    app.router.routes.remove(frontend_fallback)

app.include_router(activity_router)
app.include_router(planning_router)

if frontend_fallback is not None:
    app.router.routes.append(frontend_fallback)
