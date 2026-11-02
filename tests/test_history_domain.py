"""Consumption Rate, Days Left and Waste, worked out from Stock Events."""

from datetime import date, timedelta
from fractions import Fraction

import pytest

from home_stock.domain.history import StockEvent, StockEventKind, WasteLine, consumption_rate, days_left, waste

TODAY = date(2026, 11, 2)


def _ago(days: int) -> date:
    return TODAY - timedelta(days=days)


def _event(kind: StockEventKind, change: int, days_ago: int) -> StockEvent:
    return StockEvent(0, 1, kind, change, _ago(days_ago))


def _uses(*units_and_days_ago: tuple[int, int]) -> list[StockEvent]:
    return [_event(StockEventKind.USE, -units, days_ago) for units, days_ago in units_and_days_ago]


def test_the_rate_is_the_units_used_per_day_since_the_first_event() -> None:
    uses = _uses((2, 20), (2, 10), (2, 1))

    assert consumption_rate(uses, _ago(30), TODAY) == Fraction(6, 30)


def test_fewer_than_three_uses_give_no_rate() -> None:
    assert consumption_rate(_uses((5, 20), (5, 10)), _ago(30), TODAY) is None


@pytest.mark.parametrize(("history_days", "has_rate"), [(13, False), (14, True)])
def test_under_fourteen_days_of_history_give_no_rate(history_days: int, has_rate: bool) -> None:
    uses = _uses((1, 10), (1, 5), (1, 0))

    assert (consumption_rate(uses, _ago(history_days), TODAY) is not None) is has_rate


def test_uses_older_than_ninety_days_are_ignored_and_the_window_is_ninety_days() -> None:
    # A Use exactly 90 days ago is outside: the 90 days counted end today
    uses = _uses((50, 120), (50, 90), (3, 60), (3, 30), (3, 0))

    assert consumption_rate(uses, _ago(200), TODAY) == Fraction(9, 90)


def test_uses_older_than_ninety_days_do_not_count_towards_the_three() -> None:
    assert consumption_rate(_uses((1, 100), (1, 30), (1, 10)), _ago(200), TODAY) is None


def test_purchases_discards_and_corrections_do_not_change_the_rate() -> None:
    others = [
        _event(StockEventKind.PURCHASE, 10, 25),
        _event(StockEventKind.DISCARD, -4, 15),
        _event(StockEventKind.CORRECTION, -3, 5),
        _event(StockEventKind.CORRECTION, 2, 4),
    ]
    uses = _uses((2, 20), (2, 10), (2, 1))

    assert consumption_rate(uses + others, _ago(30), TODAY) == Fraction(6, 30)
    assert consumption_rate(_uses((2, 20)) + others, _ago(30), TODAY) is None


@pytest.mark.parametrize(("quantity", "expected"), [(10, 50), (7, 35), (1, 5), (0, 0)])
def test_days_left_is_the_quantity_over_the_rate_rounded_down(quantity: int, expected: int) -> None:
    assert days_left(quantity, Fraction(6, 30)) == expected


def test_days_left_rounds_down() -> None:
    assert days_left(10, Fraction(3, 1)) == 3


def _discard(product_id: int, units: int, days_ago: int, *, expired: bool = False) -> StockEvent:
    return StockEvent(0, product_id, StockEventKind.DISCARD, -units, _ago(days_ago), expired)


def test_waste_sums_each_products_discarded_units_most_first_with_the_expired_ones() -> None:
    events = [
        _discard(1, 2, 3, expired=True),
        _discard(2, 5, 10),
        _discard(1, 1, 20),
        _discard(1, 4, 25, expired=True),
    ]

    assert waste(events, TODAY, 30) == [WasteLine(1, 7, 6), WasteLine(2, 5, 0)]


def test_waste_counts_only_discards_within_the_period() -> None:
    # A Discard exactly 30 days ago is outside: the 30 days counted end today
    events = [
        _discard(1, 3, 29),
        _discard(1, 9, 30),
        _event(StockEventKind.USE, -4, 5),
        _event(StockEventKind.PURCHASE, 6, 5),
        _event(StockEventKind.CORRECTION, -2, 5),
    ]

    assert waste(events, TODAY, 30) == [WasteLine(1, 3, 0)]
    assert waste(events, TODAY, 90) == [WasteLine(1, 12, 0)]
    assert waste([], TODAY, 30) == []
