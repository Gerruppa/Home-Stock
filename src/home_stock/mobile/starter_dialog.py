"""Typowe produkty: the Starter Catalog as a full-screen dialog, of which the ticked Products are added in one go."""

import flet as ft

from home_stock.domain.formatting import format_days, format_pack_size
from home_stock.domain.stock import ProductDraft, Unit
from home_stock.mobile.context import Context
from home_stock.persistence.catalog import StockError, list_categories, list_units
from home_stock.persistence.products import add_products, remove_new_products
from home_stock.sources.starter_catalog import available_starter_drafts


def open_starter_dialog(ctx: Context) -> None:
    drafts = available_starter_drafts(ctx.engine)
    units = {unit.id: unit for unit in list_units(ctx.engine)}
    ticks: list[tuple[ProductDraft, ft.Checkbox]] = []
    rows: list[ft.Control] = [
        ft.Text(
            "Zaznaczone dodasz bez stanu minimalnego i bez partii."
            if drafts
            else "Masz już wszystkie typowe produkty.",
            size=12 if drafts else None,
            color=ft.Colors.ON_SURFACE_VARIANT if drafts else None,
        )
    ]
    for category in list_categories(ctx.engine):
        shown = [draft for draft in drafts if draft.category_id == category.id]
        if not shown:
            continue
        # Filled below, before anyone can tap the Category's tick
        in_category: list[ft.Checkbox] = []

        def tick_all(event: ft.Event[ft.Checkbox], in_category: list[ft.Checkbox] = in_category) -> None:
            for tick in in_category:
                tick.value = event.control.value
            ctx.update()

        rows.append(
            ft.Container(
                ft.Checkbox(
                    label=category.name,
                    value=True,
                    label_style=ft.TextStyle(weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                    on_change=tick_all,
                    key=f"starter-category-{category.id}",
                ),
                padding=ft.Padding.only(top=12),
            )
        )
        for draft in shown:
            tick = ft.Checkbox(label=draft.name, value=True, key=f"starter-tick-{len(ticks)}")
            ticks.append((draft, tick))
            in_category.append(tick)
            details = ft.Text(_details(draft, units[draft.unit_id]), size=12, color=ft.Colors.ON_SURFACE_VARIANT)
            rows.append(
                ft.Container(
                    ft.Column([tick, ft.Container(details, padding=ft.Padding.only(left=48))], spacing=0),
                    padding=ft.Padding.only(left=16),
                )
            )
    error = ft.Text("", color=ft.Colors.ERROR, visible=False, key="starter-error")
    rows.append(error)

    def save(_: object) -> None:
        chosen = [draft for draft, tick in ticks if tick.value]
        if not chosen:
            ctx.close_full_screen()
            return
        engine = ctx.engine
        try:
            added = add_products(engine, chosen)
        except StockError as problem:
            # A name taken meanwhile; the dialog stays, so nothing ticked is lost
            error.value = str(problem)
            error.visible = True
            ctx.update()
            return
        ctx.close_full_screen()
        ctx.changed()
        # All or nothing: ProductsInUseError leaves every Product in place once one has a Batch or a Stock Event
        ctx.undo(f"Dodano typowe produkty: {len(added)}", lambda: remove_new_products(engine, added))

    ctx.show_full_screen(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.IconButton(
                            ft.Icons.CLOSE,
                            tooltip="Anuluj",
                            on_click=lambda _: ctx.close_full_screen(),
                            key="starter-cancel",
                        ),
                        ft.Text("Typowe produkty", size=20, expand=True),
                        ft.FilledButton("Zapisz", on_click=save, visible=bool(drafts), key="starter-save"),
                        ft.Container(width=8),
                    ]
                ),
                ft.ListView(rows, padding=ft.Padding.symmetric(horizontal=16, vertical=8), expand=True),
            ],
            expand=True,
            key="starter-dialog",
        )
    )


def _details(draft: ProductDraft, unit: Unit) -> str:
    """ "opakowanie · 1 l · zwykle ważne 7 dni": the Unit, then the Pack Size and Usual Shelf Life where it has them."""
    parts = [unit.name]
    if draft.pack_size is not None:
        parts.append(format_pack_size(draft.pack_size))
    if draft.usual_shelf_life_days is not None:
        parts.append(f"zwykle ważne {format_days(draft.usual_shelf_life_days)}")
    return " · ".join(parts)
