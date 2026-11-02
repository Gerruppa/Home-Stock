"""Unpacking: the whole Shopping List recorded as Purchases in one dialog."""

from dataclasses import dataclass

from nicegui import ui

from home_stock.domain.formatting import format_date
from home_stock.domain.stock import Product, default_expiry, suggested_purchase
from home_stock.persistence.catalog import list_categories
from home_stock.persistence.products import MissingBatchError, discard_batch, list_running_low, purchase_many
from home_stock.ui.context import Context
from home_stock.ui.fields import error_label
from home_stock.ui.purchase_dialog import read_batch_draft


@dataclass
class _Row:
    product: Product
    tick: ui.checkbox
    quantity: ui.input
    expiry: ui.input
    quantity_error: ui.label
    expiry_error: ui.label


def open_unpacking_dialog(ctx: Context) -> None:
    products = list_running_low(ctx.engine)
    rows: list[_Row] = []
    with ctx.overlay, ui.dialog() as dialog, ui.card().classes("w-96").mark("unpacking-dialog"):
        ui.label("Rozpakuj zakupy").classes("hs-dialog-title")
        if not products:
            ui.label("Nie ma nic do rozpakowania.")
        for category in list_categories(ctx.engine):
            shown = [p for p in products if p.category_id == category.id]
            if shown:
                ui.label(category.name).classes("hs-section-title q-mt-sm")
            for product in shown:
                rows.append(_add_row(ctx, product))

        def save() -> None:
            # Every ticked row is read, so each shows its own error; nothing is saved while one has one
            ticked = [row for row in rows if row.tick.value]
            drafts = [
                read_batch_draft(row.quantity, row.expiry, row.quantity_error, row.expiry_error) for row in ticked
            ]
            purchases = [
                (row.product.id, draft) for row, draft in zip(ticked, drafts, strict=True) if draft is not None
            ]
            if len(purchases) < len(ticked):
                return
            dialog.close()
            if not purchases:
                return
            engine = ctx.engine
            batches = purchase_many(engine, purchases)
            ctx.changed()

            def undo() -> None:
                gone = False
                for batch in batches:
                    try:
                        discard_batch(engine, batch.id)
                    except MissingBatchError:
                        gone = True
                if gone:
                    # The rest are removed; say that some were already gone
                    raise MissingBatchError()

            ctx.undo(f"Rozpakowano zakupy: {len(batches)}", undo)

        with ui.row().classes("w-full justify-end"):
            ui.button("Anuluj", on_click=dialog.close).props("flat")
            if products:
                ui.button("Zapisz", on_click=save).mark("unpack-save")
    dialog.open()


def _add_row(ctx: Context, product: Product) -> _Row:
    default = default_expiry(product.usual_shelf_life_days, ctx.today())
    with ui.column().classes("w-full gap-0").mark(f"unpack-row-{product.id}"):
        with ui.row().classes("w-full items-center no-wrap"):
            tick = ui.checkbox(product.name, value=True).classes("grow").mark(f"unpack-tick-{product.id}")
            quantity = ui.input(value=str(suggested_purchase(product))).props("dense").classes("w-16")
            quantity.mark(f"unpack-quantity-{product.id}")
            expiry = ui.input(value="" if default is None else format_date(default), placeholder="DD.MM.RRRR")
            expiry.props("dense").classes("w-32").mark(f"unpack-expiry-{product.id}")
        quantity_error = error_label()
        expiry_error = error_label()
    return _Row(product, tick, quantity, expiry, quantity_error, expiry_error)
