# Prior-art survey: macros, binds and layouts for Gnomecaster (Retail 12.1.5 and Classic)

Date: 2026-10-17. Research only; nothing in /opt/Gnomecaster was changed.

Legend: VERIFIED means I read the code or the primary source (Blizzard UI source, the addon's repository, the issue thread itself). REPORTED means I only saw a description (store page, search summary, forum summary). INFERRED means my own reasoning from verified facts, not observed behaviour.

Blizzard UI source used: the local mirror `~/.cache/gnomecaster/wow-ui-source`, pinned at commit `18c6d677` ("12.1.5 (70391)", the same pin `tools/wow_api.py` uses), plus the `classic` (5.5.4.70268) and `classic_era` (1.15.9.70003) branches of https://github.com/Gethe/wow-ui-source fetched over HTTPS. Nothing here was run in a game client; every runtime claim below is either Blizzard code read statically or a third party's report.

Repositories read (cloned into `research/src/`):

| Project | Repo | Commit read |
|---|---|---|
| GSE | https://github.com/TimothyLuke/GSE-Advanced-Macro-Compiler | `eda9917` (2026-10-17) |
| Macro Toolkit | https://github.com/NumyAddon/MacroToolkit | `9d5a54e` (2026-10-14) |
| Mega Macro | https://github.com/Sellorio/mega-macro | `a960425` (2026-01-30) |
| Talent Loadout Manager | https://github.com/NumyAddon/TalentLoadoutManager | HEAD 2026-10-14 |
| LibEditModeOverride | https://github.com/plusmouse/LibEditModeOverride | HEAD 2026-06-08 |
| Ace3 | https://github.com/WoWUIDev/Ace3 | HEAD |
| wow-ai | https://github.com/chelinho139/wow-ai | `3756eb5` (2026-09-27) |
| GSE companion disclosure | https://github.com/JesperLive/gse-companion-disclosure | HEAD |

---

## 1. GSE (GnomeSequencer Enhanced)

### Execution model (VERIFIED, `GSE/API/Storage.lua`)

- Each sequence becomes one named button: `CreateFrame("Button", name, nil, "SecureActionButtonTemplate,SecureHandlerBaseTemplate")`, `RegisterForClicks("AnyUp")`, attribute `step = 1`.
- Out of combat, the sequence is compiled into a flat list of steps. Each step is a table of secure attributes (`type`, `macrotext` or `macro`, `spell`, `unit`, ...). The list is serialised into a string with `\001`/`\002`/`|` separators, chunked at `SECURE_STEPS_PER_ITERATION = 253` steps, and loaded into the restricted environment once with `gsebutton:Execute("compressedspelllist = newtable([=======[...]=======]) ...")`.
- On each click, a snippet installed with `gsebutton:WrapScript(gsebutton, "OnClick", clickexecution)` runs in the restricted environment before the secure OnClick: it copies the current step's attributes onto the button (`self:SetAttribute(k, v)`), advances `step`/`iteration` with wraparound, bumps a click serial, and calls `self:CallMethod('UpdateIcon')`. The SecureActionButtonTemplate then performs the action (for `type=macro` with `macrotext`, `SECURE_ACTIONS.macro` calls `C_Macro.RunMacroText(text, button)`; VERIFIED in Blizzard `Blizzard_FrameXML/SecureTemplates.lua:447-461`).
- Step functions are resolved at compile time, not in combat: `Sequential` keeps order, `Priority` expands to 1, 1-2, 1-2-3 ..., `ReversePriority` the mirror, `Random` shuffles once (`GSE.processAction`, Storage.lua:4033-4093). `Pause` becomes N no-op `type=click` steps computed from GCD and click rate. `If` blocks evaluate a GSE variable (user Lua, run through `loadstring` with `setfenv`) out of combat to choose a branch.
- Modifier pause, reset modifiers and modifier snapshots are read in the snippet with `IsShiftKeyDown()` etc.; options are stamped into attributes because the restricted environment cannot read SavedVariables.
- Key-down handling: the executor pins `useOnKeyDown=false`; when the CVar `ActionButtonUseKeyDown` is `1`, the keybind targets a relay button `<name>_KD` registered `AnyDown` with `type=click`, `clickbutton=<executor>` (Storage.lua:4500-4540, `GSE.GetKeybindClickTarget`). Binding is `SetBindingClick` / `SetOverrideBindingClick` (GSE/API/Events.lua:1311-1338).
- Action-bar integration: GSE wraps Blizzard and third-party action buttons so a bar slot delegates to the sequence (`type=click`, `clickbutton=<executor>`). Its code comment says WrapScript on `OnClick` is still allowed on Blizzard action buttons "in recent patches" but on `OnEnter` it is blocked, so it uses `HookScript` there (Events.lua:980-1000). That restriction is GSE's own observation (REPORTED via comment; I did not find it in Blizzard Lua).
- Each block's macro text is held to 255 characters by GSE's editor and checker (`GSE_GUI/Editor_Tree.lua:973`, `GSE_Utils/Utils.lua:1023`). One GCD action per press is a game rule; GSE relies on it and states so in its README.

### Midnight 12.x (VERIFIED in repo history and TOC)

- TOC `## Interface: 11509, 16001, 20506, 50504, 120100, 120105`.
- A `Midnight` branch was merged 2026-01-20 (`2a84eec "#1830 Final Midnight Changes"`). What visibly changed: chat-link filters disabled when `GSE.GameMode >= 12` (`Serialisation.lua:404,459`, "#1830 Not compatible with Midnight"), `issecretvalue()` guard on GCD reads (`GSE_Utils/Events.lua:274`, "#1906 temp fix for secret haste"), and a `GameMode` flavour model. The secure step engine itself does not read combat state, which is why secret values do not break it (INFERRED from the snippet: it only reads its own attributes and modifier keys).

### Storage and import format (VERIFIED, `GSE/API/Serialisation.lua`, Blizzard `EncodingUtilDocumentation.lua`)

- `!GSE3!` + `C_EncodingUtil.EncodeBase64(C_EncodingUtil.CompressString(C_EncodingUtil.SerializeCBOR(tab)))`. `CompressString` defaults to `Enum.CompressionMethod.Deflate` (raw deflate) and `EncodeBase64` to the standard variant. Off-client decode is therefore: strip prefix, base64, `zlib.decompress(data, -15)`, CBOR decode. Note GSE's own decoder passes `string.sub(data, 6)`, i.e. it keeps the second `!`, and relies on the client's base64 decoder tolerating it.
- `!GSE3!+` is a different envelope: ChaCha20 under a symmetric key embedded in `GSE/API/Codec.lua`, used for "protected" sequences that gse.tools sells or shares with `noExport`. GSE decrypts but never produces it.
- Sequence variables are Lua source that GSE compiles with `loadstring` (Storage.lua:1433-1438). Importing GSE content therefore means importing executable Lua.

### Licence (VERIFIED, `LICENSE` and `git log -- LICENSE`)

- 2021-07-06 to 2026-04-15: MIT, "Copyright (c) 2016 Timothy Minahan" (commit `9c15b61`).
- Since 2026-04-15 (commit `5f293d0 "Update LICENSE"`): "Copyright (c) 2026 Timothy Minahan / All Rights Reserved." GitHub reports `NOASSERTION`. CurseForge lists "All Rights Reserved" (REPORTED via page fetch; latest file 3.3.35, 2026-10-16).
- The step engine (`WrapScript(gsebutton, ...)`, `compressedspelllist`) and the plain `!GSE3!` CBOR format already existed in the last MIT commit `d74485e` (VERIFIED with `git show 5f293d0^:...`). Copies of that commit stay under MIT; `Codec.lua` (the `!GSE3!+` cipher) did not exist then.
- Context (REPORTED, https://github.com/JesperLive/gse-companion-disclosure): the GSE author filed takedown claims against a GSE-compatible third-party addon (GRIP-EMS) in 2026; CurseForge closed the claim on 2026-08-27. The same repository documents that the GSE Companion desktop app shipped competitor-addon detection and an unsigned auto-updater. I have not verified any of it; it matters only as a signal that reusing GSE code or its protected format invites a dispute.

## 2. Macro Toolkit, Mega Macro, other macro managers, and the real length limit

### The macrotext limit is 255 characters, and chaining is blocked (VERIFIED primary source)

- https://github.com/Stanzilla/WoWUIBugs/issues/552 (read in full). In the 11.0.0 alpha Blizzard removed `macrotext` from secure buttons. Before that, the issue states `RunMacroText` "actually supports" 1023 characters. On 2024-06-26 Meorawr posted "I've been permitted to share the following update": `macrotext` restored; "The length of macros executable by "macrotext" is being restricted to 255 characters - the same length as normal macro bodies"; "All macros (both real and "macrotext" based ones) are being additionally restricted to remove the ability to chain macros. For example, this means that one macro cannot "/click" a button that itself would execute another macro"; "This change will additionally become present in Classic clients at a future unspecified date." On 2024-07-03: "Restored and hopefully working again in 11.0.2.55399 ... To the new limited functionality." (Meorawr is the engineer who answers for Blizzard in that tracker; that is how the thread presents him. I did not verify his employment independently.)
- Macro Toolkit confirms in code (VERIFIED): commit `92b26f3` (2024-07-10, "TWW: ... disable extending macros in TWW") set `MT.extendedMacrosSupported = select(4, GetBuildInfo()) < 110000` with the comment ""extended" macros will no longer work beyond the 255 character limit"; commit `a3e8075` (2024-09-28, "Add the warning that extended macros are no longer supported to classic era (blame blizzard :/)") narrowed it to `== 40400` ("right now, only cata 4.4.0 supports extended macros"). That check is stale today (no live client reports 40400), so in practice Macro Toolkit caps at 255 everywhere.
- Mega Macro confirms (VERIFIED): `src/constants.lua` went 1023 to 255 in `9e071f2` (2024-07-05, "Updated constants to reflect changes Blizzard have made to macros") and to 250 in `f15dbf9` (2024-07-31; the 5 characters are its own ID prefix). Its CurseForge page still advertises 1023 (REPORTED; stale copy).
- Blizzard code (VERIFIED 12.1.5): `RunMacroText(text, button)` has `HasRestrictions = true` and no documented length; the limit is enforced in C, so the exact truncation or rejection behaviour on a 256+ character macrotext is not observable from Lua source. I found no Blizzard statement of whether over-length text is truncated or refused. Unknown.
- Classic (VERIFIED in source): `classic` 5.5.4 and `classic_era` 1.15.9 SecureTemplates call `C_Macro.RunMacroText`, the 11.0 relocation, which WoWUIBugs #642 ties to the same change ("as part of the recent kerfuffle around macrotext buttons", fixed in 1.15.4.56573). Whether the 255 cap is active on each Classic flavour today is REPORTED only (Macro Toolkit's commit message for Era); I could not test it.
- Macro slot counts (VERIFIED, `MacroConstantsDocumentation.lua` 12.1.5): `MAX_ACCOUNT_MACROS = 120`, `MAX_CHARACTER_MACROS = 30`.

Conclusion: no addon technique extends an executed macro past 255 characters on Retail 12.x, and the old technique (a real macro that `/click`s a macrotext button) is the chaining that 11.0 removed.

### Macro Toolkit (VERIFIED code)

- Secure buttons `MTSB<n>`: `SecureActionButtonTemplate, SecureHandlerBaseTemplate`, `type=macro`, `macrotext`, `RegisterForClicks("AnyDown")`, and `pressAndHoldAction = '1'` with the comment "As of 10.0.2, setting the attribute pressAndHoldAction to 1 will allow you to force it to run on down, regardless of the ActionButtonUseKeyDown CVar. So now we can just `/click [btn:x] btnName 1` and it will work" (`modules/mainframe.lua:1101-1114`). Extended macros were real macros whose body was a `/click MTSB<n>` stub (MacroToolkit.lua:25, 68, 214-232), the chaining pattern now blocked.
- Other parts worth knowing: a macro parser and error checker (`modules/parser.lua` `ParseMacro`, `matchedBrackets`), a "Shorten" pass that strips comments and whitespace, rewrites `target=` to `@`, `modifier` to `mod`, etc. (`ShortenMacro`, parser.lua:522+), backups, sharing, a binding frame.
- Link insertion: it assigns the global `MacroFrameText = MacroToolkitText` so Blizzard's own `ChatFrameUtil.InsertLink` branch for the macro window writes into its box (MacroToolkit.lua:121-122, options.lua:77-80). Its own `ChatEdit_InsertLink` hook is commented out ("no longer required").
- Midnight: TOC uses `@toc-version-midnight@` and friends; CurseForge lists 12.1.5 and a file of 2026-10-14 (REPORTED).
- Licence: no LICENSE file in the repo; GitHub reports none. CurseForge lists "GNU General Public License version 2 (GPLv2)" (REPORTED via page fetch). Authors: Deepac, marciowb, The_Junksterr, Numy.

### Mega Macro (VERIFIED code)

- Technique: more slots, not longer macros. It partitions the native 120 + 30 slots into global, per-class, per-spec, per-character and per-character-per-spec scopes and rewrites the native macros with `EditMacro` when the class or spec changes (`src/engine/mega-macro-engine.lua`). Bodies over the native limit went to a `SecureActionButtonTemplate` "clicky" with `macrotext` behind a `/click` stub, which is dead since 11.0.
- Midnight patch `9f596ba` (2026-01-18) assigns Blizzard globals (`_G.ActionButton_ShowOverlayGlow`, `_G.ActionButton_HideOverlayGlow`, `_G.ClearChargeCooldown`) and fields in `C_Spell` and `C_SpellActivationOverlay`. Replacing Blizzard globals taints every secure caller that reads them (INFERRED from how taint works; not observed).
- Licence: none in repo (GitHub `null`); CurseForge "All Rights Reserved" (REPORTED).

### Others

- M6 (https://www.townlong-yak.com/addons/m6, foxlit): 8.10.1 dated 2026-10-07, compatible 12.1.0 and Classic flavours; "M6 macros can be as long as you want", "Some restrictions apply following patch 11.0.0"; licence "All Rights Reserved". REPORTED only: the download is gated and I did not read its code. How it executes long macros after 11.0 is unknown to me.
- MacroManager (https://www.curseforge.com/wow/addons/macromanager, grumpyaddons): GPLv2, v0.3.3 2026-10-04; native macros, account/character moves, chat sharing, offline snapshots. REPORTED.
- MacroBank (https://www.curseforge.com/wow/addons/macro-bank): abandoned. REPORTED. "BetterMacros": not found.
- wow-ai (https://github.com/chelinho139/wow-ai, MIT, created 2026-09-23): the closest prior art to Gnomecaster as a whole. Same transport idea (pixel strip read by screen capture out; a pool of load-on-demand slot addons in; an empty versus valid `.wav` as the cheap ready signal; README says 200 slots), targets WoW: Forever 1.60.1. Its macro path (VERIFIED `addon/WoWAI/WoWAI.lua:1695-1770`): refuses in combat; asks before replacing a different macro or when the body uses `/run`, `/script` or `/click`; closes Blizzard's `MacroFrame` first because it saves its edit box into the selected macro on hide; `EditMacro` or `CreateMacro` under `pcall`, retrying with a default icon; keeps one-level undo; then `PickupMacro(newIndex)` so the player drops it on a bar. Its primer states that Blizzard code calls `ChatFrameUtil.InsertLink`, not the `ChatEdit_*` alias.

## 3. Shift-clicking links into an addon EditBox

### What Blizzard does (VERIFIED 12.1.5 and Classic)

- `ChatFrameUtil.InsertLink(text)` is defined in `Blizzard_ChatFrameBase/Mainline/ChatFrameUtilOverrides.lua:14` (Classic: `.../Classic/ChatFrameUtilOverrides.lua:1` on both `classic` and `classic_era`). It inserts into `MacroFrameText` if that has focus, then the professions search box, the Communities box, the active chat edit box, the auction house search, and returns false otherwise.
- Callers use `ChatFrameUtil.InsertLink(...)` directly: `HandleModifiedItemClick` (`Blizzard_ItemButton/Mainline/ItemButtonTemplate.lua:379`), the spellbook (`Blizzard_SpellBookItem.lua:618-630`), flyouts, item refs and others.
- `ChatEdit_InsertLink = ChatFrameUtil.InsertLink;` exists only as a copied reference in `Blizzard_DeprecatedChatInfo/Deprecated_ChatFrame.lua:43`. A `hooksecurefunc("ChatEdit_InsertLink", f)` replaces that global alone, so it never sees Blizzard's calls. Real-world confirmation: https://github.com/b-morgan/Skillet-Classic/issues/228 (2026-02-05, "ChatEdit_InsertLink is now deprecated in 2.5.5 and doesn't work properly. ChatFrameUtil.InsertLink is the 1:1 replacement").

### What real addons do (VERIFIED code)

- Ace3 `AceGUI-3.0/widgets/AceGUIWidget-EditBox.lua:20-37`:

  ```lua
  if ChatFrameUtil and ChatFrameUtil.InsertLink then
      hooksecurefunc(ChatFrameUtil, "InsertLink", function(...) return _G.AceGUIEditBoxInsertLink(...) end)
  elseif ChatEdit_InsertLink then
      hooksecurefunc("ChatEdit_InsertLink", function(...) return _G.AceGUIEditBoxInsertLink(...) end)
  end
  -- AceGUIEditBoxInsertLink: for each widget, if editbox:IsVisible() and editbox:HasFocus() then editbox:Insert(text)
  ```
- wow-ai `WoWAI.lua:2289-2298`: the same shape, `if ui.input:HasFocus() then ui.input:Insert(text) end`.
- GitHub code search also lists the `ChatFrameUtil` hook in WeakAuras options widgets, ElvUI's Ace3 copy, TellMeWhen, Total RP 3, Auctionator (search listing only; not read).
- Macro Toolkit's alternative (reassigning the global `MacroFrameText`) is the only pattern found that writes a Blizzard-read global.

### Taint

- `hooksecurefunc` is a post-hook: the original runs first and its return value is kept, so the secure caller is not tainted by the hook (standard WoW behaviour; consistent with Ace3 using it in every AceGUI edit box). I found no report of taint caused by this hook pattern. That is absence of evidence from a short search (WoWUIBugs and GitHub issues for "InsertLink taint"), not proof.
- Side effect (INFERRED from the Blizzard function): when a chat edit box is also active, Blizzard inserts there and the hook inserts into ours, so the link lands twice. Ace3 accepts that.
- Writing `MacroFrameText` from addon code taints that global, and Blizzard reads it inside `InsertLink`, which runs from secure click handlers (INFERRED; no report found).

## 4. Talent loadouts, Edit Mode layouts, Cooldown Manager layouts

### Talents (VERIFIED)

- Blizzard path (`Blizzard_PlayerSpells/ClassTalents/Blizzard_ClassTalentImportExport.lua:180-234`): parse the string with `ExportUtil.MakeImportDataStream`, check header (`bitWidthHeaderVersion = 8`) against `C_Traits.GetLoadoutSerializationVersion()`, spec against `PlayerUtil.GetCurrentSpecID()`, tree hash against `C_Traits.GetTreeHash` (an all-zero hash skips the check "to allow third-party sites"), convert to `ImportLoadoutEntryInfo`, call `C_ClassTalents.ImportLoadout(configID, entries, name, importText)`.
- API flags in 12.1.5 docs: `ImportLoadout`, `LoadConfig`, `CommitConfig`, `C_Traits.PurchaseRank`, `SetSelection` carry no `HasRestrictions`; `C_ClassTalents.SwitchToLoadoutByIndex` and `SwitchToLoadoutByName` do (`HasRestrictions = true`). All show `SecretArguments = "AllowedWhenUntainted"`, which governs passing secret values, not calling from addon code.
- Talent Loadout Manager (Numy): parses strings itself (`core/ImportExportV2.lua`, `ConvertToImportLoadoutEntryInfo`), applies through `C_Traits.SetSelection` / `PurchaseRank` / `C_ClassTalents.CommitConfig` (`TalentLoadoutManager.lua:881-1084`), switches with `SwitchToLoadoutByIndex` when present (`BlizzardLoadoutChangerV2.lua`, file guard "delete the check in 12.0.5"). The older changer says Blizzard does not fire `SELECTED_LOADOUT_CHANGED` for addon changes "and we can't do that without tainting all the things", and pokes the talent frame's dropdown to resync. A whole `core/ReduceTaint.lua` module exists to stop taint from the talent frame spreading to action bars and the cast bar ("ToggleTalentFrame starts of with a talentContainerFrame:SetInspecting call, which has a high likelihood of tainting execution").
- Licence: TLM has no LICENSE file; CurseForge "All Rights Reserved" (REPORTED), v1.6.36 2026-10-14, 12.1.5.

### Edit Mode (VERIFIED)

- API: `C_EditMode.ConvertStringToLayoutInfo`, `ConvertLayoutInfoToString`, `GetLayouts`, `SaveLayouts`, `SetActiveLayout`, `SetAccountSetting`, `OnLayoutDeleted`; none flagged `HasRestrictions` in 12.1.5. Blizzard's import dialog uses `ConvertStringToLayoutInfo` (`Blizzard_EditMode/Shared/EditModeDialogs.lua:359,378`).
- LibEditModeOverride (plusmouse, MIT, "Copyright (c) 2022-2026 plusmouse", TOC 110205, 120000): edits the `C_EditMode.GetLayouts()` table, `C_EditMode.SaveLayouts(layoutInfo)`, then makes Blizzard re-apply by `ShowUIPanel(EditModeManagerFrame); HideUIPanel(EditModeManagerFrame)`, refusing in combat. If the dropdown list is already tainted it first shows and hides `AddonList` (an existing taint workaround). It calls `EditModeManagerFrame:ReconcileWithModern(layout)` and `EditModePresetLayoutManager:GetCopyOfPresetLayouts()` from addon code.
- Taint reports: WoWUIBugs #261 (2022, addon-registered systems tainting Edit Mode; "generally resolved in 10.0.2.47067"); #889 (2026-10-13, Forever beta: any earlier taint makes exiting Edit Mode error on a secret status-bar colour in `CompactUnitFrame_UpdateHealthColor`). Meorawr's answer on #889: "It's an addon's responsibility to not taint secure functionality such as this." That is the current Blizzard stance for 12.x-era secret values.
- Edit Mode Expanded (teelolws): "All Rights Reserved", library part redistributable with credit (REPORTED, CurseForge).

### Cooldown Manager (VERIFIED Blizzard code; no addon read)

- API: `C_CooldownViewer.GetLayoutData()` and `SetLayoutData(data)` move the whole serialised store, not one layout. Blizzard's mixin caches it (`CooldownViewerSettingsDataStoreSerialization.lua:57-79`, `cachedSerializedData`).
- String format: `<version>|<payload>`, payload = Base64(Deflate(CBOR)) through `C_EncodingUtil` (same file, lines 256-281 and 320-375). Import from text goes through `CooldownViewerLayoutManagerMixin:CreateLayoutsFromSerializedData(text)` (`CooldownViewerSettingsLayoutManager.lua:936`), with a layout-count limit (`AreLayoutsFullyMaxed`).
- Calling `SetLayoutData` directly would bypass the mixin's cache and its layout bookkeeping (INFERRED from the code). I found no addon whose code I could read that applies CDM strings; Cooldown Stash describes storing and handing back Blizzard's string (REPORTED, https://www.curseforge.com/wow/addons/cooldown-stash). No taint report found.

## 5. /click on Retail 12.x and Classic

All VERIFIED in Blizzard source unless marked.

- `/click` (12.1.5 `Blizzard_ChatFrameBase/Shared/SlashCommands.lua:725-740`): parses `name [mouseButton [down]]`, `mouseButton` defaults to `LeftButton`, `down = StringToBoolean(down or "", false)`, then `button:Click(mouseButton, down)` only if `IsObjectType("Button")`, `not HasAccessConstraints()` and `not HasAnyForbiddenAspects(Enum.ForbiddenAspect.ScriptedInput)`. The `type=click` secure action has the same guard (`SecureTemplates.lua:560-566`).
- That guard is new in 12.1.0 (69214): the diff replaced `not button:IsForbidden()` with the two checks and added `ForbiddenAspect` (`ScriptedInput = 64`, "Restricts APIs that trigger synthetic input interactions on objects from Lua scripts"). Which Blizzard frames carry `ScriptedInput` is decided in C and not visible in Lua; `HasAccessConstraints` returns a secret value for `ObjectSecurity`. Classic 5.5.4 and Era 1.15.9 still use `IsForbidden()` only.
- Key-down interplay (`SecureActionButton_OnClick`, SecureTemplates.lua:805-830): the action fires when `(down and useOnKeyDown) or (not down and not useOnKeyDown)`; `useOnKeyDown` is the `useOnKeyDown` attribute or else CVar `ActionButtonUseKeyDown`. With the default CVar `1`, `/click X` (down=false) does nothing on a secure button that follows the CVar; `/click X LeftButton 1` works if the button is registered for `LeftButtonDown`. History: WoWUIBugs #283 (fixed 10.0.2: `/click name button 0|1` controls `down`), #317 (the CVar trap), #610 (2024-07-30, "[TWW] Non-macro SecureActionButton not clickable by macro"; resolved by `RegisterForClicks("AnyDown","AnyUp")` plus `pressAndHoldAction=true` and `typerelease`).
- Blizzard action buttons: `ActionBarActionButtonMixin:OnLoad` sets `type=action`, `typerelease=actionrelease` and `RegisterForClicks("AnyUp", "LeftButtonDown", "RightButtonDown")` (`Blizzard_ActionBar/Shared/ActionButton.lua:445-460`). So `/click ActionButton1 LeftButton 1` matches the default CVar (INFERRED from code). Keybinds do not use `/click`: `ActionButtonDown/Up` call `TryUseActionButton` with `isKeyPress=true` (ActionButton.lua:109-162). `ExtraActionButtonKey` does the same for `ExtraActionButton<n>` (`ExtraActionBar.lua:63-80`).
- Chaining (WoWUIBugs #552, quoted above): since 11.0.2 a macro cannot `/click` a button that would itself run a macro. So `/click ActionButton1` from a macro is fine when slot 1 holds a spell or item, and blocked when it holds a macro (INFERRED from the stated rule; not tested). Whether `ActionButtonN` or `ExtraActionButton1` carry `ScriptedInput` on 12.1.x is unknown; only a live client can show it.

---

## Recommendations

| Component | Prior art | Licence | Recommendation | Why |
|---|---|---|---|---|
| Macros longer than 255 characters | Macro Toolkit "extend", Mega Macro clickies, M6 | GPLv2 (MT, store page); ARR (Mega Macro, M6) | Avoid | Blizzard capped macrotext at 255 and blocked `/click` chaining in 11.0.2 (WoWUIBugs #552); both addons now cap at 255/250 in code. Keep `Actions.lua`'s 255 cap and make the model fit it. |
| Fitting into 255 | Macro Toolkit `ShortenMacro` (parser.lua) | GPLv2 (REPORTED) | Take idea | The rewrites (`target=` to `@`, strip comments and spaces, `modifier` to `mod`) are a short list; implement in the companion so the sanitizer and prompt share one rule set. Copying the Lua would pull GPLv2 into a repo with no licence chosen yet. |
| Macro syntax checking | Macro Toolkit `ParseMacro`, GSE sequence checker | GPLv2; ARR | Take idea | Bracket balance and unknown-command checks belong in `prompt.sanitize()` next to `MACRO_COMMANDS`, the single source. |
| More macros than slots | Mega Macro per-spec hot swap; GSE/Macro Toolkit secure buttons bound with `SetBindingClick` | ARR; ARR (GSE now) | Take idea, later | Two legal routes: rewrite native slots on spec change (`EditMacro`, out of combat), or a slotless secure `macrotext` button bound straight to a key (no chaining because no macro clicks it). Both are Blizzard API patterns, not copied code. Complexity only if users hit the 120 + 30 limit. |
| Sequences (GSE-style step buttons) | GSE engine: `SecureActionButtonTemplate` + `WrapScript` OnClick snippet stepping attributes | ARR since 2026-04-15; MIT up to `d74485e` | Take idea, defer | The mechanism is small and documented Blizzard API (`WrapScript`, `Execute`, attributes). Do not copy GSE code: licence changed and the author pursues takedowns. Needs its own design pass (key-down relay, combat rebuild rules) and a real-client test. |
| GSE string import | `!GSE3!` = Base64(Deflate(CBOR)) | Format; ARR code | Take idea (read-only converter) | Decode in the companion (`zlib` raw deflate plus a CBOR reader; a CBOR dependency must pass the 14-day cooldown and the lock check), convert macro blocks to native macros through the normal sanitizer. Never run GSE Variables (they are Lua for `loadstring`). Refuse `!GSE3!+`: decrypting it uses GSE's embedded key to bypass its protection. |
| Shift-click links into the panel | Ace3 EditBox, wow-ai | Ace3 BSD-style with "no stand-alone redistribution" clause; wow-ai MIT | Take idea (5 lines, own code) | `hooksecurefunc(ChatFrameUtil, "InsertLink", f)` with a `ChatEdit_InsertLink` fallback, insert only when our box `HasFocus()`. Verified that Blizzard calls the `ChatFrameUtil` field on Retail and both Classic branches. Avoid Macro Toolkit's `MacroFrameText` reassignment. |
| Macro apply flow | wow-ai `InstallMacro` | MIT | Take part (with credit) or idea | Close `MacroFrame` before `EditMacro`, one-level undo, confirm on replace, `PickupMacro` to cursor as an alternative to placing on bars. Small, MIT, directly useful. |
| Talent loadout strings | Blizzard `ClassTalentImportExportMixin`; TLM | Blizzard code; TLM ARR | Take idea | Parse and validate the string in the companion (header, spec), then either hand it to the player to paste in Blizzard's import box (no taint) or call `C_ClassTalents.ImportLoadout` out of combat. TLM shows the taint cost of driving the talent UI from addon code; do not touch `PlayerSpellsFrame`. Avoid `SwitchToLoadoutBy*` (restricted). |
| Edit Mode layouts | LibEditModeOverride | MIT | Take whole (embed with credit), if the feature is built | Only proven non-reload apply path (`SaveLayouts` then Blizzard re-applies via Show/Hide `EditModeManagerFrame`), out of combat. #889 says taint here is the addon's problem, so it needs a live-client check. |
| Cooldown Manager layouts | Blizzard `CooldownViewerLayoutManagerMixin`; no readable addon | Blizzard code | Take idea | Validate the `<version>|Base64(Deflate(CBOR))` string in the companion; let the player import through Blizzard's dialog. Do not call `C_CooldownViewer.SetLayoutData`: it replaces the whole store and bypasses Blizzard's cache. |
| `/click` in generated macros | Blizzard SlashCommands, Macro Toolkit comment, WoWUIBugs #283/#317/#610 | n/a | Take idea (prompt and sanitizer rules) | Emit `/click Name LeftButton 1` when targeting secure buttons under the default CVar; never `/click` a button that holds or runs a macro (chaining); treat Blizzard buttons as possibly blocked by `ScriptedInput` on 12.1.x until tested in game. Today `MACRO_COMMANDS` excludes `/click` entirely, which is the safe default. |
| Whole-product reference | wow-ai | MIT | Take idea | Same file-system transport; compare its slot pool (200), `.wav` signal and macro UX with Gnomecaster's when deciding the next steps. |

Declined: copying any GSE, Mega Macro, TLM or Edit Mode Expanded code (all "All Rights Reserved"), and Mega Macro's Midnight shim (it overwrites Blizzard globals, which taints secure callers).

## Open questions only a real client can answer

1. Does a 256+ character `macrotext` truncate or fail on 12.1.5, and on each Classic flavour?
2. Do `ActionButtonN` and `ExtraActionButton1` carry `ScriptedInput` on 12.1.x (does `/click ActionButton1 LeftButton 1` still fire)?
3. Does the `ChatFrameUtil.InsertLink` post-hook ever insert twice in practice with the chat box open?
4. Does LibEditModeOverride's Show/Hide apply cause the #889 error on Retail 12.1.5 when Gnomecaster has tainted anything earlier?
