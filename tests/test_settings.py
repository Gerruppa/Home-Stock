from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

from home_stock.domain.stock import ProductDraft
from home_stock.persistence.db import MIGRATIONS_DIR, init_db, open_engine
from home_stock.persistence.products import add_product
from home_stock.persistence.settings import LAST_ANNOUNCED_VERSION, load_setting, save_setting


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


def test_a_setting_never_saved_is_none(engine: Engine) -> None:
    assert load_setting(engine, LAST_ANNOUNCED_VERSION) is None


def test_saving_again_replaces_the_value(engine: Engine) -> None:
    save_setting(engine, LAST_ANNOUNCED_VERSION, "0.1.0")
    save_setting(engine, LAST_ANNOUNCED_VERSION, "0.2.0")

    assert load_setting(engine, LAST_ANNOUNCED_VERSION) == "0.2.0"


def test_a_setting_outlives_reopening_the_database(tmp_path: Path) -> None:
    save_setting(init_db(tmp_path / "db.sqlite3"), LAST_ANNOUNCED_VERSION, "0.1.0")

    assert load_setting(init_db(tmp_path / "db.sqlite3"), LAST_ANNOUNCED_VERSION) == "0.1.0"


def _migrate_to(engine: Engine, revision: str) -> None:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


def test_a_database_in_use_before_settings_existed_counts_as_having_announced_0_1_0(tmp_path: Path) -> None:
    engine = open_engine(tmp_path / "db.sqlite3")
    _migrate_to(engine, "0001")
    add_product(engine, ProductDraft("Mleko", category_id=1, unit_id=1))

    assert load_setting(init_db(tmp_path / "db.sqlite3"), LAST_ANNOUNCED_VERSION) == "0.1.0"
