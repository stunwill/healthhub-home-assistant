from __future__ import annotations

from .activity import router as activity_router
from .main import app

# v0.3 replaces the v0.2 daily summary with the exercise-aware version and
# registers new API routes before the SPA catch-all route.
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

if frontend_fallback is not None:
    app.router.routes.append(frontend_fallback)
