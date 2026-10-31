"""The app's own update check: the latest GitHub Release read into its version and installer."""

import json

import pytest

from home_stock.domain.app_update import UpdateError, newer_release, parse_latest_release

BASE = "https://github.com/Gerruppa/Home-Stock/releases/download/v0.2.0/"


def _release(**changes: object) -> str:
    data: dict[str, object] = {
        "tag_name": "v0.2.0",
        "draft": False,
        "prerelease": False,
        "assets": [
            {"name": "notes.txt", "browser_download_url": BASE + "notes.txt", "size": 10},
            {
                "name": "Home-Stock-0.2.0-setup.exe",
                "browser_download_url": BASE + "Home-Stock-0.2.0-setup.exe",
                "size": 4321,
            },
        ],
    }
    data.update(changes)
    return json.dumps(data)


def test_the_release_gives_its_version_and_installer() -> None:
    release = parse_latest_release(_release())

    assert release.version == "0.2.0"
    assert (
        release.installer_url
        == "https://github.com/Gerruppa/Home-Stock/releases/download/v0.2.0/Home-Stock-0.2.0-setup.exe"
    )
    assert release.size == 4321


def test_a_release_without_the_installer_is_refused() -> None:
    with pytest.raises(UpdateError, match="nie ma instalatora Home-Stock-0.2.0-setup.exe"):
        parse_latest_release(_release(assets=[]))


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/Home-Stock-0.2.0-setup.exe",
        "https://github.com/Someone/Home-Stock/releases/download/v0.2.0/Home-Stock-0.2.0-setup.exe",
    ],
)
def test_an_installer_from_a_foreign_address_is_refused(url: str) -> None:
    assets = [{"name": "Home-Stock-0.2.0-setup.exe", "browser_download_url": url, "size": 1}]

    with pytest.raises(UpdateError, match="nie ma instalatora"):
        parse_latest_release(_release(assets=assets))


@pytest.mark.parametrize("tag", ["latest", "0.2.0", "v0.2", "v0.2.0-beta"])
def test_a_tag_that_is_not_v_x_y_z_is_refused(tag: str) -> None:
    with pytest.raises(UpdateError, match="numeru wersji"):
        parse_latest_release(_release(tag_name=tag))


@pytest.mark.parametrize(
    ("running", "offered"), [("0.1.0", True), ("0.1.9", True), ("0.2.0", False), ("0.10.0", False)]
)
def test_only_a_newer_release_is_offered(running: str, offered: bool) -> None:
    release = parse_latest_release(_release())

    assert newer_release(release, running) == (release if offered else None)


@pytest.mark.parametrize("text", ["<html>", "[]", '{"tag_name": "v0.2.0"}', '{"tag_name": "v0.2.0", "assets": 3}'])
def test_an_answer_of_another_shape_is_refused(text: str) -> None:
    with pytest.raises(UpdateError, match="Nieoczekiwana odpowiedź"):
        parse_latest_release(text)
