from pathlib import Path

import pytest
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.db import init_db
from home_stock.persistence.products import DuplicateProductError, add_product, list_products

SPOZYWCZE, CHEMIA = 1, 3
SZTUKA, OPAKOWANIE = 1, 2


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


def test_added_product_is_listed_with_its_first_batch(engine: Engine) -> None:
    add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(3))

    [cukier] = list_products(engine)
    assert (cukier.name, cukier.category_id, cukier.unit_id, cukier.quantity) == ("Cukier", SPOZYWCZE, OPAKOWANIE, 3)


def test_product_without_first_batch_is_at_zero(engine: Engine) -> None:
    add_product(engine, ProductDraft("Pieprz", SPOZYWCZE, SZTUKA))

    [pieprz] = list_products(engine)
    assert pieprz.quantity == 0
    assert pieprz.batches == ()


def test_a_name_that_exists_ignoring_case_and_spaces_is_refused(engine: Engine) -> None:
    add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE))

    with pytest.raises(DuplicateProductError, match="Produkt o tej nazwie już istnieje."):
        add_product(engine, ProductDraft("  CUKIER ", SPOZYWCZE, OPAKOWANIE), BatchDraft(2))
    [cukier] = list_products(engine)
    assert cukier.quantity == 0


def test_products_are_listed_by_name(engine: Engine) -> None:
    add_product(engine, ProductDraft("płyn do naczyń", CHEMIA, SZTUKA))
    add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE))
    add_product(engine, ProductDraft("Mąka", SPOZYWCZE, OPAKOWANIE))

    assert [p.name for p in list_products(engine)] == ["Cukier", "Mąka", "płyn do naczyń"]
