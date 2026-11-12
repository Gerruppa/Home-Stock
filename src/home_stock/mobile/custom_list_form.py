"""The full-screen form that makes or edits a Custom List: a name and an optional date of the occasion."""

from collections.abc import Callable

import flet as ft

from home_stock.domain.custom_lists import CustomList, CustomListDraft
from home_stock.domain.formatting import format_date, parse_date
from home_stock.mobile.context import Context
from home_stock.mobile.fields import date_field, show_error, text_field
from home_stock.persistence.catalog import StockError
from home_stock.persistence.custom_lists import edit_custom_list, make_custom_list, undo_make_custom_list


def open_custom_list_form(ctx: Context, on_made: Callable[[int], None], custom_list: CustomList | None = None) -> None:
    """Nowa lista, or Edytuj listę with ``custom_list``; ``on_made`` gets a new list's id before the tabs are
    redrawn, so Zakupy can select it."""
    name = text_field(
        "Nazwa", "" if custom_list is None else custom_list.name, "custom-list-name", hint="np. Kolacja w sobotę"
    )
    when = None if custom_list is None else custom_list.occasion
    occasion = date_field("Data (opcjonalnie)", "" if when is None else format_date(when), "custom-list-occasion")

    def read() -> CustomListDraft | None:
        when = None
        try:
            when = parse_date(occasion.value)
        except ValueError as error:
            show_error(occasion, str(error))
        else:
            show_error(occasion, None)
        try:
            draft = CustomListDraft(name.value or "", when)
        except ValueError as error:
            show_error(name, str(error))
            return None
        show_error(name, None)
        return None if occasion.error is not None else draft

    def save(_: object) -> None:
        draft = read()
        if draft is None:
            ctx.update()
            return
        engine = ctx.engine
        if custom_list is not None:
            _edit(ctx, custom_list.id, draft)
            return
        list_id = make_custom_list(engine, draft)
        ctx.close_full_screen()
        on_made(list_id)
        ctx.changed()
        # CustomListInUseError, shown in the snackbar, once a line is on it
        ctx.undo(f"Utworzono listę: {draft.name}", lambda: undo_make_custom_list(engine, list_id))

    name.on_submit = save
    occasion.on_submit = save
    ctx.show_full_screen(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.IconButton(
                            ft.Icons.CLOSE,
                            tooltip="Anuluj",
                            on_click=lambda _: ctx.close_full_screen(),
                            key="custom-list-cancel",
                        ),
                        ft.Text("Nowa lista" if custom_list is None else "Edytuj listę", size=20, expand=True),
                        ft.FilledButton("Zapisz", on_click=save, key="custom-list-save"),
                        ft.Container(width=8),
                    ]
                ),
                ft.Container(
                    ft.Column([name, occasion], spacing=16),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                ),
            ],
            key="custom-list-form",
        )
    )


def _edit(ctx: Context, list_id: int, draft: CustomListDraft) -> None:
    engine = ctx.engine
    ctx.close_full_screen()
    try:
        before = edit_custom_list(engine, list_id, draft)
    except StockError as problem:
        ctx.changed()
        ctx.say(str(problem))
        return

    def undo() -> None:
        edit_custom_list(engine, list_id, before)

    ctx.changed()
    ctx.undo(f"Zmieniono listę: {draft.name}", undo)
