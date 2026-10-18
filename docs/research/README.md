# Research behind docs/PLAN-macros.md, 2026-10-17

Each report labels its claims VERIFIED (read in code or a primary source), REPORTED or
INFERRED, and gives the URL or `file:line`. Paths that mention `scratchpad/` or
`research/src/` point to working copies that were not kept; the URLs and commits in each
report are the sources.

- `players.md`: what players ask for and struggle with (83 requests), Midnight 12.x changes
  to macros and addons, competitors, Blizzard's policy texts. Details in
  `player-requests.md` and `competitors.md`.
- `prior-art.md`: GSE, Macro Toolkit, Mega Macro, Talent Loadout Manager,
  LibEditModeOverride, Ace3, wow-ai: techniques, licences, what to take.
- `blizzard-apis.md`: every Blizzard API the plan uses, checked in the 12.1.5 UI source
  (commit `18c6d677`), with restriction flags.
- `settings-cvars.tsv`: all 361 settings registrations of Blizzard's options panel
  (321 distinct console variables, 55 settings that are not console variables).
- `bindings.tsv`: all 447 key binding entries (362 in-game bindings).
