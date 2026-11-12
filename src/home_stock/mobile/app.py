"""Android app entry point: the database in Flet's app-private data folder, backed up and migrated, and the shell on
it. On a computer ``flet run`` points that folder at ``.flet/storage/data``, and ``--demo`` starts the shell on made-up
data instead. A few seconds after start the app asks GitHub for a newer Release (never in the demo)."""

import os
import sys
import time
import traceback
from collections.abc import Sequence
from datetime import date

import flet as ft
from sqlalchemy import Engine

from home_stock.mobile.app_update import CHECK_DELAY
from home_stock.mobile.shell import APP_TITLE, Shell
from home_stock.persistence.backup import backup_database
from home_stock.persistence.db import init_db
from home_stock.persistence.paths import DATA_DIR_ENV, android_demo_database_path, backups_dir, database_path
from home_stock.sources.app_update import UpdateSource
from home_stock.sources.demo_data import seed_demo_data

# Where Flet keeps an app's durable private files (Android's app data, a folder of the project under flet run)
FLET_DATA_ENV = "FLET_APP_STORAGE_DATA"


def start_database() -> Engine:
    """The user's database, with a Backup taken before migrations touch it."""
    path = database_path()
    backup_database(path, backups_dir())
    return init_db(path)


def start_demo_database() -> Engine:
    """A fresh database in TEMP filled with the demo data, replacing the last demo's; real data stays untouched."""
    path = android_demo_database_path()
    path.unlink(missing_ok=True)
    engine = init_db(path)
    seed_demo_data(engine, date.today())
    return engine


def main(page: ft.Page, demo: bool = False) -> None:
    page.title = APP_TITLE
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    # Services register with the page as they are made; copy and share hold them for as long as the shell lives
    clipboard, share_sheet, launcher = ft.Clipboard(), ft.Share(), ft.UrlLauncher()

    def copy(text: str) -> None:
        page.run_task(clipboard.set, text)

    def share(text: str) -> None:
        page.run_task(share_sheet.share_text, text)

    async def launch(url: str) -> None:
        # Outside the app: the browser downloads the APK, and opening the download starts Android's installer
        await launcher.launch_url(url, mode=ft.LaunchMode.EXTERNAL_APPLICATION)

    def open_url(url: str) -> None:
        page.run_task(launch, url)

    try:
        engine = start_demo_database() if demo else start_database()
        shell = Shell(engine, page.show_dialog, page.update, page.views, copy, share, open_url=open_url)
    except Exception:
        # No console on a phone: the traceback on screen is the only way to see what broke
        page.add(
            ft.SafeArea(
                ft.Column(
                    [ft.Text("Błąd startu", size=20), ft.Text(traceback.format_exc(), size=11, selectable=True)],
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
                expand=True,
            )
        )
        return
    # Android's Back asks to pop the top view; with only the tabs' view there is nothing to pop and Back leaves the app
    page.on_view_pop = lambda _: shell.close_full_screen()
    page.update()
    if not demo:
        page.run_thread(_check_for_update, shell)


def _check_for_update(shell: Shell) -> None:
    """On a thread of its own, so neither the wait nor the network holds up the screen."""
    time.sleep(CHECK_DELAY)
    shell.check_for_update(UpdateSource.android())


def run(argv: Sequence[str] | None = None) -> None:
    # Only the previews pass --demo; on the phone the app starts with no arguments
    demo = "--demo" in (sys.argv[1:] if argv is None else argv)
    if os.environ.get(FLET_DATA_ENV):
        os.environ[DATA_DIR_ENV] = os.environ[FLET_DATA_ENV]
    ft.run(lambda page: main(page, demo))
