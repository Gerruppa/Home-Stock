from datetime import date
from pathlib import Path

import pytest
from nicegui import ui
from nicegui.testing import User, user_simulation
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.catalog import list_categories, list_units
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, archive_product, get_product, list_products
from home_stock.ui.shell import build_shell

SPOZYWCZE, NAPOJE = 1, 2
SZTUKA, OPAKOWANIE = 1, 2
TODAY = date(2026, 10, 27)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


def _shell(engine: Engine) -> None:
    build_shell(engine, today=lambda: TODAY)


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


async def test_a_longer_warning_window_moves_a_batch_into_expiring_soon(engine: Engine) -> None:
    add_product(engine, ProductDraft("Szynka", SPOZYWCZE, SZTUKA), BatchDraft(1, date(2026, 10, 31)))

    async with user_simulation(lambda: _shell(engine)) as user:
        await user.open("/")
        await user.should_see("Wszystko w porządku.")
        user.find(marker="tab-settings").click()
        user.find(marker=f"category-days-{SPOZYWCZE}").clear().type("5")
        user.find(marker=f"category-save-{SPOZYWCZE}").click()

        user.find(marker="tab-start").click()
        with user.scope(marker="expiring"):
            await user.should_see("Szynka")
            await user.should_see("1 szt., termin 31.10.2026")


async def test_a_new_category_starts_with_seven_days_and_an_unused_one_can_be_deleted(engine: Engine) -> None:
    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_settings(user)
        await user.should_see(content="7", marker="category-new-days")
        user.find(marker="category-new-name").type("Ogród")
        user.find(marker="category-new-days").clear().type("14")
        user.find(marker="category-add").click()

        [ogrod] = [c for c in list_categories(engine) if c.name == "Ogród"]
        assert ogrod.warning_days == 14
        await user.should_see(content="Ogród", marker=f"category-name-{ogrod.id}")
        user.find(marker=f"category-delete-{ogrod.id}").click()
        await user.should_not_see(marker=f"category-row-{ogrod.id}")


async def test_a_category_a_product_uses_is_not_deleted(engine: Engine) -> None:
    add_product(engine, ProductDraft("Mleko", SPOZYWCZE, OPAKOWANIE))

    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_settings(user)
        user.find(marker=f"category-delete-{SPOZYWCZE}").click()
        await user.should_see(content="Nie można usunąć kategorii, do której należą produkty.", marker="category-error")
        await user.should_see(content="Spożywcze", marker=f"category-name-{SPOZYWCZE}")
    assert list_categories(engine)[0].name == "Spożywcze"


async def test_renaming_a_category_to_a_taken_name_in_another_case_is_refused(engine: Engine) -> None:
    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_settings(user)
        user.find(marker=f"category-name-{NAPOJE}").clear().type("SPOŻYWCZE")
        user.find(marker=f"category-save-{NAPOJE}").click()
        await user.should_see(content="Kategoria o tej nazwie już istnieje.", marker="category-error")
    assert list_categories(engine)[1].name == "Napoje"


async def test_a_new_unit_is_offered_in_the_product_form(engine: Engine) -> None:
    async with user_simulation(lambda: _shell(engine)) as user:
        await _open_settings(user)
        user.find(marker="unit-new-name").type("worek")
        user.find(marker="unit-new-short").type("wor.")
        user.find(marker="unit-add").click()
        await user.should_see(content="worek", marker=f"unit-name-{list_units(engine)[-1].id}")

        user.find(marker="tab-products").click()
        user.find(marker="add-product").click()
        unit = user.find(marker="unit", kind=ui.select).elements.pop()
        assert "worek" in unit.options.values()  # type: ignore[union-attr]
    assert list_units(engine)[-1].short == "wor."
