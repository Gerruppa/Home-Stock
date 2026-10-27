from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path

import pytest
from nicegui import ui
from nicegui.testing import User, user_simulation
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, PackSize, ProductDraft
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


async def test_shell_opens_on_produkty(engine: Engine) -> None:
    async with user_simulation(lambda: build_shell(engine)) as user:
        await user.open("/")
        [panels] = user.find(kind=ui.tab_panels).elements
        assert panels.value == "products"


async def test_duplicate_name_shows_a_polish_error(user: User, engine: Engine) -> None:
    add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE))
    user.find(marker="add-product").click()
    user.find(marker="name").type("cukier")
    user.find(marker="save").click()

    await user.should_see("Produkt o tej nazwie już istnieje.")
    assert len(list_products(engine)) == 1


async def test_categories_keep_the_spec_order(engine: Engine) -> None:
    add_product(engine, ProductDraft("Płyn do naczyń", CHEMIA, SZTUKA))
    add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE))

    async with user_simulation(lambda: build_shell(engine)) as user:
        await user.open("/")
        # The order on the page is the order in the element tree; ElementFilter makes no promise about its own
        [spozywcze] = user.find(marker=f"category-{SPOZYWCZE}").elements
        [chemia] = user.find(marker=f"category-{CHEMIA}").elements
        assert spozywcze.parent_slot is chemia.parent_slot
        siblings = spozywcze.parent_slot.children  # type: ignore[union-attr]
        assert siblings.index(spozywcze) < siblings.index(chemia)


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


async def _open_products(user: User) -> None:
    await user.open("/")
    user.find(marker="tab-products").click()


async def test_use_one_and_undo(engine: Engine) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(2))

    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_products(user)
        user.find(marker=f"use-{cukier}").click()
        with user.scope(marker=f"product-{cukier}"):
            await user.should_see("1 opak.")
        await user.should_see("Zużyto 1 × Cukier")

        user.find(marker="undo").click()
        with user.scope(marker=f"product-{cukier}"):
            await user.should_see("2 opak.")
        await user.should_not_see("Zużyto 1 × Cukier")


async def test_use_is_disabled_at_zero(engine: Engine) -> None:
    pieprz = add_product(engine, ProductDraft("Pieprz", SPOZYWCZE, SZTUKA))

    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_products(user)
        [button] = user.find(marker=f"use-{pieprz}", kind=ui.button).elements
        assert button.enabled is False


async def test_a_new_action_replaces_the_bar_and_undo_takes_back_only_the_last(engine: Engine) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(3))

    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_products(user)
        user.find(marker=f"use-{cukier}").click()
        user.find(marker=f"use-{cukier}").click()
        assert len(user.find(marker="undo").elements) == 1

        user.find(marker="undo").click()
        with user.scope(marker=f"product-{cukier}"):
            await user.should_see("2 opak.")


async def test_the_bar_disappears_on_its_own(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("home_stock.ui.shell.UNDO_SECONDS", 0.1)
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(2))

    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_products(user)
        user.find(marker=f"use-{cukier}").click()
        await user.should_see("Zużyto 1 × Cukier")
        await user.should_not_see("Zużyto 1 × Cukier")


async def test_another_change_hides_the_bar(engine: Engine) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(2))

    async with user_simulation(lambda: build_shell(engine)) as user:
        await _open_products(user)
        user.find(marker=f"use-{cukier}").click()
        await user.should_see("Zużyto 1 × Cukier")

        user.find(marker="add-product").click()
        user.find(marker="name").type("Mąka")
        user.find(marker="save").click()

        await user.should_not_see("Zużyto 1 × Cukier")


async def test_user_adds_a_product_with_a_pack_size_and_minimum_stock(user: User, engine: Engine) -> None:
    user.find(marker="add-product").click()
    user.find(marker="name").type("Cukier")
    _choose(user, "unit", "opakowanie")
    user.find(marker="pack-size").type("1 kg")
    user.find(marker="minimum-stock").clear().type("2")
    user.find(marker="first-quantity").type("2")
    user.find(marker="save").click()

    [cukier] = list_products(engine)
    assert cukier.pack_size == PackSize(Decimal("1"), "kg")
    assert cukier.minimum_stock == 2
    with user.scope(marker=f"product-{cukier.id}"):
        await user.should_see("2 opak. (2 kg)")


async def test_minimum_stock_is_prefilled_with_one_and_clearing_it_saves_none(user: User, engine: Engine) -> None:
    user.find(marker="add-product").click()
    [minimum] = user.find(marker="minimum-stock", kind=ui.input).elements
    assert minimum.value == "1"
    user.find(marker="name").type("Pieprz")
    user.find(marker="minimum-stock").clear()
    user.find(marker="save").click()

    await user.should_see("Pieprz")
    [pieprz] = list_products(engine)
    assert pieprz.minimum_stock is None


async def test_bad_pack_size_or_minimum_stock_shows_polish_errors_and_saves_nothing(user: User, engine: Engine) -> None:
    user.find(marker="add-product").click()
    user.find(marker="name").type("Cukier")
    user.find(marker="pack-size").type("1 szklanka")
    user.find(marker="minimum-stock").clear().type("1,5")
    user.find(marker="save").click()

    await user.should_see("Podaj rozmiar opakowania")
    await user.should_see("Podaj liczbę całkowitą")
    assert list_products(engine) == []

    user.find(marker="pack-size").clear().type("0 kg")
    user.find(marker="minimum-stock").clear().type("1")
    user.find(marker="save").click()

    await user.should_see("Podaj rozmiar opakowania")
    assert list_products(engine) == []
