"""The update notice beside the version in the header: shown for a newer Release only; installing starts the installer
and shuts the app down."""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest
from nicegui import ui
from nicegui.testing import user_simulation
from sqlalchemy import Engine

from home_stock.persistence.db import init_db
from home_stock.sources.app_update import UpdateSource
from home_stock.ui.shell import build_shell

RUNNING = "0.2.0"


def _latest(version: str) -> bytes:
    name = f"Home-Stock-{version}-setup.exe"
    url = f"https://github.com/Gerruppa/Home-Stock/releases/download/v{version}/{name}"
    asset = {"name": name, "size": 3, "browser_download_url": url}
    return json.dumps({"tag_name": f"v{version}", "assets": [asset]}).encode()


class FakeGitHub:
    """Answers the update check with a Release of ``version`` (or fails when offline) and serves ``installer``."""

    def __init__(self, version: str = "0.3.0", installer: bytes = b"abc", offline: bool = False) -> None:
        self.version, self.installer, self.offline = version, installer, offline
        self.asked: list[str] = []
        self.launched: list[list[str]] = []

    def fetch(self, url: str) -> bytes:
        self.asked.append(url)
        if self.offline:
            raise OSError("offline")
        return _latest(self.version) if "api.github.com" in url else self.installer

    def source(self, can_install: bool = True) -> UpdateSource:
        return UpdateSource(fetch=self.fetch, launch=self.launched.append, can_install=can_install)

    async def checked(self) -> None:
        """Wait until the check has asked GitHub and had a moment to act on the answer."""
        for _ in range(50):
            if self.asked:
                break
            await asyncio.sleep(0.1)
        else:
            raise AssertionError("the update check never ran")
        await asyncio.sleep(0.3)


@pytest.fixture(autouse=True)
def _no_wait_and_scratch_temp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("home_stock.ui.app_update.CHECK_DELAY", 0.0)
    # The downloaded installer goes to a temp folder: keep it out of the real TEMP
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "temp"))
    (tmp_path / "temp").mkdir()


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


async def test_a_newer_release_shows_the_notice(engine: Engine) -> None:
    github = FakeGitHub("0.3.0")
    async with user_simulation(lambda: build_shell(engine, version=RUNNING, updates=github.source())) as user:
        await user.open("/")

        await user.should_see(marker="update-available", content="Dostępna wersja 0.3.0")


@pytest.mark.parametrize("latest", [RUNNING, "0.1.0"])
async def test_the_same_or_an_older_release_shows_nothing(engine: Engine, latest: str) -> None:
    github = FakeGitHub(latest)
    async with user_simulation(lambda: build_shell(engine, version=RUNNING, updates=github.source())) as user:
        await user.open("/")
        await github.checked()

        await user.should_not_see(marker="update-available")


async def test_the_notice_opens_the_update_dialog(engine: Engine) -> None:
    github = FakeGitHub("0.3.0")
    async with user_simulation(lambda: build_shell(engine, version=RUNNING, updates=github.source())) as user:
        await user.open("/")
        await user.should_see(marker="update-available", content="Dostępna wersja 0.3.0")

        user.find(marker="update-available").click()

        with user.scope(marker="update-dialog"):
            await user.should_see("Dostępna wersja 0.3.0")
            await user.should_see("Home Stock pobierze instalator, zamknie się, zaktualizuje i uruchomi ponownie.")
            await user.should_see("Twoje dane zostają")
            await user.should_see(marker="update-install", content="Zainstaluj teraz")
            await user.should_see(marker="update-page", content="Strona wydań")
            await user.should_see(marker="update-later", content="Później")


async def test_without_install_the_dialog_only_points_to_the_release_page(engine: Engine) -> None:
    github = FakeGitHub("0.3.0")
    source = github.source(can_install=False)
    async with user_simulation(lambda: build_shell(engine, version=RUNNING, updates=source)) as user:
        await user.open("/")
        await user.should_see(marker="update-available", content="Dostępna wersja 0.3.0")

        user.find(marker="update-available").click()

        await user.should_see(marker="update-page", content="Strona wydań")
        await user.should_see(marker="update-later", content="Później")
        await user.should_not_see(marker="update-install")


@pytest.fixture
def shutdowns(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    """Each app shutdown asked for, instead of stopping the test server."""
    asked: list[bool] = []
    monkeypatch.setattr("home_stock.ui.app_update.app.shutdown", lambda: asked.append(True))
    return asked


async def test_installing_starts_the_installer_silently_and_shuts_down(engine: Engine, shutdowns: list[bool]) -> None:
    github = FakeGitHub("0.3.0", installer=b"abc")
    async with user_simulation(lambda: build_shell(engine, version=RUNNING, updates=github.source())) as user:
        await user.open("/")
        await user.should_see(marker="update-available", content="Dostępna wersja 0.3.0")
        user.find(marker="update-available").click()

        user.find(marker="update-install").click()

        await user.should_see(marker="update-status", content="Uruchamianie instalatora…")
    [[installer, *args]] = github.launched
    assert Path(installer).name == "Home-Stock-0.3.0-setup.exe"
    assert Path(installer).is_relative_to(tempfile.gettempdir())
    assert Path(installer).read_bytes() == b"abc"
    assert args == ["/SILENT", "/CLOSEAPPLICATIONS", "/NORESTART"]
    assert shutdowns == [True]


async def test_a_damaged_download_launches_nothing_and_can_be_retried(engine: Engine, shutdowns: list[bool]) -> None:
    github = FakeGitHub("0.3.0", installer=b"ab")
    async with user_simulation(lambda: build_shell(engine, version=RUNNING, updates=github.source())) as user:
        await user.open("/")
        await user.should_see(marker="update-available", content="Dostępna wersja 0.3.0")
        user.find(marker="update-available").click()

        user.find(marker="update-install").click()

        await user.should_see(marker="update-status", content="Pobrany instalator jest uszkodzony; spróbuj ponownie.")
        assert github.launched == []
        [install] = user.find(marker="update-install").elements
        assert isinstance(install, ui.button) and install.enabled

        github.installer = b"abc"
        user.find(marker="update-install").click()

        await user.should_see(marker="update-status", content="Uruchamianie instalatora…")
    assert len(github.launched) == 1
    assert shutdowns == [True]


async def test_a_failed_check_stays_silent(engine: Engine) -> None:
    github = FakeGitHub(offline=True)
    async with user_simulation(lambda: build_shell(engine, version=RUNNING, updates=github.source())) as user:
        await user.open("/")
        await github.checked()

        await user.should_not_see(marker="update-available")
