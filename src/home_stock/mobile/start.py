"""Start: what has expired, what expires soon and what to buy; the only place reminders appear (ADR-0002), so no
Android notifications. Each line opens its Product's card."""

from typing import NamedTuple

import flet as ft

from home_stock.domain.formatting import format_date, format_days_left, format_quantity
from home_stock.domain.stock import Batch, ExpiryStatus, Product, ShoppingListEntry, Unit, expiry_status
from home_stock.mobile.context import Context
from home_stock.mobile.product_card import open_product_card
from home_stock.mobile.theme import EXPIRED, EXPIRING, TO_BUY
from home_stock.persistence.catalog import list_categories, list_units
from home_stock.persistence.products import list_products, list_shopping_list


class _StartLine(NamedTuple):
    key: str
    product_id: int
    name: str
    detail: str


class _Section(NamedTuple):
    key: str
    title: str
    colour: str
    lines: list[_StartLine]


class StartTab:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.content = ft.ListView(expand=True, spacing=0, padding=ft.Padding.only(bottom=16), key="start")
        self.control: ft.Control = self.content
        self.refresh()

    def refresh(self) -> None:
        engine = self.ctx.engine
        today = self.ctx.today()
        units = {unit.id: unit for unit in list_units(engine)}
        warning_days = {category.id: category.warning_days for category in list_categories(engine)}
        expired: list[tuple[Product, Batch]] = []
        expiring: list[tuple[Product, Batch]] = []
        for product in list_products(engine):
            for batch in product.batches:
                status = expiry_status(batch, today, warning_days[product.category_id])
                if status is ExpiryStatus.EXPIRED:
                    expired.append((product, batch))
                elif status is ExpiryStatus.EXPIRING_SOON:
                    expiring.append((product, batch))
        to_buy = [_to_buy_line(entry, units) for entry in list_shopping_list(engine, today)]
        sections = [
            _Section("expired", "Przeterminowane", EXPIRED, _expiry_lines(expired, units)),
            _Section("expiring", "Kończy się termin", EXPIRING, _expiry_lines(expiring, units)),
            _Section("to-buy", "Do kupienia", TO_BUY, to_buy),
        ]
        if not any(section.lines for section in sections):
            self.content.controls = [
                ft.Container(ft.Text("Wszystko w porządku.", size=20), padding=16, key="all-clear")
            ]
            return
        self.content.controls = [self._section(section) for section in sections]

    def _section(self, section: _Section) -> ft.Control:
        key, title, colour, lines = section
        rows: list[ft.Control] = [
            ft.ListTile(
                title=ft.Text(line.name, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                subtitle=ft.Text(line.detail, size=12),
                dense=True,
                on_click=lambda _, line=line: open_product_card(self.ctx, line.product_id),
                key=line.key,
            )
            for line in lines
        ]
        if not rows:
            rows.append(ft.Container(ft.Text("Nic tutaj.", italic=True), padding=ft.Padding.only(left=16, bottom=8)))
        return ft.Container(
            ft.Column(
                [
                    ft.Container(
                        ft.Text(title, weight=ft.FontWeight.BOLD, color=colour, key=f"{key}-title"),
                        padding=ft.Padding.only(left=16, top=16, bottom=4),
                    ),
                    ft.Column(rows, spacing=0, key=f"{key}-lines"),
                ],
                spacing=0,
            ),
            # The urgency colour down the section's left edge
            border=ft.Border.only(left=ft.BorderSide(6, colour)),
            margin=ft.Margin.only(top=8),
            key=key,
        )


def _expiry_lines(dated: list[tuple[Product, Batch]], units: dict[int, Unit]) -> list[_StartLine]:
    """One line per Batch, e.g. Mleko / "2 szt., termin 27.10.2026", soonest first."""
    lines = []
    for product, batch in sorted(dated, key=lambda pair: (pair[1].expiry, pair[0].name)):
        assert batch.expiry is not None  # only dated Batches have an Expiry Status
        quantity = format_quantity(batch.quantity, units[product.unit_id], product.pack_size)
        detail = f"{quantity}, termin {format_date(batch.expiry)}"
        lines.append(_StartLine(f"start-batch-{batch.id}", product.id, product.name, detail))
    return lines


def _to_buy_line(entry: ShoppingListEntry, units: dict[int, Unit]) -> _StartLine:
    """A Shopping List line, e.g. Cukier / "1 opak., minimum 2 opak." or "3 opak., wystarczy na ok. 5 dni"."""
    product = entry.product
    unit = units[product.unit_id]
    quantity = format_quantity(product.quantity, unit, product.pack_size)
    if entry.days_left is None:
        reason = f"minimum {format_quantity(product.minimum_stock or 0, unit, None)}"
    else:
        reason = format_days_left(entry.days_left)
    return _StartLine(f"start-low-{product.id}", product.id, product.name, f"{quantity}, {reason}")
