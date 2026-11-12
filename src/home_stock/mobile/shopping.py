"""Zakupy: a chip per list, "Brakuje" first. Brakuje is the Shopping List, every Product Running Low or Running Out
under its Category, with why it is there, each bought through the Purchase dialog, the list copied or shared as text.
A Custom List shows its List Lines, with "Dopisz" to write another."""

import flet as ft

from home_stock.domain.custom_lists import NOTHING_TYPED, CustomList, ListLine, ListLineDraft
from home_stock.domain.formatting import (
    format_custom_list_label,
    format_purchase_amount,
    format_quantity,
    format_shopping_reason,
    parse_count,
)
from home_stock.domain.stock import Product, Unit, name_key
from home_stock.mobile.context import Context
from home_stock.mobile.custom_list_form import open_custom_list_form
from home_stock.mobile.fields import show_error, text_field
from home_stock.mobile.purchase_dialog import open_purchase_dialog
from home_stock.mobile.unpacking_dialog import open_unpacking_dialog
from home_stock.persistence.catalog import StockError, list_categories, list_units
from home_stock.persistence.custom_lists import add_line, list_custom_lists, list_lines, undo_add_line
from home_stock.persistence.products import (
    list_products,
    list_shopping_list,
    shopping_list_text,
    suggested_purchases,
)


class ShoppingTab:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        # The Custom List shown, or None for Brakuje; kept across the redraws of ctx.changed()
        self.selected: int | None = None
        self.line_form = LineForm(ctx)
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

    def _select(self, list_id: int | None) -> None:
        self.selected = list_id
        self.refresh()
        self.ctx.update()

    def _made(self, list_id: int) -> None:
        # Selected before the redraw that follows, so the new list is the one shown
        self.selected = list_id

    def refresh(self) -> None:
        custom_lists = list_custom_lists(self.ctx.engine)
        shown = next((lst for lst in custom_lists if lst.id == self.selected), None)
        # A list deleted meanwhile, or taken back by Cofnij: back to Brakuje
        self.selected = None if shown is None else shown.id
        rows = [self._chips(custom_lists)]
        rows += self._shopping_list() if shown is None else self._custom_list(shown)
        self.content.controls = rows

    def _chips(self, custom_lists: list[CustomList]) -> ft.Control:
        chips: list[ft.Control] = [
            ft.Chip(
                label=ft.Text("Brakuje"),
                selected=self.selected is None,
                on_select=lambda _: self._select(None),
                key="list-chip-missing",
            )
        ]
        chips += [
            ft.Chip(
                label=ft.Text(format_custom_list_label(lst)),
                selected=lst.id == self.selected,
                on_select=lambda _, list_id=lst.id: self._select(list_id),
                key=f"list-chip-{lst.id}",
            )
            for lst in custom_lists
        ]
        chips.append(
            ft.Chip(
                label=ft.Text("Nowa lista"),
                leading=ft.Icon(ft.Icons.ADD),
                on_click=lambda _: open_custom_list_form(self.ctx, self._made),
                key="new-list",
            )
        )
        return ft.Container(
            ft.Row(chips, wrap=True, spacing=8, run_spacing=4),
            padding=ft.Padding.only(left=12, right=12, top=8),
            key="list-chips",
        )

    def _shopping_list(self) -> list[ft.Control]:
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
            return rows
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
        return rows

    def _custom_list(self, custom_list: CustomList) -> list[ft.Control]:
        engine = self.ctx.engine
        active = list_products(engine)
        self.line_form.show(custom_list.id, active)
        # An Archived Product's line stays on the list
        products = {product.id: product for product in active + list_products(engine, archived=True)}
        units = {unit.id: unit for unit in list_units(engine)}
        rows: list[ft.Control] = [self.line_form.control]
        lines = list_lines(engine, custom_list.id)
        if not lines:
            rows.append(ft.Container(ft.Text("Lista jest pusta."), padding=16, key="custom-list-empty"))
        rows += [_line_tile(line, products, units) for line in lines]
        return rows


class LineForm:
    """Dopisz: a Product picked by name with a Quantity, or text that names no Product as a free-text line.

    Made once and kept across redraws, as Produkty's search box is: Flet takes controls made anew with the keys of
    the old ones for rebuilds of them, after which they no longer take taps or changes."""

    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.list_id: int | None = None
        self.by_id: dict[int, Product] = {}
        self.by_name: dict[str, Product] = {}
        self.name = self._new_name()
        # The name field is made anew to empty it (see _clear), so its key is on the box around it
        self.name_box = ft.Container(self.name, expand=True, key="line-name")
        self.quantity = text_field("Ilość", "1", "line-quantity", number=True, width=80)
        self.quantity.on_submit = self._add
        self.error = ft.Text("", color=ft.Colors.ERROR, size=12, visible=False, key="line-error")
        self.control = ft.Container(
            ft.Column(
                [
                    ft.Row(
                        [
                            self.name_box,
                            self.quantity,
                            ft.IconButton(ft.Icons.ADD, tooltip="Dopisz", on_click=self._add, key="line-add"),
                        ]
                    ),
                    self.error,
                ],
                spacing=4,
            ),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        )

    def show(self, list_id: int, active: list[Product]) -> None:
        """Offer the active Products for the Custom List ``list_id``; empty again after another list."""
        if list_id != self.list_id:
            self.list_id = list_id
            self._clear()
        self.by_id = {product.id: product for product in active}
        self.by_name = {name_key(product.name): product for product in active}
        self.name.options = [ft.DropdownOption(key=str(p.id), text=p.name) for p in active]

    @staticmethod
    def _new_name() -> ft.Dropdown:
        # No key: Flet would take a new field with the old one's key for a rebuild of it, and freeze it
        return ft.Dropdown(label="Dopisz", hint_text="produkt albo cokolwiek", editable=True, enable_filter=True)

    def _clear(self) -> None:
        # A new field: the phone keeps the text typed into the old one, even after it is set to ""
        options = self.name.options
        self.name = self._new_name()
        self.name.options = options
        # Controls compare by their fields, so the new field equals the old one and Flet would skip it: through None
        self.name_box.content = None
        self.name_box.content = self.name
        self.quantity.value = "1"
        show_error(self.quantity, None)
        self.error.visible = False

    def _say(self, problem: str) -> None:
        self.error.value, self.error.visible = problem, True
        self.ctx.update()

    def _add(self, _: object) -> None:
        picked = self.by_id.get(int(self.name.value)) if self.name.value else None
        typed = " ".join((self.name.text or "").split())
        # Text typed after picking a Product names what was typed, not the Product picked
        if typed and (picked is None or name_key(typed) != name_key(picked.name)):
            picked = self.by_name.get(name_key(typed))
        self.error.visible = False
        show_error(self.quantity, None)
        if picked is None and not typed:
            self._say(NOTHING_TYPED)
            return
        try:
            count = parse_count(self.quantity.value)
            assert count is not None
            if picked is not None:
                draft = ListLineDraft.product(picked.id, count)
            else:
                # A free-text line has no Unit: a Quantity above 1 goes into its text
                draft = ListLineDraft.note(f"{typed} × {count}" if count > 1 else typed)
        except ValueError as problem:
            show_error(self.quantity, str(problem))
            self.ctx.update()
            return
        engine = self.ctx.engine
        assert self.list_id is not None
        try:
            added = add_line(engine, self.list_id, draft)
        except StockError as problem:
            self._say(str(problem))
            return
        label = picked.name if picked is not None else draft.text
        # Empty for the next line
        self._clear()
        self.ctx.changed()
        self.ctx.undo(f"Dopisano: {label}", lambda: undo_add_line(engine, added))


def _line_tile(line: ListLine, products: dict[int, Product], units: dict[int, Unit]) -> ft.Control:
    if line.product_id is None:
        return ft.ListTile(title=ft.Text(line.text or ""), dense=True, key=f"custom-line-{line.id}")
    product = products[line.product_id]
    assert line.quantity is not None
    title = f"{product.name} (w archiwum)" if product.archived else product.name
    return ft.ListTile(
        title=ft.Text(title, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
        trailing=ft.Text(format_purchase_amount(line.quantity, units[product.unit_id]), weight=ft.FontWeight.W_500),
        dense=True,
        key=f"custom-line-{line.id}",
    )
