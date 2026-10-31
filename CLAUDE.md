# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Home Stock (version `0.2.0`, `home_stock.__version__`) tracks household stock by hand and reminds the user what is running low or about to expire; modelled on the sibling app KAPITA (`D:\PythonProject\FinancialApp`), a read-only reference: run git and edits in this repo only. The agreed spec is `docs/spec.md`, the glossary `GLOSSARY.md`, key decisions `docs/adr/`.

Work is tracked in GitHub Issues on Gerruppa/Home-Stock (label `ready-for-agent`; each ticket names the tickets that block it). Take the lowest open ticket whose blockers are closed. `docs/superpowers/plans/2026-10-27-home-stock-v1.md` is superseded by the tickets; read it only for intended names and test cases. Each ticket goes on a branch `feat/<n>-<slug>` and a PR with `Closes #<n>`; merge with `gh pr merge <n> --merge --delete-branch` only when the user says so.

## Layout

`src/home_stock/` in four layers, as in KAPITA: `domain/` (pure-Python rules: Product, Batch, Running Low, Expiry Status, Polish formatting), `persistence/` (SQLite through SQLAlchemy, Alembic migrations), `sources/` (`demo_data.py`, the made-up stock for `--demo`; importers go here too) and `ui/` (NiceGUI: `shell.py` builds the tabs and the undo bar, each tab gets a `Context` from `ui/context.py`).

Rules no config enforces:
- `domain/` never imports NiceGUI, SQLAlchemy, Alembic or pywebview (`tests/test_architecture.py` checks).
- The schema changes only through a new migration in `persistence/migrations/versions/`; `tests/test_database.py` fails when models and migrations drift. The database lives in the user's app-data folder (`HOME_STOCK_DATA_DIR` overrides it), never in the repo.
- UI text is Polish; code, DB names and docs English. Errors for the user carry a Polish message; which layer raises which is in `CODING_STANDARDS.md`.
- A change made through the UI calls `ctx.changed()` (redraws every tab, withdraws the undo bar) and then, if it can be undone, `ctx.undo(message, action)`.
- Open a `ui.dialog` inside `ctx.overlay`, which outlives every tab's redraw.

## Testing the UI

The test seams are fixed, no need to agree them per ticket: `persistence/` functions (`tests/test_<module>.py`) and each tab through `user_simulation` (`tests/test_<tab>_ui.py`).

UI tests use NiceGUI's `user_simulation` and find elements by `.mark(...)` markers; `tests/conftest.py` makes `should_see`/`should_not_see` wait up to 5 s. Gotchas:
- All four tabs sit on the page at once: scope a text check with a marker or `user.scope(...)`, since another tab may show the same text (Ustawienia shows every Category name). Markers share one namespace across tabs, so give a tab's markers its own shape (Produkty's `category-<id>`, Ustawienia's `category-row-<id>`).
- `user.find(...).elements` comes back in no page order: compare positions through `element.parent_slot.children`.
- `should_see` reads text, labels and values, not props: show a form error as a `ui.label`, not as the `error-message` prop.
- `user.find(...)` raises when nothing matches: check that an element is absent with `should_not_see(marker=...)`.

## Releasing

The changelog `src/home_stock/ui/changelog.md` (Polish) collects, under `## Nieopublikowane`, one sentence per change the user sees, without issue numbers. A release takes two steps of `scripts/release.py`:
- `.venv/Scripts/python.exe scripts/release.py prepare <X.Y.Z>` on a branch `release/<X.Y.Z>`: sets `__version__` and renames Nieopublikowane to `<X.Y.Z> — <today>`; it refuses a version that is not X.Y.Z or not newer, and an empty Nieopublikowane. Commit, open the PR, merge when the user says so.
- `.venv/Scripts/python.exe scripts/release.py publish` on an up-to-date, clean main: builds the installer (several minutes, needs Inno Setup; ask first if the user is busy at the computer), pushes the tag `v<X.Y.Z>` and creates the GitHub Release "Home Stock <X.Y.Z>" with `Home-Stock-<X.Y.Z>-setup.exe`. `scripts/release.py notes [<X.Y.Z>]` prints the Release text without publishing.

Try an installer in the scratchpad: `Home-Stock-<X.Y.Z>-setup.exe /DIR="<scratchpad>\app"` with `HOME_STOCK_DATA_DIR` set to a scratch folder. The user's own install in `%LOCALAPPDATA%\Programs\Home Stock`, and its running `HomeStock` processes, are theirs.

## Environment

- Python 3.14 in a virtualenv at `.venv/`; install with `.venv/Scripts/python.exe -m pip install -e ".[dev]"`.
- Windows host. Use the venv interpreter directly, without relying on activation:
  - Run the app: `.venv/Scripts/python.exe main.py` (`--browser` serves on http://127.0.0.1:8080; `--demo` serves there too, on a fresh database of made-up Products in `%TEMP%/Home-Stock-demo`, recreated on every start). To look at a change, start the preview `home-stock` from `.claude/launch.json` (port 8765, scratch database in `.preview-data/`), or `home-stock-demo` (port 8766) for a page already full of data.
  - Tests: `.venv/Scripts/python.exe -m pytest -n auto`. No CI: pre-commit runs them with ruff and mypy whenever a commit touches Python files.
  - Type check: `.venv/Scripts/python.exe -m mypy` (strict)
  - Lint and format: `.venv/Scripts/python.exe -m ruff check .` and `.venv/Scripts/python.exe -m ruff format .`
- Change files with Edit and Write, issue bodies too; a Python or `sed` script through Bash breaks on quotes.

## Agent skills

### Issue tracker

Issues live in GitHub Issues on Gerruppa/Home-Stock, worked through the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
