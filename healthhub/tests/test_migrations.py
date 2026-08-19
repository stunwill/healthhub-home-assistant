from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_migrations_create_current_schema(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    database = tmp_path / "migration.db"
    monkeypatch.delenv("HEALTHHUB_DATABASE_URL", raising=False)

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database}")
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "profiles" in tables
    assert "foods" in tables
    assert "diary_entries" in tables
    assert "exercise_entries" in tables
    assert "weight_entries" in tables
    assert "water_entries" in tables
    assert "planned_entries" in tables
    assert "recurrence_rules" in tables

    profile_columns = {column["name"] for column in inspector.get_columns("profiles")}
    food_columns = {column["name"] for column in inspector.get_columns("foods")}
    diary_columns = {column["name"] for column in inspector.get_columns("diary_entries")}
    planned_columns = {column["name"] for column in inspector.get_columns("planned_entries")}
    assert "nutrition_display_fields" in profile_columns
    assert "sugar_g" in food_columns
    assert "sugar_g" in diary_columns
    assert "sugar_g" in planned_columns
    assert "category" in food_columns
    assert "data_quality" in food_columns
    assert "food_components" in tables
    assert "food_preferences" in tables
    assert "import_batches" in tables
