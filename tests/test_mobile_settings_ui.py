from datetime import date
from pathlib import Path

import flet as ft
import pytest
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.mobile.shell import Shell
from home_stock.persistence.catalog import list_categories, list_units
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, archive_product, get_product, list_products
from home_stock.persistence.settings import load_buffer_days
from mobile_ui import Screen, absent, find, select, tap, texts

SPOZYWCZE, NAPOJE = 1, 2
SZTUKA, OPAKOWANIE = 1, 2
START_TAB, PRODUCTS_TAB, SETTINGS_TAB = 0, 1, 4
TODAY = date(2026, 10, 27)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


@pytest.fixture
def screen() -> Screen:
    return Screen()


def _open(engine: Engine, screen: Screen) -> Shell:
    """A fresh shell showing Ustawienia, as the user sees it after tapping its destination."""
    shell = Shell(
        engine,
        screen.present,
        screen.update,
        screen.views,
        screen.copy,
        screen.share,
        screen.open_url,
        today=lambda: TODAY,
    )
    select(shell.navigation_bar, SETTINGS_TAB)
    return shell


def _type(root: ft.Control, key: str, value: str) -> None:
    field = find(root, key)
    assert isinstance(field, ft.TextField)
    field.value = value


def _value(root: ft.Control, key: str) -> str | None:
    field = find(root, key)
    assert isinstance(field, ft.TextField)
    return field.value


def test_an_empty_archive_says_so(engine: Engine, screen: Screen) -> None:
    shell = _open(engine, screen)

    assert "Archiwum jest puste." in texts(find(shell.body, "archive"))


def test_restore_brings_the_product_back_with_its_batches_and_settings(engine: Engine, screen: Screen) -> None:
    mleko = add_product(
        engine, ProductDraft("Mleko", SPOZYWCZE, OPAKOWANIE, minimum_stock=3), BatchDraft(2, date(2026, 11, 12))
    )
    original = get_product(engine, mleko)
    archive_product(engine, mleko)
    shell = _open(engine, screen)
    assert "Mleko" in texts(find(shell.body, "archive"))

    tap(find(shell.body, f"restore-{mleko}"))

    assert "Archiwum jest puste." in texts(find(shell.body, "archive"))
    assert "Archiwum jest puste." in screen.shown
    select(shell.navigation_bar, PRODUCTS_TAB)
    find(shell.body, f"product-{mleko}")
    assert list_products(engine) == [original]


def test_a_longer_warning_window_moves_a_batch_into_expiring_soon(engine: Engine, screen: Screen) -> None:
    add_product(engine, ProductDraft("Szynka", SPOZYWCZE, SZTUKA), BatchDraft(1, date(2026, 10, 31)))
    shell = _open(engine, screen)

    _type(shell.body, f"category-days-{SPOZYWCZE}", "5")
    tap(find(shell.body, f"category-save-{SPOZYWCZE}"))

    select(shell.navigation_bar, START_TAB)
    expiring = texts(find(shell.body, "expiring"))
    assert "Szynka" in expiring
    assert "1 szt., termin 31.10.2026" in expiring


def test_a_new_category_starts_with_seven_days_and_an_unused_one_can_be_deleted(engine: Engine, screen: Screen) -> None:
    shell = _open(engine, screen)
    assert _value(shell.body, "category-new-days") == "7"

    _type(shell.body, "category-new-name", "Ogród")
    _type(shell.body, "category-new-days", "14")
    tap(find(shell.body, "category-add"))

    [ogrod] = [c for c in list_categories(engine) if c.name == "Ogród"]
    assert ogrod.warning_days == 14
    assert _value(shell.body, f"category-name-{ogrod.id}") == "Ogród"
    # Drawn anew, so the next Category starts from a blank name and seven days again
    assert (_value(shell.body, "category-new-name"), _value(shell.body, "category-new-days")) == ("", "7")

    tap(find(shell.body, f"category-delete-{ogrod.id}"))

    assert absent(shell.body, f"category-row-{ogrod.id}")


def test_a_category_a_product_uses_is_not_deleted(engine: Engine, screen: Screen) -> None:
    add_product(engine, ProductDraft("Mleko", SPOZYWCZE, OPAKOWANIE))
    shell = _open(engine, screen)

    tap(find(shell.body, f"category-delete-{SPOZYWCZE}"))

    assert texts(find(shell.body, "category-error")) == ["Nie można usunąć kategorii, do której należą produkty."]
    assert "Nie można usunąć kategorii, do której należą produkty." in screen.shown
    assert _value(shell.body, f"category-name-{SPOZYWCZE}") == "Spożywcze"
    assert list_categories(engine)[0].name == "Spożywcze"


def test_a_refusal_goes_away_after_the_next_change(engine: Engine, screen: Screen) -> None:
    add_product(engine, ProductDraft("Mleko", SPOZYWCZE, OPAKOWANIE))
    shell = _open(engine, screen)
    tap(find(shell.body, f"category-delete-{SPOZYWCZE}"))

    _type(shell.body, f"category-days-{NAPOJE}", "10")
    tap(find(shell.body, f"category-save-{NAPOJE}"))

    assert texts(find(shell.body, "category-error")) == []


def test_renaming_a_category_to_a_taken_name_in_another_case_is_refused(engine: Engine, screen: Screen) -> None:
    shell = _open(engine, screen)

    _type(shell.body, f"category-name-{NAPOJE}", "SPOŻYWCZE")
    tap(find(shell.body, f"category-save-{NAPOJE}"))

    assert texts(find(shell.body, "category-error")) == ["Kategoria o tej nazwie już istnieje."]
    assert list_categories(engine)[1].name == "Napoje"


def test_a_new_unit_is_offered_in_the_product_form(engine: Engine, screen: Screen) -> None:
    shell = _open(engine, screen)

    _type(shell.body, "unit-new-name", "worek")
    _type(shell.body, "unit-new-short", "wor.")
    tap(find(shell.body, "unit-add"))

    worek = list_units(engine)[-1]
    assert (worek.name, worek.short) == ("worek", "wor.")
    assert _value(shell.body, f"unit-name-{worek.id}") == "worek"
    select(shell.navigation_bar, PRODUCTS_TAB)
    tap(find(shell.body, "add-product"))
    unit = find(screen.top, "unit")
    assert isinstance(unit, ft.Dropdown)
    assert "worek" in [option.text for option in unit.options]


def test_a_unit_without_a_short_form_is_refused(engine: Engine, screen: Screen) -> None:
    shell = _open(engine, screen)

    _type(shell.body, f"unit-short-{OPAKOWANIE}", " ")
    tap(find(shell.body, f"unit-save-{OPAKOWANIE}"))

    assert texts(find(shell.body, "unit-error")) == ["Podaj skrót."]
    assert list_units(engine)[1].short == "opak."


def test_the_buffer_starts_at_seven_and_saves_a_new_value(engine: Engine, screen: Screen) -> None:
    shell = _open(engine, screen)
    assert _value(shell.body, "buffer-days") == "7"

    _type(shell.body, "buffer-days", "14")
    tap(find(shell.body, "buffer-save"))

    assert texts(find(shell.body, "buffer-error")) == []
    assert load_buffer_days(engine) == 14
    assert _value(shell.body, "buffer-days") == "14"


def test_an_invalid_buffer_is_refused_with_a_polish_message(engine: Engine, screen: Screen) -> None:
    shell = _open(engine, screen)

    _type(shell.body, "buffer-days", "0")
    tap(find(shell.body, "buffer-save"))

    assert texts(find(shell.body, "buffer-error")) == ["Podaj liczbę dni większą od zera, np. 7."]
    assert load_buffer_days(engine) == 7
