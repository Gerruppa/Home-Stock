from datetime import date, timedelta
from pathlib import Path

import flet as ft
import pytest
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.mobile.product_card import open_product_card
from home_stock.mobile.purchase_dialog import open_purchase_dialog
from home_stock.mobile.shell import Shell
from home_stock.persistence.db import init_db
from home_stock.persistence.products import (
    add_product,
    discard_batch,
    get_product,
    list_products,
    purchase,
    update_product,
    use_units,
)
from mobile_ui import Screen, absent, find, select, tap, texts

SPOZYWCZE = 1
SZTUKA, OPAKOWANIE = 1, 2
PRODUCTS_TAB = 1
TODAY = date(2026, 10, 27)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


@pytest.fixture
def mleko(engine: Engine) -> int:
    """Mleko with Batches 2 @ 30.10.2026 and 3 @ 12.11.2026."""
    product_id = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA), BatchDraft(2, date(2026, 10, 30)))
    purchase(engine, product_id, BatchDraft(3, date(2026, 11, 12)), TODAY)
    return product_id


@pytest.fixture
def screen() -> Screen:
    return Screen()


@pytest.fixture
def shell(engine: Engine, screen: Screen, mleko: int) -> Shell:
    """Produkty, shown once Mleko exists."""
    shell = Shell(engine, screen.present, screen.update, screen.views, today=lambda: TODAY)
    select(shell.navigation_bar, PRODUCTS_TAB)
    return shell


def _open(screen: Screen, product_id: int) -> None:
    """Tap the Product in Produkty."""
    tap(find(screen.top, f"product-{product_id}"))


def _card(screen: Screen) -> ft.Control:
    return find(screen.top, "product-card")


def _value(root: ft.Control, key: str) -> str:
    field = find(root, key)
    assert isinstance(field, ft.TextField)
    return field.value or ""


def _type(root: ft.Control, key: str, value: str) -> None:
    field = find(root, key)
    assert isinstance(field, ft.TextField)
    field.value = value


def _expiries(screen: Screen, engine: Engine, product_id: int) -> list[str]:
    """The Expiry Date field of every Batch row on the card, oldest Batch first."""
    return [_value(_card(screen), f"batch-expiry-{b.id}") for b in get_product(engine, product_id).batches]


def _batch(engine: Engine, product_id: int, expiry: date | None) -> int:
    return next(b.id for b in get_product(engine, product_id).batches if b.expiry == expiry)


def _snackbar(screen: Screen) -> ft.SnackBar:
    """The undo snackbar, open."""
    bar = screen.presented[-1]
    assert bar.open
    return bar


def test_tapping_a_product_opens_its_card_over_the_whole_screen(
    shell: Shell, engine: Engine, screen: Screen, mleko: int
) -> None:
    _open(screen, mleko)

    shown = texts(_card(screen))
    for text in ("Mleko", "Kategoria: Spożywcze", "Jednostka: sztuka", "Stan minimalny: brak", "Razem: 5 szt."):
        assert text in shown
    assert _expiries(screen, engine, mleko) == ["30.10.2026", "12.11.2026"]
    assert absent(screen.top, "products")
    assert screen.top.navigation_bar is None


def test_closing_the_card_goes_back_to_produkty(shell: Shell, screen: Screen, mleko: int) -> None:
    _open(screen, mleko)

    tap(find(screen.top, "card-close"))

    assert absent(screen.top, "product-card")
    assert find(screen.top, "products")


def test_editing_a_batch_to_zero_removes_it_whatever_its_date_and_keeps_the_product(
    shell: Shell, engine: Engine, screen: Screen, mleko: int
) -> None:
    first = _batch(engine, mleko, date(2026, 10, 30))
    _open(screen, mleko)

    _type(screen.top, f"batch-expiry-{first}", "jutro")
    _type(screen.top, f"batch-quantity-{first}", "0")
    tap(find(screen.top, f"batch-save-{first}"))

    assert absent(screen.top, f"batch-{first}")
    assert _expiries(screen, engine, mleko) == ["12.11.2026"]
    [product] = list_products(engine)
    assert (product.name, product.quantity) == ("Mleko", 3)
    assert texts(find(shell.body, f"quantity-{mleko}")) == ["3 szt."]


def test_editing_a_batch_changes_its_expiry_and_its_status_follows_the_saved_date(
    shell: Shell, engine: Engine, screen: Screen, mleko: int
) -> None:
    fresh = _batch(engine, mleko, date(2026, 11, 12))
    _open(screen, mleko)

    _type(screen.top, f"batch-expiry-{fresh}", "26.10.2026")
    assert absent(screen.top, f"batch-status-{fresh}")
    tap(find(screen.top, f"batch-save-{fresh}"))

    assert texts(find(screen.top, f"batch-status-{fresh}")) == ["przeterminowana"]
    assert _value(screen.top, f"batch-expiry-{fresh}") == "26.10.2026"
    assert get_product(engine, mleko).batches[0].expiry == date(2026, 10, 26)


def test_each_batch_is_marked_with_its_expiry_status(shell: Shell, engine: Engine, screen: Screen, mleko: int) -> None:
    purchase(engine, mleko, BatchDraft(1, date(2026, 10, 20)), TODAY)
    purchase(engine, mleko, BatchDraft(1, None), TODAY)
    _open(screen, mleko)

    expired = find(screen.top, f"batch-status-{_batch(engine, mleko, date(2026, 10, 20))}")
    expiring = find(screen.top, f"batch-status-{_batch(engine, mleko, date(2026, 10, 30))}")
    assert texts(expired) == ["przeterminowana"]
    assert texts(expiring) == ["kończy się termin"]
    # The colours of the Start sections Przeterminowane and Kończy się termin
    assert isinstance(expired, ft.Text) and isinstance(expiring, ft.Text)
    assert (expired.color, expiring.color) == ("#b3261e", "#a85d00")
    for fresh_or_undated in (date(2026, 11, 12), None):
        assert absent(screen.top, f"batch-status-{_batch(engine, mleko, fresh_or_undated)}")


@pytest.mark.parametrize("bad", ["31.02.2026", "2026-10-30"])
def test_a_bad_batch_date_shows_a_polish_error_and_saves_nothing(
    shell: Shell, engine: Engine, screen: Screen, mleko: int, bad: str
) -> None:
    original = get_product(engine, mleko)
    first = original.batches[0].id
    _open(screen, mleko)

    _type(screen.top, f"batch-expiry-{first}", bad)
    tap(find(screen.top, f"batch-save-{first}"))

    assert "Podaj datę w formacie DD.MM.RRRR." in texts(find(screen.top, f"batch-{first}"))
    assert get_product(engine, mleko) == original


def test_discard_and_undo_bring_the_batch_back_unchanged(
    shell: Shell, engine: Engine, screen: Screen, mleko: int
) -> None:
    original = get_product(engine, mleko)
    _open(screen, mleko)

    tap(find(screen.top, f"discard-{original.batches[0].id}"))

    assert _expiries(screen, engine, mleko) == ["12.11.2026"]
    bar = _snackbar(screen)
    assert (texts(bar), bar.action) == (["Wyrzucono partię: Mleko"], "Cofnij")

    tap(bar, "on_action")

    assert _expiries(screen, engine, mleko) == ["30.10.2026", "12.11.2026"]
    assert get_product(engine, mleko) == original


def test_using_several_units_from_the_card_and_one_undo_restores_every_batch(
    shell: Shell, engine: Engine, screen: Screen, mleko: int
) -> None:
    original = get_product(engine, mleko)
    _open(screen, mleko)

    _type(screen.top, "card-use-quantity", "3")
    tap(find(screen.top, "card-use"))

    assert "Razem: 2 szt." in texts(_card(screen))
    assert _expiries(screen, engine, mleko) == ["12.11.2026"]
    assert texts(_snackbar(screen)) == ["Zużyto 3 × Mleko"]

    tap(_snackbar(screen), "on_action")

    assert _expiries(screen, engine, mleko) == ["30.10.2026", "12.11.2026"]
    assert get_product(engine, mleko) == original


@pytest.mark.parametrize("action", ["card-use", "card-purchase"])
def test_a_change_on_the_card_reaches_the_screen_redrawn(shell: Shell, screen: Screen, mleko: int, action: str) -> None:
    _open(screen, mleko)

    tap(find(screen.top, action))
    if action == "card-purchase":
        tap(find(screen.top, "purchase-save"))

    assert ("Razem: 4 szt." if action == "card-use" else "Razem: 6 szt.") in screen.shown


def test_using_more_than_the_quantity_shows_a_polish_error_and_changes_nothing(
    shell: Shell, engine: Engine, screen: Screen, mleko: int
) -> None:
    original = get_product(engine, mleko)
    _open(screen, mleko)

    _type(screen.top, "card-use-quantity", "6")
    tap(find(screen.top, "card-use"))

    assert "Na stanie jest tylko 5." in texts(_card(screen))
    assert get_product(engine, mleko) == original


def test_card_lists_its_stock_events_newest_first_and_cofnij_takes_one_back(
    shell: Shell, screen: Screen, mleko: int
) -> None:
    _open(screen, mleko)
    assert "27.10.2026 · Zakup · +3 szt." in texts(find(screen.top, "card-history"))

    _type(screen.top, "card-use-quantity", "2")
    tap(find(screen.top, "card-use"))

    history = find(screen.top, "card-history")
    assert isinstance(history, ft.Column)
    assert [texts(line) for line in history.controls[:2]] == [
        ["27.10.2026 · Zużycie · −2 szt."],
        ["27.10.2026 · Zakup · +3 szt."],
    ]

    tap(_snackbar(screen), "on_action")

    shown = " ".join(texts(find(screen.top, "card-history")))
    assert "Zużycie" not in shown
    assert "Zakup" in shown


def test_a_discard_and_a_correction_are_listed(shell: Shell, engine: Engine, screen: Screen, mleko: int) -> None:
    first, second = get_product(engine, mleko).batches
    _open(screen, mleko)

    _type(screen.top, f"batch-quantity-{second.id}", "5")
    tap(find(screen.top, f"batch-save-{second.id}"))
    tap(find(screen.top, f"discard-{first.id}"))

    shown = texts(find(screen.top, "card-history"))
    assert "27.10.2026 · Wyrzucenie · −2 szt." in shown
    assert "27.10.2026 · Korekta · +2 szt." in shown


def _card_on_its_own(engine: Engine, screen: Screen, product_id: int, today: date = TODAY) -> Shell:
    shell = Shell(engine, screen.present, screen.update, screen.views, today=lambda: today)
    open_product_card(shell.ctx, product_id)
    return shell


def test_a_product_with_no_events_says_so(engine: Engine, screen: Screen) -> None:
    sol = add_product(engine, ProductDraft("Sól", SPOZYWCZE, OPAKOWANIE), BatchDraft(2))
    _card_on_its_own(engine, screen, sol)

    assert texts(find(screen.top, "card-history")) == ["Brak zdarzeń."]


def test_purchase_from_the_card_adds_a_batch_and_cofnij_takes_it_back(
    shell: Shell, engine: Engine, screen: Screen, mleko: int
) -> None:
    original = get_product(engine, mleko)
    _open(screen, mleko)
    tap(find(screen.top, "card-purchase"))

    _type(screen.top, "purchase-quantity", "2")
    _type(screen.top, "purchase-expiry", "01.03.2027")
    tap(find(screen.top, "purchase-save"))

    # Back on the card, which shows the new Batch, with Produkty redrawn behind it
    assert absent(screen.top, "purchase-dialog")
    assert "01.03.2027" in _expiries(screen, engine, mleko)
    assert texts(find(shell.body, f"quantity-{mleko}")) == ["7 szt."]
    assert texts(_snackbar(screen)) == ["Zakupiono: Mleko"]

    tap(_snackbar(screen), "on_action")

    assert _expiries(screen, engine, mleko) == ["30.10.2026", "12.11.2026"]
    assert texts(find(shell.body, f"quantity-{mleko}")) == ["5 szt."]
    assert get_product(engine, mleko) == original


def test_anuluj_closes_the_purchase_dialog_and_buys_nothing(
    shell: Shell, engine: Engine, screen: Screen, mleko: int
) -> None:
    _open(screen, mleko)
    tap(find(screen.top, "card-purchase"))

    tap(find(screen.top, "purchase-cancel"))

    assert find(screen.top, "product-card")
    assert get_product(engine, mleko).quantity == 5


def test_undoing_a_purchase_whose_batch_is_gone_says_so_and_changes_nothing(
    shell: Shell, engine: Engine, screen: Screen, mleko: int
) -> None:
    _open(screen, mleko)
    tap(find(screen.top, "card-purchase"))
    _type(screen.top, "purchase-expiry", "01.03.2027")
    tap(find(screen.top, "purchase-save"))
    discard_batch(engine, _batch(engine, mleko, date(2027, 3, 1)), TODAY)
    before = get_product(engine, mleko)

    tap(_snackbar(screen), "on_action")

    assert texts(_snackbar(screen)) == ["Tej partii już nie ma."]
    assert get_product(engine, mleko) == before


def test_a_usual_shelf_life_pre_fills_the_purchase_expiry_and_a_changed_date_is_saved_as_typed(
    engine: Engine, screen: Screen, mleko: int
) -> None:
    update_product(engine, mleko, ProductDraft("Mleko", SPOZYWCZE, SZTUKA, usual_shelf_life_days=7))
    _card_on_its_own(engine, screen, mleko)

    assert "Po zakupie: zwykle ważne 7 dni" in texts(_card(screen))
    tap(find(screen.top, "card-purchase"))
    assert _value(screen.top, "purchase-expiry") == "03.11.2026"

    _type(screen.top, "purchase-expiry", "05.11.2026")
    tap(find(screen.top, "purchase-save"))

    assert "05.11.2026" in _expiries(screen, engine, mleko)


def test_without_a_usual_shelf_life_the_purchase_expiry_starts_blank(shell: Shell, screen: Screen, mleko: int) -> None:
    _open(screen, mleko)
    tap(find(screen.top, "card-purchase"))

    assert _value(screen.top, "purchase-expiry") == ""


def test_the_purchase_dialog_on_its_own_suggests_the_amount_and_closes_back_to_the_tabs(
    engine: Engine, screen: Screen
) -> None:
    kawa = add_product(engine, ProductDraft("Kawa", SPOZYWCZE, OPAKOWANIE, minimum_stock=4), BatchDraft(1))
    shell = Shell(engine, screen.present, screen.update, screen.views, today=lambda: TODAY)
    # As Zakupy will open it
    open_purchase_dialog(shell.ctx, get_product(engine, kawa))

    assert "Zakup: Kawa" in texts(find(screen.top, "purchase-dialog"))
    # One above its Minimum Stock
    assert _value(screen.top, "purchase-quantity") == "4"
    tap(find(screen.top, "purchase-save"))

    assert screen.top.navigation_bar is shell.navigation_bar
    assert get_product(engine, kawa).quantity == 5
    assert texts(_snackbar(screen)) == ["Zakupiono: Kawa"]


@pytest.mark.parametrize(
    ("quantity", "expiry", "problem"),
    [
        ("2", "31.02.2026", "Podaj datę w formacie DD.MM.RRRR."),
        ("2", "2026-10-30", "Podaj datę w formacie DD.MM.RRRR."),
        ("1,5", "", "Podaj liczbę całkowitą"),
    ],
)
def test_a_bad_purchase_shows_a_polish_error_and_saves_nothing(
    shell: Shell, engine: Engine, screen: Screen, mleko: int, quantity: str, expiry: str, problem: str
) -> None:
    _open(screen, mleko)
    tap(find(screen.top, "card-purchase"))

    _type(screen.top, "purchase-quantity", quantity)
    _type(screen.top, "purchase-expiry", expiry)
    tap(find(screen.top, "purchase-save"))

    assert any(problem in text for text in texts(find(screen.top, "purchase-dialog")))
    assert get_product(engine, mleko).quantity == 5


def test_edit_from_the_card_opens_the_filled_in_form_and_the_card_shows_the_save(
    shell: Shell, engine: Engine, screen: Screen, mleko: int
) -> None:
    _open(screen, mleko)
    tap(find(screen.top, "card-edit"))

    assert _value(screen.top, "name") == "Mleko"
    _type(screen.top, "minimum-stock", "5")
    tap(find(screen.top, "save"))

    assert absent(screen.top, "product-form")
    assert "Stan minimalny: 5" in texts(_card(screen))
    [product] = list_products(engine)
    assert (product.id, product.name, product.minimum_stock, product.quantity) == (mleko, "Mleko", 5, 5)


def test_archive_closes_the_card_hides_the_product_and_cofnij_brings_it_back(
    shell: Shell, engine: Engine, screen: Screen, mleko: int
) -> None:
    _open(screen, mleko)

    tap(find(screen.top, "card-archive"))

    assert screen.top.navigation_bar is shell.navigation_bar
    assert absent(screen.top, f"product-{mleko}")
    assert list_products(engine) == []
    assert texts(_snackbar(screen)) == ["Zarchiwizowano: Mleko"]

    tap(_snackbar(screen), "on_action")

    assert find(screen.top, f"product-{mleko}")
    assert get_product(engine, mleko).quantity == 5


def _used_a_fifth_a_day(engine: Engine, today: date, minimum_stock: int | None) -> int:
    """Cukier with 6 Units Used over 30 days: a fifth of a Unit a day, 2 Units over the Buffer of 7."""
    cukier = add_product(
        engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE, minimum_stock=minimum_stock), BatchDraft(16)
    )
    purchase(engine, cukier, BatchDraft(1), today - timedelta(days=30))
    for days_ago in (20, 10, 1):
        use_units(engine, cukier, 2, today - timedelta(days=days_ago))
    return cukier


def test_the_card_shows_days_left_and_applies_the_suggested_minimum_stock_with_cofnij(
    engine: Engine, screen: Screen
) -> None:
    today = date(2026, 11, 2)
    cukier = _used_a_fifth_a_day(engine, today, minimum_stock=5)
    _card_on_its_own(engine, screen, cukier, today)

    assert texts(find(screen.top, "card-days-left")) == ["wystarczy na ok. 55 dni"]
    assert "Sugerowany stan minimalny: 2" in texts(find(screen.top, "card-suggested-minimum"))
    tap(find(screen.top, "card-apply-minimum"))

    assert "Stan minimalny: 2" in texts(_card(screen))
    assert absent(screen.top, "card-suggested-minimum")
    assert get_product(engine, cukier).minimum_stock == 2

    tap(_snackbar(screen), "on_action")

    assert "Stan minimalny: 5" in texts(_card(screen))
    assert find(screen.top, "card-suggested-minimum")
    assert get_product(engine, cukier).minimum_stock == 5


def test_no_suggested_minimum_stock_when_it_matches_the_current_one(engine: Engine, screen: Screen) -> None:
    today = date(2026, 11, 2)
    _card_on_its_own(engine, screen, _used_a_fifth_a_day(engine, today, minimum_stock=2), today)

    assert find(screen.top, "card-days-left")
    assert absent(screen.top, "card-suggested-minimum")


def test_the_card_shows_no_forecast_without_a_rate(shell: Shell, screen: Screen, mleko: int) -> None:
    _open(screen, mleko)

    assert absent(screen.top, "card-days-left")
    assert absent(screen.top, "card-suggested-minimum")
