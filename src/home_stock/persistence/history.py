"""The Stock History: Stock Events are written by the functions in products.py that change Batches, in their own
transaction, and read here."""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import Connection, Engine, delete, insert, select

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
    with engine.connect() as connection:
        rows = connection.execute(
            select(StockEventRow)
            .where(StockEventRow.product_id == product_id)
            .order_by(StockEventRow.on.desc(), StockEventRow.id.desc())
            .limit(limit)
        )
        return [
            StockEvent(row.id, row.product_id, StockEventKind(row.kind), row.change, row.on, row.expired)
            for row in rows
        ]
