"""Ustawienia: the Buffer, Categories with their Warning Windows, Units, and the archive, where Archived Products are
restored."""

from collections.abc import Callable

import flet as ft

from home_stock.domain.formatting import parse_buffer_days, parse_count
from home_stock.domain.stock import Category, Unit
from home_stock.mobile.context import Context
from home_stock.mobile.fields import text_field
from home_stock.mobile.starter_dialog import open_starter_dialog
from home_stock.persistence.catalog import (
    StockError,
    add_category,
    add_unit,
    delete_category,
    delete_unit,
    list_categories,
    list_units,
    update_category,
    update_unit,
)
from home_stock.persistence.products import list_products, restore_product
from home_stock.persistence.settings import load_buffer_days, save_buffer_days

# What a new Category's Warning Window starts at
NEW_WARNING_DAYS = "7"


class SettingsTab:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.buffer_rows, self.buffer_error, buffer = _section("buffer", "Zakupy", "buffer-error")
        self.category_rows, self.category_error, categories = _section("categories", "Kategorie", "category-error")
        self.unit_rows, self.unit_error, units = _section("units", "Jednostki", "unit-error")
        starter = _titled(
            "starter",
            "Typowe produkty",
            [
                ft.Text(
                    "Produkty, które ma zwykle każdy dom, do dodania jednym dotknięciem.",
                    size=12,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                ft.OutlinedButton(
                    "Dodaj typowe produkty",
                    icon=ft.Icons.PLAYLIST_ADD,
                    on_click=lambda _: open_starter_dialog(ctx),
                    key="starter-open",
                ),
            ],
        )
        # Restoring is never refused, so the archive has no line for a refusal
        self.archive_rows = ft.Column(spacing=12)
        archive = _titled("archive", "Archiwum", [self.archive_rows])
        self.control: ft.Control = ft.ListView(
            [buffer, categories, units, starter, archive], expand=True, spacing=8, padding=16, key="settings"
        )
        self.refresh()

    def refresh(self) -> None:
        for error in (self.buffer_error, self.category_error, self.unit_error):
            _show_error(error, None)
        self._refresh_buffer()
        self._refresh_categories()
        self._refresh_units()
        self._refresh_archive()

    def _refresh_buffer(self) -> None:
        engine, error = self.ctx.engine, self.buffer_error
        days = text_field("Zapas dni", str(load_buffer_days(engine)), "buffer-days", number=True)
        days.expand = True
        self.buffer_rows.controls = [
            ft.Row(
                [
                    days,
                    _icon_button(
                        ft.Icons.SAVE_OUTLINED,
                        "Zapisz",
                        "buffer-save",
                        lambda: self._change(error, lambda: save_buffer_days(engine, parse_buffer_days(days.value))),
                    ),
                ]
            ),
            ft.Text(
                "Produkt, któremu wystarczy na tyle dni lub mniej, trafia na listę zakupów.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
        ]

    def _refresh_categories(self) -> None:
        engine, error = self.ctx.engine, self.category_error
        rows: list[ft.Control] = [self._category_row(category) for category in list_categories(engine)]
        # Built anew on every redraw, so it is blank again after an add
        new_name = text_field("Nowa kategoria", "", "category-new-name")
        new_days = text_field("Dni ostrzeżenia", NEW_WARNING_DAYS, "category-new-days", number=True)
        rows.append(
            _row(
                new_name,
                new_days,
                [
                    _icon_button(
                        ft.Icons.ADD,
                        "Dodaj",
                        "category-add",
                        lambda: self._change(
                            error, lambda: add_category(engine, new_name.value, _days(new_days.value))
                        ),
                    )
                ],
            )
        )
        self.category_rows.controls = rows

    def _refresh_units(self) -> None:
        engine, error = self.ctx.engine, self.unit_error
        rows: list[ft.Control] = [self._unit_row(unit) for unit in list_units(engine)]
        new_name = text_field("Nowa jednostka", "", "unit-new-name")
        new_short = text_field("Skrót", "", "unit-new-short", hint="np. opak.")
        rows.append(
            _row(
                new_name,
                new_short,
                [
                    _icon_button(
                        ft.Icons.ADD,
                        "Dodaj",
                        "unit-add",
                        lambda: self._change(error, lambda: add_unit(engine, new_name.value, new_short.value)),
                    )
                ],
            )
        )
        self.unit_rows.controls = rows

    def _category_row(self, category: Category) -> ft.Control:
        engine = self.ctx.engine
        name = text_field("Nazwa", category.name, f"category-name-{category.id}")
        days = text_field("Dni ostrzeżenia", str(category.warning_days), f"category-days-{category.id}", number=True)
        row = _row(
            name,
            days,
            self._row_buttons(
                "category",
                category.id,
                self.category_error,
                lambda: update_category(engine, category.id, name.value, _days(days.value)),
                lambda: delete_category(engine, category.id),
            ),
        )
        row.key = f"category-row-{category.id}"
        return row

    def _unit_row(self, unit: Unit) -> ft.Control:
        engine = self.ctx.engine
        name = text_field("Nazwa", unit.name, f"unit-name-{unit.id}")
        short = text_field("Skrót", unit.short, f"unit-short-{unit.id}")
        row = _row(
            name,
            short,
            self._row_buttons(
                "unit",
                unit.id,
                self.unit_error,
                lambda: update_unit(engine, unit.id, name.value, short.value),
                lambda: delete_unit(engine, unit.id),
            ),
        )
        row.key = f"unit-row-{unit.id}"
        return row

    def _row_buttons(
        self, kind: str, row_id: int, error: ft.Text, save: Callable[[], object], remove: Callable[[], object]
    ) -> list[ft.Control]:
        """Zapisz and Usuń for a row, keyed "<kind>-save-<id>" and "<kind>-delete-<id>"."""
        return [
            _icon_button(ft.Icons.SAVE_OUTLINED, "Zapisz", f"{kind}-save-{row_id}", lambda: self._change(error, save)),
            _icon_button(
                ft.Icons.DELETE_OUTLINE, "Usuń", f"{kind}-delete-{row_id}", lambda: self._change(error, remove)
            ),
        ]

    def _change(self, error: ft.Text, action: Callable[[], object]) -> None:
        """Run a change and redraw every tab; a refused one shows its Polish message under its section instead."""
        try:
            action()
        except (StockError, ValueError) as problem:
            _show_error(error, str(problem))
            self.ctx.update()
            return
        self.ctx.changed()

    def _refresh_archive(self) -> None:
        archived = list_products(self.ctx.engine, archived=True)
        if not archived:
            self.archive_rows.controls = [ft.Text("Archiwum jest puste.")]
            return
        self.archive_rows.controls = [
            ft.Row(
                [
                    ft.Text(product.name, expand=True),
                    ft.OutlinedButton(
                        "Przywróć",
                        icon=ft.Icons.UNARCHIVE_OUTLINED,
                        on_click=lambda _, product_id=product.id: self._restore(product_id),
                        key=f"restore-{product.id}",
                    ),
                ],
                key=f"archived-{product.id}",
            )
            for product in archived
        ]

    def _restore(self, product_id: int) -> None:
        restore_product(self.ctx.engine, product_id)
        self.ctx.changed()


def _section(key: str, title: str, error_key: str) -> tuple[ft.Column, ft.Text, ft.Control]:
    """A titled section: the column its rows go in, the Text its refusals show in, and the section itself."""
    rows = ft.Column(spacing=12)
    error = ft.Text("", color=ft.Colors.ERROR, visible=False, key=error_key)
    return rows, error, _titled(key, title, [rows, error])


def _titled(key: str, title: str, controls: list[ft.Control]) -> ft.Control:
    """``controls`` under a bold title."""
    section = ft.Column([ft.Text(title, weight=ft.FontWeight.BOLD, size=16), *controls], spacing=8, key=key)
    return ft.Container(section, padding=ft.Padding.only(bottom=16))


def _row(name: ft.TextField, other: ft.TextField, buttons: list[ft.Control]) -> ft.Column:
    """A Category or Unit row: the Name on a line of its own, so a long one shows in full on a phone, and under it
    the other field with the buttons."""
    name.expand = True
    other.expand = True
    return ft.Column([ft.Row([name]), ft.Row([other, *buttons])], spacing=4)


def _icon_button(icon: ft.IconData, tooltip: str, key: str, on_click: Callable[[], None]) -> ft.IconButton:
    return ft.IconButton(icon, tooltip=tooltip, on_click=lambda _: on_click(), key=key)


def _show_error(error: ft.Text, message: str | None) -> None:
    error.value = message or ""
    error.visible = message is not None


def _days(text: str | None) -> int:
    days = parse_count(text or "")
    assert days is not None  # parse_count refuses a blank unless allow_blank
    return days
