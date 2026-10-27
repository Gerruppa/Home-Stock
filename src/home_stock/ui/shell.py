"""The window: a header and the four tabs, which all redraw after any change."""

from collections.abc import Callable
from datetime import date

from nicegui import ui
from sqlalchemy import Engine

from home_stock.ui.context import Context
from home_stock.ui.products import ProductsTab

APP_TITLE = "Home Stock"
# How long the undo bar offers Cofnij
UNDO_SECONDS = 8.0


class UndoBar:
    """One bar at the bottom of the window. Any change hides it (Context.changed), so Cofnij only ever takes back the
    latest action, never one that later changes have built on."""

    def __init__(self, changed: Callable[[], None]) -> None:
        self.changed = changed
        self.bar = ui.row().classes("fixed-bottom q-ma-md q-pa-sm items-center bg-grey-9 text-white rounded-borders")
        self.bar.mark("undo-bar")
        self.bar.set_visibility(False)
        self.timer: ui.timer | None = None

    def show(self, message: str, action: Callable[[], None]) -> None:
        def undo() -> None:
            action()
            self.changed()

        self.hide()
        with self.bar:
            ui.label(message)
            ui.button("Cofnij", on_click=undo).props("flat color=amber").mark("undo")
            self.timer = ui.timer(UNDO_SECONDS, self.hide, once=True)
        self.bar.set_visibility(True)

    def hide(self) -> None:
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None
        self.bar.clear()
        self.bar.set_visibility(False)


def build_shell(engine: Engine, today: Callable[[], date] = date.today) -> None:
    refreshers: list[Callable[[], None]] = []

    def changed() -> None:
        undo_bar.hide()
        for refresh in refreshers:
            refresh()

    undo_bar = UndoBar(changed)
    ctx = Context(engine, today, ui.element(), changed, undo_bar.show)
    with ui.header().classes("items-center"):
        ui.label(APP_TITLE).classes("text-h6")
    with ui.tabs() as tabs:
        ui.tab("start", "Start").mark("tab-start")
        ui.tab("products", "Produkty").mark("tab-products")
        ui.tab("shopping", "Lista zakupów").mark("tab-shopping")
        ui.tab("settings", "Ustawienia").mark("tab-settings")
    # Opens on Produkty while Start has no content yet (#7)
    with ui.tab_panels(tabs, value="products").classes("w-full"):
        ui.tab_panel("start")
        with ui.tab_panel("products"):
            refreshers.append(ProductsTab(ctx).refresh)
        ui.tab_panel("shopping")
        ui.tab_panel("settings")
