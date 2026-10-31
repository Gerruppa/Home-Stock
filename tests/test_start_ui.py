from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from nicegui import ui
from nicegui.testing import user_simulation
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, PackSize, ProductDraft
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product
from home_stock.ui.shell import build_shell

SPOZYWCZE, APTECZKA = 1, 5
SZTUKA, OPAKOWANIE = 1, 2
TODAY = date(2026, 10, 27)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


def _add(engine: Engine, name: str, expiry: date, category: int = SPOZYWCZE, quantity: int = 1) -> int:
    return add_product(engine, ProductDraft(name, category, SZTUKA), BatchDraft(quantity, expiry))


def _shell(engine: Engine) -> None:
    build_shell(engine, today=lambda: TODAY)


async def test_shell_opens_on_start(engine: Engine) -> None:
    async with user_simulation(lambda: _shell(engine)) as user:
        await user.open("/")
        [panels] = user.find(kind=ui.tab_panels).elements
        assert panels.value == "start"


async def test_no_products_at_all_is_all_clear(engine: Engine) -> None:
    async with user_simulation(lambda: _shell(engine)) as user:
        await user.open("/")
        await user.should_see("Wszystko w porządku.")


async def test_expired_and_expiring_by_warning_window(engine: Engine) -> None:
    _add(engine, "Jogurt", date(2026, 10, 26), quantity=2)
    _add(engine, "Ser", date(2026, 10, 30))
    _add(engine, "Mleko", date(2026, 10, 27))
    _add(engine, "Szynka", date(2026, 10, 31))
    _add(engine, "Aspiryna", date(2026, 11, 20), category=APTECZKA)

    async with user_simulation(lambda: _shell(engine)) as user:
        await user.open("/")
        with user.scope(marker="expired"):
            await user.should_see("Przeterminowane")
            await user.should_see("Jogurt")
            await user.should_see("2 szt., termin 26.10.2026")
            await user.should_not_see("Mleko", retries=1)
            await user.should_not_see("Szynka", retries=1)
        with user.scope(marker="expiring"):
            await user.should_see("Kończy się termin")
            await user.should_see("Mleko")
            await user.should_see("1 szt., termin 27.10.2026")
            await user.should_see("Ser")
            await user.should_see("1 szt., termin 30.10.2026")
            await user.should_see("Aspiryna")
            await user.should_see("1 szt., termin 20.11.2026")
            await user.should_not_see("Jogurt", retries=1)
            await user.should_not_see("Szynka", retries=1)
        with user.scope(marker="running-low"):
            await user.should_see("Nic tutaj.")
        await user.should_not_see("Wszystko w porządku.")


async def test_expiring_lines_run_soonest_first(engine: Engine) -> None:
    _add(engine, "Ser", date(2026, 10, 30))
    _add(engine, "Mleko", date(2026, 10, 27))
    _add(engine, "Aspiryna", date(2026, 11, 20), category=APTECZKA)

    async with user_simulation(lambda: _shell(engine)) as user:
        await user.open("/")
        await user.should_see("1 szt., termin 30.10.2026")
        # The order on the page is the order in the element tree; ElementFilter makes no promise about its own
        [section] = user.find(marker="expiring").elements
        [_title, *rows] = section.default_slot.children
        assert [[label.text for label in row.default_slot.children if isinstance(label, ui.label)] for row in rows] == [
            ["Mleko", "1 szt., termin 27.10.2026"],
            ["Ser", "1 szt., termin 30.10.2026"],
            ["Aspiryna", "1 szt., termin 20.11.2026"],
        ]


async def test_do_kupienia_lists_products_running_low(engine: Engine) -> None:
    kg = PackSize(Decimal(1), "kg")
    add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE, kg, minimum_stock=3), BatchDraft(3))
    add_product(engine, ProductDraft("Pieprz", SPOZYWCZE, SZTUKA))

    async with user_simulation(lambda: _shell(engine)) as user:
        await user.open("/")
        with user.scope(marker="running-low"):
            await user.should_see("Do kupienia")
            await user.should_see("Cukier")
            await user.should_see("3 opak. (3 kg), minimum 3 opak.")
            await user.should_not_see("Pieprz", retries=1)
        with user.scope(marker="expired"):
            await user.should_see("Nic tutaj.")


async def test_a_purchase_on_the_shopping_list_clears_do_kupienia(engine: Engine) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE, minimum_stock=1), BatchDraft(1))

    async with user_simulation(lambda: _shell(engine)) as user:
        await user.open("/")
        await user.should_see("1 opak., minimum 1 opak.")
        user.find(marker="tab-shopping").click()
        user.find(marker=f"bought-{cukier}").click()
        user.find(marker="purchase-save").click()

        await user.should_see("Wszystko w porządku.")
