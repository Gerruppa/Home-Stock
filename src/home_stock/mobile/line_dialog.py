"""The full-screen form that changes a List Line: a Product line's Quantity, or a free-text line's text."""

import flet as ft

from home_stock.domain.custom_lists import ListLine, ListLineDraft
from home_stock.domain.formatting import parse_count
from home_stock.mobile.context import Context
from home_stock.mobile.fields import show_error, text_field
from home_stock.persistence.catalog import StockError
from home_stock.persistence.custom_lists import change_line


def open_line_dialog(ctx: Context, line: ListLine, name: str) -> None:
    """``name`` is what the line reads as: the Product's name, or the line's text."""
    product_id = line.product_id
    if product_id is None:
        title, field = "Zmień tekst", text_field("Tekst", line.text or "", "line-edit-field")
    else:
        title = f"Zmień ilość: {name}"
        field = text_field("Ilość", str(line.quantity), "line-edit-field", number=True)

    def save(_: object) -> None:
        try:
            if product_id is None:
                draft = ListLineDraft.note(field.value or "")
            else:
                count = parse_count(field.value)
                assert count is not None
                draft = ListLineDraft.product(product_id, count)
        except ValueError as problem:
            show_error(field, str(problem))
            ctx.update()
            return
        engine = ctx.engine
        ctx.close_full_screen()
        try:
            before = change_line(engine, line.id, draft)
        except StockError as problem:
            ctx.changed()
            ctx.say(str(problem))
            return

        def undo() -> None:
            change_line(engine, line.id, before)

        ctx.changed()
        ctx.undo(f"Zmieniono: {name}", undo)

    field.on_submit = save
    ctx.show_full_screen(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.IconButton(
                            ft.Icons.CLOSE,
                            tooltip="Anuluj",
                            on_click=lambda _: ctx.close_full_screen(),
                            key="line-edit-cancel",
                        ),
                        ft.Text(title, size=20, expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.FilledButton("Zapisz", on_click=save, key="line-edit-save"),
                        ft.Container(width=8),
                    ]
                ),
                ft.Container(field, padding=ft.Padding.symmetric(horizontal=16, vertical=8)),
            ],
            key="line-edit-dialog",
        )
    )
