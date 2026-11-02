from datetime import date
from pathlib import Path

import pytest
from nicegui import ui
from nicegui.testing import User, user_simulation
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, archive_product, get_product
from home_stock.ui.shell import build_shell

SPOZYWCZE, HIGIENA = 1, 4
OPAKOWANIE, ROLKA = 2, 3
TODAY = date(2026, 11, 1)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


def _shell(engine: Engine) -> None:
    build_shell(engine, today=lambda: TODAY)


async def _open_unpacking(user: User) -> None:
    await user.open("/")
    user.find(marker="tab-shopping").click()
    user.find(marker="unpack").click()


def _low(
    engine: Engine, name: str, category: int = SPOZYWCZE, unit: int = OPAKOWANIE, shelf_life: int | None = None
) -> int:
    return add_product(
        engine, ProductDraft(name, category, unit, minimum_stock=2, usual_shelf_life_days=shelf_life), BatchDraft(1)
    )


async def test_lists_every_product_with_its_suggested_quantity_and_shelf_life_date(engine: Engine) -> None:
    papier = _low(engine, "Papier toaletowy", HIGIENA, ROLKA)
    cukier = _low(engine, "Cukier", shelf_life=10)
    add_product(engine, ProductDraft("Sól", SPOZYWCZE, OPAKOWANIE, minimum_stock=1), BatchDraft(5))

    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_unpacking(user)

        with user.scope(marker=f"unpack-row-{cukier}"):
            await user.should_see("Cukier")
        [quantity] = user.find(marker=f"unpack-quantity-{cukier}", kind=ui.input).elements
        [expiry] = user.find(marker=f"unpack-expiry-{cukier}", kind=ui.input).elements
        assert (quantity.value, expiry.value) == ("2", "11.11.2026")
        [papier_expiry] = user.find(marker=f"unpack-expiry-{papier}", kind=ui.input).elements
        assert papier_expiry.value == ""
        with user.scope(marker="unpacking-dialog"):
            await user.should_not_see("Sól")


async def test_rows_follow_the_shopping_list_order(engine: Engine) -> None:
    papier = _low(engine, "Papier toaletowy", HIGIENA, ROLKA)
    maka = _low(engine, "Mąka")
    cukier = _low(engine, "Cukier")

    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_unpacking(user)

        rows = {
            product: next(iter(user.find(marker=f"unpack-row-{product}").elements))
            for product in (papier, maka, cukier)
        }
        siblings = rows[papier].parent_slot.children  # type: ignore[union-attr]
        assert sorted(rows, key=lambda product: siblings.index(rows[product])) == [cukier, maka, papier]


async def test_zapisz_records_the_ticked_rows_only(engine: Engine) -> None:
    cukier = _low(engine, "Cukier")
    papier = _low(engine, "Papier toaletowy", HIGIENA, ROLKA)

    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_unpacking(user)
        user.find(marker=f"unpack-tick-{papier}", kind=ui.checkbox).click()
        user.find(marker=f"unpack-quantity-{cukier}").clear().type("4")
        user.find(marker=f"unpack-expiry-{cukier}").clear().type("5.12.2026")
        user.find(marker="unpack-save").click()

        await user.should_see("Rozpakowano zakupy")
        assert get_product(engine, cukier).quantity == 5
        assert {b.expiry for b in get_product(engine, cukier).batches} == {date(2026, 12, 5), None}
        assert get_product(engine, papier).quantity == 1


async def test_one_invalid_row_shows_its_error_and_saves_nothing(engine: Engine) -> None:
    cukier = _low(engine, "Cukier")
    papier = _low(engine, "Papier toaletowy", HIGIENA, ROLKA)

    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_unpacking(user)
        user.find(marker=f"unpack-expiry-{papier}").clear().type("jutro")
        user.find(marker="unpack-save").click()

        with user.scope(marker=f"unpack-row-{papier}"):
            await user.should_see("Podaj datę")
        with user.scope(marker=f"unpack-row-{cukier}"):
            await user.should_not_see("Podaj datę")
        assert get_product(engine, cukier).quantity == 1
        assert get_product(engine, papier).quantity == 1


async def test_a_bad_quantity_is_refused_under_its_row(engine: Engine) -> None:
    cukier = _low(engine, "Cukier")

    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_unpacking(user)
        user.find(marker=f"unpack-quantity-{cukier}").clear().type("0")
        user.find(marker="unpack-save").click()

        with user.scope(marker=f"unpack-row-{cukier}"):
            await user.should_see("Ilość musi być liczbą całkowitą większą od zera.")
        assert get_product(engine, cukier).quantity == 1


async def test_a_bad_row_that_is_not_ticked_is_ignored(engine: Engine) -> None:
    cukier = _low(engine, "Cukier")
    papier = _low(engine, "Papier toaletowy", HIGIENA, ROLKA)

    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_unpacking(user)
        user.find(marker=f"unpack-tick-{papier}", kind=ui.checkbox).click()
        user.find(marker=f"unpack-quantity-{papier}").clear().type("x")
        user.find(marker="unpack-save").click()

        await user.should_see("Rozpakowano zakupy")
        assert get_product(engine, cukier).quantity == 3
        assert get_product(engine, papier).quantity == 1


async def test_one_cofnij_removes_every_batch_the_unpacking_created(engine: Engine) -> None:
    cukier = _low(engine, "Cukier")
    papier = _low(engine, "Papier toaletowy", HIGIENA, ROLKA)
    before = (get_product(engine, cukier), get_product(engine, papier))

    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_unpacking(user)
        user.find(marker="unpack-save").click()
        await user.should_see("Rozpakowano zakupy")
        assert get_product(engine, cukier).quantity == 3

        user.find(marker="undo").click()

        await user.should_not_see("Rozpakowano zakupy")
        assert (get_product(engine, cukier), get_product(engine, papier)) == before


async def test_an_empty_shopping_list_says_there_is_nothing_to_unpack(engine: Engine) -> None:
    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_unpacking(user)

        await user.should_see("Nie ma nic do rozpakowania.")
        await user.should_not_see(marker="unpack-save")


def _stocked(engine: Engine, name: str, shelf_life: int | None = None) -> int:
    """A Product that is not Running Low, so not on the Shopping List."""
    draft = ProductDraft(name, SPOZYWCZE, OPAKOWANIE, minimum_stock=1, usual_shelf_life_days=shelf_life)
    return add_product(engine, draft, BatchDraft(5))


def _add_by_name(user: User, product: int) -> None:
    [field] = user.find(marker="unpack-add", kind=ui.select).elements
    field.set_value(product)


async def test_the_name_field_offers_active_products_but_not_archived_ones(engine: Engine) -> None:
    _low(engine, "Cukier")
    _stocked(engine, "Sól")
    archive_product(engine, _stocked(engine, "Soda"))

    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_unpacking(user)

        [field] = user.find(marker="unpack-add", kind=ui.select).elements
        assert sorted(field.options.values()) == ["Cukier", "Sól"]  # type: ignore[union-attr]


async def test_picking_a_product_adds_a_ticked_row_with_its_defaults(engine: Engine) -> None:
    _low(engine, "Cukier")
    sol = _stocked(engine, "Sól", shelf_life=30)

    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_unpacking(user)
        with user.scope(marker="unpacking-dialog"):
            await user.should_not_see("Spoza listy")
        _add_by_name(user, sol)

        with user.scope(marker=f"unpack-row-{sol}"):
            await user.should_see("Sól")
        with user.scope(marker="unpacking-dialog"):
            await user.should_see("Spoza listy")
        [tick] = user.find(marker=f"unpack-tick-{sol}", kind=ui.checkbox).elements
        [quantity] = user.find(marker=f"unpack-quantity-{sol}", kind=ui.input).elements
        [expiry] = user.find(marker=f"unpack-expiry-{sol}", kind=ui.input).elements
        assert (tick.value, quantity.value, expiry.value) == (True, "1", "01.12.2026")


async def test_a_product_already_in_the_dialog_is_not_added_again(engine: Engine) -> None:
    cukier = _low(engine, "Cukier")
    sol = _stocked(engine, "Sól")

    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_unpacking(user)
        _add_by_name(user, cukier)
        _add_by_name(user, sol)
        _add_by_name(user, sol)

        assert len(user.find(marker=f"unpack-row-{cukier}").elements) == 1
        assert len(user.find(marker=f"unpack-row-{sol}").elements) == 1


async def test_an_added_row_is_saved_with_the_rest_and_undone_by_the_same_cofnij(engine: Engine) -> None:
    cukier = _low(engine, "Cukier")
    sol = _stocked(engine, "Sól")

    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_unpacking(user)
        _add_by_name(user, sol)
        user.find(marker=f"unpack-quantity-{sol}").clear().type("2")
        user.find(marker="unpack-save").click()

        await user.should_see("Rozpakowano zakupy: 2")
        assert (get_product(engine, cukier).quantity, get_product(engine, sol).quantity) == (3, 7)

        user.find(marker="undo").click()

        await user.should_not_see("Rozpakowano zakupy")
        assert (get_product(engine, cukier).quantity, get_product(engine, sol).quantity) == (1, 5)


async def test_an_added_row_is_validated_like_the_others(engine: Engine) -> None:
    sol = _stocked(engine, "Sól")

    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_unpacking(user)
        _add_by_name(user, sol)
        user.find(marker=f"unpack-expiry-{sol}").type("jutro")
        user.find(marker="unpack-save").click()

        with user.scope(marker=f"unpack-row-{sol}"):
            await user.should_see("Podaj datę")
        assert get_product(engine, sol).quantity == 5


async def test_an_empty_shopping_list_still_takes_a_product_by_name(engine: Engine) -> None:
    sol = _stocked(engine, "Sól")

    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_unpacking(user)
        _add_by_name(user, sol)
        user.find(marker="unpack-save").click()

        await user.should_see("Rozpakowano zakupy: 1")
        assert get_product(engine, sol).quantity == 6
