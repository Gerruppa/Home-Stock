import os
from pathlib import Path

import flet as ft
import pytest
from sqlalchemy import Engine

from home_stock.mobile import app
from home_stock.mobile.shell import UNDO_MILLISECONDS, Shell
from home_stock.persistence.catalog import StockError
from home_stock.persistence.db import init_db
from home_stock.persistence.paths import DATA_DIR_ENV
from mobile_ui import Screen, find, select, tap, texts


class CountingTab:
    def __init__(self, name: str) -> None:
        self.control: ft.Control = ft.Text(name, key=f"counting-{name}")
        self.refreshes = 0

    def refresh(self) -> None:
        self.refreshes += 1


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "home_stock.sqlite3")


@pytest.fixture
def screen() -> Screen:
    return Screen()


@pytest.fixture
def shell(engine: Engine, screen: Screen) -> Shell:
    return Shell(engine, screen.present, screen.update)


def test_five_tabs_open_on_start(shell: Shell) -> None:
    labels = [destination.label for destination in shell.navigation_bar.destinations]
    assert labels == ["Start", "Produkty", "Zakupy", "Historia", "Ustawienia"]
    assert shell.navigation_bar.selected_index == 0
    assert shell.body.content is shell.tabs[0][2].control
    assert texts(shell.body) == ["Wkrótce"]


def test_a_tap_on_a_destination_shows_its_tab(shell: Shell, screen: Screen) -> None:
    shell.tabs[3] = (ft.Icons.HISTORY, "Historia", CountingTab("historia"))

    select(shell.navigation_bar, 3)

    assert shell.navigation_bar.selected_index == 3
    assert find(shell.body, "counting-historia")
    assert screen.updates == 1


def test_a_change_redraws_every_tab(shell: Shell, screen: Screen) -> None:
    tabs = [CountingTab(str(index)) for index in range(5)]
    shell.tabs = [(icon, label, tab) for (icon, label, _), tab in zip(shell.tabs, tabs, strict=True)]

    shell.ctx.changed()

    assert [tab.refreshes for tab in tabs] == [1] * 5
    assert screen.updates == 1


def test_undo_offers_cofnij_which_takes_the_change_back(shell: Shell, screen: Screen) -> None:
    tab = CountingTab("start")
    shell.tabs[0] = (ft.Icons.HOME_OUTLINED, "Start", tab)
    undone: list[bool] = []

    shell.ctx.changed()
    shell.ctx.undo("Zużyto 1 × Mleko", lambda: undone.append(True))

    [snackbar] = screen.presented
    assert snackbar.open
    assert texts(snackbar) == ["Zużyto 1 × Mleko"]
    assert snackbar.action == "Cofnij"

    tap(snackbar, "on_action")

    assert undone == [True]
    assert tab.refreshes == 2
    assert not snackbar.open


def test_the_snackbar_goes_away_on_its_own_even_with_cofnij(shell: Shell, screen: Screen) -> None:
    shell.ctx.undo("Dodano: Ryż", lambda: None)

    [snackbar] = screen.presented
    # Flutter keeps a snackbar with an action up until it is tapped, unless told not to persist
    assert snackbar.persist is False
    assert snackbar.duration == UNDO_MILLISECONDS


def test_a_later_change_withdraws_cofnij(shell: Shell, screen: Screen) -> None:
    shell.ctx.undo("Zużyto 1 × Mleko", lambda: None)

    shell.ctx.changed()

    assert not screen.presented[0].open


def test_an_undo_that_fails_says_why_without_cofnij(shell: Shell, screen: Screen) -> None:
    def gone() -> None:
        raise StockError("Tej partii już nie ma.")

    shell.ctx.undo("Wyrzucono partię", gone)
    snackbar = screen.presented[0]

    tap(snackbar, "on_action")

    assert snackbar.open
    assert texts(snackbar) == ["Tej partii już nie ma."]
    assert snackbar.action is None


def test_the_next_undo_reuses_the_open_snackbar(shell: Shell, screen: Screen) -> None:
    shell.ctx.undo("Zużyto 1 × Mleko", lambda: None)
    shell.ctx.undo("Zużyto 1 × Chleb", lambda: None)

    assert len(screen.presented) == 1
    assert texts(screen.presented[0]) == ["Zużyto 1 × Chleb"]


def test_the_database_is_backed_up_before_migrations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path))

    app.start_database().dispose()
    assert not (tmp_path / "backups").exists()

    app.start_database().dispose()
    assert len(list((tmp_path / "backups").iterdir())) == 1


def test_the_data_folder_is_flets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(app.FLET_DATA_ENV, str(tmp_path))
    monkeypatch.delenv(DATA_DIR_ENV, raising=False)
    monkeypatch.setattr(ft, "run", lambda main: None)

    app.run()

    assert os.environ[DATA_DIR_ENV] == str(tmp_path)
