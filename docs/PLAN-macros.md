# Plan: the macro, key binding and settings helper, 2026-10-17

Gnomecaster stops trying to be a general game guide and becomes the best way to get a
working macro, key binding or setting in World of Warcraft: written for the player's own
character and game version, checked against the player's own client before it is saved,
and explained when it does not work.

Evidence is in `docs/research/` (index in its README). Claims about Blizzard's code cite
the 12.1.5 UI source (commit `18c6d677`). A review of the first draft (fresh context,
same day) found 23 issues; what changed because of it is listed at the end.

## Why this focus

- Demand. 83 player requests were collected from Reddit, the Blizzard forums, WoWInterface
  and wowlazymacros (`research/players.md` section 1). 21 were read in full, 62 from search
  excerpts; 48 date from 2024 to 2026, 28 from 2007 to 2023. The largest groups: mouseover
  casts with fallback to target or self (11 threads), "fewer buttons" requests, often from
  players with hand injuries (10), settings toggled with `/run` or `/console` (7), key
  binding setup (7), trinket plus ability (6), focus interrupt (6), Classic auto-attack and
  stance macros (6). 20 of the 83 are impossible as asked.
- A gap. No surveyed tool combines a typed request in game with a checked macro, bar
  placement, key binding and settings changes on Retail and Classic, and none explains a
  failing macro from the player's live state (`research/players.md` 3.3). General chatbots
  fail in documented ways: invented conditionals, the wrong game version, `/script` where
  none is needed, focus instead of mouseover.
- Where Gnomecaster already works: macros and settings were the parts that worked in the
  first in-game test.
- Most recurring failure causes can be read from the client: the Self Cast Key setting, a
  Shift binding that beats `[mod:shift]`, the macro icon not being the question mark, item
  names where `item:ID` works, `[flyable]` against `[advflyable]`, the 255-character limit.
  Some cannot: whether a trinket triggers the global cooldown is not exposed by any
  documented API, so that cause comes from the model's knowledge.

## What the game allows, and what it does not

| Limit | Source |
|---|---|
| A macro is at most 255 characters. Since 11.0.2 secure-button `macrotext` is held to 255 too, and a macro cannot `/click` a button that runs another macro. Macro Toolkit and Mega Macro removed their long-macro features in code; M6 still advertises long macros "with restrictions" and its code was not read. | WoWUIBugs #552 (Blizzard engineer, 2024-06-26); `research/prior-art.md` 2 |
| One action on the global cooldown per key press; no decision by cooldown, proc, buff, inventory or cast state; no loops. | Blizzard's Midnight addon posts; `research/players.md` 2.1 |
| Nothing changes in combat (macros, bars, bindings, secure settings). | Blizzard docs; current addon rule |
| 120 account and 30 character macros; 10 equipment sets; 5 Edit Mode and 5 Cooldown Manager layouts per type. | `MacroConstantsDocumentation.lua:10-11`; `Constants.lua:197`; `research/blizzard-apis.md` 5, 6 |
| Macros may set at most 3 target markers "within a very short time"; macro chat is limited during encounters (since 2026-03-01). | Blizzard forum post 2026-03-01 |
| `SetRaidTarget`, `C_Macro.RunMacroText`, `SwitchToLoadoutByName/Index` and Click Casting profile changes are restricted (`HasRestrictions = true`): only the player's own key or click through secure code runs them. | 12.1.5 API docs |
| `C_CVar.SetCVar` refuses secure console variables (`RequiresNonSecureCVar`); 20 settings in Blizzard's options panel are secure, among them Mouseover Cast (`enableMouseoverCast`). | `CVarDocumentation.lua:118-134`; `research/blizzard-apis.md` 3.a |
| WeakAuras has no Retail version for Midnight; Classic continues. | WeakAuras team via Icy Veins, 2025-10-03 |
| NPC positions are server data, not in the game's files; Wowhead's `robots.txt` blocks AI crawlers and scrapers. | wago.tools AreaPOI table, read 2026-10-17; wowhead.com/robots.txt |
| Each answer spends at least one of 20 reply slots per UI session (up to four when the ready signal does not work). | `Core.lua`, `Inbox.lua`; `docs/REVIEW.md` R4 |

Not built, by decision: macros longer than 255 characters, `/click` chains, model-written
Lua (`/run`, `/script`), anything that acts in combat or decides for the player, WeakAuras
for Retail, scraped databases.

## Design rules for every phase

- Slots are the scarce resource. Any automatic follow-up happens in the companion, which
  can ask the model again without spending a slot; the addon asks again at most once, and
  never when three or fewer slots are left. The panel shows slots left.
- Block only what is certainly wrong (a forbidden command, an invented conditional, more
  than 255 characters, a forbidden binding); warn about anything uncertain (a name the
  client cannot resolve right now). The game resolves names more loosely than a strict
  validator would: `/cast` falls back to items and `/use` to spells
  (`SlashCommands.lua:364-385`), item names need cached item data, off-spec and
  talent-replaced spells are valid in `[spec:N]` macros.
- Combat: a reply that arrives in combat is shown at once; its changes and any follow-up
  wait until combat ends and say so (the current behaviour, `Actions.lua:534-543`).
- One source for every list (commands, conditionals, settings, bindings): in the addon,
  generated from Blizzard's source where one exists, read by the companion, covered by
  the contract test. Every list carries a flavor tag (Retail, Classic flavors).
- Conditionals, modifiers and `#showtooltip` stay English in every client; spell and item
  names are in the client's language. The prompt says so.

## Phase 0: fix what 1.2.0 gets wrong, and probe (release 1.2.1)

Each fix has a test that fails without it.

1. Marks on Retail. `Actions.lua` calls `SetRaidTarget` from addon code, restricted since
   12.0. On Retail the Apply box shows a secure Mark button (`SECURE_ACTIONS.raidtarget`,
   `SecureTemplates.lua:585-606`, set up out of combat) that the player clicks; a `/tm`
   macro with a binding is offered for repeated use. Classic keeps direct marks unless the
   probe shows otherwise.
2. Settings that fail silently. Check the return of `SetCVar`, read the value back, report
   failures. Secure and missing variables are marked in the settings list the companion
   reads (Phase B generates it; until then a hand list), with `C_CVar.GetCVarInfo` at Apply
   as the backstop. Remove `nameplateShowFriends` (no longer in 12.x; the friendly nameplate
   variables are `nameplateShowFriendlyPlayers` and `nameplateShowFriendlyNpcs`). For
   `ActionButtonUseKeyDown`, `softTargetEnemy` and `softTargetInteract` (secure) the answer
   says where the option is.
3. Restriction check. `tools/wow_api.py check` also reads `HasRestrictions` and
   `RequiresNonSecureCVar` and fails on a restricted call that is not on a reviewed list;
   it must fail on today's `SetRaidTarget` call. Undocumented globals (`CreateMacro`,
   `EditMacro`, `SetBinding`, `PickupMacro`, `PlaceAction`) carry no flags, so the check
   cannot cover them; the list of those is kept by hand and says so.
4. Macro apply. If Blizzard's macro window is loaded and shown with unsaved text, close it
   before `EditMacro` (it saves its text on hide, `Blizzard_MacroUI.lua:340-348`; seen in
   wow-ai, MIT); call `CreateMacro` and `EditMacro` under `pcall`.
5. The shared-list parser. `prompt.addon_lists` reads a table up to its first `}` and only
   `= true` entries (`prompt.py:35-41`); flavor-tagged entries would silently give an empty
   list. Change the table format to one the parser and the contract test both cover, before
   any list grows.
6. README: Gnomecaster is not endorsed by Blizzard; Blizzard approves no external apps
   (`research/players.md` 4.3); the companion is used at the player's own risk.
7. Field probes for Phase A: `/gc probe` runs the automatic checks and prints one line
   each; steps that need the player (shift-click, a button click) are prompted one by one.
   It never creates or changes anything the player keeps. List under "Open questions".

## Phase A: macros (release 1.3)

Goal: a working macro in one question, in the client's language, with the player's own
spells and items, placed and bound; a plain refusal with the nearest legal alternative
when the request is impossible.

The request context for a typical question becomes macro-first: what Phase A sends replaces
the quest log as the default. Quests stay available in a slim form, and `goto` keeps working
because the addon resolves places from game data without needing them in the context.

A1. Links in the panel. Shift-clicking an item, spell, talent, mount, toy, achievement or
quest inserts its link into the Gnomecaster box when it has focus.
- Hook `hooksecurefunc(ChatFrameUtil, "InsertLink", f)` and the `ChatEdit_InsertLink`
  alias; insert only when our box has focus and no chat box is active. Pattern from Ace3
  and wow-ai; our own five lines. Call paths for each link kind: `research/blizzard-apis.md`
  1.1. Battle pets send nothing while Blizzard's macro window is shown.
- The input counts hidden link codes, displays the link, and the request carries each link
  as a reference `{"t":"item","id":219314,"name":"..."}` (`LinkUtil.ExtractLink`).
- Item data that is not cached returns nothing at first (`C_Item.RequestLoadItemDataByID`
  exists for this); the context waits briefly for it or marks the item as unknown, never as
  passive.

A2. Macro context, with its own detail ladder and caps, measured worst case in a German
client: class, spec and flavor; spells of the active spec by localized name (capped); the
linked spells and items; on-use trinkets; macro names (capped, with counts against 120 and
30); the macro named in the question (its body); the Self Cast Key, `autoSelfCast`,
`enableMouseoverCast` and `ActionButtonUseKeyDown` settings; bindings on the keys named.
Lua errors drop to a short form. A hand-built example (40 German spell names, two trinkets,
five macro names) measured 1,715 bytes; the worst case (150 macro names alone are about
2,850 bytes) does not fit, hence the caps. Compression comes in this phase: the client can
deflate (`C_EncodingUtil.CompressString`, unrestricted in the 12.1.5 docs; its
documentation file is in both Classic branches' file lists), measured 1.76 to 1.80 times
smaller on two realistic requests. That is protocol version 2, decoded by the companion
with zlib; version 1 stays readable.

A3. Checked twice, one rule set.
- Companion, before replying, with the spell and item names from A2: allowed commands,
  conditional keywords and flavor (`[advflyable]` is Retail), bracket syntax, length;
  names that do not match the context are sent back to the model with the reason, at most
  twice, costing no slot. A shortening pass fits 255 (`target=` to `@`, `modifier` to
  `mod`, spaces): Macro Toolkit's idea, our own code (its code is GPLv2; this repo has no
  licence yet).
- Addon, at Apply, against the live client: blocks only what is certainly wrong (design
  rules); unresolved names become a warning in the Apply box. Whether `CreateMacro` counts
  255 bytes or letters is a probe question; German text is where the two differ.
- If the addon still finds a hard problem, it asks again once with the exact findings,
  unless three or fewer slots are left; a second failure is shown to the player with the
  findings and nothing is saved.

A4. Edit and undo. "Fix my trap macro" sends that macro's body; the Apply box shows old
and new. `/gc undo` restores the last macro Gnomecaster changed, kept by name and body
rather than by index, since indexes can change (one level; the idea is from wow-ai, MIT,
credited).

A5. Placing it well. A free slot on a bar the player can see is chosen with
`C_ActionBar.HasAction` (not a hidden or stance-paged bar); the macro can also be put on
the cursor (`PickupMacro`) for the player to drop. Bindings keep "ask before replacing" and
warn when a modifier binding on the same key would beat the macro's `[mod:...]`. A short
deny list protects Escape and the movement keys.

A6. "Why does my macro not work?" The addon sends the live facts behind the readable causes
(Self Cast Key, `enableMouseoverCast`, conflicting modifier bindings, the macro's icon, item
name against ID, flavor); the prompt teaches those and the ones it must know itself
(trinkets on the global cooldown, `/stopmacro [channeling]` lockouts).

A7. Built-in options first, then macros, then honest refusals.
- Mouseover with fallback, the largest request group, has a built-in answer on Retail: the
  Mouseover Cast option, and Click Casting for healers. Both are secure or restricted, so
  Gnomecaster says where they are; it writes a macro when the player wants one anyway.
- Impossible requests (decide by cooldown or proc, several actions per press, loops) get one
  sentence on why and the nearest legal build: modifiers, `/castsequence` for fixed orders,
  `[spec:N]`, or Blizzard's Single-Button Assistant in a macro (its global cooldown is 25
  percent longer, which the answer says).

A8. Starter packs and housekeeping. "Set up my healer macros" produces several macros,
placed and bound in one answer (up to 12 actions per reply exist today). "Clean up my
macros" lists macros that are on no bar and the counts against 120 and 30.

A9. Commands, flavor-tagged: add `/petaggressive`, `/petmoveto`, `/leavevehicle`,
`/loadoutname`, `/loadoutindex` (Retail), `/usetalents` (Classic) and `/cqs` (short for
`/cancelqueuedspell`); all are in the game's 12.1.0 strings. Existing macros that use
localized command aliases are read correctly. `/click`, `/run`, `/script` and `/console`
stay out.

A10. Measured quality. A macro scenario set built from the 83 requests, Retail and
Classic, English and German, scored through the real companion and the real addon checks
(`tools/eval_models.py`). Release targets: at least 60 macro scenarios; the default model
passes at least 95 percent of hard checks over two runs; no macro with an invented
conditional or a forbidden command reaches Apply; every impossible request refused with an
alternative; no false block on a valid macro from the set.

## Phase B: settings and key bindings (release 1.4)

B1. Every setting in Blizzard's options panel. `tools/wow_settings.py` generates the
settings list from Blizzard's settings definitions for each patch (321 console variables;
`research/settings-cvars.tsv`) with category, label, value range or options, and flags:
secure, read-only, needs a restart, or part of a setting that changes several variables
together (85 settings drive 103 variables through Blizzard code; those are set through
the variable Blizzard's code sets, or explained). The compact list goes to the model whole
(names and short labels, estimated 2,000 to 3,000 tokens, to be measured), so no matching
of German questions to English labels is needed. Values are checked against ranges before
Apply.

B2. Key bindings for Blizzard's own commands: 342 in-game binding commands that are neither
hidden nor debug (`research/bindings.tsv`), generated from Bindings.xml, flavor-tagged. The
`bind` action takes a command or a macro. Character and account binding sets are handled
explicitly. Per-spec bindings, a counted request the default game does not offer, are
offered as a macro per spec where possible and otherwise declined with the reason.

B3. Results reported as they are: read back after `SetCVar` and `SetBinding`; say when the
game refused.

## Phase C: Blizzard's own systems (release 1.5)

Demand here was measured by guide volume and a few threads, not counted requests
(`research/players.md` 4.1), so the phase stays small.

- Equipment sets: create, save and use with `C_EquipmentSet` (no restriction flags), plus
  `/equipset` macros. Probe first.
- Talent builds, Cooldown Manager, Edit Mode, Click Casting: guidance only. Gnomecaster
  explains where each option is and how to import a string through Blizzard's own dialog,
  which already checks it. No string decoders, no `SetLayoutData`, no LibEditModeOverride
  until a player need is counted and a probe passes.
- Classic auras (WeakAuras import strings): a separate decision after Phase A.

## Order, size, ownership

Every change lands with tests that fail without it, the full check list from `CLAUDE.md`,
and a real-model evaluation when the prompt changes; roughly 300 to 800 lines each.

1. Phase 0: one change for items 1 to 6, one for the probes (7). The owner runs the probes
   and a short in-game test.
2. Before Phase A starts, one change fixes the interfaces the tracks share, in writing and
   in tests: the link reference format, the macro context shape and byte ladder, the
   protocol version 2 envelope, the findings format between companion, model and addon, the
   old-and-new reply shape, and how undo is stored.
3. Phase A as two parallel tracks, then sequential work:
   - Track 1: links, macro context, compression (`UI.lua`, `Context.lua`, `Request.lua`,
     `Beacon.lua`, `protocol.py`).
   - Track 2: the companion side of checking, shortening and re-asking (`prompt.py`, a new
     companion module, `tools/eval_*` scenarios).
   - Then, in order: addon checks at Apply and the single fix round (`Actions.lua`, a new
     Lua module); edit, undo, placement and starter packs (`Actions.lua`); the evaluation
     run. Release 1.3 after the owner's in-game test.
4. Phase B: generators and settings, then bindings. Release 1.4.
5. Phase C: equipment sets after their probe; the rest is prompt and guidance work.

## How we know it worked

- In game, after each release, one session with a fixed checklist: link an item, a spell
  and a mount into the panel; five macros from the request set; one fix of an existing
  macro; one impossible request; one setting and one binding; `/gc undo`; slots left after
  the session.
- Measured: the A10 targets on every prompt change; the transcripts of each session reviewed
  for every failed exchange.
- Product: a request from the collected set produces a macro that works on the first Apply.

## Open questions only a real client can answer

For `/gc probe` in Phase 0 (needed by Phase 0 and A):
1. Is `SetRaidTarget` blocked from addon code on Retail 12.1.5? On Classic? Does a secure
   `raidtarget` button work when clicked?
2. Does the `ChatFrameUtil.InsertLink` hook insert into the panel (shift-click prompted),
   and twice when chat is open? Does the box display the link?
3. Does `C_Spell.GetSpellIDForSpellIdentifier` resolve German spell names? Does
   `C_SpellBook.IsSpellKnown` report talent-replaced and off-spec spells as the macro
   needs?
4. Does `C_Item.GetItemInfoInstant` resolve item names that are not cached?
5. Does `CreateMacro` limit a body to 255 bytes or 255 letters?
6. Are the three secure console variables refused by `SetCVar` from addon code?
7. Does `C_EncodingUtil.CompressString` exist and work on each flavor in the TOC?
8. What does `/reload` do to loaded reply slots (R4), and does the ready signal work?

For Phase C, with that phase:
9. Does `C_EquipmentSet.CreateEquipmentSet` work from addon code?
10. Do Blizzard's action buttons accept `/click ActionButton1 LeftButton 1` on 12.1.x?
    Only relevant if `/click` is ever reconsidered.

## Changes from the first draft (review, 2026-10-17)

Adopted: the slot budget and companion-side re-asking (the first draft spent a slot on
every automatic fix); fix rounds and combat; a capped detail ladder and compression in
Phase A (the draft's single size example was not a worst case); warnings instead of blocks
for names (`/cast` and `/use` fall back to each other); probes narrowed to Phases 0 and A
and made non-destructive; the secure Mark button as the main path; flavor tags and the
shared-list parser; written interfaces before parallel tracks; settings sent whole instead
of matched, with value ranges and grouped settings; built-in options before macros
(Mouseover Cast, Click Casting); starter packs, housekeeping, slots in the panel; a smaller
Phase C; English conditionals in every client; item data loading; undo by name; visible
bars only; a binding deny list; the Single-Button Assistant's longer global cooldown.

Declined: "CLAUDE.md still says 60 slots" (it does not; checked with grep). Refusing
instead of queueing changes made in combat: queueing until combat ends is kept, because
nothing runs in combat either way and the player keeps the answer.
