from datetime import date, timedelta
from pathlib import Path

import flet as ft
import pytest
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.mobile.shell import Shell
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, purchase, use_units
from mobile_ui import Screen, absent, find, select, tap, texts

SPOZYWCZE, CHEMIA = 1, 3
SZTUKA, OPAKOWANIE = 1, 2
PRODUCTS_TAB = 1
TODAY = date(2026, 11, 2)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


@pytest.fixture
def screen() -> Screen:
    return Screen()


def _open(engine: Engine, screen: Screen) -> ft.Control:
    """The Produkty tab of a fresh shell, as the user sees it after tapping its destination."""
    shell = Shell(engine, screen.present, screen.update, screen.views, today=lambda: TODAY)
    select(shell.navigation_bar, PRODUCTS_TAB)
    return shell.body


def _quantity(body: ft.Control, product_id: int) -> str:
    [text] = texts(find(body, f"quantity-{product_id}"))
    return text


def test_no_products_says_so(engine: Engine, screen: Screen) -> None:
    body = _open(engine, screen)

    assert "Nie masz jeszcze produktów." in texts(body)


def test_products_show_under_their_category_with_their_quantity(engine: Engine, screen: Screen) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(3))

    body = _open(engine, screen)

    assert "Cukier" in texts(find(body, f"product-{cukier}"))
    assert _quantity(body, cukier) == "3 opak."
    assert texts(find(body, f"category-{SPOZYWCZE}")) == ["Spożywcze"]
    assert absent(body, "no-products")


def test_categories_keep_the_spec_order(engine: Engine, screen: Screen) -> None:
    add_product(engine, ProductDraft("Płyn do naczyń", CHEMIA, SZTUKA))
    add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE))

    body = _open(engine, screen)

    keys = [control.key for control in find(body, "products").controls]  # type: ignore[attr-defined]
    assert keys.index(f"category-{SPOZYWCZE}") < keys.index(f"category-{CHEMIA}")


def test_search_filters_ignoring_case_and_hides_empty_categories(engine: Engine, screen: Screen) -> None:
    add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(2))
    add_product(engine, ProductDraft("Płyn do naczyń", CHEMIA, SZTUKA))
    body = _open(engine, screen)
    search = find(body, "search")
    updates = screen.updates

    search.value = "CUK"  # type: ignore[attr-defined]
    tap(search, "on_change")

    assert "Cukier" in texts(body)
    assert "Płyn do naczyń" not in texts(body)
    assert absent(body, f"category-{CHEMIA}")
    assert screen.updates == updates + 1


def test_use_one_and_undo(engine: Engine, screen: Screen) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(2))
    body = _open(engine, screen)

    tap(find(body, f"use-{cukier}"))

    assert _quantity(body, cukier) == "1 opak."
    [snackbar] = screen.presented
    assert texts(snackbar) == ["Zużyto 1 × Cukier"]

    tap(snackbar, "on_action")

    assert _quantity(body, cukier) == "2 opak."
    assert not snackbar.open


def test_use_is_disabled_at_zero(engine: Engine, screen: Screen) -> None:
    pieprz = add_product(engine, ProductDraft("Pieprz", SPOZYWCZE, SZTUKA))

    body = _open(engine, screen)

    assert find(body, f"use-{pieprz}").disabled


def test_undo_takes_back_only_the_last_use(engine: Engine, screen: Screen) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(3))
    body = _open(engine, screen)

    tap(find(body, f"use-{cukier}"))
    tap(find(body, f"use-{cukier}"))
    tap(screen.presented[-1], "on_action")

    assert _quantity(body, cukier) == "2 opak."


def test_a_running_low_quantity_shows_in_red(engine: Engine, screen: Screen) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA, minimum_stock=2), BatchDraft(1))
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE, minimum_stock=1), BatchDraft(3))

    body = _open(engine, screen)

    assert find(body, f"quantity-{mleko}").color == ft.Colors.ERROR  # type: ignore[attr-defined]
    assert find(body, f"quantity-{cukier}").color is None  # type: ignore[attr-defined]


def test_a_product_with_a_consumption_rate_shows_its_days_left(engine: Engine, screen: Screen) -> None:
    # 6 Units Used over 30 days, a fifth of a Unit a day: the 11 left last 55 days
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(16))
    purchase(engine, cukier, BatchDraft(1), TODAY - timedelta(days=30))
    for days_ago in (20, 10, 1):
        use_units(engine, cukier, 2, TODAY - timedelta(days=days_ago))
    # Only 2 Uses: no forecast
    sol = add_product(engine, ProductDraft("Sól", SPOZYWCZE, OPAKOWANIE), BatchDraft(5))
    purchase(engine, sol, BatchDraft(1), TODAY - timedelta(days=30))
    for days_ago in (20, 10):
        use_units(engine, sol, 1, TODAY - timedelta(days=days_ago))

    body = _open(engine, screen)

    assert texts(find(body, f"days-left-{cukier}")) == ["wystarczy na ok. 55 dni"]
    assert absent(body, f"days-left-{sol}")
