"""Keyboard use: Enter saves a dialog, Esc closes it, and the Produkty search takes the cursor."""

from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path

import pytest
from nicegui import ui
from nicegui.testing import User, user_simulation
from nicegui.testing.user_interaction import UserInteraction
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, get_product, list_products
from home_stock.ui.shell import build_shell

SPOZYWCZE, OPAKOWANIE = 1, 2
KEY_F = {
    "action": "keydown",
    "key": "f",
    "code": "KeyF",
    "location": 0,
    "repeat": False,
    "altKey": False,
    "ctrlKey": True,
    "metaKey": False,
    "shiftKey": False,
}


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


@pytest.fixture
async def user(engine: Engine) -> AsyncIterator[User]:
    async with user_simulation(lambda: build_shell(engine, today=lambda: date(2026, 11, 1))) as user:
        await user.open("/")
        yield user


@pytest.fixture
def mleko(engine: Engine) -> int:
    return add_product(engine, ProductDraft("Mleko", SPOZYWCZE, OPAKOWANIE, minimum_stock=2), BatchDraft(1))


def _open_cards(user: User, marker: str) -> set[ui.element]:
    """The cards marked ``marker`` whose dialog is open; a closed dialog stays in the element tree."""
    return {
        card
        for card in user.find(marker=marker).elements
        if any(isinstance(parent, ui.dialog) and parent.value for parent in card.ancestors())
    }


def _is_open(user: User, marker: str) -> bool:
    return bool(_open_cards(user, marker))


def _press(user: User, marker: str, key: str) -> None:
    [card] = _open_cards(user, marker)
    UserInteraction(user, {card}, None).trigger(key)


def _enter(user: User, marker: str) -> None:
    _press(user, marker, "keydown.enter")


def _esc(user: User, marker: str) -> None:
    _press(user, marker, "keydown.esc")


async def test_enter_in_the_product_form_saves_it(user: User, engine: Engine) -> None:
    user.find(marker="tab-products").click()
    user.find(marker="add-product").click()
    user.find(marker="name").type("Cukier")
    _enter(user, "product-form")

    assert [p.name for p in list_products(engine)] == ["Cukier"]
    assert not _is_open(user, "product-form")


async def test_enter_in_the_product_form_keeps_a_validation_error_shown(user: User, engine: Engine) -> None:
    user.find(marker="tab-products").click()
    user.find(marker="add-product").click()
    user.find(marker="first-quantity").type("1,5")
    _enter(user, "product-form")

    with user.scope(marker="product-form"):
        await user.should_see("Podaj nazwę")
    assert list_products(engine) == []


async def test_esc_closes_the_product_form_and_saves_nothing(user: User, engine: Engine) -> None:
    user.find(marker="tab-products").click()
    user.find(marker="add-product").click()
    user.find(marker="name").type("Cukier")
    _esc(user, "product-form")

    assert not _is_open(user, "product-form")
    assert list_products(engine) == []


async def test_enter_in_the_purchase_dialog_saves_and_esc_does_not(mleko: int, user: User, engine: Engine) -> None:
    user.find(marker="tab-products").click()
    user.find(marker="open-" + str(mleko)).click()
    user.find(marker="card-purchase").click()
    _esc(user, "purchase-dialog")
    assert not _is_open(user, "purchase-dialog")
    assert get_product(engine, mleko).quantity == 1

    user.find(marker="card-purchase").click()
    _enter(user, "purchase-dialog")
    assert not _is_open(user, "purchase-dialog")
    assert get_product(engine, mleko).quantity == 3


async def test_enter_in_the_purchase_dialog_keeps_a_validation_error_shown(
    mleko: int, user: User, engine: Engine
) -> None:
    user.find(marker="tab-products").click()
    user.find(marker="open-" + str(mleko)).click()
    user.find(marker="card-purchase").click()
    user.find(marker="purchase-expiry").type("jutro")
    _enter(user, "purchase-dialog")

    with user.scope(marker="purchase-dialog"):
        await user.should_see("DD.MM.RRRR")
    assert get_product(engine, mleko).quantity == 1


async def test_enter_in_a_field_of_the_product_card_does_that_fields_job(
    mleko: int, user: User, engine: Engine
) -> None:
    user.find(marker="tab-products").click()
    user.find(marker="open-" + str(mleko)).click()
    user.find(marker="card-use-quantity").trigger("keydown.enter")

    assert get_product(engine, mleko).quantity == 0


async def test_esc_closes_the_product_card(mleko: int, user: User) -> None:
    user.find(marker="tab-products").click()
    user.find(marker="open-" + str(mleko)).click()
    _esc(user, "product-card")

    assert not _is_open(user, "product-card")


async def test_enter_and_esc_in_the_unpacking_dialog(mleko: int, user: User, engine: Engine) -> None:
    user.find(marker="tab-shopping").click()
    user.find(marker="unpack").click()
    _esc(user, "unpacking-dialog")
    assert not _is_open(user, "unpacking-dialog")
    assert get_product(engine, mleko).quantity == 1

    user.find(marker="unpack").click()
    _enter(user, "unpacking-dialog")
    assert not _is_open(user, "unpacking-dialog")
    assert get_product(engine, mleko).quantity == 3


async def test_the_search_is_focused_when_produkty_opens_and_on_ctrl_f(user: User) -> None:
    [search] = user.find(marker="search", kind=ui.input).elements
    focused: list[str] = []
    original = search.run_method
    search.run_method = lambda name, *args, **kwargs: (  # type: ignore[method-assign, assignment]
        focused.append(name) if name == "focus" else original(name, *args, **kwargs)
    )
    assert focused == []

    user.find(marker="tab-products").click()
    await user.should_see(marker="search")
    assert focused == ["focus"]

    ctrl_f = KEY_F
    user.find(kind=ui.keyboard).trigger("key", ctrl_f)
    assert focused == ["focus", "focus"]


async def test_ctrl_f_leaves_the_other_tabs_alone(user: User) -> None:
    [search] = user.find(marker="search", kind=ui.input).elements
    focused: list[str] = []
    search.run_method = lambda name, *args, **kwargs: focused.append(name)  # type: ignore[method-assign, assignment]

    user.find(marker="tab-shopping").click()
    ctrl_f = KEY_F
    user.find(kind=ui.keyboard).trigger("key", ctrl_f)
    assert focused == []
