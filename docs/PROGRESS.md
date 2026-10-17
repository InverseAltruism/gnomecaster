# Progress log

## 2026-10-16: repository set up from the prototype

- Imported `wowpilot-prototype.zip` (sha256 `044f3c5744396dcaa9bb929db32baeb95e909e83c1387385f91da295ba45da08`) verbatim as the first commit, 199 files. The 60 reply slots are byte-identical to the output of `tools/make_inboxes.py`. The archive itself stays out of git.
- Second commit: README dash fixes (5 em dashes, plus 1 en dash that also misquoted the companion's plain hyphen), `.gitignore`, `CLAUDE.md`, this log.
- Test baseline with `tests/run_all.sh`, Lua 5.1.5 built from source, Python 3.12.3, Pillow 12.3.0: 97 PASS, 0 FAIL over 8 scenarios.
- Companion decode time on this server, median of 5 runs: 36 ms for a 1920x1080 PNG with a beacon, 72 ms for the 1.25x scaled screenshot, 17 ms for the JPEG one, 153 ms for a 1920x1080 noise PNG with no beacon (full 640x640 scan). A player's PC will differ.

Open items, none fixed yet:

1. `tests/run_all.sh` cannot fail. Checked by mutation: changing `place(a.slot)` to `place(a.slot + 1)` in `Actions.lua` printed 6 FAIL lines and the script still exited 0. Fix: `pipefail` plus a failure counter, so every scenario still runs and the exit status reflects them.
2. Seven constants are mirrored between Lua and Python (table in `CLAUDE.md`) with no test that they agree.
3. The three in-game unknowns in `README.md` decide whether this design works at all. The 10-minute test on a real client should come before further feature work.
4. Policy risk has not been assessed. Blizzard's UI add-on policy and Terms of Use have not been checked against the screenshot channel or the mid-session reply-slot reload. The README's comparison with the TSM and Raider.IO desktop apps is the prototype author's claim and is unverified.
5. Naming: the repo is gnomecaster, the code says Wowpilot (addon and slot folder names, `WowpilotDB`, global functions and frames, `/wp` and `/wowpilot`, `WOWPILOT_*` environment variables, the `"WP"` beacon magic). A rename touches the wire protocol and the SavedVariables name, so it belongs in one commit that covers both halves, with tests.
6. Low: with `/wp auto on`, a model-proposed `bind` can replace any key binding, a movement key for example, without a prompt; the key check is only `^[%w%-]+$`. In the default mode the confirm bar shows "(replaces ...)" before Apply.

## 2026-10-16: renamed to Gnomecaster, code review

- Renamed every identifier from Wowpilot to Gnomecaster: addon folder and TOC, the 60 reply slots (regenerated with `tools/make_inboxes.py`), `GnomecasterDB`, global functions and frame names, the key binding, slash commands `/gc` and `/gnomecaster`, `GNOMECASTER_*` environment variables, the companion's file name, and the beacon magic `"GC"`. `PROTOCOL` stays 1: the new magic already stops old and new halves from decoding each other's packets.
- No SavedVariables migration: the prototype stored only `autoApply` and the panel position.
- `/gc` was checked against warcraft.wiki.gg's list of built-in commands. That list shows full command names only, so an alias or another addon could still own `/gc`; `/gnomecaster` is the fallback.
- Tests after the rename: 97 PASS, 0 FAIL over 8 scenarios. Two mutations that leave half the rename undone (beacon magic changed only on the addon side; slot folder name changed only on the companion side) each produced 7 FAIL lines.
- Code review in `docs/REVIEW.md`. It supersedes the open-items list in the entry above, where item 5 (naming) is now done.

## 2026-10-16: refinement round (docs/PLAN.md)

- A third review by a different model family found 14 issues (C1 to C14 in `docs/REVIEW.md`), four of them corrections to the merged review. All were checked before use.
- Real model evaluation added (`tools/eval_models.py`, 20 scenarios through the real companion and addon code). First run, six models: the best scored 18/20, every model failed the same two prompt-caused scenarios, free models were rate-limited on most requests, and one provider held a request for 436.9 s. Final run after the fixes: four cheap models at 20/20 (numbers in `README.md`). Spend reported by OpenRouter across all runs: about $0.31.
- Companion split into the `companion/gnomecaster/` package; new: settings file and `setup`/`check` commands, a model client with one 40 s deadline and plain-language errors, no demo actions when a model fails, `<think>` handling, crash-proof request loop, pinned Pillow (Python 3.10+).
- Addon: macro command allowlist, escaped display text, strict number checks, retail macro limits from `Constants.MacroConsts` (30 character macros, not 18), fallbacks for two calls Blizzard's 12.1.5 UI no longer uses, a binding that replaces an existing one always asks, marks ask when the target changed, loaded slots skipped, `ack.ttf` signal, and the panel rebuilt with fades, a busy indicator, input history, kept input on refusal, placeholder, resize grip and a conversation kept across reloads.
- Verification without a game client: `tools/wow_api.py` checks every WoW call against Blizzard's UI source at build 12.1.5.70391 (619 API documents and the UI's Lua); the test mock now rejects undocumented widget methods.
- Tests: `tests/run_all.sh` 10 scenarios, 130 checks, and 47 Python unit tests, all passing; the runner now fails when anything fails. A live run sent five questions from the simulated game through the real companion to a real model and back.
- Codex works on this server since `~/.local/bin/setup-codex` (AppArmor exemption for a bubblewrap copy only the inverse group can run); its ten checks pass.

## 2026-10-16: the Windows app and its installer

The owner asked for an installer players can use without a terminal, that looks
trustworthy, with clean icons. Nearly every player is on Windows, so Windows comes first.

- Stack decided (`docs/PLAN-distribution.md`): Python with pywebview (WebView2 window) and
  pystray (tray icon), PyInstaller one-folder build with a locally compiled bootloader, Inno
  Setup per-user installer, GitHub Actions on `windows-2025`.
- App: three-step setup (find the game from the registry or a chosen folder, install the
  addon, Sign in with OpenRouter by OAuth PKCE or paste a key), a dashboard of questions and
  answers from the game, settings, close to tray, start with Windows, single instance,
  logs. A signed-in account without credit keeps its key and gets "Add credit" and "Test
  again" instead of a dead end. Player-facing advice now names the app instead of setup
  commands, in the companion and in the addon.
- Installer: no administrator prompt, branded wizard images rendered from
  `assets/brand/installer-side.svg`, follows the Windows light or dark setting, gets
  WebView2 when missing, asks to quit a running Gnomecaster (named mutex), removes the
  autostart entry on uninstall.
- Supply chain: `packaging/lock.py` hash-locks three install stages and refuses pins
  younger than 14 days or with unpinned dependencies (it caught `tomlkit` missing from the
  hatchling closure). Source archives build with `--no-build-isolation` so pip cannot fetch
  unpinned build tools. Inno Setup is downloaded by version and checked by SHA-256; the
  Actions are pinned by commit.
- Verified here: the app's backend through 60 tests in `tests/test_app.py` (fake game
  folder, fake OpenRouter sign-in and model server, fake registry, pywebview and pystray
  replaced by fakes); mutation runs on the final code with every mutation caught (27 in
  the app backend and shell, 12 in the sign-in code, 14 for the review fixes below; an
  earlier run's survivor had exposed that the callback listener's bind address was
  untested); the real window clicked through in Chromium
  against the real backend, nine steps in light and dark, no page errors; the PyInstaller
  recipe built on Linux with the addon, window files and pystray sources in the bundle;
  every locked file downloaded for Windows with hash checking; PyInstaller built from
  source with only the pinned backend.
- A review by a different model family found 9 defects, all confirmed and fixed with a test
  that fails without the fix (the 14 mutations above, plus two browser scenarios run red
  and green): overlapping workers when two starts or a start and a slow answer coincided
  (start and stop are now serialized, and pausing waits for the question in progress);
  a single-instance check that two quick launches could both pass (the Windows mutex now
  decides); a replaced sign-in that could overwrite the newer key; the setup screen not
  following a background connection check; setup marked done when listening failed; a smoke
  test that could pass on a broken page (the page now sets a ready marker last, and shows
  an error screen when the backend fails); a mutex test that only read source text; and a
  sign-in listener that one idle connection could block. Also fixed while reviewing: the
  window claimed questions wait while paused (they get no answer), and the setup steps
  cross-faded with both visible at once.
- Not verified yet: anything that needs Windows. The workflow builds, unit-tests,
  smoke-tests the app (its window has to reach the backend), builds the installer, then
  installs, smoke-tests and uninstalls it; it runs after the first push.
- Version 1.0.0 (the owner asked for a 1.0 release). A tag `v1.0.0` makes the workflow's
  `release` job publish the tested installer with `SHA256SUMS.txt` and
  `packaging/release-notes.md`; that job is the only one with write access. Before the
  first push, parsing the workflow found a YAML error (`--only-binary=:all: -r` read as a
  key) that would have failed every run; `actionlint` 1.7.12 now reports no problems.

## 2026-10-16: release 1.0.0

- First runs of the Windows workflow, both passed on the first attempt: run 38945331453
  (main) and 38945912250 (tag `v1.0.0`, which also published the release).
- On `windows-2025` with Python 3.13.16: 119 unit tests, 117 passed and 2 skipped (POSIX
  file permissions), including the real Windows mutex test; `pip check` clean; the compiled
  `runw.exe` (sha256 `98206d01...`) differs from PyInstaller's stock one (`2291f269...`).
- Smoke tests of the built app and of the installed app: `ok`, page ready, setup screen,
  tray icon present; the runner's screenshots show the window rendered with the brand
  fonts and icon. The silent install, launch and uninstall cycle passed.
- Release `v1.0.0`: `Gnomecaster-Setup-1.0.0.exe` (17,268,506 bytes, sha256
  `b281a9eb371b036ddcca06191b46352403b430ef376e1d88807ec38f8be93118`, version details
  InverseAltruism / Gnomecaster / 1.0.0, no Authenticode signature) and `SHA256SUMS.txt`.
  The repository is private, so only accounts with access can download it.
- Still unverified: a person using the installed app, and anything in the real game.

## 2026-10-16: polish pass on the app window and the in-game panel

The owner asked for nothing unpolished: smooth animations, good design, intuitive flows.

- Inventory first: every window state in both themes at three sizes, plus filmstrips of
  each animation. Problems found by looking: setup content floating above a mostly empty
  window, buttons cut off at the minimum size, no progress indicator once the step list
  hides, steps jumping when content appears (19 px and 110 px, measured), two steps visible
  at once during a change, a sign-in that could only be escaped by waiting 10 minutes, and a
  default window taller than a 1366 x 768 laptop at 125 % scaling.
- An independent design review (a separate agent, read-only) then ranked 16 issues, plus
  low-priority notes; all but two were fixed. Declined: the slashed zero (a deliberate
  legibility feature of Atkinson Hyperlegible) and dropping "You" from questions (it
  matches the in-game panel's "You:").
- Window: steps hang from a fixed top with their buttons beneath and stay reachable on
  short windows; a compact step bar on narrow ones; a drawn tick when the addon is
  installed and a drawn check on "You're set"; Cancel during the browser sign-in (answers in
  under a millisecond; the backend's sign-in winds down behind it); the out-of-credit state
  as an alert above the questions with Add credit and Check again; examples that copy
  "/gc ..." for the game's chat; action lines grouped by "done" and "waiting for Apply";
  custom radios and selects; a key form with Get a key, Cancel and no key field for Ollama;
  the window sized to the screen.
- In the game: answers type out in place (at most 1.4 s) under a gold "Gnomecaster:" label,
  lines that arrive meanwhile wait their turn, and colour codes, links and UTF-8 characters
  are never cut; the panel uses the app's violet, the brand icon and a glowing spark as its
  busy indicator, and rises as it fades in. Clients without TransformMessages show answers
  at once. Nothing here can render WoW's UI, so the panel's look is unverified.

