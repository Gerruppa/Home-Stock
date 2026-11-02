"""The window: a header and the four tabs, which all redraw after any change."""

from collections.abc import Callable
from datetime import date
from pathlib import Path

from nicegui import ui
from nicegui.events import KeyEventArguments
from sqlalchemy import Engine

from home_stock import __version__
from home_stock.persistence.catalog import StockError
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
        self.bar = ui.row().classes("fixed-bottom q-ma-md q-pa-sm items-center hs-undo-bar text-white rounded-borders")
        self.bar.mark("undo-bar")
        self.bar.set_visibility(False)
        self.timer: ui.timer | None = None

    def show(self, message: str, action: Callable[[], None]) -> None:
        def undo() -> None:
            try:
                action()
            except StockError as problem:
                # Changed meanwhile, e.g. in another window: show the stock as it is and say why nothing was undone
                self.changed()
                self.say(str(problem))
                return
            self.changed()

        self.say(message)
        with self.bar:
            ui.button("Cofnij", on_click=undo).props("flat color=amber").mark("undo")

    def say(self, message: str) -> None:
        """Show ``message`` in the bar for a while, without Cofnij."""
        self.hide()
        with self.bar:
            ui.label(message)
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
    with ui.tab_panels(tabs, value="start").classes("w-full") as panels:
        with ui.tab_panel("start").classes("hs-page"):
            refreshers.append(StartTab(ctx).refresh)
        with ui.tab_panel("products").classes("hs-page"):
            products = ProductsTab(ctx)
            refreshers.append(products.refresh)
        with ui.tab_panel("shopping").classes("hs-page"):
            refreshers.append(ShoppingTab(ctx).refresh)
        with ui.tab_panel("settings").classes("hs-page"):
            refreshers.append(SettingsTab(ctx).refresh)
    _focus_search_keys(panels, products)
    announce_new_version(ctx.overlay, engine, version)


def _focus_search_keys(panels: ui.tab_panels, products: ProductsTab) -> None:
    """The Produkty search takes the cursor when the tab opens, and again on Ctrl+F while the tab is shown."""

    def opened() -> None:
        if panels.value == "products":
            products.focus_search()

    def pressed(event: KeyEventArguments) -> None:
        if event.action.keydown and event.modifiers.ctrl and event.key == "f" and panels.value == "products":
            products.focus_search()

    panels.on_value_change(opened)
    ui.keyboard(pressed, ignore=[])
    # The keyboard event cannot stop the browser's own find box, so a script does, on Produkty only
    ui.run_javascript(
        "document.addEventListener('keydown', (e) => {"
        " if (e.ctrlKey && e.key === 'f' && document.querySelector('.q-tab--active')?.textContent.includes('Produkty'))"
        " e.preventDefault(); });"
    )
