from datetime import date
from pathlib import Path

import flet as ft
import pytest
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.mobile.shell import Shell
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, add_products, list_products, purchase
from home_stock.sources.starter_catalog import STARTER_CATALOG, available_starter_drafts
from mobile_ui import Screen, absent, find, select, tap, texts, walk

SPOZYWCZE, ZWIERZETA = 1, 6
SZTUKA = 1
PRODUCTS_TAB, SETTINGS_TAB = 1, 4
TODAY = date(2026, 11, 2)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


@pytest.fixture
def screen() -> Screen:
    return Screen()


def _shell(engine: Engine, screen: Screen) -> Shell:
    return Shell(
        engine,
        screen.present,
        screen.update,
        screen.views,
        screen.copy,
        screen.share,
        screen.open_url,
        today=lambda: TODAY,
    )


def _open_from_settings(engine: Engine, screen: Screen) -> ft.Control:
    select(_shell(engine, screen).navigation_bar, SETTINGS_TAB)
    tap(find(screen.top, "starter-open"))
    return find(screen.top, "starter-dialog")


def _ticks(dialog: ft.Control) -> dict[str, ft.Checkbox]:
    """The Products' ticks by name, without the Categories'."""
    return {
        str(tick.label): tick
        for tick in walk(dialog)
        if isinstance(tick, ft.Checkbox) and str(tick.key).startswith("starter-tick-")
    }


def test_saves_the_ticked_products_without_minimum_stock_or_batches(engine: Engine, screen: Screen) -> None:
    dialog = _open_from_settings(engine, screen)
    assert "opakowanie · 1 l · zwykle ważne 7 dni" in texts(dialog)

    # The client changes a Checkbox's value by itself, then calls on_change
    _ticks(dialog)["Mleko"].value = False
    pets = find(dialog, f"starter-category-{ZWIERZETA}")
    pets.value = False  # type: ignore[attr-defined]
    tap(pets, "on_change")
    assert _ticks(dialog)["Żwirek dla kota"].value is False
    tap(find(dialog, "starter-save"))

    assert absent(screen.top, "starter-dialog")
    [bar] = screen.presented
    assert bar.action == "Cofnij"
    assert texts(bar)[0].startswith("Dodano typowe produkty")
    products = list_products(engine)
    names = {product.name for product in products}
    assert "Mleko" not in names
    assert "Żwirek dla kota" not in names
    assert {"Masło", "Papier toaletowy", "Paracetamol"} <= names
    pets_count = sum(1 for product in STARTER_CATALOG if product.category == "Zwierzęta")
    assert len(products) == len(STARTER_CATALOG) - 1 - pets_count
    assert all(product.minimum_stock is None and product.batches == () for product in products)
    [maslo] = [product for product in products if product.name == "Masło"]
    assert maslo.usual_shelf_life_days == 30


def test_opens_from_the_empty_produkty_tab_and_cofnij_removes_what_it_added(engine: Engine, screen: Screen) -> None:
    select(_shell(engine, screen).navigation_bar, PRODUCTS_TAB)
    tap(find(screen.top, "starter-open-empty"))
    tap(find(screen.top, "starter-save"))
    assert len(list_products(engine)) == len(STARTER_CATALOG)
    assert absent(screen.top, "starter-open-empty")

    [bar] = screen.presented
    tap(bar, "on_action")

    assert list_products(engine) == []
    assert find(screen.top, "starter-open-empty")


def test_cofnij_refuses_once_a_product_has_a_purchase(engine: Engine, screen: Screen) -> None:
    dialog = _open_from_settings(engine, screen)
    tap(find(dialog, "starter-save"))
    [mleko] = [product for product in list_products(engine) if product.name == "Mleko"]
    purchase(engine, mleko.id, BatchDraft(1), TODAY)

    [bar] = screen.presented
    tap(bar, "on_action")

    said = screen.presented[-1]
    assert texts(said)[0].startswith("Nie można cofnąć")
    assert said.action is None
    assert len(list_products(engine)) == len(STARTER_CATALOG)


def test_cancel_adds_nothing(engine: Engine, screen: Screen) -> None:
    dialog = _open_from_settings(engine, screen)

    tap(find(dialog, "starter-cancel"))

    assert absent(screen.top, "starter-dialog")
    assert list_products(engine) == []


def test_leaves_out_a_name_already_taken(engine: Engine, screen: Screen) -> None:
    add_product(engine, ProductDraft("mleko", SPOZYWCZE, SZTUKA))

    ticks = _ticks(_open_from_settings(engine, screen))

    assert "Masło" in ticks
    assert "Mleko" not in ticks


def test_says_so_when_every_starter_product_is_taken(engine: Engine, screen: Screen) -> None:
    add_products(engine, available_starter_drafts(engine))

    dialog = _open_from_settings(engine, screen)

    assert "Masz już wszystkie typowe produkty." in texts(dialog)
    assert find(dialog, "starter-save").visible is False
