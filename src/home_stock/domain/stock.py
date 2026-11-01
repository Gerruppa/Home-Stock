"""Products, Batches and the rules on them: Running Low, Expiry Status and which Batches a Use takes (GLOSSARY.md)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum

# What a Pack Size may be measured in; never what a Quantity is counted in (ADR-0001)
MEASURES = ("g", "kg", "ml", "l")
# Ten years: longer than anything at home keeps, and short enough for any date it gives
MAX_USUAL_SHELF_LIFE_DAYS = 3650
USUAL_SHELF_LIFE_ERROR = f"Podaj liczbę dni od 1 do {MAX_USUAL_SHELF_LIFE_DAYS}, np. 7."


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


class ExpiryStatus(Enum):
    FRESH = "fresh"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"


def name_key(name: str) -> str:
    """The form two names are compared in: "  Mleko   2% " and "mleko 2%" are the same Product."""
    return " ".join(name.split()).casefold()


def is_running_low(product: Product) -> bool:
    return product.minimum_stock is not None and product.quantity <= product.minimum_stock


def expiry_status(batch: Batch, today: date, warning_days: int) -> ExpiryStatus | None:
    """None for a Batch without an Expiry Date; a Batch expiring today is still Expiring Soon, not Expired."""
    if batch.expiry is None:
        return None
    if batch.expiry < today:
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


def suggested_purchase(product: Product) -> int:
    """How many Units a Purchase suggests: enough to get one above Minimum Stock, at least one."""
    if product.minimum_stock is None:
        return 1
    return max(1, product.minimum_stock + 1 - product.quantity)
