# Coding standards

Judgement calls for review; what tooling checks (ruff, mypy, `tests/test_architecture.py`, `tests/test_database.py`, `tests/test_glossary.py`) is not repeated here. CLAUDE.md holds the rules every change follows.

## Names

- `tests/test_glossary.py` rejects a name using a GLOSSARY.md _Avoid_ word, except the everyday ones in its `EVERYDAY` (count, entry, order…). Those are for review: one that names the glossary's concept (an `entry` that is a Batch, a `count` that is a Quantity) takes the glossary's term.

## Where a rule lives

- A rule that needs only the fields of one thing (a blank name, a negative number) lives in a frozen draft in `domain/` (`ProductDraft`, `BatchDraft`) and raises `ValueError` with the Polish message. Persistence functions take the draft.
- A rule that needs the database (a name already taken, a Category a Product still uses, a Batch removed meanwhile) lives in `persistence/` and raises `StockError` or a subclass with the Polish message.
- The UI parses text with `domain/formatting.py` parsers, builds the draft, calls persistence, and shows any `ValueError` or `StockError` as it is.

Known exception: `persistence/catalog.py` checks Category and Unit fields itself (blank name, negative days) instead of through drafts.

## The two apps

- `mobile/` rewrites each tab of `ui/` and may repeat its layout code (a tab's sections, its lines, its grouping by Category): the two never import each other, and `ui/` goes with #113. A rule both tabs need (what is Running Low, how a line is worded) belongs in `domain/` or `persistence/`, shared by both.

## Tests

- A test reads the shipped `ui/changelog.md` only for what every release keeps: its released sections. A test of the Nieopublikowane section builds its own changelog text, since `release.py prepare` renames that section.
