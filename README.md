# Gnomecaster (prototype)

An AI helper you talk to inside World of Warcraft. You type in a Gnomecaster panel; the
answer appears there, and Gnomecaster can also act: create and edit macros, put them on
your bars, bind keys, set waypoints and the quest arrow, mark targets, change a few
settings, and explain the Lua errors your addons throw.

## Install on Windows

1. Download `Gnomecaster-Setup-<version>.exe` from the repository's Releases page and run
   it. It installs for your Windows account only, so it asks for no administrator rights.
2. Gnomecaster opens and sets itself up in three steps: it finds World of Warcraft, adds
   its addon to the game, and connects an AI when you click "Sign in with OpenRouter"
   (a new OpenRouter account needs a few dollars of credit; a typical question costs about
   two hundredths of a cent, one that needs a web search about one cent).
3. Restart World of Warcraft, then type `/gc` in chat.

Keep Gnomecaster running while you play: closing its window keeps it in the system tray,
and it can start with Windows. Its window shows each question from the game and the answer.

To update, run the new `Gnomecaster-Setup-<version>.exe`; it closes Gnomecaster for you and
keeps your settings. Uninstall from Windows Settings, Apps; it asks whether to remove the
addon and your settings too.

Each release is built and tested on Windows by `.github/workflows/windows.yml` and published
with a `SHA256SUMS.txt`. Until the installer is signed or comes from the Microsoft Store,
Windows shows "Windows protected your PC" for it: click "More info", then "Run anyway".
`docs/PLAN-distribution.md` explains why and what removes the warning.

## How it works

It has two parts:

- **the addon**, which lives in the game: the panel, and the code that reads your game
  (class and spec, zone and position, quest log, where the game says your quest goes next,
  your target, recent Lua errors) and carries out the answer;
- **the Gnomecaster app** on your PC (the companion), which passes your question and that
  game information to an AI model and hands the answer back.

Addons cannot use the internet or write files while you play, so the two talk through the
disk: the addon draws your question as a coloured grid for two frames and takes a
screenshot; the companion reads the screenshot, asks the model, and writes the answer into
small "reply slot" addons that the game loads on demand.

```
 WoW (addon)                                       Companion (your PC)
 ───────────                                       ───────────────────
 you type in the Gnomecaster panel
 addon reads live game information
        │
        ▼
 draws it as a small framed plate beside     ──►  sees the screenshot, decodes the plate,
 the panel for 2 frames, takes a screenshot        deletes the screenshot after answering
                                                          │
                                                          ▼
                                                   asks the AI model
                                                          │
 loads the next "reply slot" addon            ◄──  writes the answer into the reply slots
        │                                          and sets a "ready" signal
        ▼
 shows the answer; waypoints and marks happen at once;
 macro, bar, key and setting changes wait for your
 click on Apply (or /gc auto on)
```

Nothing touches the game's memory, nothing presses keys for you, and nothing changes in
combat. The addon uses only normal addon functions; the companion only reads screenshot
files and writes files in the AddOns folder.

## Using it

Open the panel with `/gc` (or `/gnomecaster` if another addon owns `/gc`), or bind a key in
Esc > Options > Keybindings > AddOns > Gnomecaster. Type and press Enter. Up and Down bring
back earlier questions. Examples:

- `take me to my quest` (follow a quest first)
- `where is the Atal'Aman delve` or `mark the world boss on the map`: the addon looks the
  place up in the game's own data (dungeon and raid entrances, delves, world bosses and
  world quests, flight points, map pins, zones, your quest log), pins it on the map and
  points Blizzard's arrow at it; TomTom gets the waypoint too when it is installed
- `way 45.2 63.1`
- `mark my target with skull`
- `mouseover Rejuvenation macro on slot 5, bound to Shift-E` (use one of your spells)
- `what was that error?`
- `turn on auto loot`

Gnomecaster remembers the last ten exchanges (also across `/reload`, while the app runs, and
for 30 minutes after the last question), so you can answer its questions ("yes") or refer
back to them; `/gc new` starts over. Waypoints and marks happen
at once. Macros, bar placements, key bindings and settings show in a box at the bottom of
the panel and wait for Apply; `/gc auto on` applies them directly,
except a key binding that would replace an existing one, which always asks. Macros may only
use casting and targeting commands such as `/cast`, `/use` and `/target`; Gnomecaster never
creates macros with `/run` or `/script`. The panel shows `sending`, `waiting for the
companion` and `thinking` while a question is out.

Other commands: `/gc test` (round trip and AI connection check), `/gc status`, `/gc auto
on|off`, `/gc new` (new conversation), `/gc beacon dim|classic` (see Known limits), `/gc help`.

The app's window lists every question with its answer; "What Gnomecaster saw" under an
answer shows the game information that was sent, how the previous answer's actions went,
the model's raw reply and whether it searched the web. The same records are kept for 14
days as text files in the transcripts folder (Settings, Open the transcripts folder). They
hold your questions and game information, never your API key.

## Choosing a model

28 realistic requests, sent through the real companion and checked against the real addon
code: macros, the quest arrow, coordinates, marks, settings, error explanations, Classic,
safety cases such as "don't mark anything", a request for a `/run` macro and instructions
hidden inside a Lua error, and eight German requests taken from the first in-game test
(the world boss, the Atal'Aman delve, a route to the Magisters' Terrace, enemy nameplates
followed by "ja", auto loot, a Freezing Trap macro, a retry after a failed place lookup).
OpenRouter, 2026-10-17, with web search offered:

| Model | Correct | Answer time (median / slowest) | Question without search | Per web search |
|---|---|---|---|---|
| `openai/gpt-6-luna` (the default) | 28/28 | 2.6 s / 12.2 s | $0.00016 (0.00012 to 0.00086) | $0.0108 |
| `anthropic/claude-haiku-5.5` | 28/28 | 2.6 s / 8.1 s | $0.00074 (0.00059 to 0.00141) | $0.0118 |
| `google/gemini-3.8-flash` | 28/28 | 6.2 s / 17.6 s | $0.00301 (0.00203 to 0.01114) | $0.0165 |

Costs are what OpenRouter reported; question costs vary with its prompt caching. The models
searched on 2 to 4 of the 28 requests (where a world boss is up, an unknown fact, a spell
name). The default model's row is from the final code; the other two rows are from the same
day, before one line about search results was added to the prompt. In an earlier run the
default model scored 26/28; both misses were fixed in the companion and the scoring. `deepseek/deepseek-v4.1-flash` (20/20 on the older
20 requests, 2026-10-16) was not re-run. Free (`:free`) models are not recommended: in
testing they were rate-limited on most requests. The app offers these models under
Settings, Model. A local model through Ollama works with "Use an API key instead", Ollama,
if your PC can run one; web search is only offered through OpenRouter, and
`GNOMECASTER_WEB_SEARCH=0` (or `"web_search": false` in the settings file) turns it off.

## When something goes wrong

The panel in the game and the app's window both say what happened and what to do. The
most common messages:

| Message | What to do |
|---|---|
| `... rejected the API key` | In the app: Settings, Change account (or sign in again). |
| `out of credit` | Add credit at your provider; for OpenRouter the app has an Add credit button. Then Test connection. |
| `The model ... is not available` | Choose another model in the app's Settings. |
| `The model is busy right now (rate limited)` | Wait the time it names, or choose another model. |
| `The model took longer than 40 seconds` | Try again, or choose a faster model. |
| `The companion hasn't picked up your question yet` | Open the Gnomecaster app (check the tray). The question keeps waiting, so the answer can still arrive. |
| `No answer: no reply after 60 seconds` | In the app: Settings, Open the log folder; see also the first test below. |
| `Reply slots are almost used up` | Click Reload UI on the panel. |

## What leaves your PC

With each question the companion sends the AI provider your question and the game
information the addon reads: game version and language; your character's class, spec, race,
faction and level, and whether you are in combat; zone and position; quest titles and
objectives; your target's name, level, and whether it is hostile, dead or a player; and
recent Lua error messages. Nothing else from your PC or account is sent. Your API key stays
in the settings file (`%APPDATA%\Gnomecaster\config.json`, inside your Windows profile).
"Sign in with OpenRouter" creates that key in your OpenRouter account, labelled
Gnomecaster; you can see, limit or delete it there.

## Known limits

- One question at a time, about 2.4 KB of game information per question (the quest log is
  trimmed to fit).
- 20 reply slots per game session (each is a line under Gnomecaster in the AddOns list;
  the game has no way to hide them). With the ready signal each answer uses one; with
  timed checking an answer that takes 15 seconds uses four. The panel warns early and
  offers a Reload UI button.
- Each question shows a small dark plate with a gold frame beside the panel for a moment:
  that is how the question reaches the app. `/gc beacon classic` switches back to the
  original bright square in the top-left corner, the only style proven in the game so far.
  The dim plate needs the game to save screenshots as PNG (the addon sets this for each
  question) and fails at extreme gamma with very low brightness; colour-blind filters may
  break either style.
- The game exposes no positions of people such as vendors and trainers. For those the
  model may search the web and pin the coordinates a guide gives, and says they come from
  the web.
- Questions do not work while the interface is hidden (Alt-Z).
- Nothing works in combat, by design.

## Status: what is proven and what is not

Proven on this machine, with real code:

- The whole round trip, in a simulated game: the real addon code on a mocked WoW API, the
  real companion, and fake screenshots, including JPEG and rescaled ones, both plate styles
  under gamma and brightness changes, and place lookups on a mocked game world.
  `tests/run_all.sh` runs 14 Lua suites (296 checks) and 220 Python unit tests (two of them
  run only on Windows).
- The app's setup and dashboard, clicked through in a browser against the app's real
  backend with a fake OpenRouter and a fake game folder (sign-in, an account without
  credit, installing the addon, a question from the game, settings), in light and dark.
- The AI side, against real models on OpenRouter: 28 realistic requests, scored
  automatically (`tools/eval_models.py`). Results are in "Choosing a model" above.
- Every WoW function the addon calls is either in Blizzard's own API documentation for
  build 12.1.5 or used by Blizzard's own UI code (`tools/wow_api.py`), apart from four
  that are only called when present: two old macro and binding functions (with fallbacks
  to documented ones), the Classic quest log, and the optional TomTom addon.

The packaged app on Windows is checked by the Windows build workflow on each push: it
builds the app and the installer, opens the app and checks that its window (WebView2)
rendered from the backend's state with the tray icon present, then installs, opens and
uninstalls it like a player would. On a Windows 11 test machine the installer and the app
were also clicked through by hand, with screenshots: a fresh install, an update from 1.0.0
and from this version while the app ran, both uninstall answers, light and dark mode, and a
question from a simulated game answered by a local model stand-in. A player has not used
the installed app yet.

Proven in the real game on 2026-10-17 (German Retail client, version 1.1.0): the
screenshot channel with the original bright square, reply slots read fresh from disk
while playing, and settings and macros applied through Apply.

Not proven yet, because it needs the real game:

1. The dim plate beside the panel: how it looks and whether it decodes.
2. The new panel built on Blizzard's window templates, on Retail and on Classic.
3. Place lookups on live game data (which maps list which entrances, delves and world
   bosses; a world boss being a tagged world quest).
4. Do the "ready" and "picked up" signals work (they use a font file trick)? If not, the
   addon falls back to checking on a timer: slower, but it still works.
5. Does `/reload` free used reply slots? The addon checks instead of assuming.

## Running from source (developers and testers)

Without the installer, the companion runs from a terminal. You need Python 3.10 or newer
and an AI provider key. The desktop app itself runs from source too, on Windows with the
packages in `packaging/requirements-app.txt`: `py companion\gnomecaster_app.py`.

1. **Install Python** from https://www.python.org/downloads/ (on Windows, keep "Install the
   py launcher" ticked).
2. **Get Gnomecaster**: download this repository as a zip and unzip it anywhere. Keep the
   folders together; the companion needs the `addon` folder next to it.
3. **Open a terminal in the `companion` folder** (on Windows: open the folder in Explorer,
   type `cmd` into the address bar, press Enter). On Windows use `py` as below; on macOS
   use `python3` instead.
4. **Install Pillow** (the image library the companion uses, at the tested version):
   ```
   py -m pip install -r requirements.txt
   ```
5. **Get an API key**: create an account at https://openrouter.ai, add a few dollars of
   credit, and create a key at https://openrouter.ai/keys.
6. **Run setup** and answer the questions (provider, key, model, game folder). It tests the
   connection before saving, so a wrong key or model name is caught here, not in the game:
   ```
   py gnomecaster_companion.py setup
   ```
7. **Install the addon**, then restart the game completely (new addons need a restart):
   ```
   py gnomecaster_companion.py install
   ```
   In the game's AddOns list the 20 reply slots appear grouped under Gnomecaster; leave
   them enabled. Installing removes slots 21 to 60 left by older versions. If you
   installed the earlier Wowpilot prototype, delete its `Wowpilot` and `Wowpilot_Inbox01`
   to `Wowpilot_Inbox60` folders from `Interface\AddOns`.
8. **Start the companion** and leave its window open while you play:
   ```
   py gnomecaster_companion.py run
   ```
   It checks the AI connection at start and prints `OK` or what is wrong.

`py gnomecaster_companion.py check` tests the AI connection again at any time. Settings,
including the key, live in `%APPDATA%\Gnomecaster\config.json` on Windows, inside your user
profile (on macOS and Linux the file is made readable by your account only); environment
variables `GNOMECASTER_BASE_URL`, `GNOMECASTER_API_KEY`, `GNOMECASTER_MODEL` and
`GNOMECASTER_WOW` override it.

## First in-game test (about 10 minutes)

1. **Receiving (reply slots and ready signal)**, with the companion not running:
   - in game: `/gc probe` should print `false`
   - in the terminal: `py gnomecaster_companion.py write-test`
   - in game: `/gc probe`; `true` means the ready signal works
   - in game: `/gc poll` should print "Inbox test OK - written by the companion at ..."
   - in game: `/reload`, then `/gc status`. `next slot 1` means the reload freed the slots;
     `next slot 2` means used slots stay loaded across a reload (the addon skips them).
2. **Sending (screenshot channel)**:
   - terminal: `py gnomecaster_companion.py run` (leave it running)
   - in game: `/gc ping`; the terminal should print the decoded request (your class, zone,
     quest log ...)
3. **Round trip**: in game `/gc test`. The panel should say `Round trip OK in X.Xs via
   ready-signal` (or `via timed poll`) and name the model the companion uses.
4. **The plate**: ask anything and watch the right side of the panel (or its left side
   near the screen edge). If no answer comes, `/gc beacon classic` and ask again, and tell
   me which style worked.
5. **Places**: `where is the Atal'Aman delve`, `take me to the Magisters' Terrace`,
   `mark the world boss on the map`. The panel names what it found and in which zone, or
   the closest names it knows.
6. **Memory**: let it offer something, answer `ja`, then `/reload` and refer back to it.
7. **Try the examples** from "Using it", and open "What Gnomecaster saw" in the app for
   anything that went wrong.

Please send back the result line of each step and anything red in chat. If step 2 fails,
try `/console screenshotFormat png` and `/gc ping` again, and check whether a screenshot
appeared in the game's `Screenshots` folder.

## For developers

`CLAUDE.md` describes the code layout, the protocol, the trust boundary and the checks
(`tests/run_all.sh`, `tools/wow_api.py check`, `tools/eval_models.py`).
`docs/REVIEW.md` lists known defects; `docs/PROGRESS.md` is the dated log.
