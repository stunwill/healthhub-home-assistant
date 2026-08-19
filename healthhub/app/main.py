from __future__ import annotations

import io
import json
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Annotated
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytesseract
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .database import DATABASE_PATH, ensure_data_dir, get_db
from .domain import calorie_budget
from .foodhub import FoodHubClient
from .food_library import IMPORT_FIELDS, parse_tsv
from .import_files import parse_csv_bytes, parse_xlsx_bytes, template_csv, template_xlsx_bytes
from .models import DiaryEntry, Food, FoodComponent, FoodHubRecipeLink, FoodIdentifier, FoodPreference, ImportBatch, ImportItem, Profile, utc_now
from .nutrition_capture import parse_nutrition_text, validate_nutrition_consistency
from .product_lookup import OpenFoodFactsProvider, ProductLookupResult
from .schemas import (
    ActiveProfileResponse,
    ActiveProfileSelection,
    CalorieBudgetInput,
    CalorieBudgetOutput,
    CompositeFoodCreate,
    DailySummaryOutput,
    DiaryEntryCreate,
    DiaryEntryOutput,
    FoodCreate,
    FoodOutput,
    FoodPreferenceUpdate,
    FoodUpdate,
    ImportCommitRequest,
    ImportPreviewOutput,
    ImportPreviewRequest,
    NutritionLabelReviewCreate,
    ProductCandidate,
    ProductSaveRequest,
    ProfileCreate,
    ProfileOutput,
    ProfileUpdate,
    QuickAddResult,
)

APP_VERSION = os.getenv("HEALTHHUB_VERSION", "0.7.0")
STATIC_DIR = Path(os.getenv("HEALTHHUB_STATIC_DIR", "/app/static"))
OPTIONS_FILE = Path("/data/options.json")
ACTIVE_PROFILE_FILE = Path(os.getenv("HEALTHHUB_ACTIVE_PROFILE_FILE", "/data/healthhub/active-profile.json"))
CAPTURE_DIR = Path(os.getenv("HEALTHHUB_CAPTURE_DIR", "/data/healthhub/tmp/captures"))
MAX_CAPTURE_BYTES = 10 * 1024 * 1024
MAX_IMPORT_BYTES = 5 * 1024 * 1024
ALLOWED_CAPTURE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
DbSession = Annotated[Session, Depends(get_db)]


def load_options() -> dict:
    defaults = {
        "locale": "en-AU",
        "timezone": "Australia/Melbourne",
        "foodhub": {"enabled": True, "base_url": "http://dinnerhub:8099"},
        "product_lookup": {"enabled": True, "provider": "open_food_facts", "base_url": "https://world.openfoodfacts.org"},
    }
    if not OPTIONS_FILE.exists():
        return defaults
    try:
        supplied = json.loads(OPTIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    for key in defaults:
        if key in supplied:
            defaults[key] = supplied[key]
    return defaults


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_data_dir()
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="HealthHub API", description="Personal nutrition, activity, goals and progress tracking for Home Assistant.", version=APP_VERSION, lifespan=lifespan)
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


def food_scale(food: Food) -> float:
    quantity = food.serving_quantity or food.serving_grams
    canonical = food.canonical_quantity or 100.0
    unit = food.serving_unit.lower()
    if food.nutrition_basis == "per_100g" and quantity and unit in {"g", "gram", "grams"}:
        return quantity / canonical
    if food.nutrition_basis == "per_100ml" and quantity and unit in {"ml", "millilitre", "millilitres", "milliliter", "milliliters"}:
        return quantity / canonical
    return 1.0


def food_key(name: str, brand: str | None, serving_size: float | None, serving_unit: str | None) -> tuple[str, str, float | None, str]:
    return (name.strip().lower(), (brand or "").strip().lower(), serving_size, (serving_unit or "serving").strip().lower())


def barcode_type(value: str) -> str:
    length = len(value)
    return {8: "ean8", 12: "upca", 13: "ean13", 14: "gtin14"}.get(length, "gtin")


def valid_barcode(value: str) -> bool:
    if not value.isdigit() or len(value) not in {8, 12, 13, 14}:
        return False
    digits = [int(ch) for ch in value]
    check = digits[-1]
    body = digits[:-1][::-1]
    total = sum(number * (3 if index % 2 == 0 else 1) for index, number in enumerate(body))
    return (10 - (total % 10)) % 10 == check


def local_day_bounds(target: date, timezone_name: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone_name)
    return datetime.combine(target, time.min, tzinfo=zone).astimezone(timezone.utc), datetime.combine(target, time.max, tzinfo=zone).astimezone(timezone.utc)


def preview_rows(headers: list[str], mappings: dict[str, str | None], rows: list[dict], db: Session) -> ImportPreviewOutput:
    existing = {food_key(food.name, food.brand, food.serving_quantity or food.serving_grams, food.serving_unit) for food in db.scalars(select(Food).where(Food.archived.is_(False))).all()}
    duplicates = 0
    for row in rows:
        key = food_key(str(row.get("name", "")), str(row.get("brand") or ""), float(row["serving_size"]) if row.get("serving_size") else None, str(row.get("serving_unit") or "serving"))
        row["_duplicate"] = key in existing
        duplicates += int(bool(row["_duplicate"]))
    return ImportPreviewOutput(headers=headers, mappings=mappings, total_rows=len(rows), valid_rows=sum(bool(row["_valid"]) for row in rows), warning_rows=sum(bool(row["_warnings"]) for row in rows), invalid_rows=sum(not row["_valid"] for row in rows), duplicate_rows=duplicates, rows=rows)


def product_provider() -> OpenFoodFactsProvider | None:
    options = load_options().get("product_lookup", {})
    if not options.get("enabled", True):
        return None
    return OpenFoodFactsProvider(base_url=options.get("base_url", "https://world.openfoodfacts.org"))


def product_candidate(result: ProductLookupResult) -> ProductCandidate:
    return ProductCandidate(**result.__dict__)


def local_barcode_food(db: Session, barcode: str) -> Food | None:
    identifier = db.scalar(select(FoodIdentifier).where(FoodIdentifier.value == barcode))
    return db.get(Food, identifier.food_id) if identifier else None


def quality_rank(food: Food) -> int:
    if food.verification_status == "verified" and food.source == "packaging_label":
        return 50
    if food.verification_status == "verified":
        return 40
    if food.source in {"external_product_database", "foodhub_recipe"}:
        return 30
    if food.data_quality in {"imported", "user_entered"}:
        return 20
    return 10


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "service": "HealthHub", "version": APP_VERSION, "database": "ready" if DATABASE_PATH.exists() else "initialising"}


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
        return ActiveProfileResponse(profile_id=json.loads(ACTIVE_PROFILE_FILE.read_text(encoding="utf-8"))["profile_id"])
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
def list_foods(db: DbSession, q: str | None = Query(default=None, min_length=1, max_length=180), favourite: bool | None = None, profile_id: str | None = None, include_archived: bool = False, limit: int = Query(default=50, ge=1, le=200)) -> list[Food]:
    statement = select(Food)
    if not include_archived:
        statement = statement.where(Food.archived.is_(False))
    if favourite is not None:
        statement = statement.where(Food.favourite.is_(favourite))
    if q:
        pattern = f"%{q.strip().lower()}%"
        barcode_ids = select(FoodIdentifier.food_id).where(FoodIdentifier.value.like(f"%{q.strip()}%"))
        statement = statement.where(or_(func.lower(Food.name).like(pattern), func.lower(func.coalesce(Food.brand, "")).like(pattern), func.lower(func.coalesce(Food.category, "")).like(pattern), Food.id.in_(barcode_ids)))
    if profile_id:
        statement = statement.outerjoin(FoodPreference, FoodPreference.food_id == Food.id).where(or_(FoodPreference.profile_id == profile_id, FoodPreference.profile_id.is_(None))).order_by(func.coalesce(FoodPreference.favourite, False).desc(), func.coalesce(FoodPreference.use_count, 0).desc(), func.coalesce(FoodPreference.last_used_at, Food.created_at).desc(), Food.favourite.desc(), Food.name)
    else:
        statement = statement.order_by(Food.favourite.desc(), Food.name)
    return list(db.scalars(statement.limit(limit)).all())


@app.post("/api/v1/foods", response_model=FoodOutput, status_code=status.HTTP_201_CREATED)
def create_food(payload: FoodCreate, db: DbSession) -> Food:
    values = payload.model_dump(mode="json")
    barcodes = values.pop("barcodes", [])
    if values.get("serving_quantity") is None and values.get("serving_grams") is not None:
        values["serving_quantity"] = values["serving_grams"]
    food = Food(**values)
    db.add(food)
    db.flush()
    for barcode in barcodes:
        if not valid_barcode(barcode):
            raise HTTPException(status_code=422, detail=f"Invalid barcode {barcode}")
        db.add(FoodIdentifier(food_id=food.id, identifier_type=barcode_type(barcode), value=barcode))
    db.commit()
    db.refresh(food)
    return food


@app.post("/api/v1/foods/composite", response_model=FoodOutput, status_code=status.HTTP_201_CREATED)
def create_composite_food(payload: CompositeFoodCreate, db: DbSession) -> Food:
    components = [get_food_or_404(db, item.food_id) for item in payload.components]
    if any(food.archived for food in components):
        raise HTTPException(status_code=409, detail="Archived foods cannot be components")
    fields = ("calories", "protein_g", "carbohydrates_g", "fat_g", "sugar_g", "saturated_fat_g", "fibre_g", "sodium_mg", "calcium_mg", "iron_mg", "potassium_mg", "cholesterol_mg", "alcohol_g", "caffeine_mg")
    values: dict[str, float | None] = {}
    for field in fields:
        source_values = [getattr(food, field) for food in components if getattr(food, field) is not None]
        values[field] = round(sum(float(getattr(food, field) or 0) * item.quantity for food, item in zip(components, payload.components)), 2) if source_values else None
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
    preference = db.get(FoodPreference, {"profile_id": profile_id, "food_id": food_id}) or FoodPreference(profile_id=profile_id, food_id=food_id)
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
    return preview_rows(headers, mappings, rows, db)


@app.post("/api/v1/foods/import/file", response_model=ImportPreviewOutput)
async def preview_food_file(db: DbSession, file: Annotated[UploadFile, File(...)], sheet: Annotated[str | None, Form()] = None) -> ImportPreviewOutput:
    data = await file.read(MAX_IMPORT_BYTES + 1)
    if len(data) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="Import files must be 5 MB or smaller")
    try:
        if file.filename and file.filename.lower().endswith(".csv"):
            parsed = parse_csv_bytes(data, file.filename)
        elif file.filename and file.filename.lower().endswith(".xlsx"):
            parsed = parse_xlsx_bytes(data, file.filename, sheet_name=sheet)
        else:
            raise HTTPException(status_code=415, detail="Upload a .csv or .xlsx file")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    output = preview_rows(parsed.headers, parsed.mappings, parsed.rows, db)
    return output.model_copy(update={"source_type": parsed.source_type, "source_name": parsed.source_name, "sheet_names": parsed.sheet_names, "selected_sheet": parsed.selected_sheet})


@app.post("/api/v1/foods/import/commit")
def commit_food_import(payload: ImportCommitRequest, db: DbSession) -> dict[str, object]:
    batch = ImportBatch(source=payload.source, source_name=payload.source_name)
    db.add(batch)
    db.flush()
    foods = list(db.scalars(select(Food).where(Food.archived.is_(False))).all())
    for row_number, row in enumerate(payload.rows, start=2):
        if not row.get("_valid", True):
            batch.rejected_count += 1
            errors = row.get("_errors", [])
            db.add(ImportItem(batch_id=batch.id, row_number=row_number, action="rejected", message="; ".join(str(item) for item in errors) if isinstance(errors, list) else "Invalid row"))
            continue
        name = str(row.get("name", "")).strip()
        brand = str(row.get("brand") or "").strip() or None
        serving_size = float(str(row["serving_size"])) if row.get("serving_size") not in (None, "") else None
        unit = str(row.get("serving_unit") or "serving")
        match = next((food for food in foods if food_key(food.name, food.brand, food.serving_quantity or food.serving_grams, food.serving_unit) == food_key(name, brand, serving_size, unit)), None)
        if match and payload.duplicate_action == "skip":
            batch.skipped_count += 1
            db.add(ImportItem(batch_id=batch.id, row_number=row_number, food_id=match.id, action="skipped", message="Potential duplicate"))
            continue
        values: dict[str, object] = {
            "name": name,
            "brand": brand,
            "category": str(row.get("category") or "") or None,
            "serving_name": f"{serving_size:g} {unit}" if serving_size else f"1 {unit}",
            "serving_unit": unit,
            "serving_quantity": serving_size,
            "serving_grams": serving_size if unit.lower() in {"g", "gram", "grams"} else None,
            "nutrition_basis": str(row.get("nutrition_basis") or "per_serving"),
            "canonical_quantity": row.get("canonical_quantity"),
            "canonical_unit": str(row.get("canonical_unit") or "") or None,
            "calories": float(str(row.get("calories") or 0)),
            "source": payload.source,
            "source_provider": payload.source,
            "data_quality": "imported",
            "verification_status": "unverified",
            "notes": str(row.get("notes") or "") or None,
        }
        aliases = {"carbs_g": "carbohydrates_g"}
        for field in ("protein_g", "carbs_g", "fat_g", "saturated_fat_g", "sugar_g", "fibre_g", "sodium_mg", "calcium_mg", "iron_mg", "potassium_mg", "alcohol_g", "caffeine_mg"):
            values[aliases.get(field, field)] = row.get(field)
        if match and payload.duplicate_action == "update":
            if quality_rank(match) > 20:
                batch.skipped_count += 1
                db.add(ImportItem(batch_id=batch.id, row_number=row_number, food_id=match.id, action="skipped", message="Existing higher-quality nutrition protected"))
                continue
            for field, value in values.items():
                setattr(match, field, value)
            batch.updated_count += 1
            db.add(ImportItem(batch_id=batch.id, row_number=row_number, food_id=match.id, action="updated"))
        else:
            food = Food(**values)
            db.add(food)
            db.flush()
            foods.append(food)
            batch.created_count += 1
            db.add(ImportItem(batch_id=batch.id, row_number=row_number, food_id=food.id, action="created"))
    db.commit()
    return {"batch_id": batch.id, "created": batch.created_count, "updated": batch.updated_count, "skipped": batch.skipped_count, "rejected": batch.rejected_count}


@app.get("/api/v1/foods/import/template")
def food_import_template() -> dict[str, object]:
    return {"template": "\t".join(IMPORT_FIELDS), "required": ["name"], "optional": [field for field in IMPORT_FIELDS if field != "name"], "nutrition_bases": ["per_serving", "per_100g", "per_100ml"]}


@app.get("/api/v1/foods/import/template.csv")
def csv_import_template() -> StreamingResponse:
    return StreamingResponse(io.BytesIO(template_csv().encode("utf-8")), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=healthhub-food-import-template.csv"})


@app.get("/api/v1/foods/import/template.xlsx")
def xlsx_import_template() -> StreamingResponse:
    return StreamingResponse(io.BytesIO(template_xlsx_bytes()), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=healthhub-food-import-template.xlsx"})


@app.get("/api/v1/products/barcode/{barcode}")
async def lookup_barcode(barcode: str, db: DbSession) -> dict:
    barcode = "".join(ch for ch in barcode if ch.isdigit())
    if not valid_barcode(barcode):
        raise HTTPException(status_code=422, detail="Barcode checksum or length is invalid")
    local = local_barcode_food(db, barcode)
    if local:
        return {"status": "local", "food": FoodOutput.model_validate(local), "candidate": None}
    provider = product_provider()
    if provider:
        result = await provider.lookup_barcode(barcode)
        if result:
            return {"status": "external", "food": None, "candidate": product_candidate(result)}
    return {"status": "unknown", "food": None, "candidate": {"barcode": barcode}, "message": "Create food for this barcode using a label photo or manual entry."}


@app.get("/api/v1/products/search", response_model=list[ProductCandidate])
async def search_products(q: str = Query(min_length=2, max_length=180), limit: int = Query(default=10, ge=1, le=20)) -> list[ProductCandidate]:
    provider = product_provider()
    return [] if provider is None else [product_candidate(result) for result in await provider.search(q, limit)]


@app.post("/api/v1/products/save", response_model=FoodOutput, status_code=status.HTTP_201_CREATED)
def save_product(payload: ProductSaveRequest, db: DbSession) -> Food:
    if payload.barcode:
        local = local_barcode_food(db, payload.barcode)
        if local:
            return local
    values = payload.model_dump(exclude={"reviewed", "provider", "provider_id", "barcode", "confidence", "completeness", "serving_size", "serving_unit"})
    calories = values.pop("calories") or 0
    serving_size = payload.serving_size
    serving_unit = payload.serving_unit or ("g" if payload.nutrition_basis == "per_100g" else "mL" if payload.nutrition_basis == "per_100ml" else "serving")
    food = Food(
        **values,
        calories=calories,
        serving_name=f"{serving_size:g} {serving_unit}" if serving_size else "1 serve",
        serving_unit=serving_unit,
        serving_quantity=serving_size,
        serving_grams=serving_size if serving_unit.lower() in {"g", "gram", "grams"} else None,
        canonical_quantity=100 if payload.nutrition_basis in {"per_100g", "per_100ml"} else None,
        canonical_unit="g" if payload.nutrition_basis == "per_100g" else "mL" if payload.nutrition_basis == "per_100ml" else None,
        source="external_product_database",
        source_provider=payload.provider,
        source_identifier=payload.provider_id,
        data_quality="external",
        verification_status="reviewed",
        verified_at=utc_now(),
    )
    db.add(food)
    db.flush()
    if payload.barcode and valid_barcode(payload.barcode):
        db.add(FoodIdentifier(food_id=food.id, identifier_type=barcode_type(payload.barcode), value=payload.barcode))
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
def list_diary_entries(profile_id: str, db: DbSession, day: date = Query(default_factory=date.today)) -> list[DiaryEntry]:
    profile = get_profile_or_404(db, profile_id)
    start, end = local_day_bounds(day, profile.timezone)
    return list(db.scalars(select(DiaryEntry).where(DiaryEntry.profile_id == profile_id, DiaryEntry.consumed_at.between(start, end)).order_by(DiaryEntry.consumed_at)).all())


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
    total_scale = servings * food_scale(food)
    entry = DiaryEntry(
        profile_id=profile.id,
        food_id=food.id,
        meal_period=payload.meal_period.value,
        consumed_at=payload.consumed_at.astimezone(timezone.utc),
        servings=servings,
        food_name=food.name,
        serving_name=food.serving_name,
        calories=round(food.calories * total_scale, 2),
        protein_g=scale_optional(food.protein_g, total_scale),
        carbohydrates_g=scale_optional(food.carbohydrates_g, total_scale),
        fat_g=scale_optional(food.fat_g, total_scale),
        sugar_g=scale_optional(food.sugar_g, total_scale),
        saturated_fat_g=scale_optional(food.saturated_fat_g, total_scale),
        fibre_g=scale_optional(food.fibre_g, total_scale),
        sodium_mg=scale_optional(food.sodium_mg, total_scale),
        calcium_mg=scale_optional(food.calcium_mg, total_scale),
        iron_mg=scale_optional(food.iron_mg, total_scale),
        potassium_mg=scale_optional(food.potassium_mg, total_scale),
        cholesterol_mg=scale_optional(food.cholesterol_mg, total_scale),
        alcohol_g=scale_optional(food.alcohol_g, total_scale),
        caffeine_mg=scale_optional(food.caffeine_mg, total_scale),
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
def daily_summary(profile_id: str, db: DbSession, day: date = Query(default_factory=date.today)) -> DailySummaryOutput:
    profile = get_profile_or_404(db, profile_id)
    entries = list_diary_entries(profile_id=profile_id, db=db, day=day)
    consumed = sum(entry.calories for entry in entries)
    credited, remaining = calorie_budget(daily_calorie_target=profile.daily_calorie_target, consumed_food_calories=consumed, completed_exercise_calories=0, exercise_credit_mode=profile.exercise_credit_mode, exercise_credit_percentage=profile.exercise_credit_percentage)  # type: ignore[arg-type]
    return DailySummaryOutput(profile_id=profile.id, date=day, calorie_target=profile.daily_calorie_target, consumed_calories=round(consumed), credited_exercise_calories=credited, remaining_calories=remaining, protein_g=round(sum(entry.protein_g or 0 for entry in entries), 1), carbohydrates_g=round(sum(entry.carbohydrates_g or 0 for entry in entries), 1), fat_g=round(sum(entry.fat_g or 0 for entry in entries), 1), sugar_g=round(sum(entry.sugar_g or 0 for entry in entries), 1), entry_count=len(entries))


@app.get("/api/v1/quick-add/search", response_model=list[QuickAddResult])
async def quick_add_search(db: DbSession, q: str = Query(min_length=2, max_length=180), limit: int = Query(default=12, ge=1, le=30), profile_id: str | None = None) -> list[QuickAddResult]:
    foods = list_foods(db=db, q=q, profile_id=profile_id, limit=max(1, min(limit, 12)))
    results = [QuickAddResult(id=food.id, source="healthhub", result_type=food.kind, name=food.name, subtitle=food.brand or food.serving_name, calories=round(food.calories * food_scale(food), 2), nutrition_complete=all(value is not None for value in (food.protein_g, food.carbohydrates_g, food.fat_g))) for food in foods]
    options = load_options().get("foodhub", {})
    if options.get("enabled", True) and len(results) < limit:
        client = FoodHubClient(options.get("base_url", "http://dinnerhub:8099"))
        recipes = await client.search_recipes(q, limit=limit - len(results))
        results.extend(QuickAddResult(id=recipe.id, source="foodhub", result_type="recipe", name=recipe.name, subtitle="FoodHub recipe", calories=recipe.calories_per_serving, nutrition_complete=recipe.nutrition.authoritative and recipe.nutrition.completeness == "complete") for recipe in recipes)
    return results[:limit]


@app.post("/api/v1/profiles/{profile_id}/diary/foodhub/{recipe_id}", response_model=DiaryEntryOutput, status_code=status.HTTP_201_CREATED)
async def add_foodhub_recipe(profile_id: str, recipe_id: str, db: DbSession, meal_period: str = "dinner", servings: float = 1.0) -> DiaryEntry:
    get_profile_or_404(db, profile_id)
    options = load_options().get("foodhub", {})
    client = FoodHubClient(options.get("base_url", "http://dinnerhub:8099"))
    recipe = await client.recipe_summary(recipe_id)
    if not recipe or not recipe.nutrition.authoritative or not recipe.nutrition.available:
        raise HTTPException(status_code=409, detail="FoodHub recipe nutrition is unavailable or not authoritative")
    values = recipe.nutrition.values
    link = db.get(FoodHubRecipeLink, recipe_id)
    food = db.get(Food, link.food_id) if link else None
    if food is None:
        food = Food(name=recipe.name, kind="composite", serving_name="1 serving", serving_unit="serving", serving_quantity=1, calories=values.get("calories_kcal") or 0, protein_g=values.get("protein_g"), carbohydrates_g=values.get("carbohydrate_g"), fat_g=values.get("fat_g"), saturated_fat_g=values.get("saturated_fat_g"), sugar_g=values.get("sugar_g"), fibre_g=values.get("fibre_g"), sodium_mg=values.get("sodium_mg"), source="foodhub_recipe", source_provider="FoodHub", source_identifier=recipe.id, data_quality="foodhub_derived", verification_status="verified", verified_at=utc_now(), image_url=recipe.image_url)
        db.add(food)
        db.flush()
        link = FoodHubRecipeLink(foodhub_recipe_id=recipe.id, food_id=food.id, recipe_updated_at=recipe.updated_at, nutrition_status="authoritative", last_synced_at=utc_now())
        db.add(link)
    elif recipe.updated_at and link and recipe.updated_at != link.recipe_updated_at:
        food.name = recipe.name
        food.calories = values.get("calories_kcal") or 0
        food.protein_g = values.get("protein_g")
        food.carbohydrates_g = values.get("carbohydrate_g")
        food.fat_g = values.get("fat_g")
        food.saturated_fat_g = values.get("saturated_fat_g")
        food.sugar_g = values.get("sugar_g")
        food.fibre_g = values.get("fibre_g")
        food.sodium_mg = values.get("sodium_mg")
        link.recipe_updated_at = recipe.updated_at
        link.last_synced_at = utc_now()
    db.commit()
    db.refresh(food)
    payload = DiaryEntryCreate(food_id=food.id, meal_period=meal_period, consumed_at=datetime.now(timezone.utc), servings=servings)  # type: ignore[arg-type]
    return create_diary_entry(profile_id, payload, db)


@app.get("/api/v1/integrations/foodhub")
async def foodhub_status() -> dict:
    options = load_options().get("foodhub", {})
    if not options.get("enabled", True):
        return {"available": False, "compatible": False, "message": "FoodHub integration is disabled"}
    result = await FoodHubClient(options.get("base_url", "http://dinnerhub:8099")).status()
    return {"available": result.available, "compatible": result.compatible, "version": result.version, "message": result.message, "ingredient_mapping_available": False, "ingredient_mapping_message": "Current FoodHub v1 contract exposes authoritative recipe nutrition but not recipe ingredient quantities."}


@app.post("/api/v1/capture/nutrition-label", status_code=status.HTTP_202_ACCEPTED)
async def upload_nutrition_label(image: Annotated[UploadFile, File(...)]) -> dict:
    if image.content_type not in ALLOWED_CAPTURE_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG or WebP image")
    data = await image.read(MAX_CAPTURE_BYTES + 1)
    if not data:
        raise HTTPException(status_code=422, detail="The uploaded image is empty")
    if len(data) > MAX_CAPTURE_BYTES:
        raise HTTPException(status_code=413, detail="Nutrition-label images must be 10 MB or smaller")
    try:
        pil = Image.open(io.BytesIO(data))
        pil.verify()
        pil = Image.open(io.BytesIO(data)).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=422, detail="Uploaded file is not a valid supported image") from exc
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    upload_id = str(uuid4())
    suffix = ALLOWED_CAPTURE_TYPES[image.content_type]
    target = CAPTURE_DIR / f"{upload_id}{suffix}"
    target.write_bytes(data)
    try:
        text = pytesseract.image_to_string(pil, config="--psm 6")
        ocr_data = pytesseract.image_to_data(pil, output_type=pytesseract.Output.DICT, config="--psm 6")
        confidences = [float(value) for value in ocr_data.get("conf", []) if str(value).replace(".", "", 1).isdigit() and float(value) >= 0]
        extraction = parse_nutrition_text(text)
        average = sum(confidences) / len(confidences) if confidences else 0
        overall = "high" if average >= 80 else "needs_review" if average >= 45 else "unknown"
    except (pytesseract.TesseractError, OSError):
        extraction = parse_nutrition_text("")
        overall = "unknown"
    return {"upload_id": upload_id, "status": "awaiting_review", "review_required": True, "extraction": extraction.values, "field_confidence": extraction.confidence, "confidence": overall, "warnings": extraction.warnings, "message": "Local OCR completed. Review every extracted value against the packaging image before saving."}


@app.get("/api/v1/capture/nutrition-label/{upload_id}/image")
def nutrition_label_image(upload_id: str) -> FileResponse:
    matching = list(CAPTURE_DIR.glob(f"{upload_id}.*"))
    if not matching:
        raise HTTPException(status_code=404, detail="Nutrition-label upload not found")
    return FileResponse(matching[0])


@app.post("/api/v1/capture/nutrition-label/review", response_model=FoodOutput, status_code=status.HTTP_201_CREATED)
def save_reviewed_nutrition_label(payload: NutritionLabelReviewCreate, db: DbSession) -> Food:
    matching = list(CAPTURE_DIR.glob(f"{payload.upload_id}.*"))
    if not matching:
        raise HTTPException(status_code=404, detail="Nutrition-label upload not found or already processed")
    warnings = validate_nutrition_consistency({key: getattr(payload, key) for key in ("energy_kj", "calories", "protein_g", "carbohydrates_g", "fat_g", "saturated_fat_g", "sugar_g", "fibre_g", "sodium_mg")})
    food = Food(
        name=payload.name,
        brand=payload.brand,
        kind=payload.kind.value,
        serving_name=payload.serving_name,
        serving_quantity=payload.serving_quantity,
        serving_unit=payload.serving_unit,
        serving_grams=payload.serving_grams,
        nutrition_basis=payload.nutrition_basis,
        canonical_quantity=100 if payload.nutrition_basis in {"per_100g", "per_100ml"} else None,
        canonical_unit="g" if payload.nutrition_basis == "per_100g" else "mL" if payload.nutrition_basis == "per_100ml" else None,
        energy_kj=payload.energy_kj,
        calories=payload.calories,
        protein_g=payload.protein_g,
        carbohydrates_g=payload.carbohydrates_g,
        fat_g=payload.fat_g,
        saturated_fat_g=payload.saturated_fat_g,
        sugar_g=payload.sugar_g,
        fibre_g=payload.fibre_g,
        sodium_mg=payload.sodium_mg,
        calcium_mg=payload.calcium_mg,
        iron_mg=payload.iron_mg,
        potassium_mg=payload.potassium_mg,
        cholesterol_mg=payload.cholesterol_mg,
        alcohol_g=payload.alcohol_g,
        caffeine_mg=payload.caffeine_mg,
        source="packaging_label",
        source_provider="local_ocr",
        data_quality="packaging_confirmed",
        verification_status="verified",
        verified_at=utc_now(),
        ocr_confidence="user_verified",
        notes="; ".join(warnings) if warnings else None,
    )
    db.add(food)
    db.flush()
    if payload.barcode:
        barcode = "".join(ch for ch in payload.barcode if ch.isdigit())
        if valid_barcode(barcode):
            existing = local_barcode_food(db, barcode)
            if existing:
                raise HTTPException(status_code=409, detail={"message": "Barcode already exists", "food_id": existing.id})
            db.add(FoodIdentifier(food_id=food.id, identifier_type=barcode_type(barcode), value=barcode))
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
