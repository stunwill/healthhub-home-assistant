from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExerciseCreate(BaseModel):
    activity_name: str = Field(min_length=1, max_length=120)
    duration_minutes: int = Field(gt=0, le=1440)
    calories_burned: float = Field(ge=0, le=20000)
    completed_at: datetime
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("completed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("completed_at must include a timezone")
        return value


class ExerciseOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    activity_name: str
    duration_minutes: int
    calories_burned: float
    completed_at: datetime
    source: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


class WeightCreate(BaseModel):
    weight_kg: float = Field(gt=0, le=500)
    measured_at: datetime
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("measured_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("measured_at must include a timezone")
        return value


class WeightOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    weight_kg: float
    measured_at: datetime
    source: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


class DailySummaryV030(BaseModel):
    profile_id: str
    date: date
    calorie_target: int
    consumed_calories: int
    completed_exercise_calories: int
    credited_exercise_calories: int
    remaining_calories: int
    exercise_minutes: int
    protein_g: float
    carbohydrates_g: float
    fat_g: float
    entry_count: int


class ProgressSummary(BaseModel):
    profile_id: str
    period_start: date
    period_end: date
    exercise_minutes: int
    exercise_minutes_target: int
    exercise_calories: int
    latest_weight_kg: float | None
    latest_weight_at: datetime | None
    starting_weight_kg: float | None
    goal_weight_kg: float | None
    change_from_start_kg: float | None
    weight_entries: list[WeightOutput]
