from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import (
    DiaryEntry,
    Food,
    PlannedEntry,
    PlannedEntryStatus,
    Profile,
    RecurrenceFrequency,
    RecurrenceRule,
)
from .planning_schemas import (
    PlannedEntryCreate,
    PlannedEntryOutput,
    RecurrenceRuleCreate,
    RecurrenceRuleOutput,
    WeeklyPlanDay,
    WeeklyPlanOutput,
)

router = APIRouter(prefix="/api/v1", tags=["planning"])
DbSession = Annotated[Session, Depends(get_db)]


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


def day_bounds(target: date, timezone_name: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone_name)
    start = datetime.combine(target, time.min, tzinfo=zone).astimezone(timezone.utc)
    end = datetime.combine(target, time.max, tzinfo=zone).astimezone(timezone.utc)
    return start, end


def scale(value: float | None, servings: float) -> float | None:
    return round(value * servings, 2) if value is not None else None


def planned_from_food(
    *,
    profile: Profile,
    food: Food,
    planned_for: datetime,
    meal_period: str,
    servings: float,
    recurrence_rule_id: str | None = None,
) -> PlannedEntry:
    return PlannedEntry(
        profile_id=profile.id,
        food_id=food.id,
        recurrence_rule_id=recurrence_rule_id,
        meal_period=meal_period,
        planned_for=planned_for.astimezone(timezone.utc),
        servings=servings,
        food_name=food.name,
        serving_name=food.serving_name,
        calories=round(food.calories * servings, 2),
        protein_g=scale(food.protein_g, servings),
        carbohydrates_g=scale(food.carbohydrates_g, servings),
        fat_g=scale(food.fat_g, servings),
        source=food.source,
    )


@router.get("/profiles/{profile_id}/planned", response_model=list[PlannedEntryOutput])
def list_planned_entries(
    profile_id: str,
    db: DbSession,
    start: date = Query(default_factory=date.today),
    days: int = Query(default=7, ge=1, le=31),
    include_completed: bool = True,
) -> list[PlannedEntry]:
    profile = get_profile(db, profile_id)
    first, _ = day_bounds(start, profile.timezone)
    _, last = day_bounds(start + timedelta(days=days - 1), profile.timezone)
    statement = select(PlannedEntry).where(
        PlannedEntry.profile_id == profile_id,
        PlannedEntry.planned_for.between(first, last),
    )
    if not include_completed:
        statement = statement.where(PlannedEntry.status == PlannedEntryStatus.PLANNED.value)
    return list(db.scalars(statement.order_by(PlannedEntry.planned_for)).all())


@router.post(
    "/profiles/{profile_id}/planned",
    response_model=PlannedEntryOutput,
    status_code=status.HTTP_201_CREATED,
)
def create_planned_entry(profile_id: str, payload: PlannedEntryCreate, db: DbSession) -> PlannedEntry:
    profile = get_profile(db, profile_id)
    if profile.archived:
        raise HTTPException(status_code=409, detail="Cannot plan entries for an archived profile")
    food = get_food(db, payload.food_id)
    entry = planned_from_food(
        profile=profile,
        food=food,
        planned_for=payload.planned_for,
        meal_period=payload.meal_period.value,
        servings=payload.servings,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/profiles/{profile_id}/planned/{entry_id}/consume", response_model=PlannedEntryOutput)
def consume_planned_entry(profile_id: str, entry_id: str, db: DbSession) -> PlannedEntry:
    entry = db.scalar(select(PlannedEntry).where(PlannedEntry.id == entry_id, PlannedEntry.profile_id == profile_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Planned entry not found")
    if entry.status != PlannedEntryStatus.PLANNED.value:
        raise HTTPException(status_code=409, detail="Only planned entries can be marked consumed")
    diary = DiaryEntry(
        profile_id=entry.profile_id,
        food_id=entry.food_id,
        meal_period=entry.meal_period,
        consumed_at=entry.planned_for,
        servings=entry.servings,
        food_name=entry.food_name,
        serving_name=entry.serving_name,
        calories=entry.calories,
        protein_g=entry.protein_g,
        carbohydrates_g=entry.carbohydrates_g,
        fat_g=entry.fat_g,
        source=entry.source,
    )
    db.add(diary)
    db.flush()
    entry.status = PlannedEntryStatus.CONSUMED.value
    entry.consumed_diary_entry_id = diary.id
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/profiles/{profile_id}/planned/{entry_id}/skip", response_model=PlannedEntryOutput)
def skip_planned_entry(profile_id: str, entry_id: str, db: DbSession) -> PlannedEntry:
    entry = db.scalar(select(PlannedEntry).where(PlannedEntry.id == entry_id, PlannedEntry.profile_id == profile_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Planned entry not found")
    if entry.status != PlannedEntryStatus.PLANNED.value:
        raise HTTPException(status_code=409, detail="Only planned entries can be skipped")
    entry.status = PlannedEntryStatus.SKIPPED.value
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/profiles/{profile_id}/planned/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_planned_entry(profile_id: str, entry_id: str, db: DbSession) -> Response:
    entry = db.scalar(select(PlannedEntry).where(PlannedEntry.id == entry_id, PlannedEntry.profile_id == profile_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Planned entry not found")
    if entry.status == PlannedEntryStatus.CONSUMED.value:
        raise HTTPException(status_code=409, detail="Consumed planned entries cannot be deleted")
    db.delete(entry)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def recurrence_matches(target: date, rule: RecurrenceRule) -> bool:
    if target < rule.start_date or (rule.end_date is not None and target > rule.end_date):
        return False
    if rule.frequency == RecurrenceFrequency.DAILY.value:
        return True
    if rule.frequency == RecurrenceFrequency.WEEKDAYS.value:
        return target.weekday() < 5
    return (target - rule.start_date).days % 7 == 0


def materialise_rule(db: Session, profile: Profile, food: Food, rule: RecurrenceRule, horizon_days: int = 56) -> int:
    end = min(rule.end_date or (rule.start_date + timedelta(days=horizon_days - 1)), rule.start_date + timedelta(days=horizon_days - 1))
    zone = ZoneInfo(profile.timezone)
    hour, minute = (int(part) for part in rule.local_time.split(":"))
    created = 0
    target = rule.start_date
    while target <= end:
        if recurrence_matches(target, rule):
            local_dt = datetime.combine(target, time(hour, minute), tzinfo=zone)
            utc_dt = local_dt.astimezone(timezone.utc)
            exists = db.scalar(
                select(PlannedEntry.id).where(
                    PlannedEntry.recurrence_rule_id == rule.id,
                    PlannedEntry.planned_for == utc_dt,
                )
            )
            if not exists:
                db.add(
                    planned_from_food(
                        profile=profile,
                        food=food,
                        planned_for=local_dt,
                        meal_period=rule.meal_period,
                        servings=rule.servings,
                        recurrence_rule_id=rule.id,
                    )
                )
                created += 1
        target += timedelta(days=1)
    return created


@router.get("/profiles/{profile_id}/recurrence", response_model=list[RecurrenceRuleOutput])
def list_recurrence_rules(profile_id: str, db: DbSession, include_inactive: bool = False) -> list[RecurrenceRule]:
    get_profile(db, profile_id)
    statement = select(RecurrenceRule).where(RecurrenceRule.profile_id == profile_id)
    if not include_inactive:
        statement = statement.where(RecurrenceRule.active.is_(True))
    return list(db.scalars(statement.order_by(RecurrenceRule.start_date)).all())


@router.post(
    "/profiles/{profile_id}/recurrence",
    response_model=RecurrenceRuleOutput,
    status_code=status.HTTP_201_CREATED,
)
def create_recurrence_rule(profile_id: str, payload: RecurrenceRuleCreate, db: DbSession) -> RecurrenceRule:
    profile = get_profile(db, profile_id)
    if profile.archived:
        raise HTTPException(status_code=409, detail="Cannot create recurrence for an archived profile")
    food = get_food(db, payload.food_id)
    rule = RecurrenceRule(profile_id=profile.id, **payload.model_dump(mode="json"))
    db.add(rule)
    db.flush()
    materialise_rule(db, profile, food, rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.post("/profiles/{profile_id}/recurrence/{rule_id}/archive", response_model=RecurrenceRuleOutput)
def archive_recurrence_rule(profile_id: str, rule_id: str, db: DbSession) -> RecurrenceRule:
    rule = db.scalar(select(RecurrenceRule).where(RecurrenceRule.id == rule_id, RecurrenceRule.profile_id == profile_id))
    if not rule:
        raise HTTPException(status_code=404, detail="Recurrence rule not found")
    rule.active = False
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/profiles/{profile_id}/weekly-plan", response_model=WeeklyPlanOutput)
def weekly_plan(profile_id: str, db: DbSession, start: date = Query(default_factory=date.today)) -> WeeklyPlanOutput:
    profile = get_profile(db, profile_id)
    week_start = start - timedelta(days=start.weekday())
    day_rows: list[WeeklyPlanDay] = []
    planned_total = 0
    consumed_total = 0
    for offset in range(7):
        current = week_start + timedelta(days=offset)
        first, last = day_bounds(current, profile.timezone)
        planned = list(
            db.scalars(
                select(PlannedEntry).where(
                    PlannedEntry.profile_id == profile_id,
                    PlannedEntry.planned_for.between(first, last),
                    PlannedEntry.status == PlannedEntryStatus.PLANNED.value,
                )
            ).all()
        )
        consumed = list(
            db.scalars(
                select(DiaryEntry).where(
                    DiaryEntry.profile_id == profile_id,
                    DiaryEntry.consumed_at.between(first, last),
                )
            ).all()
        )
        planned_kcal = round(sum(item.calories for item in planned))
        consumed_kcal = round(sum(item.calories for item in consumed))
        planned_total += planned_kcal
        consumed_total += consumed_kcal
        day_rows.append(
            WeeklyPlanDay(
                date=current,
                planned_calories=planned_kcal,
                planned_count=len(planned),
                consumed_calories=consumed_kcal,
                consumed_count=len(consumed),
            )
        )
    return WeeklyPlanOutput(
        profile_id=profile_id,
        start_date=week_start,
        end_date=week_start + timedelta(days=6),
        days=day_rows,
        planned_calories=planned_total,
        consumed_calories=consumed_total,
    )
