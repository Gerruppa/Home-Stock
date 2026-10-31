# Coding standards

Judgement calls for review; what tooling checks (ruff, mypy, `tests/test_architecture.py`, `tests/test_database.py`) is not repeated here. CLAUDE.md holds the rules every change follows.

## Where a rule lives

- A rule that needs only the fields of one thing (a blank name, a negative number) lives in a frozen draft in `domain/` (`ProductDraft`, `BatchDraft`) and raises `ValueError` with the Polish message. Persistence functions take the draft.
- A rule that needs the database (a name already taken, a Category a Product still uses, a Batch removed meanwhile) lives in `persistence/` and raises `StockError` or a subclass with the Polish message.
- The UI parses text with `domain/formatting.py` parsers, builds the draft, calls persistence, and shows any `ValueError` or `StockError` as it is.

Known exception: `persistence/catalog.py` checks Category and Unit fields itself (blank name, negative days) instead of through drafts.

## Tests

- A test reads the shipped `ui/changelog.md` only for what every release keeps: its released sections. A test of the Nieopublikowane section builds its own changelog text, since `release.py prepare` renames that section.
