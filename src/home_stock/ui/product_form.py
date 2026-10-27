"""The dialog that adds a Product, optionally with its first Batch."""

from nicegui import ui

from home_stock.domain.formatting import parse_count, parse_pack_size
from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.catalog import StockError, list_categories, list_units
from home_stock.persistence.products import add_product
from home_stock.ui.context import Context
from home_stock.ui.fields import error_label, show_error


def open_product_form(ctx: Context) -> None:
    categories = list_categories(ctx.engine)
    units = list_units(ctx.engine)
    with ctx.overlay, ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("Nowy produkt").classes("text-h6")
        name = ui.input("Nazwa").classes("w-full").mark("name")
        name_error = error_label()
        category = ui.select({c.id: c.name for c in categories}, label="Kategoria", value=categories[0].id)
        category.classes("w-full").mark("category")
        unit = ui.select({u.id: u.name for u in units}, label="Jednostka", value=units[0].id)
        unit.classes("w-full").mark("unit")
        pack_size = ui.input("Rozmiar opakowania (opcjonalnie)", placeholder="np. 1 kg").classes("w-full")
        pack_size.mark("pack-size")
        pack_size_error = error_label()
        # Cleared, the Product has no Minimum Stock and never goes on the Shopping List
        minimum_stock = ui.input("Stan minimalny", value="1").classes("w-full").mark("minimum-stock")
        minimum_stock_error = error_label()
        first_quantity = ui.input("Ilość na start (opcjonalnie)").classes("w-full").mark("first-quantity")
        quantity_error = error_label()

        def save() -> None:
            draft = first_batch = size = minimum = None
            valid = True
            try:
                # A cleared field holds None
                size = parse_pack_size(pack_size.value or "")
                show_error(pack_size_error, None)
            except ValueError as error:
                show_error(pack_size_error, str(error))
                valid = False
            try:
                minimum = parse_count(minimum_stock.value or "", allow_blank=True)
                show_error(minimum_stock_error, None)
            except ValueError as error:
                show_error(minimum_stock_error, str(error))
                valid = False
            try:
                draft = ProductDraft(name.value or "", category.value, unit.value, size, minimum)
                show_error(name_error, None)
            except ValueError as error:
                show_error(name_error, str(error))
            try:
                count = parse_count(first_quantity.value or "", allow_blank=True)
                # A first Quantity of 0 means no first Batch, as Batches are never empty
                first_batch = None if not count else BatchDraft(count)
                show_error(quantity_error, None)
            except ValueError as error:
                show_error(quantity_error, str(error))
                return
            if draft is None or not valid:
                return
            try:
                add_product(ctx.engine, draft, first_batch)
            except StockError as error:
                show_error(name_error, str(error))
                return
            dialog.close()
            ctx.changed()

        with ui.row().classes("w-full justify-end"):
            ui.button("Anuluj", on_click=dialog.close).props("flat")
            ui.button("Zapisz", on_click=save).mark("save")
    dialog.open()
