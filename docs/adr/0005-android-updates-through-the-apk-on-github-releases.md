# Android updates through the APK on GitHub Releases

ADR-0003's way of updating carries over to the Android app (ADR-0004), with the APK in place of the installer. Each GitHub Release "Home Stock X.Y.Z" also carries `Home-Stock-<X.Y.Z>.apk`, built by `scripts/release.py publish` and signed with the upload key from #111. A few seconds after start the app asks the GitHub API for the latest Release. When it is newer and carries the APK, "Dostępna wersja X" shows beside the version at the bottom of Ustawienia, and a snackbar says so. Tapping it hands the APK's address to the phone, whose browser downloads it, and opening the download starts Android's installer, which the user confirms. Flet has no way to hand a file to Android's installer itself (that needs a FileProvider and the REQUEST_INSTALL_PACKAGES permission in the Flutter shell), and the browser does the same work with the phone's own download and install prompts.

## Consequences

- ADR-0003 still holds for the Windows app until it is removed (#113). Its checks carry over: only a Release tagged `v<X.Y.Z>` whose asset `Home-Stock-<X.Y.Z>.apk` downloads from this repository's own Releases is offered, the check stays silent when it fails, and the demo never checks.
- Android installs the APK over the app, keeping its data, only when it is signed with the same key and its build number (versionCode) is higher. The build number is X·10000 + Y·100 + Z, so Y and Z stay under 100.
- `publish` stops before building anything unless the keystore `%USERPROFILE%\.android\home-stock-upload.jks` exists and `HOME_STOCK_KEYSTORE_PASSWORD` holds its password. Without them Flet would sign with a throwaway key, and that APK would not install over the app. Losing the key ends updates over the installed app.
- The app does not check the download's size itself: the phone's browser downloads the file, and Android's installer refuses a broken APK.
- Android may first ask to allow installs from the browser ("unknown apps"). That is the phone's own setting, granted once.
