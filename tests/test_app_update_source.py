"""The update source: asks GitHub for the latest Release, downloads the installer and starts it."""

import http.client
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from home_stock.domain.app_update import LatestRelease, UpdateError
from home_stock.sources.app_update import UpdateSource

URL = "https://github.com/Gerruppa/Home-Stock/releases/download/v0.2.0/Home-Stock-0.2.0-setup.exe"
LATEST = (
    '{"tag_name": "v0.2.0", "assets": [{"name": "Home-Stock-0.2.0-setup.exe", "size": 5, '
    f'"browser_download_url": "{URL}"}}]}}'
)


def _source(fetch: Callable[[str], bytes], launched: list[list[str]] | None = None) -> UpdateSource:
    return UpdateSource(fetch=fetch, launch=(launched.append if launched is not None else lambda command: None))


def test_it_asks_github_for_the_latest_release() -> None:
    asked: list[str] = []

    def fetch(url: str) -> bytes:
        asked.append(url)
        return LATEST.encode()

    assert _source(fetch).latest().version == "0.2.0"
    assert asked == ["https://api.github.com/repos/Gerruppa/Home-Stock/releases/latest"]


def test_a_network_failure_is_an_update_error() -> None:
    def fetch(url: str) -> bytes:
        raise OSError("offline")

    with pytest.raises(UpdateError, match="połączenia"):
        _source(fetch).latest()


def test_a_broken_read_is_an_update_error_too() -> None:
    def fetch(url: str) -> bytes:
        raise http.client.IncompleteRead(b"{")

    with pytest.raises(UpdateError, match="połączenia"):
        _source(fetch).latest()


def test_the_installer_is_saved_under_its_own_name_whatever_the_address(tmp_path: Path) -> None:
    url = "https://github.com/Gerruppa/Home-Stock/releases/download/v0.2.0/other.msi"

    path = _source(lambda url: b"12345").download(LatestRelease("0.2.0", url, 5), tmp_path)

    assert path == tmp_path / "Home-Stock-0.2.0-setup.exe"


def test_it_downloads_the_installer_into_the_folder(tmp_path: Path) -> None:
    path = _source(lambda url: b"12345").download(LatestRelease("0.2.0", URL, 5), tmp_path)

    assert path == tmp_path / "Home-Stock-0.2.0-setup.exe"
    assert path.read_bytes() == b"12345"


def test_a_download_of_the_wrong_size_is_refused_and_not_kept(tmp_path: Path) -> None:
    with pytest.raises(UpdateError, match="Pobrany instalator jest uszkodzony; spróbuj ponownie."):
        _source(lambda url: b"123").download(LatestRelease("0.2.0", URL, 5), tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_a_failed_download_is_an_update_error(tmp_path: Path) -> None:
    def fetch(url: str) -> bytes:
        raise OSError("offline")

    with pytest.raises(UpdateError, match="pobrać"):
        _source(fetch).download(LatestRelease("0.2.0", URL, 5), tmp_path)


def test_a_broken_download_is_an_update_error(tmp_path: Path) -> None:
    def fetch(url: str) -> bytes:
        raise http.client.IncompleteRead(b"12")

    with pytest.raises(UpdateError, match="pobrać"):
        _source(fetch).download(LatestRelease("0.2.0", URL, 5), tmp_path)


def test_it_starts_the_installer_silently(tmp_path: Path) -> None:
    launched: list[list[str]] = []

    _source(lambda url: b"", launched).install(tmp_path / "setup.exe")

    assert launched == [[str(tmp_path / "setup.exe"), "/SILENT", "/CLOSEAPPLICATIONS", "/NORESTART"]]


@pytest.mark.parametrize(("frozen", "can_install"), [(True, True), (False, False)])
def test_only_the_installed_app_can_install(monkeypatch: pytest.MonkeyPatch, frozen: bool, can_install: bool) -> None:
    if frozen:
        monkeypatch.setattr(sys, "frozen", True, raising=False)
    else:
        monkeypatch.delattr(sys, "frozen", raising=False)

    assert UpdateSource.real().can_install is can_install
