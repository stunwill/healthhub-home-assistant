from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Annotated
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .database import DATABASE_PATH, ensure_data_dir, get_db
from .domain import calorie_budget
from .foodhub import FoodHubClient
from .models import DiaryEntry, Food, Profile
from .schemas import (
    ActiveProfileResponse,
    ActiveProfileSelection,
    CalorieBudgetInput,
    CalorieBudgetOutput,
    DailySummaryOutput,
    DiaryEntryCreate,
    DiaryEntryOutput,
    FoodCreate,
    FoodOutput,
    FoodUpdate,
    NutritionLabelReviewCreate,
    ProfileCreate,
    ProfileOutput,
    ProfileUpdate,
    QuickAddResult,
)

APP_VERSION = os.getenv("HEALTHHUB_VERSION", "0.2.0")
STATIC_DIR = Path(os.getenv("HEALTHHUB_STATIC_DIR", "/app/static"))
OPTIONS_FILE = Path("/data/options.json")
ACTIVE_PROFILE_FILE = Path(os.getenv("HEALTHHUB_ACTIVE_PROFILE_FILE", "/data/healthhub/active-profile.json"))
CAPTURE_DIR = Path(os.getenv("HEALTHHUB_CAPTURE_DIR", "/data/healthhub/tmp/captures"))
MAX_CAPTURE_BYTES = 10 * 1024 * 1024
ALLOWED_CAPTURE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
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
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
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


def get_food_or_404(db: Session, food_id: str) -> Food:
    food = db.get(Food, food_id)
    if not food:
        raise HTTPException(status_code=404, detail="Food not found")
    return food


def scale_optional(value: float | None, servings: float) -> float | None:
    return round(value * servings, 2) if value is not None else None


def local_day_bounds(target: date, timezone_name: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone_name)
    start_local = datetime.combine(target, time.min, tzinfo=zone)
    end_local = datetime.combine(target, time.max, tzinfo=zone)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


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


@app.get("/api/v1/foods", response_model=list[FoodOutput])
def list_foods(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1, max_length=180),
    favourite: bool | None = None,
    include_archived: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Food]:
    statement = select(Food)
    if not include_archived:
        statement = statement.where(Food.archived.is_(False))
    if favourite is not None:
        statement = statement.where(Food.favourite.is_(favourite))
    if q:
        pattern = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(Food.name).like(pattern),
                func.lower(func.coalesce(Food.brand, "")).like(pattern),
            )
        )
    statement = statement.order_by(Food.favourite.desc(), Food.name).limit(limit)
    return list(db.scalars(statement).all())


@app.post("/api/v1/foods", response_model=FoodOutput, status_code=status.HTTP_201_CREATED)
def create_food(payload: FoodCreate, db: DbSession) -> Food:
    food = Food(**payload.model_dump(mode="json"))
    db.add(food)
    db.commit()
    db.refresh(food)
    return food


@app.get("/api/v1/foods/{food_id}", response_model=FoodOutput)
def get_food(food_id: str, db: DbSession) -> Food:
    return get_food_or_404(db, food_id)


@app.patch("/api/v1/foods/{food_id}", response_model=FoodOutput)
def update_food(food_id: str, payload: FoodUpdate, db: DbSession) -> Food:
    food = get_food_or_404(db, food_id)
    for field, value in payload.model_dump(exclude_unset=True, mode="json").items():
        setattr(food, field, value)
    db.commit()
    db.refresh(food)
    return food


@app.post("/api/v1/foods/{food_id}/archive", response_model=FoodOutput)
def archive_food(food_id: str, db: DbSession) -> Food:
    food = get_food_or_404(db, food_id)
    food.archived = True
    db.commit()
    db.refresh(food)
    return food


@app.get("/api/v1/profiles/{profile_id}/diary", response_model=list[DiaryEntryOutput])
def list_diary_entries(
    profile_id: str,
    db: DbSession,
    day: date = Query(default_factory=date.today),
) -> list[DiaryEntry]:
    profile = get_profile_or_404(db, profile_id)
    start, end = local_day_bounds(day, profile.timezone)
    statement = (
        select(DiaryEntry)
        .where(DiaryEntry.profile_id == profile_id, DiaryEntry.consumed_at.between(start, end))
        .order_by(DiaryEntry.consumed_at)
    )
    return list(db.scalars(statement).all())


@app.post(
    "/api/v1/profiles/{profile_id}/diary",
    response_model=DiaryEntryOutput,
    status_code=status.HTTP_201_CREATED,
)
def create_diary_entry(profile_id: str, payload: DiaryEntryCreate, db: DbSession) -> DiaryEntry:
    profile = get_profile_or_404(db, profile_id)
    if profile.archived:
        raise HTTPException(status_code=409, detail="Cannot add diary entries to an archived profile")
    food = get_food_or_404(db, payload.food_id)
    if food.archived:
        raise HTTPException(status_code=409, detail="Archived foods cannot be added to the diary")
    servings = payload.servings
    entry = DiaryEntry(
        profile_id=profile.id,
        food_id=food.id,
        meal_period=payload.meal_period.value,
        consumed_at=payload.consumed_at.astimezone(timezone.utc),
        servings=servings,
        food_name=food.name,
        serving_name=food.serving_name,
        calories=round(food.calories * servings, 2),
        protein_g=scale_optional(food.protein_g, servings),
        carbohydrates_g=scale_optional(food.carbohydrates_g, servings),
        fat_g=scale_optional(food.fat_g, servings),
        source=food.source,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@app.delete("/api/v1/profiles/{profile_id}/diary/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_diary_entry(profile_id: str, entry_id: str, db: DbSession) -> Response:
    entry = db.scalar(
        select(DiaryEntry).where(DiaryEntry.id == entry_id, DiaryEntry.profile_id == profile_id)
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Diary entry not found")
    db.delete(entry)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/v1/profiles/{profile_id}/daily-summary", response_model=DailySummaryOutput)
def daily_summary(
    profile_id: str,
    db: DbSession,
    day: date = Query(default_factory=date.today),
) -> DailySummaryOutput:
    profile = get_profile_or_404(db, profile_id)
    entries = list_diary_entries(profile_id=profile_id, db=db, day=day)
    consumed = sum(entry.calories for entry in entries)
    credited, remaining = calorie_budget(
        daily_calorie_target=profile.daily_calorie_target,
        consumed_food_calories=consumed,
        completed_exercise_calories=0,
        exercise_credit_mode=profile.exercise_credit_mode,  # type: ignore[arg-type]
        exercise_credit_percentage=profile.exercise_credit_percentage,
    )
    return DailySummaryOutput(
        profile_id=profile.id,
        date=day,
        calorie_target=profile.daily_calorie_target,
        consumed_calories=round(consumed),
        credited_exercise_calories=credited,
        remaining_calories=remaining,
        protein_g=round(sum(entry.protein_g or 0 for entry in entries), 1),
        carbohydrates_g=round(sum(entry.carbohydrates_g or 0 for entry in entries), 1),
        fat_g=round(sum(entry.fat_g or 0 for entry in entries), 1),
        entry_count=len(entries),
    )


@app.get("/api/v1/quick-add/search", response_model=list[QuickAddResult])
async def quick_add_search(
    db: DbSession,
    q: str = Query(min_length=2, max_length=180),
    limit: int = Query(default=12, ge=1, le=30),
) -> list[QuickAddResult]:
    local_limit = max(1, min(limit, 12))
    foods = list_foods(db=db, q=q, limit=local_limit)
    results = [
        QuickAddResult(
            id=food.id,
            source="healthhub",
            result_type=food.kind,
            name=food.name,
            subtitle=food.brand or food.serving_name,
            calories=food.calories,
            nutrition_complete=all(
                value is not None for value in (food.protein_g, food.carbohydrates_g, food.fat_g)
            ),
        )
        for food in foods
    ]

    options = load_options().get("foodhub", {})
    if options.get("enabled", True) and len(results) < limit:
        client = FoodHubClient(options.get("base_url", "http://dinnerhub:8099"))
        recipes = await client.search_recipes(q, limit=limit - len(results))
        results.extend(
            QuickAddResult(
                id=recipe.id,
                source="foodhub",
                result_type="recipe",
                name=recipe.name,
                subtitle="FoodHub recipe",
                calories=recipe.calories_per_serving,
                nutrition_complete=recipe.nutrition_available,
            )
            for recipe in recipes
        )
    return results[:limit]


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


@app.post("/api/v1/capture/nutrition-label", status_code=status.HTTP_202_ACCEPTED)
async def upload_nutrition_label(image: Annotated[UploadFile, File(...)]) -> dict:
    if image.content_type not in ALLOWED_CAPTURE_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG or WebP image")
    data = await image.read(MAX_CAPTURE_BYTES + 1)
    if not data:
        raise HTTPException(status_code=422, detail="The uploaded image is empty")
    if len(data) > MAX_CAPTURE_BYTES:
        raise HTTPException(status_code=413, detail="Nutrition-label images must be 10 MB or smaller")
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    upload_id = str(uuid4())
    suffix = ALLOWED_CAPTURE_TYPES[image.content_type]
    target = CAPTURE_DIR / f"{upload_id}{suffix}"
    target.write_bytes(data)
    return {
        "upload_id": upload_id,
        "status": "awaiting_review",
        "review_required": True,
        "extraction": None,
        "confidence": None,
        "message": "Image stored for review. OCR is not enabled, enter the label values manually before saving.",
    }


@app.post("/api/v1/capture/nutrition-label/review", response_model=FoodOutput, status_code=status.HTTP_201_CREATED)
def save_reviewed_nutrition_label(payload: NutritionLabelReviewCreate, db: DbSession) -> Food:
    matching = list(CAPTURE_DIR.glob(f"{payload.upload_id}.*"))
    if not matching:
        raise HTTPException(status_code=404, detail="Nutrition-label upload not found or already processed")
    food = Food(
        name=payload.name,
        brand=payload.brand,
        kind=payload.kind.value,
        serving_name=payload.serving_name,
        serving_grams=payload.serving_grams,
        energy_kj=payload.energy_kj,
        calories=payload.calories,
        protein_g=payload.protein_g,
        carbohydrates_g=payload.carbohydrates_g,
        fat_g=payload.fat_g,
        source="nutrition_label_review",
    )
    db.add(food)
    db.commit()
    db.refresh(food)
    for item in matching:
        item.unlink(missing_ok=True)
    return food


@app.get("/{full_path:path}", include_in_schema=False)
def frontend(full_path: str):  # type: ignore[no-untyped-def]
    requested = STATIC_DIR / full_path
    if full_path and requested.is_file() and requested.resolve().is_relative_to(STATIC_DIR.resolve()):
        return FileResponse(requested)
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="HealthHub frontend has not been built")
