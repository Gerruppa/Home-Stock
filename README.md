# Home Stock

A desktop app for Windows (NiceGUI in a native window, SQLite).

## Install for development

Requires Python 3.14.

```
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m pre_commit install
```

## Run

```
.venv\Scripts\python.exe main.py            # native window
.venv\Scripts\python.exe main.py --browser  # http://127.0.0.1:8080
```

## Checks

```
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format .
```
