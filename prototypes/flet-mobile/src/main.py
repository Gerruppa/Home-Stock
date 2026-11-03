"""Throwaway prototype: the Produkty tab in Flet, on the app's own domain/ and persistence/, to find out whether they
run in an Android APK (SQLite, SQLAlchemy, Alembic migrations) and how the app could look on a phone."""

import os
import sys
import traceback
from datetime import date

import flet as ft

# Flet's durable app-private folder; flet run points it at .flet/storage/data
if os.environ.get("FLET_APP_STORAGE_DATA"):
    os.environ["HOME_STOCK_DATA_DIR"] = os.environ["FLET_APP_STORAGE_DATA"]

TABS = [
    (ft.Icons.HOME_OUTLINED, "Start"),
    (ft.Icons.INVENTORY_2_OUTLINED, "Produkty"),
    (ft.Icons.SHOPPING_CART_OUTLINED, "Zakupy"),
    (ft.Icons.HISTORY, "Historia"),
    (ft.Icons.SETTINGS_OUTLINED, "Ustawienia"),
]
PRODUCTS_TAB = 1


def main(page: ft.Page) -> None:
    page.title = "Home Stock"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    try:
        ProductsApp(page)
    except Exception:
        # No console on a phone: the traceback on screen is the only way to see what broke
        page.controls.clear()
        page.add(
            ft.SafeArea(
                ft.Column(
                    [ft.Text("Błąd startu", size=20), ft.Text(traceback.format_exc(), size=11, selectable=True)],
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
                expand=True,
            )
        )
        page.update()


class ProductsApp:
    def __init__(self, page: ft.Page) -> None:
        from home_stock.persistence.db import init_db
        from home_stock.persistence.paths import database_path

        self.page = page
        self.path = database_path()
        self.engine = init_db(self.path)
        self.search = ""
        self.content = ft.ListView(expand=True, spacing=0, padding=ft.Padding.only(bottom=16))
        self.body = ft.Column(expand=True, spacing=0)
        page.navigation_bar = ft.NavigationBar(
            destinations=[ft.NavigationBarDestination(icon=icon, label=label) for icon, label in TABS],
            selected_index=PRODUCTS_TAB,
            on_change=self._tab_changed,
        )
        page.add(ft.SafeArea(self.body, expand=True))
        self._show_products()

    def _tab_changed(self, event: ft.Event[ft.NavigationBar]) -> None:
        if event.control.selected_index == PRODUCTS_TAB:
            self._show_products()
        else:
            self.body.controls = [
                ft.Container(ft.Text("W prototypie działa tylko zakładka Produkty."), padding=24),
            ]
            self.page.update()

    def _show_products(self) -> None:
        search = ft.TextField(
            label="Szukaj",
            value=self.search,
            prefix_icon=ft.Icons.SEARCH,
            dense=True,
            on_change=self._searched,
            expand=True,
        )
        self.body.controls = [
            ft.Container(ft.Row([search]), padding=ft.Padding.symmetric(horizontal=12, vertical=8)),
            self.content,
            ft.Container(
                ft.Text(f"Python {sys.version.split()[0]} · baza: {self.path}", size=10, color=ft.Colors.GREY_600),
                padding=ft.Padding.symmetric(horizontal=12, vertical=4),
            ),
        ]
        self.refresh()

    def _searched(self, event: ft.Event[ft.TextField]) -> None:
        self.search = event.control.value or ""
        self.refresh()

    def refresh(self) -> None:
        from home_stock.domain.formatting import format_days_left, format_quantity
        from home_stock.domain.history import days_left
        from home_stock.domain.stock import is_running_low, name_key
        from home_stock.persistence.catalog import list_categories, list_units
        from home_stock.persistence.history import consumption_rates
        from home_stock.persistence.products import list_products

        engine = self.engine
        products = list_products(engine)
        units = {unit.id: unit for unit in list_units(engine)}
        rates = consumption_rates(engine, date.today())
        rows: list[ft.Control] = []
        if not products:
            rows.append(ft.Container(ft.Text("Nie masz jeszcze produktów."), padding=16))
            rows.append(
                ft.Container(
                    ft.OutlinedButton("Wczytaj przykładowe dane", icon=ft.Icons.PLAYLIST_ADD, on_click=self._seed),
                    padding=ft.Padding.symmetric(horizontal=16),
                )
            )
        wanted = name_key(self.search)
        for category in list_categories(engine):
            shown = [p for p in products if p.category_id == category.id and wanted in name_key(p.name)]
            if not shown:
                continue
            rows.append(
                ft.Container(
                    ft.Text(category.name, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                    padding=ft.Padding.only(left=16, top=16, bottom=4),
                )
            )
            for product in shown:
                quantity = format_quantity(product.quantity, units[product.unit_id], product.pack_size)
                low = is_running_low(product)
                subtitle = (
                    format_days_left(days_left(product.quantity, rates[product.id])) if product.id in rates else None
                )
                rows.append(
                    ft.ListTile(
                        title=ft.Text(product.name),
                        subtitle=ft.Text(subtitle, size=12) if subtitle else None,
                        trailing=ft.Row(
                            [
                                ft.Text(quantity, color=ft.Colors.ERROR if low else None, weight=ft.FontWeight.W_500),
                                ft.IconButton(
                                    ft.Icons.REMOVE_CIRCLE_OUTLINE,
                                    tooltip="Zużyj 1",
                                    disabled=product.quantity == 0,
                                    on_click=lambda _, p=product: self._use(p.id, p.name),
                                ),
                            ],
                            tight=True,
                        ),
                        dense=True,
                    )
                )
        self.content.controls = rows
        self.page.update()

    def _seed(self, _: ft.Event[ft.OutlinedButton]) -> None:
        from home_stock.sources.demo_data import seed_demo_data

        seed_demo_data(self.engine, date.today())
        self.refresh()

    def _use(self, product_id: int, name: str) -> None:
        from home_stock.persistence.products import undo_use, use_one

        used = use_one(self.engine, product_id, date.today())
        if used is None:
            return
        self.refresh()

        def undo(_: ft.Event[ft.SnackBar]) -> None:
            undo_use(self.engine, used)
            self.refresh()

        self.page.show_dialog(ft.SnackBar(ft.Text(f"Zużyto 1 × {name}"), action="Cofnij", on_action=undo))


if __name__ == "__main__":
    ft.run(main)
