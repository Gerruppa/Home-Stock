"""The full-screen form that adds a Product, optionally with its first Batch, or edits one."""

from collections.abc import Callable

import flet as ft

from home_stock.domain.formatting import format_pack_size, parse_count, parse_pack_size, parse_usual_shelf_life
from home_stock.domain.stock import BatchDraft, Product, ProductDraft, default_expiry
from home_stock.mobile.context import Context
from home_stock.mobile.fields import show_error, text_field
from home_stock.persistence.catalog import StockError, list_categories, list_units
from home_stock.persistence.products import (
    DuplicateProductError,
    add_product,
    get_product,
    purchase,
    restore_product,
    undo_add_product,
    update_product,
)


def open_product_form(ctx: Context, product: Product | None = None) -> None:
    """A new Product when ``product`` is None, else that Product's fields filled in for editing."""
    categories = list_categories(ctx.engine)
    units = list_units(ctx.engine)
    name = text_field("Nazwa", "" if product is None else product.name, "name")
    # Shown when a new Product's name exists: offers the first Batch to the existing Product instead, or, when it is
    # Archived, restoring it
    duplicate_offer = ft.Column(key="duplicate-offer")

    def name_changed(_: ft.Event[ft.TextField]) -> None:
        if duplicate_offer.controls:
            duplicate_offer.controls = []
            ctx.update()

    name.on_change = name_changed
    category = ft.Dropdown(
        label="Kategoria",
        options=[ft.DropdownOption(key=str(c.id), text=c.name) for c in categories],
        value=str(categories[0].id if product is None else product.category_id),
        expand=True,
        key="category",
    )
    unit = ft.Dropdown(
        label="Jednostka",
        options=[ft.DropdownOption(key=str(u.id), text=u.name) for u in units],
        value=str(units[0].id if product is None else product.unit_id),
        expand=True,
        key="unit",
    )
    pack_size = text_field(
        "Rozmiar opakowania (opcjonalnie)",
        "" if product is None or product.pack_size is None else format_pack_size(product.pack_size),
        "pack-size",
        hint="np. 1 kg",
    )
    # Cleared, the Product has no Minimum Stock and never goes on the Shopping List
    minimum_text = "1" if product is None else "" if product.minimum_stock is None else str(product.minimum_stock)
    minimum_stock = text_field("Stan minimalny", minimum_text, "minimum-stock", number=True)
    usual_shelf_life = text_field(
        "Zwykle ważne, dni (opcjonalnie)",
        "" if product is None or product.usual_shelf_life_days is None else str(product.usual_shelf_life_days),
        "shelf-life",
        number=True,
        hint="np. 7",
    )
    # Batches of an existing Product are edited on its card, not here
    first_quantity = (
        None if product is not None else text_field("Ilość na start (opcjonalnie)", "", "first-quantity", number=True)
    )

    def parsed[T](field: ft.TextField, parse: Callable[[str], T]) -> tuple[T | None, bool]:
        try:
            value = parse(field.value or "")
        except ValueError as error:
            show_error(field, str(error))
            return None, False
        show_error(field, None)
        return value, True

    def save(_: ft.Event[ft.Button]) -> None:
        duplicate_offer.controls = []
        size, size_ok = parsed(pack_size, parse_pack_size)
        minimum, minimum_ok = parsed(minimum_stock, lambda text: parse_count(text, allow_blank=True))
        days, days_ok = parsed(usual_shelf_life, parse_usual_shelf_life)
        draft = parsed(
            name,
            lambda text: ProductDraft(text, int(category.value or 0), int(unit.value or 0), size, minimum, days),
        )[0]
        first_batch = None
        quantity_ok = True
        if first_quantity is not None:
            quantity, quantity_ok = parsed(first_quantity, lambda text: parse_count(text, allow_blank=True))
            # A first Quantity of 0 means no first Batch, as Batches are never empty
            first_batch = BatchDraft(quantity, default_expiry(days, ctx.today())) if quantity else None
        if draft is None or not (size_ok and minimum_ok and days_ok and quantity_ok):
            ctx.update()
            return
        try:
            if product is None:
                product_id = add_product(ctx.engine, draft, first_batch)
            else:
                update_product(ctx.engine, product.id, draft)
        except DuplicateProductError as error:
            show_error(name, str(error))
            if product is None:
                offer_existing(error, first_batch)
            ctx.update()
            return
        except StockError as error:
            show_error(name, str(error))
            ctx.update()
            return
        ctx.close_full_screen()
        ctx.changed()
        if product is None:
            ctx.undo(f"Dodano: {draft.name}", lambda: undo_add_product(ctx.engine, product_id))

    def offer_existing(duplicate: DuplicateProductError, first_batch: BatchDraft | None) -> None:
        def accept(action: Callable[[], None]) -> None:
            action()
            ctx.close_full_screen()
            ctx.changed()

        def add_to_existing() -> None:
            if first_batch is not None:
                # Dated by the existing Product's Usual Shelf Life, as its Purchase dialog would, not by this form's
                existing = get_product(ctx.engine, duplicate.product_id)
                expiry = default_expiry(existing.usual_shelf_life_days, ctx.today())
                purchase(ctx.engine, duplicate.product_id, BatchDraft(first_batch.quantity, expiry), ctx.today())

        def restore_existing() -> None:
            restore_product(ctx.engine, duplicate.product_id)

        if duplicate.archived:
            offer = ft.OutlinedButton(
                "Przywróć z archiwum", on_click=lambda _: accept(restore_existing), key="duplicate-restore"
            )
        else:
            offer = ft.OutlinedButton(
                "Dodaj partię do istniejącego", on_click=lambda _: accept(add_to_existing), key="duplicate-add-batch"
            )
        duplicate_offer.controls = [offer]

    fields: list[ft.Control] = [name, duplicate_offer, category, unit, pack_size, minimum_stock, usual_shelf_life]
    if first_quantity is not None:
        fields.append(first_quantity)
    ctx.show_full_screen(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.IconButton(
                            ft.Icons.CLOSE, tooltip="Anuluj", on_click=lambda _: ctx.close_full_screen(), key="cancel"
                        ),
                        ft.Text("Nowy produkt" if product is None else "Edytuj produkt", size=20, expand=True),
                        ft.FilledButton("Zapisz", on_click=save, key="save"),
                        ft.Container(width=8),
                    ],
                ),
                ft.ListView(fields, spacing=12, padding=ft.Padding.symmetric(horizontal=16, vertical=8), expand=True),
            ],
            expand=True,
            key="product-form",
        )
    )
