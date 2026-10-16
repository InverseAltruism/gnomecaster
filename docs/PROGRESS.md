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
