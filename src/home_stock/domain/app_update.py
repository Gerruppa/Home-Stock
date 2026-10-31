"""The app's own update check: the latest GitHub Release read into its version and the installer to download (from
KAPITA's).

The Release is ``v<version>`` with an asset ``Home-Stock-<version>-setup.exe`` (scripts/release.py publishes it); only
a download address on this project's own Releases is accepted.
"""

import json
import re
from dataclasses import dataclass

from home_stock.domain.changelog import is_newer

RELEASES_PAGE = "https://github.com/Gerruppa/Home-Stock/releases/latest"
DOWNLOAD_PREFIX = "https://github.com/Gerruppa/Home-Stock/releases/download/"

_TAG = re.compile(r"^v(?P<version>\d+\.\d+\.\d+)$")


class UpdateError(ValueError):
    """The Release cannot be used, or the update failed; the message is Polish."""


@dataclass(frozen=True)
class LatestRelease:
    version: str
    installer_url: str
    size: int


def installer_name(version: str) -> str:
    """The installer's file name, as scripts/build_installer.ps1 builds it and every Release carries it."""
    return f"Home-Stock-{version}-setup.exe"


def parse_latest_release(text: str) -> LatestRelease:
    """The version and installer of the GitHub API's ``releases/latest`` answer."""
    try:
        data = json.loads(text)
        tag = _TAG.match(str(data["tag_name"]))
        assets = data["assets"]
        if not isinstance(assets, list):
            raise TypeError
    except ValueError, KeyError, TypeError:
        raise UpdateError("Nieoczekiwana odpowiedź GitHuba o najnowszej wersji.") from None
    if tag is None:
        raise UpdateError("Najnowsze wydanie nie ma numeru wersji.")
    version = tag["version"]
    name = installer_name(version)
    for asset in assets:
        if isinstance(asset, dict) and asset.get("name") == name:
            url, size = asset.get("browser_download_url"), asset.get("size")
            if isinstance(url, str) and url.startswith(DOWNLOAD_PREFIX) and isinstance(size, int):
                return LatestRelease(version, url, size)
    raise UpdateError(f"Wydanie {version} nie ma instalatora {name}.")


def newer_release(release: LatestRelease, current: str) -> LatestRelease | None:
    """``release`` when it is newer than the running ``current`` version."""
    return release if is_newer(release.version, current) else None
