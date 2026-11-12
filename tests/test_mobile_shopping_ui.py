from datetime import date, timedelta
from pathlib import Path

import flet as ft
import pytest
from sqlalchemy import Engine

from home_stock.domain.custom_lists import CustomListDraft, ListLineDraft
from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.mobile.shell import Shell
from home_stock.persistence.custom_lists import add_line, list_custom_lists, list_lines, make_custom_list
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
    assert isinstance(box, ft.Container)
    name = box.content
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
    assert absent(body, "unpack")
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
    assert texts(find(body, f"custom-line-{line.id}")) == ["Śmietana", "kup 2 szt."]
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
    assert texts(find(body, f"custom-line-{lines[0].id}")) == ["świeczki"]
    # Empty again for the next line
    box = find(body, "line-name")
    assert isinstance(box, ft.Container) and isinstance(box.content, ft.Dropdown)
    assert (box.content.value, box.content.text) == (None, None)
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
