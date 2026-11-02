from datetime import date
from pathlib import Path

import pytest
from nicegui import ui
from nicegui.testing import User, user_simulation
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, add_products, list_products, purchase
from home_stock.sources.starter_catalog import STARTER_CATALOG, available_starter_drafts
from home_stock.ui.shell import build_shell

SPOZYWCZE, ZWIERZETA = 1, 6
SZTUKA = 1
TODAY = date(2026, 11, 2)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


def _shell(engine: Engine) -> None:
    build_shell(engine, today=lambda: TODAY)


async def _open_from_settings(user: User) -> None:
    await user.open("/")
    user.find(marker="tab-settings").click()
    user.find(marker="starter-open").click()


def _tick(user: User, name: str) -> ui.checkbox:
    with user.scope(marker="starter-dialog"):
        [tick] = user.find(kind=ui.checkbox, content=name).elements
    assert isinstance(tick, ui.checkbox)
    return tick


async def test_saves_the_ticked_products_without_minimum_stock_or_batches(engine: Engine) -> None:
    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_from_settings(user)
        with user.scope(marker="starter-dialog"):
            await user.should_see("opakowanie · 1 l · zwykle ważne 7 dni")
        _tick(user, "Mleko").set_value(False)
        user.find(marker=f"starter-category-{ZWIERZETA}").click()
        user.find(marker="starter-save").click()

        await user.should_see("Dodano typowe produkty")

    products = list_products(engine)
    names = {product.name for product in products}
    assert "Mleko" not in names
    assert "Żwirek dla kota" not in names
    assert {"Masło", "Papier toaletowy", "Paracetamol"} <= names
    pets = sum(1 for product in STARTER_CATALOG if product.category == "Zwierzęta")
    assert len(products) == len(STARTER_CATALOG) - 1 - pets
    assert all(product.minimum_stock is None and product.batches == () for product in products)
    [maslo] = [product for product in products if product.name == "Masło"]
    assert maslo.usual_shelf_life_days == 30


async def test_opens_from_the_empty_produkty_tab_and_cofnij_removes_what_it_added(engine: Engine) -> None:
    async with user_simulation(lambda: _shell(engine)) as user:
        await user.open("/")
        user.find(marker="tab-products").click()
        user.find(marker="starter-open-empty").click()
        user.find(marker="starter-save").click()
        await user.should_see("Dodano typowe produkty")
        assert len(list_products(engine)) == len(STARTER_CATALOG)

        user.find(marker="undo").click()

        await user.should_not_see("Dodano typowe produkty")
        await user.should_see(marker="starter-open-empty")
    assert list_products(engine) == []


async def test_cofnij_refuses_once_a_product_has_a_purchase(engine: Engine) -> None:
    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_from_settings(user)
        user.find(marker="starter-save").click()
        await user.should_see("Dodano typowe produkty")
        [mleko] = [product for product in list_products(engine) if product.name == "Mleko"]
        purchase(engine, mleko.id, BatchDraft(1), TODAY)

        user.find(marker="undo").click()

        await user.should_see("Nie można cofnąć")
    assert len(list_products(engine)) == len(STARTER_CATALOG)


async def test_leaves_out_a_name_already_taken(engine: Engine) -> None:
    add_product(engine, ProductDraft("mleko", SPOZYWCZE, SZTUKA))

    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_from_settings(user)

        with user.scope(marker="starter-dialog"):
            await user.should_see("Masło")
            await user.should_not_see("Mleko")


async def test_says_so_when_every_starter_product_is_taken(engine: Engine) -> None:
    add_products(engine, available_starter_drafts(engine))

    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_from_settings(user)

        with user.scope(marker="starter-dialog"):
            await user.should_see("Masz już wszystkie typowe produkty.")
        await user.should_not_see(marker="starter-save")
