"""App entry point: `--browser` serves on http://127.0.0.1:8080, otherwise a native window opens."""

import argparse

from nicegui import ui

from home_stock import __version__


@ui.page("/")
def index() -> None:
    ui.label(f"Home Stock {__version__}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="home-stock")
    parser.add_argument("--browser", action="store_true", help="serve in the browser instead of a native window")
    args = parser.parse_args()
    ui.run(title="Home Stock", native=not args.browser, reload=False, host="127.0.0.1", port=8080)
