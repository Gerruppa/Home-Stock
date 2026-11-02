"""Ustawienia: the Buffer, Categories with their Warning Windows, Units, the Starter Catalog, and the archive, where
Archived Products are restored."""

from collections.abc import Callable

from nicegui import ui

from home_stock.domain.formatting import parse_buffer_days, parse_count
from home_stock.domain.stock import Category, Unit
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
from home_stock.ui.context import Context
from home_stock.ui.fields import error_label, show_error
from home_stock.ui.starter_dialog import open_starter_dialog

# What a new Category's Warning Window starts at
NEW_WARNING_DAYS = "7"


class SettingsTab:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.buffer_row, self.buffer_error = _section("buffer", "Zakupy", "buffer-error")
        self.category_list, self.category_error = _section("categories", "Kategorie", "category-error")
        self.unit_list, self.unit_error = _section("units", "Jednostki", "unit-error")
        with ui.column().classes("w-full gap-1 hs-section hs-category").mark("starter"):
            ui.label("Typowe produkty").classes("hs-section-title")
            with ui.row().classes("w-full items-center"):
                ui.label("Produkty, które ma zwykle każdy dom, do dodania jednym kliknięciem.").classes(
                    "grow hs-muted text-sm"
                )
                ui.button(
                    "Dodaj typowe produkty", icon="playlist_add", on_click=lambda: open_starter_dialog(ctx)
                ).props("outline").mark("starter-open")
        with ui.column().classes("w-full gap-1 hs-section hs-category").mark("archive"):
            ui.label("Archiwum").classes("hs-section-title")
            self.archive_list = ui.column().classes("w-full gap-1")
        self.refresh()

    def refresh(self) -> None:
        self._refresh_buffer()
        self._refresh_categories()
        self._refresh_units()
        self._refresh_archive()

    def _refresh_buffer(self) -> None:
        engine, error = self.ctx.engine, self.buffer_error
        show_error(error, None)
        self.buffer_row.clear()
        with self.buffer_row, ui.row().classes("w-full items-center"):
            days = ui.input("Zapas dni", value=str(load_buffer_days(engine))).classes("w-32").mark("buffer-days")
            ui.label("Produkt, któremu wystarczy na tyle dni lub mniej, trafia na listę zakupów.").classes(
                "grow hs-muted text-sm hs-hint-below"
            )
            with ui.row().classes("hs-actions hs-line-end"):
                ui.button(
                    icon="save",
                    on_click=lambda: self._change(
                        error, lambda: save_buffer_days(engine, parse_buffer_days(days.value))
                    ),
                ).props("dense flat").tooltip("Zapisz").mark("buffer-save")

    def _refresh_categories(self) -> None:
        engine, error = self.ctx.engine, self.category_error
        show_error(error, None)
        self.category_list.clear()
        with self.category_list:
            for category in list_categories(engine):
                self._category_row(category)
            # Built anew on every redraw, so it is empty again after an add
            _, name_part, end = _row_parts()
            with name_part:
                new_name = ui.input("Nowa kategoria").classes("grow").mark("category-new-name")
            with end:
                new_days = ui.input("Dni ostrzeżenia", value=NEW_WARNING_DAYS).classes("w-32").mark("category-new-days")
                self._add_button(
                    "category-add", error, lambda: add_category(engine, new_name.value, _days(new_days.value))
                )

    def _refresh_units(self) -> None:
        engine, error = self.ctx.engine, self.unit_error
        show_error(error, None)
        self.unit_list.clear()
        with self.unit_list:
            for unit in list_units(engine):
                self._unit_row(unit)
            _, name_part, end = _row_parts()
            with name_part:
                new_name = ui.input("Nowa jednostka").classes("grow").mark("unit-new-name")
            with end:
                new_short = ui.input("Skrót", placeholder="np. opak.").classes("w-32").mark("unit-new-short")
                self._add_button("unit-add", error, lambda: add_unit(engine, new_name.value, new_short.value))

    def _category_row(self, category: Category) -> None:
        engine = self.ctx.engine
        row, name_part, end = _row_parts()
        row.mark(f"category-row-{category.id}")
        with name_part:
            name = ui.input("Nazwa", value=category.name).classes("grow").mark(f"category-name-{category.id}")
        with end:
            days = ui.input("Dni ostrzeżenia", value=str(category.warning_days)).classes("w-32")
            days.mark(f"category-days-{category.id}")
            self._row_buttons(
                "category",
                category.id,
                self.category_error,
                lambda: update_category(engine, category.id, name.value, _days(days.value)),
                lambda: delete_category(engine, category.id),
            )

    def _unit_row(self, unit: Unit) -> None:
        engine = self.ctx.engine
        row, name_part, end = _row_parts()
        row.mark(f"unit-row-{unit.id}")
        with name_part:
            name = ui.input("Nazwa", value=unit.name).classes("grow").mark(f"unit-name-{unit.id}")
        with end:
            short = ui.input("Skrót", value=unit.short).classes("w-32").mark(f"unit-short-{unit.id}")
            self._row_buttons(
                "unit",
                unit.id,
                self.unit_error,
                lambda: update_unit(engine, unit.id, name.value, short.value),
                lambda: delete_unit(engine, unit.id),
            )

    def _row_buttons(
        self, kind: str, row_id: int, error: ui.label, save: Callable[[], object], remove: Callable[[], object]
    ) -> None:
        """Zapisz and Usuń for a row, marked "<kind>-save-<id>" and "<kind>-delete-<id>"."""
        with ui.row().classes("hs-actions"):
            save_button = ui.button(icon="save", on_click=lambda: self._change(error, save))
            save_button.props("dense flat").tooltip("Zapisz").mark(f"{kind}-save-{row_id}")
            delete_button = ui.button(icon="delete", on_click=lambda: self._change(error, remove))
            delete_button.props("dense flat").tooltip("Usuń").mark(f"{kind}-delete-{row_id}")

    def _add_button(self, marker: str, error: ui.label, add: Callable[[], object]) -> None:
        # In a column as wide as the Zapisz and Usuń pair above, so the new row lines up with the saved ones
        with ui.row().classes("hs-actions"):
            ui.button(icon="add", on_click=lambda: self._change(error, add)).props("dense flat").tooltip("Dodaj").mark(
                marker
            )

    def _change(self, error: ui.label, action: Callable[[], object]) -> None:
        """Run a change and redraw every tab; a refused one shows its Polish message under its section instead."""
        try:
            action()
        except (StockError, ValueError) as problem:
            show_error(error, str(problem))
            return
        self.ctx.changed()

    def _refresh_archive(self) -> None:
        archived = list_products(self.ctx.engine, archived=True)
        self.archive_list.clear()
        with self.archive_list:
            if not archived:
                ui.label("Archiwum jest puste.")
            for product in archived:
                with ui.row().classes("w-full items-center").mark(f"archived-{product.id}"):
                    ui.label(product.name).classes("grow")
                    ui.button("Przywróć", icon="unarchive", on_click=lambda p=product: self._restore(p.id)).props(
                        "dense outline"
                    ).mark(f"restore-{product.id}")

    def _restore(self, product_id: int) -> None:
        restore_product(self.ctx.engine, product_id)
        self.ctx.changed()


def _row_parts() -> tuple[ui.row, ui.row, ui.row]:
    """A Category or Unit row and its two empty parts: the Name, and the rest, which wraps under the Name where they
    don't fit (a phone) so a long Name shows in full."""
    with ui.row().classes("w-full items-center") as row:
        name_part = ui.row().classes("items-center no-wrap hs-line-main")
        end = ui.row().classes("items-center no-wrap hs-line-end")
    return row, name_part, end


def _section(marker: str, title: str, error_marker: str) -> tuple[ui.column, ui.label]:
    """A titled section: the column its rows are drawn into and the label its refusals show in."""
    with ui.column().classes("w-full gap-1 hs-section hs-category").mark(marker):
        ui.label(title).classes("hs-section-title")
        rows = ui.column().classes("w-full gap-1")
        error = error_label().mark(error_marker)
    return rows, error


def _days(text: str | None) -> int:
    days = parse_count(text or "")
    assert days is not None  # parse_count refuses a blank unless allow_blank
    return days
