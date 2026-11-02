"""The Stock History: each action that changes Batches records its Stock Events, and its undo removes them."""

from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path

import pytest
from sqlalchemy import Engine

from home_stock.domain.history import StockEventKind
from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.db import init_db
from home_stock.persistence.history import consumption_rates, list_events_since, list_latest_events, list_product_events
from home_stock.persistence.products import (
    MissingBatchError,
    add_product,
    archive_product,
    discard_batch,
    edit_batch,
    get_product,
    purchase,
    purchase_many,
    restore_product,
    undo_discard,
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
    discard_batch(engine, unpacked.batches[1].id, MONDAY)

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


def _events_with_expired(engine: Engine, product_id: int) -> list[tuple[StockEventKind, int, bool]]:
    return [(event.kind, event.change, event.expired) for event in list_product_events(engine, product_id)]


def test_a_discard_records_the_batch_quantity_and_whether_it_was_expired(engine: Engine) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, OPAKOWANIE), BatchDraft(2, date(2026, 11, 1)))
    purchase(engine, mleko, BatchDraft(3, MONDAY), MONDAY)
    gone_off, fresh = get_product(engine, mleko).batches

    discard_batch(engine, gone_off.id, MONDAY)
    # A Batch expiring today is not yet Expired
    discard_batch(engine, fresh.id, MONDAY)

    assert _events_with_expired(engine, mleko) == [
        (StockEventKind.DISCARD, -3, False),
        (StockEventKind.DISCARD, -2, True),
        (StockEventKind.PURCHASE, 3, False),
    ]


def test_undoing_a_discard_puts_the_batch_back_and_removes_its_event(engine: Engine) -> None:
    cukier = _product(engine)
    before = get_product(engine, cukier)

    undo_discard(engine, discard_batch(engine, before.batches[0].id, MONDAY))

    assert get_product(engine, cukier) == before
    assert _events(engine, cukier) == []


@pytest.mark.parametrize(("quantity", "change"), [(8, 3), (2, -3), (0, -5)])
def test_editing_a_quantity_records_a_correction_with_the_difference(
    engine: Engine, quantity: int, change: int
) -> None:
    cukier = _product(engine)
    [batch] = get_product(engine, cukier).batches

    edit_batch(engine, batch.id, quantity, None, MONDAY)

    assert _events(engine, cukier) == [(StockEventKind.CORRECTION, change, MONDAY)]
    assert get_product(engine, cukier).quantity == quantity


def test_editing_only_the_expiry_date_records_nothing(engine: Engine) -> None:
    cukier = _product(engine)
    [batch] = get_product(engine, cukier).batches

    edit_batch(engine, batch.id, batch.quantity, date(2027, 1, 1), MONDAY)

    assert _events(engine, cukier) == []


def test_the_latest_events_of_all_products_come_newest_first_bounded(engine: Engine) -> None:
    cukier, maka = _product(engine), _product(engine, "Mąka")
    use_one(engine, cukier, TUESDAY)
    use_one(engine, maka, MONDAY)
    use_one(engine, cukier, MONDAY)

    events = list_latest_events(engine)

    assert [(event.product_id, event.on) for event in events] == [(cukier, TUESDAY), (cukier, MONDAY), (maka, MONDAY)]
    assert len(list_latest_events(engine, limit=2)) == 2


def test_the_latest_events_can_be_kept_to_some_products(engine: Engine) -> None:
    cukier, maka = _product(engine), _product(engine, "Mąka")
    use_one(engine, maka, MONDAY)
    for _ in range(3):
        use_one(engine, cukier, TUESDAY)

    # The limit counts only the chosen Products' events, so newer events of others never crowd them out
    assert [event.product_id for event in list_latest_events(engine, limit=1, product_ids=[maka])] == [maka]
    assert list_latest_events(engine, product_ids=[]) == []


def test_events_since_a_date_are_those_of_all_products_from_that_date_on(engine: Engine) -> None:
    cukier, maka = _product(engine), _product(engine, "Mąka")
    use_one(engine, cukier, date(2026, 11, 1))
    use_one(engine, cukier, MONDAY)
    use_one(engine, maka, TUESDAY)

    events = list_events_since(engine, MONDAY)

    assert sorted((event.product_id, event.on) for event in events) == [(cukier, MONDAY), (maka, TUESDAY)]


def test_consumption_rates_are_worked_out_for_products_with_enough_uses(engine: Engine) -> None:
    cukier, maka = _product(engine, quantity=20), _product(engine, "Mąka")
    purchase(engine, cukier, BatchDraft(1), MONDAY - timedelta(days=30))
    for days_ago in (20, 10, 1):
        use_units(engine, cukier, 2, MONDAY - timedelta(days=days_ago))
    use_one(engine, maka, MONDAY)

    assert consumption_rates(engine, MONDAY) == {cukier: Fraction(6, 30)}


def test_an_event_older_than_the_window_makes_the_rate_span_ninety_days(engine: Engine) -> None:
    cukier = _product(engine, quantity=20)
    purchase(engine, cukier, BatchDraft(1), MONDAY - timedelta(days=200))
    for days_ago in (20, 10, 1):
        use_units(engine, cukier, 3, MONDAY - timedelta(days=days_ago))

    assert consumption_rates(engine, MONDAY) == {cukier: Fraction(9, 90)}
