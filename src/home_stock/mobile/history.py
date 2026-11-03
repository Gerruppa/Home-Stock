"""Historia: Waste over the last 30 and 90 days, then the latest Stock Events of all Products, with a box that keeps
those of the Products matching a name."""

import flet as ft

from home_stock.domain.formatting import format_date, format_event_change, format_event_kind, format_waste
from home_stock.domain.stock import Product, Unit, name_key
from home_stock.mobile.context import Context
from home_stock.persistence.catalog import list_units
from home_stock.persistence.history import list_latest_events, waste_by_period
from home_stock.persistence.products import list_products


class HistoryTab:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.search = ""
        self.waste_sections = ft.Column(spacing=16)
        search = ft.TextField(
            label="Szukaj produktu",
            prefix_icon=ft.Icons.SEARCH,
            dense=True,
            expand=True,
            on_change=self._searched,
            key="history-search",
        )
        self.events = ft.Column(spacing=0, key="history-list")
        self.control: ft.Control = ft.Column(
            [
                ft.Container(self.waste_sections, padding=ft.Padding.symmetric(horizontal=16, vertical=8)),
                ft.Container(ft.Row([search]), padding=ft.Padding.symmetric(horizontal=12, vertical=8)),
                ft.Container(self.events, padding=ft.Padding.only(left=16, right=16, bottom=16)),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=0,
        )
        self.refresh()

    def _searched(self, event: ft.Event[ft.TextField]) -> None:
        self.search = event.control.value or ""
        # The name filter leaves Waste as it is
        self._refresh_events(*self._products_and_units())
        self.ctx.update()

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
        if not events:
            message = "Historia jest pusta." if not wanted else "Brak zdarzeń pasujących produktów."
            self.events.controls = [ft.Text(message)]
            return
        rows: list[ft.Control] = []
        for event in events:
            product = products[event.product_id]
            rows.append(
                ft.Row(
                    [
                        ft.Text(format_date(event.on), size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(product.name, expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(format_event_kind(event), size=12),
                        ft.Text(format_event_change(event, units[product.unit_id]), weight=ft.FontWeight.W_500),
                    ],
                    spacing=8,
                    key="history-event",
                )
            )
        self.events.controls = rows

    def _refresh_waste(self, products: dict[int, Product], units: dict[int, Unit]) -> None:
        sections: list[ft.Control] = []
        for days, lines in waste_by_period(self.ctx.engine, self.ctx.today()).items():
            rows: list[ft.Control] = [ft.Text(f"Marnowanie: ostatnie {days} dni", weight=ft.FontWeight.BOLD)]
            if not lines:
                rows.append(ft.Text("Nic nie wyrzucono.", color=ft.Colors.ON_SURFACE_VARIANT))
            for line in lines:
                product = products[line.product_id]
                rows.append(
                    ft.Row(
                        [
                            ft.Text(product.name, expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(format_waste(line, units[product.unit_id]), weight=ft.FontWeight.W_500),
                        ],
                        key=f"history-waste-{days}-line",
                    )
                )
            sections.append(ft.Column(rows, spacing=4, key=f"history-waste-{days}"))
        self.waste_sections.controls = sections
