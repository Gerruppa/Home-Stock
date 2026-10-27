from datetime import date
from decimal import Decimal

import pytest

from home_stock.domain.formatting import (
    format_date,
    format_decimal,
    format_pack_size,
    format_quantity,
    parse_count,
    parse_date,
    parse_pack_size,
)
from home_stock.domain.stock import PackSize, Unit


def test_dates() -> None:
    assert format_date(date(2026, 10, 3)) == "03.10.2026"
    assert parse_date("3.10.2026") == date(2026, 10, 3)
    assert parse_date(" 30.10.2026 ") == date(2026, 10, 30)
    assert parse_date(" ") is None
    for bad in ("31.02.2026", "2026-10-30", "jutro"):
        with pytest.raises(ValueError, match="DD.MM.RRRR"):
            parse_date(bad)


def test_counts() -> None:
    assert parse_count(" 3 ") == 3
    assert parse_count("0") == 0
    assert parse_count("", allow_blank=True) is None
    for bad in ("1,5", "abc", "-1", ""):
        with pytest.raises(ValueError, match="liczbę całkowitą"):
            parse_count(bad)


def test_pack_sizes() -> None:
    assert parse_pack_size("0,5 l") == PackSize(Decimal("0.5"), "l")
    assert parse_pack_size("1.5 L") == PackSize(Decimal("1.5"), "l")
    assert parse_pack_size("500G") == PackSize(Decimal("500"), "g")
    assert parse_pack_size("") is None
    for bad in ("1 szklanka", "0 kg", "kg"):
        with pytest.raises(ValueError, match="rozmiar opakowania"):
            parse_pack_size(bad)


def test_format_decimal_and_pack_size() -> None:
    assert format_decimal(Decimal("1.50")) == "1,5"
    assert format_decimal(Decimal("2")) == "2"
    assert format_decimal(Decimal("500")) == "500"
    assert format_pack_size(PackSize(Decimal("0.5"), "l")) == "0,5 l"


def test_format_quantity() -> None:
    opak, but = Unit(1, "opakowanie", "opak."), Unit(2, "butelka", "but.")
    assert format_quantity(2, opak, PackSize(Decimal("1"), "kg")) == "2 opak. (2 kg)"
    assert format_quantity(3, but, PackSize(Decimal("0.5"), "l")) == "3 but. (1,5 l)"
    assert format_quantity(4, opak, None) == "4 opak."
