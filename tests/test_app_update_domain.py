"""The app's own update check: the latest GitHub Release read into its version and its installer or APK."""

import json

import pytest

from home_stock.domain.app_update import (
    UpdateError,
    android_build_number,
    apk_name,
    newer_release,
    parse_latest_release,
)

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
    assert release.url == "https://github.com/Gerruppa/Home-Stock/releases/download/v0.2.0/Home-Stock-0.2.0-setup.exe"
    assert release.size == 4321


def test_a_release_without_the_installer_is_refused() -> None:
    with pytest.raises(UpdateError, match="nie ma pliku Home-Stock-0.2.0-setup.exe"):
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

    with pytest.raises(UpdateError, match="nie ma pliku"):
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


def test_the_android_app_reads_the_apk_of_the_same_release() -> None:
    apk = {"name": "Home-Stock-0.2.0.apk", "browser_download_url": BASE + "Home-Stock-0.2.0.apk", "size": 9876}
    installer = {"name": "Home-Stock-0.2.0-setup.exe", "browser_download_url": BASE + "x.exe", "size": 1}

    release = parse_latest_release(_release(assets=[installer, apk]), asset=apk_name)

    assert (release.version, release.size) == ("0.2.0", 9876)
    assert release.url == "https://github.com/Gerruppa/Home-Stock/releases/download/v0.2.0/Home-Stock-0.2.0.apk"


def test_a_release_without_the_apk_is_refused() -> None:
    with pytest.raises(UpdateError, match="nie ma pliku Home-Stock-0.2.0.apk"):
        parse_latest_release(_release(), asset=apk_name)


@pytest.mark.parametrize(
    ("version", "number"), [("0.4.0", 400), ("0.4.1", 401), ("0.10.0", 1000), ("1.0.0", 10000), ("2.3.45", 20345)]
)
def test_the_android_build_number_grows_with_the_version(version: str, number: int) -> None:
    # Android installs an APK over the app only when its build number (versionCode) is higher
    assert android_build_number(version) == number


@pytest.mark.parametrize("version", ["0.100.0", "0.1.100"])
def test_a_version_part_over_99_has_no_build_number(version: str) -> None:
    with pytest.raises(ValueError, match="99"):
        android_build_number(version)
