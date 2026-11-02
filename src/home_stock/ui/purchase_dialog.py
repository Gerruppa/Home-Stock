"""The dialog that records a Purchase: a new Batch with a Quantity and an optional Expiry Date."""

from nicegui import ui

from home_stock.domain.formatting import format_date, parse_count, parse_date
from home_stock.domain.stock import BatchDraft, Product, default_expiry, suggested_purchase
from home_stock.persistence.products import discard_batch, purchase
from home_stock.ui.context import Context
from home_stock.ui.fields import error_label, show_error


def read_batch_draft(
    quantity: ui.input, expiry: ui.input, quantity_error: ui.label, expiry_error: ui.label
) -> BatchDraft | None:
    """The Purchase typed into the two fields, or None with each problem shown under its field."""
    count_problem = date_problem = None
    count = when = None
    try:
        count = parse_count(quantity.value)
    except ValueError as error:
        count_problem = str(error)
    try:
        when = parse_date(expiry.value)
    except ValueError as error:
        date_problem = str(error)
    draft = None
    if count is not None and date_problem is None:
        try:
            draft = BatchDraft(count, when)
        except ValueError as error:
            count_problem = str(error)
    show_error(quantity_error, count_problem)
    show_error(expiry_error, date_problem)
    return draft


def open_purchase_dialog(ctx: Context, product: Product) -> None:
    with ctx.overlay, ui.dialog() as dialog, ui.card().classes("w-80").mark("purchase-dialog"):
        ui.label(f"Zakup: {product.name}").classes("hs-dialog-title")
        quantity = ui.input("Ilość", value=str(suggested_purchase(product))).classes("w-full").mark("purchase-quantity")
        quantity_error = error_label()
        default = default_expiry(product.usual_shelf_life_days, ctx.today())
        expiry = ui.input(
            "Termin ważności (opcjonalnie)",
            value="" if default is None else format_date(default),
            placeholder="DD.MM.RRRR",
        ).classes("w-full")
        expiry.mark("purchase-expiry")
        expiry_error = error_label()

        def save() -> None:
            draft = read_batch_draft(quantity, expiry, quantity_error, expiry_error)
            if draft is None:
                return
            engine = ctx.engine
            batch_id = purchase(engine, product.id, draft)
            dialog.close()
            ctx.changed()

            def undo() -> None:
                # Not a Discard, but the same removal of the Batch by id; MissingBatchError if it is already gone
                discard_batch(engine, batch_id)

            ctx.undo(f"Zakupiono: {product.name}", undo)

        with ui.row().classes("w-full justify-end"):
            ui.button("Anuluj", on_click=dialog.close).props("flat")
            ui.button("Dodaj", on_click=save).mark("purchase-save")
    dialog.open()
