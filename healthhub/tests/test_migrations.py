from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_initial_migration_creates_profiles(tmp_path: Path) -> None:
    database = tmp_path / "migration.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database}")
    assert "profiles" in inspect(engine).get_table_names()
