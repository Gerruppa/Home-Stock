"""The update notice beside the version in the header (from KAPITA's): a few seconds after start Home Stock asks GitHub
for the latest Release and, when it is newer, shows "Dostępna wersja X"; clicking it offers the installation, which
downloads the installer, starts it silently and quits so it can replace the files (the data folder stays)."""

import tempfile
import webbrowser
from pathlib import Path

from nicegui import app, run, ui

from home_stock.domain.app_update import RELEASES_PAGE, LatestRelease, UpdateError, newer_release
from home_stock.sources.app_update import UpdateSource

# Seconds after start, so the check never slows the first paint
CHECK_DELAY = 3.0


def update_notice(overlay: ui.element, updates: UpdateSource | None, version: str) -> None:
    """Build the (hidden) notice and schedule the check; nothing happens without ``updates`` (the demo, the tests)."""
    if updates is None:
        return
    button = ui.button().props("flat dense no-caps color=amber").classes("text-caption").mark("update-available")
    button.set_visibility(False)

    async def check() -> None:
        try:
            found = await run.io_bound(updates.latest)
        except UpdateError:
            # Offline or a broken answer must never nag; the next start asks again
            return
        # io_bound gives None when the app is shutting down meanwhile
        latest = newer_release(found, version) if found is not None else None
        if latest is None:
            return
        button.set_text(f"Dostępna wersja {latest.version}")
        button.on_click(lambda: _open_dialog(overlay, updates, latest))
        button.set_visibility(True)
        ui.notify(f"Dostępna nowa wersja Home Stock: {latest.version}", type="info")

    ui.timer(CHECK_DELAY, check, once=True)


def _open_dialog(overlay: ui.element, updates: UpdateSource, latest: LatestRelease) -> None:
    with overlay, ui.dialog() as dialog, ui.card().classes("w-[28rem] max-w-full").mark("update-dialog"):
        ui.label(f"Dostępna wersja {latest.version}").classes("text-h6")
        if updates.can_install:
            ui.label(
                "Home Stock pobierze instalator, zamknie się, zaktualizuje i uruchomi ponownie. Twoje dane zostają."
            )
        else:
            ui.label("Tej kopii programu nie zaktualizuje instalator; pobierz nową wersję ze strony wydań.")
        status = ui.label().classes("text-sm").mark("update-status")
        with ui.row().classes("w-full justify-end"):
            ui.button("Później", on_click=dialog.close).props("flat").mark("update-later")
            ui.button("Strona wydań", on_click=lambda: webbrowser.open(RELEASES_PAGE)).props("outline").mark(
                "update-page"
            )
            if updates.can_install:
                install = ui.button("Zainstaluj teraz").mark("update-install")
                install.on_click(lambda: _install(updates, latest, install, status))
    dialog.on("hide", dialog.delete)
    dialog.open()


async def _install(updates: UpdateSource, latest: LatestRelease, button: ui.button, status: ui.label) -> None:
    """Download the installer off the event loop, start it and quit so it can replace the files; a failure says why
    and lets the user try again."""
    button.disable()
    status.set_text("Pobieranie instalatora…")
    try:
        folder = Path(tempfile.mkdtemp(prefix="home-stock-update-"))
        installer = await run.io_bound(updates.download, latest, folder)
        if installer is None:  # the app is shutting down
            return
        updates.install(installer)
    except (UpdateError, OSError) as error:
        status.set_text(str(error) if isinstance(error, UpdateError) else "Nie udało się uruchomić instalatora.")
        button.enable()
        return
    status.set_text("Uruchamianie instalatora…")
    app.shutdown()
