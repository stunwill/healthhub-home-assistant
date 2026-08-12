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
    tables = inspect(engine).get_table_names()
    assert "profiles" in tables
    assert "foods" in tables
    assert "diary_entries" in tables
