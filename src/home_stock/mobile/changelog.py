"""The changelog: the version at the bottom of Ustawienia opens every released version, and the first start of a new
version opens "Co nowego" with only that version. The text and the choice of what to announce are in
``sources/changelog.py``."""

from collections.abc import Iterable

import flet as ft
from sqlalchemy import Engine

from home_stock.domain.changelog import TITLE, ChangelogError, Release
from home_stock.domain.formatting import format_date
from home_stock.mobile.context import Context
from home_stock.sources.changelog import load_changelog, release_to_announce


def open_changelog(ctx: Context, title: str, releases: Iterable[Release]) -> None:
    """``releases`` as a full-screen view, newest first."""
    rows: list[ft.Control] = []
    for release in releases:
        rows.append(
            ft.Text(
                f"{release.version} — {format_date(release.released)}",
                weight=ft.FontWeight.BOLD,
                size=16,
                key=f"release-{release.version}",
            )
        )
        if release.summary:
            rows.append(ft.Markdown(release.summary))
        for group in release.groups:
            rows.append(ft.Text(group.title, weight=ft.FontWeight.W_500, color=ft.Colors.PRIMARY))
            rows.append(ft.Markdown("\n".join(f"- {entry}" for entry in group.entries)))
    ctx.show_full_screen(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.IconButton(
                            ft.Icons.CLOSE,
                            tooltip="Zamknij",
                            on_click=lambda _: ctx.close_full_screen(),
                            key="changelog-close",
                        ),
                        ft.Text(title, size=20, expand=True),
                    ]
                ),
                ft.ListView(rows, spacing=8, padding=ft.Padding.symmetric(horizontal=16, vertical=8), expand=True),
            ],
            expand=True,
            key="changelog",
        )
    )


def version_button(ctx: Context, version: str) -> ft.Control:
    """The running version; tapping it opens the history of changes."""

    def open_history(_: object) -> None:
        try:
            releases = load_changelog().releases
        except ChangelogError as error:
            ctx.say(f"Nie można odczytać historii zmian: {error}")
            return
        open_changelog(ctx, TITLE, releases)

    return ft.TextButton(f"wersja {version}", tooltip=TITLE, on_click=open_history, key="app-version")


def announce_new_version(ctx: Context, engine: Engine, version: str) -> None:
    """Open "Co nowego" on the first start of ``version`` after an older one (see ``release_to_announce``)."""
    release = release_to_announce(engine, version)
    if release is not None:
        open_changelog(ctx, "Co nowego", [release])
