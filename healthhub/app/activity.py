from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .activity_models import ExerciseEntry, WaterEntry, WeightEntry
from .activity_schemas import (
    DailySummaryV030,
    ExerciseCreate,
    ExerciseOutput,
    ProgressSummary,
    WaterCreate,
    WaterOutput,
    WeightCreate,
    WeightOutput,
)
from .database import get_db
from .domain import calorie_budget
from .models import DiaryEntry, ExerciseCreditMode, Profile

router = APIRouter(prefix="/api/v1", tags=["activity"])
DbSession = Annotated[Session, Depends(get_db)]


def get_profile(db: Session, profile_id: str) -> Profile:
    profile = db.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


def local_day_bounds(target: date, timezone_name: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone_name)
    start = datetime.combine(target, time.min, tzinfo=zone).astimezone(timezone.utc)
    end = datetime.combine(target, time.max, tzinfo=zone).astimezone(timezone.utc)
    return start, end


def range_bounds(start: date, end: date, timezone_name: str) -> tuple[datetime, datetime]:
    first, _ = local_day_bounds(start, timezone_name)
    _, last = local_day_bounds(end, timezone_name)
    return first, last


@router.get("/profiles/{profile_id}/exercise", response_model=list[ExerciseOutput])
def list_exercise(
    profile_id: str,
    db: DbSession,
    start: date | None = None,
    end: date | None = None,
) -> list[ExerciseEntry]:
    profile = get_profile(db, profile_id)
    statement = select(ExerciseEntry).where(ExerciseEntry.profile_id == profile_id)
    if start is not None or end is not None:
        start_date = start or date.min
        end_date = end or date.max
        first, last = range_bounds(start_date, end_date, profile.timezone)
        statement = statement.where(ExerciseEntry.completed_at.between(first, last))
    return list(db.scalars(statement.order_by(ExerciseEntry.completed_at.desc())).all())


@router.post("/profiles/{profile_id}/exercise", response_model=ExerciseOutput, status_code=status.HTTP_201_CREATED)
def create_exercise(profile_id: str, payload: ExerciseCreate, db: DbSession) -> ExerciseEntry:
    profile = get_profile(db, profile_id)
    if profile.archived:
        raise HTTPException(status_code=409, detail="Cannot log exercise for an archived profile")
    entry = ExerciseEntry(
        profile_id=profile_id,
        activity_name=payload.activity_name.strip(),
        duration_minutes=payload.duration_minutes,
        calories_burned=payload.calories_burned,
        completed_at=payload.completed_at.astimezone(timezone.utc),
        source="manual",
        notes=payload.notes,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/profiles/{profile_id}/exercise/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise(profile_id: str, entry_id: str, db: DbSession) -> Response:
    entry = db.scalar(select(ExerciseEntry).where(ExerciseEntry.id == entry_id, ExerciseEntry.profile_id == profile_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Exercise entry not found")
    db.delete(entry)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/profiles/{profile_id}/weights", response_model=list[WeightOutput])
def list_weights(profile_id: str, db: DbSession, days: int = Query(default=90, ge=1, le=730)) -> list[WeightEntry]:
    profile = get_profile(db, profile_id)
    end_date = datetime.now(ZoneInfo(profile.timezone)).date()
    start_date = end_date - timedelta(days=days - 1)
    first, last = range_bounds(start_date, end_date, profile.timezone)
    statement = (
        select(WeightEntry)
        .where(WeightEntry.profile_id == profile_id, WeightEntry.measured_at.between(first, last))
        .order_by(WeightEntry.measured_at.desc())
    )
    return list(db.scalars(statement).all())


@router.post("/profiles/{profile_id}/weights", response_model=WeightOutput, status_code=status.HTTP_201_CREATED)
def create_weight(profile_id: str, payload: WeightCreate, db: DbSession) -> WeightEntry:
    profile = get_profile(db, profile_id)
    if profile.archived:
        raise HTTPException(status_code=409, detail="Cannot log weight for an archived profile")
    entry = WeightEntry(
        profile_id=profile_id,
        weight_kg=payload.weight_kg,
        measured_at=payload.measured_at.astimezone(timezone.utc),
        source="manual",
        notes=payload.notes,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/profiles/{profile_id}/weights/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_weight(profile_id: str, entry_id: str, db: DbSession) -> Response:
    entry = db.scalar(select(WeightEntry).where(WeightEntry.id == entry_id, WeightEntry.profile_id == profile_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Weight entry not found")
    db.delete(entry)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/profiles/{profile_id}/water", response_model=list[WaterOutput])
def list_water(profile_id: str, db: DbSession, day: date | None = None) -> list[WaterEntry]:
    profile = get_profile(db, profile_id)
    target = day or datetime.now(ZoneInfo(profile.timezone)).date()
    first, last = local_day_bounds(target, profile.timezone)
    statement = (
        select(WaterEntry)
        .where(WaterEntry.profile_id == profile_id, WaterEntry.consumed_at.between(first, last))
        .order_by(WaterEntry.consumed_at.desc())
    )
    return list(db.scalars(statement).all())


@router.post("/profiles/{profile_id}/water", response_model=WaterOutput, status_code=status.HTTP_201_CREATED)
def create_water(profile_id: str, payload: WaterCreate, db: DbSession) -> WaterEntry:
    profile = get_profile(db, profile_id)
    if profile.archived:
        raise HTTPException(status_code=409, detail="Cannot log water for an archived profile")
    entry = WaterEntry(
        profile_id=profile_id,
        amount_ml=payload.amount_ml,
        consumed_at=payload.consumed_at.astimezone(timezone.utc),
        source="manual",
        notes=payload.notes,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/profiles/{profile_id}/water/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_water(profile_id: str, entry_id: str, db: DbSession) -> Response:
    entry = db.scalar(select(WaterEntry).where(WaterEntry.id == entry_id, WaterEntry.profile_id == profile_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Water entry not found")
    db.delete(entry)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/profiles/{profile_id}/daily-summary", response_model=DailySummaryV030)
def daily_summary(profile_id: str, db: DbSession, day: date = Query(default_factory=date.today)) -> DailySummaryV030:
    profile = get_profile(db, profile_id)
    first, last = local_day_bounds(day, profile.timezone)
    diary_entries = list(
        db.scalars(select(DiaryEntry).where(DiaryEntry.profile_id == profile_id, DiaryEntry.consumed_at.between(first, last))).all()
    )
    exercise_entries = list(
        db.scalars(select(ExerciseEntry).where(ExerciseEntry.profile_id == profile_id, ExerciseEntry.completed_at.between(first, last))).all()
    )
    water_entries = list(
        db.scalars(select(WaterEntry).where(WaterEntry.profile_id == profile_id, WaterEntry.consumed_at.between(first, last))).all()
    )
    consumed = sum(entry.calories for entry in diary_entries)
    exercise_calories = sum(entry.calories_burned for entry in exercise_entries)
    exercise_minutes = sum(entry.duration_minutes for entry in exercise_entries)
    credited, remaining = calorie_budget(
        daily_calorie_target=profile.daily_calorie_target,
        consumed_food_calories=consumed,
        completed_exercise_calories=exercise_calories,
        exercise_credit_mode=ExerciseCreditMode(profile.exercise_credit_mode),
        exercise_credit_percentage=profile.exercise_credit_percentage,
    )
    return DailySummaryV030(
        profile_id=profile_id,
        date=day,
        calorie_target=profile.daily_calorie_target,
        consumed_calories=round(consumed),
        completed_exercise_calories=round(exercise_calories),
        credited_exercise_calories=credited,
        remaining_calories=remaining,
        exercise_minutes=exercise_minutes,
        hydration_ml=sum(entry.amount_ml for entry in water_entries),
        hydration_target_ml=profile.hydration_target_ml,
        protein_g=round(sum(entry.protein_g or 0 for entry in diary_entries), 1),
        carbohydrates_g=round(sum(entry.carbohydrates_g or 0 for entry in diary_entries), 1),
        fat_g=round(sum(entry.fat_g or 0 for entry in diary_entries), 1),
        sugar_g=round(sum(entry.sugar_g or 0 for entry in diary_entries), 1),
        entry_count=len(diary_entries),
    )


@router.get("/profiles/{profile_id}/progress", response_model=ProgressSummary)
def progress_summary(profile_id: str, db: DbSession, days: int = Query(default=90, ge=7, le=730)) -> ProgressSummary:
    profile = get_profile(db, profile_id)
    local_today = datetime.now(ZoneInfo(profile.timezone)).date()
    period_start = local_today - timedelta(days=days - 1)
    first, last = range_bounds(period_start, local_today, profile.timezone)
    exercises = list(
        db.scalars(select(ExerciseEntry).where(ExerciseEntry.profile_id == profile_id, ExerciseEntry.completed_at.between(first, last))).all()
    )
    weights = list(
        db.scalars(
            select(WeightEntry)
            .where(WeightEntry.profile_id == profile_id, WeightEntry.measured_at.between(first, last))
            .order_by(WeightEntry.measured_at.desc())
        ).all()
    )
    week_first, _ = local_day_bounds(local_today - timedelta(days=6), profile.timezone)
    today_first, today_last = local_day_bounds(local_today, profile.timezone)
    water_today = list(
        db.scalars(select(WaterEntry).where(WaterEntry.profile_id == profile_id, WaterEntry.consumed_at.between(today_first, today_last))).all()
    )
    latest = weights[0] if weights else None
    change = None
    if latest is not None and profile.starting_weight_kg is not None:
        change = round(latest.weight_kg - profile.starting_weight_kg, 2)
    weight_30_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    older = next((entry for entry in weights if entry.measured_at <= weight_30_cutoff), None)
    change_30 = round(latest.weight_kg - older.weight_kg, 2) if latest is not None and older is not None else None
    return ProgressSummary(
        profile_id=profile_id,
        period_start=period_start,
        period_end=local_today,
        exercise_minutes=sum(entry.duration_minutes for entry in exercises),
        exercise_minutes_last_7_days=sum(entry.duration_minutes for entry in exercises if entry.completed_at >= week_first),
        exercise_minutes_target=profile.weekly_exercise_minutes_target,
        exercise_calories=round(sum(entry.calories_burned for entry in exercises)),
        hydration_ml_today=sum(entry.amount_ml for entry in water_today),
        hydration_target_ml=profile.hydration_target_ml,
        latest_weight_kg=latest.weight_kg if latest else None,
        latest_weight_at=latest.measured_at if latest else None,
        starting_weight_kg=profile.starting_weight_kg,
        goal_weight_kg=profile.goal_weight_kg,
        change_from_start_kg=change,
        change_last_30_days_kg=change_30,
        weight_entries=[WeightOutput.model_validate(entry) for entry in weights],
    )
