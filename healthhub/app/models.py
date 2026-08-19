from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExerciseCreditMode(StrEnum):
    NONE = "none"
    FULL = "full"
    PERCENTAGE = "percentage"


class NutritionDisplayMode(StrEnum):
    """Legacy preset retained for migration and API compatibility."""

    SIMPLE = "simple"
    BALANCED = "balanced"
    DETAILED = "detailed"


class NutritionField(StrEnum):
    CALORIES = "calories"
    PROTEIN = "protein"
    CARBOHYDRATES = "carbohydrates"
    FAT = "fat"
    SUGAR = "sugar"


class MeasurementUnits(StrEnum):
    METRIC = "metric"


class FoodKind(StrEnum):
    FOOD = "food"
    DRINK = "drink"
    COMPOSITE = "composite"


class MealPeriod(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    DRINK = "drink"


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
    _nutrition_display_fields: Mapped[str] = mapped_column(
        "nutrition_display_fields", String(100), default=NutritionField.CALORIES.value
    )
    timezone: Mapped[str] = mapped_column(String(100), default="Australia/Melbourne")
    measurement_units: Mapped[str] = mapped_column(String(20), default=MeasurementUnits.METRIC.value)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    diary_entries: Mapped[list[DiaryEntry]] = relationship(back_populates="profile", cascade="all, delete-orphan")

    @property
    def nutrition_display_fields(self) -> list[str]:
        return [value for value in self._nutrition_display_fields.split(",") if value]

    @nutrition_display_fields.setter
    def nutrition_display_fields(self, values: list[str] | list[NutritionField]) -> None:
        normalised = [value.value if isinstance(value, NutritionField) else value for value in values]
        self._nutrition_display_fields = ",".join(dict.fromkeys(normalised))


class Food(Base):
    __tablename__ = "foods"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(180), index=True)
    brand: Mapped[str | None] = mapped_column(String(120), index=True)
    category: Mapped[str | None] = mapped_column(String(80), index=True)
    kind: Mapped[str] = mapped_column(String(20), default=FoodKind.FOOD.value, index=True)
    serving_name: Mapped[str] = mapped_column(String(100), default="1 serve")
    serving_unit: Mapped[str] = mapped_column(String(40), default="serving")
    serving_grams: Mapped[float | None] = mapped_column(Float)
    energy_kj: Mapped[float | None] = mapped_column(Float)
    calories: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float | None] = mapped_column(Float)
    carbohydrates_g: Mapped[float | None] = mapped_column(Float)
    fat_g: Mapped[float | None] = mapped_column(Float)
    saturated_fat_g: Mapped[float | None] = mapped_column(Float)
    sugar_g: Mapped[float | None] = mapped_column(Float)
    fibre_g: Mapped[float | None] = mapped_column(Float)
    sodium_mg: Mapped[float | None] = mapped_column(Float)
    calcium_mg: Mapped[float | None] = mapped_column(Float)
    iron_mg: Mapped[float | None] = mapped_column(Float)
    potassium_mg: Mapped[float | None] = mapped_column(Float)
    cholesterol_mg: Mapped[float | None] = mapped_column(Float)
    alcohol_g: Mapped[float | None] = mapped_column(Float)
    caffeine_mg: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40), default="manual", index=True)
    data_quality: Mapped[str] = mapped_column(String(40), default="user_entered", index=True)
    favourite: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    diary_entries: Mapped[list[DiaryEntry]] = relationship(back_populates="food")
    components: Mapped[list[FoodComponent]] = relationship(back_populates="composite", cascade="all, delete-orphan", foreign_keys="FoodComponent.composite_food_id")

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
    sugar_g: Mapped[float | None] = mapped_column(Float)
    saturated_fat_g: Mapped[float | None] = mapped_column(Float)
    fibre_g: Mapped[float | None] = mapped_column(Float)
    sodium_mg: Mapped[float | None] = mapped_column(Float)
    calcium_mg: Mapped[float | None] = mapped_column(Float)
    iron_mg: Mapped[float | None] = mapped_column(Float)
    potassium_mg: Mapped[float | None] = mapped_column(Float)
    cholesterol_mg: Mapped[float | None] = mapped_column(Float)
    alcohol_g: Mapped[float | None] = mapped_column(Float)
    caffeine_mg: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40), default="healthhub")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    profile: Mapped[Profile] = relationship(back_populates="diary_entries")
    food: Mapped[Food | None] = relationship(back_populates="diary_entries")

    __table_args__ = (Index("ix_diary_profile_consumed", "profile_id", "consumed_at"),)


class FoodComponent(Base):
    __tablename__ = "food_components"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    composite_food_id: Mapped[str] = mapped_column(ForeignKey("foods.id", ondelete="CASCADE"), index=True)
    component_food_id: Mapped[str] = mapped_column(ForeignKey("foods.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(40), default="serving")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    composite: Mapped[Food] = relationship(back_populates="components", foreign_keys=[composite_food_id])
    component: Mapped[Food] = relationship(foreign_keys=[component_food_id])


class FoodPreference(Base):
    __tablename__ = "food_preferences"

    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    food_id: Mapped[str] = mapped_column(ForeignKey("foods.id", ondelete="CASCADE"), primary_key=True)
    favourite: Mapped[bool] = mapped_column(Boolean, default=False)
    default_quantity: Mapped[float | None] = mapped_column(Float)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    __table_args__ = (UniqueConstraint("profile_id", "food_id", name="uq_food_preferences_profile_food"),)


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source: Mapped[str] = mapped_column(String(40), default="spreadsheet")
    status: Mapped[str] = mapped_column(String(20), default="completed")
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ImportItem(Base):
    __tablename__ = "import_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"), index=True)
    food_id: Mapped[str | None] = mapped_column(ForeignKey("foods.id", ondelete="SET NULL"), nullable=True)
    row_number: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(20))
    message: Mapped[str | None] = mapped_column(Text)
