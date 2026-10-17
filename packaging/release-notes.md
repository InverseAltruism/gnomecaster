An AI helper you talk to inside World of Warcraft. Ask in the Gnomecaster panel in the
game; the answer appears there, and Gnomecaster can set waypoints and the quest arrow,
mark targets, create macros, put them on your bars, bind keys, change a few settings and
explain Lua errors from your addons.

## Install (Windows 10 or 11)

1. Download `Gnomecaster-Setup-1.1.0.exe` below and run it. It installs for your Windows
   account only and asks for no administrator rights.
2. The installer is not signed yet, so Windows shows "Windows protected your PC". Click
   "More info", then "Run anyway". `SHA256SUMS.txt` below lets you check the download.
3. Gnomecaster opens and walks you through three steps: it finds World of Warcraft, adds
   its addon, and connects an AI with "Sign in with OpenRouter". A new OpenRouter account
   needs a few dollars of credit first; a typical question costs less than a tenth of a cent.
4. Restart World of Warcraft completely, then type `/gc` in chat.

Keep Gnomecaster running while you play. Closing its window keeps it in the system tray;
"Quit Gnomecaster" in the tray icon's menu ends it.

## Updating from 1.0

1. Run `Gnomecaster-Setup-1.1.0.exe`. Version 1.0 cannot be closed by the installer, so
   when it asks, right-click the Gnomecaster icon next to the clock, choose
   "Quit Gnomecaster", then click OK. Your settings and AI connection are kept.
2. In the Gnomecaster window, click "Update addon", then restart World of Warcraft.

From 1.1 on, the installer closes Gnomecaster by itself.

## First test in the game

1. `/gc test`: the panel should say `Round trip OK` and name the AI model. The
   Gnomecaster window lists the test too.
2. Try: `take me to my quest` (follow a quest first), `mark my target with skull`,
   `mouseover Rejuvenation macro on slot 5, bound to Shift-E` (use one of your own spells),
   `what was that error?`.
3. If something fails, send the panel's message, the output of `/gc status`, and the log
   file from the app (Settings, "Open the log folder", `gnomecaster.log`).

## What is new in 1.1

- In the game: answers type out in the panel under a gold "Gnomecaster:" label, the panel
  uses Gnomecaster's colours and icon, and a glowing spark shows while it waits.
- The app's setup: smoother step changes, every step fits the window, a sign-in you can
  cancel, a clearer API key form with a "Get a key" link, and an out-of-credit OpenRouter
  account named as such with an "Add credit" button.
- The window opens centred on your screen; closing it says where its icon went.
- The installer closes a running Gnomecaster by itself, and only after you click Install.
  Uninstalling asks whether to remove the addon and your settings as well.
- Retail is listed first when several game versions are installed.
- Ollama answers about 2 seconds sooner per question on Windows.

## Known limits

- Its parts were tested on a simulated game and against real AI models, the build is
  tested on Windows by an automatic install, launch and uninstall, and the installer and
  app were tried by hand on Windows 11; it has not yet been tried in the real game.
- The coloured grid flashes in the top-left corner for a moment while a question is sent.
- One question at a time; follow-up questions do not remember the earlier ones yet.
- Nothing works in combat, by design.
