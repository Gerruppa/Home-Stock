"""What every tab and dialog gets from the shell."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import flet as ft
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
    # Shows a message in the snackbar for a while, without Cofnij
    say: Callable[[str], None]
    # Puts text on the phone's clipboard
    copy: Callable[[str], None]
    # Hands text to Android's share sheet
    share: Callable[[str], None]
    # Shows a form, the phone's dialog, as a view over the tabs until close_full_screen() or Android's Back
    show_full_screen: Callable[[ft.Control], None]
    close_full_screen: Callable[[], None]
