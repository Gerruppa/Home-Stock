from datetime import date
from pathlib import Path

import pytest
from nicegui.testing import User, user_simulation
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, purchase, use_one
from home_stock.ui.shell import build_shell

SPOZYWCZE = 1
SZTUKA, OPAKOWANIE = 1, 2
MONDAY, TUESDAY = date(2026, 11, 2), date(2026, 11, 3)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


async def _open_history(user: User) -> None:
    await user.open("/")
    user.find(marker="tab-history").click()


def _texts_in_order(user: User, marker: str) -> list[str]:
    elements = list(user.find(marker=marker).elements)
    ordered = sorted(elements, key=lambda e: e.parent_slot.children.index(e))  # type: ignore[union-attr]
    return [" ".join(label.text for label in e.default_slot.children) for e in ordered]  # type: ignore[attr-defined]


async def test_with_no_events_the_history_says_it_is_empty(engine: Engine) -> None:
    add_product(engine, ProductDraft("Pieprz", SPOZYWCZE, SZTUKA))

    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_history(user)
        with user.scope(marker="history-list"):
            await user.should_see("Historia jest pusta.")


async def test_lists_the_events_of_all_products_newest_first(engine: Engine) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE))
    maka = add_product(engine, ProductDraft("Mąka", SPOZYWCZE, SZTUKA))
    purchase(engine, cukier, BatchDraft(3), MONDAY)
    purchase(engine, maka, BatchDraft(2), MONDAY)
    use_one(engine, cukier, TUESDAY)

    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_history(user)
        with user.scope(marker="history-list"):
            await user.should_see("Cukier")
        assert _texts_in_order(user, "history-event") == [
            "03.11.2026 Cukier Zużycie −1 opak.",
            "02.11.2026 Mąka Zakup +2 szt.",
            "02.11.2026 Cukier Zakup +3 opak.",
        ]


async def test_typing_part_of_a_name_keeps_only_that_products_events(engine: Engine) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE))
    maka = add_product(engine, ProductDraft("Mąka", SPOZYWCZE, SZTUKA))
    purchase(engine, cukier, BatchDraft(3), MONDAY)
    purchase(engine, maka, BatchDraft(2), MONDAY)

    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_history(user)
        user.find(marker="history-search").type("MĄK")

        with user.scope(marker="history-list"):
            await user.should_see("Mąka")
            await user.should_not_see("Cukier")


async def test_a_use_elsewhere_and_its_cofnij_show_up_in_the_history(engine: Engine) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(2))

    async with user_simulation(lambda: build_shell(engine, today=lambda: TUESDAY)) as user:
        await _open_history(user)
        user.find(marker="tab-products").click()
        user.find(marker=f"use-{cukier}").click()

        with user.scope(marker="history-list"):
            await user.should_see("Zużycie")

        user.find(marker="undo").click()

        with user.scope(marker="history-list"):
            await user.should_not_see("Zużycie")
            await user.should_see("Historia jest pusta.")


async def test_a_purchase_on_the_shopping_list_shows_up_in_the_history(engine: Engine) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE, minimum_stock=1))

    async with user_simulation(lambda: build_shell(engine, today=lambda: TUESDAY)) as user:
        await _open_history(user)
        user.find(marker="tab-shopping").click()
        user.find(marker=f"bought-{cukier}").click()
        user.find(marker="purchase-save").click()

        with user.scope(marker="history-list"):
            await user.should_see("Zakup")
