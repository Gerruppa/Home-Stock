"""The update source: asks GitHub for the latest Release and its APK."""

import http.client

import pytest

from home_stock.domain.app_update import UpdateError
from home_stock.sources.app_update import UpdateSource

APK = "https://github.com/Gerruppa/Home-Stock/releases/download/v0.2.0/Home-Stock-0.2.0.apk"
LATEST = (
    '{"tag_name": "v0.2.0", "assets": [{"name": "Home-Stock-0.2.0.apk", "size": 7, '
    f'"browser_download_url": "{APK}"}}]}}'
)


def test_it_asks_github_for_the_latest_release_and_its_apk() -> None:
    asked: list[str] = []

    def fetch(url: str) -> bytes:
        asked.append(url)
        return LATEST.encode()

    latest = UpdateSource(fetch=fetch).latest()

    assert (latest.version, latest.url) == ("0.2.0", APK)
    assert asked == ["https://api.github.com/repos/Gerruppa/Home-Stock/releases/latest"]


def test_a_release_without_the_apk_is_refused() -> None:
    answer = '{"tag_name": "v0.2.0", "assets": []}'

    with pytest.raises(UpdateError, match="nie ma pliku Home-Stock-0.2.0.apk"):
        UpdateSource(fetch=lambda url: answer.encode()).latest()


def test_a_network_failure_is_an_update_error() -> None:
    def fetch(url: str) -> bytes:
        raise OSError("offline")

    with pytest.raises(UpdateError, match="połączenia"):
        UpdateSource(fetch=fetch).latest()


def test_a_broken_read_is_an_update_error_too() -> None:
    def fetch(url: str) -> bytes:
        raise http.client.IncompleteRead(b"{")

    with pytest.raises(UpdateError, match="połączenia"):
        UpdateSource(fetch=fetch).latest()
