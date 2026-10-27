"""Pieces the forms and dialogs share."""

from nicegui import ui


def error_label() -> ui.label:
    """A hidden label under a field for show_error; a label, not the error-message prop, so tests can read it."""
    label = ui.label().classes("text-negative text-caption")
    label.set_visibility(False)
    return label


def show_error(label: ui.label, message: str | None) -> None:
    label.set_text(message or "")
    label.set_visibility(message is not None)
