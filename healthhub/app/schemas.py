from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import ExerciseCreditMode, MeasurementUnits, NutritionDisplayMode


class ProfileBase(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    colour: str | None = Field(default=None, max_length=20)
    avatar: str | None = Field(default=None, max_length=500)
    height_cm: float | None = Field(default=None, gt=0, le=300)
    starting_weight_kg: float | None = Field(default=None, gt=0, le=500)
    goal_weight_kg: float | None = Field(default=None, gt=0, le=500)
    target_date: date | None = None
    daily_calorie_target: int = Field(ge=1, le=20000)
    weekly_exercise_minutes_target: int = Field(default=0, ge=0, le=10080)
    hydration_target_ml: int | None = Field(default=None, ge=0, le=20000)
    exercise_credit_mode: ExerciseCreditMode = ExerciseCreditMode.NONE
    exercise_credit_percentage: int = Field(default=0, ge=0, le=100)
    nutrition_display_mode: NutritionDisplayMode = NutritionDisplayMode.SIMPLE
    timezone: str = "Australia/Melbourne"
    measurement_units: MeasurementUnits = MeasurementUnits.METRIC

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Timezone must be a valid IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def validate_credit_percentage(self) -> "ProfileBase":
        if self.exercise_credit_mode == ExerciseCreditMode.NONE and self.exercise_credit_percentage != 0:
            raise ValueError("No exercise credit requires a percentage of 0")
        if self.exercise_credit_mode == ExerciseCreditMode.FULL and self.exercise_credit_percentage != 100:
            raise ValueError("Full exercise credit requires a percentage of 100")
        return self


class ProfileCreate(ProfileBase):
    pass


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    colour: str | None = Field(default=None, max_length=20)
    avatar: str | None = Field(default=None, max_length=500)
    height_cm: float | None = Field(default=None, gt=0, le=300)
    starting_weight_kg: float | None = Field(default=None, gt=0, le=500)
    goal_weight_kg: float | None = Field(default=None, gt=0, le=500)
    target_date: date | None = None
    daily_calorie_target: int | None = Field(default=None, ge=1, le=20000)
    weekly_exercise_minutes_target: int | None = Field(default=None, ge=0, le=10080)
    hydration_target_ml: int | None = Field(default=None, ge=0, le=20000)
    exercise_credit_mode: ExerciseCreditMode | None = None
    exercise_credit_percentage: int | None = Field(default=None, ge=0, le=100)
    nutrition_display_mode: NutritionDisplayMode | None = None
    timezone: str | None = None
    measurement_units: MeasurementUnits | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Timezone must be a valid IANA timezone") from exc
        return value


class ProfileOutput(ProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    archived: bool
    created_at: datetime
    updated_at: datetime


class ActiveProfileSelection(BaseModel):
    profile_id: str


class ActiveProfileResponse(BaseModel):
    profile_id: str


class CalorieBudgetInput(BaseModel):
    daily_calorie_target: int = Field(ge=0)
    consumed_food_calories: float = Field(ge=0)
    completed_exercise_calories: float = Field(ge=0)
    exercise_credit_mode: ExerciseCreditMode
    exercise_credit_percentage: int = Field(ge=0, le=100)


class CalorieBudgetOutput(BaseModel):
    credited_exercise_calories: int
    remaining_calories: int
