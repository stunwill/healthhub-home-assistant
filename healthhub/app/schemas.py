from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import ExerciseCreditMode, FoodKind, MealPeriod, MeasurementUnits, NutritionDisplayMode, NutritionField


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
    nutrition_display_fields: list[NutritionField] = Field(default_factory=lambda: [NutritionField.CALORIES], min_length=1)
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

    @field_validator("nutrition_display_fields")
    @classmethod
    def unique_nutrition_fields(cls, values: list[NutritionField]) -> list[NutritionField]:
        return list(dict.fromkeys(values))

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
    nutrition_display_fields: list[NutritionField] | None = Field(default=None, min_length=1)
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

    @field_validator("nutrition_display_fields")
    @classmethod
    def unique_nutrition_fields(cls, values: list[NutritionField] | None) -> list[NutritionField] | None:
        return list(dict.fromkeys(values)) if values is not None else None


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


class FoodBase(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    brand: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=80)
    kind: FoodKind = FoodKind.FOOD
    serving_name: str = Field(default="1 serve", min_length=1, max_length=100)
    serving_unit: str = Field(default="serving", min_length=1, max_length=40)
    serving_grams: float | None = Field(default=None, gt=0, le=10000)
    energy_kj: float | None = Field(default=None, ge=0, le=100000)
    calories: float = Field(ge=0, le=25000)
    protein_g: float | None = Field(default=None, ge=0, le=5000)
    carbohydrates_g: float | None = Field(default=None, ge=0, le=5000)
    fat_g: float | None = Field(default=None, ge=0, le=5000)
    saturated_fat_g: float | None = Field(default=None, ge=0, le=5000)
    sugar_g: float | None = Field(default=None, ge=0, le=5000)
    fibre_g: float | None = Field(default=None, ge=0, le=5000)
    sodium_mg: float | None = Field(default=None, ge=0, le=100000)
    calcium_mg: float | None = Field(default=None, ge=0, le=100000)
    iron_mg: float | None = Field(default=None, ge=0, le=10000)
    potassium_mg: float | None = Field(default=None, ge=0, le=100000)
    cholesterol_mg: float | None = Field(default=None, ge=0, le=100000)
    alcohol_g: float | None = Field(default=None, ge=0, le=5000)
    caffeine_mg: float | None = Field(default=None, ge=0, le=100000)
    data_quality: str = Field(default="user_entered", min_length=1, max_length=40)
    favourite: bool = False
    notes: str | None = Field(default=None, max_length=1000)


class FoodCreate(FoodBase):
    source: str = Field(default="manual", min_length=1, max_length=40)


class FoodUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    brand: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=80)
    kind: FoodKind | None = None
    serving_name: str | None = Field(default=None, min_length=1, max_length=100)
    serving_unit: str | None = Field(default=None, min_length=1, max_length=40)
    serving_grams: float | None = Field(default=None, gt=0, le=10000)
    energy_kj: float | None = Field(default=None, ge=0, le=100000)
    calories: float | None = Field(default=None, ge=0, le=25000)
    protein_g: float | None = Field(default=None, ge=0, le=5000)
    carbohydrates_g: float | None = Field(default=None, ge=0, le=5000)
    fat_g: float | None = Field(default=None, ge=0, le=5000)
    saturated_fat_g: float | None = Field(default=None, ge=0, le=5000)
    sugar_g: float | None = Field(default=None, ge=0, le=5000)
    fibre_g: float | None = Field(default=None, ge=0, le=5000)
    sodium_mg: float | None = Field(default=None, ge=0, le=100000)
    calcium_mg: float | None = Field(default=None, ge=0, le=100000)
    iron_mg: float | None = Field(default=None, ge=0, le=10000)
    potassium_mg: float | None = Field(default=None, ge=0, le=100000)
    cholesterol_mg: float | None = Field(default=None, ge=0, le=100000)
    alcohol_g: float | None = Field(default=None, ge=0, le=5000)
    caffeine_mg: float | None = Field(default=None, ge=0, le=100000)
    data_quality: str | None = Field(default=None, min_length=1, max_length=40)
    favourite: bool | None = None
    notes: str | None = Field(default=None, max_length=1000)


class FoodOutput(FoodBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    archived: bool
    created_at: datetime
    updated_at: datetime


class FoodComponentCreate(BaseModel):
    food_id: str
    quantity: float = Field(gt=0, le=100000)
    unit: str = Field(default="serving", min_length=1, max_length=40)


class CompositeFoodCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    serving_name: str = Field(default="1 serving", min_length=1, max_length=100)
    serving_unit: str = Field(default="serving", min_length=1, max_length=40)
    components: list[FoodComponentCreate] = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=1000)


class FoodPreferenceUpdate(BaseModel):
    favourite: bool | None = None
    default_quantity: float | None = Field(default=None, gt=0, le=100000)


class ImportPreviewRequest(BaseModel):
    tsv: str = Field(min_length=1, max_length=2_000_000)
    mappings: dict[str, str] | None = None


class ImportCommitRequest(BaseModel):
    rows: list[dict[str, object]]
    duplicate_action: str = Field(default="skip", pattern="^(skip|update|new)$")


class ImportPreviewOutput(BaseModel):
    headers: list[str]
    mappings: dict[str, str | None]
    total_rows: int
    valid_rows: int
    warning_rows: int
    invalid_rows: int
    duplicate_rows: int
    rows: list[dict[str, object]]


class DiaryEntryCreate(BaseModel):
    food_id: str
    meal_period: MealPeriod = MealPeriod.SNACK
    consumed_at: datetime
    servings: float = Field(default=1.0, gt=0, le=100)

    @field_validator("consumed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("consumed_at must include a timezone")
        return value


class DiaryEntryOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    food_id: str | None
    meal_period: MealPeriod
    consumed_at: datetime
    servings: float
    food_name: str
    serving_name: str
    calories: float
    protein_g: float | None
    carbohydrates_g: float | None
    fat_g: float | None
    sugar_g: float | None
    saturated_fat_g: float | None
    fibre_g: float | None
    sodium_mg: float | None
    calcium_mg: float | None
    iron_mg: float | None
    potassium_mg: float | None
    cholesterol_mg: float | None
    alcohol_g: float | None
    caffeine_mg: float | None
    source: str
    created_at: datetime
    updated_at: datetime


class DailySummaryOutput(BaseModel):
    profile_id: str
    date: date
    calorie_target: int
    consumed_calories: int
    credited_exercise_calories: int
    remaining_calories: int
    protein_g: float
    carbohydrates_g: float
    fat_g: float
    sugar_g: float
    entry_count: int


class QuickAddResult(BaseModel):
    id: str
    source: str
    result_type: str
    name: str
    subtitle: str | None = None
    calories: float | None = None
    nutrition_complete: bool = False


class NutritionLabelReviewCreate(BaseModel):
    upload_id: str
    name: str = Field(min_length=1, max_length=180)
    brand: str | None = Field(default=None, max_length=120)
    kind: FoodKind = FoodKind.FOOD
    serving_name: str = Field(min_length=1, max_length=100)
    serving_grams: float | None = Field(default=None, gt=0, le=10000)
    energy_kj: float | None = Field(default=None, ge=0, le=100000)
    calories: float = Field(ge=0, le=25000)
    protein_g: float | None = Field(default=None, ge=0, le=5000)
    carbohydrates_g: float | None = Field(default=None, ge=0, le=5000)
    fat_g: float | None = Field(default=None, ge=0, le=5000)
    sugar_g: float | None = Field(default=None, ge=0, le=5000)
    reviewed: bool

    @model_validator(mode="after")
    def require_review(self) -> "NutritionLabelReviewCreate":
        if not self.reviewed:
            raise ValueError("Nutrition label values must be reviewed before saving")
        return self
