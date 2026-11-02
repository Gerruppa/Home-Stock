from pathlib import Path

import pytest
from sqlalchemy import Engine

from home_stock.domain.stock import Category, ProductDraft, Unit, name_key
from home_stock.persistence.catalog import list_categories
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, archive_product
from home_stock.sources.starter_catalog import STARTER_CATALOG, available_starter_drafts, starter_drafts

SPOZYWCZE, SZTUKA = 1, 1


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


def test_every_starter_product_is_in_a_seeded_category_and_unit_with_a_unique_name(engine: Engine) -> None:
    drafts = available_starter_drafts(engine)

    assert len(drafts) == len(STARTER_CATALOG)
    assert len({name_key(draft.name) for draft in drafts}) == len(drafts)
    assert all(draft.minimum_stock is None for draft in drafts)


def test_starter_products_cover_every_seeded_category(engine: Engine) -> None:
    covered = {draft.category_id for draft in available_starter_drafts(engine)}

    assert covered == {category.id for category in list_categories(engine)}


def test_a_taken_name_active_or_archived_is_left_out(engine: Engine) -> None:
    add_product(engine, ProductDraft("MLEKO", SPOZYWCZE, SZTUKA))
    archive_product(engine, add_product(engine, ProductDraft("Cukier", SPOZYWCZE, SZTUKA)))

    names = [draft.name for draft in available_starter_drafts(engine)]

    assert "Mleko" not in names
    assert "Cukier" not in names
    assert len(names) == len(STARTER_CATALOG) - 2


def test_a_renamed_category_or_unit_leaves_its_products_out() -> None:
    categories = [Category(1, "Jedzenie", 3), Category(2, "napoje", 7)]
    units = [Unit(1, "Butelka", "but."), Unit(2, "sztuka", "szt.")]

    drafts = starter_drafts(categories, units, [])

    assert {draft.category_id for draft in drafts} == {2}
    assert {draft.unit_id for draft in drafts} == {1}
    assert [draft.name for draft in drafts] == ["Woda mineralna", "Napój gazowany"]
