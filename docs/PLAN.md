# Plan after the first in-game test, 2026-10-17

## What the test showed

The owner played with version 1.1.0 on a German Retail client (12.x, level 90 character in
Silvermoon). Screenshots are in `docs/field-test-2026-10-17/`.

Proven on a real client for the first time: the screenshot channel (every question was
decoded), load-on-demand reply slots re-read from disk mid-session (many different replies
in one session), settings and macros applied through Apply.

Failed, with the cause found in the code:

| Symptom | Cause |
|---|---|
| No memory ("ja" answered with "what are you saying yes to?") | `brain.Brain.answer` sends the system prompt and the current question only |
| "Not in the available data" for the world boss, a delve, the gear upgrade vendor | the prompt orders the model to refuse anything not in the context; the context has no places at all |
| No map pins | a waypoint needs a uiMapID and coordinates from the model, which it does not have; the addon never asks the game, although `C_EncounterJournal.GetDungeonEntrancesForMap`, `C_AreaPoiInfo.GetDelvesForMap`, `C_AreaPoiInfo.GetAreaPOIForMap`, `C_TaskQuest.GetQuestsOnMap` and `C_TaxiMap.GetTaxiNodesForMap` exist in 12.1.5 |
| Asks "shall I turn it on?" in text, then forgets | the prompt never says the addon already asks before Apply |
| No way to see what went wrong | the app keeps no transcript of what was sent and answered |
| 60 entries in the addon list | one addon per reply slot; Blizzard's `AddonList.lua` (12.1.5) collapses only `## Category` nodes, never `## Group` children, and has no hide flag |
| A square of flickering coloured pixels top left on every question | the beacon: full-intensity RGB cells on black, unframed, in the screen corner |
| Windows warns before running the installer | SmartScreen on an unsigned exe; no code change removes it (`docs/PLAN-distribution.md`) |
| The look: generic, nothing of WoW or gnomes | flat violet backdrop in game, a stock SaaS style in the desktop window |

## Decisions (owner, 2026-10-17)

- 20 reply slots instead of 60; a Reload button in the panel when they run out.
- Web search only when the model decides it needs it, through OpenRouter's web search
  server tool; about $0.005-0.007 extra per searched question (OpenRouter docs, read
  2026-10-17). Other providers answer without search.
- Desktop look: "gnomish workshop": dark iron and brass, cogs and rivets, blueprint and
  parchment panels, a fantasy serif for headings. Original art only; no Blizzard assets
  outside the game.
- In game: Blizzard's own frame templates and fonts so the panel looks like part of the UI.
- Signing: later. Unsigned builds keep the SmartScreen warning until then.

## Work, in parallel tracks with fixed file ownership

A. Companion brain (Python). Conversation memory, the new prompt, web search, action
   results fed back, the transcript, the flaky test, evaluation scenarios from the real
   questions. Files: `brain.py`, `prompt.py` (except the `goto` entry in `ACTION_FIELDS`),
   `model.py`, `service.py`, `serve.py`, `app_api.py`, new modules, their tests,
   `tools/eval_*`.
B. Addon, places and context (Lua). `Places.lua` (new: find a place by name in the game's
   own data), the `goto` action, richer context, action results, `/gc new`. Files:
   `Places.lua`, `Actions.lua`, `Context.lua`, `Request.lua`, the TOC file list, slash
   commands in `Core.lua`, the `goto` entry in `prompt.ACTION_FIELDS`, Lua scenarios.
C. Transport. The beacon as a framed plate beside the panel, dim palette with calibrated
   decoding, search of the whole screenshot, `/gc beacon classic` fallback; 20 slots and the
   cleanup of stale slot folders on install. Files: `Beacon.lua`, `protocol.py`,
   `Inbox.lua`, `ns.NUM_SLOTS` in `Core.lua`, `tools/make_inboxes.py`, the slot folders,
   `game.py`, `test_protocol*`, `test_contract.py`.
D. In-game panel. Blizzard templates, gnomish details, `UI.BeaconAnchor()`. Files:
   `UI.lua`, `Media/` (except `icon.tga`), template support in the test mock.
E. Desktop window. The workshop redesign, a new icon, the transcript view. Files:
   `desktop/ui/`, `assets/brand/`, generated icons, `tools/make_icons.py`.

## Interfaces between the tracks

1. `goto` action: `{"type":"goto","name":"<place>","kind":"dungeon|raid|delve|boss|quest|flight|poi|zone|any","quest":<questID, optional>}`.
   The addon resolves the name against the game's data in the client's language, sets the
   map pin and Blizzard's arrow (TomTom too when it is loaded) and reports what it found.
2. Action results: the addon sends the outcome of the previous reply's actions in the next
   packet as top-level `last`: at most 6 entries `{"type":..., "ok":true|false, "say":"<= 120 chars"}`,
   including Apply decisions (`applied`, `declined`, `pending`).
3. Conversation key: top-level `conv` (at most 16 characters), created by the addon on the
   first question, kept in SavedVariables across `/reload`, renewed by `/gc new`. The
   companion keeps the last 10 exchanges per key and forgets a key after 30 minutes idle.
4. Transcript: every exchange (time, conv, question, context, `last`, raw model output, the
   cleaned reply, error, seconds, model, whether it searched) appended as JSON lines under
   the data folder's `transcripts/`, 14 days kept. Window calls: `getHistory({"limit":n})`
   returns `{"ok":true,"items":[...]}`; `openTranscripts({})` opens the folder. No key ever.
5. Beacon anchor: `ns.UI.BeaconAnchor()` returns the frame the plate attaches to, or nil
   (then the plate sits top left as before).
6. Reply slots: 20, in all places the contract test lists.

Each change lands with a test that fails without it; the full check list in `CLAUDE.md`
runs before handing over. Unverifiable here and left to the next in-game test: the plate's
look and decoding on a real screen, the new panel's look, place lookups on live game data.

Status, end of 2026-10-17: all five tracks are merged and pass the checks; two reviews
(E1 to E9 in `docs/REVIEW.md`) are fixed or declined with reasons. Changes against the
plan: the per-search price is about $0.0108 (OpenAI's native search through OpenRouter),
not the $0.005-0.007 first quoted; with search the model may pin a guide's coordinates for
vendors and trainers on the player's map; the conversation key is per character. Next:
the owner's in-game test (`README.md`, First in-game test).

---

# Refinement plan, 2026-10-16

Goal: make Gnomecaster worth a first in-game test: correct and safe answers, a connection that
works the first time, failures that say what to do, and a panel that feels smooth. Inputs:
`docs/REVIEW.md` (two reviews), a third review run the same day, and the first real model
evaluation (`tools/eval_models.py`, numbers below).

## What the evaluation showed

20 scenarios through the real companion and addon code, OpenRouter, default model settings.

| Model | Hard pass | Fallbacks | p50 / max latency | Cost per request |
|---|---|---|---|---|
| openai/gpt-6-luna | 18/20 | 0 | 2.9 s / 6.0 s | $0.00017 |
| google/gemini-3.8-flash | 18/20 | 0 | 3.7 s / 14.7 s | $0.00199 |
| deepseek/deepseek-v4.1-flash | 18/20 | 0 | 3.7 s / 44.0 s | $0.00011 |
| anthropic/claude-haiku-5.5 | 17/20 | 1 | 3.1 s / 436.9 s | $0.00034 |
| qwen/qwen3.8-flash | 13/20 | 5 (upstream 429) | 10.4 s / 24.0 s | $0.00019 |
| google/gemma-4-31b-it:free | 0/20 | 20 (upstream 429) | n/a | free |

- Every model failed the same two scenarios, both caused by the prompt: it never forbids `/run`
  in macros, and it never lists the settings the addon accepts (models proposed `graphicsQuality`,
  one invented `autoLoot`).
- The 436.9 s request was a provider error (HTTP 200, `finish_reason: error`, half an answer).
  The companion's 60 s timeout is per socket read, not per request, so nothing stopped it.
- Free models were rate-limited upstream on most calls. The README must stop recommending them.

## Phases

Each phase lands with tests that fail without it. `tests/run_all.sh` must be able to fail first.

1. Test gate. `run_all.sh` exits non-zero on any failure and also runs the Python unit tests.
   The WoW mock rejects widget methods that Blizzard's API documentation does not list
   (`tests/wow_api_methods.lua`, generated by `tools/wow_api.py`). One test pins the constants
   mirrored between Lua and Python.
2. Companion, model connection. One overall deadline per request (40 s) so a reply always lands
   while the addon still waits. `finish_reason`, empty content and `<think>` blocks handled. Errors
   mapped to plain instructions (bad key, no credit, unknown model, rate limit with retry time,
   provider error, timeout, no network). No regex-demo actions when a model is configured; the demo
   only runs when none is, and says so. One retry for 429/5xx when time allows. `handle()` never
   raises; the screenshot is deleted only after the reply is written; surrogates cannot crash it.
3. Companion, setup. Settings from a config file written by a `setup` command (provider preset,
   key typed hidden, model, game folder), overridable by environment variables. `setup` and `run`
   check the endpoint, key and model before play. `/gc test` reports that check, so a dead key no
   longer shows "Round trip OK".
4. Prompt. Lists the allowed settings by exact name (read from `Actions.lua`, the single source),
   forbids script commands in macros, honours negation, uses spell names in the client's language,
   keeps answers short and free of `|` escape characters. Re-run the evaluation; pick the default
   model from the numbers.
5. Addon, safety and correctness. Macro bodies limited to an allowlist of slash commands; model
   text escaped before display; numbers validated strictly (integers, consistent coordinate
   scale); macro limits from `Constants.MacroConsts` (retail has 30 character macros, the addon
   assumed 18); `GetMacroIndexByName` and `SetBindingMacro` used when present, with fallbacks
   through `GetMacroInfo` and `SetBinding`, which Blizzard's own UI uses at build 12.1.5; a mark
   asks first if the target changed since the question.
6. Addon, reliability. Skip reply slots that are already loaded at startup; remember per client
   that the ready signal works; the companion signals the next nine slots (the most the addon can
   spend while waiting) instead of six.
7. Addon, feel. Panel and confirm bar fade in and out; animated thinking indicator; input history
   on the arrow keys; typed text kept when a request is refused; placeholder text; the panel opens
   when an answer arrives; resizable panel with saved size; recent conversation kept across reloads.
   Every widget call is checked against Blizzard's API documentation, since nothing here can run
   the game client.

Out of scope for this round: a Windows executable (PyInstaller cannot cross-compile from Linux;
a GitHub Actions build on a Windows runner is the likely route), and anything that needs the
in-game test results first.

## Status, end of 2026-10-16

All seven phases are done; `docs/REVIEW.md` maps each finding to its fix and test. Changes
against the plan:

- Phase 6: remembering across sessions that the ready signal works was dropped. If the
  companion later ran without a signal font, a remembered "works" would push the first poll
  from 3 s to 12 s; saving one slot on the first question is not worth that. Added instead:
  `ack.ttf`, so the panel shows when the companion picked a question up and, once signals are
  known to work, reports a stopped companion within 5 s instead of 60.
- Phase 4: two prompt-adjacent fixes came from the second evaluation run: prose answers are
  kept as the answer (one model explained a refusal in prose and the player saw a format
  error), and macro names over WoW's 16 bytes are shortened consistently across macro, bar
  and bind actions.
- Final evaluation: `openai/gpt-6-luna`, `anthropic/claude-haiku-5.5`,
  `deepseek/deepseek-v4.1-flash` and `google/gemini-3.8-flash` each passed 20 of 20.
  `openai/gpt-6-luna` stays the setup default.
