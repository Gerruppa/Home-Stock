"""The changelog: the version in the header opens every released version, and the first start of a new version
opens "Co nowego" with only that version (from KAPITA's).

The text lives in ``changelog.md`` beside this module (format in ``domain/changelog.py``), kept by hand: a PR adds an
entry to its "Nieopublikowane" section, which the window never shows.
"""

from collections.abc import Iterable
from importlib.resources import files

from nicegui import ui
from sqlalchemy import Engine

from home_stock.domain.changelog import TITLE, Changelog, ChangelogError, Release, is_newer, parse_changelog
from home_stock.domain.formatting import format_date
from home_stock.persistence.settings import LAST_ANNOUNCED_VERSION, load_setting, save_setting


def load_changelog() -> Changelog:
    """The changelog shipped with the app."""
    return parse_changelog(files(__package__).joinpath("changelog.md").read_text(encoding="utf-8"))


def open_changelog(overlay: ui.element, title: str, releases: Iterable[Release]) -> None:
    """A scrolling dialog of ``releases``, newest first."""
    with overlay, ui.dialog() as dialog, ui.card().classes("w-[40rem] max-w-full").mark("changelog"):
        ui.label(title).classes("text-h6")
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
    """On the first start of ``version`` after an older one, open "Co nowego" with its section, and record it; a fresh
    database (a first install, every ``--demo``) only records it, and going back to an older version records nothing,
    so the newer one is not announced twice."""
    last = load_setting(engine, LAST_ANNOUNCED_VERSION)
    if last is not None and not is_newer(version, last):
        return
    save_setting(engine, LAST_ANNOUNCED_VERSION, version)
    if last is None:
        return
    try:
        release = load_changelog().release(version)
    except ChangelogError:
        # A broken file never stops the start; clicking the version says what is wrong
        return
    if release is not None:
        open_changelog(overlay, "Co nowego", [release])
