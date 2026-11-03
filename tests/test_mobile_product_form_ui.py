from datetime import date
from decimal import Decimal
from pathlib import Path

import flet as ft
import pytest
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, PackSize, ProductDraft
from home_stock.mobile.product_form import open_product_form
from home_stock.mobile.shell import Shell
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, archive_product, get_product, list_products, use_one
from mobile_ui import Screen, absent, find, select, tap, texts

SPOZYWCZE, CHEMIA = 1, 3
SZTUKA, OPAKOWANIE = 1, 2
PRODUCTS_TAB = 1
TODAY = date(2026, 10, 27)
FORM_FIELDS = ("name", "category", "unit", "pack-size", "minimum-stock", "shelf-life")


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


@pytest.fixture
def screen() -> Screen:
    return Screen()


@pytest.fixture
def shell(engine: Engine, screen: Screen) -> Shell:
    shell = Shell(engine, screen.present, screen.update, today=lambda: TODAY)
    select(shell.navigation_bar, PRODUCTS_TAB)
    return shell


def _type(root: ft.Control, key: str, value: str) -> None:
    """Replace what the field with ``key`` holds, as typing into it does."""
    field = find(root, key)
    assert isinstance(field, ft.TextField)
    field.value = value
    if field.on_change is not None:
        tap(field, "on_change")


def _choose(root: ft.Control, key: str, option: int) -> None:
    dropdown = find(root, key)
    assert isinstance(dropdown, ft.Dropdown)
    dropdown.value = str(option)


def _add(shell: Shell, **fields: str) -> None:
    """Open the form from Produkty, fill in ``fields`` (keys with dashes as underscores) and save."""
    tap(find(shell.body, "add-product"))
    for key, value in fields.items():
        _type(shell.body, key.replace("_", "-"), value)
    tap(find(shell.body, "save"))


def test_the_add_button_opens_the_form_over_the_whole_screen(shell: Shell) -> None:
    tap(find(shell.body, "add-product"))

    form = find(shell.body, "product-form")
    assert "Nowy produkt" in texts(form)
    assert absent(shell.body, "products")
    assert shell.navigation_bar.visible is False


def test_user_adds_a_product_with_a_first_batch_and_cofnij_takes_it_back(
    shell: Shell, engine: Engine, screen: Screen
) -> None:
    tap(find(shell.body, "add-product"))
    _type(shell.body, "name", "Cukier")
    _choose(shell.body, "category", SPOZYWCZE)
    _choose(shell.body, "unit", OPAKOWANIE)
    _type(shell.body, "first-quantity", "3")
    tap(find(shell.body, "save"))

    [cukier] = list_products(engine)
    assert (cukier.name, cukier.category_id, cukier.unit_id, cukier.quantity) == ("Cukier", SPOZYWCZE, OPAKOWANIE, 3)
    assert absent(shell.body, "product-form")
    assert shell.navigation_bar.visible is True
    assert texts(find(shell.body, f"quantity-{cukier.id}")) == ["3 opak."]
    [bar] = screen.presented
    assert (texts(bar), bar.action) == (["Dodano: Cukier"], "Cofnij")

    tap(bar, "on_action")

    assert list_products(engine) == []
    assert "Nie masz jeszcze produktów." in texts(shell.body)


def test_anuluj_closes_the_form_and_saves_nothing(shell: Shell, engine: Engine) -> None:
    tap(find(shell.body, "add-product"))
    _type(shell.body, "name", "Cukier")
    tap(find(shell.body, "cancel"))

    assert absent(shell.body, "product-form")
    assert shell.navigation_bar.visible is True
    assert list_products(engine) == []


def test_user_adds_a_product_with_a_pack_size_minimum_stock_and_usual_shelf_life(shell: Shell, engine: Engine) -> None:
    tap(find(shell.body, "add-product"))
    minimum = find(shell.body, "minimum-stock")
    assert isinstance(minimum, ft.TextField)
    assert minimum.value == "1"
    _choose(shell.body, "unit", OPAKOWANIE)
    _type(shell.body, "name", "Mleko")
    _type(shell.body, "pack-size", "1 l")
    _type(shell.body, "minimum-stock", "2")
    _type(shell.body, "shelf-life", "7")
    _type(shell.body, "first-quantity", "2")
    tap(find(shell.body, "save"))

    [mleko] = list_products(engine)
    assert (mleko.pack_size, mleko.minimum_stock, mleko.usual_shelf_life_days) == (PackSize(Decimal("1"), "l"), 2, 7)
    assert [(b.quantity, b.expiry) for b in mleko.batches] == [(2, date(2026, 11, 3))]


def test_clearing_minimum_stock_saves_none(shell: Shell, engine: Engine) -> None:
    _add(shell, name="Pieprz", minimum_stock="")

    [pieprz] = list_products(engine)
    assert pieprz.minimum_stock is None


def test_invalid_input_shows_polish_errors_and_saves_nothing(shell: Shell, engine: Engine) -> None:
    _add(shell, first_quantity="1,5", pack_size="1 szklanka", minimum_stock="1,5", shelf_life="tydzień")

    shown = " ".join(texts(find(shell.body, "product-form")))
    assert "Podaj nazwę produktu." in shown
    assert "Podaj liczbę całkowitą" in shown
    assert "Podaj rozmiar opakowania" in shown
    assert "Podaj liczbę dni od 1 do 3650, np. 7." in shown
    assert list_products(engine) == []


def test_fixing_the_input_clears_its_error_on_the_next_save(shell: Shell, engine: Engine) -> None:
    _add(shell, name="Mleko", shelf_life="0")
    _type(shell.body, "shelf-life", "7")
    _type(shell.body, "pack-size", "0 kg")
    tap(find(shell.body, "save"))

    shown = " ".join(texts(find(shell.body, "product-form")))
    assert "Podaj liczbę dni" not in shown
    assert "Podaj rozmiar opakowania" in shown
    assert list_products(engine) == []


def test_adding_an_existing_name_offers_its_first_batch_to_the_existing_product(
    shell: Shell, engine: Engine, screen: Screen
) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA, usual_shelf_life_days=7), BatchDraft(3))
    _add(shell, name=" mleko ", first_quantity="2")

    assert "Produkt o tej nazwie już istnieje." in texts(find(shell.body, "product-form"))
    assert absent(shell.body, "duplicate-restore")
    tap(find(shell.body, "duplicate-add-batch"))

    assert absent(shell.body, "product-form")
    assert texts(find(shell.body, f"quantity-{mleko}")) == ["5 szt."]
    [product] = list_products(engine)
    # Dated by the existing Product's Usual Shelf Life
    assert [(b.quantity, b.expiry) for b in product.batches] == [(2, date(2026, 11, 3)), (3, None)]


def test_accepting_the_offer_without_a_first_quantity_adds_nothing(shell: Shell, engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA), BatchDraft(3))
    _add(shell, name="MLEKO")
    tap(find(shell.body, "duplicate-add-batch"))

    assert absent(shell.body, "product-form")
    [product] = list_products(engine)
    assert (product.id, product.quantity) == (mleko, 3)


def test_changing_the_name_withdraws_the_offer(shell: Shell, engine: Engine) -> None:
    add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA))
    _add(shell, name="Mleko")
    find(shell.body, "duplicate-add-batch")

    _type(shell.body, "name", "Mleko 2%")

    assert absent(shell.body, "duplicate-add-batch")


def test_adding_an_archived_name_offers_restoring_it(shell: Shell, engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA), BatchDraft(3))
    archive_product(engine, mleko)
    _add(shell, name="mleko")

    assert "Produkt o tej nazwie już istnieje." in texts(find(shell.body, "product-form"))
    assert absent(shell.body, "duplicate-add-batch")
    tap(find(shell.body, "duplicate-restore"))

    assert texts(find(shell.body, f"quantity-{mleko}")) == ["3 szt."]
    [product] = list_products(engine)
    assert (product.id, product.name, product.quantity) == (mleko, "Mleko", 3)


def test_the_edit_form_is_filled_in_with_the_product(shell: Shell, engine: Engine) -> None:
    cukier = add_product(
        engine,
        ProductDraft("Cukier", CHEMIA, OPAKOWANIE, PackSize(Decimal("0.5"), "kg"), None, usual_shelf_life_days=365),
        BatchDraft(1),
    )
    open_product_form(shell.ctx, get_product(engine, cukier))

    form = find(shell.body, "product-form")
    assert "Edytuj produkt" in texts(form)
    values = {key: find(form, key).value for key in FORM_FIELDS}  # type: ignore[attr-defined]
    assert values == {
        "name": "Cukier",
        "category": str(CHEMIA),
        "unit": str(OPAKOWANIE),
        "pack-size": "0,5 kg",
        "minimum-stock": "",
        "shelf-life": "365",
    }
    assert absent(form, "first-quantity")


def test_editing_saves_the_product_and_keeps_its_batches(shell: Shell, engine: Engine, screen: Screen) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA), BatchDraft(5))
    open_product_form(shell.ctx, get_product(engine, mleko))
    _type(shell.body, "minimum-stock", "5")
    _choose(shell.body, "unit", OPAKOWANIE)
    tap(find(shell.body, "save"))

    assert absent(shell.body, "product-form")
    assert texts(find(shell.body, f"quantity-{mleko}")) == ["5 opak."]
    [product] = list_products(engine)
    assert (product.id, product.name, product.minimum_stock, product.unit_id, product.quantity) == (
        mleko,
        "Mleko",
        5,
        OPAKOWANIE,
        5,
    )
    assert screen.presented == []


def test_renaming_to_a_name_that_exists_is_refused(shell: Shell, engine: Engine) -> None:
    add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA))
    kefir = add_product(engine, ProductDraft("Kefir", SPOZYWCZE, SZTUKA))
    open_product_form(shell.ctx, get_product(engine, kefir))
    _type(shell.body, "name", "MLEKO")
    tap(find(shell.body, "save"))

    assert "Produkt o tej nazwie już istnieje." in texts(find(shell.body, "product-form"))
    assert absent(shell.body, "duplicate-add-batch")
    assert get_product(engine, kefir).name == "Kefir"


def test_cofnij_after_the_product_was_used_says_so_and_keeps_it(shell: Shell, engine: Engine, screen: Screen) -> None:
    _add(shell, name="Mleko", first_quantity="2")
    [mleko] = list_products(engine)
    [bar] = screen.presented
    use_one(engine, mleko.id, TODAY)

    tap(bar, "on_action")

    assert texts(bar) == ["Nie można cofnąć: ten produkt ma już historię."]
    assert [product.quantity for product in list_products(engine)] == [1]
