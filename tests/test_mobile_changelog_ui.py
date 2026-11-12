"""The changelog in the Android app: the version at the bottom of Ustawienia opening it, and "Co nowego" once a
version."""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import Engine

from home_stock import __version__
from home_stock.mobile.app import start_demo_database
from home_stock.mobile.shell import Shell
from home_stock.persistence.db import init_db
from home_stock.persistence.settings import LAST_ANNOUNCED_VERSION, load_setting, save_setting
from home_stock.sources.changelog import load_changelog
from mobile_ui import Screen, absent, find, select, tap, texts, walk

SETTINGS_TAB = 4


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


def _start(engine: Engine, screen: Screen, version: str = __version__) -> Shell:
    return Shell(engine, screen.present, screen.update, screen.views, screen.copy, screen.share, version=version)


def test_ustawienia_shows_the_running_version(engine: Engine) -> None:
    screen = Screen()
    select(_start(engine, screen).navigation_bar, SETTINGS_TAB)

    assert find(screen.top, "app-version").content == f"wersja {__version__}"  # type: ignore[attr-defined]


def test_tapping_the_version_opens_every_released_version(engine: Engine) -> None:
    screen = Screen()
    shell = _start(engine, screen)
    select(shell.navigation_bar, SETTINGS_TAB)
    assert absent(screen.top, "changelog")

    tap(find(screen.top, "app-version"))

    shown = texts(find(screen.top, "changelog"))
    assert "Historia zmian" in shown
    assert any(text.startswith("0.1.0 — ") for text in shown)
    assert len([text for text in shown if " — " in text and text[0].isdigit()]) == len(load_changelog().releases)
    assert "Nowe funkcje" in shown
    assert any("Lista zakupów wynika z minimalnych zapasów" in text for text in shown)
    assert not any("Nieopublikowane" in text for text in shown)

    tap(find(screen.top, "changelog-close"))

    assert screen.top.navigation_bar is shell.navigation_bar


def test_the_first_start_of_a_new_version_shows_it_once(engine: Engine) -> None:
    save_setting(engine, LAST_ANNOUNCED_VERSION, "0.0.9")
    screen = Screen()
    _start(engine, screen)

    dialog = find(screen.top, "changelog")
    assert "Co nowego" in texts(dialog)
    assert [control.key for control in walk(dialog) if str(control.key).startswith("release-")] == [
        f"release-{__version__}"
    ]
    assert load_setting(engine, LAST_ANNOUNCED_VERSION) == __version__

    again = Screen()
    _start(engine, again)

    assert absent(again.top, "changelog")


def test_a_fresh_database_only_records_the_version(engine: Engine) -> None:
    screen = Screen()
    _start(engine, screen)

    assert absent(screen.top, "changelog")
    assert load_setting(engine, LAST_ANNOUNCED_VERSION) == __version__


def test_a_version_without_a_changelog_section_shows_nothing(engine: Engine) -> None:
    save_setting(engine, LAST_ANNOUNCED_VERSION, __version__)
    screen = Screen()
    _start(engine, screen, version="99.0.0")

    assert absent(screen.top, "changelog")
    assert load_setting(engine, LAST_ANNOUNCED_VERSION) == "99.0.0"


def test_going_back_to_an_older_version_keeps_the_newer_one_announced(engine: Engine) -> None:
    save_setting(engine, LAST_ANNOUNCED_VERSION, "99.0.0")
    screen = Screen()
    _start(engine, screen)

    assert absent(screen.top, "changelog")
    assert load_setting(engine, LAST_ANNOUNCED_VERSION) == "99.0.0"


def test_the_demo_shows_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    screen = Screen()
    _start(start_demo_database(), screen)

    assert absent(screen.top, "changelog")
