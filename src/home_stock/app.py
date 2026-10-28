"""App entry point: the database in the user's app-data folder, migrated, and the shell on it in a native window
(``--browser`` serves it on http://127.0.0.1:8080 instead; ``--demo`` serves made-up data from TEMP there)."""

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from typing import Any

from nicegui import ui
from sqlalchemy import Engine

from home_stock.persistence.db import init_db
from home_stock.persistence.paths import database_path, demo_database_path
from home_stock.sources.demo_data import seed_demo_data
from home_stock.ui.shell import APP_TITLE, build_shell


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    # No abbreviations: under the tests sys.argv holds pytest's own options
    parser = argparse.ArgumentParser(prog="home-stock", allow_abbrev=False)
    parser.add_argument("--browser", action="store_true", help="UI w przeglądarce (localhost) zamiast okna")
    parser.add_argument("--demo", action="store_true", help="przykładowe dane w folderze tymczasowym, w przeglądarce")
    parser.add_argument("--port", type=int, default=8080)
    # parse_known_args: a frozen exe may get arguments of its own (multiprocessing)
    return parser.parse_known_args(argv)[0]


def run_options(args: argparse.Namespace) -> dict[str, Any]:
    """window_size alone switches NiceGUI to native mode, so the browser mode (``--browser`` or ``--demo``) leaves it
    out; the native window finds a free port itself, the browser mode opens no tab (the URL is in the console) and
    listens on this computer only."""
    if args.browser or args.demo:
        return {"host": "127.0.0.1", "port": args.port, "show": False}
    return {"native": True, "window_size": (1200, 800)}


def start_demo_database() -> Engine:
    """A fresh database in TEMP filled with the demo data, replacing the last demo's; real data stays untouched."""
    path = demo_database_path()
    path.unlink(missing_ok=True)
    engine = init_db(path)
    seed_demo_data(engine, date.today())
    return engine


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    engine = start_demo_database() if args.demo else init_db(database_path())
    ui.run(lambda: build_shell(engine), title=APP_TITLE, reload=False, language="pl", **run_options(args))
