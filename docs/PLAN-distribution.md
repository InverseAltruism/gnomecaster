# Distribution plan: from scripts to an app players install, 2026-10-16

Goal: a World of Warcraft player who has never opened a terminal installs Gnomecaster with
one download, sees no frightening warnings, and is answering questions in the game within
a few minutes. Everything below was researched on 2026-10-16; sources are in the research
notes linked at the end of each section.

## What the player experiences

1. Clicks "Get it from Microsoft" on the Gnomecaster page (or downloads the installer).
2. The app opens on a three-step setup: finds World of Warcraft by itself, installs the
   addon with one click, then "Sign in with OpenRouter" opens the browser; after approving,
   the app has its key. No copying keys, no terminal, no Python.
3. A short "You're set" screen says how to open Gnomecaster in the game (`/gc` or a key).
4. Afterwards the app sits in the tray, starts with Windows if wanted, shows what was asked
   in the game and what came back, and says plainly what to do when something breaks.

The interface is built (`desktop/ui/`) and was clicked through in light and dark against
the real backend (see `docs/PROGRESS.md`). The brand mark (a gnome mage's curled hat with an arcane spark) is one SVG,
`assets/brand/gnomecaster-icon.svg`, from which `tools/make_icons.py` renders the Windows
`.ico`, the macOS `.icns`, every PNG size, the installer's wizard images and the in-game
icon. Windows comes first: nearly every player is on Windows, so macOS waits.

## Trust: signing and warnings

Findings that decide this (Microsoft and CA/Browser Forum documents, read 2026-10-16):

- No certificate removes the SmartScreen warning on day one any more. Since 2024 EV and OV
  certificates are treated alike; reputation builds over weeks of clean installs.
- The Microsoft Store is the only route with no warning from the first download: Store
  packages are signed by Microsoft. Developer accounts for individuals are free (photo ID
  and selfie); the individual account type is meant for apps that are not part of a
  business. A website can offer the Store's web installer ("Get it from Microsoft" badge).
- For a direct download, an EU individual can buy Certum's individual cloud certificate
  (about EUR 117 a year before VAT, signing by hand) or SSL.com's individual certificate
  with eSigner (about USD 309 a year, signing in CI). Microsoft's Artifact Signing is open
  to individuals only in the US and Canada; EU organisations can use it.
- Windows 11 Smart App Control checks every executable and DLL, so every file shipped must
  be signed, not only the installer.

Decision: the Microsoft Store (MSIX) is the main channel. A signed direct installer follows
when a certificate exists. Until then, testers get an unsigned build from GitHub Releases
with a note that explains the warning.

Needs the owner (cannot be automated): the Microsoft Partner Center developer account and
first submission; later, buying a code signing certificate and passing its identity check.

## Connecting the AI without copying keys

OpenRouter's documented OAuth PKCE flow: the app opens
`https://openrouter.ai/auth?callback_url=http://localhost:<port>/callback&code_challenge=...&code_challenge_method=S256&state=...&key_label=Gnomecaster`,
listens on `127.0.0.1` on a free port, checks `state`, and exchanges the code at
`POST https://openrouter.ai/api/v1/auth/keys` for an ordinary API key. No client
registration exists or is needed; players without an account can sign up inside the flow
and set their own spending limit on the consent page. `GET /api/v1/key` shows usage and
the remaining limit, which the dashboard displays.

Known limit: with a localhost callback the consent page names the app `localhost:<port>`.
A small hosted page that forwards the code to the app would show the real name; that is a
later step.

## Stack (decided 2026-10-16)

- Python with pywebview 6.2.1 (the window is Microsoft Edge WebView2) and pystray 0.19.5 (the
  tray icon). The companion's tested code runs unchanged inside the app; the window is
  plain HTML, CSS and JavaScript (`desktop/ui/`), so a later move to Tauri would keep it.
  Prior art: WeakAuras Companion (Electron) shows the model of a desktop helper that writes
  into the AddOns folder; it reads the game's install path from the same registry value.
- PyInstaller 6.22.3, one folder, bootloader compiled on the build machine, no UPX.
- Inno Setup 6.7.3 installer, per user (no administrator prompt), modern wizard that
  follows the Windows light or dark setting, branded images, WebView2 installed when
  missing (Microsoft's documented registry check and bootstrapper).
- GitHub Actions on `windows-2025` builds, tests and smoke-tests it (`packaging/README.md`).
- Every dependency exact, hash-locked, and at least 14 days old (`packaging/lock.py`).

Rejected: Electron (it ships its own browser in every download, where WebView2 comes with
Windows 11); a single-file PyInstaller build (it unpacks itself to a temp folder at
each start: slower, and often reported to trigger antivirus false positives).

## Phases

1. Brand assets and the app interface. Done.
2. App shell: window, tray, single instance, autostart, the backend calls the interface
   uses (`desktop/ui/api.js` is the contract), OAuth sign-in, game detection from the
   registry and the usual folders. Done; tested on Linux with fakes for the Windows parts.
3. Build: done for the direct installer. Version 1.0.0 was built, tested and published by
   the workflow on 2026-10-16 (release `v1.0.0`, unsigned). Next: the MSIX package for the
   Store, which also needs "Start with Windows" through the package's startup task.
4. Store submission (owner), then a signed direct installer (owner buys the certificate).
5. macOS: later, needs an Apple Developer membership.

## What the owner has to do

- Microsoft Partner Center: create the free individual developer account (photo ID and
  selfie), reserve the name Gnomecaster, and pass the package identity it assigns into the
  MSIX build.
- Later, for a direct download without the warning building up slowly: buy an individual
  code signing certificate (Certum, about EUR 117 a year before VAT, signing by hand; or
  SSL.com with eSigner, about USD 309 a year, signing in CI) and pass its identity check.
