An AI helper you talk to inside World of Warcraft. Ask in the Gnomecaster panel in the
game; the answer appears there, and Gnomecaster can put places on your map and point the
arrow at them, follow quests, mark targets, create macros, put them on your bars, bind
keys, change a few settings and explain Lua errors from your addons.

## Install (Windows 10 or 11)

1. Download `Gnomecaster-Setup-1.2.0.exe` below and run it. It installs for your Windows
   account only and asks for no administrator rights.
2. The installer is not signed yet, so Windows shows "Windows protected your PC". Click
   "More info", then "Run anyway". `SHA256SUMS.txt` below lets you check the download.
3. Gnomecaster opens and walks you through three steps: it finds World of Warcraft, adds
   its addon, and connects an AI with "Sign in with OpenRouter". A new OpenRouter account
   needs a few dollars of credit first. A typical question costs about two hundredths of a
   cent; one that needs a web search about one cent.
4. Restart World of Warcraft completely, then type `/gc` in chat.

Keep Gnomecaster running while you play. Closing its window keeps it in the system tray;
"Quit Gnomecaster" in the tray icon's menu ends it.

## Updating from 1.1 or 1.0

1. Run `Gnomecaster-Setup-1.2.0.exe`. It closes Gnomecaster 1.1 by itself. Version 1.0
   cannot be closed by the installer: when it asks, right-click the Gnomecaster icon next
   to the clock, choose "Quit Gnomecaster", then click OK. Your settings and AI connection
   are kept.
2. In the Gnomecaster window, click "Update addon". This also removes reply slots 21 to 60,
   which 1.2 no longer uses.
3. Restart World of Warcraft completely (not just `/reload`): the addon has a new file.

## First test in the game

1. `/gc test`: the panel should say `Round trip OK` and name the AI model.
2. Ask anything and watch beside the panel: a small dark plate with a gold frame shows for
   a moment while the question is sent. If no answer comes, type `/gc beacon classic` and
   ask again; that brings back the bright square in the top-left corner of 1.1.
3. Try: `where is the Atal'Aman delve`, `take me to the Magisters' Terrace`, `mark the
   world boss on the map`, `take me to my quest`, `mark my target with skull`, and a macro
   with one of your own spells.
4. If something fails, open the answer in the Gnomecaster window and click "What
   Gnomecaster saw", and send that together with the panel's message and `/gc status`.

## What is new in 1.2

This release is the rework after the first test in the real game.

- Places: Gnomecaster finds dungeons and raids, delves, world bosses and world quests,
  flight points, map pins, zones and your quests by name in the game's own data, in your
  client's language, pins them on the map and points Blizzard's arrow at them (TomTom gets
  the waypoint too when it is installed).
- Memory: it remembers the last ten exchanges of each character, also across `/reload`,
  so "yes" to its question works. `/gc new` starts over.
- It acts instead of asking: changes still wait for your Apply in the panel.
- It uses what the AI knows about World of Warcraft and says when it is not sure; through
  OpenRouter it can search the web when it needs to, for example for where a vendor stands.
- The whole quest log, with zones, goes along with each question.
- A new panel in the game, built on Blizzard's own window frame.
- A new look for the app, a gnome tinker's workbench, and a new icon.
- "What Gnomecaster saw" under each answer in the app: what the game sent, the AI's raw
  reply and what happened. Transcripts are kept for 14 days (Settings, Open the
  transcripts folder); they never contain your API key.
- 20 reply slots instead of 60 in the AddOns list.

## Known limits

- The new plate, the new panel and the place search were tested on a simulated game and
  against real AI models, not yet in the real game. `/gc beacon classic` is the fallback
  for the plate.
- The AddOns list shows the 20 reply slots under Gnomecaster; the game cannot hide them.
  After at most 17 questions the panel asks you to reload the interface (sooner when the
  game reads replies on a timer).
- One question at a time, and nothing works in combat, by design.
