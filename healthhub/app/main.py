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
from .food_library import parse_tsv
from .models import DiaryEntry, Food, FoodComponent, FoodPreference, ImportBatch, ImportItem, Profile, utc_now
from .schemas import (
    ActiveProfileResponse,
    ActiveProfileSelection,
    CalorieBudgetInput,
    CalorieBudgetOutput,
    DailySummaryOutput,
    DiaryEntryCreate,
    DiaryEntryOutput,
    FoodCreate,
    CompositeFoodCreate,
    FoodPreferenceUpdate,
    FoodOutput,
    FoodUpdate,
    NutritionLabelReviewCreate,
    ProfileCreate,
    ProfileOutput,
    ProfileUpdate,
    QuickAddResult,
    ImportPreviewRequest,
    ImportCommitRequest,
    ImportPreviewOutput,
)

APP_VERSION = os.getenv("HEALTHHUB_VERSION", "0.6.0")
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


def food_key(name: str, brand: str | None, serving_size: float | None, serving_unit: str | None) -> tuple[str, str, float | None, str]:
    return (name.strip().lower(), (brand or "").strip().lower(), serving_size, (serving_unit or "serving").strip().lower())


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
    values = payload.model_dump(mode="json")
    nutrition_fields = values.pop("nutrition_display_fields")
    profile = Profile(**values)
    profile.nutrition_display_fields = nutrition_fields
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
    nutrition_fields = values.pop("nutrition_display_fields", None)
    mode = values.get("exercise_credit_mode", profile.exercise_credit_mode)
    percentage = values.get("exercise_credit_percentage", profile.exercise_credit_percentage)
    if mode == "none":
        percentage = 0
    elif mode == "full":
        percentage = 100
    values["exercise_credit_percentage"] = percentage
    for field, value in values.items():
        setattr(profile, field, value)
    if nutrition_fields is not None:
        profile.nutrition_display_fields = nutrition_fields
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
    profile_id: str | None = None,
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
            or_(func.lower(Food.name).like(pattern), func.lower(func.coalesce(Food.brand, "")).like(pattern))
        )
    if profile_id:
        statement = statement.outerjoin(FoodPreference, FoodPreference.food_id == Food.id).where(
            or_(FoodPreference.profile_id == profile_id, FoodPreference.profile_id.is_(None))
        )
        statement = statement.order_by(func.coalesce(FoodPreference.use_count, 0).desc(), func.coalesce(FoodPreference.last_used_at, Food.created_at).desc(), Food.favourite.desc(), Food.name)
    else:
        statement = statement.order_by(Food.favourite.desc(), Food.name)
    statement = statement.limit(limit)
    return list(db.scalars(statement).all())


@app.post("/api/v1/foods", response_model=FoodOutput, status_code=status.HTTP_201_CREATED)
def create_food(payload: FoodCreate, db: DbSession) -> Food:
    food = Food(**payload.model_dump(mode="json"))
    db.add(food)
    db.commit()
    db.refresh(food)
    return food


@app.post("/api/v1/foods/composite", response_model=FoodOutput, status_code=status.HTTP_201_CREATED)
def create_composite_food(payload: CompositeFoodCreate, db: DbSession) -> Food:
    components = [get_food_or_404(db, item.food_id) for item in payload.components]
    if any(food.archived for food in components):
        raise HTTPException(status_code=409, detail="Archived foods cannot be components")
    values: dict[str, float | None] = {}
    fields = ("calories", "protein_g", "carbohydrates_g", "fat_g", "sugar_g", "saturated_fat_g", "fibre_g", "sodium_mg", "calcium_mg", "iron_mg", "potassium_mg", "cholesterol_mg", "alcohol_g", "caffeine_mg")
    for field in fields:
        source_values = [getattr(food, field) for food, component in zip(components, payload.components) if getattr(food, field) is not None]
        values[field] = round(sum(float(getattr(food, field) or 0) * component.quantity for food, component in zip(components, payload.components)), 2) if source_values else None
    food = Food(name=payload.name, kind="composite", serving_name=payload.serving_name, serving_unit=payload.serving_unit, source="healthhub", data_quality="user_entered", notes=payload.notes, **values)
    db.add(food)
    db.flush()
    for item in payload.components:
        db.add(FoodComponent(composite_food_id=food.id, component_food_id=item.food_id, quantity=item.quantity, unit=item.unit))
    db.commit()
    db.refresh(food)
    return food


@app.put("/api/v1/profiles/{profile_id}/foods/{food_id}/preference")
def update_food_preference(profile_id: str, food_id: str, payload: FoodPreferenceUpdate, db: DbSession) -> dict[str, object]:
    get_profile_or_404(db, profile_id)
    get_food_or_404(db, food_id)
    preference = db.get(FoodPreference, {"profile_id": profile_id, "food_id": food_id})
    if preference is None:
        preference = FoodPreference(profile_id=profile_id, food_id=food_id)
        db.add(preference)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(preference, field, value)
    db.commit()
    return {"profile_id": profile_id, "food_id": food_id, "favourite": preference.favourite, "default_quantity": preference.default_quantity}


@app.get("/api/v1/profiles/{profile_id}/foods/recent", response_model=list[FoodOutput])
def recent_foods(profile_id: str, db: DbSession, limit: int = Query(default=12, ge=1, le=50)) -> list[Food]:
    get_profile_or_404(db, profile_id)
    return list(db.scalars(select(Food).join(FoodPreference).where(FoodPreference.profile_id == profile_id, FoodPreference.last_used_at.is_not(None)).order_by(FoodPreference.last_used_at.desc()).limit(limit)).all())


@app.post("/api/v1/foods/import/preview", response_model=ImportPreviewOutput)
def preview_food_import(payload: ImportPreviewRequest, db: DbSession) -> ImportPreviewOutput:
    headers, mappings, rows = parse_tsv(payload.tsv, payload.mappings)
    existing = {food_key(food.name, food.brand, food.serving_grams, food.serving_unit) for food in db.scalars(select(Food).where(Food.archived.is_(False))).all()}
    duplicates = 0
    for row in rows:
        key = food_key(str(row.get("name", "")), str(row.get("brand") or ""), float(row["serving_size"]) if row.get("serving_size") else None, str(row.get("serving_unit") or "serving"))
        row["_duplicate"] = key in existing
        duplicates += int(row["_duplicate"])
    return ImportPreviewOutput(headers=headers, mappings=mappings, total_rows=len(rows), valid_rows=sum(bool(row["_valid"]) for row in rows), warning_rows=sum(bool(row["_warnings"]) for row in rows), invalid_rows=sum(not row["_valid"] for row in rows), duplicate_rows=duplicates, rows=rows)


@app.post("/api/v1/foods/import/commit")
def commit_food_import(payload: ImportCommitRequest, db: DbSession) -> dict[str, object]:
    batch = ImportBatch(source="spreadsheet")
    db.add(batch)
    db.flush()
    for row_number, row in enumerate(payload.rows, start=2):
        if not row.get("_valid", True):
            batch.rejected_count += 1
            errors = row.get("_errors", [])
            message = "; ".join(str(item) for item in errors) if isinstance(errors, list) else "Invalid row"
            db.add(ImportItem(batch_id=batch.id, row_number=row_number, action="rejected", message=message))
            continue
        name = str(row.get("name", "")).strip()
        brand = str(row.get("brand") or "").strip() or None
        serving_size = float(str(row["serving_size"])) if row.get("serving_size") not in (None, "") else None
        unit = str(row.get("serving_unit") or "serving")
        match = next((food for food in db.scalars(select(Food).where(Food.archived.is_(False))).all() if food_key(food.name, food.brand, food.serving_grams, food.serving_unit) == food_key(name, brand, serving_size, unit)), None)
        if match and payload.duplicate_action == "skip":
            batch.skipped_count += 1
            db.add(ImportItem(batch_id=batch.id, row_number=row_number, food_id=match.id, action="skipped", message="Potential duplicate"))
            continue
        values: dict[str, object] = {"name": name, "brand": brand, "category": str(row.get("category") or "") or None, "serving_name": f"{serving_size:g} {unit}" if serving_size else f"1 {unit}", "serving_unit": unit, "serving_grams": serving_size, "calories": float(str(row.get("calories") or 0)), "source": "spreadsheet", "data_quality": "imported", "notes": str(row.get("notes") or "") or None}
        aliases = {"carbs_g": "carbohydrates_g"}
        for field in ("protein_g", "carbs_g", "fat_g", "saturated_fat_g", "sugar_g", "fibre_g", "sodium_mg", "calcium_mg", "iron_mg", "potassium_mg", "alcohol_g", "caffeine_mg"):
            values[aliases.get(field, field)] = row.get(field)
        if match and payload.duplicate_action == "update":
            for field, value in values.items():
                setattr(match, field, value)
            batch.updated_count += 1
            db.add(ImportItem(batch_id=batch.id, row_number=row_number, food_id=match.id, action="updated"))
        else:
            food = Food(**values)
            db.add(food)
            db.flush()
            batch.created_count += 1
            db.add(ImportItem(batch_id=batch.id, row_number=row_number, food_id=food.id, action="created"))
    db.commit()
    return {"batch_id": batch.id, "created": batch.created_count, "updated": batch.updated_count, "skipped": batch.skipped_count, "rejected": batch.rejected_count}


@app.get("/api/v1/foods/import/template")
def food_import_template() -> dict[str, str]:
    return {"template": "\t".join(["name", "brand", "category", "serving_size", "serving_unit", "calories", "protein_g", "carbs_g", "fat_g", "saturated_fat_g", "sugar_g", "fibre_g", "sodium_mg", "calcium_mg", "iron_mg", "potassium_mg", "alcohol_g", "caffeine_mg", "notes"])}


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


@app.post("/api/v1/profiles/{profile_id}/diary", response_model=DiaryEntryOutput, status_code=status.HTTP_201_CREATED)
def create_diary_entry(profile_id: str, payload: DiaryEntryCreate, db: DbSession) -> DiaryEntry:
    profile = get_profile_or_404(db, profile_id)
    if profile.archived:
        raise HTTPException(status_code=409, detail="Cannot add diary entries to an archived profile")
    food = get_food_or_404(db, payload.food_id)
    if food.archived:
        raise HTTPException(status_code=409, detail="Archived foods cannot be added to the diary")
    preference = db.get(FoodPreference, {"profile_id": profile_id, "food_id": food.id})
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
        sugar_g=scale_optional(food.sugar_g, servings),
        saturated_fat_g=scale_optional(food.saturated_fat_g, servings),
        fibre_g=scale_optional(food.fibre_g, servings),
        sodium_mg=scale_optional(food.sodium_mg, servings),
        calcium_mg=scale_optional(food.calcium_mg, servings),
        iron_mg=scale_optional(food.iron_mg, servings),
        potassium_mg=scale_optional(food.potassium_mg, servings),
        cholesterol_mg=scale_optional(food.cholesterol_mg, servings),
        alcohol_g=scale_optional(food.alcohol_g, servings),
        caffeine_mg=scale_optional(food.caffeine_mg, servings),
        source=food.source,
    )
    if preference is None:
        preference = FoodPreference(profile_id=profile_id, food_id=food.id, use_count=1, last_used_at=utc_now())
        db.add(preference)
    else:
        preference.use_count += 1
        preference.last_used_at = utc_now()
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@app.delete("/api/v1/profiles/{profile_id}/diary/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_diary_entry(profile_id: str, entry_id: str, db: DbSession) -> Response:
    entry = db.scalar(select(DiaryEntry).where(DiaryEntry.id == entry_id, DiaryEntry.profile_id == profile_id))
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
        sugar_g=round(sum(entry.sugar_g or 0 for entry in entries), 1),
        entry_count=len(entries),
    )


@app.get("/api/v1/quick-add/search", response_model=list[QuickAddResult])
async def quick_add_search(
    db: DbSession,
    q: str = Query(min_length=2, max_length=180),
    limit: int = Query(default=12, ge=1, le=30),
    profile_id: str | None = None,
) -> list[QuickAddResult]:
    local_limit = max(1, min(limit, 12))
    foods = list_foods(db=db, q=q, profile_id=profile_id, limit=local_limit)
    results = [
        QuickAddResult(
            id=food.id,
            source="healthhub",
            result_type=food.kind,
            name=food.name,
            subtitle=food.brand or food.serving_name,
            calories=food.calories,
            nutrition_complete=all(value is not None for value in (food.protein_g, food.carbohydrates_g, food.fat_g)),
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
        sugar_g=payload.sugar_g,
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
