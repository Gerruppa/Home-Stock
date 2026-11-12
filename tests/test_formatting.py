from datetime import date
from decimal import Decimal

import pytest

from home_stock.domain.custom_lists import CustomList, ListLine
from home_stock.domain.formatting import (
    format_custom_list,
    format_custom_list_title,
    format_date,
    format_days,
    format_days_left,
    format_decimal,
    format_event_change,
    format_event_kind,
    format_pack_size,
    format_quantity,
    format_shopping_list,
    format_shopping_reason,
    format_stock_event,
    parse_buffer_days,
    parse_count,
    parse_date,
    parse_pack_size,
    parse_usual_shelf_life,
)
from home_stock.domain.history import StockEvent, StockEventKind
from home_stock.domain.stock import Category, PackSize, Product, ShoppingListEntry, Unit


def test_format_shopping_list() -> None:
    spozywcze, higiena, chemia = Category(1, "Spożywcze", 7), Category(4, "Higiena", 30), Category(5, "Chemia", 30)
    opak, rolka = Unit(2, "opakowanie", "opak."), Unit(3, "rolka", "rol.")
    units = {opak.id: opak, rolka.id: rolka}
    cukier = Product(1, "Cukier", 1, 2, None, 3, False, ())
    papier = Product(2, "Papier toaletowy", 4, 3, None, 4, False, ())
    mleko = Product(3, "Mleko", 1, 2, None, None, False, ())

    amounts = {cukier.id: 4, papier.id: 5, mleko.id: 1}

    text = format_shopping_list([higiena, spozywcze, chemia], units, [cukier, papier, mleko], amounts)

    assert text == "Higiena\nPapier toaletowy — kup 5 rol.\n\nSpożywcze\nCukier — kup 4 opak.\nMleko — kup 1 opak."
    assert format_shopping_list([spozywcze], units, [], {}) == ""


def test_format_custom_list_title_with_and_without_a_date() -> None:
    assert format_custom_list_title(CustomList(1, "Kolacja w sobotę", date(2026, 11, 15))) == (
        "Kolacja w sobotę · 15.11.2026"
    )
    assert format_custom_list_title(CustomList(1, "Grill", None)) == "Grill"


def test_format_custom_list_gives_the_lines_to_buy_in_order_under_the_title() -> None:
    kolacja = CustomList(1, "Kolacja w sobotę", date(2026, 11, 15))
    szt, opak = Unit(1, "sztuka", "szt."), Unit(2, "opakowanie", "opak.")
    smietana = Product(1, "Śmietana 30%", 1, szt.id, None, None, False, ())
    makaron = Product(2, "Makaron", 1, opak.id, None, None, False, ())
    lines = [
        ListLine(1, kolacja.id, smietana.id, 2, None, False),
        ListLine(2, kolacja.id, None, None, "świeczki", False),
        ListLine(3, kolacja.id, None, None, "kwiaty", True),
        ListLine(4, kolacja.id, makaron.id, 1, None, False),
    ]

    text = format_custom_list(kolacja, lines, {p.id: p for p in (smietana, makaron)}, {u.id: u for u in (szt, opak)})

    assert text == "Kolacja w sobotę · 15.11.2026\nŚmietana 30% — 2 szt.\nświeczki\nMakaron — 1 opak."
    grill = CustomList(2, "Grill", None)
    assert format_custom_list(grill, [ListLine(5, grill.id, None, None, "węgiel", False)], {}, {}) == "Grill\nwęgiel"


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


def test_usual_shelf_life_days() -> None:
    assert parse_usual_shelf_life(" 7 ") == 7
    assert parse_usual_shelf_life("") is None
    assert parse_usual_shelf_life("3650") == 3650
    for bad in ("0", "-3", "1,5", "tydzień", "3651", "²"):
        with pytest.raises(ValueError, match="liczbę dni od 1 do 3650"):
            parse_usual_shelf_life(bad)
    assert (format_days(1), format_days(2), format_days(14)) == ("1 dzień", "2 dni", "14 dni")


def test_format_days_left() -> None:
    assert format_days_left(1) == "wystarczy na ok. 1 dzień"
    assert format_days_left(55) == "wystarczy na ok. 55 dni"


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


def test_format_stock_event() -> None:
    szt = Unit(1, "sztuka", "szt.")
    use = StockEvent(1, 1, StockEventKind.USE, -2, date(2026, 11, 2))
    purchase = StockEvent(2, 1, StockEventKind.PURCHASE, 3, date(2026, 10, 27))

    assert format_stock_event(use, szt) == "02.11.2026 · Zużycie · −2 szt."
    assert format_stock_event(purchase, szt) == "27.10.2026 · Zakup · +3 szt."


def test_format_a_stock_events_kind_and_change_apart() -> None:
    szt = Unit(1, "sztuka", "szt.")
    gone_off = StockEvent(1, 1, StockEventKind.DISCARD, -2, date(2026, 11, 2), expired=True)

    assert format_event_kind(gone_off) == "Wyrzucenie (przeterminowane)"
    assert format_event_change(gone_off, szt) == "−2 szt."


def test_format_discard_and_correction_events() -> None:
    szt = Unit(1, "sztuka", "szt.")
    gone_off = StockEvent(1, 1, StockEventKind.DISCARD, -2, date(2026, 11, 2), expired=True)
    thrown = StockEvent(2, 1, StockEventKind.DISCARD, -1, date(2026, 11, 2))
    fixed = StockEvent(3, 1, StockEventKind.CORRECTION, 3, date(2026, 11, 2))

    assert format_stock_event(gone_off, szt) == "02.11.2026 · Wyrzucenie (przeterminowane) · −2 szt."
    assert format_stock_event(thrown, szt) == "02.11.2026 · Wyrzucenie · −1 szt."
    assert format_stock_event(fixed, szt) == "02.11.2026 · Korekta · +3 szt."


def test_format_shopping_reason() -> None:
    cukier = Product(1, "Cukier", 1, 1, None, 2, False, ())

    assert format_shopping_reason(ShoppingListEntry(cukier)) == "poniżej minimum"
    assert format_shopping_reason(ShoppingListEntry(cukier, days_left=3)) == "wystarczy na ok. 3 dni"


def test_parse_buffer_days() -> None:
    assert parse_buffer_days(" 14 ") == 14
    for bad in ("", "0", "-1", "1,5", "tydzień", "²"):
        with pytest.raises(ValueError, match="Podaj liczbę dni większą od zera"):
            parse_buffer_days(bad)
