# Updates through GitHub Releases, with a Backup before migrations

How the phone gets the update is ADR-0005. Written for the first, desktop version, which downloaded an installer; revised when that version was removed (#113).

Home Stock ships on GitHub Releases (`scripts/release.py publish`), and the installed app offers each new one: a few seconds after start it asks the GitHub API for the latest Release and, when it is newer, shows "Dostępna wersja X" beside the version. GitHub Releases cost nothing, already hold the code, and need no server of our own; a manual "download from the page" alone would leave most installs on old versions. Because an update can run migrations on the user's only copy of their stock, every start takes a Backup of the database before migrations touch it, so a bad migration can be undone by hand.

## Consequences

- Only a Release tagged `v<X.Y.Z>` whose file downloads from this repository's own Releases is accepted.
- The check is silent when it fails (offline, rate-limited, a broken answer): the next start asks again. The demo never checks.
- An update never touches the data folder; going back to an older version means restoring a Backup by hand.
