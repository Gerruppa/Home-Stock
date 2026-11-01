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
    # Redraws every tab after a change, and withdraws the Cofnij offered for an earlier one
    changed: Callable[[], None]
    # Shows what was just done with "Cofnij" for a while; Cofnij runs the action given, then redraws every tab. A
    # StockError from the action (changed meanwhile) shows its message in the bar instead. Call it after changed(),
    # which hides the bar
    undo: Callable[[str, Callable[[], None]], None]
