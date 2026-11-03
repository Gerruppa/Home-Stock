"""Android app entry point: the database in Flet's app-private data folder, backed up and migrated, and the shell on
it. On a computer ``flet run`` points that folder at ``.flet/storage/data``."""

import os
import traceback

import flet as ft
from sqlalchemy import Engine

from home_stock.mobile.shell import APP_TITLE, Shell
from home_stock.persistence.backup import backup_database
from home_stock.persistence.db import init_db
from home_stock.persistence.paths import DATA_DIR_ENV, backups_dir, database_path

# Where Flet keeps an app's durable private files (Android's app data, a folder of the project under flet run)
FLET_DATA_ENV = "FLET_APP_STORAGE_DATA"


def start_database() -> Engine:
    """The user's database, with a Backup taken before migrations touch it."""
    path = database_path()
    backup_database(path, backups_dir())
    return init_db(path)


def main(page: ft.Page) -> None:
    page.title = APP_TITLE
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    try:
        shell = Shell(start_database(), page.show_dialog, page.update)
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
    page.navigation_bar = shell.navigation_bar
    page.add(ft.SafeArea(shell.body, expand=True))


def run() -> None:
    if os.environ.get(FLET_DATA_ENV):
        os.environ[DATA_DIR_ENV] = os.environ[FLET_DATA_ENV]
    ft.run(main)
