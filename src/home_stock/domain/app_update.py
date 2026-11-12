"""The app's own update check: the latest GitHub Release read into its version and its APK (from KAPITA's).

The Release is ``v<version>`` with the asset ``Home-Stock-<version>.apk`` (scripts/release.py publishes it); only a
download address on this project's own Releases is accepted.
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
    # Where the APK downloads from
    url: str


def apk_name(version: str) -> str:
    """The Android app's file name, as every Release carries it."""
    return f"Home-Stock-{version}.apk"


def android_build_number(version: str) -> int:
    """The APK's build number (Android's versionCode) for ``version``: Android installs an APK over the app only when
    this is higher, so X.Y.Z gives X·10000 + Y·100 + Z, which keeps the order while Y and Z stay under 100."""
    major, minor, patch = (int(part) for part in version.split("."))
    if minor > 99 or patch > 99:
        raise ValueError(f"{version}: the minor and patch parts must stay at 99 or under for the APK's build number")
    return major * 10000 + minor * 100 + patch


def parse_latest_release(text: str) -> LatestRelease:
    """The version and the APK of the GitHub API's ``releases/latest`` answer."""
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
    name = apk_name(version)
    for asset in assets:
        if isinstance(asset, dict) and asset.get("name") == name:
            url = asset.get("browser_download_url")
            if isinstance(url, str) and url.startswith(DOWNLOAD_PREFIX):
                return LatestRelease(version, url)
    raise UpdateError(f"Wydanie {version} nie ma pliku {name}.")


def newer_release(release: LatestRelease, current: str) -> LatestRelease | None:
    """``release`` when it is newer than the running ``current`` version."""
    return release if is_newer(release.version, current) else None
