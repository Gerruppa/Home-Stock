"""Driving the Android app's controls in tests, without a page or a phone: Flet controls are dataclasses, so their
tree is walked field by field, controls are found by their ``key``, and a tap calls the handler a tap would."""

from collections.abc import Iterator
from dataclasses import dataclass, field, fields
from typing import Any

import flet as ft


def walk(control: ft.Control, *, visible_only: bool = False) -> Iterator[ft.Control]:
    """``control`` and every control under it, each before its children and children in the order of their fields
    and lists (a Column's top to bottom); with ``visible_only``, without hidden controls and what is under them."""
    seen: set[int] = set()
    stack = [control]
    while stack:
        current = stack.pop()
        if id(current) in seen or (visible_only and not current.visible):
            continue
        seen.add(id(current))
        yield current
        children: list[ft.Control] = []
        for item in fields(current):
            if item.name.startswith("_"):
                continue
            value = getattr(current, item.name, None)
            if isinstance(value, ft.Control):
                children.append(value)
            elif isinstance(value, list | tuple):
                children.extend(child for child in value if isinstance(child, ft.Control))
        # Reversed onto the stack, so the first child comes out first
        stack.extend(reversed(children))


def find(root: ft.Control, key: str) -> ft.Control:
    """The one control under ``root`` with ``key``; fails when there is none or more than one."""
    found = [control for control in walk(root) if control.key == key]
    assert len(found) == 1, f"{len(found)} controls with key {key!r}"
    return found[0]


def absent(root: ft.Control, key: str) -> bool:
    return all(control.key != key for control in walk(root))


def texts(root: ft.Control) -> list[str]:
    """Every Text value under ``root`` that is not hidden, in reading order: what the user reads."""
    return [
        control.value for control in walk(root, visible_only=True) if isinstance(control, ft.Text) and control.value
    ]


def tap(control: ft.Control, handler: str = "on_click") -> None:
    """Call ``control``'s ``handler`` as Flet does when the user taps it."""
    callback = getattr(control, handler)
    assert callback is not None, f"{type(control).__name__} has no {handler}"
    callback(ft.Event(handler.removeprefix("on_"), control))


def select(bar: ft.NavigationBar, index: int) -> None:
    """Tap the navigation bar's destination at ``index``."""
    bar.selected_index = index
    tap(bar, "on_change")


@dataclass
class Screen:
    """Stands in for the page: records the snackbars shown, how often controls were sent to the screen and the texts
    put on the clipboard or shared, and holds the page's stack of views, the tabs' first."""

    presented: list[ft.SnackBar] = field(default_factory=list)
    updates: int = 0
    copied: list[str] = field(default_factory=list)
    shared: list[str] = field(default_factory=list)
    views: list[ft.View] = field(default_factory=lambda: [ft.View()])
    # The top view's texts as last sent to the screen: a control changed after the latest update never shows
    shown: list[str] = field(default_factory=list)

    @property
    def top(self) -> ft.View:
        """The view the user sees."""
        return self.views[-1]

    def present(self, snackbar: ft.SnackBar) -> None:
        # Page.show_dialog opens it
        snackbar.open = True
        self.presented.append(snackbar)

    def copy(self, text: str) -> None:
        self.copied.append(text)

    def share(self, text: str) -> None:
        self.shared.append(text)

    def update(self, *_: Any) -> None:
        self.updates += 1
        self.shown = texts(self.top)
