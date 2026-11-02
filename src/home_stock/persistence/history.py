"""The Stock History: Stock Events are written by the functions in products.py that change Batches, in their own
transaction, and read here."""

from collections.abc import Collection, Sequence
from datetime import date, timedelta
from fractions import Fraction

from sqlalchemy import ColumnElement, Connection, Engine, delete, func, insert, select, true

from home_stock.domain.history import RATE_WINDOW_DAYS, StockEvent, StockEventKind, consumption_rate
from home_stock.persistence.models import StockEventRow


def record_event(
    connection: Connection, product_id: int, kind: StockEventKind, change: int, on: date, *, expired: bool = False
) -> int:
    """Write one Stock Event inside the caller's transaction; returns its id. ``expired`` only for a Discard."""
    event_id: int = connection.execute(
        insert(StockEventRow)
        .values(product_id=product_id, kind=kind.value, change=change, on=on, expired=expired)
        .returning(StockEventRow.id)
    ).scalar_one()
    return event_id


def remove_events(connection: Connection, event_ids: Sequence[int]) -> None:
    """Remove the Stock Events of an action being undone, inside the undo's transaction."""
    connection.execute(delete(StockEventRow).where(StockEventRow.id.in_(event_ids)))


def list_product_events(engine: Engine, product_id: int, limit: int = 20) -> list[StockEvent]:
    """A Product's latest Stock Events, newest first."""
    return _latest_events(engine, StockEventRow.product_id == product_id, limit)


def list_latest_events(
    engine: Engine, limit: int = 200, product_ids: Collection[int] | None = None
) -> list[StockEvent]:
    """The latest Stock Events of all Products (the Historia tab shows the default 200), or only of ``product_ids``,
    newest first."""
    where = true() if product_ids is None else StockEventRow.product_id.in_(product_ids)
    return _latest_events(engine, where, limit)


def _latest_events(engine: Engine, where: ColumnElement[bool], limit: int | None) -> list[StockEvent]:
    with engine.connect() as connection:
        rows = connection.execute(
            select(StockEventRow).where(where).order_by(StockEventRow.on.desc(), StockEventRow.id.desc()).limit(limit)
        )
        return [
            StockEvent(row.id, row.product_id, StockEventKind(row.kind), row.change, row.on, row.expired)
            for row in rows
        ]


def list_events_since(engine: Engine, since: date) -> list[StockEvent]:
    """The Stock Events of all Products from ``since`` on, newest first."""
    return _latest_events(engine, StockEventRow.on >= since, None)


def consumption_rates(engine: Engine, today: date) -> dict[int, Fraction]:
    """The Consumption Rate of each Product that has one, by Product id."""
    events_by_product: dict[int, list[StockEvent]] = {}
    for event in list_events_since(engine, today - timedelta(days=RATE_WINDOW_DAYS)):
        events_by_product.setdefault(event.product_id, []).append(event)
    with engine.connect() as connection:
        first_events = connection.execute(
            select(StockEventRow.product_id, func.min(StockEventRow.on)).group_by(StockEventRow.product_id)
        ).all()
    rates = {}
    for product_id, first_event_on in first_events:
        rate = consumption_rate(events_by_product.get(product_id, []), first_event_on, today)
        if rate is not None:
            rates[product_id] = rate
    return rates
