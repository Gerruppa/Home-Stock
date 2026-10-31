"""Produkty: every active Product under its Category, with a search box."""

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from home_stock.domain.formatting import format_quantity
from home_stock.domain.stock import Product, is_running_low, name_key
from home_stock.persistence.catalog import list_categories, list_units
from home_stock.persistence.products import list_products, restore_batch, use_one
from home_stock.ui.context import Context
from home_stock.ui.product_card import open_product_card
from home_stock.ui.product_form import open_product_form


class ProductsTab:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.search = ""
        with ui.row().classes("w-full items-center"):
            search = ui.input("Szukaj", on_change=self._searched).props("clearable outlined dense")
            search.classes("grow").mark("search")
            ui.button("Dodaj produkt", icon="add", on_click=lambda: open_product_form(ctx)).mark("add-product")
        self.content = ui.column().classes("w-full gap-4")
        self.refresh()

    def _searched(self, event: ValueChangeEventArguments[str | None]) -> None:
        self.search = event.value or ""
        self.refresh()

    def refresh(self) -> None:
        engine = self.ctx.engine
        products = list_products(engine)
        units = {unit.id: unit for unit in list_units(engine)}
        self.content.clear()
        with self.content:
            if not products:
                ui.label("Nie masz jeszcze produktów.")
                return
            wanted = name_key(self.search)
            for category in list_categories(engine):
                shown = [p for p in products if p.category_id == category.id and wanted in name_key(p.name)]
                if not shown:
                    continue
                with ui.column().classes("w-full gap-0 hs-section hs-category").mark(f"category-{category.id}"):
                    ui.label(category.name).classes("hs-section-title q-mb-xs")
                    for product in shown:
                        with ui.row().classes("w-full items-center no-wrap hs-line").mark(f"product-{product.id}"):
                            name = ui.label(product.name).classes("grow cursor-pointer")
                            name.on("click", lambda p=product: open_product_card(self.ctx, p.id)).mark(
                                f"open-{product.id}"
                            )
                            quantity = ui.label(
                                format_quantity(product.quantity, units[product.unit_id], product.pack_size)
                            ).classes("hs-qty")
                            if is_running_low(product):
                                quantity.classes("hs-qty-low")
                            use = ui.button("−1", on_click=lambda p=product: self._use(p)).props("dense outline")
                            use.mark(f"use-{product.id}").set_enabled(product.quantity > 0)

    def _use(self, product: Product) -> None:
        engine = self.ctx.engine
        batch_before = use_one(engine, product.id)
        if batch_before is None:
            return
        self.ctx.changed()
        self.ctx.undo(f"Zużyto 1 × {product.name}", lambda: restore_batch(engine, batch_before))
