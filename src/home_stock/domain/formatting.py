"""Polish text for dates, counts and Pack Sizes, both ways: every value shown in or read from the UI goes here."""

import re
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal, InvalidOperation

from home_stock.domain.stock import (
    MAX_USUAL_SHELF_LIFE_DAYS,
    MEASURES,
    USUAL_SHELF_LIFE_ERROR,
    Category,
    PackSize,
    Product,
    Unit,
    suggested_purchase,
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


def format_purchase_amount(product: Product, unit: Unit) -> str:
    """ "kup 3 opak.": how much of the Product the Shopping List says to buy."""
    return f"kup {suggested_purchase(product)} {unit.short}"


def format_shopping_list(categories: Sequence[Category], units: Mapping[int, Unit], products: Sequence[Product]) -> str:
    """The Shopping List as plain text: a heading per Category that has Products to buy, in the order given."""
    sections = []
    for category in categories:
        lines = [
            f"{product.name} — {format_purchase_amount(product, units[product.unit_id])}"
            for product in products
            if product.category_id == category.id
        ]
        if lines:
            sections.append("\n".join([category.name, *lines]))
    return "\n\n".join(sections)
