from __future__ import annotations

from .main import app
from .planning import router as planning_router

app.include_router(planning_router)
