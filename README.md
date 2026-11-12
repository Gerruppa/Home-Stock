# Home Stock

Tracks household stock by hand and reminds you what is running low or about to expire. An Android app built with
Flet, with the data on the phone (SQLite, ADR-0004).

## Install on the phone

Download `Home-Stock-<version>.apk` from the latest GitHub Release on the phone and open it. The first time, Android
asks to allow installing apps from outside the Play Store. A newer APK installs over the app and keeps your data; the
app itself says in Ustawienia when a newer version is out (ADR-0005).

## Release

The changelog `src/home_stock/sources/changelog.md` gathers the coming changes under `## Nieopublikowane`. A release is two
steps around a release PR:

```
.venv\Scripts\python.exe scripts\release.py prepare 0.2.0   # on a release/0.2.0 branch: version and dated changelog
.venv\Scripts\python.exe scripts\release.py publish         # on main once the PR is merged
```

`prepare` sets `__version__` and turns `## Nieopublikowane` into `## 0.2.0 — <today>`; it refuses a version that is not
X.Y.Z or not newer, and an empty Nieopublikowane section. `publish` needs a clean main equal to `origin/main`, an
authenticated `gh` and the upload key (the keystore `%USERPROFILE%\.android\home-stock-upload.jks`, its password in
`HOME_STOCK_KEYSTORE_PASSWORD`): it builds the signed APK, pushes the tag `v0.2.0` and creates the GitHub Release
"Home Stock 0.2.0" with `Home-Stock-0.2.0.apk`, its notes a short install paragraph and that version's changelog
section. `scripts\release.py notes 0.2.0` prints those notes.

## Install for development

Requires Python 3.14.

```
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m pre_commit install
```

## Run in a browser

To look at the app on http://localhost:8770, on a scratch database in `.preview-data\android`:

```
$env:FLET_FORCE_WEB_SERVER = "true"; $env:FLET_SERVER_PORT = "8770"; $env:FLET_APP_STORAGE_DATA = ".preview-data\android"
.venv\Scripts\python.exe src\android_main.py
```

Add `--demo` for made-up Products in `%TEMP%\Home-Stock-demo` instead, created afresh on every start, with something in
every section of Start and on the Shopping List.

On the phone the database lives in the app's private folder. Every start takes a Backup of it into `backups\` beside it
before migrations run, keeping the newest 30 (the demo takes none).

## Build the APK

Build from `android\`, whose `pyproject.toml` packs `src\` with only the dependencies the phone needs. Windows Developer
Mode must be on. The first build downloads Flutter, a JDK and the Android SDK, and takes about half an hour.

```
cd android
$env:PIP_PROGRESS_BAR = "off"; $env:PYTHONUTF8 = "1"
..\.venv\Scripts\flet.exe build apk --yes --arch arm64-v8a --no-rich-output
```

Without `PIP_PROGRESS_BAR=off` the pip it runs hangs after downloading, and without `PYTHONUTF8=1` it crashes on a
cp1250 console. The APK lands in `android\build\apk\`; it is signed with a throwaway key, so for a phone that has the
released app use `scripts\release.py publish`.

## Checks

```
.venv\Scripts\python.exe -m pytest -n auto
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format .
```
