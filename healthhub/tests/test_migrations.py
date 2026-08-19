from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _config(database: Path) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    return config


def test_migrations_create_current_schema(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    database = tmp_path / "migration.db"
    monkeypatch.delenv("HEALTHHUB_DATABASE_URL", raising=False)
    config = _config(database)
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database}")
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    for table in ("profiles", "foods", "diary_entries", "exercise_entries", "weight_entries", "water_entries", "planned_entries", "recurrence_rules", "food_components", "food_preferences", "import_batches", "food_identifiers", "foodhub_recipe_links", "foodhub_ingredient_mappings"):
        assert table in tables

    profile_columns = {column["name"] for column in inspector.get_columns("profiles")}
    food_columns = {column["name"] for column in inspector.get_columns("foods")}
    diary_columns = {column["name"] for column in inspector.get_columns("diary_entries")}
    planned_columns = {column["name"] for column in inspector.get_columns("planned_entries")}
    assert "nutrition_display_fields" in profile_columns
    assert "sugar_g" in food_columns
    assert "sugar_g" in diary_columns
    assert "sugar_g" in planned_columns
    for column in ("category", "data_quality", "serving_quantity", "nutrition_basis", "canonical_quantity", "canonical_unit", "source_provider", "source_identifier", "verification_status", "ocr_confidence", "image_url"):
        assert column in food_columns


def test_upgrade_from_v06_preserves_food_and_diary_data(tmp_path: Path) -> None:
    database = tmp_path / "v06-upgrade.db"
    config = _config(database)
    command.upgrade(config, "0006_food_library_imports")
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        profile_id = "migration-profile"
        connection.execute(text("INSERT INTO profiles (id, display_name, daily_calorie_target, weekly_exercise_minutes_target, hydration_target_ml, exercise_credit_mode, exercise_credit_percentage, nutrition_display_mode, nutrition_display_fields, timezone, measurement_units, archived, created_at, updated_at) VALUES (:id, 'Migration Test', 2000, 150, NULL, 'none', 0, 'simple', 'calories', 'Australia/Melbourne', 'metric', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {"id": profile_id})
        connection.execute(text("INSERT INTO foods (id, name, kind, serving_name, serving_unit, calories, source, data_quality, favourite, archived, created_at, updated_at) VALUES ('migration-food', 'Existing food', 'food', '80 g', 'g', 298.4, 'manual', 'user_entered', 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO diary_entries (id, profile_id, food_id, meal_period, consumed_at, servings, food_name, serving_name, calories, source, created_at, updated_at) VALUES ('migration-entry', :profile_id, 'migration-food', 'snack', CURRENT_TIMESTAMP, 1, 'Existing food', '80 g', 298.4, 'healthhub', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {"profile_id": profile_id})
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT name FROM foods WHERE id='migration-food'")).scalar_one() == "Existing food"
        assert connection.execute(text("SELECT calories FROM diary_entries WHERE id='migration-entry'")).scalar_one() == 298.4
        assert connection.execute(text("SELECT nutrition_basis FROM foods WHERE id='migration-food'")).scalar_one() == "per_serving"
