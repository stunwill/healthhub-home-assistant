from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from .database import get_db
from .foodhub import FoodHubClient
from .main import get_food_or_404, get_profile_or_404, load_options, scale_optional
from .models import DiaryEntry, Food, FoodHubRecipeLink, FoodIdentifier, FoodPreference, MealPeriod, utc_now
from .planning import create_planned_entry
from .planning_schemas import PlannedEntryCreate, PlannedEntryOutput
from .schemas import DiaryEntryOutput, FoodOutput, QuickAddResult

router = APIRouter(prefix="/api/v1", tags=["v0.8"])
DbSession = Annotated[Session, Depends(get_db)]
logger = logging.getLogger("healthhub.performance")
_foodhub_client: FoodHubClient | None = None
_foodhub_base_url: str | None = None


class DiaryEntryUpdate(BaseModel):
    meal_period: MealPeriod | None = None
    consumed_at: datetime | None = None
    servings: float | None = Field(default=None, gt=0, le=100)

    @field_validator("consumed_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("consumed_at must include a timezone")
        return value


def foodhub_client() -> FoodHubClient | None:
    global _foodhub_client, _foodhub_base_url
    options = load_options().get("foodhub", {})
    if not options.get("enabled", True):
        return None
    base_url = str(options.get("base_url", "http://dinnerhub:8099"))
    if _foodhub_client is None:
        _foodhub_client = FoodHubClient(base_url)
        _foodhub_base_url = base_url
    elif _foodhub_base_url != base_url:
        logger.warning("FoodHub base URL changed; restart HealthHub to refresh the pooled client")
    return _foodhub_client


async def close_foodhub_client() -> None:
    global _foodhub_client, _foodhub_base_url
    if _foodhub_client is not None:
        await _foodhub_client.close()
        _foodhub_client = None
        _foodhub_base_url = None


def result_from_food(food: Food, preference: FoodPreference | None = None) -> QuickAddResult:
    tags: list[str] = []
    if preference and preference.favourite:
        tags.append("Favourite")
    elif food.favourite:
        tags.append("Favourite")
    if preference and preference.use_count:
        tags.append("Frequent")
    if preference and preference.last_used_at:
        tags.append("Recent")
    detail = food.brand or food.serving_name
    subtitle = " · ".join([*tags[:2], detail]) if tags else detail
    scale = 1.0
    quantity = food.serving_quantity or food.serving_grams
    canonical = food.canonical_quantity or 100.0
    unit = food.serving_unit.lower()
    if food.nutrition_basis == "per_100g" and quantity and unit in {"g", "gram", "grams"}:
        scale = quantity / canonical
    elif food.nutrition_basis == "per_100ml" and quantity and unit in {"ml", "millilitre", "millilitres", "milliliter", "milliliters"}:
        scale = quantity / canonical
    return QuickAddResult(
        id=food.id,
        source="healthhub",
        result_type=food.kind,
        name=food.name,
        subtitle=subtitle,
        calories=round(food.calories * scale, 2),
        nutrition_complete=all(value is not None for value in (food.protein_g, food.carbohydrates_g, food.fat_g)),
    )


@router.get("/quick-add/local-search", response_model=list[QuickAddResult])
def local_quick_add_search(
    db: DbSession,
    profile_id: str,
    q: str | None = Query(default=None, max_length=180),
    limit: int = Query(default=12, ge=1, le=30),
) -> list[QuickAddResult]:
    started = perf_counter()
    get_profile_or_404(db, profile_id)
    preference_join = and_(FoodPreference.food_id == Food.id, FoodPreference.profile_id == profile_id)
    statement = select(Food, FoodPreference).outerjoin(FoodPreference, preference_join).where(Food.archived.is_(False))
    if q and q.strip():
        needle = q.strip()
        pattern = f"%{needle.lower()}%"
        barcode_ids = select(FoodIdentifier.food_id).where(FoodIdentifier.value.like(f"%{needle}%"))
        statement = statement.where(
            or_(
                func.lower(Food.name).like(pattern),
                func.lower(func.coalesce(Food.brand, "")).like(pattern),
                func.lower(func.coalesce(Food.category, "")).like(pattern),
                Food.id.in_(barcode_ids),
            )
        )
    statement = statement.order_by(
        func.coalesce(FoodPreference.favourite, False).desc(),
        func.coalesce(FoodPreference.use_count, 0).desc(),
        func.coalesce(FoodPreference.last_used_at, Food.created_at).desc(),
        Food.favourite.desc(),
        Food.name,
    ).limit(limit)
    rows = db.execute(statement).all()
    results = [result_from_food(food, preference) for food, preference in rows]
    logger.info("performance operation=local_search duration_ms=%.1f results=%d", (perf_counter() - started) * 1000, len(results))
    return results


@router.get("/quick-add/foodhub-search", response_model=list[QuickAddResult])
async def foodhub_quick_add_search(db: DbSession, q: str = Query(min_length=2, max_length=180), limit: int = Query(default=8, ge=1, le=12)) -> list[QuickAddResult]:
    started = perf_counter()
    client = foodhub_client()
    if client is None:
        return []
    recipes = await client.search_recipes(q, limit=limit)
    linked_ids = set(db.scalars(select(FoodHubRecipeLink.foodhub_recipe_id).where(FoodHubRecipeLink.foodhub_recipe_id.in_([item.id for item in recipes]))).all()) if recipes else set()
    results = [
        QuickAddResult(
            id=recipe.id,
            source="foodhub",
            result_type="recipe",
            name=recipe.name,
            subtitle="FoodHub Recipe",
            calories=recipe.calories_per_serving,
            nutrition_complete=recipe.nutrition.authoritative and recipe.nutrition.completeness == "complete",
        )
        for recipe in recipes
        if recipe.id not in linked_ids
    ]
    logger.info("performance operation=foodhub_search duration_ms=%.1f results=%d", (perf_counter() - started) * 1000, len(results))
    return results


async def sync_foodhub_recipe(recipe_id: str, db: Session) -> Food:
    client = foodhub_client()
    if client is None:
        raise HTTPException(status_code=503, detail="FoodHub integration is disabled")
    recipe = await client.recipe_summary(recipe_id)
    if not recipe or not recipe.nutrition.authoritative or not recipe.nutrition.available:
        raise HTTPException(status_code=409, detail="FoodHub recipe nutrition is unavailable or not authoritative")
    values = recipe.nutrition.values
    link = db.get(FoodHubRecipeLink, recipe_id)
    food = db.get(Food, link.food_id) if link else None
    if food is None:
        food = Food(
            name=recipe.name,
            kind="composite",
            serving_name="1 serving",
            serving_unit="serving",
            serving_quantity=1,
            calories=values.get("calories_kcal") or 0,
            protein_g=values.get("protein_g"),
            carbohydrates_g=values.get("carbohydrate_g"),
            fat_g=values.get("fat_g"),
            saturated_fat_g=values.get("saturated_fat_g"),
            sugar_g=values.get("sugar_g"),
            fibre_g=values.get("fibre_g"),
            sodium_mg=values.get("sodium_mg"),
            source="foodhub_recipe",
            source_provider="FoodHub",
            source_identifier=recipe.id,
            data_quality="foodhub_derived",
            verification_status="verified",
            verified_at=utc_now(),
            image_url=recipe.image_url,
        )
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
        food.image_url = recipe.image_url
        link.recipe_updated_at = recipe.updated_at
        link.last_synced_at = utc_now()
    db.commit()
    db.refresh(food)
    return food


@router.post("/foods/foodhub/{recipe_id}", response_model=FoodOutput)
async def sync_foodhub_food(recipe_id: str, db: DbSession) -> Food:
    return await sync_foodhub_recipe(recipe_id, db)


@router.post("/profiles/{profile_id}/planned/foodhub/{recipe_id}", response_model=PlannedEntryOutput, status_code=status.HTTP_201_CREATED)
async def plan_foodhub_recipe(
    profile_id: str,
    recipe_id: str,
    db: DbSession,
    meal_period: MealPeriod = MealPeriod.DINNER,
    planned_for: datetime = Query(...),
    servings: float = Query(default=1.0, gt=0, le=100),
) -> object:
    food = await sync_foodhub_recipe(recipe_id, db)
    payload = PlannedEntryCreate(food_id=food.id, meal_period=meal_period, planned_for=planned_for, servings=servings)
    return create_planned_entry(profile_id, payload, db)


@router.patch("/profiles/{profile_id}/diary/{entry_id}", response_model=DiaryEntryOutput)
def update_diary_entry(profile_id: str, entry_id: str, payload: DiaryEntryUpdate, db: DbSession) -> DiaryEntry:
    get_profile_or_404(db, profile_id)
    entry = db.scalar(select(DiaryEntry).where(DiaryEntry.id == entry_id, DiaryEntry.profile_id == profile_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Diary entry not found")
    values = payload.model_dump(exclude_unset=True)
    servings = values.pop("servings", None)
    if servings is not None:
        ratio = servings / entry.servings
        entry.servings = servings
        entry.calories = round(entry.calories * ratio, 2)
        for field in ("protein_g", "carbohydrates_g", "fat_g", "sugar_g", "saturated_fat_g", "fibre_g", "sodium_mg", "calcium_mg", "iron_mg", "potassium_mg", "cholesterol_mg", "alcohol_g", "caffeine_mg"):
            setattr(entry, field, scale_optional(getattr(entry, field), ratio))
    if values.get("meal_period") is not None:
        entry.meal_period = values["meal_period"].value
    if values.get("consumed_at") is not None:
        entry.consumed_at = values["consumed_at"].astimezone(timezone.utc)
    db.commit()
    db.refresh(entry)
    return entry
