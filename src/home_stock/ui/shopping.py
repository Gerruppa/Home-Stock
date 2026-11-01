"""Lista zakupów: every Product Running Low under its Category, each bought through the Purchase dialog."""

import json

from nicegui import ui

from home_stock.domain.formatting import format_purchase_amount, format_quantity, format_shopping_list
from home_stock.domain.stock import is_running_low
from home_stock.persistence.catalog import list_categories, list_units
from home_stock.persistence.products import list_products
from home_stock.ui.context import Context
from home_stock.ui.purchase_dialog import open_purchase_dialog


class ShoppingTab:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.content = ui.column().classes("w-full gap-4")
        self.refresh()

    @staticmethod
    def _copy(text: str) -> None:
        ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(text)})")
        ui.notify("Skopiowano listę zakupów.")

    def refresh(self) -> None:
        engine = self.ctx.engine
        products = [p for p in list_products(engine) if is_running_low(p)]
        units = {unit.id: unit for unit in list_units(engine)}
        self.content.clear()
        with self.content:
            if not products:
                ui.label("Nic nie trzeba kupować.")
                return
            categories = list_categories(engine)
            text = format_shopping_list(categories, units, products)
            ui.button("Kopiuj listę", icon="content_copy", on_click=lambda: self._copy(text)).props(
                "dense outline"
            ).mark("copy-list")
            for category in categories:
                shown = [p for p in products if p.category_id == category.id]
                if not shown:
                    continue
                with (
                    ui.column()
                    .classes("w-full gap-0 hs-section hs-running-low")
                    .mark(f"shopping-category-{category.id}")
                ):
                    ui.label(category.name).classes("hs-section-title q-mb-xs")
                    for product in shown:
                        with ui.row().classes("w-full items-center no-wrap hs-line").mark(f"shopping-{product.id}"):
                            ui.label(product.name).classes("grow")
                            ui.label(
                                format_quantity(product.quantity, units[product.unit_id], product.pack_size)
                            ).classes("hs-qty")
                            ui.label(format_purchase_amount(product, units[product.unit_id])).classes("hs-qty")
                            ui.button(
                                "Kupione", icon="check", on_click=lambda p=product: open_purchase_dialog(self.ctx, p)
                            ).props("dense outline").mark(f"bought-{product.id}")
