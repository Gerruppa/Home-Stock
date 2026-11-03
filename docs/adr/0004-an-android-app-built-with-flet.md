# An Android app built with Flet, the data on the phone

Home Stock moves from a Windows app (NiceGUI in a pywebview window) to an Android app, because the cupboards are checked with a phone in hand, not at the desk. The app is built with Flet, which packs Python into an APK, so `domain/`, `persistence/` (SQLite through SQLAlchemy and Alembic) and `sources/` stay as they are and only the UI is rewritten, as `mobile/` beside `ui/`. A prototype proved the stack on a real phone on 2026-11-03: the APK starts, migrates its database and runs the Produkty tab. A rewrite in Kotlin, Flutter or as a web app would have meant writing the tested rules again. A hosted web app would have needed a server and a login, and NiceGUI on the computer, reached from the phone, only works while the computer is on.

## Consequences

- The phone is the only device: the database lives in Flet's app-private folder (`FLET_APP_STORAGE_DATA`), with a Backup before migrations as on Windows. There is no sync and no server, and the Windows data is not transferred: a new phone starts empty or from the Starter Catalog.
- Android only, installed by hand from an APK (no Play Store, no iOS). Updates install over the app only when every APK is signed with the same key, which the user keeps outside the repo.
- `android/pyproject.toml` builds the APK from the repo's `src/`, without `ui/` and with only the dependencies the phone needs. SQLAlchemy stays at 2.0.50, the newest with an Android wheel. The app ships `.py` files, not `.pyc`, so Alembic finds its migrations.
- The Windows app stays until the Android app has every feature (#99), then it is removed, and with it ADR-0003's Windows installer. Releases then ship the APK.
- Reminders stay in the app (ADR-0002): no Android notifications.
