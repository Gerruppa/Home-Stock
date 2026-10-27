"""The window: a header and the four tabs, which all redraw after any change."""

from collections.abc import Callable
from datetime import date

from nicegui import ui
from sqlalchemy import Engine

from home_stock.ui.context import Context
from home_stock.ui.products import ProductsTab

APP_TITLE = "Home Stock"


def build_shell(engine: Engine, today: Callable[[], date] = date.today) -> None:
    refreshers: list[Callable[[], None]] = []

    def changed() -> None:
        for refresh in refreshers:
            refresh()

    ctx = Context(engine, today, ui.element(), changed)
    with ui.header().classes("items-center"):
        ui.label(APP_TITLE).classes("text-h6")
    with ui.tabs() as tabs:
        ui.tab("start", "Start").mark("tab-start")
        ui.tab("products", "Produkty").mark("tab-products")
        ui.tab("shopping", "Lista zakupów").mark("tab-shopping")
        ui.tab("settings", "Ustawienia").mark("tab-settings")
    with ui.tab_panels(tabs, value="start").classes("w-full"):
        ui.tab_panel("start")
        with ui.tab_panel("products"):
            refreshers.append(ProductsTab(ctx).refresh)
        ui.tab_panel("shopping")
        ui.tab_panel("settings")
