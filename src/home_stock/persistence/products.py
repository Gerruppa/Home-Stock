"""Products and their Batches."""

from sqlalchemy import ColumnElement, Connection, Engine, delete, insert, select, update

from home_stock.domain.stock import (
    Batch,
    BatchDraft,
    PackSize,
    Product,
    ProductDraft,
    batch_to_use,
    name_key,
    use_order,
)
from home_stock.persistence.catalog import StockError
from home_stock.persistence.models import BatchRow, ProductRow


class DuplicateProductError(StockError):
    """A Product (active or Archived) already has the name, compared by name_key."""

    def __init__(self, product_id: int, archived: bool) -> None:
        super().__init__("Produkt o tej nazwie już istnieje.")
        self.product_id = product_id
        self.archived = archived


def add_product(engine: Engine, draft: ProductDraft, first_batch: BatchDraft | None = None) -> int:
    """Save a new Product, with its first Batch if given; returns its id."""
    pack = draft.pack_size
    with engine.begin() as connection:
        existing = connection.execute(
            select(ProductRow.id, ProductRow.archived).where(ProductRow.name_key == name_key(draft.name))
        ).first()
        if existing is not None:
            raise DuplicateProductError(existing.id, existing.archived)
        product_id: int = connection.execute(
            insert(ProductRow)
            .values(
                name=draft.name,
                name_key=name_key(draft.name),
                category_id=draft.category_id,
                unit_id=draft.unit_id,
                pack_amount=None if pack is None else pack.amount,
                pack_measure=None if pack is None else pack.measure,
                minimum_stock=draft.minimum_stock,
                archived=False,
            )
            .returning(ProductRow.id)
        ).scalar_one()
        if first_batch is not None:
            connection.execute(
                insert(BatchRow).values(product_id=product_id, quantity=first_batch.quantity, expiry=first_batch.expiry)
            )
    return product_id


def list_products(engine: Engine, *, archived: bool = False) -> list[Product]:
    """The active Products (or the Archived ones), by name; each with its Batches in the order Uses take them."""
    with engine.connect() as connection:
        return _load_products(connection, ProductRow.archived == archived)


def get_product(engine: Engine, product_id: int) -> Product:
    """One Product, active or Archived, with its Batches in the order Uses take them."""
    with engine.connect() as connection:
        [product] = _load_products(connection, ProductRow.id == product_id)
        return product


def use_one(engine: Engine, product_id: int) -> Batch | None:
    """Take one Unit off the Batch a Use takes; a Batch that reaches 0 goes. Returns that Batch as it was before,
    for restore_batch to undo the Use, or None when the Product has no Units."""
    with engine.begin() as connection:
        [product] = _load_products(connection, ProductRow.id == product_id)
        batch = batch_to_use(product.batches)
        if batch is None:
            return None
        if batch.quantity == 1:
            connection.execute(delete(BatchRow).where(BatchRow.id == batch.id))
        else:
            connection.execute(update(BatchRow).where(BatchRow.id == batch.id).values(quantity=batch.quantity - 1))
        return batch


def restore_batch(engine: Engine, batch: Batch) -> None:
    """Put ``batch`` back as given, whether it still exists or was removed: the undo of a Use.

    SQLite gives a new Batch the id of one just removed, so a row that now holds the id for another Product is left
    alone and the Batch comes back under a new id."""
    values = {"product_id": batch.product_id, "quantity": batch.quantity, "expiry": batch.expiry}
    with engine.begin() as connection:
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
        )
        for row in rows
    ]
