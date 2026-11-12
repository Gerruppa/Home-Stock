"""Zakupy: a chip per list, "Brakuje" first. Brakuje is the Shopping List, every Product Running Low or Running Out
under its Category, with why it is there, each bought through the Purchase dialog, the list copied or shared as text.
A Custom List shows its List Lines, with "Dopisz" to write another, "Rozpakuj zakupy" to unpack them, and the
lines to buy copied or shared as text."""

from collections.abc import Callable

import flet as ft

from home_stock.domain.custom_lists import NOTHING_TYPED, CustomList, ListLine, ListLineDraft
from home_stock.domain.formatting import (
    format_custom_list,
    format_custom_list_label,
    format_custom_list_title,
    format_purchase_amount,
    format_quantity,
    format_shopping_reason,
    parse_count,
)
from home_stock.domain.stock import Product, Unit, name_key
from home_stock.mobile.context import Context
from home_stock.mobile.custom_list_form import open_custom_list_form
from home_stock.mobile.fields import show_error, text_field
from home_stock.mobile.line_dialog import open_line_dialog
from home_stock.mobile.purchase_dialog import open_purchase_dialog
from home_stock.mobile.unpacking_dialog import open_unpacking_dialog
from home_stock.persistence.catalog import StockError, list_categories, list_units
from home_stock.persistence.custom_lists import (
    add_line,
    delete_custom_list,
    delete_line,
    list_custom_lists,
    list_lines,
    restore_custom_list,
    restore_lines,
    tick_line,
    undo_add_line,
    undo_buy_lines,
)
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
        text = (lambda: shopping_list_text(engine, self.ctx.today())) if entries else None
        rows: list[ft.Control] = [self._buttons(None, text, "Skopiowano listę zakupów.")]
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

    def _buttons(self, custom_list_id: int | None, text: Callable[[], str] | None, copied_message: str) -> ft.Control:
        """Rozpakuj zakupy, of Brakuje or of the Custom List ``custom_list_id``, then Kopiuj listę and Udostępnij of
        the text ``text`` makes while there is something to buy; ``copied_message`` says the copy is made."""
        # Rozpakuj zakupy even with nothing to buy: it also takes Products from outside the list
        buttons: list[ft.Control] = [
            ft.OutlinedButton(
                "Rozpakuj zakupy",
                icon=ft.Icons.INVENTORY_2_OUTLINED,
                on_click=lambda _: open_unpacking_dialog(self.ctx, custom_list_id),
                key="unpack",
            )
        ]
        if text is not None:
            buttons += [
                ft.OutlinedButton(
                    "Kopiuj listę",
                    icon=ft.Icons.CONTENT_COPY,
                    on_click=lambda _: self._copy(text(), copied_message),
                    key="copy-list",
                ),
                ft.OutlinedButton(
                    "Udostępnij", icon=ft.Icons.SHARE, on_click=lambda _: self.ctx.share(text()), key="share-list"
                ),
            ]
        return ft.Container(ft.Row(buttons, wrap=True), padding=ft.Padding.symmetric(horizontal=12, vertical=8))

    def _copy(self, text: str, copied_message: str) -> None:
        self.ctx.copy(text)
        self.ctx.say(copied_message)

    def _custom_list(self, custom_list: CustomList) -> list[ft.Control]:
        engine = self.ctx.engine
        active = list_products(engine)
        self.line_form.show(custom_list.id, active)
        # An Archived Product's line stays on the list
        products = {product.id: product for product in active + list_products(engine, archived=True)}
        units = {unit.id: unit for unit in list_units(engine)}
        lines = list_lines(engine, custom_list.id)
        to_buy = [line for line in lines if not line.bought]
        bought = [line for line in lines if line.bought]
        text = (lambda: format_custom_list(custom_list, lines, products, units)) if to_buy else None
        rows: list[ft.Control] = [
            self._title(custom_list),
            self.line_form.control,
            self._buttons(custom_list.id, text, f"Skopiowano listę: {custom_list.name}"),
        ]
        if not lines:
            rows.append(ft.Container(ft.Text("Lista jest pusta."), padding=16, key="custom-list-empty"))
        elif not to_buy:
            rows.append(ft.Container(ft.Text("Wszystko kupione."), padding=16, key="all-bought"))
        rows += [self._line_tile(line, products, units) for line in to_buy]
        if bought:
            rows.append(
                ft.Container(
                    ft.Text("Kupione", weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                    padding=ft.Padding.only(left=16, top=16, bottom=4),
                    key="bought-heading",
                )
            )
            rows += [self._line_tile(line, products, units) for line in bought]
        return rows

    def _title(self, custom_list: CustomList) -> ft.Control:
        """The list's name and date, with its menu: Edytuj listę, Usuń listę."""
        menu = ft.PopupMenuButton(
            icon=ft.Icons.MORE_VERT,
            tooltip="Lista",
            items=[
                ft.PopupMenuItem(
                    content=ft.Text("Edytuj listę"),
                    icon=ft.Icons.EDIT_OUTLINED,
                    on_click=lambda _: open_custom_list_form(self.ctx, self._made, custom_list),
                    key="edit-list",
                ),
                ft.PopupMenuItem(
                    content=ft.Text("Usuń listę"),
                    icon=ft.Icons.DELETE_OUTLINE,
                    on_click=lambda _: self._delete_list(custom_list),
                    key="delete-list",
                ),
            ],
            key="list-menu",
        )
        return ft.Container(
            ft.Row(
                [
                    ft.Text(
                        format_custom_list_title(custom_list),
                        size=18,
                        weight=ft.FontWeight.W_500,
                        expand=True,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        key="custom-list-title",
                    ),
                    menu,
                ]
            ),
            padding=ft.Padding.only(left=16, right=4, top=8),
        )

    def _delete_list(self, custom_list: CustomList) -> None:
        engine = self.ctx.engine
        try:
            deleted = delete_custom_list(engine, custom_list.id)
        except StockError as problem:
            self.ctx.changed()
            self.ctx.say(str(problem))
            return

        def undo() -> None:
            restore_custom_list(engine, deleted)
            # Shown again, as it was before Usuń
            self.selected = custom_list.id

        self.ctx.changed()
        self.ctx.undo(f"Usunięto listę: {custom_list.name}", undo)

    def _line_tile(self, line: ListLine, products: dict[int, Product], units: dict[int, Unit]) -> ft.Control:
        """A line to buy has a tick and a menu (Zmień ilość or Zmień tekst, Usuń); a bought one is crossed out, with
        Usuń only."""
        product = None if line.product_id is None else products[line.product_id]
        name = line.text or "" if product is None else product.name
        title = f"{name} (w archiwum)" if product is not None and product.archived else name
        style = ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH) if line.bought else None
        color = ft.Colors.ON_SURFACE_VARIANT if line.bought else None
        items = [
            ft.PopupMenuItem(
                content=ft.Text("Usuń"),
                icon=ft.Icons.DELETE_OUTLINE,
                on_click=lambda _: self._delete_line(line, name),
                key=f"delete-line-{line.id}",
            )
        ]
        if not line.bought:
            items.insert(
                0,
                ft.PopupMenuItem(
                    content=ft.Text("Zmień tekst" if product is None else "Zmień ilość"),
                    icon=ft.Icons.EDIT_OUTLINED,
                    on_click=lambda _: open_line_dialog(self.ctx, line, name),
                    key=f"change-line-{line.id}",
                ),
            )
        trailing: list[ft.Control] = []
        if product is not None and line.quantity is not None:
            trailing.append(
                ft.Text(
                    format_purchase_amount(line.quantity, units[product.unit_id]),
                    weight=ft.FontWeight.W_500,
                    style=style,
                    color=color,
                )
            )
        if not line.bought:
            trailing.append(
                ft.IconButton(
                    ft.Icons.CHECK_CIRCLE_OUTLINE,
                    tooltip="Kupione",
                    on_click=lambda _: self._tick(line, product),
                    key=f"tick-{line.id}",
                )
            )
        trailing.append(ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, tooltip="Pozycja", items=items))
        return ft.ListTile(
            title=ft.Text(title, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, style=style, color=color),
            trailing=ft.Row(trailing, tight=True),
            dense=True,
            key=f"custom-line-{line.id}",
        )

    def _tick(self, line: ListLine, product: Product | None) -> None:
        """A Product line is bought through the Purchase dialog; a free-text line is ticked at once."""
        if product is not None:
            open_purchase_dialog(self.ctx, product, line)
            return
        engine = self.ctx.engine
        try:
            bought = tick_line(engine, line.id)
        except StockError as problem:
            self.ctx.changed()
            self.ctx.say(str(problem))
            return
        self.ctx.changed()
        self.ctx.undo(f"Kupiono: {line.text}", lambda: undo_buy_lines(engine, bought))

    def _delete_line(self, line: ListLine, name: str) -> None:
        engine = self.ctx.engine
        try:
            deleted = delete_line(engine, line.id)
        except StockError as problem:
            self.ctx.changed()
            self.ctx.say(str(problem))
            return
        self.ctx.changed()
        self.ctx.undo(f"Usunięto: {name}", lambda: restore_lines(engine, [deleted]))


class LineForm:
    """Dopisz: a Product picked by name with a Quantity, or text that names no Product as a free-text line.

    Made once and kept across redraws, as Produkty's search box is: Flet takes controls made anew with the keys of
    the old ones for rebuilds of them, after which they no longer take taps or changes."""

    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.list_id: int | None = None
        self.by_id: dict[int, Product] = {}
        self.by_name: dict[str, Product] = {}
        # How many name fields were made: each new one differs from the last by it (see _clear)
        self.made = 0
        self.name = self._new_name()
        # The name field is made anew to empty it (see _clear), so its key is on the row around it
        self.name_box = ft.Row([self.name], expand=True, key="line-name")
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

    def _new_name(self) -> ft.Dropdown:
        # A key of its own: with the old one's key, or none, Flet takes the new field for the old one (and freezes
        # it), and the phone keeps the text typed into it
        self.made += 1
        return ft.Dropdown(
            label="Dopisz",
            hint_text="produkt albo cokolwiek",
            editable=True,
            enable_filter=True,
            expand=True,
            key=f"line-name-field-{self.made}",
        )

    def _clear(self) -> None:
        # A new field: the phone keeps the text typed into the old one, even after it is set to ""
        options = self.name.options
        self.name = self._new_name()
        self.name.options = options
        self.name_box.controls = [self.name]
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
