An AI helper you talk to inside World of Warcraft. Ask in the Gnomecaster panel in the
game; the answer appears there, and Gnomecaster can set waypoints and the quest arrow,
mark targets, create macros, put them on your bars, bind keys, change a few settings and
explain Lua errors from your addons.

## Install (Windows 10 or 11)

1. Download `Gnomecaster-Setup-1.0.0.exe` below and run it. It installs for your Windows
   account only and asks for no administrator rights.
2. The installer is not signed yet, so Windows shows "Windows protected your PC". Click
   "More info", then "Run anyway". `SHA256SUMS.txt` below lets you check the download.
3. Gnomecaster opens and walks you through three steps: it finds World of Warcraft, adds
   its addon, and connects an AI with "Sign in with OpenRouter". A new OpenRouter account
   needs a few dollars of credit first; a typical question costs less than a tenth of a cent.
4. Restart World of Warcraft completely, then type `/gc` in chat.

Keep Gnomecaster running while you play. Closing its window keeps it in the system tray;
"Quit Gnomecaster" in the tray icon's menu ends it.

## First test in the game

1. `/gc test`: the panel should say `Round trip OK` and name the AI model. The
   Gnomecaster window lists the test too.
2. Try: `take me to my quest` (follow a quest first), `mark my target with skull`,
   `mouseover Rejuvenation macro on slot 5, bound to Shift-E` (use one of your own spells),
   `what was that error?`.
3. If something fails, send the panel's message, the output of `/gc status`, and the log
   file from the app (Settings, "Open the log folder", `gnomecaster.log`).

## What is new in 1.0

- The Windows app and its installer: no Python, no terminal.
- Sign in with OpenRouter in the browser instead of copying an API key; an API key or a
  local Ollama model still work under "Use an API key instead".
- The app shows each question from the game and its answer, starts with Windows if you
  want, and explains what to do when the AI connection fails.

## Known limits

- This is the first release that runs on a player's PC. Its parts were tested on a
  simulated game and against real AI models, and the build is tested on Windows by an
  automatic install, launch and uninstall; it has not yet been tried in the real game.
- The coloured grid flashes in the top-left corner for a moment while a question is sent.
- One question at a time; follow-up questions do not remember the earlier ones yet.
- Nothing works in combat, by design.
