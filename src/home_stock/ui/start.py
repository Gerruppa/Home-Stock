"""Start: what has expired, what expires soon and what to buy; the only place reminders appear (ADR-0002). Each line
opens its Product's card."""

from typing import NamedTuple

from nicegui import ui

from home_stock.domain.formatting import format_date, format_quantity
from home_stock.domain.stock import Batch, ExpiryStatus, Product, Unit, expiry_status, is_running_low
from home_stock.persistence.catalog import list_categories, list_units
from home_stock.persistence.products import list_products
from home_stock.ui.context import Context
from home_stock.ui.product_card import open_product_card


class _StartLine(NamedTuple):
    marker: str
    product_id: int
    name: str
    detail: str


class StartTab:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.content = ui.column().classes("w-full gap-4")
        self.refresh()

    def refresh(self) -> None:
        engine = self.ctx.engine
        today = self.ctx.today()
        products = list_products(engine)
        units = {unit.id: unit for unit in list_units(engine)}
        warning_days = {category.id: category.warning_days for category in list_categories(engine)}
        expired: list[tuple[Product, Batch]] = []
        expiring: list[tuple[Product, Batch]] = []
        for product in products:
            for batch in product.batches:
                status = expiry_status(batch, today, warning_days[product.category_id])
                if status is ExpiryStatus.EXPIRED:
                    expired.append((product, batch))
                elif status is ExpiryStatus.EXPIRING_SOON:
                    expiring.append((product, batch))
        sections = [
            ("expired", "Przeterminowane", _expiry_lines(expired, units)),
            ("expiring", "Kończy się termin", _expiry_lines(expiring, units)),
            ("running-low", "Do kupienia", [_running_low_line(p, units) for p in products if is_running_low(p)]),
        ]
        self.content.clear()
        with self.content:
            if not any(lines for _, _, lines in sections):
                ui.label("Wszystko w porządku.").classes("text-h6")
                return
            for marker, title, lines in sections:
                with ui.column().classes(f"w-full gap-0 hs-section hs-{marker}").mark(marker):
                    ui.label(title).classes("hs-section-title q-mb-xs")
                    if not lines:
                        ui.label("Nic tutaj.").classes("hs-empty")
                    for line in lines:
                        row = ui.row().classes("w-full items-baseline no-wrap hs-line cursor-pointer").mark(line.marker)
                        row.on("click", lambda line=line: open_product_card(self.ctx, line.product_id))
                        with row:
                            ui.label(line.name).classes("grow")
                            ui.label(line.detail).classes("hs-qty")


def _expiry_lines(dated: list[tuple[Product, Batch]], units: dict[int, Unit]) -> list[_StartLine]:
    """One line per Batch, e.g. Mleko / "2 szt., termin 27.10.2026", soonest first."""
    lines = []
    for product, batch in sorted(dated, key=lambda pair: (pair[1].expiry, pair[0].name)):
        assert batch.expiry is not None  # only dated Batches have an Expiry Status
        quantity = format_quantity(batch.quantity, units[product.unit_id], product.pack_size)
        detail = f"{quantity}, termin {format_date(batch.expiry)}"
        lines.append(_StartLine(f"start-batch-{batch.id}", product.id, product.name, detail))
    return lines


def _running_low_line(product: Product, units: dict[int, Unit]) -> _StartLine:
    unit = units[product.unit_id]
    quantity = format_quantity(product.quantity, unit, product.pack_size)
    minimum = format_quantity(product.minimum_stock or 0, unit, None)
    return _StartLine(f"start-low-{product.id}", product.id, product.name, f"{quantity}, minimum {minimum}")
