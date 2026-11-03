from datetime import date, timedelta
from pathlib import Path

import pytest
from nicegui import ui
from nicegui.testing import User, user_simulation
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.db import init_db
from home_stock.persistence.products import (
    add_product,
    get_product,
    purchase,
    shopping_list_text,
    update_product,
    use_units,
)
from home_stock.persistence.settings import save_buffer_days
from home_stock.ui.shell import build_shell

SPOZYWCZE, HIGIENA = 1, 4
TODAY = date(2026, 11, 2)
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


async def test_each_product_shows_the_amount_to_buy(engine: Engine) -> None:
    papier = add_product(engine, ProductDraft("Papier toaletowy", HIGIENA, ROLKA, minimum_stock=3), BatchDraft(1))

    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_shopping(user)
        with user.scope(marker=f"shopping-{papier}"):
            await user.should_see("kup 3 rol.")


async def test_kopiuj_liste_confirms_that_the_list_was_copied(engine: Engine) -> None:
    add_product(engine, ProductDraft("Papier toaletowy", HIGIENA, ROLKA, minimum_stock=3), BatchDraft(1))

    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_shopping(user)
        user.find(marker="copy-list").click()
        await user.should_see("Skopiowano listę zakupów.")


async def test_no_kopiuj_liste_for_an_empty_list(engine: Engine) -> None:
    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_shopping(user)
        await user.should_see("Nic nie trzeba kupować.")
        await user.should_not_see(marker="copy-list")


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


async def test_a_purchase_from_the_list_can_be_undone_and_the_product_returns(engine: Engine) -> None:
    chusteczki = add_product(engine, ProductDraft("Chusteczki", HIGIENA, OPAKOWANIE, minimum_stock=2), BatchDraft(1))
    original = get_product(engine, chusteczki)

    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_shopping(user)
        user.find(marker=f"bought-{chusteczki}").click()
        user.find(marker="purchase-save").click()
        await user.should_see("Zakupiono: Chusteczki")

        user.find(marker="undo").click()

        with user.scope(marker=f"shopping-{chusteczki}"):
            await user.should_see("1 opak.")
        await user.should_not_see("Zakupiono: Chusteczki")
        assert get_product(engine, chusteczki) == original


def _running_out(engine: Engine) -> int:
    """Cukier without a Minimum Stock: 6 Units Used over 30 days, a fifth of a Unit a day; the 1 left lasts 5 days."""
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(6))
    purchase(engine, cukier, BatchDraft(1), TODAY - timedelta(days=30))
    for days_ago in (20, 10, 1):
        use_units(engine, cukier, 2, TODAY - timedelta(days=days_ago))
    return cukier


async def test_each_line_says_why_the_product_is_on_the_list(engine: Engine) -> None:
    papier = add_product(engine, ProductDraft("Papier toaletowy", HIGIENA, ROLKA, minimum_stock=3), BatchDraft(1))
    cukier = _running_out(engine)

    async with user_simulation(lambda: build_shell(engine, today=lambda: TODAY)) as user:
        await _open_shopping(user)
        with user.scope(marker=f"shopping-{papier}"):
            await user.should_see("poniżej minimum")
        with user.scope(marker=f"shopping-{cukier}"):
            await user.should_see("wystarczy na ok. 5 dni")


async def test_a_product_running_out_is_on_start_unpacking_and_the_copied_list(engine: Engine) -> None:
    cukier = _running_out(engine)

    assert shopping_list_text(engine, TODAY) == "Spożywcze\nCukier — kup 1 opak."
    async with user_simulation(lambda: build_shell(engine, today=lambda: TODAY)) as user:
        await user.open("/")
        with user.scope(marker=f"start-low-{cukier}"):
            await user.should_see("1 opak., wystarczy na ok. 5 dni")
        user.find(marker="tab-shopping").click()
        user.find(marker="unpack").click()
        await user.should_see(marker=f"unpack-row-{cukier}")


async def test_with_a_rate_the_list_kupione_and_unpacking_suggest_enough_to_cover_the_buffer(engine: Engine) -> None:
    cukier = _running_out(engine)
    update_product(engine, cukier, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE, minimum_stock=1))
    # A fifth of a Unit a day over a Buffer of 7 is 2 Units above the Minimum Stock of 1; 1 is there: buy 2

    assert shopping_list_text(engine, TODAY) == "Spożywcze\nCukier — kup 2 opak."
    async with user_simulation(lambda: build_shell(engine, today=lambda: TODAY)) as user:
        await _open_shopping(user)
        with user.scope(marker=f"shopping-{cukier}"):
            await user.should_see("kup 2 opak.")
        user.find(marker=f"bought-{cukier}").click()
        [quantity] = user.find(marker="purchase-quantity", kind=ui.input).elements
        assert quantity.value == "2"
        user.find(marker="purchase-save").click()
        await user.should_see("Nic nie trzeba kupować.")

        user.find(marker="undo").click()
        await user.should_see(marker=f"shopping-{cukier}")
        user.find(marker="unpack").click()
        [unpack_quantity] = user.find(marker=f"unpack-quantity-{cukier}", kind=ui.input).elements
        assert unpack_quantity.value == "2"


async def test_a_product_lasting_beyond_a_smaller_buffer_is_not_listed(engine: Engine) -> None:
    cukier = _running_out(engine)
    save_buffer_days(engine, 4)

    async with user_simulation(lambda: build_shell(engine, today=lambda: TODAY)) as user:
        await _open_shopping(user)
        await user.should_see("Nic nie trzeba kupować.")
        await user.should_not_see(marker=f"shopping-{cukier}")
