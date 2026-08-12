from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import DATABASE_PATH, ensure_data_dir, get_db
from .domain import calorie_budget
from .foodhub import FoodHubClient
from .models import Profile
from .schemas import (
    ActiveProfileResponse,
    ActiveProfileSelection,
    CalorieBudgetInput,
    CalorieBudgetOutput,
    ProfileCreate,
    ProfileOutput,
    ProfileUpdate,
)

APP_VERSION = os.getenv("HEALTHHUB_VERSION", "0.1.0")
STATIC_DIR = Path(os.getenv("HEALTHHUB_STATIC_DIR", "/app/static"))
OPTIONS_FILE = Path("/data/options.json")
ACTIVE_PROFILE_FILE = Path(os.getenv("HEALTHHUB_ACTIVE_PROFILE_FILE", "/data/healthhub/active-profile.json"))
DbSession = Annotated[Session, Depends(get_db)]


def load_options() -> dict:
    defaults = {
        "locale": "en-AU",
        "timezone": "Australia/Melbourne",
        "foodhub": {"enabled": True, "base_url": "http://dinnerhub:8099"},
    }
    if not OPTIONS_FILE.exists():
        return defaults
    try:
        supplied = json.loads(OPTIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    defaults.update({k: v for k, v in supplied.items() if k in defaults})
    return defaults


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_data_dir()
    yield


app = FastAPI(
    title="HealthHub API",
    description="Personal nutrition, activity, goals and progress tracking for Home Assistant.",
    version=APP_VERSION,
    lifespan=lifespan,
)

if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.middleware("http")
async def restrict_direct_access(request: Request, call_next):  # type: ignore[no-untyped-def]
    enforce = os.getenv("HEALTHHUB_ENFORCE_INGRESS", "false").lower() == "true"
    allowed = {"172.30.32.2", "127.0.0.1", "::1", "testclient"}
    client_host = request.client.host if request.client else "unknown"
    if enforce and client_host not in allowed:
        return Response(status_code=403, content="HealthHub is available through Home Assistant Ingress only")
    return await call_next(request)


def get_profile_or_404(db: Session, profile_id: str) -> Profile:
    profile = db.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.get("/api/v1/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "HealthHub",
        "version": APP_VERSION,
        "database": "ready" if DATABASE_PATH.exists() else "initialising",
    }


@app.get("/api/v1/version")
def version() -> dict:
    return {"name": "HealthHub", "version": APP_VERSION, "api_versions": ["v1"]}


@app.get("/api/v1/profiles", response_model=list[ProfileOutput])
def list_profiles(db: DbSession, include_archived: bool = False) -> list[Profile]:
    statement = select(Profile).order_by(Profile.display_name)
    if not include_archived:
        statement = statement.where(Profile.archived.is_(False))
    return list(db.scalars(statement).all())


@app.post("/api/v1/profiles", response_model=ProfileOutput, status_code=status.HTTP_201_CREATED)
def create_profile(payload: ProfileCreate, db: DbSession) -> Profile:
    profile = Profile(**payload.model_dump(mode="json"))
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@app.get("/api/v1/profiles/{profile_id}", response_model=ProfileOutput)
def get_profile(profile_id: str, db: DbSession) -> Profile:
    return get_profile_or_404(db, profile_id)


@app.patch("/api/v1/profiles/{profile_id}", response_model=ProfileOutput)
def update_profile(profile_id: str, payload: ProfileUpdate, db: DbSession) -> Profile:
    profile = get_profile_or_404(db, profile_id)
    values = payload.model_dump(exclude_unset=True, mode="json")
    mode = values.get("exercise_credit_mode", profile.exercise_credit_mode)
    percentage = values.get("exercise_credit_percentage", profile.exercise_credit_percentage)
    if mode == "none":
        percentage = 0
    elif mode == "full":
        percentage = 100
    values["exercise_credit_percentage"] = percentage
    for field, value in values.items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


@app.post("/api/v1/profiles/{profile_id}/archive", response_model=ProfileOutput)
def archive_profile(profile_id: str, db: DbSession) -> Profile:
    profile = get_profile_or_404(db, profile_id)
    profile.archived = True
    db.commit()
    db.refresh(profile)
    return profile


@app.get("/api/v1/active-profile", response_model=ActiveProfileResponse | None)
def get_active_profile() -> ActiveProfileResponse | None:
    if not ACTIVE_PROFILE_FILE.exists():
        return None
    try:
        payload = json.loads(ACTIVE_PROFILE_FILE.read_text(encoding="utf-8"))
        return ActiveProfileResponse(profile_id=payload["profile_id"])
    except (OSError, json.JSONDecodeError, KeyError):
        return None


@app.put("/api/v1/active-profile", response_model=ActiveProfileResponse)
def set_active_profile(payload: ActiveProfileSelection, db: DbSession) -> ActiveProfileResponse:
    profile = get_profile_or_404(db, payload.profile_id)
    if profile.archived:
        raise HTTPException(status_code=409, detail="Archived profiles cannot be active")
    ACTIVE_PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_PROFILE_FILE.write_text(json.dumps({"profile_id": profile.id}), encoding="utf-8")
    return ActiveProfileResponse(profile_id=profile.id)


@app.post("/api/v1/calorie-budget", response_model=CalorieBudgetOutput)
def calculate_budget(payload: CalorieBudgetInput) -> CalorieBudgetOutput:
    credited, remaining = calorie_budget(**payload.model_dump())
    return CalorieBudgetOutput(credited_exercise_calories=credited, remaining_calories=remaining)


@app.get("/api/v1/integrations/foodhub")
async def foodhub_status() -> dict:
    options = load_options().get("foodhub", {})
    if not options.get("enabled", True):
        return {"available": False, "compatible": False, "message": "FoodHub integration is disabled"}
    client = FoodHubClient(options.get("base_url", "http://dinnerhub:8099"))
    result = await client.status()
    return {
        "available": result.available,
        "compatible": result.compatible,
        "version": result.version,
        "message": result.message,
    }


@app.post("/api/v1/capture/nutrition-label")
async def prepare_nutrition_label_capture() -> dict:
    return {
        "status": "not_implemented",
        "review_required": True,
        "supported_inputs": ["camera_photo", "uploaded_image"],
        "workflow": ["capture_or_upload", "extract", "review", "correct", "save"],
        "message": "Nutrition-label extraction is planned for a later release. No OCR is performed in v0.1.0.",
    }


@app.get("/{full_path:path}", include_in_schema=False)
def frontend(full_path: str):  # type: ignore[no-untyped-def]
    requested = STATIC_DIR / full_path
    if full_path and requested.is_file() and requested.resolve().is_relative_to(STATIC_DIR.resolve()):
        return FileResponse(requested)
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="HealthHub frontend has not been built")
