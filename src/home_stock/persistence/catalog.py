"""Categories and Units."""

from sqlalchemy import Connection, Engine, delete, insert, select, update
from sqlalchemy.orm import InstrumentedAttribute

from home_stock.domain.stock import Category, Unit, name_key
from home_stock.persistence.models import CategoryRow, ProductRow, UnitRow


class StockError(Exception):
    """A change the user asked for that cannot be saved; the message is the Polish text to show them."""


DUPLICATE_CATEGORY = "Kategoria o tej nazwie już istnieje."
DUPLICATE_UNIT = "Jednostka o tej nazwie już istnieje."
MISSING_NAME = "Podaj nazwę."


def list_categories(engine: Engine) -> list[Category]:
    """In the order they were created, so the seeded ones keep the spec's order."""
    with engine.connect() as connection:
        rows = connection.execute(select(CategoryRow).order_by(CategoryRow.id))
        return [Category(row.id, row.name, row.warning_days) for row in rows]


def add_category(engine: Engine, name: str, warning_days: int) -> int:
    """Save a new Category; returns its id."""
    name = _checked_category_name(name, warning_days)
    with engine.begin() as connection:
        _refuse_duplicate(connection, CategoryRow.id, CategoryRow.name, name, DUPLICATE_CATEGORY)
        category_id: int = connection.execute(
            insert(CategoryRow).values(name=name, warning_days=warning_days).returning(CategoryRow.id)
        ).scalar_one()
    return category_id


def update_category(engine: Engine, category_id: int, name: str, warning_days: int) -> None:
    """Keeping its own name, even in another case, is no duplicate."""
    name = _checked_category_name(name, warning_days)
    with engine.begin() as connection:
        _refuse_duplicate(
            connection, CategoryRow.id, CategoryRow.name, name, DUPLICATE_CATEGORY, other_than=category_id
        )
        connection.execute(
            update(CategoryRow).where(CategoryRow.id == category_id).values(name=name, warning_days=warning_days)
        )


def delete_category(engine: Engine, category_id: int) -> None:
    """Only a Category no Product uses, Archived ones included."""
    with engine.begin() as connection:
        if connection.execute(select(ProductRow.id).where(ProductRow.category_id == category_id)).first():
            raise StockError("Nie można usunąć kategorii, do której należą produkty.")
        connection.execute(delete(CategoryRow).where(CategoryRow.id == category_id))


def list_units(engine: Engine) -> list[Unit]:
    with engine.connect() as connection:
        rows = connection.execute(select(UnitRow).order_by(UnitRow.id))
        return [Unit(row.id, row.name, row.short) for row in rows]


def add_unit(engine: Engine, name: str, short: str) -> int:
    """Save a new Unit; returns its id."""
    name, short = _clean(name, MISSING_NAME), _clean(short, "Podaj skrót.")
    with engine.begin() as connection:
        _refuse_duplicate(connection, UnitRow.id, UnitRow.name, name, DUPLICATE_UNIT)
        unit_id: int = connection.execute(
            insert(UnitRow).values(name=name, short=short).returning(UnitRow.id)
        ).scalar_one()
    return unit_id


def update_unit(engine: Engine, unit_id: int, name: str, short: str) -> None:
    """Keeping its own name, even in another case, is no duplicate."""
    name, short = _clean(name, MISSING_NAME), _clean(short, "Podaj skrót.")
    with engine.begin() as connection:
        _refuse_duplicate(connection, UnitRow.id, UnitRow.name, name, DUPLICATE_UNIT, other_than=unit_id)
        connection.execute(update(UnitRow).where(UnitRow.id == unit_id).values(name=name, short=short))


def delete_unit(engine: Engine, unit_id: int) -> None:
    """Only a Unit no Product uses, Archived ones included."""
    with engine.begin() as connection:
        if connection.execute(select(ProductRow.id).where(ProductRow.unit_id == unit_id)).first():
            raise StockError("Nie można usunąć jednostki, której używają produkty.")
        connection.execute(delete(UnitRow).where(UnitRow.id == unit_id))


def _checked_category_name(name: str, warning_days: int) -> str:
    """The name cleaned, once the Category's fields are checked."""
    if warning_days < 0:
        raise StockError("Liczba dni nie może być ujemna.")
    return _clean(name, MISSING_NAME)


def _clean(text: str, blank_message: str) -> str:
    text = " ".join(text.split())
    if not text:
        raise StockError(blank_message)
    return text


def _refuse_duplicate(
    connection: Connection,
    id_column: InstrumentedAttribute[int],
    name_column: InstrumentedAttribute[str],
    name: str,
    message: str,
    *,
    other_than: int | None = None,
) -> None:
    """Names are compared by name_key, which SQL cannot do; the tables hold a handful of rows, so all are read."""
    for row_id, existing in connection.execute(select(id_column, name_column)):
        if row_id != other_than and name_key(existing) == name_key(name):
            raise StockError(message)
