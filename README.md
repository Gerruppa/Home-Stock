# Home Stock

Tracks household stock by hand and reminds you what is running low or about to expire. Today it is a desktop app for
Windows (NiceGUI in a native window, SQLite). It is moving to an Android app built with Flet, with the data on the
phone (ADR-0004). The Windows app stays until the Android app has every feature (#99).

## Install from the installer

Run `Home-Stock-<version>-setup.exe`. It installs for the current user only (no administrator rights) into
`%LOCALAPPDATA%\Programs\Home Stock`, adds Home Stock to the Start menu and to the desktop (untick it in the wizard to skip that). Installing a
newer version over it upgrades in place; uninstalling (Settings > Apps) leaves your data alone. Home Stock needs the
Microsoft Edge WebView2 runtime, which Windows 11 already has.

## Build the installer

Needs Inno Setup 6 (`winget install JRSoftware.InnoSetup`) and the `build` extra:

```
.venv\Scripts\python.exe -m pip install -e ".[dev,build]"
powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1
```

The installer lands in `dist\Home-Stock-<version>-setup.exe`; the version comes from `src/home_stock/__init__.py`. A
silent install (`/SILENT /CLOSEAPPLICATIONS /NORESTART`) closes a running Home Stock and starts the new one when done.
To change the icon, edit and run `.venv\Scripts\python.exe scripts\make_icons.py`.

## Release

The changelog `src/home_stock/ui/changelog.md` gathers the coming changes under `## Nieopublikowane`. A release is two
steps around a release PR:

```
.venv\Scripts\python.exe scripts\release.py prepare 0.2.0   # on a release/0.2.0 branch: version and dated changelog
.venv\Scripts\python.exe scripts\release.py publish         # on main once the PR is merged
```

`prepare` sets `__version__` and turns `## Nieopublikowane` into `## 0.2.0 — <today>`; it refuses a version that is not
X.Y.Z or not newer, and an empty Nieopublikowane section. `publish` needs a clean main equal to `origin/main` and an
authenticated `gh`: it builds the installer, pushes the tag `v0.2.0` and creates the GitHub Release "Home Stock 0.2.0"
with `Home-Stock-0.2.0-setup.exe`, its notes a short install paragraph and that version's changelog section.
`scripts\release.py notes 0.2.0` prints those notes.

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
.venv\Scripts\python.exe main.py --demo     # made-up data, http://127.0.0.1:8080
```

Your data lives in the app-data folder (`%LOCALAPPDATA%\Home Stock`; set `HOME_STOCK_DATA_DIR` to use another).
`--demo` never touches it: it serves a database of made-up Products from `%TEMP%\Home-Stock-demo`, created afresh on
every start, with something in every section of Start and on the Shopping List.

Every start takes a Backup of the database into `backups\` in the data folder before migrations run, keeping the newest
30 (the demo takes none). To restore one, close Home Stock and copy the chosen file over `home_stock.sqlite3`.

Without a console (the installed app, or `home-stock-gui`), the output goes to `home_stock.log` in the data folder,
overwritten at each start.

## The Android app

`src/home_stock/mobile/` rewrites the UI tab by tab in Flet. `domain/`, `persistence/` and `sources/` are shared with
the Windows app. Start, Produkty (with the Product card and form) and Zakupy (with Unpacking) work. Historia and
Ustawienia still show "Wkrótce".

To look at it in a browser on http://localhost:8770, on a scratch database in `.preview-data\android`:

```
$env:FLET_FORCE_WEB_SERVER = "true"; $env:FLET_SERVER_PORT = "8770"; $env:FLET_APP_STORAGE_DATA = ".preview-data\android"
.venv\Scripts\python.exe src\android_main.py
```

On the phone the database lives in the app's private folder, with a Backup before migrations as on Windows. Nothing
syncs with the Windows app, and nothing is copied over from it.

### Build the APK

Build from `android\`, whose `pyproject.toml` packs `src\` without the Windows app. Windows Developer Mode must be on.
The first build downloads Flutter, a JDK and the Android SDK, and takes about half an hour.

```
cd android
$env:PIP_PROGRESS_BAR = "off"; $env:PYTHONUTF8 = "1"
..\.venv\Scripts\flet.exe build apk --yes --arch arm64-v8a --no-rich-output
```

Without `PIP_PROGRESS_BAR=off` the pip it runs hangs after downloading, and without `PYTHONUTF8=1` it crashes on a
cp1250 console. The APK lands in `android\build\apk\`; install it on the phone by hand.

## Checks

```
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format .
```
