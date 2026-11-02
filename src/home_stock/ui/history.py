"""Historia: Waste over the last 30 and 90 days, then the latest Stock Events of all Products, with a box that keeps
those of the Products matching a name."""

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from home_stock.domain.formatting import format_date, format_event_change, format_event_kind, format_waste
from home_stock.domain.stock import Product, Unit, name_key
from home_stock.persistence.catalog import list_units
from home_stock.persistence.history import list_latest_events, waste_by_period
from home_stock.persistence.products import list_products
from home_stock.ui.context import Context


class HistoryTab:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.search = ""
        self.waste_sections = ui.column().classes("w-full gap-4")
        ui.input("Szukaj produktu", on_change=self._searched).props("clearable outlined dense").classes("w-full").mark(
            "history-search"
        )
        self.content = ui.column().classes("w-full gap-0").mark("history-list")
        self.refresh()

    def _searched(self, event: ValueChangeEventArguments[str | None]) -> None:
        self.search = event.value or ""
        # The name filter leaves Waste as it is
        self._refresh_events(*self._products_and_units())

    def _products_and_units(self) -> tuple[dict[int, Product], dict[int, Unit]]:
        engine = self.ctx.engine
        # Archived Products keep their history, so it names them too
        products = {p.id: p for p in list_products(engine) + list_products(engine, archived=True)}
        return products, {unit.id: unit for unit in list_units(engine)}

    def refresh(self) -> None:
        products, units = self._products_and_units()
        self._refresh_waste(products, units)
        self._refresh_events(products, units)

    def _refresh_events(self, products: dict[int, Product], units: dict[int, Unit]) -> None:
        wanted = name_key(self.search)
        matching_ids = None if not wanted else [p.id for p in products.values() if wanted in name_key(p.name)]
        events = list_latest_events(self.ctx.engine, product_ids=matching_ids)
        self.content.clear()
        with self.content:
            if not events:
                ui.label("Historia jest pusta." if not wanted else "Brak zdarzeń pasujących produktów.")
                return
            for event in events:
                product = products[event.product_id]
                with ui.row().classes("w-full items-center no-wrap hs-line").mark("history-event"):
                    ui.label(format_date(event.on)).classes("hs-muted")
                    ui.label(product.name).classes("grow")
                    ui.label(format_event_kind(event))
                    ui.label(format_event_change(event, units[product.unit_id])).classes("hs-qty")

    def _refresh_waste(self, products: dict[int, Product], units: dict[int, Unit]) -> None:
        self.waste_sections.clear()
        with self.waste_sections:
            for days, lines in waste_by_period(self.ctx.engine, self.ctx.today()).items():
                with ui.column().classes("w-full gap-0 hs-section").mark(f"history-waste-{days}"):
                    ui.label(f"Marnowanie: ostatnie {days} dni").classes("hs-section-title q-mb-xs")
                    if not lines:
                        ui.label("Nic nie wyrzucono.").classes("hs-muted")
                    for line in lines:
                        product = products[line.product_id]
                        with ui.row().classes("w-full items-center no-wrap hs-line").mark(f"history-waste-{days}-line"):
                            ui.label(product.name).classes("grow")
                            ui.label(format_waste(line, units[product.unit_id])).classes("hs-qty")
