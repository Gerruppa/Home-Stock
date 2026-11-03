from datetime import date, timedelta
from pathlib import Path

import flet as ft
import pytest
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.mobile.shell import Shell
from home_stock.persistence.db import init_db
from home_stock.persistence.products import (
    add_product,
    get_product,
    purchase,
    shopping_list_text,
    update_product,
    use_units,
)
from home_stock.persistence.settings import save_buffer_days
from mobile_ui import Screen, absent, find, select, tap, texts

SPOZYWCZE, HIGIENA = 1, 4
SZTUKA, OPAKOWANIE, ROLKA = 1, 2, 3
SHOPPING_TAB = 2
TODAY = date(2026, 11, 2)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


@pytest.fixture
def screen() -> Screen:
    return Screen()


def _open(engine: Engine, screen: Screen) -> ft.Control:
    """The Zakupy tab of a fresh shell, as the user sees it after tapping its destination."""
    shell = Shell(engine, screen.present, screen.update, screen.views, screen.copy, screen.share, today=lambda: TODAY)
    select(shell.navigation_bar, SHOPPING_TAB)
    return shell.body


def _quantity_field(screen: Screen) -> ft.TextField:
    field = find(screen.top, "purchase-quantity")
    assert isinstance(field, ft.TextField)
    return field


def _running_out(engine: Engine) -> int:
    """Cukier without a Minimum Stock: 6 Units Used over 30 days, a fifth of a Unit a day; the 1 left lasts 5 days."""
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(6))
    purchase(engine, cukier, BatchDraft(1), TODAY - timedelta(days=30))
    for days_ago in (20, 10, 1):
        use_units(engine, cukier, 2, TODAY - timedelta(days=days_ago))
    return cukier


def test_an_empty_list_says_so_and_offers_nothing_to_copy_or_share(engine: Engine, screen: Screen) -> None:
    add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE, minimum_stock=1), BatchDraft(2))

    body = _open(engine, screen)

    assert "Nic nie trzeba kupować." in texts(body)
    assert absent(body, "copy-list")
    assert absent(body, "share-list")


def test_lists_products_running_low_by_category(engine: Engine, screen: Screen) -> None:
    papier = add_product(engine, ProductDraft("Papier toaletowy", HIGIENA, ROLKA, minimum_stock=3), BatchDraft(3))
    add_product(engine, ProductDraft("Pieprz", SPOZYWCZE, SZTUKA))
    add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE, minimum_stock=1), BatchDraft(2))

    body = _open(engine, screen)

    assert texts(find(body, f"shopping-category-{HIGIENA}")) == ["Higiena i kosmetyki"]
    line = texts(find(body, f"shopping-{papier}"))
    assert "Papier toaletowy" in line
    assert "3 rol." in line
    assert absent(body, f"shopping-category-{SPOZYWCZE}")
    assert "Nic nie trzeba kupować." not in texts(body)


def test_each_product_shows_the_amount_to_buy(engine: Engine, screen: Screen) -> None:
    papier = add_product(engine, ProductDraft("Papier toaletowy", HIGIENA, ROLKA, minimum_stock=3), BatchDraft(1))

    body = _open(engine, screen)

    assert "kup 3 rol." in texts(find(body, f"shopping-{papier}"))


def test_each_line_says_why_the_product_is_on_the_list(engine: Engine, screen: Screen) -> None:
    papier = add_product(engine, ProductDraft("Papier toaletowy", HIGIENA, ROLKA, minimum_stock=3), BatchDraft(1))
    cukier = _running_out(engine)

    body = _open(engine, screen)

    assert "poniżej minimum" in texts(find(body, f"shopping-{papier}"))
    assert "wystarczy na ok. 5 dni" in texts(find(body, f"shopping-{cukier}"))


def test_kopiuj_liste_copies_the_list_as_text_and_says_so(engine: Engine, screen: Screen) -> None:
    add_product(engine, ProductDraft("Papier toaletowy", HIGIENA, ROLKA, minimum_stock=3), BatchDraft(1))
    _running_out(engine)
    body = _open(engine, screen)

    tap(find(body, "copy-list"))

    assert screen.copied == [shopping_list_text(engine, TODAY)]
    assert screen.copied == ["Spożywcze\nCukier — kup 1 opak.\n\nHigiena i kosmetyki\nPapier toaletowy — kup 3 rol."]
    assert texts(screen.presented[-1]) == ["Skopiowano listę zakupów."]


def test_udostepnij_shares_the_list_as_text(engine: Engine, screen: Screen) -> None:
    add_product(engine, ProductDraft("Papier toaletowy", HIGIENA, ROLKA, minimum_stock=3), BatchDraft(1))
    body = _open(engine, screen)

    tap(find(body, "share-list"))

    assert screen.shared == ["Higiena i kosmetyki\nPapier toaletowy — kup 3 rol."]


def test_kupione_suggests_enough_and_the_product_leaves_the_list(engine: Engine, screen: Screen) -> None:
    chusteczki = add_product(engine, ProductDraft("Chusteczki", HIGIENA, OPAKOWANIE, minimum_stock=2), BatchDraft(1))
    body = _open(engine, screen)

    tap(find(body, f"bought-{chusteczki}"))
    assert _quantity_field(screen).value == "2"
    tap(find(screen.top, "purchase-save"))

    assert "Nic nie trzeba kupować." in texts(body)
    assert get_product(engine, chusteczki).quantity == 3
    assert screen.top is screen.views[0]


def test_a_product_still_running_low_after_the_purchase_stays(engine: Engine, screen: Screen) -> None:
    chusteczki = add_product(engine, ProductDraft("Chusteczki", HIGIENA, OPAKOWANIE, minimum_stock=4), BatchDraft(1))
    body = _open(engine, screen)

    tap(find(body, f"bought-{chusteczki}"))
    _quantity_field(screen).value = "1"
    tap(find(screen.top, "purchase-save"))

    assert "2 opak." in texts(find(body, f"shopping-{chusteczki}"))


def test_a_purchase_from_the_list_can_be_undone_and_the_product_returns(engine: Engine, screen: Screen) -> None:
    chusteczki = add_product(engine, ProductDraft("Chusteczki", HIGIENA, OPAKOWANIE, minimum_stock=2), BatchDraft(1))
    original = get_product(engine, chusteczki)
    body = _open(engine, screen)

    tap(find(body, f"bought-{chusteczki}"))
    tap(find(screen.top, "purchase-save"))
    snackbar = screen.presented[-1]
    assert texts(snackbar) == ["Zakupiono: Chusteczki"]

    tap(snackbar, "on_action")

    assert "1 opak." in texts(find(body, f"shopping-{chusteczki}"))
    assert not snackbar.open
    assert get_product(engine, chusteczki) == original


def test_a_product_running_out_is_on_unpacking(engine: Engine, screen: Screen) -> None:
    cukier = _running_out(engine)
    body = _open(engine, screen)

    tap(find(body, "unpack"))

    assert find(screen.top, f"unpack-row-{cukier}")


def test_with_a_rate_the_list_kupione_and_unpacking_suggest_enough_to_cover_the_buffer(
    engine: Engine, screen: Screen
) -> None:
    cukier = _running_out(engine)
    update_product(engine, cukier, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE, minimum_stock=1))
    # A fifth of a Unit a day over a Buffer of 7 is 2 Units above the Minimum Stock of 1; 1 is there: buy 2
    body = _open(engine, screen)

    assert "kup 2 opak." in texts(find(body, f"shopping-{cukier}"))
    tap(find(body, f"bought-{cukier}"))
    assert _quantity_field(screen).value == "2"
    tap(find(screen.top, "purchase-save"))
    assert "Nic nie trzeba kupować." in texts(body)

    tap(screen.presented[-1], "on_action")

    assert "kup 2 opak." in texts(find(body, f"shopping-{cukier}"))
    tap(find(body, "unpack"))
    unpack_quantity = find(screen.top, f"unpack-quantity-{cukier}")
    assert isinstance(unpack_quantity, ft.TextField)
    assert unpack_quantity.value == "2"


def test_a_product_lasting_beyond_a_smaller_buffer_is_not_listed(engine: Engine, screen: Screen) -> None:
    cukier = _running_out(engine)
    save_buffer_days(engine, 4)

    body = _open(engine, screen)

    assert "Nic nie trzeba kupować." in texts(body)
    assert absent(body, f"shopping-{cukier}")
