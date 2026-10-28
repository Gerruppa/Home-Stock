"""Made-up stock for ``--demo``: every Start section and the Shopping List have entries, dates relative to today."""

from datetime import date, timedelta
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, PackSize, ProductDraft
from home_stock.persistence.catalog import list_categories, list_units
from home_stock.persistence.products import add_product, archive_product, purchase


class DemoProduct(NamedTuple):
    name: str
    category: str
    unit: str
    pack_size: PackSize | None
    minimum_stock: int | None
    # (Quantity, days from today to the Expiry Date, or None for no Expiry Date)
    batches: list[tuple[int, int | None]]


PRODUCTS = [
    # Expiring Soon and Running Low
    DemoProduct("Mleko 2%", "Spożywcze", "sztuka", PackSize(Decimal(1), "l"), 2, [(1, 2)]),
    DemoProduct("Jogurt naturalny", "Spożywcze", "sztuka", None, 1, [(2, -2)]),  # Expired
    DemoProduct("Cukier", "Spożywcze", "opakowanie", PackSize(Decimal(1), "kg"), 1, [(2, None)]),
    DemoProduct("Sok pomarańczowy", "Napoje", "butelka", None, 1, [(3, 5)]),  # Expiring Soon
    DemoProduct("Woda mineralna", "Napoje", "butelka", None, 4, [(6, 180)]),
    DemoProduct("Płyn do naczyń", "Chemia i środki czystości", "butelka", None, 1, []),  # Running Low, at 0
    DemoProduct("Papier toaletowy", "Dom i inne", "rolka", None, 4, [(8, None)]),
    DemoProduct("Pasta do zębów", "Higiena i kosmetyki", "tubka", None, None, [(2, 400)]),  # without Minimum Stock
    DemoProduct("Paracetamol", "Apteczka", "opakowanie", None, 1, [(2, 200)]),
    DemoProduct("Karma dla kota", "Zwierzęta", "puszka", None, 3, [(4, 60), (2, 20)]),
]
ARCHIVED = DemoProduct("Kawa rozpuszczalna", "Spożywcze", "słoik", None, 1, [(1, 90)])


def seed_demo_data(engine: Engine, today: date) -> None:
    """Fill a fresh database (seeded Categories and Units only) with the demo Products."""
    categories = {category.name: category.id for category in list_categories(engine)}
    units = {unit.name: unit.id for unit in list_units(engine)}

    def add(demo: DemoProduct) -> int:
        draft = ProductDraft(demo.name, categories[demo.category], units[demo.unit], demo.pack_size, demo.minimum_stock)
        product_id = add_product(engine, draft)
        for quantity, days_to_expiry in demo.batches:
            expiry = None if days_to_expiry is None else today + timedelta(days=days_to_expiry)
            purchase(engine, product_id, BatchDraft(quantity, expiry))
        return product_id

    for demo in PRODUCTS:
        add(demo)
    archive_product(engine, add(ARCHIVED))
