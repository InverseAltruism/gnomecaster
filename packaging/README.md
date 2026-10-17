# Building the Windows app

The player gets one file, `Gnomecaster-Setup-<version>.exe`. It installs the app for the
current Windows account (no administrator prompt), adds Start menu and optional desktop
shortcuts, and gets Microsoft Edge WebView2 first if the PC lacks it. The app is the
companion, its window and a tray icon in one program; see `docs/PLAN-distribution.md` for
why it is built this way.

A running Gnomecaster is closed only once the player has chosen to go ahead: when Setup
starts copying files (`PrepareToInstall`) and after the uninstaller's "Are you sure?"
(`usAppMutexCheck`). Both run `Gnomecaster.exe --quit`, which returns once the process has
let go of the `Gnomecaster.Running` mutex. If the app still runs (1.0.0 has no `--quit`),
the player is asked to quit it from its tray icon. Inno's own `AppMutex` check is not used:
it runs before the Welcome page. An update skips the shortcut page and says it keeps the
settings. Uninstalling asks whether to remove the addon and the settings as well
(`--remove-everything`); a silent uninstall keeps them.

`.github/workflows/windows.yml` does everything below on GitHub's `windows-2025` runner for
each push to main and each pull request, and keeps the installer and the smoke test's
results as the run's artifacts. Pushing a tag `v<version>` (it must equal
`companion/gnomecaster/__init__.py`'s version) also runs the `release` job, the only job
with write access: it publishes the tested installer, `SHA256SUMS.txt` and
`packaging/release-notes.md` as the GitHub release.

## Steps

1. Python 3.13.16. pythonnet, which pywebview uses on Windows, needs 3.11 or newer.
2. Three installs, every file checked against the hashes in the `.txt` locks:
   - `requirements-backend.txt` from wheels: setuptools and hatchling, the build backends.
   - `requirements-build.txt` with `--no-binary=pyinstaller` and
     `PYINSTALLER_COMPILE_BOOTLOADER=1`: PyInstaller compiles its bootloader on the build
     machine. PyInstaller's guide gives the stock bootloader's wide use as a cause of
     antivirus false positives. `check_bootloader.py` fails the build if the installed
     `runw.exe` equals the one in PyInstaller's published wheel.
   - `requirements-app.txt`: pywebview, pythonnet, pystray, Pillow and their dependencies.
   The last two use `--no-build-isolation`: pip would otherwise fetch unpinned, unhashed
   build tools for source archives (PyInstaller, proxy-tools).
3. The unit tests, on Windows.
4. `python -m PyInstaller packaging/gnomecaster.spec`: one folder, `dist\Gnomecaster`, with
   `Gnomecaster.exe` (windowed, the brand icon, version details from
   `companion/gnomecaster/__init__.py`), the addon, the window's files and the tray icon.
   No UPX. pystray (LGPL-3.0) is kept as plain `.py` files so it can be replaced.
5. Smoke test: `Gnomecaster.exe --smoke-test <folder>` opens the real window, waits until
   the page has asked the backend for its state, writes `smoke.json` and a picture of the
   window, and quits.
6. Inno Setup 6.7.3, from its GitHub release, checked against its SHA-256, then
   `ISCC.exe /DAppVersion=<version> packaging\gnomecaster.iss`.
7. Like a player: a silent install, the smoke test on the installed app, a silent uninstall,
   and a check that the app is gone.

## Changing a dependency

Edit the pin in a `requirements-*.in` and run `python3 packaging/lock.py` (needs the
`packaging` library). It refuses releases younger than 14 days, a package pinned in two
files, and any dependency for Windows x64 and CPython 3.13 that no file pins.
`lock.py --check` fails when a `.txt` no longer matches.

## Images

`tools/make_icons.py` renders the `.ico`, the PNGs and the installer's wizard images (one per
screen scaling Inno Setup lists) from `assets/brand/gnomecaster-icon.svg` and
`assets/brand/installer-side.svg`. `--check` fails when a generated file is out of date.

## Not done yet

- Code signing. Every `.exe` and `.dll` needs a signature for Smart App Control and, over
  time, SmartScreen; this waits for a certificate (`docs/PLAN-distribution.md`).
- The Microsoft Store package (MSIX). It needs the owner's Partner Center identity, and
  "Start with Windows" must use the package's startup task there: Microsoft's MSIX
  documentation says a packaged app's writes under HKCU go to a private per-app copy, so
  the Run key entry the installer build uses would not reach Windows.
