"""The window: a header and the four tabs, which all redraw after any change."""

from collections.abc import Callable
from datetime import date
from pathlib import Path

from nicegui import ui
from sqlalchemy import Engine

from home_stock import __version__
from home_stock.sources.app_update import UpdateSource
from home_stock.ui.app_update import update_notice
from home_stock.ui.changelog import announce_new_version, version_label
from home_stock.ui.context import Context
from home_stock.ui.products import ProductsTab
from home_stock.ui.settings import SettingsTab
from home_stock.ui.shopping import ShoppingTab
from home_stock.ui.start import StartTab
from home_stock.ui.theme import apply_theme

APP_TITLE = "Home Stock"
# The favicon; the exe, the installer and the shortcuts use home-stock.ico beside it
APP_ICON = Path(__file__).parent / "assets" / "home-stock.png"
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


def build_shell(
    engine: Engine,
    today: Callable[[], date] = date.today,
    version: str = __version__,
    updates: UpdateSource | None = None,
) -> None:
    """The window on ``engine``; ``updates`` checks GitHub for a newer version (none in the demo and the tests)."""
    refreshers: list[Callable[[], None]] = []

    def changed() -> None:
        undo_bar.hide()
        for refresh in refreshers:
            refresh()

    apply_theme()
    undo_bar = UndoBar(changed)
    ctx = Context(engine, today, ui.element(), changed, undo_bar.show)
    with ui.header().classes("items-center"):
        ui.label(APP_TITLE).classes("text-h6")
        ui.space()
        update_notice(ctx.overlay, updates, version)
        version_label(ctx.overlay, version)
    with ui.tabs().props("align=left active-color=primary indicator-color=primary no-caps").classes("w-full") as tabs:
        ui.tab("start", "Start").mark("tab-start")
        ui.tab("products", "Produkty").mark("tab-products")
        ui.tab("shopping", "Lista zakupów").mark("tab-shopping")
        ui.tab("settings", "Ustawienia").mark("tab-settings")
    with ui.tab_panels(tabs, value="start").classes("w-full"):
        with ui.tab_panel("start").classes("hs-page"):
            refreshers.append(StartTab(ctx).refresh)
        with ui.tab_panel("products").classes("hs-page"):
            refreshers.append(ProductsTab(ctx).refresh)
        with ui.tab_panel("shopping").classes("hs-page"):
            refreshers.append(ShoppingTab(ctx).refresh)
        with ui.tab_panel("settings").classes("hs-page"):
            refreshers.append(SettingsTab(ctx).refresh)
    announce_new_version(ctx.overlay, engine, version)
