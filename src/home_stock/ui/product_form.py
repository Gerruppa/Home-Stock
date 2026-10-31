"""The dialog that adds a Product, optionally with its first Batch, or edits one."""

from collections.abc import Callable

from nicegui import ui

from home_stock.domain.formatting import format_pack_size, parse_count, parse_pack_size, parse_shelf_life
from home_stock.domain.stock import BatchDraft, Product, ProductDraft, default_expiry
from home_stock.persistence.catalog import StockError, list_categories, list_units
from home_stock.persistence.products import (
    DuplicateProductError,
    add_product,
    purchase,
    restore_product,
    update_product,
)
from home_stock.ui.context import Context
from home_stock.ui.fields import error_label, show_error


def open_product_form(ctx: Context, product: Product | None = None) -> None:
    """A new Product when ``product`` is None, else that Product's fields filled in for editing."""
    categories = list_categories(ctx.engine)
    units = list_units(ctx.engine)
    with ctx.overlay, ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("Nowy produkt" if product is None else "Edytuj produkt").classes("hs-dialog-title")
        name = ui.input("Nazwa", value="" if product is None else product.name).classes("w-full").mark("name")
        name_error = error_label()
        # Shown when a new Product's name exists: offers the first Batch to the existing Product instead, or, when it
        # is Archived, restoring it
        duplicate_offer = ui.row().classes("w-full")
        duplicate_offer.set_visibility(False)
        name.on_value_change(lambda: duplicate_offer.set_visibility(False))
        category = ui.select(
            {c.id: c.name for c in categories},
            label="Kategoria",
            value=categories[0].id if product is None else product.category_id,
        )
        category.classes("w-full").mark("category")
        unit = ui.select(
            {u.id: u.name for u in units}, label="Jednostka", value=units[0].id if product is None else product.unit_id
        )
        unit.classes("w-full").mark("unit")
        pack_size = ui.input(
            "Rozmiar opakowania (opcjonalnie)",
            value="" if product is None or product.pack_size is None else format_pack_size(product.pack_size),
            placeholder="np. 1 kg",
        )
        pack_size.classes("w-full").mark("pack-size")
        pack_size_error = error_label()
        # Cleared, the Product has no Minimum Stock and never goes on the Shopping List
        minimum_text = "1" if product is None else "" if product.minimum_stock is None else str(product.minimum_stock)
        minimum_stock = ui.input("Stan minimalny", value=minimum_text).classes("w-full").mark("minimum-stock")
        minimum_stock_error = error_label()
        shelf_life = ui.input(
            "Zwykle ważne, dni (opcjonalnie)",
            value="" if product is None or product.shelf_life_days is None else str(product.shelf_life_days),
            placeholder="np. 7",
        )
        shelf_life.classes("w-full").mark("shelf-life")
        shelf_life_error = error_label()
        # Batches of an existing Product are edited on its card, not here
        if product is None:
            first_quantity = ui.input("Ilość na start (opcjonalnie)").classes("w-full").mark("first-quantity")
            quantity_error = error_label()

        def save() -> None:
            draft = first_batch = size = minimum = days = None
            valid = True
            duplicate_offer.set_visibility(False)
            try:
                size = parse_pack_size(pack_size.value)
                show_error(pack_size_error, None)
            except ValueError as error:
                show_error(pack_size_error, str(error))
                valid = False
            try:
                minimum = parse_count(minimum_stock.value, allow_blank=True)
                show_error(minimum_stock_error, None)
            except ValueError as error:
                show_error(minimum_stock_error, str(error))
                valid = False
            try:
                days = parse_shelf_life(shelf_life.value)
                show_error(shelf_life_error, None)
            except ValueError as error:
                show_error(shelf_life_error, str(error))
                valid = False
            try:
                draft = ProductDraft(name.value or "", category.value, unit.value, size, minimum, days)
                show_error(name_error, None)
            except ValueError as error:
                show_error(name_error, str(error))
            if product is None:
                try:
                    count = parse_count(first_quantity.value, allow_blank=True)
                    # A first Quantity of 0 means no first Batch, as Batches are never empty
                    first_batch = None if not count else BatchDraft(count, default_expiry(days, ctx.today()))
                    show_error(quantity_error, None)
                except ValueError as error:
                    show_error(quantity_error, str(error))
                    return
            if draft is None or not valid:
                return
            try:
                if product is None:
                    add_product(ctx.engine, draft, first_batch)
                else:
                    update_product(ctx.engine, product.id, draft)
            except DuplicateProductError as error:
                show_error(name_error, str(error))
                if product is None:
                    offer_existing(error, first_batch)
                return
            except StockError as error:
                show_error(name_error, str(error))
                return
            dialog.close()
            ctx.changed()

        def offer_existing(duplicate: DuplicateProductError, first_batch: BatchDraft | None) -> None:
            def accept(action: Callable[[], None]) -> None:
                action()
                dialog.close()
                ctx.changed()

            def add_to_existing() -> None:
                if first_batch is not None:
                    purchase(ctx.engine, duplicate.product_id, first_batch)

            def restore_existing() -> None:
                restore_product(ctx.engine, duplicate.product_id)

            duplicate_offer.clear()
            with duplicate_offer:
                if duplicate.archived:
                    ui.button("Przywróć z archiwum", on_click=lambda: accept(restore_existing)).props("outline").mark(
                        "duplicate-restore"
                    )
                else:
                    ui.button("Dodaj partię do istniejącego", on_click=lambda: accept(add_to_existing)).props(
                        "outline"
                    ).mark("duplicate-add-batch")
            duplicate_offer.set_visibility(True)

        with ui.row().classes("w-full justify-end"):
            ui.button("Anuluj", on_click=dialog.close).props("flat")
            ui.button("Zapisz", on_click=save).mark("save")
    dialog.open()
