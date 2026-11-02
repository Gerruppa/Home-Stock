"""The keys every dialog answers to: Enter saves it as its main button would, Esc closes it without saving."""

from collections.abc import Callable

from nicegui import ui

# Enter on a button or a select does that element's own job (press it, pick from the list), not the dialog's
_ENTER_ELSEWHERE = "(event) => { if (!event.target.closest('button, .q-select')) emit() }"
# Esc in a select closes its list first; Quasar's own Esc closes the dialog when no list is open
_ESC_ELSEWHERE = "(event) => { if (!event.target.closest('.q-select')) emit() }"


def wire_dialog_keys(dialog: ui.dialog, card: ui.card, save: Callable[[], object] | None = None) -> None:
    """Make ``card``, the dialog's content, close ``dialog`` on Esc and call ``save`` on Enter (no Enter key without
    ``save``). A validation error stays shown as with the button, since ``save`` is the button's own handler."""
    card.on("keydown.esc", dialog.close, js_handler=_ESC_ELSEWHERE)
    if save is not None:
        card.on("keydown.enter", lambda: save(), js_handler=_ENTER_ELSEWHERE)
