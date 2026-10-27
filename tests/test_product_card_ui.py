from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path

import pytest
from nicegui.testing import User, user_simulation
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, get_product, list_products, purchase
from home_stock.ui.shell import build_shell

SPOZYWCZE = 1
SZTUKA, OPAKOWANIE = 1, 2


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
