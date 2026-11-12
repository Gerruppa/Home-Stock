"""Polish text for dates, counts and Pack Sizes, both ways: every value shown in or read from the UI goes here."""

import re
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal, InvalidOperation

from home_stock.domain.custom_lists import CustomList, ListLine
from home_stock.domain.history import StockEvent, StockEventKind, WasteLine
from home_stock.domain.stock import (
    BUFFER_ERROR,
    MAX_USUAL_SHELF_LIFE_DAYS,
    MEASURES,
    USUAL_SHELF_LIFE_ERROR,
    Category,
    ExpiryStatus,
    PackSize,
    Product,
    ShoppingListEntry,
    Unit,
    all_expired_on,
    check_buffer_days,
    expiry_status,
    use_order,
)

DATE_ERROR = "Podaj datę w formacie DD.MM.RRRR."
COUNT_ERROR = "Podaj liczbę całkowitą, np. 2."
PACK_SIZE_ERROR = "Podaj rozmiar opakowania, np. 1 kg albo 500 ml."

_DATE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
_PACK_SIZE = re.compile(r"(\d+(?:[.,]\d+)?)\s*([a-z]+)")


def _field_text(text: str | None) -> str:
    """A field's text, stripped; a cleared field holds None, which reads as blank."""
    return (text or "").strip()


def format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def parse_date(text: str | None) -> date | None:
    """A date typed as D.M.RRRR (leading zeros optional); None for a blank field."""
    text = _field_text(text)
    if not text:
        return None
    match = _DATE.fullmatch(text)
    if match is None:
        raise ValueError(DATE_ERROR)
    day, month, year = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        raise ValueError(DATE_ERROR) from None


def parse_count(text: str | None, *, allow_blank: bool = False) -> int | None:
    """A whole number of Units, zero allowed; None for a blank field when ``allow_blank``."""
    text = _field_text(text)
    if not text and allow_blank:
        return None
    if not text.isdigit():
        raise ValueError(COUNT_ERROR)
    return int(text)


def parse_usual_shelf_life(text: str | None) -> int | None:
    """A Usual Shelf Life: a whole number of days within ProductDraft's range; None for a blank field.

    Checks the range itself, so the form shows the error under this field rather than under the name."""
    text = _field_text(text)
    if not text:
        return None
    # isdigit alone takes "²", which int() refuses
    if not (text.isascii() and text.isdigit()) or not 1 <= int(text) <= MAX_USUAL_SHELF_LIFE_DAYS:
        raise ValueError(USUAL_SHELF_LIFE_ERROR)
    return int(text)


def format_days(days: int) -> str:
    """ "1 dzień", "7 dni": Polish takes "dni" for every number of days but one."""
    return f"{days} {'dzień' if days == 1 else 'dni'}"


def format_days_left(days: int) -> str:
    """ "wystarczy na ok. 12 dni": a Product's Days Left."""
    return f"wystarczy na ok. {format_days(days)}"


def parse_pack_size(text: str | None) -> PackSize | None:
    """ "1 kg", "0,5 l", "500g": an amount above zero and one of MEASURES; None for a blank field."""
    text = _field_text(text).lower()
    if not text:
        return None
    match = _PACK_SIZE.fullmatch(text)
    if match is None or match.group(2) not in MEASURES:
        raise ValueError(PACK_SIZE_ERROR)
    try:
        amount = Decimal(match.group(1).replace(",", "."))
    except InvalidOperation:
        raise ValueError(PACK_SIZE_ERROR) from None
    if amount <= 0:
        raise ValueError(PACK_SIZE_ERROR)
    return PackSize(amount, match.group(2))


def format_decimal(value: Decimal) -> str:
    """No trailing zeros and a decimal comma: 1.50 -> "1,5", 500 -> "500"."""
    text = format(value.normalize(), "f")
    return text.replace(".", ",")


def format_pack_size(size: PackSize) -> str:
    return f"{format_decimal(size.amount)} {size.measure}"


def format_quantity(quantity: int, unit: Unit, pack_size: PackSize | None) -> str:
    """ "2 opak. (2 kg)": the Quantity in Units, then what they hold together when the Product has a Pack Size."""
    text = f"{quantity} {unit.short}"
    if pack_size is None:
        return text
    return f"{text} ({format_pack_size(PackSize(pack_size.amount * quantity, pack_size.measure))})"


_EVENT_KINDS = {
    StockEventKind.USE: "Zużycie",
    StockEventKind.PURCHASE: "Zakup",
    StockEventKind.DISCARD: "Wyrzucenie",
    StockEventKind.CORRECTION: "Korekta",
}


def format_stock_event(event: StockEvent, unit: Unit) -> str:
    """ "02.11.2026 · Zużycie · −2 szt.": a line of the Stock History, the change signed."""
    return f"{format_date(event.on)} · {format_event_kind(event)} · {format_event_change(event, unit)}"


def format_event_kind(event: StockEvent) -> str:
    """ "Wyrzucenie (przeterminowane)": what the Stock Event was."""
    return _EVENT_KINDS[event.kind] + (" (przeterminowane)" if event.expired else "")


def format_event_change(event: StockEvent, unit: Unit) -> str:
    """ "−2 szt.": the Units the Stock Event added or took off, signed."""
    sign = "+" if event.change > 0 else "−"
    return f"{sign}{abs(event.change)} {unit.short}"


def format_waste(line: WasteLine, unit: Unit) -> str:
    """ "3 szt. (przeterminowane: 2)": the Units of a Product Discarded in a period, and how many were Expired."""
    return f"{line.units} {unit.short} (przeterminowane: {line.expired_units})"


def format_purchase_amount(count: int, unit: Unit) -> str:
    """ "kup 3 opak.": how much of the Product the Shopping List says to buy."""
    return f"kup {count} {unit.short}"


def format_shopping_list(
    categories: Sequence[Category],
    units: Mapping[int, Unit],
    products: Sequence[Product],
    amounts: Mapping[int, int],
) -> str:
    """The Shopping List as plain text: a heading per Category that has Products to buy, in the order given, each
    with its suggested Purchase from ``amounts`` by Product id."""
    sections = []
    for category in categories:
        lines = [
            f"{product.name} — {format_purchase_amount(amounts[product.id], units[product.unit_id])}"
            for product in products
            if product.category_id == category.id
        ]
        if lines:
            sections.append("\n".join([category.name, *lines]))
    return "\n\n".join(sections)


def format_custom_list_label(custom_list: CustomList) -> str:
    """ "Kolacja · 15.11", or the name alone without a date: a Custom List's chip on Zakupy."""
    return _named_with_occasion(custom_list, "%d.%m")


def format_custom_list_title(custom_list: CustomList) -> str:
    """ "Kolacja · 15.11.2026", or the name alone without a date: a Custom List's title and its text's first line."""
    return _named_with_occasion(custom_list, "%d.%m.%Y")


def _named_with_occasion(custom_list: CustomList, date_format: str) -> str:
    if custom_list.occasion is None:
        return custom_list.name
    return f"{custom_list.name} · {custom_list.occasion.strftime(date_format)}"


def format_custom_list(
    custom_list: CustomList, lines: Sequence[ListLine], products: Mapping[int, Product], units: Mapping[int, Unit]
) -> str:
    """A Custom List as plain text, what its "Kopiuj listę" copies and "Udostępnij" shares: the title, then each line
    to buy in the order given, a Product line as "Śmietana 30% — 2 szt.", a free-text line as written."""
    rows = [format_custom_list_title(custom_list)]
    for line in lines:
        if line.bought:
            continue
        if line.product_id is None:
            rows.append(line.text or "")
        else:
            product = products[line.product_id]
            assert line.quantity is not None, "a Product line has a Quantity"
            rows.append(f"{product.name} — {format_quantity(line.quantity, units[product.unit_id], None)}")
    return "\n".join(rows)


def format_at_home(product: Product, unit: Unit, today: date, warning_days: int, occasion: date | None) -> str:
    """ "w domu: 1 szt.", or "w domu: brak": how much of a Product on a Custom List is at home. The nearest Expiry
    Date follows when that Batch is Expiring Soon or Expired: "w domu: 1 szt. · ważne do 14.11", and "· przed okazją"
    when the list has an ``occasion`` and nothing at home lasts until it."""
    if not product.batches:
        return "w domu: brak"
    parts = [f"w domu: {format_quantity(product.quantity, unit, product.pack_size)}"]
    first = min(product.batches, key=use_order)
    if first.expiry is not None and expiry_status(first, today, warning_days) != ExpiryStatus.FRESH:
        parts.append(f"ważne do {first.expiry.strftime('%d.%m')}")
    if occasion is not None and all_expired_on(product, occasion):
        parts.append("przed okazją")
    return " · ".join(parts)


def format_shopping_reason(entry: ShoppingListEntry) -> str:
    """ "poniżej minimum" or "wystarczy na ok. 3 dni": why the Product is on the Shopping List."""
    return "poniżej minimum" if entry.days_left is None else format_days_left(entry.days_left)


def parse_buffer_days(text: str | None) -> int:
    """The Buffer: a whole number of days above zero."""
    text = _field_text(text)
    # isdigit alone takes "²", which int() refuses
    if not (text.isascii() and text.isdigit()):
        raise ValueError(BUFFER_ERROR)
    return check_buffer_days(int(text))
