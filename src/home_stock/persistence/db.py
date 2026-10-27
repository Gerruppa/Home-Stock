"""Opening the SQLite database and bringing its schema up to date."""

from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def open_engine(path: Path) -> Engine:
    """Engine for the SQLite file at ``path``, creating its folder if needed; foreign keys are enforced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}")

    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(connection: Any, _record: Any) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def init_db(path: Path) -> Engine:
    """Create the database file if needed and apply all pending migrations."""
    engine = open_engine(path)
    migrate(engine)
    return engine


def migrate(engine: Engine) -> None:
    """Apply all pending migrations to the database of ``engine``."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
