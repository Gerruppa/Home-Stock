"""Produkty: every active Product under its Category, with a search box."""

import flet as ft

from home_stock.domain.formatting import format_days_left, format_quantity
from home_stock.domain.history import days_left
from home_stock.domain.stock import Product, is_running_low, name_key
from home_stock.mobile.context import Context
from home_stock.persistence.catalog import list_categories, list_units
from home_stock.persistence.history import consumption_rates
from home_stock.persistence.products import list_products, undo_use, use_one


class ProductsTab:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.search = ""
        search = ft.TextField(
            label="Szukaj", prefix_icon=ft.Icons.SEARCH, dense=True, expand=True, on_change=self._searched, key="search"
        )
        self.content = ft.ListView(expand=True, spacing=0, padding=ft.Padding.only(bottom=16), key="products")
        self.control: ft.Control = ft.Column(
            [ft.Container(ft.Row([search]), padding=ft.Padding.symmetric(horizontal=12, vertical=8)), self.content],
            expand=True,
            spacing=0,
        )
        self.refresh()

    def _searched(self, event: ft.Event[ft.TextField]) -> None:
        self.search = event.control.value or ""
        self.refresh()
        self.ctx.update()

    def refresh(self) -> None:
        engine = self.ctx.engine
        products = list_products(engine)
        units = {unit.id: unit for unit in list_units(engine)}
        rates = consumption_rates(engine, self.ctx.today())
        rows: list[ft.Control] = []
        if not products:
            rows.append(ft.Container(ft.Text("Nie masz jeszcze produktów."), padding=16, key="no-products"))
        wanted = name_key(self.search)
        for category in list_categories(engine):
            shown = [p for p in products if p.category_id == category.id and wanted in name_key(p.name)]
            if not shown:
                continue
            rows.append(
                ft.Container(
                    ft.Text(category.name, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                    padding=ft.Padding.only(left=16, top=16, bottom=4),
                    key=f"category-{category.id}",
                )
            )
            for product in shown:
                days = (
                    ft.Text(
                        format_days_left(days_left(product.quantity, rates[product.id])),
                        size=12,
                        key=f"days-left-{product.id}",
                    )
                    if product.id in rates
                    else None
                )
                rows.append(
                    ft.ListTile(
                        title=ft.Text(product.name, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        subtitle=days,
                        trailing=ft.Row(
                            [
                                ft.Text(
                                    format_quantity(product.quantity, units[product.unit_id], product.pack_size),
                                    color=ft.Colors.ERROR if is_running_low(product) else None,
                                    weight=ft.FontWeight.W_500,
                                    key=f"quantity-{product.id}",
                                ),
                                ft.IconButton(
                                    ft.Icons.REMOVE_CIRCLE_OUTLINE,
                                    tooltip="Zużyj 1",
                                    disabled=product.quantity == 0,
                                    on_click=lambda _, p=product: self._use(p),
                                    key=f"use-{product.id}",
                                ),
                            ],
                            tight=True,
                        ),
                        dense=True,
                        key=f"product-{product.id}",
                    )
                )
        self.content.controls = rows

    def _use(self, product: Product) -> None:
        engine = self.ctx.engine
        used = use_one(engine, product.id, self.ctx.today())
        if used is None:
            return
        self.ctx.changed()
        self.ctx.undo(f"Zużyto 1 × {product.name}", lambda: undo_use(engine, used))
