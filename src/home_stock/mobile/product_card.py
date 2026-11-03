"""The full-screen Product card: its fields, editable through the Product form, a Use of several Units, its Batches,
each editable or Discarded, Purchases and its Stock History."""

from collections.abc import Callable
from dataclasses import replace
from datetime import date

import flet as ft
from sqlalchemy import Engine

from home_stock.domain.formatting import (
    format_date,
    format_days,
    format_days_left,
    format_pack_size,
    format_quantity,
    format_stock_event,
    parse_count,
    parse_date,
)
from home_stock.domain.history import days_left
from home_stock.domain.stock import Batch, ExpiryStatus, Product, Unit, expiry_status, suggested_minimum_stock
from home_stock.mobile.context import Context
from home_stock.mobile.fields import date_field, show_error, text_field
from home_stock.mobile.product_form import open_product_form
from home_stock.mobile.purchase_dialog import open_purchase_dialog
from home_stock.mobile.theme import EXPIRED, EXPIRING
from home_stock.persistence.catalog import StockError, list_categories, list_units
from home_stock.persistence.history import consumption_rates, list_product_events
from home_stock.persistence.products import (
    archive_product,
    discard_batch,
    edit_batch,
    get_product,
    restore_product,
    undo_discard,
    undo_use,
    update_product,
    use_units,
)
from home_stock.persistence.settings import load_buffer_days

# The colours of the Start sections Przeterminowane and Kończy się termin
_STATUS_MARKS = {
    ExpiryStatus.EXPIRED: ("przeterminowana", EXPIRED),
    ExpiryStatus.EXPIRING_SOON: ("kończy się termin", EXPIRING),
}


def open_product_card(ctx: Context, product_id: int) -> None:
    content = ft.ListView(spacing=8, padding=ft.Padding.symmetric(horizontal=16, vertical=8), expand=True)

    def changed() -> None:
        # Drawn first: the shell's changed() sends the screen its update
        draw()
        ctx.changed()

    def undo(message: str, action: Callable[[], None]) -> None:
        def undo_and_draw() -> None:
            try:
                action()
            finally:
                # The shell's Cofnij redraws the tabs, not the card
                draw()

        ctx.undo(message, undo_and_draw)

    # What the card does or opens (a Discard, the Purchase dialog) redraws the card too, also on Cofnij
    card_ctx = replace(ctx, changed=changed, undo=undo)

    def draw() -> None:
        product = get_product(ctx.engine, product_id)
        category = next(c for c in list_categories(ctx.engine) if c.id == product.category_id)
        unit = next(u for u in list_units(ctx.engine) if u.id == product.unit_id)
        title.value = product.name
        lines = [f"Kategoria: {category.name}", f"Jednostka: {unit.name}"]
        if product.pack_size is not None:
            lines.append(f"Rozmiar opakowania: {format_pack_size(product.pack_size)}")
        lines.append(f"Stan minimalny: {'brak' if product.minimum_stock is None else product.minimum_stock}")
        if product.usual_shelf_life_days is not None:
            lines.append(f"Po zakupie: zwykle ważne {format_days(product.usual_shelf_life_days)}")
        rows: list[ft.Control] = [ft.Text(line, color=ft.Colors.ON_SURFACE_VARIANT) for line in lines]
        rows.append(
            ft.Text(
                f"Razem: {format_quantity(product.quantity, unit, product.pack_size)}",
                size=18,
                weight=ft.FontWeight.W_600,
            )
        )
        rate = consumption_rates(ctx.engine, ctx.today()).get(product.id)
        if rate is not None:
            rows.append(
                ft.Text(
                    format_days_left(days_left(product.quantity, rate)),
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    key="card-days-left",
                )
            )
            suggested = suggested_minimum_stock(rate, load_buffer_days(ctx.engine))
            if suggested != product.minimum_stock:
                rows.append(_suggested_minimum_row(card_ctx, product, suggested))
        rows.append(_use_row(card_ctx, product))
        rows.append(_section("Partie"))
        if not product.batches:
            rows.append(ft.Text("Brak partii."))
        rows.extend(_batch_row(card_ctx, product, batch, category.warning_days) for batch in product.batches)
        rows.append(
            ft.Row(
                [
                    ft.FilledButton(
                        "Dodaj partię",
                        icon=ft.Icons.ADD,
                        on_click=lambda _: open_purchase_dialog(card_ctx, product),
                        key="card-purchase",
                    ),
                    ft.OutlinedButton(
                        "Edytuj",
                        icon=ft.Icons.EDIT,
                        on_click=lambda _: open_product_form(card_ctx, product),
                        key="card-edit",
                    ),
                    ft.TextButton(
                        "Archiwizuj",
                        icon=ft.Icons.INVENTORY_2_OUTLINED,
                        style=ft.ButtonStyle(color=ft.Colors.ERROR),
                        on_click=lambda _: archive(),
                        key="card-archive",
                    ),
                ],
                wrap=True,
            )
        )
        rows.append(_section("Historia"))
        rows.append(_history(ctx.engine, product, unit))
        content.controls = rows

    def archive() -> None:
        engine = ctx.engine
        product = get_product(engine, product_id)
        archive_product(engine, product_id)
        ctx.close_full_screen()
        ctx.changed()
        ctx.undo(f"Zarchiwizowano: {product.name}", lambda: restore_product(engine, product_id))

    title = ft.Text("", size=20, expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)
    draw()
    ctx.show_full_screen(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.IconButton(
                            ft.Icons.ARROW_BACK,
                            tooltip="Zamknij",
                            on_click=lambda _: ctx.close_full_screen(),
                            key="card-close",
                        ),
                        title,
                    ]
                ),
                content,
            ],
            expand=True,
            key="product-card",
        )
    )


def _section(title: str) -> ft.Control:
    return ft.Container(
        ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY), padding=ft.Padding.only(top=8)
    )


def _history(engine: Engine, product: Product, unit: Unit) -> ft.Control:
    """The Product's latest Stock Events, newest first."""
    events = list_product_events(engine, product.id)
    lines: list[ft.Control] = [ft.Text(format_stock_event(event, unit), size=13) for event in events]
    if not events:
        lines.append(ft.Text("Brak zdarzeń.", color=ft.Colors.ON_SURFACE_VARIANT))
    return ft.Column(lines, spacing=2, key="card-history")


def _suggested_minimum_row(ctx: Context, product: Product, suggested: int) -> ft.Control:
    """The Suggested Minimum Stock, applied in one tap."""

    def apply(_: ft.Event[ft.TextButton]) -> None:
        engine, old = ctx.engine, product.minimum_stock
        _save_minimum_stock(engine, product.id, suggested)
        ctx.changed()
        ctx.undo(f"Zmieniono stan minimalny: {product.name}", lambda: _save_minimum_stock(engine, product.id, old))

    return ft.Row(
        [
            ft.Text(f"Sugerowany stan minimalny: {suggested}", color=ft.Colors.ON_SURFACE_VARIANT, expand=True),
            ft.TextButton("Zastosuj", on_click=apply, key="card-apply-minimum"),
        ],
        key="card-suggested-minimum",
    )


def _save_minimum_stock(engine: Engine, product_id: int, minimum_stock: int | None) -> None:
    """Only the Minimum Stock changes: the other fields are read afresh, so an edit made meanwhile stays."""
    draft = replace(get_product(engine, product_id).draft(), minimum_stock=minimum_stock)
    update_product(engine, product_id, draft)


def _use_row(ctx: Context, product: Product) -> ft.Control:
    quantity = text_field("Ilość", "1", "card-use-quantity", number=True, width=96)

    def use(_: object) -> None:
        engine = ctx.engine
        try:
            count = parse_count(quantity.value or "") or 0
            used = use_units(engine, product.id, count, ctx.today())
        except (ValueError, StockError) as problem:
            show_error(quantity, str(problem))
            ctx.update()
            return
        ctx.changed()
        ctx.undo(f"Zużyto {count} × {product.name}", lambda: undo_use(engine, used))

    quantity.on_submit = use
    return ft.Row(
        [quantity, ft.OutlinedButton("Zużyj", disabled=product.quantity == 0, on_click=use, key="card-use")],
        vertical_alignment=ft.CrossAxisAlignment.START,
    )


def _batch_row(ctx: Context, product: Product, batch: Batch, warning_days: int) -> ft.Control:
    """Two lines, to fit a phone: the Quantity beside the whole Expiry Date, then its status and the buttons."""
    quantity = text_field("Ilość", str(batch.quantity), f"batch-quantity-{batch.id}", number=True, width=88)
    expiry = date_field(
        "Termin ważności", "" if batch.expiry is None else format_date(batch.expiry), f"batch-expiry-{batch.id}"
    )
    expiry.expand = True
    # Under the row, for a problem with either field or with the Batch itself (changed meanwhile)
    error = ft.Text("", color=ft.Colors.ERROR, size=12, visible=False, key=f"batch-error-{batch.id}")

    def fail(problem: Exception) -> None:
        error.value = str(problem)
        error.visible = True
        ctx.update()

    def save(_: object) -> None:
        try:
            quantity_left = parse_count(quantity.value or "") or 0
            # A Quantity of 0 removes the Batch, so its date no longer matters
            when = parse_date(expiry.value or "") if quantity_left else None
            edit_batch(ctx.engine, batch.id, quantity_left, when, ctx.today())
        except (ValueError, StockError) as problem:
            fail(problem)
            return
        ctx.changed()

    def discard(_: ft.Event[ft.TextButton]) -> None:
        engine = ctx.engine
        try:
            discarded = discard_batch(engine, batch.id, ctx.today())
        except StockError as problem:
            fail(problem)
            return
        ctx.changed()
        ctx.undo(f"Wyrzucono partię: {product.name}", lambda: undo_discard(engine, discarded))

    quantity.on_submit = save
    expiry.on_submit = save
    return ft.Container(
        ft.Column(
            [
                ft.Row([quantity, expiry], vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Row(
                    [
                        ft.Container(_expiry_status_mark(batch, ctx.today(), warning_days), expand=True),
                        ft.TextButton("Zapisz", on_click=save, key=f"batch-save-{batch.id}"),
                        ft.TextButton(
                            "Wyrzuć",
                            style=ft.ButtonStyle(color=ft.Colors.ERROR),
                            on_click=discard,
                            key=f"discard-{batch.id}",
                        ),
                    ]
                ),
                error,
            ],
            spacing=0,
        ),
        padding=ft.Padding.only(top=8),
        key=f"batch-{batch.id}",
    )


def _expiry_status_mark(batch: Batch, today: date, warning_days: int) -> ft.Control | None:
    """The saved Expiry Date's status, in its Start section's colour; none for a Fresh or undated Batch."""
    status = expiry_status(batch, today, warning_days)
    if status not in _STATUS_MARKS:
        return None
    text, colour = _STATUS_MARKS[status]
    return ft.Text(text, color=colour, weight=ft.FontWeight.W_500, key=f"batch-status-{batch.id}")
