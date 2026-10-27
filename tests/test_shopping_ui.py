from pathlib import Path

import pytest
from nicegui import ui
from nicegui.testing import User, user_simulation
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, get_product
from home_stock.ui.shell import build_shell

SPOZYWCZE, HIGIENA = 1, 4
SZTUKA, OPAKOWANIE, ROLKA = 1, 2, 3


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


async def _open_shopping(user: User) -> None:
    await user.open("/")
    user.find(marker="tab-shopping").click()


async def test_an_empty_list_says_so(engine: Engine) -> None:
    add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE, minimum_stock=1), BatchDraft(2))

    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_shopping(user)
        await user.should_see("Nic nie trzeba kupować.")


async def test_lists_products_running_low_by_category(engine: Engine) -> None:
    papier = add_product(engine, ProductDraft("Papier toaletowy", HIGIENA, ROLKA, minimum_stock=3), BatchDraft(3))
    add_product(engine, ProductDraft("Pieprz", SPOZYWCZE, SZTUKA))
    add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE, minimum_stock=1), BatchDraft(2))

    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_shopping(user)
        with user.scope(marker=f"shopping-category-{HIGIENA}"):
            await user.should_see("Higiena i kosmetyki")
        with user.scope(marker=f"shopping-{papier}"):
            await user.should_see("Papier toaletowy")
            await user.should_see("3 rol.")
        await user.should_not_see(marker=f"shopping-category-{SPOZYWCZE}")
        await user.should_not_see("Nic nie trzeba kupować.")


async def test_kupione_suggests_enough_and_the_product_leaves_the_list(engine: Engine) -> None:
    chusteczki = add_product(engine, ProductDraft("Chusteczki", HIGIENA, OPAKOWANIE, minimum_stock=2), BatchDraft(1))

    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_shopping(user)
        user.find(marker=f"bought-{chusteczki}").click()
        [quantity] = user.find(marker="purchase-quantity", kind=ui.input).elements
        assert quantity.value == "2"
        user.find(marker="purchase-save").click()

        await user.should_see("Nic nie trzeba kupować.")
        assert get_product(engine, chusteczki).quantity == 3


async def test_a_product_still_running_low_after_the_purchase_stays(engine: Engine) -> None:
    chusteczki = add_product(engine, ProductDraft("Chusteczki", HIGIENA, OPAKOWANIE, minimum_stock=4), BatchDraft(1))

    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_shopping(user)
        user.find(marker=f"bought-{chusteczki}").click()
        user.find(marker="purchase-quantity").clear().type("1")
        user.find(marker="purchase-save").click()

        with user.scope(marker=f"shopping-{chusteczki}"):
            await user.should_see("2 opak.")
