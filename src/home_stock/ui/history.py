"""Historia: the latest Stock Events of all Products, with a box that keeps one Product's by name."""

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from home_stock.domain.formatting import format_date, format_event_change, format_event_kind
from home_stock.domain.stock import name_key
from home_stock.persistence.catalog import list_units
from home_stock.persistence.history import list_latest_events
from home_stock.persistence.products import list_products
from home_stock.ui.context import Context

# How many Stock Events the tab shows at most
HISTORY_LIMIT = 200


class HistoryTab:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.search = ""
        ui.input("Szukaj produktu", on_change=self._searched).props("clearable outlined dense").classes("w-full").mark(
            "history-search"
        )
        self.content = ui.column().classes("w-full gap-0").mark("history-list")
        self.refresh()

    def _searched(self, event: ValueChangeEventArguments[str | None]) -> None:
        self.search = event.value or ""
        self.refresh()

    def refresh(self) -> None:
        engine = self.ctx.engine
        # Archived Products keep their history, so it names them too
        products = {p.id: p for p in list_products(engine) + list_products(engine, archived=True)}
        units = {unit.id: unit for unit in list_units(engine)}
        wanted = name_key(self.search)
        chosen = None if not wanted else [p.id for p in products.values() if wanted in name_key(p.name)]
        events = list_latest_events(engine, HISTORY_LIMIT, chosen)
        self.content.clear()
        with self.content:
            if not events:
                ui.label("Historia jest pusta." if not wanted else "Brak zdarzeń dla tego produktu.")
                return
            for event in events:
                product = products[event.product_id]
                with ui.row().classes("w-full items-center no-wrap hs-line").mark("history-event"):
                    ui.label(format_date(event.on)).classes("hs-muted")
                    ui.label(product.name).classes("grow")
                    ui.label(format_event_kind(event))
                    ui.label(format_event_change(event, units[product.unit_id])).classes("hs-qty")
