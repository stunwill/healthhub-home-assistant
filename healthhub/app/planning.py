from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import logging
from time import perf_counter
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import DiaryEntry, Food, FoodPreference, Profile
from .planning_models import PlannedEntry, PlannedEntryStatus, RecurrenceFrequency, RecurrenceRule, SavedMeal, SavedMealItem
from .planning_schemas import (
    CopyDayRequest,
    CopyEntryRequest,
    CopyMealRequest,
    DailyPlanOutput,
    PlannedEntryCreate,
    PlannedEntryOutput,
    PlannedEntryUpdate,
    RecurrenceRuleCreate,
    RecurrenceRuleOutput,
    SavedMealCreate,
    SavedMealOutput,
    SavedMealUpdate,
    WeeklyPlanDay,
    WeeklyPlanOutput,
)

router = APIRouter(prefix="/api/v1", tags=["planning"])
DbSession = Annotated[Session, Depends(get_db)]
logger = logging.getLogger("healthhub.performance")


def get_profile(db: Session, profile_id: str) -> Profile:
    profile = db.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


def get_food(db: Session, food_id: str) -> Food:
    food = db.get(Food, food_id)
    if not food:
        raise HTTPException(status_code=404, detail="Food not found")
    if food.archived:
        raise HTTPException(status_code=409, detail="Archived foods cannot be planned")
    return food


def profile_today(profile: Profile) -> date:
    return datetime.now(ZoneInfo(profile.timezone)).date()


def day_bounds(target: date, timezone_name: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone_name)
    start = datetime.combine(target, time.min, tzinfo=zone).astimezone(timezone.utc)
    end = datetime.combine(target, time.max, tzinfo=zone).astimezone(timezone.utc)
    return start, end


def aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def scale(value: float | None, servings: float) -> float | None:
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


def planned_from_food(*, profile: Profile, food: Food, planned_for: datetime, meal_period: str, servings: float, recurrence_rule_id: str | None = None) -> PlannedEntry:
    total_scale = servings * food_scale(food)
    return PlannedEntry(profile_id=profile.id, food_id=food.id, recurrence_rule_id=recurrence_rule_id, meal_period=meal_period, planned_for=planned_for.astimezone(timezone.utc), servings=servings, food_name=food.name, serving_name=food.serving_name, calories=round(food.calories * total_scale, 2), protein_g=scale(food.protein_g, total_scale), carbohydrates_g=scale(food.carbohydrates_g, total_scale), fat_g=scale(food.fat_g, total_scale), sugar_g=scale(food.sugar_g, total_scale), source=food.source)


def update_usage(db: Session, profile_id: str, food_id: str) -> None:
    preference = db.get(FoodPreference, {"profile_id": profile_id, "food_id": food_id})
    if preference is None:
        from .models import utc_now
        preference = FoodPreference(profile_id=profile_id, food_id=food_id, use_count=1, last_used_at=utc_now())
        db.add(preference)
    else:
        from .models import utc_now
        preference.use_count += 1
        preference.last_used_at = utc_now()


def diary_from_planned(entry: PlannedEntry) -> DiaryEntry:
    return DiaryEntry(profile_id=entry.profile_id, food_id=entry.food_id, meal_period=entry.meal_period, consumed_at=entry.planned_for, servings=entry.servings, food_name=entry.food_name, serving_name=entry.serving_name, calories=entry.calories, protein_g=entry.protein_g, carbohydrates_g=entry.carbohydrates_g, fat_g=entry.fat_g, sugar_g=entry.sugar_g, source=entry.source)


def copy_planned_snapshot(entry: PlannedEntry, profile_id: str, planned_for: datetime, meal_period: str | None = None) -> PlannedEntry:
    return PlannedEntry(profile_id=profile_id, food_id=entry.food_id, meal_period=meal_period or entry.meal_period, planned_for=planned_for.astimezone(timezone.utc), servings=entry.servings, food_name=entry.food_name, serving_name=entry.serving_name, calories=entry.calories, protein_g=entry.protein_g, carbohydrates_g=entry.carbohydrates_g, fat_g=entry.fat_g, sugar_g=entry.sugar_g, source=entry.source, status=PlannedEntryStatus.PLANNED.value)


def copy_diary_snapshot(entry: DiaryEntry, profile_id: str, planned_for: datetime, meal_period: str | None = None) -> PlannedEntry:
    return PlannedEntry(profile_id=profile_id, food_id=entry.food_id, meal_period=meal_period or entry.meal_period, planned_for=planned_for.astimezone(timezone.utc), servings=entry.servings, food_name=entry.food_name, serving_name=entry.serving_name, calories=entry.calories, protein_g=entry.protein_g, carbohydrates_g=entry.carbohydrates_g, fat_g=entry.fat_g, sugar_g=entry.sugar_g, source=entry.source, status=PlannedEntryStatus.PLANNED.value)


@router.get("/profiles/{profile_id}/planned", response_model=list[PlannedEntryOutput])
def list_planned_entries(profile_id: str, db: DbSession, start: date | None = None, days: int = Query(default=7, ge=1, le=31), include_completed: bool = True) -> list[PlannedEntry]:
    profile = get_profile(db, profile_id)
    start_date = start or profile_today(profile)
    first, _ = day_bounds(start_date, profile.timezone)
    _, last = day_bounds(start_date + timedelta(days=days - 1), profile.timezone)
    statement = select(PlannedEntry).where(PlannedEntry.profile_id == profile_id, PlannedEntry.planned_for.between(first, last))
    if not include_completed:
        statement = statement.where(PlannedEntry.status == PlannedEntryStatus.PLANNED.value)
    return list(db.scalars(statement.order_by(PlannedEntry.planned_for)).all())


@router.post("/profiles/{profile_id}/planned", response_model=PlannedEntryOutput, status_code=status.HTTP_201_CREATED)
def create_planned_entry(profile_id: str, payload: PlannedEntryCreate, db: DbSession) -> PlannedEntry:
    started = perf_counter()
    profile = get_profile(db, profile_id)
    if profile.archived:
        raise HTTPException(status_code=409, detail="Cannot plan entries for an archived profile")
    food = get_food(db, payload.food_id)
    entry = planned_from_food(profile=profile, food=food, planned_for=payload.planned_for, meal_period=payload.meal_period.value, servings=payload.servings)
    db.add(entry)
    update_usage(db, profile_id, food.id)
    db.commit()
    db.refresh(entry)
    logger.info("performance operation=add_to_plan duration_ms=%.1f", (perf_counter() - started) * 1000)
    return entry


@router.patch("/profiles/{profile_id}/planned/{entry_id}", response_model=PlannedEntryOutput)
def update_planned_entry(profile_id: str, entry_id: str, payload: PlannedEntryUpdate, db: DbSession) -> PlannedEntry:
    entry = db.scalar(select(PlannedEntry).where(PlannedEntry.id == entry_id, PlannedEntry.profile_id == profile_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Planned entry not found")
    if entry.status != PlannedEntryStatus.PLANNED.value:
        raise HTTPException(status_code=409, detail="Only planned entries can be edited")
    values = payload.model_dump(exclude_unset=True)
    servings = values.pop("servings", None)
    if servings is not None:
        ratio = servings / entry.servings
        entry.servings = servings
        entry.calories = round(entry.calories * ratio, 2)
        entry.protein_g = scale(entry.protein_g, ratio)
        entry.carbohydrates_g = scale(entry.carbohydrates_g, ratio)
        entry.fat_g = scale(entry.fat_g, ratio)
        entry.sugar_g = scale(entry.sugar_g, ratio)
    if values.get("meal_period") is not None:
        entry.meal_period = values["meal_period"].value
    if values.get("planned_for") is not None:
        entry.planned_for = values["planned_for"].astimezone(timezone.utc)
    db.commit(); db.refresh(entry); return entry


@router.post("/profiles/{profile_id}/planned/{entry_id}/consume", response_model=PlannedEntryOutput)
def consume_planned_entry(profile_id: str, entry_id: str, db: DbSession) -> PlannedEntry:
    entry = db.scalar(select(PlannedEntry).where(PlannedEntry.id == entry_id, PlannedEntry.profile_id == profile_id))
    if not entry: raise HTTPException(status_code=404, detail="Planned entry not found")
    if entry.status != PlannedEntryStatus.PLANNED.value: raise HTTPException(status_code=409, detail="Only planned entries can be marked consumed")
    diary = diary_from_planned(entry); db.add(diary); db.flush(); entry.status = PlannedEntryStatus.CONSUMED.value; entry.consumed_diary_entry_id = diary.id; db.commit(); db.refresh(entry); return entry


@router.post("/profiles/{profile_id}/planned/{entry_id}/skip", response_model=PlannedEntryOutput)
def skip_planned_entry(profile_id: str, entry_id: str, db: DbSession) -> PlannedEntry:
    entry = db.scalar(select(PlannedEntry).where(PlannedEntry.id == entry_id, PlannedEntry.profile_id == profile_id))
    if not entry: raise HTTPException(status_code=404, detail="Planned entry not found")
    if entry.status != PlannedEntryStatus.PLANNED.value: raise HTTPException(status_code=409, detail="Only planned entries can be skipped")
    entry.status = PlannedEntryStatus.SKIPPED.value; db.commit(); db.refresh(entry); return entry


@router.delete("/profiles/{profile_id}/planned/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_planned_entry(profile_id: str, entry_id: str, db: DbSession) -> Response:
    entry = db.scalar(select(PlannedEntry).where(PlannedEntry.id == entry_id, PlannedEntry.profile_id == profile_id))
    if not entry: raise HTTPException(status_code=404, detail="Planned entry not found")
    if entry.status == PlannedEntryStatus.CONSUMED.value: raise HTTPException(status_code=409, detail="Consumed planned entries cannot be deleted")
    db.delete(entry); db.commit(); return Response(status_code=status.HTTP_204_NO_CONTENT)


def recurrence_matches(target: date, rule: RecurrenceRule) -> bool:
    if target < rule.start_date or (rule.end_date is not None and target > rule.end_date): return False
    if rule.frequency == RecurrenceFrequency.DAILY.value: return True
    if rule.frequency == RecurrenceFrequency.WEEKDAYS.value: return target.weekday() < 5
    return (target - rule.start_date).days % 7 == 0


def materialise_rule(db: Session, profile: Profile, food: Food, rule: RecurrenceRule, horizon_days: int = 56) -> int:
    horizon_end = rule.start_date + timedelta(days=horizon_days - 1)
    end = min(rule.end_date, horizon_end) if rule.end_date is not None else horizon_end
    zone = ZoneInfo(profile.timezone); hour, minute = (int(part) for part in rule.local_time.split(":"))
    first = datetime.combine(rule.start_date, time.min, tzinfo=zone).astimezone(timezone.utc); last = datetime.combine(end, time.max, tzinfo=zone).astimezone(timezone.utc)
    existing = {aware_utc(value) for value in db.scalars(select(PlannedEntry.planned_for).where(PlannedEntry.recurrence_rule_id == rule.id, PlannedEntry.planned_for.between(first, last))).all()}
    created = 0; target = rule.start_date
    while target <= end:
        if recurrence_matches(target, rule):
            local_dt = datetime.combine(target, time(hour, minute), tzinfo=zone); utc_dt = local_dt.astimezone(timezone.utc)
            if utc_dt not in existing:
                db.add(planned_from_food(profile=profile, food=food, planned_for=local_dt, meal_period=rule.meal_period, servings=rule.servings, recurrence_rule_id=rule.id)); existing.add(utc_dt); created += 1
        target += timedelta(days=1)
    return created


@router.get("/profiles/{profile_id}/recurrence", response_model=list[RecurrenceRuleOutput])
def list_recurrence_rules(profile_id: str, db: DbSession, include_inactive: bool = False) -> list[RecurrenceRule]:
    get_profile(db, profile_id); statement = select(RecurrenceRule).where(RecurrenceRule.profile_id == profile_id)
    if not include_inactive: statement = statement.where(RecurrenceRule.active.is_(True))
    return list(db.scalars(statement.order_by(RecurrenceRule.start_date)).all())


@router.post("/profiles/{profile_id}/recurrence", response_model=RecurrenceRuleOutput, status_code=status.HTTP_201_CREATED)
def create_recurrence_rule(profile_id: str, payload: RecurrenceRuleCreate, db: DbSession) -> RecurrenceRule:
    started = perf_counter(); profile = get_profile(db, profile_id)
    if profile.archived: raise HTTPException(status_code=409, detail="Cannot create recurrence for an archived profile")
    food = get_food(db, payload.food_id); rule = RecurrenceRule(profile_id=profile.id, food_id=payload.food_id, frequency=payload.frequency.value, meal_period=payload.meal_period.value, servings=payload.servings, start_date=payload.start_date, end_date=payload.end_date, local_time=payload.local_time)
    db.add(rule); db.flush(); created = materialise_rule(db, profile, food, rule); update_usage(db, profile_id, food.id); db.commit(); db.refresh(rule)
    logger.info("performance operation=create_recurrence duration_ms=%.1f materialised=%d", (perf_counter() - started) * 1000, created); return rule


@router.post("/profiles/{profile_id}/recurrence/{rule_id}/archive", response_model=RecurrenceRuleOutput)
def archive_recurrence_rule(profile_id: str, rule_id: str, db: DbSession) -> RecurrenceRule:
    rule = db.scalar(select(RecurrenceRule).where(RecurrenceRule.id == rule_id, RecurrenceRule.profile_id == profile_id))
    if not rule: raise HTTPException(status_code=404, detail="Recurrence rule not found")
    rule.active = False; db.commit(); db.refresh(rule); return rule


@router.get("/profiles/{profile_id}/weekly-plan", response_model=WeeklyPlanOutput)
def weekly_plan(profile_id: str, db: DbSession, start: date | None = None) -> WeeklyPlanOutput:
    started = perf_counter(); profile = get_profile(db, profile_id); requested = start or profile_today(profile); week_start = requested - timedelta(days=requested.weekday()); week_end = week_start + timedelta(days=6); first, _ = day_bounds(week_start, profile.timezone); _, last = day_bounds(week_end, profile.timezone)
    planned = list(db.scalars(select(PlannedEntry).where(PlannedEntry.profile_id == profile_id, PlannedEntry.planned_for.between(first, last), PlannedEntry.status == PlannedEntryStatus.PLANNED.value)).all())
    consumed = list(db.scalars(select(DiaryEntry).where(DiaryEntry.profile_id == profile_id, DiaryEntry.consumed_at.between(first, last))).all())
    zone = ZoneInfo(profile.timezone); planned_by_day: dict[date, list[PlannedEntry]] = {}; consumed_by_day: dict[date, list[DiaryEntry]] = {}
    for item in planned: planned_by_day.setdefault(aware_utc(item.planned_for).astimezone(zone).date(), []).append(item)
    for item in consumed: consumed_by_day.setdefault(aware_utc(item.consumed_at).astimezone(zone).date(), []).append(item)
    days: list[WeeklyPlanDay] = []
    for offset in range(7):
        current = week_start + timedelta(days=offset); p = planned_by_day.get(current, []); c = consumed_by_day.get(current, []); days.append(WeeklyPlanDay(date=current, planned_calories=round(sum(item.calories for item in p)), planned_count=len(p), consumed_calories=round(sum(item.calories for item in c)), consumed_count=len(c)))
    output = WeeklyPlanOutput(profile_id=profile_id, start_date=week_start, end_date=week_end, days=days, planned_calories=sum(day.planned_calories for day in days), consumed_calories=sum(day.consumed_calories for day in days)); logger.info("performance operation=weekly_summary duration_ms=%.1f", (perf_counter() - started) * 1000); return output


@router.get("/profiles/{profile_id}/day-plan", response_model=DailyPlanOutput)
def day_plan(profile_id: str, db: DbSession, day: date | None = None) -> DailyPlanOutput:
    profile = get_profile(db, profile_id); target = day or profile_today(profile); first, last = day_bounds(target, profile.timezone)
    planned = list(db.scalars(select(PlannedEntry).where(PlannedEntry.profile_id == profile_id, PlannedEntry.planned_for.between(first, last), PlannedEntry.status == PlannedEntryStatus.PLANNED.value).order_by(PlannedEntry.planned_for)).all())
    consumed = list(db.scalars(select(DiaryEntry).where(DiaryEntry.profile_id == profile_id, DiaryEntry.consumed_at.between(first, last)).order_by(DiaryEntry.consumed_at)).all())
    planned_calories = round(sum(item.calories for item in planned)); consumed_calories = round(sum(item.calories for item in consumed)); combined = [*planned, *consumed]
    return DailyPlanOutput(profile_id=profile_id, date=target, calorie_target=profile.daily_calorie_target, consumed_calories=consumed_calories, planned_calories=planned_calories, remaining_after_planned=profile.daily_calorie_target - consumed_calories - planned_calories, protein_g=round(sum(item.protein_g or 0 for item in combined), 1), carbohydrates_g=round(sum(item.carbohydrates_g or 0 for item in combined), 1), fat_g=round(sum(item.fat_g or 0 for item in combined), 1), sugar_g=round(sum(item.sugar_g or 0 for item in combined), 1), planned=planned, consumed=consumed)


@router.post("/profiles/{profile_id}/copy-entry", response_model=PlannedEntryOutput, status_code=status.HTTP_201_CREATED)
def copy_entry(profile_id: str, payload: CopyEntryRequest, db: DbSession) -> PlannedEntry:
    profile = get_profile(db, profile_id); target_local = datetime.combine(payload.target_date, payload.local_time, tzinfo=ZoneInfo(profile.timezone)); planned = db.scalar(select(PlannedEntry).where(PlannedEntry.id == payload.entry_id, PlannedEntry.profile_id == profile_id))
    if planned: copy = copy_planned_snapshot(planned, profile_id, target_local, payload.meal_period.value if payload.meal_period else None)
    else:
        diary = db.scalar(select(DiaryEntry).where(DiaryEntry.id == payload.entry_id, DiaryEntry.profile_id == profile_id))
        if not diary: raise HTTPException(status_code=404, detail="Entry not found")
        copy = copy_diary_snapshot(diary, profile_id, target_local, payload.meal_period.value if payload.meal_period else None)
    db.add(copy); db.commit(); db.refresh(copy); return copy


@router.post("/profiles/{profile_id}/copy-meal", response_model=list[PlannedEntryOutput], status_code=status.HTTP_201_CREATED)
def copy_meal(profile_id: str, payload: CopyMealRequest, db: DbSession) -> list[PlannedEntry]:
    profile = get_profile(db, profile_id); first, last = day_bounds(payload.source_date, profile.timezone); zone = ZoneInfo(profile.timezone)
    planned = list(db.scalars(select(PlannedEntry).where(PlannedEntry.profile_id == profile_id, PlannedEntry.planned_for.between(first, last), PlannedEntry.meal_period == payload.meal_period.value)).all()); consumed = list(db.scalars(select(DiaryEntry).where(DiaryEntry.profile_id == profile_id, DiaryEntry.consumed_at.between(first, last), DiaryEntry.meal_period == payload.meal_period.value)).all()); copies: list[PlannedEntry] = []
    for item in planned: local = aware_utc(item.planned_for).astimezone(zone); copies.append(copy_planned_snapshot(item, profile_id, datetime.combine(payload.target_date, local.timetz().replace(tzinfo=None), tzinfo=zone)))
    for item in consumed: local = aware_utc(item.consumed_at).astimezone(zone); copies.append(copy_diary_snapshot(item, profile_id, datetime.combine(payload.target_date, local.timetz().replace(tzinfo=None), tzinfo=zone)))
    db.add_all(copies); db.commit(); [db.refresh(item) for item in copies]; return copies


@router.post("/profiles/{profile_id}/copy-day", response_model=list[PlannedEntryOutput], status_code=status.HTTP_201_CREATED)
def copy_day(profile_id: str, payload: CopyDayRequest, db: DbSession) -> list[PlannedEntry]:
    profile = get_profile(db, profile_id); first, last = day_bounds(payload.source_date, profile.timezone); zone = ZoneInfo(profile.timezone)
    planned = list(db.scalars(select(PlannedEntry).where(PlannedEntry.profile_id == profile_id, PlannedEntry.planned_for.between(first, last))).all()); consumed = list(db.scalars(select(DiaryEntry).where(DiaryEntry.profile_id == profile_id, DiaryEntry.consumed_at.between(first, last))).all()); copies: list[PlannedEntry] = []
    for item in planned: local = aware_utc(item.planned_for).astimezone(zone); copies.append(copy_planned_snapshot(item, profile_id, datetime.combine(payload.target_date, local.timetz().replace(tzinfo=None), tzinfo=zone)))
    for item in consumed: local = aware_utc(item.consumed_at).astimezone(zone); copies.append(copy_diary_snapshot(item, profile_id, datetime.combine(payload.target_date, local.timetz().replace(tzinfo=None), tzinfo=zone)))
    db.add_all(copies); db.commit(); [db.refresh(item) for item in copies]; return copies


@router.get("/profiles/{profile_id}/saved-meals", response_model=list[SavedMealOutput])
def list_saved_meals(profile_id: str, db: DbSession, include_archived: bool = False) -> list[SavedMeal]:
    get_profile(db, profile_id); statement = select(SavedMeal).where(SavedMeal.profile_id == profile_id)
    if not include_archived: statement = statement.where(SavedMeal.archived.is_(False))
    return list(db.scalars(statement.order_by(SavedMeal.name)).all())


@router.post("/profiles/{profile_id}/saved-meals", response_model=SavedMealOutput, status_code=status.HTTP_201_CREATED)
def create_saved_meal(profile_id: str, payload: SavedMealCreate, db: DbSession) -> SavedMeal:
    get_profile(db, profile_id); meal = SavedMeal(profile_id=profile_id, name=payload.name.strip(), default_meal_period=payload.default_meal_period.value); db.add(meal); db.flush()
    for position, item in enumerate(payload.items): get_food(db, item.food_id); db.add(SavedMealItem(saved_meal_id=meal.id, food_id=item.food_id, servings=item.servings, position=position))
    db.commit(); db.refresh(meal); return meal


@router.patch("/profiles/{profile_id}/saved-meals/{meal_id}", response_model=SavedMealOutput)
def update_saved_meal(profile_id: str, meal_id: str, payload: SavedMealUpdate, db: DbSession) -> SavedMeal:
    meal = db.scalar(select(SavedMeal).where(SavedMeal.id == meal_id, SavedMeal.profile_id == profile_id))
    if not meal: raise HTTPException(status_code=404, detail="Saved meal not found")
    if payload.name is not None: meal.name = payload.name.strip()
    if payload.default_meal_period is not None: meal.default_meal_period = payload.default_meal_period.value
    if payload.items is not None:
        for existing in list(meal.items): db.delete(existing)
        for position, item in enumerate(payload.items): get_food(db, item.food_id); db.add(SavedMealItem(saved_meal_id=meal.id, food_id=item.food_id, servings=item.servings, position=position))
    db.commit(); db.refresh(meal); return meal


@router.post("/profiles/{profile_id}/saved-meals/{meal_id}/archive", response_model=SavedMealOutput)
def archive_saved_meal(profile_id: str, meal_id: str, db: DbSession) -> SavedMeal:
    meal = db.scalar(select(SavedMeal).where(SavedMeal.id == meal_id, SavedMeal.profile_id == profile_id))
    if not meal: raise HTTPException(status_code=404, detail="Saved meal not found")
    meal.archived = True; db.commit(); db.refresh(meal); return meal


@router.post("/profiles/{profile_id}/saved-meals/{meal_id}/plan", response_model=list[PlannedEntryOutput], status_code=status.HTTP_201_CREATED)
def plan_saved_meal(profile_id: str, meal_id: str, payload: PlannedEntryCreate, db: DbSession) -> list[PlannedEntry]:
    profile = get_profile(db, profile_id); meal = db.scalar(select(SavedMeal).where(SavedMeal.id == meal_id, SavedMeal.profile_id == profile_id, SavedMeal.archived.is_(False)))
    if not meal: raise HTTPException(status_code=404, detail="Saved meal not found")
    entries: list[PlannedEntry] = []
    for item in sorted(meal.items, key=lambda value: value.position):
        food = get_food(db, item.food_id); entry = planned_from_food(profile=profile, food=food, planned_for=payload.planned_for, meal_period=payload.meal_period.value, servings=item.servings * payload.servings); entries.append(entry); db.add(entry); update_usage(db, profile_id, food.id)
    db.commit(); [db.refresh(entry) for entry in entries]; return entries
