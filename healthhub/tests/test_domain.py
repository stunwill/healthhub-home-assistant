from app.domain import calorie_budget
from app.models import ExerciseCreditMode


def test_no_exercise_credit() -> None:
    credited, remaining = calorie_budget(
        daily_calorie_target=1700,
        consumed_food_calories=1250,
        completed_exercise_calories=300,
        exercise_credit_mode=ExerciseCreditMode.NONE,
        exercise_credit_percentage=0,
    )
    assert credited == 0
    assert remaining == 450


def test_full_exercise_credit() -> None:
    credited, remaining = calorie_budget(
        daily_calorie_target=1700,
        consumed_food_calories=1250,
        completed_exercise_calories=300,
        exercise_credit_mode=ExerciseCreditMode.FULL,
        exercise_credit_percentage=100,
    )
    assert credited == 300
    assert remaining == 750


def test_percentage_exercise_credit() -> None:
    credited, remaining = calorie_budget(
        daily_calorie_target=1700,
        consumed_food_calories=1250,
        completed_exercise_calories=300,
        exercise_credit_mode=ExerciseCreditMode.PERCENTAGE,
        exercise_credit_percentage=50,
    )
    assert credited == 150
    assert remaining == 600
