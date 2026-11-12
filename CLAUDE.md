# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Home Stock (version in `home_stock.__version__`) tracks household stock by hand and reminds the user what is running low or about to expire; modelled on the sibling app KAPITA (`D:\PythonProject\FinancialApp`), a read-only reference: run git and edits in this repo only. The agreed spec is `docs/spec.md`, the glossary `GLOSSARY.md`, key decisions `docs/adr/`.

Work is tracked in GitHub Issues on Gerruppa/Home-Stock (label `ready-for-agent`; each ticket names the tickets that block it). Take the lowest open ticket whose blockers are closed. `docs/superpowers/plans/2026-10-27-home-stock-v1.md` is superseded by the tickets; read it only for intended names and test cases. Each ticket goes on a branch `feat/<n>-<slug>` and a PR with `Closes #<n>`; merge with `gh pr merge <n> --merge --delete-branch` only when the user says so. Diff and review a branch against `origin/main` after `git fetch`: a worktree's local `main` never moves.

## Layout

`src/home_stock/` in layers, as in KAPITA:
- `domain/`: pure-Python rules (Product, Batch, Running Low, Expiry Status, Polish formatting).
- `persistence/`: SQLite through SQLAlchemy, Alembic migrations.
- `sources/`: `demo_data.py`, the made-up stock for `--demo`; importers go here too.
- `mobile/`: the app, for Android, in Flet (ADR-0004). `shell.py` builds the bottom navigation bar and the undo snackbar, and each tab gets a `Context` from `mobile/context.py`. `src/android_main.py` starts it.

Rules no config enforces:
- `domain/` never imports Flet, SQLAlchemy or Alembic (`tests/test_architecture.py` checks).
- The schema changes only through a new migration in `persistence/migrations/versions/`; `tests/test_database.py` fails when models and migrations drift. The database lives in the user's app-data folder (`HOME_STOCK_DATA_DIR` overrides it), never in the repo.
- UI text is Polish; code, DB names and docs English. Errors for the user carry a Polish message; which layer raises which is in `CODING_STANDARDS.md`.
- A change made through the UI calls `ctx.changed()` (redraws every tab, withdraws the undo snackbar) and then, if it can be undone, `ctx.undo(message, action)`.
- A dialog or form opens over the tabs with `ctx.show_full_screen(...)` and closes with `ctx.close_full_screen()`, so Android's Back closes it.

## Testing the UI

The test seams are fixed, no need to agree them per ticket: `persistence/` functions (`tests/test_<module>.py`) and each tab as `tests/test_mobile_<tab>_ui.py`, in plain Python, without a page, a phone or Flutter:
- Flet controls are dataclasses. `tests/mobile_ui.py` walks their tree, so `find(root, key)` (failing unless exactly one control has the key) and `absent(root, key)` use the `key=` given to a control. `texts(root)` returns what the user reads, in reading order and without hidden controls, and `tap(control)` (or `tap(snackbar, "on_action")`) calls the handler a tap would.
- Nothing in `mobile/` touches the page or calls a control's own `update()`, which fails off the page. The shell is handed how to show a snackbar and how to send changes to the screen, and `mobile_ui.Screen` stands in for both.
- All five tabs sit in the shell at once, and keys share one namespace across them: give a tab's keys their own shape (Zakupy's `list-chip-<id>`, Ustawienia's `category-row-<id>`).

## Releasing

The changelog `src/home_stock/sources/changelog.md` (Polish) collects, under `## Nieopublikowane`, one sentence per change the user sees, without issue numbers. A release takes two steps of `scripts/release.py`:
- `.venv/Scripts/python.exe scripts/release.py prepare <X.Y.Z>` on a branch `release/<X.Y.Z>`: sets `__version__` and renames Nieopublikowane to `<X.Y.Z> — <today>`; it refuses a version that is not X.Y.Z or not newer, and an empty Nieopublikowane. Commit, open the PR, merge when the user says so.
- `.venv/Scripts/python.exe scripts/release.py publish` on an up-to-date, clean main: builds the APK signed with the upload key (`flet build apk`; several minutes, the first build about half an hour), pushes the tag `v<X.Y.Z>` and creates the GitHub Release "Home Stock <X.Y.Z>" with `Home-Stock-<X.Y.Z>.apk`. Ask first if the user is busy at the computer. `scripts/release.py notes [<X.Y.Z>]` prints the Release text without publishing.
  - The APK is signed with the keystore `%USERPROFILE%\.android\home-stock-upload.jks` (alias `upload`, #111), its password in the user's environment variable `HOME_STOCK_KEYSTORE_PASSWORD`; without both, `publish` stops before building anything. Never print, log or commit the password, and never replace the keystore: an APK signed with another key does not install over the app.
  - The APK's version is `__version__` and its build number X·10000 + Y·100 + Z, which Android compares on update (ADR-0005).

## Environment

- Python 3.14 in a virtualenv at `.venv/`; install with `.venv/Scripts/python.exe -m pip install -e ".[dev]"`. A worktree's `.venv` is the main checkout's, whose editable install imports the main checkout's `src/`: pytest, mypy and the previews set `src` themselves; give anything else run from a worktree (`src/android_main.py`, a `python -c` probe) `PYTHONPATH=src`.
- Windows host. Use the venv interpreter directly, without relying on activation:
  - To look at a change, start the preview `home-stock-android` from `.claude/launch.json` (port 8770, scratch database in `.preview-data/android`), which shows the app in the browser, or `home-stock-android-demo` (port 8771, `android_main.py --demo`) on made-up Products in `%TEMP%/Home-Stock-demo`, fresh on every start. A preview runs the code as it was at its start: restart it after a change.
  - Build the APK from `android/` (Windows Developer Mode must be on): `PIP_PROGRESS_BAR=off PYTHONUTF8=1 ../.venv/Scripts/flet.exe build apk --yes --arch arm64-v8a --no-rich-output`.
    - Without `PIP_PROGRESS_BAR=off` the pip it runs hangs after downloading, and without `PYTHONUTF8=1` it crashes on a cp1250 console.
    - The first build downloads Flutter, a JDK and the Android SDK and takes about half an hour; run it in the background.
    - The APK lands in `android/build/apk/`.
  - Tests: `.venv/Scripts/python.exe -m pytest -n auto`. No CI: pre-commit runs them with ruff and mypy whenever a commit touches Python files.
    - One pytest at a time. Alone the suite takes about 25 s; two at once, each with `-n auto`, take minutes, and a commit's hook has been killed (exit 137). While working run single test files, and let the commit's hook run the whole suite.
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
