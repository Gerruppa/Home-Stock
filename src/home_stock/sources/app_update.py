"""The app's own updates: the latest GitHub Release and its APK, which the phone downloads and Android's own installer
puts over the app (from KAPITA's)."""

import http.client
import urllib.request
from collections.abc import Callable

from home_stock.domain.app_update import LatestRelease, UpdateError, parse_latest_release

LATEST_URL = "https://api.github.com/repos/Gerruppa/Home-Stock/releases/latest"
# What a failed fetch raises: no network, an HTTP error, or a connection cut mid-body (IncompleteRead)
_NETWORK_ERRORS = (OSError, http.client.HTTPException)


def fetch(url: str) -> bytes:
    """The body at ``url``; a failure raises one of _NETWORK_ERRORS."""
    request = urllib.request.Request(url, headers={"User-Agent": "Home Stock", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        body: bytes = response.read()
        return body


class UpdateSource:
    def __init__(self, fetch: Callable[[str], bytes] = fetch) -> None:
        self.fetch = fetch

    def latest(self) -> LatestRelease:
        try:
            body = self.fetch(LATEST_URL)
        except _NETWORK_ERRORS:
            raise UpdateError("Brak połączenia z GitHubem; nie sprawdzono, czy jest nowa wersja.") from None
        return parse_latest_release(body.decode("utf-8", errors="replace"))
