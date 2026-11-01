"""The printable Shopping List: a page of its own, with no header, tabs or buttons, opened by "Drukuj"."""

from nicegui import ui
from sqlalchemy import Engine

from home_stock.ui.shopping import PRINT_PATH, shopping_list_text


def register_print_page(engine: Engine) -> None:
    """Serve the list at PRINT_PATH, read afresh on every visit."""

    @ui.page(PRINT_PATH, title="Lista zakupów")
    def print_page() -> None:
        # Text and Category blocks are the ones "Kopiuj listę" copies: a heading line, then one line per Product
        with ui.column().classes("gap-1 q-pa-md"):
            for block in shopping_list_text(engine).split("\n\n"):
                heading, *lines = block.split("\n")
                ui.label(heading).classes("text-h6 q-mt-md")
                for line in lines:
                    ui.label(line)
        # The print dialog is the page's only purpose
        ui.run_javascript("window.print()")
