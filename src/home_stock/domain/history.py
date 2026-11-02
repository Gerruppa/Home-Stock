"""The Stock History: what happened to a Product's stock, one Stock Event per change."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class StockEventKind(StrEnum):
    """Stored by value in the database, so a value never changes once released."""

    USE = "use"
    PURCHASE = "purchase"


@dataclass(frozen=True)
class StockEvent:
    id: int
    product_id: int
    kind: StockEventKind
    # Signed: a Use takes Units off, a Purchase adds them
    change: int
    on: date
    # Whether the Discarded Batch was Expired; False for every other kind
    expired: bool = False
