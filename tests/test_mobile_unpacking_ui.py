from datetime import date
from pathlib import Path

import flet as ft
import pytest
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.mobile.shell import Shell
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, archive_product, get_product
from mobile_ui import Screen, absent, find, select, tap, texts, walk

SPOZYWCZE, HIGIENA = 1, 4
OPAKOWANIE, ROLKA = 2, 3
SHOPPING_TAB = 2
TODAY = date(2026, 11, 1)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


@pytest.fixture
def screen() -> Screen:
    return Screen()


def _open(engine: Engine, screen: Screen) -> ft.Control:
    """Rozpakuj zakupy tapped in Zakupy: the form over the whole screen."""
    shell = Shell(engine, screen.present, screen.update, screen.views, screen.copy, screen.share, today=lambda: TODAY)
    select(shell.navigation_bar, SHOPPING_TAB)
    tap(find(shell.body, "unpack"))
    return find(screen.top, "unpacking-dialog")


def _low(
    engine: Engine, name: str, category: int = SPOZYWCZE, unit: int = OPAKOWANIE, shelf_life: int | None = None
) -> int:
    return add_product(
        engine, ProductDraft(name, category, unit, minimum_stock=2, usual_shelf_life_days=shelf_life), BatchDraft(1)
    )


def _stocked(engine: Engine, name: str, shelf_life: int | None = None) -> int:
    """A Product that is not Running Low, so not on the Shopping List."""
    draft = ProductDraft(name, SPOZYWCZE, OPAKOWANIE, minimum_stock=1, usual_shelf_life_days=shelf_life)
    return add_product(engine, draft, BatchDraft(5))


def _field(form: ft.Control, key: str) -> ft.TextField:
    field = find(form, key)
    assert isinstance(field, ft.TextField)
    return field


def _tick(form: ft.Control, product_id: int) -> ft.Checkbox:
    tick = find(form, f"unpack-tick-{product_id}")
    assert isinstance(tick, ft.Checkbox)
    return tick


def _untick(form: ft.Control, product_id: int) -> None:
    # The client changes a Checkbox's value by itself, without a handler of the app's
    _tick(form, product_id).value = False


def _add_by_name(form: ft.Control, product_id: int) -> None:
    field = find(form, "unpack-add")
    assert isinstance(field, ft.Dropdown)
    field.value = str(product_id)
    tap(field, "on_select")


def _save(screen: Screen) -> None:
    tap(find(screen.top, "unpack-save"))


def _snackbar(screen: Screen) -> ft.SnackBar:
    bar = screen.presented[-1]
    assert bar.open
    return bar


def test_lists_every_product_with_its_suggested_quantity_and_shelf_life_date(engine: Engine, screen: Screen) -> None:
    papier = _low(engine, "Papier toaletowy", HIGIENA, ROLKA)
    cukier = _low(engine, "Cukier", shelf_life=10)
    add_product(engine, ProductDraft("Sól", SPOZYWCZE, OPAKOWANIE, minimum_stock=1), BatchDraft(5))

    form = _open(engine, screen)

    assert _tick(form, cukier).label == "Cukier"
    assert (_field(form, f"unpack-quantity-{cukier}").value, _field(form, f"unpack-expiry-{cukier}").value) == (
        "2",
        "11.11.2026",
    )
    assert _field(form, f"unpack-expiry-{papier}").value == ""
    assert sorted(str(tick.label) for tick in walk(form) if isinstance(tick, ft.Checkbox)) == [
        "Cukier",
        "Papier toaletowy",
    ]


def test_rows_follow_the_shopping_list_order(engine: Engine, screen: Screen) -> None:
    papier = _low(engine, "Papier toaletowy", HIGIENA, ROLKA)
    maka = _low(engine, "Mąka")
    cukier = _low(engine, "Cukier")

    form = _open(engine, screen)

    keys = [control.key for control in find(form, "unpack-rows").controls]  # type: ignore[attr-defined]
    rows = [f"unpack-row-{product}" for product in (cukier, maka, papier)]
    assert sorted(rows, key=keys.index) == rows


def test_zapisz_records_the_ticked_rows_only(engine: Engine, screen: Screen) -> None:
    cukier = _low(engine, "Cukier")
    papier = _low(engine, "Papier toaletowy", HIGIENA, ROLKA)
    form = _open(engine, screen)

    _untick(form, papier)
    _field(form, f"unpack-quantity-{cukier}").value = "4"
    _field(form, f"unpack-expiry-{cukier}").value = "5.12.2026"
    _save(screen)

    assert texts(_snackbar(screen)) == ["Rozpakowano zakupy: 1"]
    assert screen.top is screen.views[0]
    assert get_product(engine, cukier).quantity == 5
    assert {b.expiry for b in get_product(engine, cukier).batches} == {date(2026, 12, 5), None}
    assert get_product(engine, papier).quantity == 1


def test_one_invalid_row_shows_its_error_and_saves_nothing(engine: Engine, screen: Screen) -> None:
    cukier = _low(engine, "Cukier")
    papier = _low(engine, "Papier toaletowy", HIGIENA, ROLKA)
    form = _open(engine, screen)

    _field(form, f"unpack-expiry-{papier}").value = "jutro"
    updates = screen.updates
    _save(screen)

    assert any(text.startswith("Podaj datę") for text in texts(find(form, f"unpack-row-{papier}")))
    assert not any(text.startswith("Podaj datę") for text in texts(find(form, f"unpack-row-{cukier}")))
    assert screen.updates == updates + 1
    assert find(screen.top, "unpacking-dialog") is form
    assert get_product(engine, cukier).quantity == 1
    assert get_product(engine, papier).quantity == 1


def test_a_bad_quantity_is_refused_under_its_row(engine: Engine, screen: Screen) -> None:
    cukier = _low(engine, "Cukier")
    form = _open(engine, screen)

    _field(form, f"unpack-quantity-{cukier}").value = "0"
    _save(screen)

    assert "Ilość musi być liczbą całkowitą większą od zera." in texts(find(form, f"unpack-row-{cukier}"))
    assert get_product(engine, cukier).quantity == 1


def test_both_problems_of_a_row_show_under_it(engine: Engine, screen: Screen) -> None:
    cukier = _low(engine, "Cukier")
    form = _open(engine, screen)

    _field(form, f"unpack-quantity-{cukier}").value = "x"
    _field(form, f"unpack-expiry-{cukier}").value = "jutro"
    _save(screen)

    shown = texts(find(form, f"unpack-row-{cukier}"))
    assert "Podaj liczbę całkowitą, np. 2.\nPodaj datę w formacie DD.MM.RRRR." in shown


def test_a_bad_row_that_is_not_ticked_is_ignored(engine: Engine, screen: Screen) -> None:
    cukier = _low(engine, "Cukier")
    papier = _low(engine, "Papier toaletowy", HIGIENA, ROLKA)
    form = _open(engine, screen)

    _untick(form, papier)
    _field(form, f"unpack-quantity-{papier}").value = "x"
    _save(screen)

    assert texts(_snackbar(screen)) == ["Rozpakowano zakupy: 1"]
    assert get_product(engine, cukier).quantity == 3
    assert get_product(engine, papier).quantity == 1


def test_one_cofnij_removes_every_batch_the_unpacking_created(engine: Engine, screen: Screen) -> None:
    cukier = _low(engine, "Cukier")
    papier = _low(engine, "Papier toaletowy", HIGIENA, ROLKA)
    before = (get_product(engine, cukier), get_product(engine, papier))
    _open(engine, screen)

    _save(screen)
    snackbar = _snackbar(screen)
    assert texts(snackbar) == ["Rozpakowano zakupy: 2"]
    assert get_product(engine, cukier).quantity == 3

    tap(snackbar, "on_action")

    assert not snackbar.open
    assert (get_product(engine, cukier), get_product(engine, papier)) == before


def test_an_empty_shopping_list_says_there_is_nothing_to_unpack(engine: Engine, screen: Screen) -> None:
    form = _open(engine, screen)

    assert "Nie ma nic do rozpakowania." in texts(form)
    assert not find(form, "unpack-save").visible


def test_nothing_ticked_closes_the_form_and_saves_nothing(engine: Engine, screen: Screen) -> None:
    cukier = _low(engine, "Cukier")
    form = _open(engine, screen)

    _untick(form, cukier)
    _save(screen)

    assert screen.top is screen.views[0]
    assert screen.presented == []
    assert get_product(engine, cukier).quantity == 1


def test_the_name_field_offers_active_products_but_not_archived_ones(engine: Engine, screen: Screen) -> None:
    _low(engine, "Cukier")
    _stocked(engine, "Sól")
    archive_product(engine, _stocked(engine, "Soda"))

    form = _open(engine, screen)

    field = find(form, "unpack-add")
    assert isinstance(field, ft.Dropdown)
    assert sorted(option.text or "" for option in field.options or []) == ["Cukier", "Sól"]


def test_picking_a_product_adds_a_ticked_row_with_its_defaults(engine: Engine, screen: Screen) -> None:
    _low(engine, "Cukier")
    sol = _stocked(engine, "Sól", shelf_life=30)
    form = _open(engine, screen)
    assert not find(form, "unpack-added").visible
    updates = screen.updates

    _add_by_name(form, sol)

    assert _tick(form, sol).label == "Sól"
    assert find(form, "unpack-added").visible
    assert "Spoza listy" in texts(find(form, "unpack-added"))
    assert (_tick(form, sol).value, _field(form, f"unpack-quantity-{sol}").value) == (True, "1")
    assert _field(form, f"unpack-expiry-{sol}").value == "01.12.2026"
    field = find(form, "unpack-add")
    assert isinstance(field, ft.Dropdown)
    assert (field.value, field.text) == (None, "")
    assert screen.updates == updates + 1


def test_a_product_already_in_the_dialog_is_not_added_again(engine: Engine, screen: Screen) -> None:
    cukier = _low(engine, "Cukier")
    sol = _stocked(engine, "Sól")
    form = _open(engine, screen)

    _add_by_name(form, cukier)
    _add_by_name(form, sol)
    _add_by_name(form, sol)

    # find() fails unless exactly one control has the key
    find(form, f"unpack-row-{cukier}")
    find(form, f"unpack-row-{sol}")


def test_an_added_row_is_saved_with_the_rest_and_undone_by_the_same_cofnij(engine: Engine, screen: Screen) -> None:
    cukier = _low(engine, "Cukier")
    sol = _stocked(engine, "Sól")
    form = _open(engine, screen)

    _add_by_name(form, sol)
    _field(form, f"unpack-quantity-{sol}").value = "2"
    _save(screen)

    snackbar = _snackbar(screen)
    assert texts(snackbar) == ["Rozpakowano zakupy: 2"]
    assert (get_product(engine, cukier).quantity, get_product(engine, sol).quantity) == (3, 7)

    tap(snackbar, "on_action")

    assert (get_product(engine, cukier).quantity, get_product(engine, sol).quantity) == (1, 5)


def test_an_added_row_is_validated_like_the_others(engine: Engine, screen: Screen) -> None:
    sol = _stocked(engine, "Sól")
    form = _open(engine, screen)

    _add_by_name(form, sol)
    _field(form, f"unpack-expiry-{sol}").value = "jutro"
    _save(screen)

    assert any(text.startswith("Podaj datę") for text in texts(find(form, f"unpack-row-{sol}")))
    assert get_product(engine, sol).quantity == 5


def test_an_empty_shopping_list_still_takes_a_product_by_name(engine: Engine, screen: Screen) -> None:
    sol = _stocked(engine, "Sól")
    form = _open(engine, screen)
    assert absent(form, f"unpack-row-{sol}")

    _add_by_name(form, sol)

    assert find(form, "unpack-save").visible
    assert "Nie ma nic do rozpakowania." not in texts(form)
    _save(screen)
    assert texts(_snackbar(screen)) == ["Rozpakowano zakupy: 1"]
    assert get_product(engine, sol).quantity == 6


def test_rozpakuj_zakupy_is_offered_on_an_empty_list_too(engine: Engine, screen: Screen) -> None:
    shell = Shell(engine, screen.present, screen.update, screen.views, screen.copy, screen.share)
    select(shell.navigation_bar, SHOPPING_TAB)

    assert find(shell.body, "unpack")
    assert "Nic nie trzeba kupować." in texts(shell.body)
