"""The changelog: the shipped file, and the version in the header opening it."""

from pathlib import Path

import pytest
from nicegui.testing import user_simulation
from sqlalchemy import Engine

from home_stock import __version__
from home_stock.persistence.db import init_db
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
            await user.should_not_see("kopię zapasową")
