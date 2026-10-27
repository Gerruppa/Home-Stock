"""Categories and Units."""

from sqlalchemy import Engine, select

from home_stock.domain.stock import Category, Unit
from home_stock.persistence.models import CategoryRow, UnitRow


def list_categories(engine: Engine) -> list[Category]:
    """In the order they were created, so the seeded ones keep the spec's order."""
    with engine.connect() as connection:
        rows = connection.execute(select(CategoryRow).order_by(CategoryRow.id))
        return [Category(row.id, row.name, row.warning_days) for row in rows]


def list_units(engine: Engine) -> list[Unit]:
    with engine.connect() as connection:
        rows = connection.execute(select(UnitRow).order_by(UnitRow.id))
        return [Unit(row.id, row.name, row.short) for row in rows]
