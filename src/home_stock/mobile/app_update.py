"""The update notice beside the version in Ustawienia: a few seconds after start the app asks GitHub for the latest
Release and, when it is newer and carries the APK, shows "Dostępna wersja X". Tapping it hands the APK's address to
the phone, which downloads it; opening the download starts Android's installer, which puts it over the app and keeps
the data (every APK is signed with the same key)."""

import flet as ft

from home_stock.domain.app_update import UpdateError, newer_release
from home_stock.mobile.context import Context
from home_stock.sources.app_update import UpdateSource

# Seconds after start, so the check never slows the first screen
CHECK_DELAY = 3.0


class UpdateNotice:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        # Hidden until a newer Release turns up
        self.control = ft.TextButton(
            icon=ft.Icons.SYSTEM_UPDATE,
            visible=False,
            style=ft.ButtonStyle(color=ft.Colors.TERTIARY),
            key="update-available",
        )

    def check(self, updates: UpdateSource, version: str) -> None:
        """Ask GitHub for the latest Release (blocking: the app runs it on a thread of its own) and show it when it is
        newer than ``version``; a failed check stays silent, and the next start asks again."""
        try:
            latest = newer_release(updates.latest(), version)
        except UpdateError:
            return
        if latest is None:
            return
        self.control.content = ft.Text(f"Dostępna wersja {latest.version}")
        self.control.on_click = lambda _: self._download(latest.url)
        self.control.visible = True
        self.ctx.say(f"Dostępna nowa wersja Home Stock: {latest.version}")
        self.ctx.update()

    def _download(self, url: str) -> None:
        self.ctx.open_url(url)
        self.ctx.say("Pobieranie nowej wersji; otwórz pobrany plik, aby ją zainstalować. Twoje dane zostają.")
