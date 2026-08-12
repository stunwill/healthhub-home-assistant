from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


class FoodKind(StrEnum):
    FOOD = "food"
    DRINK = "drink"


class MealPeriod(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    DRINK = "drink"


class PlannedEntryStatus(StrEnum):
    PLANNED = "planned"
    CONSUMED = "consumed"
    SKIPPED = "skipped"


class RecurrenceFrequency(StrEnum):
    DAILY = "daily"
    WEEKDAYS = "weekdays"
    WEEKLY = "weekly"


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

    diary_entries: Mapped[list[DiaryEntry]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    planned_entries: Mapped[list[PlannedEntry]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    recurrence_rules: Mapped[list[RecurrenceRule]] = relationship(back_populates="profile", cascade="all, delete-orphan")


class Food(Base):
    __tablename__ = "foods"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(180), index=True)
    brand: Mapped[str | None] = mapped_column(String(120), index=True)
    kind: Mapped[str] = mapped_column(String(20), default=FoodKind.FOOD.value, index=True)
    serving_name: Mapped[str] = mapped_column(String(100), default="1 serve")
    serving_grams: Mapped[float | None] = mapped_column(Float)
    energy_kj: Mapped[float | None] = mapped_column(Float)
    calories: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float | None] = mapped_column(Float)
    carbohydrates_g: Mapped[float | None] = mapped_column(Float)
    fat_g: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40), default="manual", index=True)
    favourite: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    diary_entries: Mapped[list[DiaryEntry]] = relationship(back_populates="food")
    planned_entries: Mapped[list[PlannedEntry]] = relationship(back_populates="food")
    recurrence_rules: Mapped[list[RecurrenceRule]] = relationship(back_populates="food")

    __table_args__ = (Index("ix_foods_search", "archived", "name", "brand"),)


class DiaryEntry(Base):
    __tablename__ = "diary_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    food_id: Mapped[str | None] = mapped_column(ForeignKey("foods.id", ondelete="SET NULL"), index=True)
    meal_period: Mapped[str] = mapped_column(String(20), default=MealPeriod.SNACK.value, index=True)
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    servings: Mapped[float] = mapped_column(Float, default=1.0)
    food_name: Mapped[str] = mapped_column(String(180))
    serving_name: Mapped[str] = mapped_column(String(100))
    calories: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float | None] = mapped_column(Float)
    carbohydrates_g: Mapped[float | None] = mapped_column(Float)
    fat_g: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40), default="healthhub")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    profile: Mapped[Profile] = relationship(back_populates="diary_entries")
    food: Mapped[Food | None] = relationship(back_populates="diary_entries")

    __table_args__ = (Index("ix_diary_profile_consumed", "profile_id", "consumed_at"),)


class RecurrenceRule(Base):
    __tablename__ = "recurrence_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    food_id: Mapped[str] = mapped_column(ForeignKey("foods.id", ondelete="CASCADE"), index=True)
    frequency: Mapped[str] = mapped_column(String(20), index=True)
    meal_period: Mapped[str] = mapped_column(String(20), default=MealPeriod.SNACK.value)
    servings: Mapped[float] = mapped_column(Float, default=1.0)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date | None] = mapped_column(Date)
    local_time: Mapped[str] = mapped_column(String(5), default="12:00")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    profile: Mapped[Profile] = relationship(back_populates="recurrence_rules")
    food: Mapped[Food] = relationship(back_populates="recurrence_rules")
    planned_entries: Mapped[list[PlannedEntry]] = relationship(back_populates="recurrence_rule")


class PlannedEntry(Base):
    __tablename__ = "planned_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    food_id: Mapped[str | None] = mapped_column(ForeignKey("foods.id", ondelete="SET NULL"), index=True)
    recurrence_rule_id: Mapped[str | None] = mapped_column(ForeignKey("recurrence_rules.id", ondelete="SET NULL"), index=True)
    meal_period: Mapped[str] = mapped_column(String(20), default=MealPeriod.SNACK.value, index=True)
    planned_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    servings: Mapped[float] = mapped_column(Float, default=1.0)
    food_name: Mapped[str] = mapped_column(String(180))
    serving_name: Mapped[str] = mapped_column(String(100))
    calories: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float | None] = mapped_column(Float)
    carbohydrates_g: Mapped[float | None] = mapped_column(Float)
    fat_g: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40), default="healthhub")
    status: Mapped[str] = mapped_column(String(20), default=PlannedEntryStatus.PLANNED.value, index=True)
    consumed_diary_entry_id: Mapped[str | None] = mapped_column(ForeignKey("diary_entries.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    profile: Mapped[Profile] = relationship(back_populates="planned_entries")
    food: Mapped[Food | None] = relationship(back_populates="planned_entries")
    recurrence_rule: Mapped[RecurrenceRule | None] = relationship(back_populates="planned_entries")

    __table_args__ = (
        Index("ix_planned_profile_date", "profile_id", "planned_for"),
        Index("ix_planned_profile_status", "profile_id", "status"),
    )
