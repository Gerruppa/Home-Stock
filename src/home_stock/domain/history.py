"""The Stock History: what happened to a Product's stock, one Stock Event per change, and the Consumption Rate,
Days Left and Waste worked out from it."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from fractions import Fraction


class StockEventKind(StrEnum):
    """Stored by value in the database, so a value never changes once released."""

    USE = "use"
    PURCHASE = "purchase"
    DISCARD = "discard"
    # A hand edit of a Batch's Quantity, by the difference
    CORRECTION = "correction"


@dataclass(frozen=True)
class StockEvent:
    id: int
    product_id: int
    kind: StockEventKind
    # Signed: a Use or Discard takes Units off, a Purchase adds them, a Correction either
    change: int
    on: date
    # Whether the Discarded Batch was Expired; False for every other kind
    expired: bool = False


# The Consumption Rate looks only this far back, so a change in habits shows within a season
RATE_WINDOW_DAYS = 90
# Below these there is no Consumption Rate: too few Uses, or too short a history, to forecast from
MIN_RATE_USES = 3
MIN_RATE_HISTORY_DAYS = 14


def consumption_rate(events: Sequence[StockEvent], first_event_on: date, today: date) -> Fraction | None:
    """Units Used per day: the Uses of the last 90 days over the days since the later of the Product's first Stock
    Event (``first_event_on``) and 90 days ago. Purchases, Discards and Corrections never count. None without enough
    Uses or history."""
    window_start = today - timedelta(days=RATE_WINDOW_DAYS)
    uses = [event for event in events if event.kind is StockEventKind.USE and event.on > window_start]
    history_days = (today - max(first_event_on, window_start)).days
    if len(uses) < MIN_RATE_USES or history_days < MIN_RATE_HISTORY_DAYS:
        return None
    return Fraction(-sum(event.change for event in uses), history_days)


def days_left(quantity: int, rate: Fraction) -> int:
    """How many days the Quantity lasts at the Consumption Rate, rounded down."""
    return math.floor(quantity / rate)


# The periods Historia sums Waste over, each ending today like the Consumption Rate's window
WASTE_PERIODS_DAYS = (30, 90)


@dataclass(frozen=True)
class WasteLine:
    product_id: int
    # Units Discarded in the period, and how many of them were in Expired Batches
    units: int
    expired_units: int


def waste(events: Sequence[StockEvent], today: date, days: int) -> list[WasteLine]:
    """Waste: the Units each Product had Discarded in the last ``days`` days, most first (ties by Product id), with
    how many were Expired. Uses, Purchases and Corrections never count."""
    period_start = today - timedelta(days=days)
    # Product id → [Units, Expired Units]
    totals: dict[int, list[int]] = {}
    for event in events:
        if event.kind is StockEventKind.DISCARD and event.on > period_start:
            total = totals.setdefault(event.product_id, [0, 0])
            total[0] -= event.change
            if event.expired:
                total[1] -= event.change
    lines = [WasteLine(product_id, units, expired) for product_id, (units, expired) in totals.items()]
    return sorted(lines, key=lambda line: (-line.units, line.product_id))
