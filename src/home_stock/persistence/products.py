"""Products and their Batches."""

from sqlalchemy import Engine, insert, select

from home_stock.domain.stock import Batch, BatchDraft, PackSize, Product, ProductDraft, name_key, use_order
from home_stock.persistence.models import BatchRow, ProductRow


def add_product(engine: Engine, draft: ProductDraft, first_batch: BatchDraft | None = None) -> int:
    """Save a new Product, with its first Batch if given; returns its id."""
    pack = draft.pack_size
    with engine.begin() as connection:
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
        rows = connection.execute(
            select(ProductRow).where(ProductRow.archived == archived).order_by(ProductRow.name_key)
        ).all()
        batches: dict[int, list[Batch]] = {}
        for batch in connection.execute(select(BatchRow)):
            batches.setdefault(batch.product_id, []).append(
                Batch(batch.id, batch.product_id, batch.quantity, batch.expiry)
            )
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
