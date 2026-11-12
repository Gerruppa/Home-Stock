"""The changelog shipped with the app, and which version's section a start announces; both apps show it.

The text lives in ``changelog.md`` beside this module (format in ``domain/changelog.py``), kept by hand: a PR adds an
entry to its "Nieopublikowane" section, which the app never shows.
"""

from importlib.resources import files

from sqlalchemy import Engine

from home_stock.domain.changelog import Changelog, ChangelogError, Release, is_newer, parse_changelog
from home_stock.persistence.settings import LAST_ANNOUNCED_VERSION, load_setting, save_setting


def load_changelog() -> Changelog:
    """The changelog shipped with the app."""
    return parse_changelog(files(__package__).joinpath("changelog.md").read_text(encoding="utf-8"))


def release_to_announce(engine: Engine, version: str) -> Release | None:
    """On the first start of ``version`` after an older one, its section for "Co nowego", and record it; a fresh
    database (a first install, every ``--demo``) only records it, and going back to an older version records nothing,
    so the newer one is not announced twice."""
    last = load_setting(engine, LAST_ANNOUNCED_VERSION)
    if last is not None and not is_newer(version, last):
        return None
    save_setting(engine, LAST_ANNOUNCED_VERSION, version)
    if last is None:
        return None
    try:
        return load_changelog().release(version)
    except ChangelogError:
        # A broken file never stops the start; tapping the version says what is wrong
        return None
