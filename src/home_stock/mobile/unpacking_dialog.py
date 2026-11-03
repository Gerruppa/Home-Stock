"""Unpacking: the whole Shopping List recorded as Purchases in one full-screen form."""

from dataclasses import dataclass

import flet as ft

from home_stock.domain.formatting import format_date
from home_stock.domain.stock import BatchDraft, Product, default_expiry
from home_stock.mobile.context import Context
from home_stock.mobile.fields import date_field, text_field
from home_stock.mobile.purchase_dialog import parse_batch_draft
from home_stock.persistence.catalog import list_categories
from home_stock.persistence.products import (
    list_products,
    list_shopping_list,
    purchase_many,
    suggested_purchases,
    undo_purchase,
)


@dataclass
class _Row:
    product: Product
    tick: ft.Checkbox
    quantity: ft.TextField
    expiry: ft.TextField
    # Under the row, for a problem with either field: side by side, they are too narrow to carry one each
    error: ft.Text
    control: ft.Control

    def read(self) -> BatchDraft | None:
        """The Purchase typed into the row, or None with its problems shown under it."""
        draft, *problems = parse_batch_draft(self.quantity.value or "", self.expiry.value or "")
        shown = [problem for problem in problems if problem is not None]
        self.error.value = "\n".join(shown)
        self.error.visible = bool(shown)
        return draft


def open_unpacking_dialog(ctx: Context) -> None:
    products = [entry.product for entry in list_shopping_list(ctx.engine, ctx.today())]
    # Impulse buys: any active Product, picked by name, gets a row like the Shopping List's below the list
    active = {product.id: product for product in list_products(ctx.engine)}
    amounts = suggested_purchases(ctx.engine, list(active.values()), ctx.today())
    rows: list[_Row] = []
    listed: list[ft.Control] = []
    for category in list_categories(ctx.engine):
        shown = [p for p in products if p.category_id == category.id]
        if shown:
            listed.append(_heading(category.name))
        for product in shown:
            rows.append(_new_row(ctx, product, amounts[product.id]))
            listed.append(rows[-1].control)
    nothing = ft.Text("Nie ma nic do rozpakowania.", visible=not products, key="nothing-to-unpack")
    # Under its own heading, not the last Category's
    added = ft.Column([_heading("Spoza listy")], spacing=0, visible=False, key="unpack-added")
    name = ft.Dropdown(
        label="Dodaj produkt spoza listy",
        options=[ft.DropdownOption(key=str(p.id), text=p.name) for p in active.values()],
        editable=True,
        enable_filter=True,
        expand=True,
        key="unpack-add",
    )

    def add_by_name(_: object) -> None:
        product = active.get(int(name.value)) if name.value else None
        # Empty again, typed text too, for the next impulse buy
        name.value = None
        name.text = ""
        if product is not None and all(row.product.id != product.id for row in rows):
            rows.append(_new_row(ctx, product, amounts[product.id]))
            added.controls.append(rows[-1].control)
            added.visible = True
            nothing.visible = False
            save_button.visible = True
        ctx.update()

    name.on_select = add_by_name

    def save(_: object) -> None:
        # Every ticked row is read, so each shows its own problems; nothing is saved while one has one
        ticked = [row for row in rows if row.tick.value]
        drafts = [row.read() for row in ticked]
        purchases = [(row.product.id, draft) for row, draft in zip(ticked, drafts, strict=True) if draft is not None]
        if len(purchases) < len(ticked):
            ctx.update()
            return
        ctx.close_full_screen()
        if not purchases:
            return
        engine = ctx.engine
        unpacked = purchase_many(engine, purchases, ctx.today())
        ctx.changed()
        # All or nothing: MissingBatchError leaves every Batch in place when one is already gone
        ctx.undo(f"Rozpakowano zakupy: {len(unpacked.batches)}", lambda: undo_purchase(engine, unpacked))

    save_button = ft.FilledButton("Zapisz", on_click=save, visible=bool(products), key="unpack-save")
    ctx.show_full_screen(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.IconButton(
                            ft.Icons.CLOSE,
                            tooltip="Anuluj",
                            on_click=lambda _: ctx.close_full_screen(),
                            key="unpack-cancel",
                        ),
                        ft.Text("Rozpakuj zakupy", size=20, expand=True),
                        save_button,
                        ft.Container(width=8),
                    ]
                ),
                ft.ListView(
                    [
                        nothing,
                        ft.Column(listed, spacing=0, key="unpack-rows"),
                        added,
                        ft.Container(ft.Row([name]), padding=ft.Padding.only(top=16)),
                    ],
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                    expand=True,
                ),
            ],
            expand=True,
            key="unpacking-dialog",
        )
    )


def _heading(text: str) -> ft.Control:
    return ft.Container(
        ft.Text(text, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY), padding=ft.Padding.only(top=16, bottom=4)
    )


def _new_row(ctx: Context, product: Product, suggested: int) -> _Row:
    """Two lines, to fit a phone: the tick with the name, then the Quantity beside the whole Expiry Date."""
    default = default_expiry(product.usual_shelf_life_days, ctx.today())
    tick = ft.Checkbox(label=product.name, value=True, key=f"unpack-tick-{product.id}")
    quantity = text_field("Ilość", str(suggested), f"unpack-quantity-{product.id}", number=True, width=88)
    expiry = date_field(
        "Termin ważności", "" if default is None else format_date(default), f"unpack-expiry-{product.id}"
    )
    expiry.expand = True
    error = ft.Text("", color=ft.Colors.ERROR, size=12, visible=False, key=f"unpack-error-{product.id}")
    control = ft.Container(
        ft.Column([tick, ft.Row([quantity, expiry]), error], spacing=4),
        padding=ft.Padding.only(bottom=8),
        key=f"unpack-row-{product.id}",
    )
    return _Row(product, tick, quantity, expiry, error, control)
