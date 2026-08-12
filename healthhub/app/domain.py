from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .models import ExerciseCreditMode


def round_kcal(value: float | Decimal) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calorie_budget(
    *,
    daily_calorie_target: int,
    consumed_food_calories: float,
    completed_exercise_calories: float,
    exercise_credit_mode: ExerciseCreditMode,
    exercise_credit_percentage: int,
) -> tuple[int, int]:
    if exercise_credit_mode == ExerciseCreditMode.NONE:
        rate = Decimal("0")
    elif exercise_credit_mode == ExerciseCreditMode.FULL:
        rate = Decimal("1")
    else:
        rate = Decimal(exercise_credit_percentage) / Decimal("100")

    credited = Decimal(str(completed_exercise_calories)) * rate
    remaining = Decimal(daily_calorie_target) - Decimal(str(consumed_food_calories)) + credited
    return round_kcal(credited), round_kcal(remaining)
