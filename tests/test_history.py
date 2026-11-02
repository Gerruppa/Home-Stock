"""The Stock History: each action that changes Batches records its Stock Events, and its undo removes them."""

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import Engine

from home_stock.domain.history import StockEventKind
from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.db import init_db
from home_stock.persistence.history import list_product_events
from home_stock.persistence.products import (
    MissingBatchError,
    add_product,
    archive_product,
    discard_batch,
    get_product,
    purchase,
    purchase_many,
    restore_product,
    undo_purchase,
    undo_use,
    use_one,
    use_units,
)

SPOZYWCZE, OPAKOWANIE = 1, 2
MONDAY, TUESDAY = date(2026, 11, 2), date(2026, 11, 3)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


def _product(engine: Engine, name: str = "Cukier", quantity: int = 5) -> int:
    return add_product(engine, ProductDraft(name, SPOZYWCZE, OPAKOWANIE), BatchDraft(quantity))


def _events(engine: Engine, product_id: int) -> list[tuple[StockEventKind, int, date]]:
    return [(event.kind, event.change, event.on) for event in list_product_events(engine, product_id)]


def test_a_new_product_starts_with_no_history(engine: Engine) -> None:
    cukier = _product(engine)

    assert _events(engine, cukier) == []


def test_a_use_records_the_units_taken_on_its_date(engine: Engine) -> None:
    cukier = _product(engine)

    use_one(engine, cukier, MONDAY)
    use_units(engine, cukier, 3, TUESDAY)

    assert _events(engine, cukier) == [(StockEventKind.USE, -3, TUESDAY), (StockEventKind.USE, -1, MONDAY)]


def test_a_use_of_a_product_at_zero_records_nothing(engine: Engine) -> None:
    pieprz = add_product(engine, ProductDraft("Pieprz", SPOZYWCZE, OPAKOWANIE))

    assert use_one(engine, pieprz, MONDAY) is None
    assert _events(engine, pieprz) == []


def test_a_purchase_records_its_quantity(engine: Engine) -> None:
    cukier = _product(engine)

    purchase(engine, cukier, BatchDraft(2), MONDAY)

    assert _events(engine, cukier) == [(StockEventKind.PURCHASE, 2, MONDAY)]


def test_an_unpacking_records_a_purchase_per_batch(engine: Engine) -> None:
    cukier = _product(engine)
    maka = _product(engine, "Mąka")

    purchase_many(engine, [(cukier, BatchDraft(2)), (maka, BatchDraft(3))], MONDAY)

    assert _events(engine, cukier) == [(StockEventKind.PURCHASE, 2, MONDAY)]
    assert _events(engine, maka) == [(StockEventKind.PURCHASE, 3, MONDAY)]


def test_undoing_a_use_puts_the_batches_back_and_removes_only_its_event(engine: Engine) -> None:
    cukier = _product(engine)
    use_one(engine, cukier, MONDAY)
    before = get_product(engine, cukier)

    used = use_units(engine, cukier, 2, TUESDAY)
    undo_use(engine, used)

    assert get_product(engine, cukier) == before
    assert _events(engine, cukier) == [(StockEventKind.USE, -1, MONDAY)]


def test_undoing_a_purchase_removes_its_batch_and_its_event(engine: Engine) -> None:
    cukier = _product(engine)
    before = get_product(engine, cukier)

    undo_purchase(engine, purchase(engine, cukier, BatchDraft(2), MONDAY))

    assert get_product(engine, cukier) == before
    assert _events(engine, cukier) == []


def test_undoing_an_unpacking_removes_every_batch_and_event_or_none(engine: Engine) -> None:
    cukier = _product(engine)
    maka = _product(engine, "Mąka")
    unpacked = purchase_many(engine, [(cukier, BatchDraft(2)), (maka, BatchDraft(3))], MONDAY)
    discard_batch(engine, unpacked.batches[1].id)

    with pytest.raises(MissingBatchError):
        undo_purchase(engine, unpacked)
    assert _events(engine, cukier) == [(StockEventKind.PURCHASE, 2, MONDAY)]
    assert get_product(engine, cukier).quantity == 7


def test_an_archived_product_keeps_its_events(engine: Engine) -> None:
    cukier = _product(engine)
    use_one(engine, cukier, MONDAY)

    archive_product(engine, cukier)
    restore_product(engine, cukier)

    assert _events(engine, cukier) == [(StockEventKind.USE, -1, MONDAY)]


def test_the_latest_events_come_first_and_the_list_is_bounded(engine: Engine) -> None:
    cukier = _product(engine, quantity=30)
    for _ in range(25):
        use_one(engine, cukier, MONDAY)

    events = list_product_events(engine, cukier, limit=20)

    assert len(events) == 20
    assert [event.id for event in events] == sorted((event.id for event in events), reverse=True)
