"""Release Home Stock in two steps, around the release PR (from KAPITA's):

    .venv/Scripts/python.exe scripts/release.py prepare 0.2.0   # on the release branch, before the PR
    .venv/Scripts/python.exe scripts/release.py publish         # on main, once the PR is merged

`prepare` sets `__version__` and turns the changelog's "Nieopublikowane" into "<version> — <today>". `publish` builds
the installer from main (scripts/build_installer.ps1), pushes the tag `v<version>` and creates the GitHub Release
"Home Stock <version>" with the installer and the version's changelog section; `notes` prints that text.
"""

import argparse
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from home_stock.domain.changelog import UNRELEASED, ChangelogError, is_newer, parse_changelog

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "src" / "home_stock" / "__init__.py"
CHANGELOG = ROOT / "src" / "home_stock" / "ui" / "changelog.md"
_VERSION_LINE = re.compile(r'^__version__ = "(?P<version>[^"]+)"$', re.MULTILINE)
_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def current_version(init_text: str) -> str:
    if (match := _VERSION_LINE.search(init_text)) is None:
        raise ValueError("no __version__ line")
    return match["version"]


def bump_version(init_text: str, version: str) -> str:
    """The version file with ``version``, which must be newer than the one it holds."""
    if not _SEMVER.match(version):
        raise ValueError(f"{version} is not X.Y.Z")
    if not is_newer(version, current_version(init_text)):
        raise ValueError(f"{version} is not newer than {current_version(init_text)}")
    return _VERSION_LINE.sub(f'__version__ = "{version}"', init_text, count=1)


def release_changelog(text: str, version: str, day: date) -> str:
    """The changelog with its "Nieopublikowane" section numbered and dated; it must hold an entry."""
    if not parse_changelog(text).unreleased:
        raise ChangelogError(f"Sekcja „{UNRELEASED}” jest pusta albo jej brak: nie ma czego wydać.")
    # Matched as the parser reads a heading, trailing spaces and all
    heading = re.compile(rf"^## {UNRELEASED}[ \t]*$", re.MULTILINE)
    released = heading.sub(f"## {version} — {day.isoformat()}", text, count=1)
    parse_changelog(released)  # still well-formed, newest first
    return released


def release_notes(text: str, version: str) -> str:
    """The GitHub Release's text: how to install, then the version's changelog section."""
    release = parse_changelog(text).release(version)
    if release is None:
        raise ChangelogError(f"Historia zmian nie ma sekcji wersji {version}.")
    lines = [
        f"**Home Stock** {version} dla Windows.",
        "",
        "## Instalacja",
        "",
        f"Pobierz `{installer_name(version)}` i uruchom. Instalator instaluje Home Stock albo aktualizuje "
        "zainstalowaną wersję, a Twoje dane w `%LOCALAPPDATA%\\Home Stock` zostają.",
        "",
        "## Zmiany",
    ]
    if release.summary:
        lines += ["", release.summary]
    for group in release.groups:
        lines += ["", f"### {group.title}", *(f"- {entry}" for entry in group.entries)]
    return "\n".join(lines) + "\n"


def installer_name(version: str) -> str:
    return f"Home-Stock-{version}-setup.exe"


def _run(*command: str) -> str:
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
    if done.returncode != 0:
        sys.exit(f"{' '.join(command)} failed:\n{done.stdout}{done.stderr}")
    return done.stdout.strip()


def prepare(version: str) -> None:
    # Both checked before either is written, so a refusal leaves the release branch as it was
    init_text = bump_version(VERSION_FILE.read_text(encoding="utf-8"), version)
    changelog = release_changelog(CHANGELOG.read_text(encoding="utf-8"), version, date.today())
    VERSION_FILE.write_text(init_text, encoding="utf-8")
    CHANGELOG.write_text(changelog, encoding="utf-8")
    print(f"Version {version}: commit, open the release PR and merge it, then run `release.py publish` on main.")


def publish() -> None:
    if _run("git", "branch", "--show-current") != "main":
        sys.exit("Publish from main, after the release PR is merged.")
    if _run("git", "status", "--porcelain", "--untracked-files=no"):
        sys.exit("The working tree has uncommitted changes.")
    version = current_version(VERSION_FILE.read_text(encoding="utf-8"))
    tag = f"v{version}"
    _run("git", "fetch", "origin", "main", "--tags")
    if _run("git", "rev-parse", "HEAD") != _run("git", "rev-parse", "origin/main"):
        sys.exit("main differs from origin/main: pull or push first.")
    if _run("git", "tag", "--list", tag):
        sys.exit(f"The tag {tag} exists already.")
    notes = release_notes(CHANGELOG.read_text(encoding="utf-8"), version)

    print(f"Building {installer_name(version)} (several minutes)...", flush=True)
    _run("powershell", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "build_installer.ps1"))
    installer = ROOT / "dist" / installer_name(version)
    if not installer.exists():
        sys.exit(f"{installer} was not built.")

    _run("git", "tag", tag)
    _run("git", "push", "origin", tag)
    with tempfile.TemporaryDirectory() as folder:
        notes_file = Path(folder) / "notes.md"
        notes_file.write_text(notes, encoding="utf-8")
        _run(
            "gh",
            "release",
            "create",
            tag,
            str(installer),
            "--title",
            f"Home Stock {version}",
            "--notes-file",
            str(notes_file),
        )
    assets = _run("gh", "release", "view", tag, "--json", "assets", "-q", ".assets[].name")
    if installer.name not in assets.splitlines():
        sys.exit(f"The Release {tag} has no {installer.name}.")
    print(_run("gh", "release", "view", tag, "--json", "url", "-q", ".url"))


def main(argv: list[str] | None = None) -> None:
    # The changelog is Polish; a cp1250 console cannot print all of it
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare", help="set the version and date the changelog section").add_argument("version")
    commands.add_parser("publish", help="build the installer, push the tag, create the GitHub Release")
    notes = commands.add_parser("notes", help="print the GitHub Release text of a version")
    notes.add_argument("version", nargs="?")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            prepare(args.version)
        elif args.command == "publish":
            publish()
        else:
            text = CHANGELOG.read_text(encoding="utf-8")
            version = args.version or current_version(VERSION_FILE.read_text(encoding="utf-8"))
            print(release_notes(text, version), end="")
    except ValueError as error:  # ChangelogError among them
        sys.exit(str(error))


if __name__ == "__main__":
    main()
