from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .models import MealPeriod, utc_now


class PlannedEntryStatus(StrEnum):
    PLANNED = "planned"
    CONSUMED = "consumed"
    SKIPPED = "skipped"


class RecurrenceFrequency(StrEnum):
    DAILY = "daily"
    WEEKDAYS = "weekdays"
    WEEKLY = "weekly"


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

    __table_args__ = (
        Index("ix_planned_profile_date", "profile_id", "planned_for"),
        Index("ix_planned_profile_status", "profile_id", "status"),
    )
