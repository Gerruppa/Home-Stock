"""Products and their Batches."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import ColumnElement, Connection, Engine, delete, insert, select, update

from home_stock.domain.formatting import format_shopping_list
from home_stock.domain.history import StockEventKind
from home_stock.domain.stock import (
    Batch,
    BatchDraft,
    PackSize,
    Product,
    ProductDraft,
    ShoppingListEntry,
    is_expired,
    name_key,
    shopping_list,
    suggested_purchase,
    units_to_use,
    use_order,
)
from home_stock.persistence.catalog import StockError, list_categories, list_units
from home_stock.persistence.history import consumption_rates, record_event, remove_events
from home_stock.persistence.models import BatchRow, ProductRow, StockEventRow
from home_stock.persistence.settings import load_buffer_days


class DuplicateProductError(StockError):
    """A Product (active or Archived) already has the name, compared by name_key."""

    def __init__(self, product_id: int, archived: bool) -> None:
        super().__init__("Produkt o tej nazwie już istnieje.")
        self.product_id = product_id
        self.archived = archived


class MissingBatchError(StockError):
    """The Batch was removed meanwhile, e.g. by a Use or a second click on Wyrzuć."""

    def __init__(self) -> None:
        super().__init__("Tej partii już nie ma.")


def add_product(engine: Engine, draft: ProductDraft, first_batch: BatchDraft | None = None) -> int:
    """Save a new Product, with its first Batch if given; returns its id."""
    with engine.begin() as connection:
        _refuse_duplicate(connection, draft.name)
        product_id: int = connection.execute(
            insert(ProductRow).values(**_product_values(draft), archived=False).returning(ProductRow.id)
        ).scalar_one()
        if first_batch is not None:
            connection.execute(
                insert(BatchRow).values(product_id=product_id, quantity=first_batch.quantity, expiry=first_batch.expiry)
            )
    return product_id


def add_products(engine: Engine, drafts: Sequence[ProductDraft]) -> tuple[int, ...]:
    """Save new Products without Batches in one transaction, the Starter Catalog's; returns their ids in order. A name
    already taken saves none."""
    with engine.begin() as connection:
        product_ids = []
        for draft in drafts:
            _refuse_duplicate(connection, draft.name)
            product_ids.append(
                connection.execute(
                    insert(ProductRow).values(**_product_values(draft), archived=False).returning(ProductRow.id)
                ).scalar_one()
            )
    return tuple(product_ids)


class ProductsInUseError(StockError):
    """The undo of add_products when a Product it added is gone or has a Batch or a Stock Event by then."""

    def __init__(self) -> None:
        super().__init__("Nie można cofnąć: część tych produktów ma już partie albo historię.")


def remove_new_products(engine: Engine, product_ids: Sequence[int]) -> None:
    """Remove Products add_products saved, all or none: ProductsInUseError, with nothing removed, when one is gone or
    has a Batch or a Stock Event."""
    with engine.begin() as connection:
        existing = connection.execute(select(ProductRow.id).where(ProductRow.id.in_(product_ids))).scalars().all()
        used = connection.execute(
            select(BatchRow.id)
            .where(BatchRow.product_id.in_(product_ids))
            .union_all(select(StockEventRow.id).where(StockEventRow.product_id.in_(product_ids)))
        ).first()
        if len(existing) < len(set(product_ids)) or used is not None:
            raise ProductsInUseError()
        connection.execute(delete(ProductRow).where(ProductRow.id.in_(product_ids)))


class ProductInUseError(StockError):
    """The undo of add_product when the Product is gone or has a Stock Event by then."""

    def __init__(self) -> None:
        super().__init__("Nie można cofnąć: ten produkt ma już historię.")


def undo_add_product(engine: Engine, product_id: int) -> None:
    """Remove a Product add_product saved, with its first Batch: ProductInUseError, with nothing removed, when it is
    gone or has a Stock Event."""
    with engine.begin() as connection:
        existing = connection.execute(select(ProductRow.id).where(ProductRow.id == product_id)).first()
        used = connection.execute(select(StockEventRow.id).where(StockEventRow.product_id == product_id)).first()
        if existing is None or used is not None:
            raise ProductInUseError()
        connection.execute(delete(BatchRow).where(BatchRow.product_id == product_id))
        connection.execute(delete(ProductRow).where(ProductRow.id == product_id))


def update_product(engine: Engine, product_id: int, draft: ProductDraft) -> None:
    """Save the Product's fields from ``draft``; its Batches stay. Keeping its own name is no duplicate."""
    with engine.begin() as connection:
        _refuse_duplicate(connection, draft.name, other_than=product_id)
        connection.execute(update(ProductRow).where(ProductRow.id == product_id).values(**_product_values(draft)))


def archive_product(engine: Engine, product_id: int) -> None:
    """Hide the Product with its Batches from every list; its name stays taken (docs/spec.md)."""
    _set_archived(engine, product_id, True)


def restore_product(engine: Engine, product_id: int) -> None:
    """Bring an Archived Product back with its Batches and settings: Przywróć, and the undo of an Archive.

    No name check: an Archived Product keeps its name, so no active Product can have taken it meanwhile."""
    _set_archived(engine, product_id, False)


def _set_archived(engine: Engine, product_id: int, archived: bool) -> None:
    with engine.begin() as connection:
        connection.execute(update(ProductRow).where(ProductRow.id == product_id).values(archived=archived))


def _refuse_duplicate(connection: Connection, name: str, *, other_than: int | None = None) -> None:
    query = select(ProductRow.id, ProductRow.archived).where(ProductRow.name_key == name_key(name))
    if other_than is not None:
        query = query.where(ProductRow.id != other_than)
    existing = connection.execute(query).first()
    if existing is not None:
        raise DuplicateProductError(existing.id, existing.archived)


def _product_values(draft: ProductDraft) -> dict[str, object]:
    pack = draft.pack_size
    return {
        "name": draft.name,
        "name_key": name_key(draft.name),
        "category_id": draft.category_id,
        "unit_id": draft.unit_id,
        "pack_amount": None if pack is None else pack.amount,
        "pack_measure": None if pack is None else pack.measure,
        "minimum_stock": draft.minimum_stock,
        "usual_shelf_life_days": draft.usual_shelf_life_days,
    }


def list_products(engine: Engine, *, archived: bool = False) -> list[Product]:
    """The active Products (or the Archived ones), by name; each with its Batches in the order Uses take them."""
    with engine.connect() as connection:
        return _load_products(connection, ProductRow.archived == archived)


def list_shopping_list(engine: Engine, today: date) -> list[ShoppingListEntry]:
    """The Shopping List: the active Products Running Low or Running Out within the Buffer, by name."""
    return shopping_list(list_products(engine), consumption_rates(engine, today), load_buffer_days(engine))


def suggested_purchases(engine: Engine, products: Sequence[Product], today: date) -> dict[int, int]:
    """How many Units a Purchase of each of ``products`` suggests, by id: the one source of the amount the Shopping
    List, the Purchase dialog and Unpacking show."""
    rates, buffer_days = consumption_rates(engine, today), load_buffer_days(engine)
    return {product.id: suggested_purchase(product, rates.get(product.id), buffer_days) for product in products}


def shopping_list_text(engine: Engine, today: date) -> str:
    """The Shopping List as plain text, what "Kopiuj listę" copies, "Udostępnij" shares and the printable page
    shows."""
    units = {unit.id: unit for unit in list_units(engine)}
    products = [entry.product for entry in list_shopping_list(engine, today)]
    return format_shopping_list(list_categories(engine), units, products, suggested_purchases(engine, products, today))


def get_product(engine: Engine, product_id: int) -> Product:
    """One Product, active or Archived, with its Batches in the order Uses take them."""
    with engine.connect() as connection:
        [product] = _load_products(connection, ProductRow.id == product_id)
        return product


@dataclass(frozen=True)
class Purchased:
    """What a Purchase or an Unpacking added, for undo_purchase: the new Batches and their Stock Events."""

    batches: tuple[Batch, ...]
    event_ids: tuple[int, ...]


@dataclass(frozen=True)
class Used:
    """What a Use took, for undo_use: the Batches it touched as they were before, and its Stock Event."""

    batches_before: tuple[Batch, ...]
    event_ids: tuple[int, ...]


def purchase(engine: Engine, product_id: int, draft: BatchDraft, on: date) -> Purchased:
    """Add a new Batch to the Product, a Purchase dated ``on``."""
    return purchase_many(engine, [(product_id, draft)], on)


def purchase_many(engine: Engine, purchases: Sequence[tuple[int, BatchDraft]], on: date) -> Purchased:
    """The Purchases of an Unpacking in one transaction: a new Batch and a Purchase event for each (product id,
    draft), in order."""
    batches: list[Batch] = []
    event_ids: list[int] = []
    with engine.begin() as connection:
        for product_id, draft in purchases:
            batches.append(
                Batch(
                    *connection.execute(
                        insert(BatchRow)
                        .values(product_id=product_id, quantity=draft.quantity, expiry=draft.expiry)
                        .returning(BatchRow.id, BatchRow.product_id, BatchRow.quantity, BatchRow.expiry)
                    ).one()
                )
            )
            event_ids.append(record_event(connection, product_id, StockEventKind.PURCHASE, draft.quantity, on))
    return Purchased(tuple(batches), tuple(event_ids))


def undo_purchase(engine: Engine, purchased: Purchased) -> None:
    """Remove the Batches and Stock Events of a Purchase or an Unpacking, all or none: MissingBatchError, with nothing
    removed, when a Batch is already gone."""
    with engine.begin() as connection:
        for batch in purchased.batches:
            _discard_batch(connection, batch.id)
        remove_events(connection, purchased.event_ids)


def edit_batch(engine: Engine, batch_id: int, quantity: int, expiry: date | None, on: date) -> None:
    """Set a Batch's Quantity and Expiry Date by hand; a Quantity of 0 removes the Batch, the Product stays. A changed
    Quantity is a Correction dated ``on``, by the difference; a Quantity of 0 too, not a Discard."""
    if quantity < 0:
        raise StockError("Ilość nie może być ujemna.")
    with engine.begin() as connection:
        before = connection.execute(select(BatchRow).where(BatchRow.id == batch_id)).first()
        if before is None:
            raise MissingBatchError()
        if quantity == 0:
            connection.execute(delete(BatchRow).where(BatchRow.id == batch_id))
        else:
            connection.execute(update(BatchRow).where(BatchRow.id == batch_id).values(quantity=quantity, expiry=expiry))
        if quantity != before.quantity:
            record_event(connection, before.product_id, StockEventKind.CORRECTION, quantity - before.quantity, on)


@dataclass(frozen=True)
class Discarded:
    """What a Discard removed, for undo_discard: the Batch as it was, and its Stock Event."""

    batch: Batch
    event_ids: tuple[int, ...]


def discard_batch(engine: Engine, batch_id: int, on: date) -> Discarded:
    """Remove a whole Batch, a Discard dated ``on`` and marked Expired when the Batch was by then."""
    with engine.begin() as connection:
        batch = _discard_batch(connection, batch_id)
        event_id = record_event(
            connection, batch.product_id, StockEventKind.DISCARD, -batch.quantity, on, expired=is_expired(batch, on)
        )
    return Discarded(batch, (event_id,))


def undo_discard(engine: Engine, discarded: Discarded) -> None:
    """Put the Batch back as it was and remove the Discard's Stock Event, in one transaction."""
    with engine.begin() as connection:
        _restore_batch(connection, discarded.batch)
        remove_events(connection, discarded.event_ids)


def _discard_batch(connection: Connection, batch_id: int) -> Batch:
    row = connection.execute(delete(BatchRow).where(BatchRow.id == batch_id).returning(BatchRow)).first()
    if row is None:
        raise MissingBatchError()
    return Batch(row.id, row.product_id, row.quantity, row.expiry)


class NotEnoughStockError(StockError):
    """A Use of more Units than the Product's Quantity."""

    def __init__(self, quantity: int) -> None:
        super().__init__(f"Na stanie jest tylko {quantity}.")


def use_units(engine: Engine, product_id: int, count: int, on: date) -> Used:
    """Take ``count`` Units off the Batches in the order Uses take them, a Use dated ``on``; a Batch that reaches 0
    goes. Nothing changes when it refuses."""
    if count < 1:
        raise StockError("Podaj co najmniej 1.")
    with engine.begin() as connection:
        [product] = _load_products(connection, ProductRow.id == product_id)
        if count > product.quantity:
            raise NotEnoughStockError(product.quantity)
        taken = units_to_use(product.batches, count)
        for batch, units in taken:
            if units == batch.quantity:
                connection.execute(delete(BatchRow).where(BatchRow.id == batch.id))
            else:
                connection.execute(
                    update(BatchRow).where(BatchRow.id == batch.id).values(quantity=batch.quantity - units)
                )
        event_id = record_event(connection, product_id, StockEventKind.USE, -count, on)
        return Used(tuple(batch for batch, _ in taken), (event_id,))


def use_one(engine: Engine, product_id: int, on: date) -> Used | None:
    """use_units of one Unit, or None when the Product has no Units."""
    try:
        return use_units(engine, product_id, 1, on)
    except NotEnoughStockError:
        return None


def undo_use(engine: Engine, used: Used) -> None:
    """Put back the Batches a Use touched and remove its Stock Event, in one transaction."""
    with engine.begin() as connection:
        for batch in used.batches_before:
            _restore_batch(connection, batch)
        remove_events(connection, used.event_ids)


def _restore_batch(connection: Connection, batch: Batch) -> None:
    # Put ``batch`` back as given, whether it still exists or was removed. SQLite gives a new Batch the id of one just
    # removed, so a row that now holds the id for another Product is left alone and the Batch comes back under a new id
    values = {"product_id": batch.product_id, "quantity": batch.quantity, "expiry": batch.expiry}
    holder = connection.execute(select(BatchRow.product_id).where(BatchRow.id == batch.id)).scalar_one_or_none()
    if holder == batch.product_id:
        connection.execute(update(BatchRow).where(BatchRow.id == batch.id).values(**values))
    elif holder is None:
        connection.execute(insert(BatchRow).values(id=batch.id, **values))
    else:
        connection.execute(insert(BatchRow).values(**values))


def _load_products(connection: Connection, condition: ColumnElement[bool]) -> list[Product]:
    rows = connection.execute(select(ProductRow).where(condition).order_by(ProductRow.name_key)).all()
    batches: dict[int, list[Batch]] = {}
    product_ids = [row.id for row in rows]
    for batch in connection.execute(select(BatchRow).where(BatchRow.product_id.in_(product_ids))):
        batches.setdefault(batch.product_id, []).append(Batch(batch.id, batch.product_id, batch.quantity, batch.expiry))
    return [
        Product(
            row.id,
            row.name,
            row.category_id,
            row.unit_id,
            None
            if row.pack_amount is None or row.pack_measure is None
            else PackSize(row.pack_amount, row.pack_measure),
            row.minimum_stock,
            row.archived,
            tuple(sorted(batches.get(row.id, []), key=use_order)),
            row.usual_shelf_life_days,
        )
        for row in rows
    ]
