# Home Stock on Android: Flet prototype

Throwaway prototype: the Produkty tab rewritten in [Flet](https://flet.dev) on the app's own `domain/`,
`persistence/` and `sources/`, built into an APK. Tested on a phone on 2026-11-03: it starts, migrates its SQLite
database and the Produkty tab works (sample data, −1, Cofnij, search).

## Run and build

In this folder, with its own venv (Flet must not go into the app's `.venv`):

```bash
py -3.14 -m venv .venv
.venv/Scripts/python.exe -m pip install "flet[all]" "sqlalchemy==2.0.50" alembic platformdirs
.venv/Scripts/python.exe sync_core.py
PIP_PROGRESS_BAR=off PYTHONUTF8=1 .venv/Scripts/flet.exe build apk --yes --arch arm64-v8a --no-rich-output
```

`sync_core.py` copies the NiceGUI-free layers into `src/home_stock` (git-ignored); run it after each change to them.
The APK lands in `build/apk/`. The preview `flet-prototype` in `.claude/launch.json` serves the prototype on port 8770.

## What the build taught

- Windows Developer Mode must be on; the first build downloads Flutter, a JDK and the Android SDK (several GB, the
  first Gradle run about 25 minutes, later builds a few).
- `PIP_PROGRESS_BAR=off`: without it the pip that `flet build` runs for the Android packages hangs after downloading.
- `PYTHONUTF8=1`: without it the build crashes printing the Android SDK download progress to a cp1250 console.
- SQLAlchemy 2.0.50 is the newest with an Android wheel on pypi.flet.dev; the app asks for 2.1 but runs on 2.0.50.
- `[tool.flet.compile] app = false`: the default `.pyc` compilation removes the `.py` files Alembic finds the
  migrations by.
- The database goes in `FLET_APP_STORAGE_DATA`, passed on as `HOME_STOCK_DATA_DIR`.
