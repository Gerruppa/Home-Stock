"""The changelog: its Markdown read into Releases, and versions compared numerically."""

from datetime import date

import pytest

from home_stock.domain.changelog import ChangelogError, is_newer, parse_changelog

SAMPLE = """\
# Historia zmian

## Nieopublikowane

### Poprawki
- Poprawiono kolor karty Produktu.

## 1.1.0 — 2026-11-02

### Nowe funkcje
- Lista zakupów do wydruku.
- Kopia zapasowa.

### Zmiany
- Zakładka Start pokazuje najpierw przeterminowane.

## 1.0.0 — 2026-10-19

Pierwsze wydanie.

### Nowe funkcje
- Produkty i Partie.
"""


def test_reads_released_versions_newest_first_with_their_groups() -> None:
    changelog = parse_changelog(SAMPLE)

    newest, first = changelog.releases
    assert (newest.version, newest.released, newest.summary) == ("1.1.0", date(2026, 11, 2), "")
    assert [(group.title, group.entries) for group in newest.groups] == [
        ("Nowe funkcje", ("Lista zakupów do wydruku.", "Kopia zapasowa.")),
        ("Zmiany", ("Zakładka Start pokazuje najpierw przeterminowane.",)),
    ]
    assert (first.version, first.summary) == ("1.0.0", "Pierwsze wydanie.")


def test_keeps_the_unreleased_entries_apart() -> None:
    changelog = parse_changelog(SAMPLE)

    assert [(group.title, group.entries) for group in changelog.unreleased] == [
        ("Poprawki", ("Poprawiono kolor karty Produktu.",))
    ]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("## 1.0.0 — 2026-10-19\n\n### Nowe funkcje\n- A.\n", "Historia zmian"),
        ("# Historia zmian\n\n## 1.0 z października\n\n### Poprawki\n- A.\n", "1.0 z października"),
        ("# Historia zmian\n\n## 1.0.0 — 2026-10-19\n\n### Inne\n- A.\n", "Inne"),
        ("# Historia zmian\n\n## 1.0.0 — 2026-10-19\n\n### Poprawki\n- A.\n\n### Nowe funkcje\n- B.\n", "kolejności"),
        ("# Historia zmian\n\n## 1.0.0 — 2026-10-19\n\n### Poprawki\n- A.\n\n### Poprawki\n- B.\n", "kolejności"),
        ("# Historia zmian\n\n## 1.0.0 — 2026-10-19\n\n### Poprawki\n\n", "Poprawki"),
        ("# Historia zmian\n\n## 1.0.0 — 2026-10-19\n\n", "1.0.0"),
        ("# Historia zmian\n\n## 1.0.0 — 2026-10-19\n\n- Wpis bez grupy.\n", "Wpis bez grupy."),
        (
            "# Historia zmian\n\n## 1.0.0 — 2026-10-19\n\n### Poprawki\n- A.\n\n"
            "## 1.1.0 — 2026-11-02\n\n### Poprawki\n- B.\n",
            "1.1.0",
        ),
        (
            "# Historia zmian\n\n## 1.0.0 — 2026-11-02\n\n### Poprawki\n- B.\n\n"
            "## 1.0.0 — 2026-10-19\n\n### Poprawki\n- A.\n",
            "1.0.0",
        ),
        ("# Historia zmian\n\n## 1.0.0 — 2026-10-19\n\n### Poprawki\nTekst bez punktu.\n", "Tekst bez punktu."),
        ("# Historia zmian\n\n## 1.0.0 — 2026-13-01\n\n### Poprawki\n- A.\n", "błędną datę"),
        ("# Historia zmian\n\nWstęp.\n\n## 1.0.0 — 2026-10-19\n\n### Poprawki\n- A.\n", "Wstęp."),
        ("# Historia zmian\n\n## 1.0.0 — 2026-10-19\n\n### Poprawki\n- A.\n\n## Nieopublikowane\n", "na samej górze"),
        ("# Historia zmian\n\n## Nieopublikowane\n\n## Nieopublikowane\n", "na samej górze"),
    ],
)
def test_refuses_a_broken_changelog_naming_the_entry(text: str, message: str) -> None:
    with pytest.raises(ChangelogError, match=message):
        parse_changelog(text)


@pytest.mark.parametrize(
    ("version", "than", "newer"),
    [
        ("1.10.0", "1.9.0", True),
        ("1.9.0", "1.10.0", False),
        ("2.0.0", "1.99.99", True),
        ("1.0.0", "1.0.0", False),
    ],
)
def test_compares_versions_numerically(version: str, than: str, newer: bool) -> None:
    assert is_newer(version, than) is newer
