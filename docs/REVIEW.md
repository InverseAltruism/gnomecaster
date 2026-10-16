# Code review, 2026-10-16

Scope: the whole repo after the rename to Gnomecaster. Apart from names, the code is identical to commit `0bfb684`. Every file was read. Two reviews were run independently and every finding below was re-checked before inclusion. "Verified" means the exact code path was read or the behaviour was reproduced by running code; "inferred" means it depends on game-client behaviour nobody here can run. Commands and counts are in `docs/PROGRESS.md` or quoted here.

## Verdict

Good prototype code by someone who knows the WoW runtime. The addon has clear module boundaries, is defensive against an API that differs per game version and hides values in combat, and the Lua serialiser between model output and the game holds up under fuzzing. It is not yet product-grade. Validation checks the shape of model-proposed actions but not their meaning, so a macro can carry arbitrary Lua, and with auto-apply on it is installed and bound to a key without a prompt. One malformed model reply crashes the companion. The test runner cannot fail, the whole model path has no tests, and knowledge is hand-mirrored between Lua and Python. Each of these is cheap to fix. The open question that matters more is whether the screenshot and reply-slot channels work on a real client at all, including what `/reload` does to loaded reply slots.

## Strengths

- Addon modules split by concern, 72 to 259 lines each, loaded in dependency order by the TOC, all through one `ns` table. `Request` orchestrates `Context` and `Json` into `Beacon` on the way out and `Inbox` into `Actions` on the way back; nothing below `Request` calls it.
- Built for a hostile runtime: every context section runs under pcall (`Context.lua:23`); API fallbacks across game flavors (`Core.lua:31-33`, `Context.lua:40-41`, `Context.lua:101-132`); Midnight secret values are dropped before encoding, keys included (`Core.lua:18-25`, `Json.lua:43`).
- The serialiser is injection-safe: only printable ASCII passes through `lua_str`, every other byte becomes a three-digit escape. 5006 generated strings, including injection attempts such as `"]] os.exit(1) --`, round-trip byte-exact through Lua 5.1.5.
- The wire protocol has the right parts and the two ends agree: magic, version, big-endian length, adler32 with matching initial state, MSB-first 3-bit packing, and markers at both ends of row 0 that calibrate the cell size. Decoding survives JPEG and 1.25x scaling (tested) and takes 17 to 153 ms per screenshot.
- The ready signal only trusts a not-ready to ready transition seen while waiting, so a cached font cannot trigger it falsely; the companion's `MIN_NOT_READY` and generation counter are the matching half. All three delivery modes are covered by scenarios.
- The action handler table (`check`, `describe`, `run`, `instant`, `order` per type, `Actions.lua:42-185`) is the right extension point, and `pcall` around each `run` keeps one bad action from aborting the rest.
- The harness runs the real addon and companion code and asserts on recorded API calls with their arguments. The README is candid about what is unproven.

## Findings

### R1. High: model-proposed macros can run arbitrary Lua, unprompted under auto-apply (verified)

`Actions.lua:107-111` checks a macro body only for length (255) and `Actions.lua:154-157` a binding key only against `^[%w%-]+$`; nothing on either side filters `/run`, `/script` or `/click`. Reproduced with the real `Actions` code and auto-apply on: a macro with body `#showtooltip\n/cast Rejuvenation\n/run DeleteCursorItem()` was created and bound to `W` with no prompt. The Lua then runs on the player's next press of W, with the hardware event that protected calls need.

Who can do this: whoever controls the model's reply. That is the configured endpoint (the README suggests free third-party models) or a plain model mistake. Prompt injection through game data is unlikely: quest text comes from Blizzard and player names are letters only. What they gain is Lua execution on a key press, which they do not otherwise have. In the default mode the body is shown on the confirm bar before Apply, but the bar renders WoW escape sequences live, so a colour code matching the bar's background could hide a line (inferred; see R10).

Fix: an allowlist of macro commands (`#showtooltip`, `/cast`, `/use`, `/castsequence`, targeting and stop commands) instead of a denylist; always confirm macro and bind changes even under auto-apply; escape `|` as `||` in anything displayed from the model.

### R2. High: any error while answering stops the companion and loses the request (verified)

`handle()` runs without an exception handler (`companion/gnomecaster_companion.py:571`), `main` catches only `KeyboardInterrupt`, and the screenshot is deleted before `handle()` runs (line 568). Reproduced trigger: Python's `json.loads` accepts a lone UTF-16 surrogate such as `"\ud83d"` (half an emoji), `sanitize()` keeps it, and `lua_str` raises `UnicodeEncodeError` at line 181. A stub brain returning `{"say": "Here you go \ud83d"}` made `handle()` raise. Inferred second trigger: on Windows, `atomic_write` re-raises `PermissionError` if a scanner or the client holds `inbox.lua` for more than its 2 s retry window. Either way the process exits, and the addon reports "is the companion app running?" after 60 s.
Fix: `lua_str` encodes with `errors="replace"`; `cmd_run` catches per-request errors, logs them and continues; delete the screenshot only after `handle()` succeeds.

### R3. High: `tests/run_all.sh` cannot fail (verified)

Line 12 pipes each scenario into `grep` without `pipefail`, so the exit status is grep's. Mutations that broke action-bar placement (6 FAIL lines) and that left half the rename undone (7 FAIL lines each) all exited 0. Nothing can gate on this script.
Fix: `set -o pipefail` and a failure counter, so every scenario still runs and the exit status reflects all of them.

### R4. Medium: what `/reload` does to loaded reply slots is unknown (inferred)

The design assumes `/reload` frees the reply slots (the `Inbox.lua` header comment, README, and the Reload UI button offered when slots run out). The only documentation found says a reload loads "all enabled non-LoadOnDemand addons" and says nothing about load-on-demand addons that were already loaded. If they stay loaded, `Inbox.next` restarts at 1 while slots 1 to k are loaded: `LoadAddOn` returns true without running the file, every such slot counts as empty, each costs a timed poll of about 3 s, and after enough reloads a session cannot get a reply at all.
Fix that is safe under either behaviour: at startup, advance `Inbox.next` past every slot that `C_AddOns.IsAddOnLoaded` reports as loaded (nothing calls it today). Added to the in-game test in `README.md`.

### R5. Medium: README claims and the companion's real entry point are untested (verified)

- "Bad model output (unknown action types, nested junk) is dropped": `sanitize`, `parse_json_loose` and `_ask_model` are not called by any test, and the offline brain never produces bad output, so the skip branch in `Actions.Handle` never runs.
- "Ordinary screenshots are ignored and left alone": no test decodes an image without a beacon, and `cmd_run`, which decides between delete and leave, never runs. The magenta specks in `render.py` do not test rejection either, because the scan reaches the real beacon at pixel (0,0) first and stops.
- `tests/driver.py:21-31` re-implements `handle()` without the generation counter and `not_before`, and passes `keep_probe=True`. `MIN_NOT_READY`, the probe-expiry timer and `handle()` itself have no coverage, and the copy can drift from the original.
- Also untested: slot exhaustion (`Request.lua:50-52`, `68-71`) and `Actions.Apply` in combat (`Actions.lua:239-248`). The e2e macro assertions depend on the offline demo's regular expressions, not on the model path.
Fix: tests for these, `driver.py` calling `handle()` with a stub brain; until then, move the two claims out of "proven".

### R6. Medium: knowledge hand-mirrored across Lua and Python (verified)

- Seven constants, listed in `CLAUDE.md`, with no test that compares them. Mutation shows the e2e tests catch drift in the beacon magic and slot folder names. They cannot catch drift in the slot count, the TOC Interface list or the action-type list, because the scenarios use only slots 1 to 3 and only valid actions (inferred from the scenarios).
- The action schema lives in four places: the prose in `SYSTEM_PROMPT`, `ACTION_TYPES`, `offline_answer`, and the `Actions.lua` handlers. Each new action touches all four.
- The waypoint scale (0 to 1 or 0 to 100) is encoded three times: the prompt says 0 to 1, `offline_answer` divides by 100, `Actions.lua:50` rescales both if either exceeds 1, so `x=0.5, y=50` becomes `x=0.005`.
- The addon sends `slots = ns.NUM_SLOTS` in every packet (`Request.lua:21`); the companion never reads it.
Fix: one test that reads both sides; the companion takes the slot count from the packet.

### R7. Medium: the companion is one file holding four concerns (verified)

`companion/gnomecaster_companion.py`, 616 lines: screenshot decoding (57-173), reply-slot writing and Lua serialisation (176-290), the brain with the prompt, `sanitize`, a 71-line regex demo and the HTTP client (293-477), and CLI plus folder watching (480-616). `handle()` reaches into `Slots.lock` and `Slots.generation` (lines 520-521) instead of calling a `Slots` method. A single file suits a prototype handed to a tester, and the seams are clean, so the split into a package (protocol, slots, brain, cli) is mechanical. Do it before the brain grows.

### R8. Medium: test runs can call a real model (verified)

`tests/driver.py` constructs `Brain()`, which reads `GNOMECASTER_BASE_URL`, `GNOMECASTER_MODEL` and `GNOMECASTER_API_KEY` from the environment, and `run_all.sh` does not clear them. A developer with them set spends API credit on every run and gets nondeterministic failures, since the assertions expect the offline demo's replies.
Fix: clear the variables in `run_all.sh`, or have the driver force the offline brain.

### R9. Medium: the mock cannot prove the game-facing assumptions (verified)

- `tests/wowmock.lua:11-15` returns a no-op for any widget method it does not define, so a misspelled method, or one missing on a game flavor, passes. This is the bug class the in-game test is most likely to hit.
- The mock's secret value is a table, while a real secret is assumed to keep its type (inferred). The addon's guards have the form `type(v) ~= "string" or IsSecret(v)`, so the mock cannot show whether the `IsSecret` half is what protects a field.
- The mock's `SetFont` returns true exactly when the file is non-empty, which is the hypothesis under test, so the probe scenarios prove the addon is consistent with the hypothesis, not that it holds.
These are limits to state, not things to fix in the mock.

### R10. Low: model text is displayed with live WoW escape sequences (verified)

`UI.AddLine` (`UI.lua:117-120`) passes `say` and every `describe` string to `AddMessage` unescaped. A reply can fake the green "Round trip OK" line, draw textures with `|T...|t`, or hide part of a confirm-bar entry (R1). Fix: escape `|` as `||` in model-supplied strings.

### R11. Low: module boundaries in the addon (verified)

`Actions.lua` makes 9 calls into `ns.UI` while `UI.lua:84,89` calls back into `Actions.Apply` and `Actions.Cancel`; the pending changes live in `Actions` and the bar that shows them in `UI`. That is a two-way dependency, and it means `Actions` cannot be tested without the UI and a second front end (voice, for example) would have to copy logic. `Core.lua:59-98` mixes the namespace and helpers with the slash-command dispatcher, and `Inbox.lua:138-158` carries chat-printing debug commands inside the transport module. Fix: `Actions.Handle` returns results or fires callbacks and `UI` renders them; slash commands move next to `Request`.

### R12. Low: validation normalises garbage instead of rejecting it (verified)

Python's `json.loads` accepts `NaN` and `1e400`, and `lua_value` writes both as `0` (line 204). Reproduced: a waypoint with `x: NaN, y: 1e400` arrives as a valid waypoint at (0, 0) instead of being dropped. `num()` (`Actions.lua:27-32`) has no integer check (icon 2.5, slot 5.5 reach the API inside pcall), and `map` has no upper bound.

### R13. Low: duplicated truncation helper (verified)

`Context.lua:12` `trim` and `Errors.lua:19` `plainString` are the same function. Move one copy to `Core` as `ns.Trim`.

### R14. Low: a truncated screenshot is never retried (verified path, inferred trigger)

`cmd_run` treats a file as complete when its size is unchanged across two polls 150 ms apart, and adds the name to `seen` before decoding (line 558). If the client pauses mid-write for longer, decoding fails, the error is printed, and the file is never looked at again; the request times out after 60 s.

### R15. Low: a covered beacon fails with the wrong message (inferred)

The grid is drawn at TOOLTIP strata in the top-left corner (`Beacon.lua:80`). A tooltip or another addon's frame over that corner would corrupt it; the companion prints a checksum error, and the addon waits 60 s and then asks whether the companion is running. Worth trying during the in-game test with a tooltip held over the corner.

### R16. Low: no dependency manifest (verified)

Pillow is installed with an unpinned `pip install pillow`; there is no requirements file or lockfile.

### R17. Low: dead code (verified)

`Inbox.Cancel`, `Beacon.IsBusy`, the `Beacon.adler32` export and `find_marker` have no callers.

## Considered and declined

- Messages written to a hidden panel. Reported by the second review, but the ask and test paths call `UI.Toggle(false)`, which shows the panel; only `/gc ping` after closing the panel is affected. Not worth a change.
- Generating the reply slots at install time instead of committing them. The committed slots are byte-identical to the generator's output, install and the tests need them, and R6's test covers drift.
- Rewriting `Inbox.Await` as an explicit state machine. It is one dense 50-line closure, but both reviews traced its paths (stale reply, slow companion, cached fonts, no companion) without finding a defect, and scenarios cover all three delivery modes.
- Replacing `Json.lua` with a library. WoW ships none; the 72-line encoder is deterministic and handles secret values.

## Suggested order

1. The 10-minute in-game test from `README.md`, now including the `/reload` check (R4). It decides whether the design works and needs a real client.
2. R3, so that every later change is gated.
3. R1 and R2, each with a test.
4. R4's startup skip, which is safe whatever the in-game test shows.
5. R5, R6 and R8: tests for the model path, the mirrored constants, and test isolation.
6. The low findings as they come up; R7 before the brain grows.
