"""Products, Batches and the rules on them: Running Low, Running Out, the Shopping List, Expiry Status and which
Batches a Use takes (GLOSSARY.md)."""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
from fractions import Fraction

from home_stock.domain.history import days_left

# What a Pack Size may be measured in; never what a Quantity is counted in (ADR-0001)
MEASURES = ("g", "kg", "ml", "l")
# Ten years: longer than anything at home keeps, and short enough for any date it gives
MAX_USUAL_SHELF_LIFE_DAYS = 3650
USUAL_SHELF_LIFE_ERROR = f"Podaj liczbę dni od 1 do {MAX_USUAL_SHELF_LIFE_DAYS}, np. 7."
# How many days ahead the Shopping List looks for Products Running Out, until Ustawienia sets another
DEFAULT_BUFFER_DAYS = 7
BUFFER_ERROR = "Podaj liczbę dni większą od zera, np. 7."


@dataclass(frozen=True)
class Category:
    id: int
    name: str
    warning_days: int


@dataclass(frozen=True)
class Unit:
    id: int
    name: str
    # Written after a number: "2 opak."
    short: str


@dataclass(frozen=True)
class PackSize:
    amount: Decimal
    measure: str


@dataclass(frozen=True)
class Batch:
    id: int
    product_id: int
    quantity: int
    expiry: date | None


@dataclass(frozen=True)
class BatchDraft:
    quantity: int
    expiry: date | None = None

    def __post_init__(self) -> None:
        if self.quantity < 1:
            raise ValueError("Ilość musi być liczbą całkowitą większą od zera.")


@dataclass(frozen=True)
class ProductDraft:
    name: str
    category_id: int
    unit_id: int
    pack_size: PackSize | None = None
    minimum_stock: int | None = None
    # Usual Shelf Life in days
    usual_shelf_life_days: int | None = None

    def __post_init__(self) -> None:
        name = " ".join(self.name.split())
        if not name:
            raise ValueError("Podaj nazwę produktu.")
        if self.minimum_stock is not None and self.minimum_stock < 0:
            raise ValueError("Stan minimalny nie może być ujemny.")
        if self.usual_shelf_life_days is not None and not 1 <= self.usual_shelf_life_days <= MAX_USUAL_SHELF_LIFE_DAYS:
            raise ValueError(USUAL_SHELF_LIFE_ERROR)
        object.__setattr__(self, "name", name)


@dataclass(frozen=True)
class Product:
    id: int
    name: str
    category_id: int
    unit_id: int
    pack_size: PackSize | None
    minimum_stock: int | None
    archived: bool
    batches: tuple[Batch, ...]
    # Usual Shelf Life in days
    usual_shelf_life_days: int | None = None

    @property
    def quantity(self) -> int:
        return sum(batch.quantity for batch in self.batches)

    def draft(self) -> ProductDraft:
        """Its fields as a draft, to save with one of them changed."""
        return ProductDraft(
            self.name, self.category_id, self.unit_id, self.pack_size, self.minimum_stock, self.usual_shelf_life_days
        )


class ExpiryStatus(Enum):
    FRESH = "fresh"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"


def name_key(name: str) -> str:
    """The form two names are compared in: "  Mleko   2% " and "mleko 2%" are the same Product."""
    return " ".join(name.split()).casefold()


def is_running_low(product: Product) -> bool:
    return product.minimum_stock is not None and product.quantity <= product.minimum_stock


def is_expired(batch: Batch, today: date) -> bool:
    """Its Expiry Date has passed; a Batch expiring today is not yet Expired."""
    return batch.expiry is not None and batch.expiry < today


def expiry_status(batch: Batch, today: date, warning_days: int) -> ExpiryStatus | None:
    """None for a Batch without an Expiry Date; a Batch expiring today is still Expiring Soon, not Expired."""
    if batch.expiry is None:
        return None
    if is_expired(batch, today):
        return ExpiryStatus.EXPIRED
    if batch.expiry <= today + timedelta(days=warning_days):
        return ExpiryStatus.EXPIRING_SOON
    return ExpiryStatus.FRESH


def use_order(batch: Batch) -> tuple[bool, date, int]:
    """Sort key of the order Uses take Batches in: nearest Expiry Date first, undated last, older Batch first."""
    return (batch.expiry is None, batch.expiry or date.max, batch.id)


def units_to_use(batches: Sequence[Batch], count: int) -> list[tuple[Batch, int]]:
    """How many Units a Use of ``count`` takes off each Batch: in use_order, each emptied before the next."""
    taken: list[tuple[Batch, int]] = []
    for batch in sorted(batches, key=use_order):
        if count == 0:
            break
        units = min(count, batch.quantity)
        taken.append((batch, units))
        count -= units
    return taken


def default_expiry(usual_shelf_life_days: int | None, today: date) -> date | None:
    """The Expiry Date a new Batch starts with: today plus the Usual Shelf Life, None for a Product without one."""
    if usual_shelf_life_days is None:
        return None
    return today + timedelta(days=usual_shelf_life_days)


def suggested_minimum_stock(rate: Fraction, buffer_days: int) -> int:
    """The Units Used over the Buffer at the Consumption Rate, rounded up, at least 1."""
    return max(1, math.ceil(rate * buffer_days))


def suggested_purchase(product: Product, rate: Fraction | None, buffer_days: int) -> int:
    """How many Units a Purchase suggests, at least one: with a Consumption Rate, enough to cover the Buffer above
    Minimum Stock and to last past the Buffer, so the Product leaves the Shopping List; without one, enough to get one
    above Minimum Stock."""
    if rate is not None:
        covered = (product.minimum_stock or 0) + suggested_minimum_stock(rate, buffer_days)
        # Days Left rounds down, so lasting past the Buffer takes a whole day more of Units
        target = max(covered, math.ceil(rate * (buffer_days + 1)))
    elif product.minimum_stock is not None:
        target = product.minimum_stock + 1
    else:
        return 1
    return max(1, target - product.quantity)


@dataclass(frozen=True)
class ShoppingListEntry:
    product: Product
    # Set when the Product is on the list for Running Out rather than Running Low
    days_left: int | None = None


def check_buffer_days(days: int) -> int:
    """The Buffer if it is a whole number of days above zero; ValueError with the Polish message otherwise."""
    if days < 1:
        raise ValueError(BUFFER_ERROR)
    return days


def is_running_out(product: Product, rate: Fraction | None, buffer_days: int) -> bool:
    """Its Days Left is within the Buffer; a Product without a Consumption Rate never Runs Out."""
    return rate is not None and days_left(product.quantity, rate) <= buffer_days


def shopping_list(
    products: Sequence[Product], rates: Mapping[int, Fraction], buffer_days: int
) -> list[ShoppingListEntry]:
    """The Products Running Low or Running Out, in the order given; one both Running Low and Out is Running Low."""
    entries = []
    for product in products:
        rate = rates.get(product.id)
        if is_running_low(product):
            entries.append(ShoppingListEntry(product))
        elif rate is not None and is_running_out(product, rate, buffer_days):
            entries.append(ShoppingListEntry(product, days_left(product.quantity, rate)))
    return entries
