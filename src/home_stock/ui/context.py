"""What every tab and dialog gets from the shell."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from nicegui import ui
from sqlalchemy import Engine


@dataclass
class Context:
    engine: Engine
    today: Callable[[], date]
    # Dialogs are opened inside it: an element that outlives every tab's redraw, so a redraw never deletes one
    overlay: ui.element
    # Redraws every tab after a change
    changed: Callable[[], None]
