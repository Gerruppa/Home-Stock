from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from nicegui import ui
from nicegui.testing import User, user_simulation
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, PackSize, ProductDraft
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, get_product, list_products, purchase, update_product
from home_stock.ui.shell import build_shell

SPOZYWCZE, CHEMIA = 1, 3
SZTUKA, OPAKOWANIE = 1, 2
FORM_FIELDS = ("name", "category", "unit", "pack-size", "minimum-stock", "shelf-life")


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


@pytest.fixture
def mleko(engine: Engine) -> int:
    """Mleko with Batches 2 @ 30.10.2026 and 3 @ 12.11.2026."""
    product_id = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA), BatchDraft(2, date(2026, 10, 30)))
    purchase(engine, product_id, BatchDraft(3, date(2026, 11, 12)))
    return product_id


@pytest.fixture
async def user(engine: Engine, mleko: int) -> AsyncIterator[User]:
    """The Produkty tab, opened once Mleko exists."""
    async with user_simulation(lambda: build_shell(engine, today=lambda: date(2026, 10, 27))) as user:
        await user.open("/")
        user.find(marker="tab-products").click()
        yield user


def _fill(user: User, marker: str, text: str) -> None:
    field = user.find(marker=marker)
    field.clear()
    field.type(text)


async def test_card_shows_category_unit_and_batches(user: User, mleko: int) -> None:
    user.find(marker=f"open-{mleko}").click()

    with user.scope(marker="product-card"):
        await user.should_see("Mleko")
        await user.should_see("Spożywcze")
        await user.should_see("sztuka")
        await user.should_see("30.10.2026")
        await user.should_see("12.11.2026")


async def test_editing_a_batch_to_zero_removes_it_and_keeps_the_product(user: User, engine: Engine, mleko: int) -> None:
    first = get_product(engine, mleko).batches[0]
    user.find(marker=f"open-{mleko}").click()
    await user.should_see("30.10.2026")

    _fill(user, f"batch-quantity-{first.id}", "0")
    user.find(marker=f"batch-save-{first.id}").click()

    with user.scope(marker="product-card"):
        await user.should_not_see("30.10.2026")
    [product] = list_products(engine)
    assert (product.name, product.quantity) == ("Mleko", 3)


async def test_a_quantity_of_zero_removes_the_batch_whatever_its_date_field_says(
    user: User, engine: Engine, mleko: int
) -> None:
    first = get_product(engine, mleko).batches[0]
    user.find(marker=f"open-{mleko}").click()

    _fill(user, f"batch-expiry-{first.id}", "jutro")
    _fill(user, f"batch-quantity-{first.id}", "0")
    user.find(marker=f"batch-save-{first.id}").click()

    with user.scope(marker="product-card"):
        await user.should_not_see("30.10.2026")
    assert get_product(engine, mleko).quantity == 3


async def test_editing_a_batch_changes_its_expiry(user: User, engine: Engine, mleko: int) -> None:
    first = get_product(engine, mleko).batches[0]
    user.find(marker=f"open-{mleko}").click()

    _fill(user, f"batch-expiry-{first.id}", "1.11.2026")
    user.find(marker=f"batch-save-{first.id}").click()

    with user.scope(marker="product-card"):
        await user.should_see("01.11.2026")
    assert get_product(engine, mleko).batches[0].expiry == date(2026, 11, 1)


@pytest.mark.parametrize("bad", ["31.02.2026", "2026-10-30"])
async def test_a_bad_batch_date_shows_a_polish_error_and_saves_nothing(
    user: User, engine: Engine, mleko: int, bad: str
) -> None:
    original = get_product(engine, mleko)
    user.find(marker=f"open-{mleko}").click()

    _fill(user, f"batch-expiry-{original.batches[0].id}", bad)
    user.find(marker=f"batch-save-{original.batches[0].id}").click()

    await user.should_see("Podaj datę w formacie DD.MM.RRRR.")
    assert get_product(engine, mleko) == original


async def test_discard_and_undo_bring_the_batch_back_unchanged(user: User, engine: Engine, mleko: int) -> None:
    original = get_product(engine, mleko)
    first = original.batches[0]
    user.find(marker=f"open-{mleko}").click()

    user.find(marker=f"discard-{first.id}").click()

    with user.scope(marker="product-card"):
        await user.should_not_see("30.10.2026")
    await user.should_see("Wyrzucono partię: Mleko")
    assert get_product(engine, mleko).quantity == 3

    user.find(marker="undo").click()

    with user.scope(marker="product-card"):
        await user.should_see("30.10.2026")
    assert get_product(engine, mleko) == original


async def test_purchase_from_the_card_adds_a_batch(user: User, engine: Engine, mleko: int) -> None:
    user.find(marker=f"open-{mleko}").click()
    user.find(marker="card-purchase").click()

    _fill(user, "purchase-quantity", "2")
    user.find(marker="purchase-expiry").type("01.03.2027")
    user.find(marker="purchase-save").click()

    # The card stays open through the Produkty tab redrawing behind it, and shows the new Batch
    with user.scope(marker="product-card"):
        await user.should_see("01.03.2027")
    with user.scope(marker=f"product-{mleko}"):
        await user.should_see("7 szt.")
    assert get_product(engine, mleko).quantity == 7


async def test_a_usual_shelf_life_pre_fills_the_purchase_expiry_and_a_changed_date_is_saved_as_typed(
    user: User, engine: Engine, mleko: int
) -> None:
    update_product(engine, mleko, ProductDraft("Mleko", SPOZYWCZE, SZTUKA, shelf_life_days=7))
    user.find(marker=f"open-{mleko}").click()

    with user.scope(marker="product-card"):
        await user.should_see("zwykle ważne 7 dni")
    user.find(marker="card-purchase").click()
    [expiry] = user.find(marker="purchase-expiry", kind=ui.input).elements
    assert expiry.value == "03.11.2026"

    _fill(user, "purchase-expiry", "05.11.2026")
    user.find(marker="purchase-save").click()

    with user.scope(marker="product-card"):
        await user.should_see("05.11.2026")
    assert date(2026, 11, 5) in [b.expiry for b in get_product(engine, mleko).batches]


async def test_without_a_usual_shelf_life_the_purchase_expiry_starts_blank(user: User, mleko: int) -> None:
    user.find(marker=f"open-{mleko}").click()
    user.find(marker="card-purchase").click()

    [expiry] = user.find(marker="purchase-expiry", kind=ui.input).elements
    assert expiry.value == ""


@pytest.mark.parametrize("bad", ["31.02.2026", "2026-10-30"])
async def test_a_bad_purchase_date_shows_a_polish_error_and_saves_nothing(
    user: User, engine: Engine, mleko: int, bad: str
) -> None:
    user.find(marker=f"open-{mleko}").click()
    user.find(marker="card-purchase").click()

    user.find(marker="purchase-expiry").type(bad)
    user.find(marker="purchase-save").click()

    await user.should_see("Podaj datę w formacie DD.MM.RRRR.")
    assert get_product(engine, mleko).quantity == 5


async def test_two_uses_leave_the_later_batch(user: User, engine: Engine, mleko: int) -> None:
    user.find(marker=f"use-{mleko}").click()
    user.find(marker=f"use-{mleko}").click()
    with user.scope(marker=f"product-{mleko}"):
        await user.should_see("3 szt.")

    user.find(marker=f"open-{mleko}").click()
    with user.scope(marker="product-card"):
        await user.should_see("12.11.2026")
        await user.should_not_see("30.10.2026")


async def test_edit_from_the_card_saves_minimum_stock_under_the_same_name(
    user: User, engine: Engine, mleko: int
) -> None:
    user.find(marker=f"open-{mleko}").click()
    user.find(marker="card-edit").click()

    [name] = user.find(marker="name", kind=ui.input).elements
    assert name.value == "Mleko"
    _fill(user, "minimum-stock", "5")
    user.find(marker="save").click()

    with user.scope(marker="product-card"):
        await user.should_see("Stan minimalny: 5")
    [product] = list_products(engine)
    assert (product.id, product.name, product.minimum_stock, product.quantity) == (mleko, "Mleko", 5, 5)


async def test_the_edit_form_is_filled_in_with_the_product(engine: Engine) -> None:
    cukier = add_product(
        engine,
        ProductDraft("Cukier", CHEMIA, OPAKOWANIE, PackSize(Decimal("0.5"), "kg"), None, shelf_life_days=365),
        BatchDraft(1),
    )
    async with user_simulation(lambda: build_shell(engine)) as user:
        await user.open("/")
        user.find(marker="tab-products").click()
        user.find(marker=f"open-{cukier}").click()
        user.find(marker="card-edit").click()

        fields = {marker: user.find(marker=marker).elements.pop() for marker in FORM_FIELDS}
        assert {marker: field.value for marker, field in fields.items()} == {  # type: ignore[attr-defined]
            "name": "Cukier",
            "category": CHEMIA,
            "unit": OPAKOWANIE,
            "pack-size": "0,5 kg",
            "minimum-stock": "",
            "shelf-life": "365",
        }
        await user.should_not_see(marker="first-quantity")


async def test_renaming_to_a_name_that_exists_is_refused(engine: Engine, mleko: int) -> None:
    kefir = add_product(engine, ProductDraft("Kefir", SPOZYWCZE, SZTUKA))
    async with user_simulation(lambda: build_shell(engine)) as user:
        await user.open("/")
        user.find(marker="tab-products").click()
        user.find(marker=f"open-{kefir}").click()
        user.find(marker="card-edit").click()

        _fill(user, "name", "MLEKO")
        user.find(marker="save").click()

        await user.should_see("Produkt o tej nazwie już istnieje.")
        await user.should_not_see(marker="duplicate-add-batch")
    assert get_product(engine, kefir).name == "Kefir"


async def test_archive_hides_the_product_from_every_tab_and_undo_brings_it_back(engine: Engine) -> None:
    # Running Low and Expiring Soon, so it shows on Produkty, Start and Lista zakupów alike
    mleko = add_product(
        engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA, minimum_stock=5), BatchDraft(2, date(2026, 10, 28))
    )
    async with user_simulation(lambda: build_shell(engine, today=lambda: date(2026, 10, 27))) as user:
        await user.open("/")
        with user.scope(marker="expiring"):
            await user.should_see("Mleko")
        user.find(marker="tab-products").click()
        user.find(marker=f"open-{mleko}").click()
        user.find(marker="card-archive").click()

        await user.should_see("Zarchiwizowano: Mleko")
        await user.should_not_see(marker=f"product-{mleko}")
        await user.should_not_see(marker=f"shopping-{mleko}")
        # With Mleko gone Start has nothing left to show
        await user.should_see("Wszystko w porządku.")

        user.find(marker="undo").click()

        await user.should_see(marker=f"product-{mleko}")
        await user.should_see(marker=f"shopping-{mleko}")
        for section in ("expiring", "running-low"):
            with user.scope(marker=section):
                await user.should_see("Mleko")
    assert get_product(engine, mleko).quantity == 2
