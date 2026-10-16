# Wowpilot — prototype

An in-game AI helper for World of Warcraft. You type (or later: talk) inside a WoW
panel; the helper answers there and *does* things: creates and edits macros, puts
them on your bars, binds keys, sets waypoints and the quest arrow, marks targets,
changes settings, and explains your Lua errors.

This prototype exists to prove the hard part: **getting requests out of the game
and answers back in, without tabbing out, copy-pasting or reloading.** The AI part
is deliberately simple (any OpenAI-compatible model, or an offline demo).

## How it works

```
 WoW (addon)                                       Companion app (your PC)
 ───────────                                       ───────────────────────
 you type in the Wowpilot panel
 addon reads live context from the client          
 (class/spec, zone + coords, quest log,
  where the game says your quest goes next,
  target, recent Lua errors)
        │
        ▼
 draws it as a coloured grid in the top-left  ──►  sees the new screenshot file,
 corner for 2 frames and calls Screenshot()        decodes the grid, deletes the file
                                                          │
                                                          ▼
                                                   asks the model (with the context)
                                                          │
 loads the next "reply slot" addon            ◄──  writes the answer into the reply
 (load-on-demand addons are read from disk          slot files + a "ready" signal
  at the moment they're loaded)
        │
        ▼
 shows the answer; runs waypoints/marks at once;
 macro / bar / keybind / setting changes wait for
 one click on Apply (or /wp auto on)
```

Nothing touches the game's memory, nothing sends key presses, nothing works in
combat. The addon only uses normal addon functions; the app only reads screenshot
files and writes files in the AddOns folder (the same kind of thing the TSM and
Raider.IO desktop apps do).

## What's proven and what isn't

Tested here (Lua 5.1.1 — WoW's Lua version — running the real addon code against a
mocked WoW API, plus the real companion code):

- request → screenshot grid → decode → answer → reply slot → actions, end to end
- macro created + placed on slot 5 + bound to SHIFT-E only after Apply
- quest arrow set to the game's own next-step coordinates
- Lua error captured and sent along; secret (Midnight) values left out safely
- decoding survives JPEG screenshots and a 1.25× rescaled screenshot; ordinary
  screenshots are ignored and left alone
- bad model output (unknown action types, nested junk) is dropped

**Not yet proven in the real game** — that's what the 10-minute test below is for:

1. Can addons call `Screenshot()` and does the grid come out readable?
2. Are load-on-demand addon files really read fresh from disk mid-session?
3. Does the "ready" signal work (EditBox `SetFont` noticing a font file appear)?
   If not, the addon falls back to timed polling by itself — slower (≈3 s
   minimum) and it uses up reply slots faster, but it still works.

## 10-minute test

Needs Python 3.9+ and Pillow (`pip install pillow`). Commands are run from the
`companion` folder. Replace the path with your own game folder.

1. **Install the addon** (copies `Wowpilot` + 60 `Wowpilot_InboxNN` reply slots):
   ```
   python wowpilot_companion.py install --wow "C:\Program Files (x86)\World of Warcraft\_retail_"
   ```
   Then **fully restart WoW** (new addons need a restart, not just /reload).
   In the AddOns list the reply slots appear grouped under Wowpilot — leave them enabled.

2. **Test receiving (reply slots + ready signal)**, before starting the companion:
   - in game: `/wp probe` → expect `false`
   - in a terminal: `python wowpilot_companion.py write-test --wow "...\_retail_"`
   - in game: `/wp probe` → `true` means the ready signal works
   - in game: `/wp poll` → should print "Inbox test OK – written by the companion at …"
   - then `/reload` (resets the slots for the next test)

3. **Test sending (screenshot channel)**:
   - terminal: `python wowpilot_companion.py run --wow "...\_retail_"` (leave it running)
   - in game: `/wp ping` → the terminal should print the decoded request
     (your class, zone, quest log …)

4. **Full round trip**: in game `/wp test` → the panel should say
   `Round trip OK in X.Xs via ready-signal` (or `via timed poll`).

5. **Try it** (offline demo, no model needed): open the panel with `/wp` (or `/wowpilot` if another addon owns `/wp`) or bind a key
   (Esc → Options → Keybindings → AddOns → Wowpilot) and try:
   - `take me to my quest` (track a quest first)
   - `way 45.2 63.1`
   - `mark skull` (with a target)
   - `macro for Rejuvenation on slot 5 bind to shift-e` (use one of your spells)
   - `what was that error`

**Please send back:** the result line of each step, and anything red in chat.
If step 3 fails, also try `/console screenshotFormat png` and `/wp ping` again,
and check whether a screenshot appeared in the `Screenshots` folder.

## Connecting a model

Set three environment variables before `run` (any OpenAI-compatible endpoint):

| Option | WOWPILOT_BASE_URL | WOWPILOT_MODEL (example) |
|---|---|---|
| OpenRouter (free models with a free account) | `https://openrouter.ai/api/v1` | a `:free` model id |
| OpenAI API key | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Local model (Ollama) | `http://localhost:11434/v1` | `llama3.1` |

plus `WOWPILOT_API_KEY` (not needed for Ollama).

Windows PowerShell example:
```
$env:WOWPILOT_BASE_URL="https://openrouter.ai/api/v1"; $env:WOWPILOT_API_KEY="sk-or-..."; $env:WOWPILOT_MODEL="<model id>"
python wowpilot_companion.py run --wow "C:\Program Files (x86)\World of Warcraft\_retail_"
```

## Known limits of this prototype

- One request at a time; ~2.4 KB of context per request (the addon trims the quest
  log to fit). Compression would roughly triple that.
- 60 reply slots per session. With the ready signal each answer uses one; with timed
  polling about 2–3. When they run out the panel offers a one-click Reload UI.
- The grid flashes in the top-left corner for a moment while the screenshot is taken.
- Colour-blind filters or other post-processing that changes colours may break the
  grid (tell me if you use one).
- No knowledge base yet: the model only knows what the game client sends (which is
  exact and current) plus its own training. It's instructed to say "I can't look
  that up yet" instead of inventing NPC locations or patch facts.
- Not in combat, by design: Blizzard blocks macro/bar/binding changes in combat, and
  Midnight hides combat data from addons.

## Layout

```
addon/Wowpilot/            the addon (Core, Context, Errors, Beacon=send, Inbox=receive, Actions, UI, Request)
addon/Wowpilot_Inbox01-60/ reply slots (load-on-demand)
companion/                 the desktop companion (single Python file)
tools/make_inboxes.py      regenerates the reply slots
tests/                     the simulation harness used above (needs a Lua 5.1 interpreter)
```
