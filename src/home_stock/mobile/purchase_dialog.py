"""The full-screen dialog that records a Purchase: a new Batch with a Quantity and an optional Expiry Date."""

from collections.abc import Callable
from functools import partial

import flet as ft

from home_stock.domain.custom_lists import ListLine
from home_stock.domain.formatting import format_date, parse_count, parse_date
from home_stock.domain.stock import BatchDraft, Product, default_expiry
from home_stock.mobile.context import Context
from home_stock.mobile.fields import date_field, show_error, text_field
from home_stock.persistence.catalog import StockError
from home_stock.persistence.custom_lists import buy_lines, undo_buy_lines
from home_stock.persistence.products import purchase, suggested_purchases, undo_purchase


def parse_batch_draft(quantity: str, expiry: str) -> tuple[BatchDraft | None, str | None, str | None]:
    """The Purchase typed as a Quantity and an Expiry Date: the draft, or None with the problem of each."""
    count_problem = date_problem = None
    count = when = None
    try:
        count = parse_count(quantity)
    except ValueError as error:
        count_problem = str(error)
    try:
        when = parse_date(expiry)
    except ValueError as error:
        date_problem = str(error)
    draft = None
    if count is not None and date_problem is None:
        try:
            draft = BatchDraft(count, when)
        except ValueError as error:
            count_problem = str(error)
    return draft, count_problem, date_problem


def read_batch_draft(quantity: ft.TextField, expiry: ft.TextField) -> BatchDraft | None:
    """The Purchase typed into the two fields, or None with each problem shown on its field."""
    draft, count_problem, date_problem = parse_batch_draft(quantity.value or "", expiry.value or "")
    show_error(quantity, count_problem)
    show_error(expiry, date_problem)
    return draft


def open_purchase_dialog(ctx: Context, product: Product, line: ListLine | None = None) -> None:
    """With a Custom List's ``line``, the line's Quantity is filled in and saving marks the line bought too, both
    taken back by one Cofnij."""
    if line is not None and line.quantity is not None:
        suggested = line.quantity
    else:
        suggested = suggested_purchases(ctx.engine, [product], ctx.today())[product.id]
    quantity = text_field("Ilość", str(suggested), "purchase-quantity", number=True)
    default = default_expiry(product.usual_shelf_life_days, ctx.today())
    expiry = date_field(
        "Termin ważności (opcjonalnie)", "" if default is None else format_date(default), "purchase-expiry"
    )

    def save(_: object) -> None:
        draft = read_batch_draft(quantity, expiry)
        if draft is None:
            ctx.update()
            return
        engine = ctx.engine
        undo: Callable[[], None]
        if line is None:
            purchased = purchase(engine, product.id, draft, ctx.today())
            undo = partial(undo_purchase, engine, purchased)
        else:
            try:
                bought = buy_lines(engine, [(line.id, draft)], ctx.today())
            except StockError as problem:
                # The line was deleted or ticked meanwhile: nothing recorded
                ctx.close_full_screen()
                ctx.changed()
                ctx.say(str(problem))
                return
            undo = partial(undo_buy_lines, engine, bought)
        ctx.close_full_screen()
        ctx.changed()
        # MissingBatchError, shown in the snackbar, when the Batch is already gone
        ctx.undo(f"Zakupiono: {product.name}", undo)

    quantity.on_submit = save
    expiry.on_submit = save
    ctx.show_full_screen(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.IconButton(
                            ft.Icons.CLOSE,
                            tooltip="Anuluj",
                            on_click=lambda _: ctx.close_full_screen(),
                            key="purchase-cancel",
                        ),
                        ft.Text(
                            f"Zakup: {product.name}",
                            size=20,
                            expand=True,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.FilledButton("Dodaj", on_click=save, key="purchase-save"),
                        ft.Container(width=8),
                    ]
                ),
                ft.ListView(
                    [quantity, expiry], spacing=12, padding=ft.Padding.symmetric(horizontal=16, vertical=8), expand=True
                ),
            ],
            expand=True,
            key="purchase-dialog",
        )
    )
