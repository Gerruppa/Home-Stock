# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Home Stock is a new app (version `0.1.0`, `home_stock.__version__`), modelled on the sibling app KAPITA (`D:\PythonProject\FinancialApp`). It tracks household stock by hand and reminds the user what is running low or about to expire. So far there is only the skeleton; the agreed spec is `docs/spec.md`, the glossary `GLOSSARY.md` and key decisions are in `docs/adr/`. The default branch is `main`; work goes on a feature branch and a PR.

## Layout

`src/home_stock/` in four layers, as in KAPITA: `domain/` (pure-Python calculations), `persistence/` (SQLite through SQLAlchemy), `sources/` (importers and services above persistence; add when needed) and `ui/` (NiceGUI).

Rules no config enforces:
- `domain/` never imports NiceGUI, SQLAlchemy, Alembic or pywebview (`tests/test_architecture.py` checks).
- The schema changes only through an Alembic migration. The database lives in the user's app-data folder (`platformdirs`), never in the repo.
- UI text is Polish; code, DB names and docs English. Errors for the user carry a Polish message.
- UI tests use NiceGUI's `user_simulation` and find elements by `.mark(...)` markers.

## Environment

- Python 3.14 in a virtualenv at `.venv/`; install with `.venv/Scripts/python.exe -m pip install -e ".[dev]"`.
- Windows host. Use the venv interpreter directly, without relying on activation:
  - Run the app: `.venv/Scripts/python.exe main.py` (`--browser` serves on http://127.0.0.1:8080).
  - Tests: `.venv/Scripts/python.exe -m pytest -n auto`
  - Type check: `.venv/Scripts/python.exe -m mypy` (strict)
  - Lint and format: `.venv/Scripts/python.exe -m ruff check .` and `.venv/Scripts/python.exe -m ruff format .`
- Review the uncommitted diff before the first commit, apply the fixes, then commit once.
