"""The changelog: the shipped file, the version in the header opening it, and "Co nowego" once a version."""

import tempfile
from pathlib import Path

import pytest
from nicegui.testing import user_simulation
from sqlalchemy import Engine

from home_stock import __version__
from home_stock.app import start_demo_database
from home_stock.persistence.db import init_db
from home_stock.persistence.settings import LAST_ANNOUNCED_VERSION, load_setting, save_setting
from home_stock.ui.changelog import load_changelog
from home_stock.ui.shell import build_shell


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


def test_the_shipped_changelog_has_the_current_version() -> None:
    changelog = load_changelog()

    assert changelog.releases[0].version == __version__, f"changelog.md nie zaczyna się wersją {__version__}"


async def test_the_header_shows_the_running_version(engine: Engine) -> None:
    async with user_simulation(lambda: build_shell(engine)) as user:
        await user.open("/")

        await user.should_see(marker="app-version", content=f"wersja {__version__}")


async def test_clicking_the_version_opens_every_released_version(engine: Engine) -> None:
    async with user_simulation(lambda: build_shell(engine)) as user:
        await user.open("/")
        await user.should_not_see(marker="changelog")

        user.find(marker="app-version").click()

        await user.should_see(marker="changelog")
        with user.scope(marker="changelog"):
            await user.should_see("Historia zmian")
            await user.should_see("0.1.0 — ")
            await user.should_see("Nowe funkcje")
            await user.should_see("Lista zakupów wynika z minimalnych zapasów")
            await user.should_not_see("Nieopublikowane")


async def test_the_first_start_of_a_new_version_shows_it_once(engine: Engine) -> None:
    save_setting(engine, LAST_ANNOUNCED_VERSION, "0.0.9")
    async with user_simulation(lambda: build_shell(engine)) as user:
        await user.open("/")

        await user.should_see(marker="changelog")
        with user.scope(marker="changelog"):
            await user.should_see("Co nowego")
            await user.should_see(f"{__version__} — ")
    assert load_setting(engine, LAST_ANNOUNCED_VERSION) == __version__

    async with user_simulation(lambda: build_shell(engine)) as user:
        await user.open("/")
        await user.should_see(marker="app-version")

        await user.should_not_see(marker="changelog")


async def test_a_fresh_database_only_records_the_version(engine: Engine) -> None:
    async with user_simulation(lambda: build_shell(engine)) as user:
        await user.open("/")
        await user.should_see(marker="app-version")

        await user.should_not_see(marker="changelog")
    assert load_setting(engine, LAST_ANNOUNCED_VERSION) == __version__


async def test_a_version_without_a_changelog_section_shows_nothing(engine: Engine) -> None:
    save_setting(engine, LAST_ANNOUNCED_VERSION, __version__)
    async with user_simulation(lambda: build_shell(engine, version="99.0.0")) as user:
        await user.open("/")
        await user.should_see(marker="app-version")

        await user.should_not_see(marker="changelog")
    assert load_setting(engine, LAST_ANNOUNCED_VERSION) == "99.0.0"


async def test_going_back_to_an_older_version_keeps_the_newer_one_announced(engine: Engine) -> None:
    save_setting(engine, LAST_ANNOUNCED_VERSION, "99.0.0")
    async with user_simulation(lambda: build_shell(engine)) as user:
        await user.open("/")
        await user.should_see(marker="app-version")

        await user.should_not_see(marker="changelog")
    assert load_setting(engine, LAST_ANNOUNCED_VERSION) == "99.0.0"


async def test_the_demo_shows_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    engine = start_demo_database()
    async with user_simulation(lambda: build_shell(engine)) as user:
        await user.open("/")
        await user.should_see(marker="app-version")

        await user.should_not_see(marker="changelog")
