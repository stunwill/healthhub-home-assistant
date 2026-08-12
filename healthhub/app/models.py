from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExerciseCreditMode(StrEnum):
    NONE = "none"
    FULL = "full"
    PERCENTAGE = "percentage"


class NutritionDisplayMode(StrEnum):
    SIMPLE = "simple"
    BALANCED = "balanced"
    DETAILED = "detailed"


class MeasurementUnits(StrEnum):
    METRIC = "metric"


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    display_name: Mapped[str] = mapped_column(String(100), index=True)
    colour: Mapped[str | None] = mapped_column(String(20))
    avatar: Mapped[str | None] = mapped_column(String(500))
    height_cm: Mapped[float | None] = mapped_column(Float)
    starting_weight_kg: Mapped[float | None] = mapped_column(Float)
    goal_weight_kg: Mapped[float | None] = mapped_column(Float)
    target_date: Mapped[date | None] = mapped_column(Date)
    daily_calorie_target: Mapped[int] = mapped_column(Integer)
    weekly_exercise_minutes_target: Mapped[int] = mapped_column(Integer, default=0)
    hydration_target_ml: Mapped[int | None] = mapped_column(Integer)
    exercise_credit_mode: Mapped[str] = mapped_column(String(20), default=ExerciseCreditMode.NONE.value)
    exercise_credit_percentage: Mapped[int] = mapped_column(Integer, default=0)
    nutrition_display_mode: Mapped[str] = mapped_column(String(20), default=NutritionDisplayMode.SIMPLE.value)
    timezone: Mapped[str] = mapped_column(String(100), default="Australia/Melbourne")
    measurement_units: Mapped[str] = mapped_column(String(20), default=MeasurementUnits.METRIC.value)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
