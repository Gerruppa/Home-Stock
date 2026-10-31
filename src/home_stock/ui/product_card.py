"""The Product card: its fields, editable through the Product form, its Batches, each editable or Discarded, and
Purchases."""

from collections.abc import Callable
from dataclasses import replace

from nicegui import ui

from home_stock.domain.formatting import (
    format_date,
    format_days,
    format_pack_size,
    format_quantity,
    parse_count,
    parse_date,
)
from home_stock.domain.stock import Batch, Product
from home_stock.persistence.catalog import StockError, list_categories, list_units
from home_stock.persistence.products import (
    archive_product,
    discard_batch,
    edit_batch,
    get_product,
    restore_batch,
    restore_product,
)
from home_stock.ui.context import Context
from home_stock.ui.fields import error_label, show_error
from home_stock.ui.product_form import open_product_form
from home_stock.ui.purchase_dialog import open_purchase_dialog


def open_product_card(ctx: Context, product_id: int) -> None:
    with ctx.overlay, ui.dialog() as dialog, ui.card().classes("w-[36rem]").mark("product-card"):
        content = ui.column().classes("w-full gap-1")
        with ui.row().classes("w-full justify-end"):
            ui.button("Zamknij", on_click=dialog.close).props("flat")

    def changed() -> None:
        ctx.changed()
        draw()

    # What the card opens (the Purchase dialog) redraws the card too
    card_ctx = replace(ctx, changed=changed)

    def draw() -> None:
        product = get_product(ctx.engine, product_id)
        category = next(c for c in list_categories(ctx.engine) if c.id == product.category_id)
        unit = next(u for u in list_units(ctx.engine) if u.id == product.unit_id)
        content.clear()
        with content:
            ui.label(product.name).classes("hs-dialog-title")
            ui.label(f"Kategoria: {category.name}").classes("hs-muted")
            ui.label(f"Jednostka: {unit.name}").classes("hs-muted")
            if product.pack_size is not None:
                ui.label(f"Rozmiar opakowania: {format_pack_size(product.pack_size)}").classes("hs-muted")
            minimum = "brak" if product.minimum_stock is None else str(product.minimum_stock)
            ui.label(f"Stan minimalny: {minimum}").classes("hs-muted")
            if product.shelf_life_days is not None:
                ui.label(f"Termin ważności: zwykle ważne {format_days(product.shelf_life_days)}").classes("hs-muted")
            ui.label(f"Razem: {format_quantity(product.quantity, unit, product.pack_size)}").classes("hs-qty")
            ui.label("Partie").classes("hs-section-title hs-section-title-green")
            if not product.batches:
                ui.label("Brak partii.")
            for batch in product.batches:
                _batch_row(card_ctx, product, batch, draw)
            with ui.row():
                ui.button("Dodaj partię", icon="add", on_click=lambda: open_purchase_dialog(card_ctx, product)).mark(
                    "card-purchase"
                )
                ui.button("Edytuj", icon="edit", on_click=lambda: open_product_form(card_ctx, product)).props(
                    "outline"
                ).mark("card-edit")
                ui.button("Archiwizuj", icon="inventory_2", on_click=lambda: archive()).props(
                    "flat color=negative"
                ).mark("card-archive")

    def archive() -> None:
        engine = ctx.engine
        product = get_product(engine, product_id)
        archive_product(engine, product_id)
        dialog.close()
        ctx.changed()
        ctx.undo(f"Zarchiwizowano: {product.name}", lambda: restore_product(engine, product_id))

    draw()
    dialog.open()


def _batch_row(ctx: Context, product: Product, batch: Batch, draw: Callable[[], None]) -> None:
    with ui.row().classes("w-full items-start no-wrap").mark(f"batch-{batch.id}"):
        quantity = ui.input("Ilość", value=str(batch.quantity)).classes("w-24").mark(f"batch-quantity-{batch.id}")
        expiry = ui.input(
            "Termin ważności",
            value="" if batch.expiry is None else format_date(batch.expiry),
            placeholder="DD.MM.RRRR",
        )
        expiry.classes("grow").mark(f"batch-expiry-{batch.id}")
        ui.button("Zapisz", on_click=lambda: save()).props("flat").mark(f"batch-save-{batch.id}")
        ui.button("Wyrzuć", on_click=lambda: discard()).props("flat color=negative").mark(f"discard-{batch.id}")
    error = error_label()

    def save() -> None:
        try:
            count = parse_count(quantity.value) or 0
            # A Quantity of 0 removes the Batch, so its date no longer matters
            when = parse_date(expiry.value) if count else None
            edit_batch(ctx.engine, batch.id, count, when)
        except (ValueError, StockError) as problem:
            show_error(error, str(problem))
            return
        ctx.changed()

    def discard() -> None:
        engine = ctx.engine
        try:
            discarded = discard_batch(engine, batch.id)
        except StockError as problem:
            show_error(error, str(problem))
            return
        ctx.changed()

        def undo() -> None:
            restore_batch(engine, discarded)
            # The shell's Cofnij redraws the tabs, not the card
            draw()

        ctx.undo(f"Wyrzucono partię: {product.name}", undo)
