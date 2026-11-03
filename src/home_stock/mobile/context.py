"""What every tab and dialog gets from the shell."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from sqlalchemy import Engine


@dataclass
class Context:
    engine: Engine
    today: Callable[[], date]
    # Sends controls a tab changed by itself (e.g. after a search) to the screen
    update: Callable[[], None]
    # Redraws every tab after a change, and withdraws the Cofnij offered for an earlier one
    changed: Callable[[], None]
    # Shows what was just done with "Cofnij" in a snackbar; Cofnij runs the action given, then redraws every tab. A
    # StockError from the action (changed meanwhile) shows its message in the snackbar instead. Call it after
    # changed(), which hides the snackbar
    undo: Callable[[str, Callable[[], None]], None]
