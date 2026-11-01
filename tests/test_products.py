from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.catalog import StockError
from home_stock.persistence.db import MIGRATIONS_DIR, init_db, open_engine
from home_stock.persistence.products import (
    DuplicateProductError,
    add_product,
    archive_product,
    discard_batch,
    edit_batch,
    get_product,
    list_products,
    purchase,
    restore_batch,
    restore_product,
    update_product,
    use_one,
    use_units,
)

SPOZYWCZE, CHEMIA = 1, 3
SZTUKA, OPAKOWANIE = 1, 2


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


def test_added_product_is_listed_with_its_first_batch(engine: Engine) -> None:
    add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(3))

    [cukier] = list_products(engine)
    assert (cukier.name, cukier.category_id, cukier.unit_id, cukier.quantity) == ("Cukier", SPOZYWCZE, OPAKOWANIE, 3)


def test_usual_shelf_life_is_saved_and_changed(engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA, usual_shelf_life_days=7))
    assert get_product(engine, mleko).usual_shelf_life_days == 7

    update_product(engine, mleko, ProductDraft("Mleko", SPOZYWCZE, SZTUKA))
    assert get_product(engine, mleko).usual_shelf_life_days is None


def test_products_from_before_usual_shelf_life_migrate_without_one(tmp_path: Path) -> None:
    engine = open_engine(tmp_path / "db.sqlite3")
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0002")
        connection.execute(
            text(
                "INSERT INTO products (name, name_key, category_id, unit_id, archived)"
                " VALUES ('Mleko', 'mleko', 1, 1, 0)"
            )
        )

    [mleko] = list_products(init_db(tmp_path / "db.sqlite3"))
    assert (mleko.name, mleko.usual_shelf_life_days) == ("Mleko", None)


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


def test_duplicate_reports_the_existing_product(engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA))

    with pytest.raises(DuplicateProductError) as raised:
        add_product(engine, ProductDraft(" mleko ", SPOZYWCZE, SZTUKA))
    assert (raised.value.product_id, raised.value.archived) == (mleko, False)


def test_editing_a_product_saves_its_fields_and_its_own_name_is_no_duplicate(engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA), BatchDraft(2))

    update_product(engine, mleko, ProductDraft("mleko", SPOZYWCZE, OPAKOWANIE, minimum_stock=5))

    [product] = list_products(engine)
    assert (product.name, product.unit_id, product.minimum_stock, product.quantity) == ("mleko", OPAKOWANIE, 5, 2)


def test_renaming_to_a_name_that_exists_is_refused(engine: Engine) -> None:
    add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA))
    kefir = add_product(engine, ProductDraft("Kefir", SPOZYWCZE, SZTUKA))

    with pytest.raises(DuplicateProductError, match="Produkt o tej nazwie już istnieje."):
        update_product(engine, kefir, ProductDraft("MLEKO", SPOZYWCZE, SZTUKA))
    assert get_product(engine, kefir).name == "Kefir"


def test_products_are_listed_by_name(engine: Engine) -> None:
    add_product(engine, ProductDraft("płyn do naczyń", CHEMIA, SZTUKA))
    add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE))
    add_product(engine, ProductDraft("Mąka", SPOZYWCZE, OPAKOWANIE))

    assert [p.name for p in list_products(engine)] == ["Cukier", "Mąka", "płyn do naczyń"]


def test_use_takes_one_unit_and_returns_the_batch_as_it_was(engine: Engine) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(2))

    before = use_one(engine, cukier)

    assert before is not None and before.quantity == 2
    assert get_product(engine, cukier).quantity == 1


def test_using_the_last_unit_removes_the_batch_and_keeps_the_product(engine: Engine) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(1))

    use_one(engine, cukier)

    [product] = list_products(engine)
    assert (product.name, product.quantity, product.batches) == ("Cukier", 0, ())


def test_use_on_a_product_at_zero_does_nothing(engine: Engine) -> None:
    pieprz = add_product(engine, ProductDraft("Pieprz", SPOZYWCZE, SZTUKA))

    assert use_one(engine, pieprz) is None
    assert get_product(engine, pieprz).quantity == 0


def test_restoring_undoes_a_use_exactly(engine: Engine) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(1))
    original = get_product(engine, cukier)

    before = use_one(engine, cukier)
    assert before is not None
    restore_batch(engine, before)

    assert get_product(engine, cukier) == original


def test_restoring_never_overwrites_a_batch_that_reused_the_id(engine: Engine) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(1))
    before = use_one(engine, cukier)
    assert before is not None
    # SQLite gives the next Batch the id of the one the Use removed
    maka = add_product(engine, ProductDraft("Mąka", SPOZYWCZE, OPAKOWANIE), BatchDraft(5))

    restore_batch(engine, before)

    assert get_product(engine, maka).quantity == 5
    assert get_product(engine, cukier).quantity == 1


def test_uses_take_the_nearest_expiry_first(engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA), BatchDraft(3, date(2026, 11, 12)))
    purchase(engine, mleko, BatchDraft(2, date(2026, 10, 30)))

    use_one(engine, mleko)
    second = use_one(engine, mleko)

    assert second is not None and (second.quantity, second.expiry) == (1, date(2026, 10, 30))
    [batch] = get_product(engine, mleko).batches
    assert (batch.quantity, batch.expiry) == (3, date(2026, 11, 12))


def test_using_several_units_empties_the_nearest_expiry_first(engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA), BatchDraft(5, date(2026, 11, 12)))
    purchase(engine, mleko, BatchDraft(2, date(2026, 10, 30)))

    use_units(engine, mleko, 3)

    [batch] = get_product(engine, mleko).batches
    assert (batch.quantity, batch.expiry) == (4, date(2026, 11, 12))


def test_using_several_units_takes_undated_batches_last(engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA), BatchDraft(2))
    purchase(engine, mleko, BatchDraft(2, date(2026, 11, 12)))

    use_units(engine, mleko, 3)

    [batch] = get_product(engine, mleko).batches
    assert (batch.quantity, batch.expiry) == (1, None)


@pytest.mark.parametrize(("count", "message"), [(8, "Na stanie jest tylko 7."), (0, "Podaj co najmniej 1.")])
def test_using_more_than_the_quantity_or_none_is_refused_and_changes_nothing(
    engine: Engine, count: int, message: str
) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA), BatchDraft(5, date(2026, 11, 12)))
    purchase(engine, mleko, BatchDraft(2, date(2026, 10, 30)))
    original = get_product(engine, mleko)

    with pytest.raises(StockError, match=message):
        use_units(engine, mleko, count)
    assert get_product(engine, mleko) == original


def test_restoring_every_batch_a_use_touched_undoes_it_exactly(engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA), BatchDraft(5, date(2026, 11, 12)))
    purchase(engine, mleko, BatchDraft(2, date(2026, 10, 30)))
    original = get_product(engine, mleko)

    before = use_units(engine, mleko, 3)
    for batch in before:
        restore_batch(engine, batch)

    assert get_product(engine, mleko) == original


def test_purchase_adds_a_batch(engine: Engine) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(1))

    purchase(engine, cukier, BatchDraft(2, date(2027, 3, 1)))

    product = get_product(engine, cukier)
    assert product.quantity == 3
    assert date(2027, 3, 1) in [batch.expiry for batch in product.batches]


def test_editing_a_batch_changes_its_quantity_and_expiry(engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA), BatchDraft(2, date(2026, 10, 30)))
    [batch] = get_product(engine, mleko).batches

    edit_batch(engine, batch.id, 4, None)

    [edited] = get_product(engine, mleko).batches
    assert (edited.id, edited.quantity, edited.expiry) == (batch.id, 4, None)


def test_editing_a_batch_to_zero_removes_it_and_keeps_the_product(engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA), BatchDraft(2, date(2026, 10, 30)))
    [batch] = get_product(engine, mleko).batches

    edit_batch(engine, batch.id, 0, batch.expiry)

    [product] = list_products(engine)
    assert (product.name, product.quantity, product.batches) == ("Mleko", 0, ())


def test_editing_a_batch_to_a_negative_quantity_is_refused(engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA), BatchDraft(2))
    [batch] = get_product(engine, mleko).batches

    with pytest.raises(StockError, match="Ilość nie może być ujemna."):
        edit_batch(engine, batch.id, -1, None)
    assert get_product(engine, mleko).quantity == 2


def test_restoring_undoes_a_discard_exactly(engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA), BatchDraft(2, date(2026, 10, 30)))
    purchase(engine, mleko, BatchDraft(3, date(2026, 11, 12)))
    original = get_product(engine, mleko)

    discarded = discard_batch(engine, original.batches[0].id)
    assert get_product(engine, mleko).quantity == 3
    restore_batch(engine, discarded)

    assert get_product(engine, mleko) == original


def test_a_batch_already_gone_cannot_be_edited_or_discarded(engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA), BatchDraft(2))
    [batch] = get_product(engine, mleko).batches
    discard_batch(engine, batch.id)

    with pytest.raises(StockError, match="Tej partii już nie ma."):
        discard_batch(engine, batch.id)
    with pytest.raises(StockError, match="Tej partii już nie ma."):
        edit_batch(engine, batch.id, 3, None)


def test_archiving_hides_a_product_and_restoring_brings_it_back_with_its_settings(engine: Engine) -> None:
    mleko = add_product(
        engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA, minimum_stock=2), BatchDraft(3, date(2026, 11, 12))
    )
    original = get_product(engine, mleko)

    archive_product(engine, mleko)

    assert list_products(engine) == []
    [archived] = list_products(engine, archived=True)
    assert (archived.id, archived.archived) == (mleko, True)

    restore_product(engine, mleko)

    assert list_products(engine) == [original]
    assert list_products(engine, archived=True) == []


def test_an_archived_name_is_still_taken(engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA))
    archive_product(engine, mleko)

    with pytest.raises(DuplicateProductError) as raised:
        add_product(engine, ProductDraft("mleko", SPOZYWCZE, SZTUKA))
    assert (raised.value.product_id, raised.value.archived) == (mleko, True)
