"""Custom Lists and their List Lines: what the user writes by hand for an occasion, beside the Shopping List
(GLOSSARY.md, ADR-0006)."""

from dataclasses import dataclass
from datetime import date

from home_stock.domain.stock import name_key

QUANTITY_ERROR = "Ilość musi być liczbą całkowitą większą od zera."
NOTHING_TYPED = "Wpisz, co kupić."


@dataclass(frozen=True)
class CustomListDraft:
    name: str
    # The date of the occasion, which only labels and orders the list
    occasion: date | None = None

    def __post_init__(self) -> None:
        name = " ".join(self.name.split())
        if not name:
            raise ValueError("Podaj nazwę listy.")
        object.__setattr__(self, "name", name)


@dataclass(frozen=True)
class CustomList:
    id: int
    name: str
    occasion: date | None


def custom_list_order(custom_list: CustomList) -> tuple[bool, date, str]:
    """Sort key of the Custom Lists: by date of the occasion, undated last, then by name."""
    return custom_list.occasion is None, custom_list.occasion or date.max, name_key(custom_list.name)


@dataclass(frozen=True)
class ListLineDraft:
    """A Product with a Quantity, or free text: use product() or note()."""

    product_id: int | None
    quantity: int | None
    text: str | None

    @classmethod
    def product(cls, product_id: int, quantity: int) -> ListLineDraft:
        if quantity < 1:
            raise ValueError(QUANTITY_ERROR)
        return cls(product_id, quantity, None)

    @classmethod
    def note(cls, text: str) -> ListLineDraft:
        text = " ".join(text.split())
        if not text:
            raise ValueError(NOTHING_TYPED)
        return cls(None, None, text)


@dataclass(frozen=True)
class ListLine:
    id: int
    list_id: int
    # A Product line has product_id and quantity; a free-text line has text
    product_id: int | None
    quantity: int | None
    text: str | None
    bought: bool
