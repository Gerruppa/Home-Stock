"""Zakupy: every Product Running Low or Running Out under its Category, with why it is there, each bought through the
Purchase dialog; the list copied or shared as text."""

import flet as ft

from home_stock.domain.formatting import format_purchase_amount, format_quantity, format_shopping_reason
from home_stock.mobile.context import Context
from home_stock.mobile.purchase_dialog import open_purchase_dialog
from home_stock.mobile.unpacking_dialog import open_unpacking_dialog
from home_stock.persistence.catalog import list_categories, list_units
from home_stock.persistence.products import list_shopping_list, shopping_list_text, suggested_purchases


class ShoppingTab:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.content = ft.ListView(expand=True, spacing=0, padding=ft.Padding.only(bottom=16), key="shopping")
        self.control: ft.Control = self.content
        self.refresh()

    def _list_text(self) -> str:
        return shopping_list_text(self.ctx.engine, self.ctx.today())

    def _copy(self) -> None:
        self.ctx.copy(self._list_text())
        self.ctx.say("Skopiowano listę zakupów.")

    def _share(self) -> None:
        self.ctx.share(self._list_text())

    def refresh(self) -> None:
        engine = self.ctx.engine
        entries = list_shopping_list(engine, self.ctx.today())
        # Rozpakuj zakupy even with nothing to buy: it also takes Products from outside the list
        buttons: list[ft.Control] = [
            ft.OutlinedButton(
                "Rozpakuj zakupy",
                icon=ft.Icons.INVENTORY_2_OUTLINED,
                on_click=lambda _: open_unpacking_dialog(self.ctx),
                key="unpack",
            )
        ]
        if entries:
            buttons += [
                ft.OutlinedButton(
                    "Kopiuj listę", icon=ft.Icons.CONTENT_COPY, on_click=lambda _: self._copy(), key="copy-list"
                ),
                ft.OutlinedButton(
                    "Udostępnij", icon=ft.Icons.SHARE, on_click=lambda _: self._share(), key="share-list"
                ),
            ]
        rows: list[ft.Control] = [
            ft.Container(ft.Row(buttons, wrap=True), padding=ft.Padding.symmetric(horizontal=12, vertical=8))
        ]
        if not entries:
            rows.append(ft.Container(ft.Text("Nic nie trzeba kupować."), padding=16, key="nothing-to-buy"))
            self.content.controls = rows
            return
        amounts = suggested_purchases(engine, [entry.product for entry in entries], self.ctx.today())
        units = {unit.id: unit for unit in list_units(engine)}
        for category in list_categories(engine):
            shown = [entry for entry in entries if entry.product.category_id == category.id]
            if not shown:
                continue
            rows.append(
                ft.Container(
                    ft.Text(category.name, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                    padding=ft.Padding.only(left=16, top=16, bottom=4),
                    key=f"shopping-category-{category.id}",
                )
            )
            for entry in shown:
                product = entry.product
                unit = units[product.unit_id]
                rows.append(
                    ft.ListTile(
                        title=ft.Text(product.name, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        subtitle=ft.Text(format_shopping_reason(entry), size=12),
                        trailing=ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(
                                            format_quantity(product.quantity, unit, product.pack_size),
                                            weight=ft.FontWeight.W_500,
                                        ),
                                        ft.Text(format_purchase_amount(amounts[product.id], unit), size=12),
                                    ],
                                    horizontal_alignment=ft.CrossAxisAlignment.END,
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    spacing=0,
                                    tight=True,
                                ),
                                ft.IconButton(
                                    ft.Icons.CHECK_CIRCLE_OUTLINE,
                                    tooltip="Kupione",
                                    on_click=lambda _, p=product: open_purchase_dialog(self.ctx, p),
                                    key=f"bought-{product.id}",
                                ),
                            ],
                            tight=True,
                        ),
                        dense=True,
                        key=f"shopping-{product.id}",
                    )
                )
        self.content.controls = rows
