# Updates through GitHub Releases, with a Backup before migrations

Home Stock ships as a Windows installer attached to a GitHub Release (`scripts/release.py publish`), and the installed app offers each new one: a few seconds after start it asks the GitHub API for the latest Release and, when it is newer, shows "Dostępna wersja X" beside the version; one click downloads the installer, starts it silently and quits, and the installer upgrades in place and starts the new version. GitHub Releases cost nothing, already hold the code, and need no server of our own; a manual "download from the page" alone would leave most installs on old versions. Because an update can run migrations on the user's only copy of their stock, every start takes a Backup of the database before migrations touch it, so a bad migration can be undone by hand.

## Consequences

- Only a Release tagged `v<X.Y.Z>` with an asset `Home-Stock-<X.Y.Z>-setup.exe` downloaded from this repository's own Releases is accepted; the download must have the size GitHub reports.
- The check is silent when it fails (offline, rate-limited, a broken answer): the next start asks again. The demo never checks.
- Only the installed (frozen) app installs; a source checkout only links to the Releases page.
- The installer is unsigned, so Windows SmartScreen may warn on the first manual install; the silent upgrade does not show the wizard.
- The data folder is never touched by the installer or the uninstaller; going back to an older version means restoring a Backup by hand.
