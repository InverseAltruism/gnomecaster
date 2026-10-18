# Track 1: what players actually ask for (macros, keybinds, settings)

Collected 2026-10-17. Sources: Reddit (r/wow, r/wownoob, r/CompetitiveWoW, r/classicwow, r/WoWMacros, r/Corsair), Blizzard US and EU forums (UI and Macro subforum is `https://us.forums.blizzard.com/en/wow/c/guides/ui-macro/35`; most help threads live under `/en/wow/t/...`), WoWInterface Macro Help (`https://www.wowinterface.com/forums/forumdisplay.php?f=140`), wowlazymacros.com, MMO-Champion, Wowhead forums, OwnedCore.

## Method and evidence labels

- `fetched`: I read the page itself (Exa web_fetch, which returned the Reddit post body with author, score and UTC timestamp).
- `snippet`: I saw the quoted text in a search result excerpt (Exa search highlights). The quote is verbatim from the excerpt, the page itself was not opened.
- Dates: for fetched Reddit posts, the post timestamp. For Blizzard, WoWInterface and wowlazymacros, the date printed next to the post inside the excerpt. Exa's index date was NOT trusted on its own: several results carried a placeholder date on the same day of year as today (`-10-17`); every such item was either fetched to get the real date or left out.
- MMO-Champion and OwnedCore excerpts show no post date: marked "date not visible".
- Quotes keep the poster's spelling.

## Tags

- `OK`: doable with plain macro commands (`/cast`, `/use`, conditionals, `/castsequence`, `/focus`, `/petattack`, `/equipset`, and so on).
- `NEEDS_RUN`: needs `/run` or `/script` (Lua).
- `NEEDS_CLICK`: needs `/click`.
- `IMPOSSIBLE`: needs automation or logic Blizzard forbids or the macro system cannot express (more than one GCD action per press, choosing by cooldown, procs, inventory, cast state, unit position).
- `ALLOWLIST` note: the request is plain-macro but uses a command or CVar that is not in Gnomecaster's current `MACRO_COMMANDS` / `CVAR_ALLOW` in `/opt/Gnomecaster/addon/Gnomecaster/Actions.lua` (lines 16-41, read 2026-10-17). This is my inference from reading that table, not a test run.

---

## 1. Mouseover and targeting (including @cursor ground target)

1. "how do I edit this in a way that allows both options depending on the target I am hovering over?" (Penance help/harm mouseover). r/wow, 2025-08-16, fetched. https://www.reddit.com/r/wow/comments/1mrrkqx/anyone_know_how_to_write_mouseover_macros_that/ . `OK` (`[@mouseover,nodead][nodead][@player]`).
2. "use it on my current target (if there is one) or on my mouseover if I choose" (Storm Bolt). r/wownoob, 2025-09-08, snippet. https://www.reddit.com/r/wownoob/comments/1nc41e1/how_to_make_a_macro_to_attack_either_my_current/ . `OK`. Replies also point to the built-in Mouseover Cast option.
3. "When and only when I mouse over a party member, press F = LOH on that member" (Paladin, Midnight era). r/wow, 2026-04-12, fetched. https://www.reddit.com/r/wow/comments/1sj28xb/is_mouseover_macro_still_a_thing_looking_for_help/ . `OK`.
4. "I want it to cast on whatever I have mouse'd over (including myself) first". Blizzard US forums, 2021-04-28, snippet. https://us.forums.blizzard.com/en/wow/t/mouseover-question/950430 . Mostly `OK`; mousing over your own 3D model is `IMPOSSIBLE` (not a mouseover unit); the thread's workaround is `/console NameplatePersonalClickThrough 0` (ALLOWLIST: neither `/console` nor that CVar is allowed).
5. "the following macro does not work /target Loom'ithar" (Mythic Manaforge Omega boss). Blizzard US forums, 2025-08-25, snippet. https://us.forums.blizzard.com/en/wow/t/target-unusable/2157483 . `OK` (`/target [@boss1]`).
6. "one-button macro to cast Rake (and thus shift into cat form) when I am in caster" plus Moonfire in cat, with mouseover. Blizzard US forums, 2025-09-03, snippet. https://us.forums.blizzard.com/en/wow/t/need-help-getting-a-druid-macro-perfect/2163252 . `OK` (form and mouseover in one bracket, one `/cast` line).
7. "is there any way to cast the ground spells on the focused target by just pressing the button ?" r/wow, 2025-09-05, fetched. https://www.reddit.com/r/wow/comments/1n9hch9/cast_ground_spells_without_left_mouse_click_wow/ . `IMPOSSIBLE` for "at the focus": ground spells only accept `@cursor` or `@player`. `@cursor` part is `OK`.
8. "is there a way to have it target my current target instead of where my cursor currently is?" r/wownoob, 2023-04-21, fetched. https://www.reddit.com/r/wownoob/comments/12tozt7/ground_targeting_aoe/ . `IMPOSSIBLE` (same reason).
9. "incoporate "@cursor" to the mouseover section ... without requiring a left-click for placement" (Ravager). r/wow, 2024-10-03, snippet. https://www.reddit.com/r/wow/comments/1fuyh5f/ravager_macro/ . `OK` as `[@cursor]`; landing on the moused-over unit is `IMPOSSIBLE`.
10. "I cannot get the @cursor or @player macros to work at all" (Rain of Fire, Death and Decay). r/wow, 2025-02-21, fetched. https://www.reddit.com/r/wow/comments/1iuhxjy/cursor_macros/ . `OK` (the macro is right; see failure mode F4, self-cast key setting).
11. "alt = self cast ... control = focus target (harm) damage spell" (seven-step help/harm priority). r/wownoob, 2026-06-05, fetched. https://www.reddit.com/r/wownoob/comments/1txw2hd/anyway_around_the_255_character_limit_for/ . `OK` once rewritten on one `/cast` line (a reply got it to 206 characters).
12. "cast on my focus but if im moused over a player frame it will cast riptide on them instead". MMO-Champion, date not visible, snippet. https://www.mmo-champion.com/threads/2406916-Focus-macro-mousover-macro . `OK`.
13. "mouseover rupture, alt mouseover kick". MMO-Champion, date not visible, snippet. https://www.mmo-champion.com/threads/2616520-Mouseover-Macro-Help . `OK`.

## 2. Healer macros (mouseover heals, Clique-style)

14. "a mouseover macro that would cast when im hovered over a party/raid frame". r/wownoob, 2023-07-02, fetched. https://www.reddit.com/r/wownoob/comments/14okg5f/mouseover_macro_wow_party_frame/ . `OK`.
15. "Left click on party member = LOH ... Middle click on party member = Cleanse" (scenario 2 of item 3's post). r/wow, 2026-04-12, fetched. https://www.reddit.com/r/wow/comments/1sj28xb/is_mouseover_macro_still_a_thing_looking_for_help/ . `IMPOSSIBLE` as a macro or key binding: this is click casting on unit frames (built-in Click Casting UI or Clique).
16. "mod:shift mouseover macro which casts "Eternal Flame" when shift is pressed, and Light of Dawn when not". r/wownoob, 2026-09-07, fetched. https://www.reddit.com/r/wownoob/comments/1wa17vs/macro_help/ . `OK` (cause: Shift+key already bound, see F5).
17. Shift Word of Glory, Alt Lay on Hands, default Flash of Light, all mouseover then target then self: "it exceeds the characters limit". r/WoWMacros, 2025-08-03, snippet. https://www.reddit.com/r/WoWMacros/comments/1mggbao/how_to_simplify_a_macro_to_stay_within_the/ . `OK` after shortening (drop redundant `@target` brackets, use `[]`).
18. "I've hit the character limit and I don't know if there's a way to compress it" (Classic Anniversary Shaman, add Chain Heal). Blizzard US Classic forums, 2025-12-12, snippet. https://us.forums.blizzard.com/en/wow/t/a-way-to-compress-a-mouseover-macro-so-i-can-use-it-for-more-stuff/2214067 . `OK` (reply got it to 199 characters).
19. "I wish to have the mist cast as a mouse over" (Thunder Focus Tea + Renewing Mist, heal kept landing on self). WoWInterface, 2015-04-19, snippet. https://www.wowinterface.com/forums/showthread.php?t=52215 . `OK` (they used `harm` on a heal).

## 3. Trinket and cooldown stacking

20. "I want to use the trinket every time I use the Ability" and "the same tooltip as the ability and the same CD counter". r/wownoob, 2025-02-10, fetched. https://www.reddit.com/r/wownoob/comments/1imkkrk/how_to_macro_a_trinket_to_use_before_an_ability/ . `OK` (`#showtooltip Ability`, `/use 14`, `/cast Ability`).
21. "If Trinket A = cooldown -> Use Trinket B If Trinket B = cooldown -> Use Trinket A". Wowhead forums, 2021-07-18, snippet. https://www.wowhead.com/forums/topic/macro-trinket-323450 . `OK` (`/use 13` then `/use 14`, works while neither is on the GCD).
22. "first check if my trinkets are off cooldown and THEN use /use them". OwnedCore, date not visible, snippet. https://www.ownedcore.com/forums/world-of-warcraft/world-of-warcraft-general/wow-ui-macros-talent-specs/305966-check-if-trinket-off-cooldown-then-use.html . The cooldown check is `IMPOSSIBLE` (macros cannot branch on cooldown); plain `/use 13`, `/use 14`, `/cast` is `OK`.
23. "If the trinket is on cooldown then just skip that line and cast the spell". WoWInterface, 2007-11-17 (old, canonical), snippet. https://www.wowinterface.com/forums/showthread.php?t=13536 . `OK` for off-GCD trinkets; thread shows it failing on some items (F7).
24. "Is it possible to have the tooltips for both trinkets come up?" MMO-Champion, date not visible (Cataclysm era, inferred from the poster's level-85 signature), snippet. https://www.mmo-champion.com/threads/686369-trinket-macro-with-tooltip-cooldown . `IMPOSSIBLE` (one icon per macro button).
25. "I've made a macro and the trinkets get used but Pyroblast won't cast". Blizzard US forums, 2019-03-20, snippet. https://us.forums.blizzard.com/en/wow/t/macro-problem-pyroblast-after-trinket-use/129839 . `OK` once the on-GCD trinket is removed (F7).

## 4. Castsequence

26. "it was designed to cast once after killing a mob" (`/castsequence reset=target/dead Death Strike, null`). Blizzard US forums, 2025-07-23, snippet. https://us.forums.blizzard.com/en/wow/t/macro-help/2136237 . `OK` (fix offered: `null` to `0`).
27. "I'm trying to make a macro to cast three utility buffs and it just casts the first one". Blizzard US forums, 2025-11-10, snippet. https://us.forums.blizzard.com/en/wow/t/help-with-shaman-macros/2197472 . One press: `IMPOSSIBLE` (three GCD spells). Three presses via `/castsequence`: `OK`.
28. "Is it possible to macro ancestral swiftness and then laval lash?" Same thread, November 2025 (reply dated 2025-11-24), snippet. https://us.forums.blizzard.com/en/wow/t/help-with-shaman-macros/2197472 . `OK` if the first spell is off the GCD.
29. "Cast "Thrash" CD by CD no matter what ... "mangle" be casted second Priority If thrash is on CD". wowlazymacros, date not visible, snippet. https://wowlazymacros.com/t/need-help-with-a-sequence/22025/1 . `IMPOSSIBLE` (priority by cooldown state).
30. "I don't want to cast the same spell too quickly in succession" (Blur / Alter Time double-press guard). Blizzard EU forums, 2026-02-26, snippet. https://eu.forums.blizzard.com/en/wow/t/was-castsequence-reset-changed-this-week/608323 . `OK`.
31. "I want to make a simple macro that does a couple of spells in a row" (Outlaw). r/wownoob, 2021-05-31, snippet. https://www.reddit.com/r/wownoob/comments/noquuv/castsequence_not_working/ . `IMPOSSIBLE` in one press.

## 5. Modifiers (shift, ctrl, alt)

32. "Specially using ctrl+alt modifier to cast on @arena3" (MoP Classic). Blizzard US forums, 2025-08-30, snippet. https://us.forums.blizzard.com/en/wow/t/macro-no-more-working-on-mop/2160851 . `OK` (multi-modifier clauses first, F19).
33. "This should cast Blessing on my focus, if one exists and my my target (or self) if I hit any modifier key". Blizzard US forums, 2025-10-29, snippet. https://us.forums.blizzard.com/en/wow/t/conditional-macros-not-working-after-tue-patch-of-29-oct-2025/2192352 . `OK` (root cause was the self-cast key setting, F4).
34. "The idea being to hit number keys with no mod key, shift and control". r/wownoob, 2023-07-20, snippet. https://www.reddit.com/r/wownoob/comments/154ebmr/macro_troubleshooting/ . `OK` (root cause: keybind conflict, F5).

## 6. Pet macros

35. "work on both target and mouseover, prioritizing mouseover" (`/petattack`). r/classicwow, 2024-09-12, snippet. https://www.reddit.com/r/classicwow/comments/1ff3uxa/anyone_know_how_to_make_a_targetmouse_over_pet/ . `OK`.
36. "an all in one pet attack/control macro ... If you hold shift it will cast dash". Blizzard US Hunter forums, 2019-10-19, snippet. https://us.forums.blizzard.com/en/wow/t/pet-attack-macro/337354 . Base version `OK`; the reply's longer variant needed a second macro via `/click` (`NEEDS_CLICK`), which also no longer works since 11.0 (F2).
37. "how do I make it so my pet starts moving to attack when I attack" (TBC Classic). r/wownoob, 2021-10-27, snippet. https://www.reddit.com/r/wownoob/comments/qgjs5x/how_do_i_make_a_macro_for_hunter_pet_to_attack/ . `OK`.

## 7. Mounts (random favorite, flying vs ground, skyriding)

38. "my flying mount and ground mount on the same button" ... "It only ever summons my flying mount". r/wow, 2026-02-06, fetched. https://www.reddit.com/r/wow/comments/1qxfxdf/macro_for_flying_and_ground_mounts/ . `OK` (`[flyable]`, `[advflyable]`).
39. "Is there a mod condition which makes skyriding/dragonriding an option?" Blizzard US forums, 2024-08-28, snippet. https://us.forums.blizzard.com/en/wow/t/multiple-mount-macro-with-skyridingground-mounts/1932801 . `OK` (`[advflyable]`).
40. "a macro that randomly selects different mounts depending on the scenario" and "function like the official's "favorite mount" spell". r/wow, 2024-07-04, fetched. https://www.reddit.com/r/wow/comments/1dv32sw/please_teach_me_how_to_write_a_macro_that/ . `OK` with `/userandom [cond] a, b; c, d` until the 255-character limit; calling the real Summon Random Favorite Mount needs `NEEDS_CLICK` or `NEEDS_RUN` (`/click MountJournalSummonRandomFavoriteButton` or `/run C_MountJournal.SummonByID(0)`, per https://warcraft.wiki.gg/wiki/Summon_Random_Favorite_Mount , wiki page seen as a snippet).

## 8. Toys, items, consumables

41. "click a health stone, and then if needed, a heath pot moments later with the same button". Blizzard US forums, 2025-01-22, snippet. https://us.forums.blizzard.com/en/wow/t/heath-pothealth-stone-single-button-macro-needed/2049033 . `OK` (modifier or `/castsequence`).
42. "is there some sort of @exists clause that will check if healthstone exists before trying to use it?" Blizzard US forums, 2024-10-07, snippet. https://us.forums.blizzard.com/en/wow/t/healthstonepotion-macro-check/1979174 . Inventory check `IMPOSSIBLE` (no item-count conditional); `/castsequence` with item IDs `OK`.
43. "use HS if exists, or not on cd, else use pot". r/wow, 2023-02-09, snippet. https://www.reddit.com/r/wow/comments/10xvtci/healthston_or_healing_potion_1_button_macro/ . `IMPOSSIBLE` (cooldown and inventory decision; replies point to the AutoPotion addon, which rewrites the macro out of combat).
44. "Is there a addon or macro to use a random hearthstone from my collection?" r/wow, 2026-07-16, fetched. https://www.reddit.com/r/wow/comments/1uyhobh/is_there_a_addon_or_macro_to_use_a_random/ . `OK` with `/castrandom` and item IDs (character limit caps the list); the top reply (46 points) used `/run C_ToyBox.UseToyByItemID(...)` (`NEEDS_RUN`).
45. "I'd love if there was a way to pick a hearthstone at random to use". r/wow, 2024-12-27, fetched. https://www.reddit.com/r/wow/comments/1hn98uy/there_a_way_to_do_a_random_hearthstone/ . `OK` (`/castrandom`).

## 9. Focus and interrupt

46. "use my counterspell without having to manually select the target". r/wow, 2024-10-20, snippet. https://www.reddit.com/r/wow/comments/1g7tpoo/intrerupt_macro/ . `OK` (`/focus [@mouseover,exists,harm][]` plus `/cast [@focus,exists][@target] Counterspell`).
47. "Curious about your focus macro setup for kicks in M+". r/CompetitiveWoW, 2023-02-07, snippet. https://www.reddit.com/r/CompetitiveWoW/comments/10vs1z9/focus_macros/ . `OK`.
48. "All it needs to do is put a mob on focus and stick an icon on top of it." r/CompetitiveWoW, 2026-03-26, fetched. https://www.reddit.com/r/CompetitiveWoW/comments/1s446qb/kick_target_macro_broken_since_midnight/ . `OK` (`/focus`, `/tm`), but Midnight's marker rate limit breaks it (F12).
49. "I can see the cast bar, but I can't click on the specific mob among all the others" (Mage, M+). r/wownoob, 2025-08-08, snippet. https://www.reddit.com/r/wownoob/comments/1mktm01/how_do_you_manage_to_interrupt_in_mythic/ . `OK` (focus kick).
50. "automatic target the mob who is casting". r/CompetitiveWoW, 2022-04-30, snippet. https://www.reddit.com/r/CompetitiveWoW/comments/ufazdo/share_a_good_automatic_target_interrupt_macro/ . Picking the caster is `IMPOSSIBLE` (no cast-state targeting; the posted macro just `/targetenemy`-cycles).

## 10. Stopcasting

51. "my character stop casting whatever and instantly hit cs". r/classicwow, 2025-02-05, snippet. https://www.reddit.com/r/classicwow/comments/1iieh2r/counterspell_cancel_cast_macro/ . `OK`. A reply adds `/run ... SendChatMessage` (`NEEDS_RUN`, and chat lines are also outside Gnomecaster's allowlist).
52. "stopcasting only if casting anything other than Pyroblast". WoWInterface, 2012-07-28, snippet. https://www.wowinterface.com/forums/showthread.php?t=43794 . `IMPOSSIBLE` (only `[channeling]` exists, no casting-spell conditional).
53. "it stops the FB cast, but doesn't do the Ice Barrier, unless I keep tapping the key". Blizzard US forums, thread started 2020-12-15, this reply's date not visible (later replies dated 2025-04-03), snippet. https://us.forums.blizzard.com/en/wow/t/help-with-caststopcast-macro/777987 . `OK` in principle, flaky in practice (F20).

## 11. Equipment set swapping

54. "Switches to the secondary talent set ... Switches to a specific equipment set". WoWInterface, 2023-04-10, snippet. https://www.wowinterface.com/forums/showthread.php?t=59553 . Gear part `OK` (`/equipset`); doing it after the spec swap finishes needed `C_Timer.After` (`NEEDS_RUN`). `/usetalents` is ALLOWLIST (not in `MACRO_COMMANDS`).
55. "change gear AND talents with one click". WoWInterface, 2018-02-20, snippet. https://www.wowinterface.com/forums/showthread.php?t=56056 . Gear `OK`; retail spec swap needs `/run SetSpecialization(...)` (`NEEDS_RUN`, see https://eu.forums.blizzard.com/en/wow/t/useful-macro-to-change-spec-and-gear-set-with-one-click/121808 , 2020-01-24, snippet).
56. "this macro will either work for the first 5 minutes-1 month, then just stops doing anything" (`#equipslot` + Sinister Strike). r/wownoob, 2026-08-31, fetched. https://www.reddit.com/r/wownoob/comments/1w3my7k/whats_wrong_with_my_macro/ . `OK` (reply: use `/equipset`; `#equipslot` is not a real meta command as written).

## 12. UI toggles that people solve with /run or /console

57. "when I enable friendly nameplates (shift+V), all enemy nameplates automatically toggle off" and later "a way to get this to work in combat?" Blizzard EU forums, 2024-07-15, snippet. https://eu.forums.blizzard.com/en/wow/t/nameplate-toggle-macro-help/523132 . `NEEDS_RUN` (`SetCVar`); in combat `IMPOSSIBLE` (scripts suppressed). Gnomecaster's setting action covers `nameplateShowEnemies` and `nameplateShowFriends` out of combat.
58. "a macro for the button to sell the gray objects ... Without the need for addons". r/wownoob, 2024-04-07, fetched. https://www.reddit.com/r/wownoob/comments/1by8p7x/macro_to_sell_greys/ . `NEEDS_RUN` (container loop). Replies note the vendor window has a button for it.
59. Toggle NPC and friendly names for screenshots ("I can only figure out how to do via checkbox"). r/classicwow, 2019-09-23, fetched. https://www.reddit.com/r/classicwow/comments/d8cnua/macro_to_toggle_npc_friendly_names/ . `NEEDS_RUN`; ALLOWLIST (`UnitNameNPC`, `UnitNameFriendlyPlayerName` not in `CVAR_ALLOW`).
60. "The old command "/console SoftTargetEnemy 3" doesn't seem to work anymore" (toggle action targeting). Blizzard US forums, 2022-12-08, snippet. https://us.forums.blizzard.com/en/wow/t/how-to-turn-onoff-action-targeting-with-a-macro-or-command/1437079 . Toggle is `NEEDS_RUN`; left/right-click `/console` version works but `/console` is ALLOWLIST. `softTargetEnemy` itself is in `CVAR_ALLOW`.
61. "my macro to teleport to my house does not work anymore" (`/run C_Housing.TeleportHome`, "blocked because of an action that is usable only by the blizzard UI"). r/wownoob, 2026-01-29, fetched. https://www.reddit.com/r/wownoob/comments/1qq5cj5/previous_macros_broken_with_120/ . `NEEDS_RUN`, and in 12.0 the call is protected, so now `IMPOSSIBLE` from a macro.
62. "problem is that the Midnight pre-patch broke the macros" (`/run C_CraftingOrders.PlaceNewOrder`). MMO-Champion, date not visible (Midnight pre-patch era), snippet. https://www.mmo-champion.com/threads/2666687-how-to-fix-crafting-macro-for-Midnight . `NEEDS_RUN` (fix: `reagentItems` renamed to `reagentInfos` in 12.0.0).
63. "It resets on logout, so make it a macro and put it on your hotbar" (`/console CameraDistanceMaxZoomFactor 3.8`). r/classicwow, 2023-09-15, snippet. https://www.reddit.com/r/classicwow/comments/16jkpam/reminder_you_can_use_a_macro_to_increase_your/ . `/console` in a macro is ALLOWLIST; the CVar is in `CVAR_ALLOW`, so the setting action covers it.

## 13. Keybind questions

64. "I would like different keybindings for each spec" ... "I've tried mods-they don't work". Blizzard US forums, 2024-10-12, snippet. https://us.forums.blizzard.com/en/wow/t/keybinding-changes-affecting-multiple-specs-why/1983189 . Not possible in the default UI (bindings are account or character, not spec); addons such as Spec Keybinds do it by rebinding on spec change (https://www.curseforge.com/wow/addons/spec-keybinds , snippet). Not a macro, so no macro tag; for Gnomecaster it is a bind-on-spec-change feature request.
65. "When I go to configure these buttons, I see that one of them is ctrl, one is shift, and one is alt" (Redragon side buttons). r/wow, 2023-01-31, snippet. https://www.reddit.com/r/wow/comments/10q6atd/question_about_keybinds/ . Bindable after remapping in the mouse software; out of game scope.
66. "I was planning on binding my main rotation to the thumb buttons" (12-button mouse, Fury). r/wownoob, 2024-02-07, fetched. https://www.reddit.com/r/wownoob/comments/1aleu10/mmo_mouse_keybinds/ . Layout advice request; binding itself `OK`.
67. "how can i unbind the mouse buttons from keys 1-12, but still be able to assign them with VUDHO". r/Corsair, 2024-07-10, snippet. https://www.reddit.com/r/Corsair/comments/1e09ah4/how_to_unbind_side_buttons_in_wow/ . Out of game scope (mouse driver).
68. "take the keybindings I have set for my main and make them my account-wide keybinds". Blizzard US forums, 2024-01-22, snippet. https://us.forums.blizzard.com/en/wow/t/turn-character-specific-keybinds-into-account-wide-keybinds/1772164 . Answer was a file copy with the game closed; an in-game tool could re-apply bindings, macro tag not applicable.
69. "is there any way to allow using MB3 and MB4 on party/raid frames?" Blizzard US forums, 2021-04-28, snippet. https://us.forums.blizzard.com/en/wow/t/mouseover-question/950430 . `IMPOSSIBLE` with mouse-button binds (unit frames eat the click, F6); works with keyboard keys or Click Casting.
70. Shadowstep mouseover "works unless cursor is above a party frame" when bound to mouse button 5. r/wow, 2024-11-14, snippet. https://www.reddit.com/r/wow/comments/1gqt70s/mouseover_macro_not_working_on_partyraid_frames/ . Same as 69: remap the mouse button to a key, or Click Casting.

## 14. Classic-specific

71. "I want to turn auto shot on, and if I press the button again it doesn't turn auto shot off". Blizzard US forums, 2019-05-30, snippet. https://us.forums.blizzard.com/en/wow/t/hunter-auto-shot-macro-help-wow-classic/187106 . `OK` (`/cast !Auto Shot`, `/startattack`).
72. "a macro allows you to turn on shoot without turning it back off again" (wand). Blizzard US Classic forums, 2019-08-27, snippet. https://us.forums.blizzard.com/en/wow/t/wand-macro/271335 . `OK` (`/castsequence reset=2 !Shoot, null`); the old `/script` version is blocked.
73. "I need to hit the macro at least twice to make it work" (`/stopattack` + `/startattack` + Shadow Bolt). Blizzard EU forums, 2024-12-09, snippet. https://eu.forums.blizzard.com/en/wow/t/classic-1x-stopattack-not-working-when-its-in-the-line-above-startattack/552739 . `OK` partly; suggested `/console stopAutoAttackOnTargetChange 1` is ALLOWLIST.
74. "a macro that will Revenge if available or overpower if available". Blizzard US forums, 2020-03-11, snippet. https://us.forums.blizzard.com/en/wow/t/classic-revenge-overpower-macro/467177 . "If available" (proc) is `IMPOSSIBLE`; by stance (`[stance:1] Overpower; [stance:2] Revenge`) `OK`.
75. "one to work that takes me from thunder clap back to defensive stance". Blizzard US forums, 2019-11-09, snippet. https://us.forums.blizzard.com/en/wow/t/classic-warrior-best-classic-macros/358678 . `OK` (stance change and ability on separate GCDs; sometimes two presses).
76. "starting in Bat stance, then a spell for example Spell reflect or Disarm, which will go into Def Stance" (TBC). Blizzard US forums, 2021-04-30, snippet. https://us.forums.blizzard.com/en/wow/t/warrior-stance-dance-macro-question/951881 . `OK`.

## 15. One-button rotation and GSE-style automation

77. "turn the sequence on with F1 and it loops it until I hit F1 again". r/wow, 2025-02-23, snippet. https://www.reddit.com/r/wow/comments/1iwd7ms/help_with_macros/ . `IMPOSSIBLE` (one action per hardware press).
78. "Am I allowed to use autohotkey to spam one-button-rotation?" Blizzard US Customer Support forums, 2026-06-03, snippet. https://us.forums.blizzard.com/en/wow/t/am-i-allowed-to-use-autohotkey-to-spam-one-button-rotation/2312526 . `IMPOSSIBLE` (external automation, bannable per replies).
79. "I have arthritis and need macros to lower the number of buttons I use". Blizzard US forums, 2025-02-07, snippet. https://us.forums.blizzard.com/en/wow/t/gsegnomesquencer/2056920 . `OK` within one action per press (`/castsequence`, modifiers).
80. "I have a bunch of wrist/hand injuries so I like to use macros". r/wownoob, 2024-09-09, snippet. https://www.reddit.com/r/wownoob/comments/1fd3j1k/the_war_within_easiest_to_use_macros_with/ . `OK` (fewer buttons via sequences and modifiers).
81. "my goal is a one-button macro to avoid tendonitis" ... "prioritizes the use of wrath hammers as soon as they become available". wowlazymacros, 2024-08-28, snippet. https://wowlazymacros.com/t/i-need-help-with-the-order-of-the-sequences/44254 . `IMPOSSIBLE` for "as soon as available" (reacting to cooldowns/procs).
82. "I'd like to have something just do my combos for me depending on different situations". r/wow, 2020-08-03, fetched. https://www.reddit.com/r/wow/comments/i2qqbr/is_it_allowed_to_have_a_single_button_perform/ . `IMPOSSIBLE` (situational decision logic).
83. "its where u press multiply keys and u bind it to a key and its spam thos keys". Blizzard EU forums, 2024-10-29, snippet. https://eu.forums.blizzard.com/en/wow/t/is-macro-software-illigal/546222 . `IMPOSSIBLE` (input automation).

---

## Failure modes players report

- F1, 255-character limit, and addons can no longer extend it. https://www.reddit.com/r/wownoob/comments/1txw2hd/anyway_around_the_255_character_limit_for/ (2026-06-05, fetched: "I used to have an addon that allow me to write long macros"); https://us.forums.blizzard.com/en/wow/t/255-macro-character-limit/1902483 (2024-07-26, snippet, the 11.0 `macrotext` removal); https://www.curseforge.com/wow/addons/macro-toolkit (snippet: "It's no longer possible to "extend" macros beyond the 255 character limit").
- F2, `/click` chaining removed in 11.0. Blizzard pinned guide says "chaining macros together with `/click` ... have been eliminated in 11.0": https://us.forums.blizzard.com/en/wow/t/macros-essential-information/21139 (snippet); confirmed in a 2024-12-03 reply: https://us.forums.blizzard.com/en/wow/t/255-macro-character-limit/1902483 . GSE users hit the same wall ("a macro (on your actionbar) cannot click another macro"): https://wowlazymacros.com/t/i-cant-use-macros-anymore/42545 (2024-07-29, snippet).
- F3, "macro does nothing". Causes seen: spell names typed in English on a Spanish client (https://www.reddit.com/r/wownoob/comments/15sn6od/macros_not_working/ , 2023-08-16, fetched for date, cause from snippet); a fake `#equipslot` line (https://www.reddit.com/r/wownoob/comments/1w3my7k/whats_wrong_with_my_macro/ , 2026-08-31, fetched); macro not dragged to a bar or the old spell pressed instead (https://www.reddit.com/r/wownoob/comments/15lmt37/question_about_macros_not_working/ , 2023-08-08, snippet).
- F4, Self Cast Key bug: since 9.2.5, a self-cast modifier key breaks `@unit` and `@cursor` macros with modifiers. https://us.forums.blizzard.com/en/wow/t/conditional-macros-not-working-after-tue-patch-of-29-oct-2025/2192352 (2025-10-30, snippet); https://us.forums.blizzard.com/en/wow/t/help-what-does-this-do-exactly/1808665 (2024-03-16, snippet).
- F5, a binding on Shift+key (or similar) beats the macro's `[mod:shift]`. https://www.reddit.com/r/wownoob/comments/1wa17vs/macro_help/ (2026-09-07, fetched: "Keybinds have priority vs macro modifiers"); https://www.reddit.com/r/wownoob/comments/154ebmr/macro_troubleshooting/ (2023-07-20, snippet); https://www.mmo-champion.com/threads/888225-Macro-assist (date not visible, snippet).
- F6, mouse-button binds do nothing over unit frames ("unit frames will "eat" the mouse click"). https://us.forums.blizzard.com/en/wow/t/mouseover-and-interrupt-macro/668575 (2020-10-08, snippet); https://www.reddit.com/r/wow/comments/1gqt70s/mouseover_macro_not_working_on_partyraid_frames/ (2024-11-14, snippet).
- F7, trinket on the GCD, or on cooldown, blocks the spell. "if the trinket is on CD, i get an error, Item is not ready yet, and it does NOT continue to cast the spell": https://www.wowinterface.com/forums/showthread.php?t=13536 (2007-11-17, snippet); "Your trinket is on the GCD": https://us.forums.blizzard.com/en/wow/t/trinket-spell-macro/429887 (2020-01-31, snippet); https://us.forums.blizzard.com/en/wow/t/macro-problem-pyroblast-after-trinket-use/129839 (2019-03-20, snippet); BfA change "now only 1 on use trinket will work": https://us.forums.blizzard.com/en/wow/t/help-with-a-trinket-macro/818313 (2021-01-07, snippet).
- F8, one GCD action per press; `/castsequence` stalls on a failed cast. https://us.forums.blizzard.com/en/wow/t/help-with-shaman-macros/2197472 (2025-11-10, snippet); https://warcraft.wiki.gg/wiki/MACRO_castsequence ("will not advance to the next action ... if the previous action was not performed successfully", snippet); GSE wiki (generator/spender lines get stuck): https://github-wiki-see.page/m/TimothyLuke/GSE-Advanced-Macro-Compiler/wiki/Understanding--castsequence (snippet).
- F9, `/castsequence reset=` breakage. TWW Season 2: "we have lost the ability to use `/castsequence reset=...`" then later "This issue has been addressed and Fix by Blizzard": https://us.forums.blizzard.com/en/wow/t/broke-castsequence-resetresets-macrotextin-game-macros-attention-blizzard/2079589 (2025-03-19 to 2025-03-31, snippet). `reset=N` counts from last press, not last cast: https://eu.forums.blizzard.com/en/wow/t/was-castsequence-reset-changed-this-week/608323 (2026-02-26, snippet). `null` resolving to a real item/spell: https://wowlazymacros.com/t/two-most-asked-questions-base-spells-and-macro-locks/17772 (2020-10-28, snippet).
- F10, `#showtooltip` icon stuck or "?" icon. Icon must be the "?" for it to update, and edits silently replace it: https://us.forums.blizzard.com/en/wow/t/macro-icons-controlled-by-showtooltip-not-updating-properly-since-100/1396423 (2022-11-08 to 2024-06-06, snippet); https://us.forums.blizzard.com/en/wow/t/showtooltip-working/2137057 (2025-07-25, snippet); https://us.forums.blizzard.com/en/wow/t/showtooltip-not-working-in-macros/1439407 (2022-12-09, snippet); Classic `#showtooltip` turned into `@showtooltip`: https://us.forums.blizzard.com/en/wow/t/showtooltip-not-working-anymore/2135054 (2025-07-21, snippet).
- F11, macros per character vs account, and lost macros/binds. "Only general macros are deleted. Character specific macros remain": https://www.reddit.com/r/wow/comments/1555gwz/general_macros_being_deleted_when_i_switch/ (2023-07-20, snippet). Wowhead guide: 120 account macros plus 18 per character: https://www.wowhead.com/guide/macro-writing-creating (snippet). Blizzard support: binds and macros not saved after ALT+F4 or read-only WTF: https://us.battle.net/support/en/article/000021759 (snippet). Character-specific binding toggle flips on by itself: https://us.forums.blizzard.com/en/wow/t/character-specific-keybinds-problem/45580 (2018-12-12, reply 2023-06-29, snippet).
- F12, Midnight (12.x) changes that hit macros. Blizzard (2026-03-01): "Macros are prevented from setting a target marker on more than 3 units within a very short time", plus chat limits during encounters: https://us.forums.blizzard.com/en/wow/t/macro-changes-now-live-target-markers-and-chat-messages/2261956 (snippet). Players report markers blocked for a long time: https://www.reddit.com/r/CompetitiveWoW/comments/1s446qb/kick_target_macro_broken_since_midnight/ (2026-03-26, fetched: "if you mark too much you get rate limited for like 30 minutes"). `/run` calls now protected: https://www.reddit.com/r/wownoob/comments/1qq5cj5/previous_macros_broken_with_120/ (2026-01-29, fetched). API renames break `/run` macros: https://www.mmo-champion.com/threads/2666687-how-to-fix-crafting-macro-for-Midnight (snippet). GSE 3.2 disabled at pre-patch, sequences must be converted: https://www.patreon.com/elfyau/posts/important-gse-im-148026871 (2026-01-12, snippet); "GSE reports that this sequence is too old": https://wowlazymacros.com/t/subtlety-midnight-12-0/60276?page=2 (2026-03-24, snippet). Secret values and combat-log removal are addon-side, not macro-side: https://warcraft.wiki.gg/wiki/Patch_12.0.0/API_changes/notes (snippet). I found no source saying Midnight changed plain `/cast` conditionals or `/castsequence` itself; a Balance Druid poster tested `[nochanneling]` and `@mouseover` macros on the 12.0 beta and reports them working: https://us.forums.blizzard.com/en/wow/t/balance-druid-macros-working-1125120-beta/2199491 (2025-11-14, snippet). One reporter says `/stopmacro [channeling]` locks casts "for a few seconds" in the same 2026-03-01 thread (snippet; unconfirmed).
- F13, `/castsequence` with conditionals or modifiers inside GSE behaves differently from the same macro on a bar. https://www.reddit.com/r/WoWMacros/comments/1hl8mpi/modifier_macros_not_working_in_gse/ (2024-12-24, snippet); https://github.com/TimothyLuke/GSE-Advanced-Macro-Compiler/issues/1498 (2024-07, snippet).
- F14, `@mouseover` falling through. Without a trailing `[]` nothing is cast when there is no mouseover: https://www.wowinterface.com/forums/showthread.php?t=52215 (2015-12-26 reply, snippet). `[@mouseover][@player]` without `help` never reaches `@player` ("it will be attempting to cast at mouseover regardless"): https://us.forums.blizzard.com/en/wow/t/help-what-does-this-do-exactly/1808665 (2024-03-16, snippet). Missing `help,nodead` leaves the "choose a target" hand up: https://www.reddit.com/r/wownoob/comments/14okg5f/mouseover_macro_wow_party_frame/ (2023-07-02, snippet from a reply).
- F15, your own 3D character is not a mouseover target. https://us.forums.blizzard.com/en/wow/t/mouseover-question/950430 (2021-04-28, snippet).
- F16, script toggles do not run in combat. https://eu.forums.blizzard.com/en/wow/t/nameplate-toggle-macro-help/523132 (2024-07-16 reply, snippet).
- F17, items by name fail; use `item:ID`. "There's been numerous reports of potions not working in macros this xpac when they've been name based": https://us.forums.blizzard.com/en/wow/t/healthstonepotion-macro-check/1979174 (2024-10-07, snippet). Toy IDs instead of names for `/castrandom`: https://www.reddit.com/r/wow/comments/avcomg/is_there_a_way_to_make_a_macro_that_uses_a_random/ (2019-02-27, snippet).
- F18, conditional order: multi-modifier clauses must precede single ones ("The multi modifier options need to come before the singles"): https://us.forums.blizzard.com/en/wow/t/macro-no-more-working-on-mop/2160851 (2025-08-30, snippet). Separate `/cast` lines where the first is unconditional always win (Druid forms): https://us.forums.blizzard.com/en/wow/t/need-help-getting-a-druid-macro-perfect/2163252 (2025-09-03, snippet).
- F19, `/stopcasting` flaky, sometimes needs to appear twice: https://us.forums.blizzard.com/en/wow/t/help-with-caststopcast-macro/777987 (reply 2025-04-03: "Double-/stopcasting fixed it" then "It's buggy at best", snippet).
- F20, mount conditionals confusion (`[flyable]` vs `[advflyable]` vs `[noflyable]`) after skyriding: https://us.forums.blizzard.com/en/wow/t/multiple-mount-macro-with-skyridingground-mounts/1932801 (2024-08-28 to 2025-11-28, snippet). Summon Random Favorite Mount cannot be cast by name: https://warcraft.wiki.gg/wiki/Summon_Random_Favorite_Mount (snippet).

## Allowlist gaps seen in real requests (inference from reading Actions.lua, not tested)

Commands players used that `MACRO_COMMANDS` rejects: `/console` (items 4, 60, 63, 73), `/usetalents` (54), `/petaggressive` (listed in the Warcraft Tavern Classic hunter pet set, https://www.warcrafttavern.com/wow-classic/guides/hunter-pet-macros/ , snippet), `/petmoveto` (Hunter keybind post, https://us.forums.blizzard.com/en/wow/t/what-keybinds-do-you-use/2039384 , 2025-01-04, snippet), `/leavevehicle` (Wowhead mount comment, https://www.wowhead.com/spell=150544/summon-random-favorite-mount , snippet), and the `/cqs` alias of `/cancelqueuedspell` (item 73 thread and 777987). CVars requested but not in `CVAR_ALLOW`: `UnitNameNPC`, `UnitNameFriendlyPlayerName`, `stopAutoAttackOnTargetChange`, `SpellQueueWindow` (https://eu.forums.blizzard.com/en/wow/t/spellqueuewindow-interrupts/376382 , 2022-08-17, snippet), `NameplatePersonalShowAlways`. I am not recommending adding any of these here; that is a separate judgement (some, like `/console`, would let a model set any CVar).

---

## Count per category (from the numbered list above)

| Category | Items | Count |
|---|---|---|
| 1. Mouseover and targeting, @cursor | 1-13 | 13 |
| 2. Healer macros | 14-19 | 6 |
| 3. Trinket and cooldown stacking | 20-25 | 6 |
| 4. Castsequence | 26-31 | 6 |
| 5. Modifiers | 32-34 | 3 |
| 6. Pet macros | 35-37 | 3 |
| 7. Mounts | 38-40 | 3 |
| 8. Toys, items, consumables | 41-45 | 5 |
| 9. Focus and interrupt | 46-50 | 5 |
| 10. Stopcasting | 51-53 | 3 |
| 11. Equipment set swapping | 54-56 | 3 |
| 12. UI toggles via /run or /console | 57-63 | 7 |
| 13. Keybind questions | 64-70 | 7 |
| 14. Classic-specific | 71-76 | 6 |
| 15. One-button rotation, GSE | 77-83 | 7 |
| Total | 1-83 | 83 |

Date spread of the 83 items (counted with grep over the item lines): 48 from 2024-2026 (2024: 18, 2025: 19, 2026: 11), 28 from 2007-2023, 7 with no visible date. Evidence: 21 fetched, 62 snippet.

Requests that are `IMPOSSIBLE` as asked (20 of 83): items 7, 8, 15, 22, 24, 27 (one press), 29, 31, 42 (inventory check), 43, 50, 52, 61 (since 12.0), 69, 74 ("if available"), 77, 78, 81, 82, 83.

## Top 10 request types I saw most often

Ranked by how many distinct threads in this list asked for it (my count from the list above, not a sample of all forums):

1. Mouseover cast with fallback to target or self (items 1-3, 11-14, 16-19): 11 threads.
2. One-button or fewer-buttons rotation, often for hand injuries (27, 29, 31, 77-83): 10 threads.
3. Script-only UI toggles: nameplates, names, sell greys, action targeting, camera, housing (57-63): 7 threads.
4. Keybind setup: mouse side buttons, per-spec binds, account vs character (64-70): 7 threads.
5. Trinket plus ability on one button, or "use whichever trinket is ready" (20-25): 6 threads.
6. Focus interrupt and focus-plus-marker (12, 46-50): 6 threads.
7. Classic auto-attack, wand, auto shot and stance dancing (71-76): 6 threads.
8. Healthstone then potion, or random hearthstone toy (41-45): 5 threads.
9. Ground-target `@cursor` or "at my target" (7-10): 4 threads.
10. Macro too long for 255 characters (11, 17, 18): 3 request threads, tied with the five types below.

Not ranked above but present: mount flying/ground/skyriding (3), pet attack mouseover (3), gear plus spec swap (3), stopcasting before kick (3), modifier ordering (3).
