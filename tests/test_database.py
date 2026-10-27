from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from home_stock.persistence.catalog import list_categories, list_units
from home_stock.persistence.db import init_db
from home_stock.persistence.models import Base


def test_models_match_migrations(tmp_path: Path) -> None:
    engine = init_db(tmp_path / "db.sqlite3")
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


def test_first_run_seeds_categories_and_units(tmp_path: Path) -> None:
    engine = init_db(tmp_path / "db.sqlite3")

    categories = list_categories(engine)
    assert [(c.name, c.warning_days) for c in categories] == [
        ("Spożywcze", 3),
        ("Napoje", 7),
        ("Chemia i środki czystości", 30),
        ("Higiena i kosmetyki", 30),
        ("Apteczka", 30),
        ("Zwierzęta", 7),
        ("Dom i inne", 30),
    ]
    assert [(u.name, u.short) for u in list_units(engine)] == [
        ("sztuka", "szt."),
        ("opakowanie", "opak."),
        ("rolka", "rol."),
        ("butelka", "but."),
        ("puszka", "pusz."),
        ("tubka", "tub."),
        ("słoik", "sł."),
        ("para", "par."),
    ]


def test_opening_again_keeps_the_data(tmp_path: Path) -> None:
    init_db(tmp_path / "db.sqlite3").dispose()
    assert len(list_categories(init_db(tmp_path / "db.sqlite3"))) == 7
