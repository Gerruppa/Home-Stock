"""The changelog: the version in the header opens every released version, and the first start of a new version
opens "Co nowego" with only that version (from KAPITA's). The text and the choice of what to announce are in
``sources/changelog.py``."""

from collections.abc import Iterable

from nicegui import ui
from sqlalchemy import Engine

from home_stock.domain.changelog import TITLE, ChangelogError, Release
from home_stock.domain.formatting import format_date
from home_stock.sources.changelog import load_changelog, release_to_announce
from home_stock.ui.dialog_keys import wire_dialog_keys


def open_changelog(overlay: ui.element, title: str, releases: Iterable[Release]) -> None:
    """A scrolling dialog of ``releases``, newest first."""
    with overlay, ui.dialog() as dialog, ui.card().classes("w-[40rem] max-w-full").mark("changelog") as card:
        ui.label(title).classes("hs-dialog-title")
        with ui.scroll_area().classes("w-full h-[60vh]"):
            for release in releases:
                ui.label(f"{release.version} — {format_date(release.released)}").classes("text-base text-bold pt-2")
                if release.summary:
                    ui.markdown(release.summary).classes("text-sm")
                for group in release.groups:
                    ui.label(group.title).classes("text-sm text-weight-medium pt-1")
                    ui.markdown("\n".join(f"- {entry}" for entry in group.entries)).classes("text-sm")
        with ui.row().classes("w-full justify-end"):
            ui.button("Zamknij", on_click=dialog.close).props("flat")
    wire_dialog_keys(dialog, card)
    dialog.on("hide", dialog.delete)
    dialog.open()


def version_label(overlay: ui.element, version: str) -> None:
    """The running version; clicking it opens the history of changes."""

    def open_history() -> None:
        try:
            releases = load_changelog().releases
        except ChangelogError as error:
            ui.notify(f"Nie można odczytać historii zmian: {error}", type="negative")
            return
        open_changelog(overlay, TITLE, releases)

    label = ui.label(f"wersja {version}").classes("text-caption cursor-pointer opacity-70")
    label.mark("app-version").tooltip(TITLE)
    label.on("click", open_history)


def announce_new_version(overlay: ui.element, engine: Engine, version: str) -> None:
    """Open "Co nowego" on the first start of ``version`` after an older one (see ``release_to_announce``)."""
    release = release_to_announce(engine, version)
    if release is not None:
        open_changelog(overlay, "Co nowego", [release])
