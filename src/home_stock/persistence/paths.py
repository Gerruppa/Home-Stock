"""Location of the user's data, always outside the repository."""

import os
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "Home Stock"
DATA_DIR_ENV = "HOME_STOCK_DATA_DIR"
DATABASE_FILE = "home_stock.sqlite3"


def data_dir() -> Path:
    """The app-data folder (e.g. %LOCALAPPDATA%/Home Stock); override with HOME_STOCK_DATA_DIR."""
    override = os.environ.get(DATA_DIR_ENV)
    return Path(override) if override else Path(user_data_dir(APP_NAME, appauthor=False))


def database_path() -> Path:
    return data_dir() / DATABASE_FILE
