"""The app's own updates: the latest GitHub Release, the download of its installer and starting it (from KAPITA's; the
installer built by scripts/build_installer.ps1 upgrades the installed Home Stock in place and keeps the data folder)."""

import http.client
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path

from home_stock.domain.app_update import LatestRelease, UpdateError, installer_name, parse_latest_release

LATEST_URL = "https://api.github.com/repos/Gerruppa/Home-Stock/releases/latest"
# Inno Setup: no wizard, close the running Home Stock first, no reboot; the installer starts the new version itself
INSTALLER_ARGS = ("/SILENT", "/CLOSEAPPLICATIONS", "/NORESTART")
# What a failed fetch raises: no network, an HTTP error, or a connection cut mid-body (IncompleteRead)
_NETWORK_ERRORS = (OSError, http.client.HTTPException)


def fetch(url: str) -> bytes:
    """The body at ``url``; a failure raises one of _NETWORK_ERRORS."""
    request = urllib.request.Request(url, headers={"User-Agent": "Home Stock", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        body: bytes = response.read()
        return body


def launch(command: list[str]) -> None:
    """Start ``command`` apart from this process, which exits right after so the installer can replace its files."""
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    subprocess.Popen(command, creationflags=flags, close_fds=True)


class UpdateSource:
    def __init__(
        self,
        fetch: Callable[[str], bytes] = fetch,
        launch: Callable[[list[str]], None] = launch,
        can_install: bool = False,
    ) -> None:
        self.fetch = fetch
        self.launch = launch
        # Only the installed (frozen) app can be replaced by the installer; a source checkout just points to the page
        self.can_install = can_install

    @classmethod
    def real(cls) -> UpdateSource:
        return cls(can_install=bool(getattr(sys, "frozen", False)))

    def latest(self) -> LatestRelease:
        try:
            body = self.fetch(LATEST_URL)
        except _NETWORK_ERRORS:
            raise UpdateError("Brak połączenia z GitHubem; nie sprawdzono, czy jest nowa wersja.") from None
        return parse_latest_release(body.decode("utf-8", errors="replace"))

    def download(self, release: LatestRelease, folder: Path) -> Path:
        """The installer of ``release`` saved in ``folder``; a file of the wrong size is never written."""
        try:
            data = self.fetch(release.installer_url)
        except _NETWORK_ERRORS:
            raise UpdateError("Nie udało się pobrać instalatora; spróbuj ponownie.") from None
        if len(data) != release.size:
            raise UpdateError("Pobrany instalator jest uszkodzony; spróbuj ponownie.")
        path = folder / installer_name(release.version)
        path.write_bytes(data)
        return path

    def install(self, installer: Path) -> None:
        self.launch([str(installer), *INSTALLER_ARGS])
