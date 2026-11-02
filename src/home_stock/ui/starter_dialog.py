"""Typowe produkty: the Starter Catalog, of which the ticked Products are added in one go."""

from nicegui import ui

from home_stock.domain.formatting import format_days, format_pack_size
from home_stock.domain.stock import ProductDraft, Unit
from home_stock.persistence.catalog import StockError, list_categories, list_units
from home_stock.persistence.products import add_products, remove_new_products
from home_stock.sources.starter_catalog import available_starter_drafts
from home_stock.ui.context import Context
from home_stock.ui.dialog_keys import wire_dialog_keys
from home_stock.ui.fields import error_label, show_error


def open_starter_dialog(ctx: Context) -> None:
    drafts = available_starter_drafts(ctx.engine)
    units = {unit.id: unit for unit in list_units(ctx.engine)}
    ticks: list[tuple[ProductDraft, ui.checkbox]] = []
    with ctx.overlay, ui.dialog() as dialog, ui.card().classes("w-96").mark("starter-dialog") as card:
        ui.label("Typowe produkty").classes("hs-dialog-title")
        if drafts:
            ui.label("Zaznaczone dodasz bez stanu minimalnego i bez partii.").classes("hs-muted text-sm")
        else:
            ui.label("Masz już wszystkie typowe produkty.")
        for category in list_categories(ctx.engine):
            shown = [draft for draft in drafts if draft.category_id == category.id]
            if not shown:
                continue
            category_tick = ui.checkbox(category.name, value=True).classes("hs-section-title q-mt-sm")
            category_tick.mark(f"starter-category-{category.id}")
            in_category = []
            for draft in shown:
                with ui.column().classes("w-full gap-0 q-ml-md"):
                    tick = ui.checkbox(draft.name, value=True).mark(f"starter-tick-{len(ticks)}")
                    ui.label(_details(draft, units[draft.unit_id])).classes("hs-muted text-sm q-ml-xl")
                ticks.append((draft, tick))
                in_category.append(tick)
            category_tick.on_value_change(
                lambda event, in_category=in_category: [tick.set_value(event.value) for tick in in_category]
            )
        error = error_label().mark("starter-error")

        def save() -> None:
            chosen = [draft for draft, tick in ticks if tick.value]
            if not chosen:
                dialog.close()
                return
            engine = ctx.engine
            try:
                added = add_products(engine, chosen)
            except StockError as problem:
                # A name taken in another window meanwhile; the dialog stays, so nothing ticked is lost
                show_error(error, str(problem))
                return
            dialog.close()
            ctx.changed()
            # All or nothing: ProductsInUseError leaves every Product in place once one has a Batch or a Stock Event
            ctx.undo(f"Dodano typowe produkty: {len(added)}", lambda: remove_new_products(engine, added))

        with ui.row().classes("w-full justify-end"):
            ui.button("Anuluj", on_click=dialog.close).props("flat")
            ui.button("Zapisz", on_click=save).mark("starter-save").set_visibility(bool(drafts))
    wire_dialog_keys(dialog, card, save)
    # A hundred rows each time it opens: gone once closed
    dialog.on("hide", dialog.delete)
    dialog.open()


def _details(draft: ProductDraft, unit: Unit) -> str:
    """ "opakowanie · 1 l · zwykle ważne 7 dni": the Unit, then the Pack Size and Usual Shelf Life where it has them."""
    parts = [unit.name]
    if draft.pack_size is not None:
        parts.append(format_pack_size(draft.pack_size))
    if draft.usual_shelf_life_days is not None:
        parts.append(f"zwykle ważne {format_days(draft.usual_shelf_life_days)}")
    return " · ".join(parts)
