from datetime import date
from pathlib import Path

import pytest
from nicegui.testing import User, user_simulation
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, discard_batch, purchase, use_one
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


def _discarded(engine: Engine, product_id: int, draft: BatchDraft, bought: date, thrown: date) -> None:
    [batch] = purchase(engine, product_id, draft, bought).batches
    discard_batch(engine, batch.id, thrown)


async def test_waste_lists_each_products_discarded_units_most_first_for_30_and_90_days(engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA))
    chleb = add_product(engine, ProductDraft("Chleb", SPOZYWCZE, SZTUKA))
    # 8 days ago, 12 days past its date: Expired
    _discarded(engine, mleko, BatchDraft(3, date(2026, 10, 13)), date(2026, 10, 1), date(2026, 10, 25))
    # 74 days ago: in the 90 days only
    _discarded(engine, mleko, BatchDraft(3), date(2026, 8, 1), date(2026, 8, 20))
    _discarded(engine, chleb, BatchDraft(5), date(2026, 10, 30), date(2026, 10, 31))
    # A Use is no Waste
    purchase(engine, chleb, BatchDraft(4), date(2026, 10, 30))
    use_one(engine, chleb, date(2026, 11, 1))

    async with user_simulation(lambda: build_shell(engine, today=lambda: MONDAY)) as user:
        await _open_history(user)
        with user.scope(marker="history-waste-30"):
            await user.should_see("Chleb")
        assert _texts_in_order(user, "history-waste-30-line") == [
            "Chleb 5 szt. (przeterminowane: 0)",
            "Mleko 3 szt. (przeterminowane: 3)",
        ]
        assert _texts_in_order(user, "history-waste-90-line") == [
            "Mleko 6 szt. (przeterminowane: 3)",
            "Chleb 5 szt. (przeterminowane: 0)",
        ]


async def test_with_no_discards_in_a_period_waste_says_nothing_was_thrown_away(engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA))
    _discarded(engine, mleko, BatchDraft(2), date(2026, 8, 1), date(2026, 8, 20))
    chleb = add_product(engine, ProductDraft("Chleb", SPOZYWCZE, SZTUKA), BatchDraft(1))
    use_one(engine, chleb, MONDAY)

    async with user_simulation(lambda: build_shell(engine, today=lambda: MONDAY)) as user:
        await _open_history(user)
        with user.scope(marker="history-waste-30"):
            await user.should_see("Nic nie wyrzucono.")
        with user.scope(marker="history-waste-90"):
            await user.should_see("Mleko")
            await user.should_not_see("Nic nie wyrzucono.")


async def test_the_name_filter_leaves_waste_as_it_is(engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA))
    _discarded(engine, mleko, BatchDraft(2), date(2026, 10, 20), date(2026, 10, 25))

    async with user_simulation(lambda: build_shell(engine, today=lambda: MONDAY)) as user:
        await _open_history(user)
        user.find(marker="history-search").type("Chleb")

        with user.scope(marker="history-list"):
            await user.should_see("Brak zdarzeń pasujących produktów.")
        with user.scope(marker="history-waste-30"):
            await user.should_see("Mleko")
