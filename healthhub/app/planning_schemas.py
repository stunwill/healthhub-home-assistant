from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import MealPeriod, PlannedEntryStatus, RecurrenceFrequency


class PlannedEntryCreate(BaseModel):
    food_id: str
    meal_period: MealPeriod = MealPeriod.SNACK
    planned_for: datetime
    servings: float = Field(default=1.0, gt=0, le=100)

    @field_validator("planned_for")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("planned_for must include a timezone")
        return value


class PlannedEntryOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    food_id: str | None
    recurrence_rule_id: str | None
    meal_period: MealPeriod
    planned_for: datetime
    servings: float
    food_name: str
    serving_name: str
    calories: float
    protein_g: float | None
    carbohydrates_g: float | None
    fat_g: float | None
    source: str
    status: PlannedEntryStatus
    consumed_diary_entry_id: str | None
    created_at: datetime
    updated_at: datetime


class RecurrenceRuleCreate(BaseModel):
    food_id: str
    frequency: RecurrenceFrequency
    meal_period: MealPeriod = MealPeriod.SNACK
    servings: float = Field(default=1.0, gt=0, le=100)
    start_date: date
    end_date: date | None = None
    local_time: str = Field(default="12:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")

    @model_validator(mode="after")
    def validate_dates(self) -> "RecurrenceRuleCreate":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class RecurrenceRuleOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    food_id: str
    frequency: RecurrenceFrequency
    meal_period: MealPeriod
    servings: float
    start_date: date
    end_date: date | None
    local_time: str
    active: bool
    created_at: datetime
    updated_at: datetime


class WeeklyPlanDay(BaseModel):
    date: date
    planned_calories: int
    planned_count: int
    consumed_calories: int
    consumed_count: int


class WeeklyPlanOutput(BaseModel):
    profile_id: str
    start_date: date
    end_date: date
    days: list[WeeklyPlanDay]
    planned_calories: int
    consumed_calories: int
