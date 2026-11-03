"""The screen: the five tabs behind a bottom navigation bar, which all redraw after any change, and the undo snackbar.

The shell never touches the Flet page itself: it is handed how to show a snackbar and how to send changes to the
screen, so the tests drive it without a page."""

from collections.abc import Callable
from datetime import date
from typing import Protocol

import flet as ft
from sqlalchemy import Engine

from home_stock.mobile.context import Context
from home_stock.mobile.products import ProductsTab
from home_stock.persistence.catalog import StockError

APP_TITLE = "Home Stock"
# How long the undo snackbar offers Cofnij
UNDO_MILLISECONDS = 8000


class Tab(Protocol):
    control: ft.Control

    def refresh(self) -> None: ...


class ComingSoonTab:
    """A tab not rewritten for the phone yet."""

    def __init__(self) -> None:
        self.control: ft.Control = ft.Container(ft.Text("Wkrótce"), padding=24, key="coming-soon")

    def refresh(self) -> None:
        pass


class UndoBar:
    """One snackbar at the bottom of the screen. Any change hides it (Context.changed), so Cofnij only ever takes back
    the latest action, never one that later changes have built on."""

    def __init__(
        self, changed: Callable[[], None], present: Callable[[ft.SnackBar], None], update: Callable[[], None]
    ) -> None:
        self.changed = changed
        self.present = present
        self.update = update
        self.snackbar = ft.SnackBar(ft.Text(""), duration=UNDO_MILLISECONDS, key="undo-bar")

    def show(self, message: str, action: Callable[[], None]) -> None:
        def undo(_: ft.Event[ft.SnackBar]) -> None:
            try:
                action()
            except StockError as problem:
                # Changed meanwhile: show the stock as it is and say why nothing was undone
                self.changed()
                self.say(str(problem))
                return
            self.changed()

        self._open(message, "Cofnij", undo)

    def say(self, message: str) -> None:
        """Show ``message`` in the snackbar for a while, without Cofnij."""
        self._open(message, None, None)

    def hide(self) -> None:
        if self.snackbar.open:
            self.snackbar.open = False
            self.update()

    def _open(
        self, message: str, action: str | None, on_action: Callable[[ft.Event[ft.SnackBar]], None] | None
    ) -> None:
        self.snackbar.content = ft.Text(message)
        self.snackbar.action = action
        self.snackbar.on_action = on_action
        if self.snackbar.open:
            self.update()
        else:
            self.present(self.snackbar)


class Shell:
    """The five tabs on ``engine``, Start first. ``present`` shows a snackbar (Page.show_dialog) and ``update`` sends
    changed controls to the screen (Page.update)."""

    def __init__(
        self,
        engine: Engine,
        present: Callable[[ft.SnackBar], None],
        update: Callable[[], None],
        today: Callable[[], date] = date.today,
    ) -> None:
        self.update = update
        self.undo_bar = UndoBar(self.changed, present, update)
        self.ctx = Context(engine, today, update, self.changed, self.undo_bar.show)
        self.tabs: list[tuple[ft.IconData, str, Tab]] = [
            (ft.Icons.HOME_OUTLINED, "Start", ComingSoonTab()),
            (ft.Icons.INVENTORY_2_OUTLINED, "Produkty", ProductsTab(self.ctx)),
            (ft.Icons.CHECKLIST, "Zakupy", ComingSoonTab()),
            (ft.Icons.HISTORY, "Historia", ComingSoonTab()),
            (ft.Icons.SETTINGS_OUTLINED, "Ustawienia", ComingSoonTab()),
        ]
        self.navigation_bar = ft.NavigationBar(
            destinations=[
                ft.NavigationBarDestination(icon=icon, label=label, key=f"tab-{index}")
                for index, (icon, label, _) in enumerate(self.tabs)
            ],
            selected_index=0,
            on_change=self._selected,
        )
        self.body = ft.Container(self.tabs[0][2].control, expand=True, key="tab-body")

    def changed(self) -> None:
        self.undo_bar.hide()
        for _, _, tab in self.tabs:
            tab.refresh()
        self.update()

    def select(self, index: int) -> None:
        """Show the tab at ``index``, as a tap on its destination does."""
        self.navigation_bar.selected_index = index
        self.body.content = self.tabs[index][2].control
        self.update()

    def _selected(self, event: ft.Event[ft.NavigationBar]) -> None:
        self.select(event.control.selected_index)
