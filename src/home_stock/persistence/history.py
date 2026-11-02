"""The Stock History: Stock Events are written by the functions in products.py that change Batches, in their own
transaction, and read here."""

from collections.abc import Collection, Sequence
from datetime import date

from sqlalchemy import ColumnElement, Connection, Engine, delete, insert, select, true

from home_stock.domain.history import StockEvent, StockEventKind
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
    """The latest Stock Events of all Products, or only of ``product_ids``, newest first."""
    where = true() if product_ids is None else StockEventRow.product_id.in_(product_ids)
    return _latest_events(engine, where, limit)


def _latest_events(engine: Engine, where: ColumnElement[bool], limit: int) -> list[StockEvent]:
    with engine.connect() as connection:
        rows = connection.execute(
            select(StockEventRow).where(where).order_by(StockEventRow.on.desc(), StockEventRow.id.desc()).limit(limit)
        )
        return [
            StockEvent(row.id, row.product_id, StockEventKind(row.kind), row.change, row.on, row.expired)
            for row in rows
        ]
