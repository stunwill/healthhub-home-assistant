from __future__ import annotations

from .main import app
from .planning import router as planning_router

# The v0.2 application defines the SPA catch-all after its API routes. Register
# v0.3 planning routes before that fallback so /api/v1/planning requests are not
# treated as frontend paths.
frontend_fallback = next(
    (route for route in app.router.routes if getattr(route, "path", None) == "/{full_path:path}"),
    None,
)
if frontend_fallback is not None:
    app.router.routes.remove(frontend_fallback)

app.include_router(planning_router)

if frontend_fallback is not None:
    app.router.routes.append(frontend_fallback)
