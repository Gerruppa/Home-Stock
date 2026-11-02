"""Lista zakupów: every Product Running Low under its Category, each bought through the Purchase dialog."""

import json
from datetime import date

from nicegui import ui
from sqlalchemy import Engine

from home_stock.domain.formatting import (
    format_purchase_amount,
    format_quantity,
    format_shopping_list,
    format_shopping_reason,
)
from home_stock.persistence.catalog import list_categories, list_units
from home_stock.persistence.products import list_shopping_list
from home_stock.ui.context import Context
from home_stock.ui.purchase_dialog import open_purchase_dialog
from home_stock.ui.unpacking_dialog import open_unpacking_dialog

# Where "Drukuj" opens the printable list (served by print_list.py)
PRINT_PATH = "/drukuj"


def shopping_list_text(engine: Engine, today: date) -> str:
    """The Shopping List as plain text, what "Kopiuj listę" copies and the printable page shows."""
    units = {unit.id: unit for unit in list_units(engine)}
    products = [entry.product for entry in list_shopping_list(engine, today)]
    return format_shopping_list(list_categories(engine), units, products)


class ShoppingTab:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.content = ui.column().classes("w-full gap-4")
        self.refresh()

    @staticmethod
    def _copy_list(text: str) -> None:
        ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(text)})")
        ui.notify("Skopiowano listę zakupów.")

    def refresh(self) -> None:
        engine = self.ctx.engine
        entries = list_shopping_list(engine, self.ctx.today())
        products = [entry.product for entry in entries]
        units = {unit.id: unit for unit in list_units(engine)}
        categories = list_categories(engine)
        self.content.clear()
        with self.content:
            with ui.row().classes("gap-2"):
                ui.button(
                    "Rozpakuj zakupy", icon="inventory_2", on_click=lambda: open_unpacking_dialog(self.ctx)
                ).props("dense outline").mark("unpack")
                if products:
                    text = format_shopping_list(categories, units, products)
                    ui.button("Kopiuj listę", icon="content_copy", on_click=lambda: self._copy_list(text)).props(
                        "dense outline"
                    ).mark("copy-list")
                    # A new window, so the list stays on screen; the native window hands it to the default browser
                    ui.button("Drukuj", icon="print", on_click=lambda: ui.navigate.to(PRINT_PATH, new_tab=True)).props(
                        "dense outline"
                    ).mark("print-list")
            if not products:
                ui.label("Nic nie trzeba kupować.")
                return
            for category in categories:
                shown = [e for e in entries if e.product.category_id == category.id]
                if not shown:
                    continue
                with (
                    ui.column()
                    .classes("w-full gap-0 hs-section hs-running-low")
                    .mark(f"shopping-category-{category.id}")
                ):
                    ui.label(category.name).classes("hs-section-title q-mb-xs")
                    for entry in shown:
                        product = entry.product
                        with ui.row().classes("w-full items-center no-wrap hs-line").mark(f"shopping-{product.id}"):
                            ui.label(product.name).classes("grow")
                            ui.label(format_shopping_reason(entry)).classes("hs-muted text-sm")
                            unit = units[product.unit_id]
                            ui.label(format_quantity(product.quantity, unit, product.pack_size)).classes("hs-qty")
                            ui.label(format_purchase_amount(product, unit)).classes("hs-qty")
                            ui.button(
                                "Kupione", icon="check", on_click=lambda p=product: open_purchase_dialog(self.ctx, p)
                            ).props("dense outline").mark(f"bought-{product.id}")
