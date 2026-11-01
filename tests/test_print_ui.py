from pathlib import Path

import pytest
from nicegui.testing import User, user_simulation
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product
from home_stock.ui.print_list import register_print_page
from home_stock.ui.shell import build_shell

SPOZYWCZE, HIGIENA = 1, 4
OPAKOWANIE, ROLKA = 2, 3


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


async def _open_shopping(user: User) -> None:
    await user.open("/")
    user.find(marker="tab-shopping").click()


async def test_drukuj_opens_the_list_without_the_window_around_it(engine: Engine) -> None:
    add_product(engine, ProductDraft("Papier toaletowy", HIGIENA, ROLKA, minimum_stock=3), BatchDraft(1))
    add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE, minimum_stock=1), BatchDraft(1))
    add_product(engine, ProductDraft("Sól", SPOZYWCZE, OPAKOWANIE, minimum_stock=1), BatchDraft(5))

    async with user_simulation(lambda: build_shell(engine)) as user:
        register_print_page(engine)
        await _open_shopping(user)
        user.find(marker="print-list").click()

        await user.should_see("Spożywcze")
        await user.should_see("Cukier — kup 1 opak.")
        await user.should_see("Higiena i kosmetyki")
        await user.should_see("Papier toaletowy — kup 3 rol.")
        await user.should_not_see("Sól")
        await user.should_not_see("Lista zakupów")
        await user.should_not_see(marker="tab-shopping")
        await user.should_not_see(marker="print-list")


async def test_no_drukuj_for_an_empty_list(engine: Engine) -> None:
    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_shopping(user)
        await user.should_see("Nic nie trzeba kupować.")
        await user.should_not_see(marker="print-list")
