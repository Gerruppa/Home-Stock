"""The update notice in the Android app: the check after start shows "Dostępna wersja X" beside the version in
Ustawienia, and tapping it hands the APK's download address to the phone."""

import http.client
import json
from pathlib import Path

import pytest
from sqlalchemy import Engine

from home_stock import __version__
from home_stock.mobile.shell import Shell
from home_stock.persistence.db import init_db
from home_stock.sources.app_update import UpdateSource
from mobile_ui import Screen, find, select, tap, texts

SETTINGS_TAB = 4
APK = "https://github.com/Gerruppa/Home-Stock/releases/download/v99.0.0/Home-Stock-99.0.0.apk"


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


def _answer(version: str, assets: list[dict[str, object]] | None = None) -> bytes:
    if assets is None:
        url = f"https://github.com/Gerruppa/Home-Stock/releases/download/v{version}/Home-Stock-{version}.apk"
        assets = [{"name": f"Home-Stock-{version}.apk", "browser_download_url": url, "size": 123}]
    return json.dumps({"tag_name": f"v{version}", "assets": assets}).encode()


def _shell(engine: Engine, screen: Screen) -> Shell:
    shell = Shell(engine, screen.present, screen.update, screen.views, screen.copy, screen.share, screen.open_url)
    select(shell.navigation_bar, SETTINGS_TAB)
    return shell


def _notice_shown(screen: Screen) -> bool:
    return find(screen.top, "update-available").visible


def test_nothing_shows_before_the_check(engine: Engine) -> None:
    screen = Screen()
    _shell(engine, screen)

    assert not _notice_shown(screen)


def test_a_newer_release_shows_beside_the_version_and_says_so(engine: Engine) -> None:
    screen = Screen()
    shell = _shell(engine, screen)

    shell.check_for_update(UpdateSource.android(fetch=lambda url: _answer("99.0.0")))

    assert _notice_shown(screen)
    assert texts(find(screen.top, "update-available")) == ["Dostępna wersja 99.0.0"]
    [bar] = screen.presented
    assert texts(bar) == ["Dostępna nowa wersja Home Stock: 99.0.0"]
    assert "Dostępna wersja 99.0.0" in screen.shown


def test_tapping_the_notice_hands_the_apk_to_the_phone(engine: Engine) -> None:
    screen = Screen()
    shell = _shell(engine, screen)
    shell.check_for_update(UpdateSource.android(fetch=lambda url: _answer("99.0.0")))

    tap(find(screen.top, "update-available"))

    assert screen.opened == [APK]
    assert "otwórz pobrany plik" in texts(screen.presented[-1])[0]


@pytest.mark.parametrize("version", [__version__, "0.0.1"])
def test_the_running_or_an_older_version_shows_nothing(engine: Engine, version: str) -> None:
    screen = Screen()
    shell = _shell(engine, screen)

    shell.check_for_update(UpdateSource.android(fetch=lambda url: _answer(version)))

    assert not _notice_shown(screen)
    assert screen.presented == []


def test_a_release_with_only_the_windows_installer_shows_nothing(engine: Engine) -> None:
    installer = "https://github.com/Gerruppa/Home-Stock/releases/download/v99.0.0/Home-Stock-99.0.0-setup.exe"
    answer = _answer("99.0.0", [{"name": "Home-Stock-99.0.0-setup.exe", "browser_download_url": installer, "size": 1}])
    screen = Screen()
    shell = _shell(engine, screen)

    shell.check_for_update(UpdateSource.android(fetch=lambda url: answer))

    assert not _notice_shown(screen)


def test_a_failed_check_stays_silent(engine: Engine) -> None:
    def offline(url: str) -> bytes:
        raise http.client.HTTPException("offline")

    screen = Screen()
    shell = _shell(engine, screen)

    shell.check_for_update(UpdateSource.android(fetch=offline))

    assert not _notice_shown(screen)
    assert screen.presented == []
