from pathlib import Path

import pytest
from sqlalchemy import Engine

from home_stock.domain.stock import Category, ProductDraft, Unit
from home_stock.persistence.catalog import (
    StockError,
    add_category,
    add_unit,
    delete_category,
    delete_unit,
    list_categories,
    list_units,
    update_category,
    update_unit,
)
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, archive_product

SPOZYWCZE, NAPOJE = 1, 2
SZTUKA, OPAKOWANIE = 1, 2


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


def test_add_rename_and_delete_an_unused_category(engine: Engine) -> None:
    ogrod = add_category(engine, "  Ogród ", 14)
    assert list_categories(engine)[-1] == Category(ogrod, "Ogród", 14)

    update_category(engine, ogrod, "Ogród i balkon", 20)
    assert list_categories(engine)[-1] == Category(ogrod, "Ogród i balkon", 20)

    delete_category(engine, ogrod)
    assert ogrod not in [category.id for category in list_categories(engine)]


def test_a_category_name_taken_ignoring_case_is_refused(engine: Engine) -> None:
    with pytest.raises(StockError, match="Kategoria o tej nazwie już istnieje."):
        add_category(engine, " spożywcze ", 3)
    with pytest.raises(StockError, match="Kategoria o tej nazwie już istnieje."):
        update_category(engine, NAPOJE, "SPOŻYWCZE", 7)
    assert list_categories(engine)[NAPOJE - 1] == Category(NAPOJE, "Napoje", 7)


def test_a_category_keeps_its_own_name_in_another_case(engine: Engine) -> None:
    update_category(engine, NAPOJE, "NAPOJE", 10)
    assert list_categories(engine)[NAPOJE - 1] == Category(NAPOJE, "NAPOJE", 10)


@pytest.mark.parametrize(
    ("name", "days", "message"), [("  ", 3, "Podaj nazwę."), ("Ogród", -1, "Liczba dni nie może być ujemna.")]
)
def test_a_category_needs_a_name_and_days_not_below_zero(engine: Engine, name: str, days: int, message: str) -> None:
    with pytest.raises(StockError, match=message):
        add_category(engine, name, days)
    with pytest.raises(StockError, match=message):
        update_category(engine, NAPOJE, name, days)


def test_a_category_an_archived_product_uses_cannot_be_deleted(engine: Engine) -> None:
    archive_product(engine, add_product(engine, ProductDraft("Mleko", SPOZYWCZE, OPAKOWANIE)))
    with pytest.raises(StockError, match="Nie można usunąć kategorii, do której należą produkty."):
        delete_category(engine, SPOZYWCZE)
    assert list_categories(engine)[0] == Category(SPOZYWCZE, "Spożywcze", 3)


def test_add_rename_and_delete_an_unused_unit(engine: Engine) -> None:
    worek = add_unit(engine, " worek ", " wor. ")
    assert list_units(engine)[-1] == Unit(worek, "worek", "wor.")

    update_unit(engine, worek, "worek foliowy", "wor. fol.")
    assert list_units(engine)[-1] == Unit(worek, "worek foliowy", "wor. fol.")

    delete_unit(engine, worek)
    assert worek not in [unit.id for unit in list_units(engine)]


def test_a_unit_name_taken_ignoring_case_is_refused(engine: Engine) -> None:
    with pytest.raises(StockError, match="Jednostka o tej nazwie już istnieje."):
        add_unit(engine, "Sztuka", "szt.")
    with pytest.raises(StockError, match="Jednostka o tej nazwie już istnieje."):
        update_unit(engine, OPAKOWANIE, "SZTUKA", "szt.")
    update_unit(engine, OPAKOWANIE, "Opakowanie", "opak.")
    assert list_units(engine)[OPAKOWANIE - 1] == Unit(OPAKOWANIE, "Opakowanie", "opak.")


@pytest.mark.parametrize(("name", "short", "message"), [("  ", "wor.", "Podaj nazwę."), ("worek", " ", "Podaj skrót.")])
def test_a_unit_needs_a_name_and_a_short_form(engine: Engine, name: str, short: str, message: str) -> None:
    with pytest.raises(StockError, match=message):
        add_unit(engine, name, short)
    with pytest.raises(StockError, match=message):
        update_unit(engine, OPAKOWANIE, name, short)


def test_a_unit_an_archived_product_uses_cannot_be_deleted(engine: Engine) -> None:
    archive_product(engine, add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA)))
    with pytest.raises(StockError, match="Nie można usunąć jednostki, której używają produkty."):
        delete_unit(engine, SZTUKA)
    assert list_units(engine)[0] == Unit(SZTUKA, "sztuka", "szt.")
