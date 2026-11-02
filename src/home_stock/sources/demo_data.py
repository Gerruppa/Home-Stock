"""Made-up stock for ``--demo``: every Start section and the Shopping List have entries, and about two months of Stock
History give forecasts and Waste; dates relative to today."""

from datetime import date, timedelta
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, PackSize, ProductDraft
from home_stock.persistence.catalog import list_categories, list_units
from home_stock.persistence.products import add_product, archive_product, discard_batch, purchase, use_units


class DemoDiscard(NamedTuple):
    """A Batch bought and Discarded in the Stock History; days counted back from today, the Expiry Date forward."""

    bought_days_ago: int
    quantity: int
    days_to_expiry: int
    discarded_days_ago: int


class DemoProduct(NamedTuple):
    name: str
    category: str
    unit: str
    pack_size: PackSize | None
    minimum_stock: int | None
    # The stock today: (Quantity, days from today to the Expiry Date, or None for no Expiry Date)
    batches: list[tuple[int, int | None]]
    # A Use of one Unit every this many days over the Stock History, the latest this many days ago; the stock today is
    # bought on that day, after it
    use_every: int | None = None
    # Only for a Product without Uses, which would take the dated Batch first
    discards: tuple[DemoDiscard, ...] = ()


# The Stock History starts this many days ago with a Purchase, and is restocked halfway, for the Units its Uses take
HISTORY_DAYS = 62
RESTOCK_DAYS_AGO = 31
# When the stock today was bought, for a Product without Uses
BOUGHT_DAYS_AGO = 7

PRODUCTS = [
    # Expiring Soon and Running Low
    DemoProduct("Mleko 2%", "Spożywcze", "sztuka", PackSize(Decimal(1), "l"), 2, [(1, 2)], use_every=2),
    # Expired today, and an Expired Discard in the Waste
    DemoProduct("Jogurt naturalny", "Spożywcze", "sztuka", None, 1, [(2, -2)], discards=(DemoDiscard(35, 3, -28, 25),)),
    DemoProduct("Cukier", "Spożywcze", "opakowanie", PackSize(Decimal(1), "kg"), 1, [(2, None)], use_every=15),
    # Expiring Soon, and a Discard before its Expiry Date
    DemoProduct("Sok pomarańczowy", "Napoje", "butelka", None, 1, [(3, 5)], discards=(DemoDiscard(20, 1, 10, 12),)),
    # Running Out within the Buffer (5 days) while above its Minimum Stock
    DemoProduct("Woda mineralna", "Napoje", "butelka", None, 4, [(5, 180)], use_every=1),
    # Running Low, at 0; without Uses, which would show "wystarczy na ok. 0 dni"
    DemoProduct("Płyn do naczyń", "Chemia i środki czystości", "butelka", None, 1, []),
    DemoProduct("Papier toaletowy", "Dom i inne", "rolka", None, 4, [(8, None)], use_every=3),
    # Without Minimum Stock
    DemoProduct("Pasta do zębów", "Higiena i kosmetyki", "tubka", None, None, [(2, 400)], use_every=20),
    DemoProduct("Paracetamol", "Apteczka", "opakowanie", None, 1, [(2, 200)], discards=(DemoDiscard(60, 1, -5, 3),)),
    DemoProduct("Karma dla kota", "Zwierzęta", "puszka", None, 3, [(4, 60), (2, 20)], use_every=2),
]
ARCHIVED = DemoProduct("Kawa rozpuszczalna", "Spożywcze", "słoik", None, 1, [(1, 90)])


def seed_demo_data(engine: Engine, today: date) -> None:
    """Fill a fresh database (seeded Categories and Units only) with the demo Products and their Stock History."""
    categories = {category.name: category.id for category in list_categories(engine)}
    units = {unit.name: unit.id for unit in list_units(engine)}

    def days_ago(days: int) -> date:
        return today - timedelta(days=days)

    def add(demo: DemoProduct) -> int:
        draft = ProductDraft(demo.name, categories[demo.category], units[demo.unit], demo.pack_size, demo.minimum_stock)
        product_id = add_product(engine, draft)
        if demo.use_every is not None:
            use_days = range(demo.use_every, HISTORY_DAYS, demo.use_every)
            # Exactly the Units the Uses take, all used up before the stock today is bought
            before_restock = sum(days > RESTOCK_DAYS_AGO for days in use_days)
            for bought, units_bought in (
                (HISTORY_DAYS, before_restock),
                (RESTOCK_DAYS_AGO, len(use_days) - before_restock),
            ):
                if units_bought:
                    purchase(engine, product_id, BatchDraft(units_bought), days_ago(bought))
            for days in reversed(use_days):
                use_units(engine, product_id, 1, days_ago(days))
        for discard in demo.discards:
            thrown = BatchDraft(discard.quantity, days_ago(-discard.days_to_expiry))
            [batch] = purchase(engine, product_id, thrown, days_ago(discard.bought_days_ago)).batches
            discard_batch(engine, batch.id, days_ago(discard.discarded_days_ago))
        for quantity, days_to_expiry in demo.batches:
            expiry = None if days_to_expiry is None else today + timedelta(days=days_to_expiry)
            purchase(engine, product_id, BatchDraft(quantity, expiry), days_ago(demo.use_every or BOUGHT_DAYS_AGO))
        return product_id

    for demo in PRODUCTS:
        add(demo)
    archive_product(engine, add(ARCHIVED))
