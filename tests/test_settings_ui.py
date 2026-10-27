from datetime import date
from pathlib import Path

import pytest
from nicegui.testing import User, user_simulation
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, archive_product, get_product, list_products
from home_stock.ui.shell import build_shell

SPOZYWCZE = 1
OPAKOWANIE = 2


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


async def _open_settings(user: User) -> None:
    await user.open("/")
    user.find(marker="tab-settings").click()


async def test_an_empty_archive_says_so(engine: Engine) -> None:
    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_settings(user)
        with user.scope(marker="archive"):
            await user.should_see("Archiwum jest puste.")


async def test_restore_brings_the_product_back_with_its_batches_and_settings(engine: Engine) -> None:
    mleko = add_product(
        engine, ProductDraft("Mleko", SPOZYWCZE, OPAKOWANIE, minimum_stock=3), BatchDraft(2, date(2026, 11, 12))
    )
    original = get_product(engine, mleko)
    archive_product(engine, mleko)

    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_settings(user)
        with user.scope(marker="archive"):
            await user.should_see("Mleko")
        user.find(marker=f"restore-{mleko}").click()

        with user.scope(marker="archive"):
            await user.should_see("Archiwum jest puste.")
        await user.should_see(marker=f"product-{mleko}")
    assert list_products(engine) == [original]
