"""Ustawienia: the archive, where Archived Products are restored."""

from nicegui import ui

from home_stock.persistence.products import list_products, restore_product
from home_stock.ui.context import Context


class SettingsTab:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        with ui.column().classes("w-full gap-1").mark("archive"):
            ui.label("Archiwum").classes("text-subtitle1 text-weight-medium")
            self.archive_list = ui.column().classes("w-full gap-1")
        self.refresh()

    def refresh(self) -> None:
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
