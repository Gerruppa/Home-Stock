from datetime import date
from pathlib import Path

import flet as ft
import pytest
from sqlalchemy import Engine

from home_stock.domain.custom_lists import CustomListDraft, ListLineDraft
from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.mobile.shell import Shell
from home_stock.persistence.custom_lists import add_line, buy_lines, get_line, make_custom_list, tick_line
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


def _open(engine: Engine, screen: Screen, custom_list: int | None = None) -> ft.Control:
    """Rozpakuj zakupy tapped in Zakupy, on Brakuje or on the Custom List given: the form over the whole screen."""
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
    select(shell.navigation_bar, SHOPPING_TAB)
    if custom_list is not None:
        tap(find(shell.body, f"list-chip-{custom_list}"), "on_select")
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
    shell = Shell(engine, screen.present, screen.update, screen.views, screen.copy, screen.share, screen.open_url)
    select(shell.navigation_bar, SHOPPING_TAB)

    assert find(shell.body, "unpack")
    assert "Nic nie trzeba kupować." in texts(shell.body)


def _party(engine: Engine) -> tuple[int, int, int, int, int]:
    """Urodziny with Papier × 4 and Cukier × 3, neither Running Low; returns the list, the two Products and their
    lines."""
    papier = add_product(engine, ProductDraft("Papier toaletowy", HIGIENA, ROLKA), BatchDraft(5))
    cukier = _stocked(engine, "Cukier", shelf_life=10)
    urodziny = make_custom_list(engine, CustomListDraft("Urodziny"))
    papier_line = add_line(engine, urodziny, ListLineDraft.product(papier, 4)).line_id
    cukier_line = add_line(engine, urodziny, ListLineDraft.product(cukier, 3)).line_id
    return urodziny, papier, cukier, papier_line, cukier_line


def test_a_custom_list_s_rows_are_its_lines_by_category_with_their_quantities(engine: Engine, screen: Screen) -> None:
    urodziny, papier, cukier, _, _ = _party(engine)
    _low(engine, "Mąka")

    form = _open(engine, screen, urodziny)

    assert sorted(str(tick.label) for tick in walk(form) if isinstance(tick, ft.Checkbox)) == [
        "Cukier",
        "Papier toaletowy",
    ]
    assert (_field(form, f"unpack-quantity-{cukier}").value, _field(form, f"unpack-expiry-{cukier}").value) == (
        "3",
        "11.11.2026",
    )
    assert _field(form, f"unpack-quantity-{papier}").value == "4"
    keys = [control.key for control in find(form, "unpack-rows").controls]  # type: ignore[attr-defined]
    rows = [f"unpack-row-{product}" for product in (cukier, papier)]
    assert sorted(rows, key=keys.index) == rows


def test_free_text_bought_and_archived_lines_are_left_out(engine: Engine, screen: Screen) -> None:
    urodziny, _, cukier, papier_line, _ = _party(engine)
    tick_line(engine, add_line(engine, urodziny, ListLineDraft.note("balony")).line_id)
    add_line(engine, urodziny, ListLineDraft.note("świeczki"))
    buy_lines(engine, [(papier_line, BatchDraft(4))], TODAY)
    archive_product(engine, cukier)
    sol = _stocked(engine, "Sól")
    add_line(engine, urodziny, ListLineDraft.product(sol, 2))

    form = _open(engine, screen, urodziny)

    assert [str(tick.label) for tick in walk(form) if isinstance(tick, ft.Checkbox)] == ["Sól"]
    assert _field(form, f"unpack-quantity-{sol}").value == "2"


def test_a_custom_list_with_nothing_to_unpack_says_so(engine: Engine, screen: Screen) -> None:
    urodziny = make_custom_list(engine, CustomListDraft("Urodziny"))
    add_line(engine, urodziny, ListLineDraft.note("świeczki"))

    form = _open(engine, screen, urodziny)

    assert "Nie ma nic do rozpakowania." in texts(form)
    assert not find(form, "unpack-save").visible


def test_zapisz_on_a_custom_list_buys_the_ticked_lines_and_one_cofnij_takes_all_back(
    engine: Engine, screen: Screen
) -> None:
    urodziny, papier, cukier, papier_line, cukier_line = _party(engine)
    sol = _stocked(engine, "Sól")
    form = _open(engine, screen, urodziny)

    _untick(form, papier)
    _add_by_name(form, sol)
    _save(screen)

    snackbar = _snackbar(screen)
    assert texts(snackbar) == ["Rozpakowano zakupy: 2"]
    assert (get_line(engine, cukier_line).bought, get_line(engine, papier_line).bought) == (True, False)
    assert [get_product(engine, p).quantity for p in (cukier, papier, sol)] == [8, 5, 6]

    tap(snackbar, "on_action")

    assert not get_line(engine, cukier_line).bought
    assert [get_product(engine, p).quantity for p in (cukier, papier, sol)] == [5, 5, 5]


def test_a_line_bought_meanwhile_saves_nothing_and_says_so(engine: Engine, screen: Screen) -> None:
    urodziny, _, cukier, _, cukier_line = _party(engine)
    _open(engine, screen, urodziny)

    buy_lines(engine, [(cukier_line, BatchDraft(1))], TODAY)
    _save(screen)

    assert texts(_snackbar(screen)) == ["Ta pozycja jest już kupiona."]
    assert screen.top is screen.views[0]
    assert get_product(engine, cukier).quantity == 6


def test_brakuje_s_unpacking_ignores_the_custom_lists(engine: Engine, screen: Screen) -> None:
    _party(engine)
    maka = _low(engine, "Mąka")

    form = _open(engine, screen)

    assert [str(tick.label) for tick in walk(form) if isinstance(tick, ft.Checkbox)] == ["Mąka"]
    assert _field(form, f"unpack-quantity-{maka}").value == "2"
