from datetime import date
from decimal import Decimal

import pytest

from home_stock.domain.formatting import (
    format_date,
    format_days,
    format_decimal,
    format_pack_size,
    format_quantity,
    parse_count,
    parse_date,
    parse_pack_size,
    parse_shelf_life,
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


def test_shelf_life_days() -> None:
    assert parse_shelf_life(" 7 ") == 7
    assert parse_shelf_life("") is None
    for bad in ("0", "-3", "1,5", "tydzień"):
        with pytest.raises(ValueError, match="liczbę dni większą od zera"):
            parse_shelf_life(bad)
    assert (format_days(1), format_days(2), format_days(14)) == ("1 dzień", "2 dni", "14 dni")


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


def test_a_cleared_field_reads_as_blank() -> None:
    # NiceGUI gives a cleared input the value None
    assert parse_date(None) is None
    assert parse_count(None, allow_blank=True) is None
    assert parse_pack_size(None) is None
    with pytest.raises(ValueError, match="liczbę całkowitą"):
        parse_count(None)
