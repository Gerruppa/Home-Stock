"""scripts/release.py: the version bump, the changelog's dated section, the Release text and publish's checks."""

import importlib.util
import re
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest

from home_stock.domain.changelog import ChangelogError, parse_changelog


def _load() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / "release.py"
    spec = importlib.util.spec_from_file_location("release", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release = _load()

INIT = '"""Home Stock."""\n\n__version__ = "0.1.0"\n'
CHANGELOG = """# Historia zmian

## Nieopublikowane

### Nowe funkcje
- Nowa rzecz.

### Poprawki
- Poprawiona rzecz.

## 0.1.0 — 2026-10-28

Pierwsza wersja.

### Nowe funkcje
- Starsza rzecz.
"""


def test_the_version_bump_changes_only_the_version_line() -> None:
    assert release.bump_version(INIT, "0.2.0") == '"""Home Stock."""\n\n__version__ = "0.2.0"\n'


@pytest.mark.parametrize("version", ["0.1.0", "0.0.9", "0.2", "v0.2.0"])
def test_a_version_not_newer_or_not_x_y_z_is_refused(version: str) -> None:
    with pytest.raises(ValueError, match=re.escape(version)):
        release.bump_version(INIT, version)


def test_the_unreleased_section_gets_the_version_and_the_day() -> None:
    released = release.release_changelog(CHANGELOG, "0.2.0", date(2026, 11, 2))

    assert released == (
        "# Historia zmian\n"
        "\n"
        "## 0.2.0 — 2026-11-02\n"
        "\n"
        "### Nowe funkcje\n"
        "- Nowa rzecz.\n"
        "\n"
        "### Poprawki\n"
        "- Poprawiona rzecz.\n"
        "\n"
        "## 0.1.0 — 2026-10-28\n"
        "\n"
        "Pierwsza wersja.\n"
        "\n"
        "### Nowe funkcje\n"
        "- Starsza rzecz.\n"
    )
    assert [r.version for r in parse_changelog(released).releases] == ["0.2.0", "0.1.0"]


@pytest.mark.parametrize(
    "text",
    [
        "# Historia zmian\n\n## 0.1.0 — 2026-10-28\n\n### Nowe funkcje\n- Starsza rzecz.\n",
        "# Historia zmian\n\n## Nieopublikowane\n\n## 0.1.0 — 2026-10-28\n\n### Nowe funkcje\n- Starsza rzecz.\n",
    ],
    ids=["missing", "empty"],
)
def test_a_release_with_nothing_unreleased_is_refused(text: str) -> None:
    with pytest.raises(ChangelogError, match="Nieopublikowane"):
        release.release_changelog(text, "0.2.0", date(2026, 11, 2))


def test_an_unreleased_heading_with_trailing_spaces_is_dated_too() -> None:
    text = CHANGELOG.replace("## Nieopublikowane\n", "## Nieopublikowane  \n")

    released = release.release_changelog(text, "0.2.0", date(2026, 11, 2))

    assert released == release.release_changelog(CHANGELOG, "0.2.0", date(2026, 11, 2))


@pytest.fixture
def files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """The version file and the changelog, as scratch copies holding INIT and CHANGELOG."""
    version_file, changelog = tmp_path / "__init__.py", tmp_path / "changelog.md"
    version_file.write_text(INIT, encoding="utf-8")
    changelog.write_text(CHANGELOG, encoding="utf-8")
    monkeypatch.setattr(release, "VERSION_FILE", version_file)
    monkeypatch.setattr(release, "CHANGELOG", changelog)
    return version_file, changelog


def test_prepare_bumps_the_version_and_dates_the_unreleased_section(files: tuple[Path, Path]) -> None:
    version_file, changelog = files

    release.main(["prepare", "0.2.0"])

    assert release.current_version(version_file.read_text(encoding="utf-8")) == "0.2.0"
    released = parse_changelog(changelog.read_text(encoding="utf-8"))
    assert released.unreleased == ()
    assert released.releases[0].version == "0.2.0"
    assert released.releases[0].released == date.today()


@pytest.mark.parametrize("version", ["0.1.0", "0.2"])
def test_a_refused_prepare_changes_neither_file(files: tuple[Path, Path], version: str) -> None:
    with pytest.raises(SystemExit, match=re.escape(version)):
        release.main(["prepare", version])

    assert [path.read_text(encoding="utf-8") for path in files] == [INIT, CHANGELOG]


def test_prepare_with_nothing_unreleased_leaves_the_version_alone(files: tuple[Path, Path]) -> None:
    version_file, changelog = files
    changelog.write_text(
        "# Historia zmian\n\n## 0.1.0 — 2026-10-28\n\n### Nowe funkcje\n- Starsza rzecz.\n", encoding="utf-8"
    )

    with pytest.raises(SystemExit, match="Nieopublikowane"):
        release.main(["prepare", "0.2.0"])

    assert version_file.read_text(encoding="utf-8") == INIT


def test_notes_say_how_to_install_then_list_the_version_s_changes(capsys: pytest.CaptureFixture[str]) -> None:
    release.main(["notes", "0.1.0"])

    section = release.CHANGELOG.read_text(encoding="utf-8").split("## 0.1.0 — 2026-10-28\n\n")[1]
    assert capsys.readouterr().out == (
        "**Home Stock** 0.1.0 dla Windows.\n"
        "\n"
        "## Instalacja\n"
        "\n"
        "Pobierz `Home-Stock-0.1.0-setup.exe` i uruchom. Instalator instaluje Home Stock albo aktualizuje "
        "zainstalowaną wersję, a Twoje dane w `%LOCALAPPDATA%\\Home Stock` zostają.\n"
        "\n"
        "## Zmiany\n"
        "\n"
        f"{section}"
    )


def test_notes_for_a_version_missing_from_the_changelog_are_refused() -> None:
    with pytest.raises(SystemExit, match=r"9\.9\.9"):
        release.main(["notes", "9.9.9"])


@pytest.mark.parametrize(
    ("branch", "status", "refusal"),
    [
        ("feat/32-release-script", "", "main"),
        ("main", " M src/home_stock/__init__.py", "uncommitted"),
    ],
    ids=["off main", "dirty tree"],
)
def test_publish_refuses_before_touching_anything(
    monkeypatch: pytest.MonkeyPatch, branch: str, status: str, refusal: str
) -> None:
    answers = {
        ("git", "branch", "--show-current"): branch,
        ("git", "status", "--porcelain", "--untracked-files=no"): status,
    }

    def run(*command: str) -> str:
        assert command in answers, f"publish ran {command} after it should have stopped"
        return answers[command]

    monkeypatch.setattr(release, "_run", run)

    with pytest.raises(SystemExit, match=refusal):
        release.main(["publish"])
