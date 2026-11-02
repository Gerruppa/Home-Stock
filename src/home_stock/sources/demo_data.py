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


class DemoUsualPurchase(NamedTuple):
    """The household's usual Purchase of a Product with Uses: its Quantity, and its Usual Shelf Life (None for a
    Product without dated stock)."""

    quantity: int
    shelf_life_days: int | None = None


class DemoUse(NamedTuple):
    """A Use in the Stock History."""

    used_days_ago: int
    quantity: int


class DemoPurchase(NamedTuple):
    """A Purchase in the Stock History; its Expiry Date ``shelf_life_days`` after it, or none."""

    bought_days_ago: int
    quantity: int
    shelf_life_days: int | None


class DemoProduct(NamedTuple):
    name: str
    category: str
    unit: str
    pack_size: PackSize | None
    minimum_stock: int | None
    # The stock today: (Quantity, days from today to the Expiry Date, or None for no Expiry Date)
    batches: list[tuple[int, int | None]]
    # A Use of ``units_per_use`` every this many days over the Stock History, the latest this many days ago; the stock
    # today is bought on that day, after it
    use_every: int | None = None
    units_per_use: int = 1
    usual_purchase: DemoUsualPurchase = DemoUsualPurchase(1)
    # Only for a Product without Uses, which would take the dated Batch first
    discards: tuple[DemoDiscard, ...] = ()


# The Stock History starts this many days ago with a Purchase
HISTORY_DAYS = 62
# When the stock today was bought, for a Product without Uses
BOUGHT_DAYS_AGO = 7

PRODUCTS = [
    # Expiring Soon and Running Low
    DemoProduct(
        "Mleko 2%",
        "Spożywcze",
        "sztuka",
        PackSize(Decimal(1), "l"),
        2,
        [(1, 2)],
        use_every=2,
        usual_purchase=DemoUsualPurchase(4, 10),
    ),
    # Expired today, and an Expired Discard in the Waste
    DemoProduct("Jogurt naturalny", "Spożywcze", "sztuka", None, 1, [(2, -2)], discards=(DemoDiscard(35, 3, -28, 25),)),
    DemoProduct(
        "Cukier",
        "Spożywcze",
        "opakowanie",
        PackSize(Decimal(1), "kg"),
        1,
        [(2, None)],
        use_every=15,
        usual_purchase=DemoUsualPurchase(2),
    ),
    # Expiring Soon, and a Discard before its Expiry Date
    DemoProduct("Sok pomarańczowy", "Napoje", "butelka", None, 1, [(3, 5)], discards=(DemoDiscard(20, 1, 10, 12),)),
    # Running Out within the Buffer (5 days) while above its Minimum Stock
    DemoProduct(
        "Woda mineralna",
        "Napoje",
        "butelka",
        None,
        4,
        [(5, 180)],
        use_every=2,
        units_per_use=2,
        usual_purchase=DemoUsualPurchase(6, 365),
    ),
    # Running Low, at 0; without Uses, which would show "wystarczy na ok. 0 dni"
    DemoProduct("Płyn do naczyń", "Chemia i środki czystości", "butelka", None, 1, []),
    DemoProduct(
        "Papier toaletowy",
        "Dom i inne",
        "rolka",
        None,
        4,
        [(8, None)],
        use_every=3,
        usual_purchase=DemoUsualPurchase(8),
    ),
    # Without Minimum Stock
    DemoProduct(
        "Pasta do zębów",
        "Higiena i kosmetyki",
        "tubka",
        None,
        None,
        [(2, 400)],
        use_every=20,
        usual_purchase=DemoUsualPurchase(2, 400),
    ),
    DemoProduct("Paracetamol", "Apteczka", "opakowanie", None, 1, [(2, 200)], discards=(DemoDiscard(60, 1, -5, 3),)),
    DemoProduct(
        "Karma dla kota",
        "Zwierzęta",
        "puszka",
        None,
        3,
        [(4, 60), (2, 20)],
        use_every=2,
        usual_purchase=DemoUsualPurchase(6, 365),
    ),
]
ARCHIVED = DemoProduct("Kawa rozpuszczalna", "Spożywcze", "słoik", None, 1, [(1, 90)])


def history_uses(demo: DemoProduct) -> list[DemoUse]:
    """The Product's Uses in the Stock History, oldest first."""
    if demo.use_every is None:
        return []
    return [DemoUse(days, demo.units_per_use) for days in reversed(range(demo.use_every, HISTORY_DAYS, demo.use_every))]


def history_purchases(demo: DemoProduct) -> list[DemoPurchase]:
    """The usual Purchases that stock the Product's Uses, oldest first: one on the day of the Use that would find too
    little, the first when the Stock History starts. They add up to exactly the Units the Uses take, so every Use takes
    only them and the stock today stays whole."""
    uses = history_uses(demo)
    usual = demo.usual_purchase
    to_use = sum(use.quantity for use in uses)
    on_hand = 0
    purchases: list[DemoPurchase] = []
    for use in uses:
        if on_hand < use.quantity:
            quantity = min(usual.quantity, to_use - on_hand)
            bought = use.used_days_ago if purchases else HISTORY_DAYS
            purchases.append(DemoPurchase(bought, quantity, usual.shelf_life_days))
            on_hand += quantity
        on_hand -= use.quantity
        to_use -= use.quantity
    return purchases


def seed_demo_data(engine: Engine, today: date) -> None:
    """Fill a fresh database (seeded Categories and Units only) with the demo Products and their Stock History."""
    categories = {category.name: category.id for category in list_categories(engine)}
    units = {unit.name: unit.id for unit in list_units(engine)}

    def days_ago(days: int) -> date:
        return today - timedelta(days=days)

    def add(demo: DemoProduct) -> int:
        draft = ProductDraft(demo.name, categories[demo.category], units[demo.unit], demo.pack_size, demo.minimum_stock)
        product_id = add_product(engine, draft)
        purchases = iter(history_purchases(demo))
        bought = next(purchases, None)
        for use in history_uses(demo):
            # A Purchase comes before the Use of its day
            while bought is not None and bought.bought_days_ago >= use.used_days_ago:
                shelf_life = bought.shelf_life_days
                expiry = None if shelf_life is None else days_ago(bought.bought_days_ago - shelf_life)
                purchase(engine, product_id, BatchDraft(bought.quantity, expiry), days_ago(bought.bought_days_ago))
                bought = next(purchases, None)
            use_units(engine, product_id, use.quantity, days_ago(use.used_days_ago))
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
