from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from nicegui import ui
from nicegui.testing import User, user_simulation
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, list_products
from home_stock.ui.shell import build_shell

SPOZYWCZE, CHEMIA = 1, 3
SZTUKA, OPAKOWANIE = 1, 2


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


@pytest.fixture
async def user(engine: Engine) -> AsyncIterator[User]:
    async with user_simulation(lambda: build_shell(engine)) as user:
        await user.open("/")
        user.find(marker="tab-products").click()
        yield user


def _choose(user: User, marker: str, label: str) -> None:
    select = user.find(marker=marker, kind=ui.select).elements.pop()
    select.set_value(next(value for value, text in select.options.items() if text == label))  # type: ignore[union-attr]


async def test_shell_has_the_four_tabs(engine: Engine) -> None:
    async with user_simulation(lambda: build_shell(engine)) as user:
        await user.open("/")
        for label in ("Start", "Produkty", "Lista zakupów", "Ustawienia"):
            await user.should_see(label)


async def test_no_products_says_so(user: User) -> None:
    await user.should_see("Nie masz jeszcze produktów.")


async def test_user_adds_a_product_with_a_first_batch(user: User, engine: Engine) -> None:
    user.find(marker="add-product").click()
    user.find(marker="name").type("Cukier")
    _choose(user, "category", "Spożywcze")
    _choose(user, "unit", "opakowanie")
    user.find(marker="first-quantity").type("3")
    user.find(marker="save").click()

    [cukier] = list_products(engine)
    with user.scope(marker=f"product-{cukier.id}"):
        await user.should_see("Cukier")
        await user.should_see("3 opak.")
    with user.scope(marker=f"category-{SPOZYWCZE}"):
        await user.should_see("Cukier")
    await user.should_not_see("Nie masz jeszcze produktów.")


async def test_invalid_input_shows_a_polish_error_and_saves_nothing(user: User, engine: Engine) -> None:
    user.find(marker="add-product").click()
    user.find(marker="first-quantity").type("1,5")
    user.find(marker="save").click()

    await user.should_see("Podaj nazwę produktu.")
    await user.should_see("Podaj liczbę całkowitą")
    assert list_products(engine) == []


async def test_search_filters_ignoring_case_and_hides_empty_categories(engine: Engine) -> None:
    add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(2))
    add_product(engine, ProductDraft("Płyn do naczyń", CHEMIA, SZTUKA))

    async with user_simulation(lambda: build_shell(engine)) as user:
        await user.open("/")
        user.find(marker="tab-products").click()
        await user.should_see("Płyn do naczyń")
        user.find(marker="search").type("CUK")

        await user.should_see("Cukier")
        await user.should_not_see("Płyn do naczyń")
        await user.should_not_see("Chemia i środki czystości")
