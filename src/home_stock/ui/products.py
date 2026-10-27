"""Produkty: every active Product under its Category, with a search box."""

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from home_stock.domain.formatting import format_quantity
from home_stock.domain.stock import name_key
from home_stock.persistence.catalog import list_categories, list_units
from home_stock.persistence.products import list_products
from home_stock.ui.context import Context
from home_stock.ui.product_form import open_product_form


class ProductsTab:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.search = ""
        with ui.row().classes("w-full items-center"):
            ui.input("Szukaj", on_change=self._searched).props("clearable").mark("search")
            ui.button("Dodaj produkt", icon="add", on_click=lambda: open_product_form(ctx)).mark("add-product")
        self.content = ui.column().classes("w-full")
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
            for category in sorted(list_categories(engine), key=lambda c: name_key(c.name)):
                shown = [p for p in products if p.category_id == category.id and wanted in name_key(p.name)]
                if not shown:
                    continue
                with ui.column().classes("w-full gap-1").mark(f"category-{category.id}"):
                    ui.label(category.name).classes("text-subtitle1 text-weight-medium")
                    for product in shown:
                        with ui.row().classes("w-full items-center").mark(f"product-{product.id}"):
                            ui.label(product.name).classes("grow")
                            ui.label(format_quantity(product.quantity, units[product.unit_id], product.pack_size))
