"""Pieces the forms and the card share."""

import flet as ft

DATE_HINT = "DD.MM.RRRR"


def text_field(
    label: str, value: str, key: str, *, number: bool = False, hint: str | None = None, width: int | None = None
) -> ft.TextField:
    return ft.TextField(
        label=label,
        value=value,
        hint_text=hint,
        keyboard_type=ft.KeyboardType.NUMBER if number else ft.KeyboardType.TEXT,
        width=width,
        key=key,
    )


def date_field(label: str, value: str, key: str) -> ft.TextField:
    """An Expiry Date typed as DD.MM.RRRR, on the keyboard of digits and dots."""
    field = text_field(label, value, key, hint=DATE_HINT)
    field.keyboard_type = ft.KeyboardType.DATETIME
    return field


def show_error(field: ft.TextField, message: str | None) -> None:
    # A Text rather than a string, so the tests read it as the user does
    field.error = None if message is None else ft.Text(message, color=ft.Colors.ERROR, size=12)
