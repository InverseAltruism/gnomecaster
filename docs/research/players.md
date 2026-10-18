# What players need from a macro, keybind and settings helper

Research for Gnomecaster, 2026-10-17. Scope: Retail (Midnight, live patch 12.1.5 per Icy Veins and Method guide headers seen today) and Classic flavors.

## How to read this

- Official: Blizzard news articles, patch notes, the EULA, posts by Blizzard staff. Community: everything else (Reddit, forums, wikis, addon pages, news sites). Every claim below says which.
- fetched: the page itself was read in this session. snippet: the text came from a search excerpt and the page was not opened.
- Two detail files back this report and hold the full lists:
  - `docs/research/player-requests.md`: 83 player requests with quotes, links, dates and tags, plus 20 failure modes.
  - `docs/research/competitors.md`: AI and non-AI tools with download counts, dates and sources.
- Counts in this report were recomputed from those files with grep in this session. Neither file nor this report involved running the game client.

## Key findings

1. The bulk of real requests is plain-macro work that Gnomecaster's allowlist already covers: mouseover with fallback, trinket plus ability, focus interrupt, mounts, consumables, Classic auto-attack and stance macros. Of 83 collected requests, 20 are impossible as asked (they need a decision on cooldown, proc, inventory or cast state, or several actions per press), 11 lines mention needing `/run`, 2 need `/click`.
2. The second-largest cluster is "fewer buttons" requests, often from players with hand injuries (10 threads). Most of these are impossible as asked; the useful answer is an explanation plus the nearest legal macro, or Blizzard's Single-Button Assistant.
3. Failure diagnosis is a real gap: the same handful of causes (Self Cast Key setting, a Shift+key binding beating `[mod:shift]`, mouse buttons over unit frames, trinket on the GCD, `#showtooltip` icon, 255 characters) explains most "my macro does nothing" threads, and no surveyed tool explains failures from live game state.
4. Midnight is a trust problem as much as an API one. Blizzard's stated rule is that addons "should not be able to automate combat decisions" (official). WeakAuras left Retail. Blizzard pushed players to its own Cooldown Manager, Assisted Highlight, Single-Button Assistant, Boss Warnings and Damage Meter, and players need help configuring them.
5. Hard constraint found in Gnomecaster itself: `SetRaidTarget`, which `Actions.lua` line 299 calls for the mark action, is listed as protected since patch 12.0.0 (2026-01-20) on warcraft.wiki.gg (community wiki, fetched). Players report `/run SetRaidTarget` macros broken since then. Not tested in a client; see the last section.
6. No surveyed tool combines a typed request in game with a checked macro, bar placement, key binding and setting changes on both Retail and Classic. The closest in architecture is `chelinho139/wow-ai` (Forever only); the closest on Retail is Myth MacroMKR (no free-text requests).
7. Policy: Blizzard has never approved any external companion app and says it will not. Its official texts forbid automation and unauthorized third-party software broadly; the rule players cite, "one keypress, one action", is a community paraphrase. Gnomecaster's screenshot channel sits in the same grey zone as Lyre and a 2026 chat-translator app whose author asked Blizzard directly and got no ruling.

---

## 1. What players actually struggle with

Sources mined: Reddit (r/wow, r/wownoob, r/CompetitiveWoW, r/classicwow, r/WoWMacros), Blizzard US and EU forums (UI and Macro subforum: https://us.forums.blizzard.com/en/wow/c/guides/ui-macro/35), WoWInterface, wowlazymacros.com, MMO-Champion, Wowhead forums.

Corpus (from `player-requests.md`): 83 requests; 21 fetched, 62 snippet; 48 dated 2024 to 2026, 28 dated 2007 to 2023 (labelled with their year), 7 with no visible date.

### 1.1 Examples by category

Tags: OK (plain macro commands), RUN (needs `/run` or `/script`), CLICK (needs `/click`), IMPOSSIBLE (forbidden or not expressible).

**Mouseover and targeting, including `@cursor` (13 requests)**

| Request (short quote) | Source, date | Tag |
|---|---|---|
| "allows both options depending on the target I am hovering over" (Penance) | https://www.reddit.com/r/wow/comments/1mrrkqx/anyone_know_how_to_write_mouseover_macros_that/ (2025-08-16, fetched) | OK |
| "When and only when I mouse over a party member, press F = LOH" | https://www.reddit.com/r/wow/comments/1sj28xb/is_mouseover_macro_still_a_thing_looking_for_help/ (2026-04-12, fetched) | OK |
| "cast the ground spells on the focused target by just pressing the button" | https://www.reddit.com/r/wow/comments/1n9hch9/cast_ground_spells_without_left_mouse_click_wow/ (2025-09-05, fetched) | IMPOSSIBLE at the focus (ground spells take `@cursor` or `@player` only) |
| "I cannot get the @cursor or @player macros to work at all" | https://www.reddit.com/r/wow/comments/1iuhxjy/cursor_macros/ (2025-02-21, fetched) | OK; cause is the Self Cast Key setting |
| "alt = self cast ... control = focus target (harm) damage spell" | https://www.reddit.com/r/wownoob/comments/1txw2hd/anyway_around_the_255_character_limit_for/ (2026-06-05, fetched) | OK once compressed to 206 characters |
| "the following macro does not work /target Loom'ithar" | https://us.forums.blizzard.com/en/wow/t/target-unusable/2157483 (2025-08-25, snippet) | OK with `@boss1` |

**Healer macros (6)**

| Request | Source, date | Tag |
|---|---|---|
| "cast when im hovered over a party/raid frame" | https://www.reddit.com/r/wownoob/comments/14okg5f/mouseover_macro_wow_party_frame/ (2023-07-02, fetched) | OK |
| "Left click on party member = LOH ... Middle click ... = Cleanse" | https://www.reddit.com/r/wow/comments/1sj28xb/is_mouseover_macro_still_a_thing_looking_for_help/ (2026-04-12, fetched) | IMPOSSIBLE as a macro: click casting (built-in Click Casting or Clique) |
| "mod:shift mouseover macro which casts Eternal Flame when shift is pressed" | https://www.reddit.com/r/wownoob/comments/1wa17vs/macro_help/ (2026-09-07, fetched) | OK; cause was a Shift+key binding |
| "I've hit the character limit and I don't know if there's a way to compress it" (Classic Shaman) | https://us.forums.blizzard.com/en/wow/t/a-way-to-compress-a-mouseover-macro-so-i-can-use-it-for-more-stuff/2214067 (2025-12-12, snippet) | OK at 199 characters |

**Trinket and cooldown stacking (6)**

| Request | Source, date | Tag |
|---|---|---|
| "I want to use the trinket every time I use the Ability" | https://www.reddit.com/r/wownoob/comments/1imkkrk/how_to_macro_a_trinket_to_use_before_an_ability/ (2025-02-10, fetched) | OK |
| "first check if my trinkets are off cooldown and THEN use them" | https://www.ownedcore.com/forums/world-of-warcraft/world-of-warcraft-general/wow-ui-macros-talent-specs/305966-check-if-trinket-off-cooldown-then-use.html (date not visible, snippet) | IMPOSSIBLE check; plain `/use 13` then `/cast` OK |
| "the trinkets get used but Pyroblast won't cast" | https://us.forums.blizzard.com/en/wow/t/macro-problem-pyroblast-after-trinket-use/129839 (2019-03-20, snippet) | OK without the on-GCD trinket |

**Castsequence (6)**

| Request | Source, date | Tag |
|---|---|---|
| "cast three utility buffs and it just casts the first one" | https://us.forums.blizzard.com/en/wow/t/help-with-shaman-macros/2197472 (2025-11-10, snippet) | IMPOSSIBLE in one press; OK over three presses |
| "Cast Thrash CD by CD ... mangle ... if thrash is on CD" | https://wowlazymacros.com/t/need-help-with-a-sequence/22025/1 (date not visible, snippet) | IMPOSSIBLE (priority by cooldown) |
| "I don't want to cast the same spell too quickly in succession" | https://eu.forums.blizzard.com/en/wow/t/was-castsequence-reset-changed-this-week/608323 (2026-02-26, snippet) | OK |

**Modifiers (3)**

| Request | Source, date | Tag |
|---|---|---|
| "using ctrl+alt modifier to cast on @arena3" (MoP Classic) | https://us.forums.blizzard.com/en/wow/t/macro-no-more-working-on-mop/2160851 (2025-08-30, snippet) | OK; multi-modifier clauses must come first |
| "cast Blessing on my focus ... my target (or self) if I hit any modifier key" | https://us.forums.blizzard.com/en/wow/t/conditional-macros-not-working-after-tue-patch-of-29-oct-2025/2192352 (2025-10-29, snippet) | OK; Self Cast Key again |

**Pet (3)**

| Request | Source, date | Tag |
|---|---|---|
| "work on both target and mouseover, prioritizing mouseover" (`/petattack`) | https://www.reddit.com/r/classicwow/comments/1ff3uxa/anyone_know_how_to_make_a_targetmouse_over_pet/ (2024-09-12, snippet) | OK |
| "all in one pet attack/control macro ... If you hold shift it will cast dash" | https://us.forums.blizzard.com/en/wow/t/pet-attack-macro/337354 (2019-10-19, snippet) | OK; the longer variant used CLICK, dead since 11.0 |

**Mounts (3)**

| Request | Source, date | Tag |
|---|---|---|
| "my flying mount and ground mount on the same button ... It only ever summons my flying mount" | https://www.reddit.com/r/wow/comments/1qxfxdf/macro_for_flying_and_ground_mounts/ (2026-02-06, fetched) | OK (`[flyable]`, `[advflyable]`) |
| "function like the official favorite mount spell" | https://www.reddit.com/r/wow/comments/1dv32sw/please_teach_me_how_to_write_a_macro_that/ (2024-07-04, fetched) | OK with `/userandom`; the real Summon Random Favorite Mount needs CLICK or RUN |

**Toys, items, consumables (5)**

| Request | Source, date | Tag |
|---|---|---|
| "a health stone, and then if needed, a heath pot moments later with the same button" | https://us.forums.blizzard.com/en/wow/t/heath-pothealth-stone-single-button-macro-needed/2049033 (2025-01-22, snippet) | OK |
| "use HS if exists, or not on cd, else use pot" | https://www.reddit.com/r/wow/comments/10xvtci/healthston_or_healing_potion_1_button_macro/ (2023-02-09, snippet) | IMPOSSIBLE (inventory and cooldown decision) |
| "a macro to use a random hearthstone from my collection" | https://www.reddit.com/r/wow/comments/1uyhobh/is_there_a_addon_or_macro_to_use_a_random/ (2026-07-16, fetched) | OK with `/castrandom`; top reply used RUN |

**Focus and interrupt (5)**

| Request | Source, date | Tag |
|---|---|---|
| "use my counterspell without having to manually select the target" | https://www.reddit.com/r/wow/comments/1g7tpoo/intrerupt_macro/ (2024-10-20, snippet) | OK |
| "put a mob on focus and stick an icon on top of it" | https://www.reddit.com/r/CompetitiveWoW/comments/1s446qb/kick_target_macro_broken_since_midnight/ (2026-03-26, fetched; 67 points, 43 comments) | OK, but hit by Midnight's marker rate limit |
| "automatic target the mob who is casting" | https://www.reddit.com/r/CompetitiveWoW/comments/ufazdo/share_a_good_automatic_target_interrupt_macro/ (2022-04-30, snippet) | IMPOSSIBLE (no cast-state targeting) |

**Stopcasting (3)**

| Request | Source, date | Tag |
|---|---|---|
| "stop casting whatever and instantly hit cs" | https://www.reddit.com/r/classicwow/comments/1iieh2r/counterspell_cancel_cast_macro/ (2025-02-05, snippet) | OK |
| "stopcasting only if casting anything other than Pyroblast" | https://www.wowinterface.com/forums/showthread.php?t=43794 (2012-07-28, snippet) | IMPOSSIBLE |

**Equipment sets (3)**

| Request | Source, date | Tag |
|---|---|---|
| "change gear AND talents with one click" | https://www.wowinterface.com/forums/showthread.php?t=56056 (2018-02-20, snippet) | Gear OK (`/equipset`); Retail spec swap RUN |
| "work for the first 5 minutes-1 month, then just stops doing anything" (`#equipslot`) | https://www.reddit.com/r/wownoob/comments/1w3my7k/whats_wrong_with_my_macro/ (2026-08-31, fetched) | OK with `/equipset` |

**UI toggles that need `/run` or `/console` (7)**

| Request | Source, date | Tag |
|---|---|---|
| "when I enable friendly nameplates ... all enemy nameplates automatically toggle off" | https://eu.forums.blizzard.com/en/wow/t/nameplate-toggle-macro-help/523132 (2024-07-15, snippet) | RUN; IMPOSSIBLE in combat |
| "a macro ... to sell the gray objects ... Without the need for addons" | https://www.reddit.com/r/wownoob/comments/1by8p7x/macro_to_sell_greys/ (2024-04-07, fetched) | RUN |
| "my macro to teleport to my house does not work anymore" ("blocked because of an action that is usable only by the blizzard UI") | https://www.reddit.com/r/wownoob/comments/1qq5cj5/previous_macros_broken_with_120/ (2026-01-29, fetched) | RUN, protected since 12.0 |
| "It resets on logout, so make it a macro" (camera zoom `/console`) | https://www.reddit.com/r/classicwow/comments/16jkpam/reminder_you_can_use_a_macro_to_increase_your/ (2023-09-15, snippet) | `/console`; Gnomecaster covers it as a setting |

**Keybind questions (7)**

| Request | Source, date | Tag |
|---|---|---|
| "I would like different keybindings for each spec ... I've tried mods-they don't work" | https://us.forums.blizzard.com/en/wow/t/keybinding-changes-affecting-multiple-specs-why/1983189 (2024-10-12, snippet) | Not in the default UI; addons rebind on spec change |
| "binding my main rotation to the thumb buttons" | https://www.reddit.com/r/wownoob/comments/1aleu10/mmo_mouse_keybinds/ (2024-02-07, fetched) | OK |
| "make them my account-wide keybinds" | https://us.forums.blizzard.com/en/wow/t/turn-character-specific-keybinds-into-account-wide-keybinds/1772164 (2024-01-22, snippet) | Doable by re-applying bindings |
| Shadowstep mouseover "works unless cursor is above a party frame" | https://www.reddit.com/r/wow/comments/1gqt70s/mouseover_macro_not_working_on_partyraid_frames/ (2024-11-14, snippet) | IMPOSSIBLE on a mouse button; unit frames eat the click |

**Classic-specific (6)**

| Request | Source, date | Tag |
|---|---|---|
| "turn auto shot on, and if I press the button again it doesn't turn auto shot off" | https://us.forums.blizzard.com/en/wow/t/hunter-auto-shot-macro-help-wow-classic/187106 (2019-05-30, snippet) | OK |
| "I need to hit the macro at least twice" (`/stopattack`, `/startattack`) | https://eu.forums.blizzard.com/en/wow/t/classic-1x-stopattack-not-working-when-its-in-the-line-above-startattack/552739 (2024-12-09, snippet) | Partly OK |
| "Revenge if available or overpower if available" | https://us.forums.blizzard.com/en/wow/t/classic-revenge-overpower-macro/467177 (2020-03-11, snippet) | IMPOSSIBLE by proc; OK by stance |

**One-button rotation and GSE-style automation (7)**

| Request | Source, date | Tag |
|---|---|---|
| "turn the sequence on with F1 and it loops it until I hit F1 again" | https://www.reddit.com/r/wow/comments/1iwd7ms/help_with_macros/ (2025-02-23, snippet) | IMPOSSIBLE |
| "Am I allowed to use autohotkey to spam one-button-rotation?" | https://us.forums.blizzard.com/en/wow/t/am-i-allowed-to-use-autohotkey-to-spam-one-button-rotation/2312526 (2026-06-03, snippet) | IMPOSSIBLE (external automation) |
| "I have arthritis and need macros to lower the number of buttons I use" | https://us.forums.blizzard.com/en/wow/t/gsegnomesquencer/2056920 (2025-02-07, snippet) | OK within one action per press |
| "a one-button macro to avoid tendonitis ... wrath hammers as soon as they become available" | https://wowlazymacros.com/t/i-need-help-with-the-order-of-the-sequences/44254 (2024-08-28, snippet) | IMPOSSIBLE (react to availability) |

That is 46 examples here; the other 37 are in `player-requests.md`.

### 1.2 Most frequent request types

Ranked by distinct threads in the corpus (a collected sample, not a census):

1. Mouseover cast with fallback to target or self: 11.
2. One-button or fewer-buttons rotation, often for injuries: 10.
3. Script-only UI toggles (nameplates, names, sell greys, action targeting, camera, housing): 7.
4. Keybind setup (mouse side buttons, per-spec binds, account vs character): 7.
5. Trinket plus ability: 6. Focus interrupt and focus plus marker: 6. Classic auto-attack, wand, auto shot, stance: 6.
6. Healthstone then potion, random hearthstone: 5.

### 1.3 Failure modes players report

All with sources in `player-requests.md` (F1 to F20). The ones that recur:

- 255-character limit, with no addon workaround since 11.0. The pinned UI and Macro guide (community author Adreaver, last changelog entry 2024-09-24, fetched) says: "There were previously ways around this limit with add-ons, or by chaining macros together with `/click`, but those have been eliminated in 11.0". https://us.forums.blizzard.com/en/wow/t/macros-essential-information/21139. Players keep petitioning for more: "Increase macro character limit to 1000 or 2x current" https://us.forums.blizzard.com/en/wow/t/petition-to-create-shorthand-macro-options-going-into-midnight/2185802 (2025-10-16, fetched; no Blizzard reply).
- `/click` from a macro that runs another macro is blocked since 11.0.2 (warcraft.wiki.gg, community).
- Self Cast Key setting breaks `@unit` and `@cursor` macros with modifiers (threads 2024-03-16 and 2025-10-30).
- A Shift+key binding takes priority over `[mod:shift]` in a macro on the unmodified key (2026-09-07, fetched).
- Mouse-button bindings do nothing over unit frames.
- Trinket on the GCD or on cooldown stops the following spell.
- `#showtooltip` icons only update when the macro icon is the question mark.
- Items by name fail where `item:ID` works.
- `/stopmacro [channeling]` locking casts for seconds after a channel: https://us.forums.blizzard.com/en/wow/t/nochanelling-and-stopmacro-when-channeling-broken/2234111 (opened 2026-01-22, replies to 2026-04-12, fetched; no Blizzard reply; workaround `[nochanneling]` on the `/cast` line).
- Midnight marker and chat limits (section 2).

### 1.4 What needs `/run` or `/click`, and what no addon can do

- `/run` is what players reach for to toggle CVars, sell greys, summon the real random favorite mount, use a random toy, or chain spec and gear swaps. Gnomecaster's setting action covers the CVar cases out of combat without `/run`. Several `/run` calls became protected in 12.0 (housing teleport, `SetRaidTarget`) and API renames broke others (crafting order macro, MMO-Champion, snippet).
- `/click` chaining is dead on Retail since 11.0.
- Impossible for any macro or addon, by design: choosing an action from cooldown, proc, buff, inventory or cast state; more than one GCD action per press; looping or auto-repeat; ground spells at a unit; acting in combat for the player. Official basis: Blizzard says addons "will no longer be able to use that combat information to drive custom logic or make decisions for you" (section 2). Community basis: the pinned guide's "Macros cannot simulate additional keypresses. One keypress = one action." and "Macros cannot make smart decisions for you."

---

## 2. Midnight 12.x changes that affect macros, keybinds, settings and addons

Dates: pre-patch 12.0.0 went live 2026-01-20 (US) and 2026-01-21 (EU) per Icy Veins (snippet) and warcraft.wiki.gg (fetched: "Patch 12.0.0 (2026-01-20)"). Midnight launch: 2026-03-02 per Blizzard Watch, 2026-03-03 per Notebookcheck (both snippet; likely a regional difference, not verified).

### 2.1 Official (Blizzard)

| What | Key text | Source, date |
|---|---|---|
| Addon goal | "Addons should not be able to automate combat decisions for the player." "If the UI displays a piece of combat information, addons will, in most cases, be able to present that information to you in a different way. However, addons will no longer be able to use that combat information to drive custom logic or make decisions for you." | https://news.blizzard.com/en-us/article/24244638/how-midnights-upcoming-game-changes-will-impact-combat-addons (fetched; no date on the page; written "as we approach the end of the first month of our Midnight alpha") |
| Secret values | Combat state is "a secret value that can be displayed by addons, but not known by them". Native replacements: Assisted Highlight and One-Button Rotation (11.1.7), Cooldown Manager (11.1.5, "much-refined" in Midnight), Boss Warnings, Combat Audio Alerts, Damage Meter, raid frame improvements. | https://news.blizzard.com/en-us/article/24246290/combat-philosophy-and-addon-disarmament-in-midnight (Ion Hazzikostas, fetched; no date on the page; written at the start of beta) |
| Restrictions scoped to encounters | "we're going to make changes to only apply the new logic while there is an active raid encounter or M+ run underway" (chat and addon comms) | Blizzard statement quoted by Icy Veins, https://www.icy-veins.com/wow/news/combat-addon-restrictions-eased-in-midnight/ (2025-10-03, fetched) |
| API loosening list | Whitelisted spells (Skyriding, GCD spell, Maelstrom Weapon, combat res), secret boolean to colour APIs, non-secret cast sequence ID, `SecondsFormatter`; "we DO plan to have these new addon restrictions active in pre-patch (12.0.0)" | Blizzard post from the WoW UI Dev Discord quoted by Icy Veins, https://www.icy-veins.com/wow/news/blizzard-relaxing-more-addon-limitations-in-midnight/ (2025-12-17, fetched) |
| Macro limits | "Macros are prevented from setting a target marker on more than 3 units within a very short time." During an active encounter: no macro chat to non-group channels; group chat and whispers rate-limited; recipients must be in the instance. | https://us.forums.blizzard.com/en/wow/t/macro-changes-now-live-target-markers-and-chat-messages/2261956 (2026-03-01, fetched); MMO-Champion labels it "Originally Posted by Blizzard (Blue Tracker / Official Forums)", https://www.mmo-champion.com/content/14060-Midnight-Macro-Changes-Now-Live-Target-Markers-and-Chat-Messages (2026-03-01, fetched) |
| Cooldown Manager in pre-patch notes | "Players can now save multiple layouts as well as share or import other player layouts." "Up to 3 alerts can be assigned to a cooldown." "Text-to-Speech is available as an option for Sound Alerts." Target debuffs and pandemic indicators added. | Midnight Pre-Expansion Content Update Notes, mirrored at https://www.bluetracker.gg/wow/topic/us-en/24244455-midnight-pre-expansion-content-update-notes/ (2026-01-21, fetched). I read all four 100,000-character windows of the page with a targeted prompt; no bullet mentioned macros, key bindings or Assisted Combat. |
| Single-Button Assistant | Added 2025-06-17 in 11.1.7; "The global cooldown of abilities used through the Single-Button Assistant is 25% longer." | warcraft.wiki.gg (community wiki), https://warcraft.wiki.gg/wiki/Single-Button_Assistant (fetched); official launch post listed in `competitors.md` (snippet) |
| Third-party software | "The use of third-party software that modifies the World of Warcraft game client is against our Terms of Service." | Kaivax, https://us.forums.blizzard.com/en/wow/t/prohibitions-on-third-party-software/2142972 (2025-08-05, snippet; EU copy fetched). Kaivax is a Blizzard community manager; the staff badge was not visible in the fetched text. |

### 2.2 Community-documented (wikis, addon authors, players)

- `SetRaidTarget`: "Patch 12.0.0 (2026-01-20): Protected." The page says it "can only be called from secure code" and "should be usable via" SecureActionButtonTemplate. https://warcraft.wiki.gg/wiki/API_SetRaidTarget (fetched). Players confirm: "/run ... SetRaidTarget("target", 8)" stopped working while `/tm` still works, https://us.forums.blizzard.com/en/wow/t/setraidtarget-macros-broken/2233486 (2026-01-22 to 2026-04-17, fetched; no Blizzard reply).
- Marker rate limit misfiring: "if you mark too much you get rate limited for like 30 minutes" and "/tm x doesn't work at all for me anymore", https://www.reddit.com/r/CompetitiveWoW/comments/1s446qb/kick_target_macro_broken_since_midnight/ (2026-03-26, fetched).
- 12.0.0 API changes: `C_RestrictedActions` and `ADDON_RESTRICTION_STATE_CHANGED` added, `COMBAT_LOG_EVENT_UNFILTERED` errors on register, 137 CVars added and 153 removed, `C_ActionBar` namespace replaces global action functions; nothing on slash commands or macro conditionals in the part read (the first 100,000 of 186,297 characters). https://warcraft.wiki.gg/wiki/Patch_12.0.0/API_changes (fetched).
- "Load out of date AddOns" removed: an addon whose TOC lacks the current interface number does not load (forum threads 2025-11-05 and 2026-01-18, snippet; GRIP changelog). Details in `competitors.md`.
- Plain macro conditionals: no source found saying Midnight changed `/cast` conditionals or `/castsequence`; a 12.0 beta tester reports `[nochanneling]` and `@mouseover` working (https://us.forums.blizzard.com/en/wow/t/balance-druid-macros-working-1125120-beta/2199491, 2025-11-14, snippet).
- WeakAuras: "As it stands, we do not expect to release a WeakAuras version for Midnight." Classic stays. https://www.icy-veins.com/wow/news/weakauras-to-end-support-in-midnight/ (2025-10-03, fetched). Their follow-up: "it's impractical to replicate the functionality of the builtin Cooldown Manager with an addon", https://www.icy-veins.com/wow/news/weakauras-responds-to-addon-limitation-loosening-in-midnight/ (2025-11-28, fetched).
- GSE needed a Midnight rewrite; GSE 3.2 stopped at the pre-patch and old sequences must be converted (Patreon 2026-01-12 and wowlazymacros, snippet).
- Classic flavors: no source states that secret values apply to Classic Era, MoP Classic or Forever; WeakAuras Classic continues. Retail-only scope is my inference.

### 2.3 APIs for Blizzard's configurable systems (community wiki, not tested)

| System | API seen | Restriction listed |
|---|---|---|
| Cooldown Manager layouts | `C_CooldownViewer.GetLayoutData()` returns a string; `C_CooldownViewer.SetLayoutData(data)` takes one; added 11.2.5 / 5.5.3 / 1.15.8 | `AllowedWhenUntainted` (snippet: https://warcraft.wiki.gg/wiki/API_C_CooldownViewer.SetLayoutData) |
| Talent loadouts | `C_ClassTalents.LoadConfig(configID, autoApply)` | `AllowedWhenUntainted`, `SecretArguments` (fetched: https://warcraft.wiki.gg/wiki/API_C_ClassTalents.LoadConfig) |
| Edit Mode | `C_EditMode.SetActiveLayout(activeLayout)` | none shown (fetched) |
| Equipment sets | `C_EquipmentSet.UseEquipmentSet(id)` | "#nocombat", "does not produce error messages when it fails" (fetched) |
| Macros and bars | `CreateMacro` (body over 255 characters is truncated; 120 account and 18 character macros), `EditMacro`, `PickupMacro` ("#nocombat", restricted since 2.2) | fetched. The `EditMacro` page gives character indexes 121 to 150, which conflicts with 18; unresolved. |
| Bindings | `SetBinding` needs `SaveBindings()` or bindings reset on next login | fetched |
| Settings | `C_CVar.SetCVar` "Returns nil if attempting to set a secure cvar in combat"; "Secure CVars cannot be set in combat and only with SetCVar instead of /console" | fetched |

What `AllowedWhenUntainted` means for an addon caller on 12.x is not explained on these pages; whether Gnomecaster can call `SetLayoutData` or `LoadConfig` is unverified until tried in a client.

---

## 3. Competitors and alternatives

Full tables with download counts and sources: `competitors.md`. I re-fetched the two most important entries (wow-ai on GitHub, MacroMKR on CurseForge) and the figures matched.

### 3.1 AI tools

| Tool | What it does | In game | Versions | Price | Usage |
|---|---|---|---|---|---|
| wow-ai / "AI Agents Chat" | Chat with local coding agents (Claude Code, Codex, Grok Build, Antigravity, Hermes) from the game; world-map routes; "Create macro" button with undo. Pixel strip captured four times a second, 200 load-on-demand reply slots, empty-vs-valid `.wav` ready signal. | Yes | Forever only | MIT, free; needs the agent's own subscription | 147 stars, 34 forks, created 2026-09-23 (fetched); CurseForge 33 downloads (agent, fetched) |
| Myth MacroMKR | Spec-aware macro builder, macro audit (over 255, missing target guards, mash-breaking `/castsequence`), keybind advice, talent loadout switching per activity; desktop app with unnamed "AI features" on combat logs and one-click macro fixes | Yes (addon); no free-text requests | Retail 12.0.5 to 12.1.5 | free | 1,462 downloads, updated 2026-10-16 (fetched) |
| WoWGPT | In-game chat with built-in agents; optional LLM bridge; no macro creation | Yes | Retail and four Classic flavors | free | 621 downloads (agent, fetched) |
| Azeroth Companion | In-game LLM chat, round trip per `/reload` | Yes | WotLK 3.3.5a first, Retail with caveats | MIT, free | 1 star (agent, fetched) |
| MacroCrafter | Web macro generator, "spec-aware"; says a free addon and companion app are planned | No | Retail (Midnight), FFXIV | 39.93, 77.93, 129.93 per year (currency not named) | none visible (agent, fetched) |
| EZMacro | Web generator; claims validation of 255 characters, spell names, one GCD per press | No | Retail and Classic flavors | free, ads | top macros copied 126 to 184 times (agent, fetched) |
| Custom GPTs | Five found; most-used shows 4.2 stars from 15 reviews, "Over 1K Conversations" | No | varies | ChatGPT account | (agent, fetched or snippet) |

Player reports on general chatbots writing macros:
- Invented conditionals ("nodebuff is not a thing in WoW macros"), https://www.reddit.com/r/WoWMacros/comments/16vcdaj/i_asked_chatgpt_to_wright_me_a_macro/ (2023-09-29, snippet).
- "Asked for mouse over macros and it went with focus. I didn't realize until I was in the dungeon", https://www.reddit.com/r/classicwow/comments/1b2yk6z/you_can_use_chat_gpt_to_write_macros/ (2024-02-29 per Exa, snippet; 387 points, 81 comments in the excerpt).
- GSE author: "Anything you create with CharGPT will be lacklustre", https://wowlazymacros.com/t/need-help-converting-a-macro-i-made/39079 (2024-01-12, snippet).
- Outdated API knowledge: "it only knows pre-dragonflight API definitions", https://us.forums.blizzard.com/en/wow/t/using-chatgpt-or-perplexity-to-help-write-addons/1880836 (2024-06-22, snippet).
- Defaulting to `/script` (a `Minimap:SetZoom` macro), https://eu.forums.blizzard.com/en/wow/t/chatgpt-for-wow-macros-and-addons/424108 (2023-01-19, fetched).
- Positive reports exist too: "Every macro ive tried so far has worked", https://www.reddit.com/r/wowhardcore/comments/1u76icl/pro_tip_ai_is_very_good_at_writing_macros_simply/ (2026-06-16, snippet).

### 3.2 Non-AI helpers (CurseForge downloads, fetched by the track 3 agent)

Bartender4 81,926,490; Dominos 22,817,294; Clique 20,472,772; OPie 12,244,552; GSE 10,166,609; ConsolePort 4,240,068; Macro Toolkit 3,233,185; BindPad 820,214 (last update 2026-02-17, nothing listed for 12.1.x). Midnight Helper (not AI) puts spells on bars 5 to 7 with undo and coaches keybinds; its site claims 17,700 downloads while the CurseForge copy fetched showed 11,111.

Guides: Wowhead, Icy Veins and Method publish per-spec macro pages and Cooldown Manager and UI import strings for 12.1.x (snippet). Blizzard's own tools: Quick Keybind Mode, Edit Mode (layout share and import), Cooldown Manager (12.1 adds trinkets, potions, racials), Assisted Highlight and Single-Button Assistant, talent loadout strings.

### 3.3 Gaps

- No surveyed tool does all of: typed request in game, validated macro, bar placement, key binding with a warning before replacing a binding, CVar changes, on both Retail and Classic.
- None states that it refuses `/run`, `/script` or `/click`.
- None explains a failure from live state (spell not known, wrong flavor, protected call, Self Cast Key, a conflicting Shift binding).
- None explains Lua errors (error-display addons such as BugSack were not surveyed).

---

## 4. What would make players choose an in-game AI helper

### 4.1 Demand signals

- Players already use chatbots for macros and like the speed ("I use chatgpt for everything wow", r/classicwow 2024-02-29, snippet), but the failures above are the reason to want a tool grounded in the player's own spellbook, flavor and settings.
- Accessibility is a recurring motive: arthritis, tendonitis and wrist injuries in the "fewer buttons" threads; a disabled r/wow poster testing the default UI before Midnight: "a lot of the new Blizzard UI elements are no where near anywhere as functional as the addons that they're designed to replace", https://www.reddit.com/r/wow/comments/1oh8e5s/is_the_cooldown_manager_partially_nonfunctional/ (2025-11-17 per Exa, snippet). Deaf players rely on macro raid callouts hit by the 2026-03-01 limits (replies in the Blizzard thread, fetched).
- Blizzard's own systems need setup help. Wowhead, Blizzard Watch, Method and others published Cooldown Manager setup guides for 12.x; Blizzard Watch: the settings button is "way too hidden inside two menus" (2026-01-16, snippet). Help threads: "Cooldown Manager not showing personal cooldowns" (r/wownoob, snippet), "Cooldown Manager updates for Midnight?" (r/wow 2025-10-31, snippet). I did not count these threads the way section 1 counts macro requests, so the demand here rests on guide volume and a few threads.

### 4.2 Concerns players raise

- "Is it cheating?" Community consensus: what runs entirely inside the addon sandbox is fine; anything outside it is risky. "Anything that runs entirely in the blizzard defined and provided addon sandbox is fine" (Blizzard forum, 2025-08-05, snippet); same view on r/CompetitiveWoW about overlays, https://www.reddit.com/r/CompetitiveWoW/comments/1sdeg8z/overlays/ (2026-04-05, snippet).
- AI that presses keys is rejected outright: Wingman-AI "is against ToS" (community, https://eu.forums.blizzard.com/en/wow/t/illegal-3rd-party-software-or-legal-tool/589002, 2025-09-16, snippet); "Anything that breaks the rule of 1 hardware action ... = 1 in-game action on 1 client is a violation" (community, https://us.forums.blizzard.com/en/wow/t/advanced-ai-vs-wow/2320186, 2026-06-24, snippet), while "If the ai does some sort of visual promp on what spell to do next and the player has to do it that would not be agaist the rules" (same thread, a player).
- Screen-reading companions: a developer asked Blizzard on 2026-09-30 whether an addon that paints chat as coloured squares, read by a Windows app, is allowed under EULA 1.C.vi. Replies: "Blizzard doesn't give any sort of approval for any external apps" and pixel scanning "will almost certainly trigger Warden" (both players; the Warden claim is unverified). Vrakthris answered only with a link to the developer portal. https://us.forums.blizzard.com/en/wow/t/policy-question-is-a-chat-translation-companion-app-allowed/2367458 (fetched).
- Code quality: AI-written addons "kept trying to use APIs that don't exist anymore" (r/wowaddons, 2026-03-03, snippet); taint and performance worries (r/wowaddons, 2026-04-08, snippet).
- Paying: on an AI addon generator, "Was curious til I had to pay. Hard pass." (r/wowaddons, 2026-03-03, snippet). Blizzard's addon policy also forbids charging for an addon (below).

### 4.3 Blizzard's stated policy (official texts)

- EULA, last revised 2024-03-21 (fetched, https://www.blizzard.com/en-us/legal/fba4d00f-c7e4-4883-b8b9-1b4500a402ea/blizzard-end-user-license-agreement):
  - Cheating: "any code and/or software, not expressly authorized by Blizzard, that can be used in connection with the Platform ... which changes and/or facilitates the gameplay or other functionality".
  - Bots: "any code and/or software, not expressly authorized by Blizzard, that allows the automated control of a Game".
  - Data mining, 1.C.vi: "Use any unauthorized process or software that intercepts, collects, reads, or “mines” information" generated by or stored in the Platform.
  - Section 4: Blizzard "MAY MONITOR YOUR COMPUTER ... MEMORY FOR UNAUTHORIZED THIRD PARTY PROGRAMS".
  - Add-ons are not mentioned by name.
- UI Add-On Development Policy (text from 2009, reposted by Kaivax 2018-11-19, fetched, https://us.forums.blizzard.com/en/wow/t/ui-add-on-development-policy/24534): add-ons must be free; code must not be "hidden or obfuscated"; must not harm realms or players (for example "excessive use of the chat system"); no ads, no in-game donation requests; must follow the EULA and Terms of Use; Blizzard may disable any add-on functionality. Nothing about talking to external programs.
- Third-party software (Kaivax, 2025-08-05): modifying the client is against the ToS and Blizzard takes action "up to and including the permanent closure" (snippet of the US post; EU copy fetched).
- Customer support (Vrakthris, 2026-06-18): "botting/automation has been and will continue to be against policy. If such behavior is verified it can mean a suspension or permanent closure of an account." https://us.forums.blizzard.com/en/wow/t/ai-built-scripts-addons-and-programs/2317420 (snippet). Staff status is my inference from "our Community Team" in the same post.
- Input broadcasting (official, 2020-11-03, quoted in forum threads, snippet): prohibits "all software and hardware mechanisms to mirror commands to multiple World of Warcraft accounts ... or to automate or streamline multi-boxing in any way".
- "One keypress, one action": I found no official Blizzard sentence with this wording. It appears in the community-written pinned macro guide and in many player replies.

---

## Implications for Gnomecaster

### Ranked capabilities by evidence of demand

1. Mouseover, focus and fallback-targeting macros, written for the player's actual spells and flavor. The largest category (13 requests, 11 threads of the top type, plus 5 focus and interrupt and 6 healer). All plain-macro and inside the current `MACRO_COMMANDS`. The demand is mostly for getting conditional order right (`[@mouseover,help,nodead][@target][@player]`, multi-modifier clauses first) and for staying under 255 characters, where model output must be checked by length and compressed.
2. Explaining why a macro or binding does not work, from live state. 20 recurring failure modes; no competitor does it live. The highest-value checks: Self Cast Key setting, a Shift/Ctrl/Alt binding on the same key, mouse-button binds over unit frames, an on-GCD trinket before a spell, the macro icon not being the question mark, name vs `item:ID`, `[flyable]` vs `[advflyable]`, `/stopmacro [channeling]` lockout.
3. "Fewer buttons" help with honest refusals. 10 threads, mostly impossible as asked. The product should say plainly what a macro cannot do (no cooldown or proc logic, one GCD action per press, no loops), then offer the nearest legal build: modifiers, `/castsequence` for fixed orders, `[spec:N]` macros, or the Single-Button Assistant wrapped as `/cast [nochanneling] Single-Button Assistant` (community macro, 2026-06-15). This also matches the evidence that AI chatbots fail by promising logic macros cannot run.
4. Key bindings with conflict checks. 7 threads; requests include mouse side buttons, per-spec binds (not supported by the default UI), and copying a character's binds to the account set. Bindings need `SaveBindings()`, cannot change in combat, and the existing "ask before replacing a binding" rule matches the Shift-key failure mode.
5. Settings that players now script with `/run` or `/console`. 7 threads; the allowlist covers nameplates, camera zoom and soft targeting. Requested but not allowed today: `UnitNameNPC`, `UnitNameFriendlyPlayerName`, `stopAutoAttackOnTargetChange`, `SpellQueueWindow`, `NameplatePersonalShowAlways`. I am not recommending `/console` in macros: it would let model text set any CVar and bypass `CVAR_ALLOW`.
6. Trinket, consumable, mount, pet and Classic auto-attack macros. 6 + 5 + 3 + 3 + 6 requests, all plain-macro. Commands seen in requests but missing from the allowlist: `/petaggressive`, `/petmoveto`, `/leavevehicle`, `/usetalents` (Classic dual spec), and the `/cqs` short form. These are plain secure commands; whether to add them is a separate decision.
7. Blizzard's configurable systems: Cooldown Manager setup, Edit Mode layouts, talent loadouts, equipment sets. Demand is real, but I measured it by guide volume and a few threads, not by counted requests. The APIs exist (`C_CooldownViewer.SetLayoutData`, `C_ClassTalents.LoadConfig`, `C_EditMode.SetActiveLayout`, `C_EquipmentSet.UseEquipmentSet`), but whether an addon can call them on 12.x is unverified. The safe first step is to explain where each option lives (the Advanced Cooldown Settings button is hard to find) and to build `/equipset` macros. Applying layout strings needs a client test first.
8. Lower priority by evidence: macro sharing and library features (already well served by Macro Toolkit, MacroIDE, Wowhead and Icy Veins), and rotation advice (Blizzard's Assisted Highlight covers it, and recommending combat decisions is what Blizzard is shutting down).

### Hard constraints

- No combat automation, by design and by policy. The helper may write a macro, bind a key or change a setting out of combat; it must never decide or act during combat. Official basis: the Midnight addon posts and the EULA bot clause. In-combat requests should be refused with the reason, not queued to fire later.
- One macro line is one action per press; no cooldown, proc, buff, inventory or cast-state logic; no `/click` chains (blocked since 11.0); 255 characters per macro body (`CreateMacro` truncates silently); 120 account and 18 character macro slots (the `EditMacro` page says 121 to 150 for character macros; resolve in a client).
- Protected calls on Retail 12.x. `SetRaidTarget` is listed as protected since 12.0.0, and Gnomecaster's mark action calls it directly from addon code (`addon/Gnomecaster/Actions.lua:299`). On Retail this most likely fails with an "action blocked" error. That is my inference from the wiki and player reports; nothing here can run the client. Options: on Retail, offer a `/tm` macro or a binding instead of marking directly, keep direct marks on Classic flavors, and teach `tools/wow_api.py` to flag functions whose wiki page says protected or restricted. `PickupMacro` and `UseEquipmentSet` are `#nocombat`; secure CVars refuse `SetCVar` in combat.
- Macro marker and chat limits since 2026-03-01: more than 3 markers "within a very short time" is blocked, and players report long lockouts. A generated macro that marks several units, or that sends chat during an encounter, will misfire. Keep `/tm` and `/wm` macros to one marker per press.
- TOC interface numbers must match each live client, since Midnight removed "Load out of date AddOns". Today's TOC lists `120105, 120100, 50504, 20506, 11509, 16001` (read 2026-10-17); Wrath Titan Reforged (38001) is not listed.
- Classic differs: `/run` still works there, `SetRaidTarget` is not listed as protected for Classic in what I read, `[advflyable]` and skyriding do not exist, and players report `#showtooltip` regressions. The model must know which flavor it is writing for; wrong-flavor output is one of the reported chatbot failures.
- Policy exposure of the companion. Blizzard approves no external apps, and EULA 1.C.vi on software that "reads" game information is broad enough to cover a screenshot channel. Mitigations that fit the official texts: do everything in game through the addon API; never send input to the game; keep the addon free, unobfuscated and without ads or donation prompts (Add-On Policy); and say plainly in the README and UI that the companion is unendorsed and used at the player's own risk. Do not claim it is "allowed" or "ToS compliant": no Blizzard source says so (Lyre's page makes that claim on its own authority). Gnomecaster reads the screenshot files the game writes rather than capturing the live screen. That may matter, but nothing official says it does.
- Prior art: wow-ai (MIT) uses the same three-part transport (pixel message, pre-made load-on-demand reply slots, a file-validity ready signal). If any idea is taken from it, credit it in the docs.

### Sources most worth keeping

- https://news.blizzard.com/en-us/article/24244638/how-midnights-upcoming-game-changes-will-impact-combat-addons
- https://news.blizzard.com/en-us/article/24246290/combat-philosophy-and-addon-disarmament-in-midnight
- https://us.forums.blizzard.com/en/wow/t/macro-changes-now-live-target-markers-and-chat-messages/2261956
- https://warcraft.wiki.gg/wiki/API_SetRaidTarget
- https://www.icy-veins.com/wow/news/blizzard-relaxing-more-addon-limitations-in-midnight/
- https://www.blizzard.com/en-us/legal/fba4d00f-c7e4-4883-b8b9-1b4500a402ea/blizzard-end-user-license-agreement
- https://us.forums.blizzard.com/en/wow/t/ui-add-on-development-policy/24534
- https://us.forums.blizzard.com/en/wow/t/policy-question-is-a-chat-translation-companion-app-allowed/2367458
- https://us.forums.blizzard.com/en/wow/t/macros-essential-information/21139
- https://github.com/chelinho139/wow-ai
- https://www.curseforge.com/wow/addons/myth-macromkr
