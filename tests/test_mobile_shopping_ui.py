from datetime import date, timedelta
from pathlib import Path

import flet as ft
import pytest
from sqlalchemy import Engine

from home_stock.domain.custom_lists import CustomListDraft, ListLineDraft
from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.mobile.shell import Shell
from home_stock.persistence.custom_lists import add_line, get_line, list_custom_lists, list_lines, make_custom_list
from home_stock.persistence.db import init_db
from home_stock.persistence.products import (
    add_product,
    archive_product,
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


def _shell(engine: Engine, screen: Screen) -> Shell:
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
    return shell


def _field(screen: Screen, key: str) -> ft.TextField:
    field = find(screen.top, key)
    assert isinstance(field, ft.TextField)
    return field


def _make_list(body: ft.Control, screen: Screen, name: str, occasion: str = "") -> None:
    tap(find(body, "new-list"))
    _field(screen, "custom-list-name").value = name
    _field(screen, "custom-list-occasion").value = occasion
    tap(find(screen.top, "custom-list-save"))


def _write(body: ft.Control, *, product: int | None = None, text: str | None = None, quantity: str = "1") -> None:
    box = find(body, "line-name")
    assert isinstance(box, ft.Row)
    [name] = box.controls
    assert isinstance(name, ft.Dropdown)
    name.value = None if product is None else str(product)
    name.text = text
    quantity_field = find(body, "line-quantity")
    assert isinstance(quantity_field, ft.TextField)
    quantity_field.value = quantity
    tap(find(body, "line-add"))


def _only_list(engine: Engine) -> int:
    [custom_list] = list_custom_lists(engine)
    return custom_list.id


def test_nowa_lista_makes_a_list_and_selects_it(engine: Engine, screen: Screen) -> None:
    add_product(engine, ProductDraft("Papier toaletowy", HIGIENA, ROLKA, minimum_stock=3), BatchDraft(1))
    body = _open(engine, screen)

    _make_list(body, screen, "  Kolacja ", "15.11.2026")

    kolacja = _only_list(engine)
    assert screen.top is screen.views[0]
    chip = find(body, f"list-chip-{kolacja}")
    assert isinstance(chip, ft.Chip)
    assert chip.selected
    assert texts(chip) == ["Kolacja · 15.11"]
    assert "Lista jest pusta." in texts(body)
    assert absent(body, "copy-list")
    assert texts(screen.presented[-1]) == ["Utworzono listę: Kolacja"]


def test_brakuje_shows_the_shopping_list_again(engine: Engine, screen: Screen) -> None:
    papier = add_product(engine, ProductDraft("Papier toaletowy", HIGIENA, ROLKA, minimum_stock=3), BatchDraft(1))
    body = _open(engine, screen)
    _make_list(body, screen, "Kolacja")

    tap(find(body, "list-chip-missing"), "on_select")

    assert find(body, f"shopping-{papier}")
    assert absent(body, "line-name")
    tap(find(body, f"list-chip-{_only_list(engine)}"), "on_select")
    assert find(body, "line-name")


def test_a_list_needs_a_name_and_a_proper_date(engine: Engine, screen: Screen) -> None:
    body = _open(engine, screen)
    tap(find(body, "new-list"))
    _field(screen, "custom-list-occasion").value = "jutro"

    tap(find(screen.top, "custom-list-save"))

    assert "Podaj nazwę listy." in texts(screen.top)
    assert "Podaj datę w formacie DD.MM.RRRR." in texts(screen.top)
    assert list_custom_lists(engine) == []


def test_cofnij_takes_back_a_new_list_and_brakuje_is_shown(engine: Engine, screen: Screen) -> None:
    body = _open(engine, screen)
    _make_list(body, screen, "Kolacja")

    tap(screen.presented[-1], "on_action")

    assert list_custom_lists(engine) == []
    chip = find(body, "list-chip-missing")
    assert isinstance(chip, ft.Chip)
    assert chip.selected
    assert "Nic nie trzeba kupować." in texts(body)


def test_dopisz_writes_a_product_with_its_quantity_and_cofnij_takes_it_back(engine: Engine, screen: Screen) -> None:
    smietana = add_product(engine, ProductDraft("Śmietana", SPOZYWCZE, SZTUKA))
    body = _open(engine, screen)
    _make_list(body, screen, "Kolacja")

    _write(body, product=smietana, quantity="2")

    [line] = list_lines(engine, _only_list(engine))
    # Then the line's menu: Zmień ilość, Usuń
    assert texts(find(body, f"custom-line-{line.id}"))[:3] == ["Śmietana", "w domu: brak", "kup 2 szt."]
    assert "Lista jest pusta." not in texts(body)
    assert texts(screen.presented[-1]) == ["Dopisano: Śmietana"]

    tap(screen.presented[-1], "on_action")

    assert list_lines(engine, _only_list(engine)) == []
    assert "Lista jest pusta." in texts(body)


def test_a_typed_product_name_writes_that_product(engine: Engine, screen: Screen) -> None:
    smietana = add_product(engine, ProductDraft("Śmietana 30%", SPOZYWCZE, SZTUKA))
    body = _open(engine, screen)
    _make_list(body, screen, "Kolacja")

    _write(body, text=" śmietana  30% ")

    [line] = list_lines(engine, _only_list(engine))
    assert (line.product_id, line.quantity) == (smietana, 1)


def test_text_naming_no_product_becomes_a_free_text_line(engine: Engine, screen: Screen) -> None:
    body = _open(engine, screen)
    _make_list(body, screen, "Kolacja")

    _write(body, text="świeczki")
    _write(body, text="wino", quantity="3")

    lines = list_lines(engine, _only_list(engine))
    assert [line.text for line in lines] == ["świeczki", "wino × 3"]
    assert texts(find(body, f"custom-line-{lines[0].id}"))[0] == "świeczki"
    # Empty again for the next line
    box = find(body, "line-name")
    assert isinstance(box, ft.Row)
    [name] = box.controls
    assert isinstance(name, ft.Dropdown)
    assert (name.value, name.text) == (None, None)
    quantity = find(body, "line-quantity")
    assert isinstance(quantity, ft.TextField)
    assert quantity.value == "1"


def test_the_same_product_adds_to_its_line(engine: Engine, screen: Screen) -> None:
    smietana = add_product(engine, ProductDraft("Śmietana", SPOZYWCZE, SZTUKA))
    body = _open(engine, screen)
    _make_list(body, screen, "Kolacja")
    _write(body, product=smietana, quantity="2")

    _write(body, product=smietana, quantity="3")

    [line] = list_lines(engine, _only_list(engine))
    assert "kup 5 szt." in texts(find(body, f"custom-line-{line.id}"))
    tap(screen.presented[-1], "on_action")
    assert "kup 2 szt." in texts(find(body, f"custom-line-{line.id}"))


def test_dopisz_with_nothing_typed_or_a_wrong_quantity_says_so(engine: Engine, screen: Screen) -> None:
    smietana = add_product(engine, ProductDraft("Śmietana", SPOZYWCZE, SZTUKA))
    body = _open(engine, screen)
    _make_list(body, screen, "Kolacja")

    _write(body)
    assert "Wpisz, co kupić." in texts(body)

    _write(body, product=smietana, quantity="0")
    assert "Ilość musi być liczbą całkowitą większą od zera." in texts(body)
    _write(body, product=smietana, quantity="dwa")
    assert "Podaj liczbę całkowitą, np. 2." in texts(body)
    assert list_lines(engine, _only_list(engine)) == []


def test_the_selected_list_stays_after_a_redraw(engine: Engine, screen: Screen) -> None:
    shell = _shell(engine, screen)
    _make_list(shell.body, screen, "Kolacja")
    _make_list(shell.body, screen, "Grill")
    grill = next(lst.id for lst in list_custom_lists(engine) if lst.name == "Grill")

    shell.changed()

    chip = find(shell.body, f"list-chip-{grill}")
    assert isinstance(chip, ft.Chip)
    assert chip.selected
    assert find(shell.body, "line-name")


def test_a_line_of_an_archived_product_stays_and_says_so(engine: Engine, screen: Screen) -> None:
    smietana = add_product(engine, ProductDraft("Śmietana", SPOZYWCZE, SZTUKA))
    kolacja = make_custom_list(engine, CustomListDraft("Kolacja"))
    add_line(engine, kolacja, ListLineDraft.product(smietana, 1))
    archive_product(engine, smietana)
    body = _open(engine, screen)

    tap(find(body, f"list-chip-{kolacja}"), "on_select")

    [line] = list_lines(engine, kolacja)
    assert "Śmietana (w archiwum)" in texts(find(body, f"custom-line-{line.id}"))


def _dinner_on_screen(engine: Engine, screen: Screen) -> tuple[ft.Control, int, int, int, int]:
    """Kolacja (15.11.2026) with Śmietana × 2 and "świeczki", selected on Zakupy; returns the tab's body, the list,
    the Product and the two line ids."""
    smietana = add_product(engine, ProductDraft("Śmietana", SPOZYWCZE, SZTUKA))
    kolacja = make_custom_list(engine, CustomListDraft("Kolacja", date(2026, 11, 15)))
    product_line = add_line(engine, kolacja, ListLineDraft.product(smietana, 2)).line_id
    note_line = add_line(engine, kolacja, ListLineDraft.note("świeczki")).line_id
    body = _open(engine, screen)
    tap(find(body, f"list-chip-{kolacja}"), "on_select")
    return body, kolacja, smietana, product_line, note_line


def _bought(engine: Engine, line_id: int) -> bool:
    return get_line(engine, line_id).bought


def test_the_list_shows_its_name_and_date(engine: Engine, screen: Screen) -> None:
    body, *_ = _dinner_on_screen(engine, screen)

    assert texts(find(body, "custom-list-title")) == ["Kolacja · 15.11.2026"]


def test_a_free_text_line_ticked_goes_under_kupione_and_cofnij_brings_it_back(engine: Engine, screen: Screen) -> None:
    body, _, _, _, note_line = _dinner_on_screen(engine, screen)

    tap(find(body, f"tick-{note_line}"))

    assert _bought(engine, note_line)
    assert find(body, "bought-heading")
    assert absent(body, f"tick-{note_line}")
    # Bought lines come after the heading
    shown = texts(body)
    assert shown.index("Kupione") < shown.index("świeczki")
    assert texts(screen.presented[-1]) == ["Kupiono: świeczki"]

    tap(screen.presented[-1], "on_action")

    assert not _bought(engine, note_line)
    assert absent(body, "bought-heading")
    assert find(body, f"tick-{note_line}")


def test_a_product_line_is_bought_with_its_quantity_and_one_cofnij_takes_back_both(
    engine: Engine, screen: Screen
) -> None:
    body, _, smietana, product_line, _ = _dinner_on_screen(engine, screen)

    tap(find(body, f"tick-{product_line}"))
    assert _quantity_field(screen).value == "2"
    tap(find(screen.top, "purchase-save"))

    assert _bought(engine, product_line)
    assert get_product(engine, smietana).quantity == 2
    assert screen.top is screen.views[0]

    tap(screen.presented[-1], "on_action")

    assert not _bought(engine, product_line)
    assert get_product(engine, smietana).quantity == 0


def test_cancelling_the_purchase_leaves_the_line_to_buy(engine: Engine, screen: Screen) -> None:
    body, _, smietana, product_line, _ = _dinner_on_screen(engine, screen)

    tap(find(body, f"tick-{product_line}"))
    tap(find(screen.top, "purchase-cancel"))

    assert not _bought(engine, product_line)
    assert get_product(engine, smietana).quantity == 0


def test_with_every_line_bought_the_list_says_so(engine: Engine, screen: Screen) -> None:
    body, _, _, product_line, note_line = _dinner_on_screen(engine, screen)

    tap(find(body, f"tick-{note_line}"))
    tap(find(body, f"tick-{product_line}"))
    tap(find(screen.top, "purchase-save"))

    assert "Wszystko kupione." in texts(body)
    # A bought line keeps only Usuń
    assert absent(body, f"change-line-{product_line}")
    assert find(body, f"delete-line-{product_line}")
    # Nothing left to copy or share
    assert absent(body, "copy-list")
    assert absent(body, "share-list")


def test_kopiuj_liste_copies_the_custom_list_s_lines_to_buy(engine: Engine, screen: Screen) -> None:
    body, _, _, _, note_line = _dinner_on_screen(engine, screen)
    tap(find(body, f"tick-{note_line}"))

    tap(find(body, "copy-list"))

    assert screen.copied == ["Kolacja · 15.11.2026\nŚmietana — 2 szt."]
    assert texts(screen.presented[-1]) == ["Skopiowano listę: Kolacja"]


def test_udostepnij_shares_the_custom_list(engine: Engine, screen: Screen) -> None:
    body, *_ = _dinner_on_screen(engine, screen)

    tap(find(body, "share-list"))

    assert screen.shared == ["Kolacja · 15.11.2026\nŚmietana — 2 szt.\nświeczki"]


def test_zmien_ilosc_changes_a_product_line_and_cofnij_changes_it_back(engine: Engine, screen: Screen) -> None:
    body, _, _, product_line, _ = _dinner_on_screen(engine, screen)

    tap(find(body, f"change-line-{product_line}"))
    field = _field(screen, "line-edit-field")
    assert field.value == "2"
    field.value = "4"
    tap(find(screen.top, "line-edit-save"))

    assert get_line(engine, product_line).quantity == 4
    assert "kup 4 szt." in texts(find(body, f"custom-line-{product_line}"))
    tap(screen.presented[-1], "on_action")
    assert get_line(engine, product_line).quantity == 2


def test_zmien_ilosc_refuses_zero(engine: Engine, screen: Screen) -> None:
    body, _, _, product_line, _ = _dinner_on_screen(engine, screen)

    tap(find(body, f"change-line-{product_line}"))
    _field(screen, "line-edit-field").value = "0"
    tap(find(screen.top, "line-edit-save"))

    assert "Ilość musi być liczbą całkowitą większą od zera." in texts(screen.top)
    assert get_line(engine, product_line).quantity == 2


def test_zmien_tekst_changes_a_free_text_line(engine: Engine, screen: Screen) -> None:
    body, _, _, _, note_line = _dinner_on_screen(engine, screen)

    tap(find(body, f"change-line-{note_line}"))
    _field(screen, "line-edit-field").value = "świece zapachowe"
    tap(find(screen.top, "line-edit-save"))

    assert get_line(engine, note_line).text == "świece zapachowe"


def test_usun_removes_a_line_and_cofnij_puts_it_back(engine: Engine, screen: Screen) -> None:
    body, kolacja, _, product_line, _ = _dinner_on_screen(engine, screen)
    before = list_lines(engine, kolacja)

    tap(find(body, f"delete-line-{product_line}"))

    assert absent(body, f"custom-line-{product_line}")
    assert texts(screen.presented[-1]) == ["Usunięto: Śmietana"]
    tap(screen.presented[-1], "on_action")
    assert list_lines(engine, kolacja) == before


def test_edytuj_liste_renames_and_re_dates_the_list(engine: Engine, screen: Screen) -> None:
    body, kolacja, *_ = _dinner_on_screen(engine, screen)

    tap(find(body, "edit-list"))
    assert _field(screen, "custom-list-name").value == "Kolacja"
    assert _field(screen, "custom-list-occasion").value == "15.11.2026"
    _field(screen, "custom-list-name").value = "Kolacja u mamy"
    _field(screen, "custom-list-occasion").value = ""
    tap(find(screen.top, "custom-list-save"))

    assert texts(find(body, f"list-chip-{kolacja}")) == ["Kolacja u mamy"]
    tap(screen.presented[-1], "on_action")
    assert texts(find(body, f"list-chip-{kolacja}")) == ["Kolacja · 15.11"]


def test_usun_liste_shows_brakuje_and_cofnij_brings_the_list_back(engine: Engine, screen: Screen) -> None:
    body, kolacja, _, _, note_line = _dinner_on_screen(engine, screen)
    tap(find(body, f"tick-{note_line}"))
    lines = list_lines(engine, kolacja)

    tap(find(body, "delete-list"))

    assert list_custom_lists(engine) == []
    assert absent(body, f"list-chip-{kolacja}")
    chip = find(body, "list-chip-missing")
    assert isinstance(chip, ft.Chip) and chip.selected
    assert texts(screen.presented[-1]) == ["Usunięto listę: Kolacja"]

    tap(screen.presented[-1], "on_action")

    assert list_lines(engine, kolacja) == lines
    chip = find(body, f"list-chip-{kolacja}")
    assert isinstance(chip, ft.Chip) and chip.selected


def test_a_line_to_buy_says_how_much_is_at_home(engine: Engine, screen: Screen) -> None:
    # Spożywcze warns 3 days ahead: Śmietana's Batch expiring 4.11 is Expiring Soon on 2.11, and gone before 15.11
    smietana = add_product(engine, ProductDraft("Śmietana", SPOZYWCZE, SZTUKA), BatchDraft(1, date(2026, 11, 4)))
    maslo = add_product(engine, ProductDraft("Masło", SPOZYWCZE, SZTUKA))
    kolacja = make_custom_list(engine, CustomListDraft("Kolacja", date(2026, 11, 15)))
    smietana_line = add_line(engine, kolacja, ListLineDraft.product(smietana, 2)).line_id
    maslo_line = add_line(engine, kolacja, ListLineDraft.product(maslo, 1)).line_id
    note_line = add_line(engine, kolacja, ListLineDraft.note("świeczki")).line_id
    body = _open(engine, screen)

    tap(find(body, f"list-chip-{kolacja}"), "on_select")

    assert "w domu: 1 szt. · ważne do 04.11 · przed okazją" in texts(find(body, f"custom-line-{smietana_line}"))
    assert "w domu: brak" in texts(find(body, f"custom-line-{maslo_line}"))
    assert not any(text.startswith("w domu") for text in texts(find(body, f"custom-line-{note_line}")))


def test_a_bought_line_says_nothing_of_what_is_at_home(engine: Engine, screen: Screen) -> None:
    body, _, _, _, note_line = _dinner_on_screen(engine, screen)
    tap(find(body, f"tick-{note_line}"))
    [product_line] = [line for line in list_lines(engine, _only_list(engine)) if line.product_id is not None]
    tap(find(body, f"tick-{product_line.id}"))
    tap(find(screen.top, "purchase-save"))

    assert not any(text.startswith("w domu") for text in texts(find(body, f"custom-line-{product_line.id}")))


def _name_field(body: ft.Control) -> ft.Dropdown:
    box = find(body, "line-name")
    assert isinstance(box, ft.Row)
    [name] = box.controls
    assert isinstance(name, ft.Dropdown)
    return name


def test_dopisz_says_how_much_of_the_picked_product_is_at_home(engine: Engine, screen: Screen) -> None:
    smietana = add_product(engine, ProductDraft("Śmietana", SPOZYWCZE, SZTUKA), BatchDraft(2))
    body = _open(engine, screen)
    _make_list(body, screen, "Kolacja")
    assert texts(find(body, "line-at-home")) == []

    name = _name_field(body)
    name.value = str(smietana)
    tap(name, "on_select")

    assert texts(find(body, "line-at-home")) == ["w domu: 2 szt."]

    # Text naming no Product writes a free-text line, which says nothing of what is at home
    name.text = "świeczki"
    tap(name, "on_text_change")
    assert texts(find(body, "line-at-home")) == []

    name.text = "śmietana"
    tap(name, "on_text_change")
    assert texts(find(body, "line-at-home")) == ["w domu: 2 szt."]

    tap(find(body, "line-add"))
    assert texts(find(body, "line-at-home")) == []
