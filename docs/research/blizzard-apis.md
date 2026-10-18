# Blizzard API building blocks for Gnomecaster (12.1.5)

Source: github.com/Gethe/wow-ui-source at `18c6d677b605b312f3d813d498404631fb941977` ("12.1.5 (70391)", 2026-10-13), checked out at `~/.cache/gnomecaster/wow-ui-source`. All `file:line` references without a prefix are relative to `Interface/AddOns/` in that checkout. API flags come from `Blizzard_APIDocumentationGenerated/*.lua` (abbreviated `Doc/` below).

Labels:
- VERIFIED: read in the Lua or XML source or the generated docs at that commit.
- INFERRED: not visible in Lua (C-side behaviour, runtime only) or taken from a secondary source; reasoning given.

Secondary sources used, each fetched 2026-10-17 and cached under `research/`:
- `xml/`: XML files from raw.githubusercontent.com at the commit above (the cache holds Lua only).
- `xml/Blizzard_FrameXML_Bindings_70391.xml`: the main key binding file. It is not in Gethe's export since 10.2.7 (commit `f5ad9406`, 2024-05-07, deleted `Interface/FrameXML/Bindings.xml`; no replacement path exists in the 12.1.5 tree). Reconstructed from townlong-yak.com's FrameXML viewer page for `Blizzard_FrameXML/Bindings.xml`, build 12.1.5.70448, which the page labels "unchanged since 12.1.5.70391" (our build). Raw download there sits behind a JavaScript challenge, so the file was rebuilt from the viewer's numbered lines (1798 lines, parsed cleanly as XML). Treat line numbers in `bindings.tsv` for that file as townlong-yak's line numbers.
- `ketho/CVars.lua`: Ketho/BlizzardInterfaceResources `live` branch, CVar dump from 12.1.0 (69283). Used only to check that a CVar exists and to read its "secure" flag; it is one minor version older than our build.
- `ketho/GlobalStrings_enUS.lua`: same repo, 12.1.0 (69587). Used for slash command strings and binding labels.

Generated data files:
- `docs/research/settings-cvars.tsv`: 361 rows, every settings registration in the options panel (step 3a).
- `docs/research/bindings.tsv`: 447 rows, every `<Binding>` and `<ModifiedClick>` (step 3b).

---

## 1. Links

### 1.1 The shift-click path (VERIFIED)

Every link-producing click ends in `ChatFrameUtil.InsertLink(text)`, defined once for Mainline at `Blizzard_ChatFrameBase/Mainline/ChatFrameUtilOverrides.lua:14-78`. Order of destinations inside it:

1. `MacroFrameText` has focus (`:19-39`): the macro branch, see 1.4.
2. Professions recipe search box has focus and the text is an item link (`:41-50`): sets the item name.
3. `CommunitiesFrame.ChatEditBox` has focus (`:51-54`): `Insert(text)`.
4. An active chat edit box exists (`ChatFrameUtil.GetActiveWindow()`, which is `ACTIVE_CHAT_EDIT_BOX`, `Blizzard_ChatFrameBase/Shared/ChatFrameUtil.lua:496-498`): `Insert(text)` and `SetFocus()` (`:56-61`).
5. Auction House visible (`:62-75`): item or battle pet name into its search.
6. Otherwise returns `false` (`:77`).

Callers per link kind:

| Kind | Click handler | What it passes |
|---|---|---|
| Items in bags | `Blizzard_UIPanels_Game/Mainline/ContainerFrame.lua:1605` calls `HandleModifiedItemClick(C_Container.GetContainerItemLink(...))` | item link |
| Equipped items | `Blizzard_UIPanels_Game/Mainline/PaperDollFrame.lua:1689`, same function with `GetInventoryItemLink` | item link |
| (shared) | `HandleModifiedItemClick`, `Blizzard_ItemButton/Mainline/ItemButtonTemplate.lua:367-399`: if `IsModifiedClick("CHATLINK")` then `ChatFrameUtil.InsertLink(link)` (`:379`); if that returns false it falls through to DRESSUP and EXPANDITEM | |
| Links clicked in chat | `SetItemRef`, `Blizzard_UIPanels_Game/Mainline/ItemRef.lua:6-27`: modified click goes to `HandleModifiedItemClick(GetFixedLink(text))` (`:17-19`) | the clicked link |
| Spellbook | `SpellBookItemMixin:OnModifiedIconClick`, `Blizzard_PlayerSpells/SpellBook/Blizzard_SpellBookItem.lua:604-637`. If `MacroFrameText:HasFocus()`: plain spell name, `name(subName)` when a subname exists, passives skipped (`:612-622`). Otherwise trade skill link or `C_SpellBook.GetSpellBookItemLink` (`:625-630`). Also fires `EventRegistry` "SpellBookItemMixin.OnModifiedClick" first (`:609`) | name or spell link |
| Talents (spend buttons) | `Blizzard_SharedTalentUI/Blizzard_TalentButtonSpend.lua:12-14`: `C_Spell.GetSpellLink(self:GetSpellID())`; also `Blizzard_TalentButtonSelect.lua:78`, `Blizzard_SharedTalentSelectionTemplates.lua:204` | spell link, also when the macro frame is focused |
| Talent loadout | `Blizzard_PlayerSpells/ClassTalents/Blizzard_ClassTalentsFrame.lua:553-558`; link built at `:466` as `LinkUtil.FormatLink(LinkTypes.TalentBuild, text, specID, level, exportString)`; falls back to `ChatFrameUtil.OpenChat` | `talentbuild` link |
| Mounts | `MountListItem_OnClick` / `MountListDragButton_OnClick`, `Blizzard_Collections/Mainline/Blizzard_MountCollection.lua:914-949`. If `MacroFrame:IsShown()` (shown, not focused): `C_Spell.GetSpellName(spellID)`; otherwise `C_MountJournal.GetMountLink(spellID)` | name or mount link |
| Toys | `ToySpellButton_OnModifiedClick`, `Blizzard_Collections/Mainline/Blizzard_ToyBox.lua:288-295`: `C_ToyBox.GetToyLink(itemID)` | item link |
| Battle pets | `PetJournalListItemMixin:OnClick`, `Blizzard_Collections/Shared/Blizzard_PetCollection.lua:968-976`: nothing at all while `MacroFrame` is shown ("Macros are not yet supported", `:972`); else `C_PetJournal.GetBattlePetLink(petID)` | battlepet link |
| Achievements | `AchievementTemplateMixin:ProcessClick`, `Blizzard_AchievementUI/Mainline/Blizzard_AchievementUI.lua:1101-1112`: `GetAchievementLink(id)` | achievement link |
| Quests (log) | `QuestMapLogTitleButton_OnClick`, `Blizzard_UIPanels_Game/Mainline/QuestMapFrame.lua:2302-2305` | via `TryInsertQuestLinkForQuestID` |
| Quests (tracker) | `Blizzard_ObjectiveTracker/Blizzard_QuestObjectiveTracker.lua:51-54`, bonus objectives `Blizzard_BonusObjectiveTracker.lua:63`, world quests on the map `Blizzard_SharedMapDataProviders/WorldQuestDataProvider.lua:434`, POI buttons `Blizzard_POIButton/POIButton.lua:459` | same |

`ChatFrameUtil.TryInsertQuestLinkForQuestID(questID)` is `TryInsertChatLink(GetQuestLink(questID))` (`Blizzard_ChatFrameBase/Shared/ChatFrameUtil.lua:616-618`), and `TryInsertChatLink` checks `IsModifiedClick("CHATLINK")` before calling `InsertLink` (`:610-614`). `ChatFrameUtil.LinkItem` (`:597-608`) calls `InsertLink` only when a chat box is active, else `OpenChat`.

Total: 95 call sites of `ChatFrameUtil.InsertLink(` in the 12.1.5 Lua (grep count, all flavors).

### 1.2 Link string formats

VERIFIED from Lua:
- Generic shape: `|H<type>:<options>|h<display>|h`, usually wrapped in `|c...|r`. `LinkUtil.FormatLink` builds it (`Blizzard_SharedXML/LinkUtil.lua:69-77`); `LinkUtil.ExtractLink(text)` returns `linkType, linkOptions, displayText` with the pattern `|H([^:]*):([^|]*)|h(.*)|h` (`:95-101`); `LinkUtil.SplitLink` (`:85-87`), `LinkUtil.SplitLinkOptions` (`:89-91`).
- Link type names: `LinkTypes` table, `LinkUtil.lua:1-65` (`item`, `spell`, `battlepet`, `talentbuild`, `talent`, `worldmap`, ...). `quest`, `achievement`, `trade`, `enchant`, `instancelock`, `journal` are recognised in `GetFixedLink` (`Blizzard_UIPanels_Game/Mainline/ItemRef.lua:29-78`) but are not in `LinkTypes`; they are handled in C through `ItemRefTooltip:SetHyperlink`.
- Item: first option is the item ID: `GetItemInfoFromHyperlink` matches `|Hitem:((%d+).-)|h` (`LinkUtil.lua:123-128`).
- Achievement: first option is the achievement ID, third is completion (`GetAchievementInfoFromHyperlink`, `LinkUtil.lua:130-136`).
- Battle pet: `speciesID:level:breedQuality:maxHealth:power:speed:battlePetID` (`Blizzard_UIPanels_Game/Mainline/ItemRefHandlers.lua:104-105`).
- Talent build: `specID:level:exportString` (`Blizzard_ClassTalentsFrame.lua:466`; handler `ItemRefHandlers.lua:259-264` passes the options to `PlayerSpellsUtil.InspectLoadout`).
- Spell: `spell:<id>...`; the only Lua parser is `link:match("spell:(%d+)")` in `Blizzard_PTRFeedback/Blizzard_PTRFeedback_Tooltips.lua:35`.

INFERRED: the remaining fields of item, spell and quest links (enchant, gems, bonus IDs, quest level) are produced in C and not parsed anywhere in the 12.1.5 Lua. The mount link type returned by `C_MountJournal.GetMountLink` (documented return name `mountCreatureDisplayInfoLink`, `Doc/MountJournalDocumentation.lua:325`) is not parsed in Lua either; treat its type as unknown until seen in game.

### 1.3 Parsing IDs (VERIFIED as APIs; behaviour on links is documented where stated)

- Any link: `LinkUtil.ExtractLink`, then `tonumber` on the first option.
- Item: `GetItemInfoFromHyperlink(link)` (`LinkUtil.lua:123`), or `C_Item.GetItemInfoInstant(link)` (first return `itemID`; `Doc/ItemDocumentation.lua:637`).
- Spell: `C_Spell.GetSpellIDForSpellIdentifier(link)`, documented as "Meant primarily for getting a spell id from a spell name or link; Returns nothing if spell does not exist" (`Doc/SpellDocumentation.lua:358`).
- Achievement: `GetAchievementInfoFromHyperlink` (`LinkUtil.lua:130`).
- Pet: options split as in `ItemRefHandlers.lua:105`.

### 1.4 How the macro frame turns a link into a line (VERIFIED)

`ChatFrameUtilOverrides.lua:19-39`, only while `MacroFrameText:HasFocus()`:
- If the text contains `item:`, `item = C_Item.GetItemInfo(text)` (the item name; `:21-23`).
- At the start of a line (cursor 0 or after `\n`, `:25`): an item with an on-use spell (`C_Item.GetItemSpell(text)`) becomes `SLASH_USE1 .. " " .. name .. "\n"`; an item without one becomes `SLASH_EQUIP1 .. " " .. name`; anything else becomes `SLASH_CAST1 .. " " .. text .. "\n"` (`:26-34`).
- Mid-line: inserts the item name or the raw text (`:36`).
- Spellbook and mounts pre-convert to a plain name when the macro frame is up (1.1), so they become `/cast Name`. Talent buttons do not, so a talent shift-click into the macro frame inserts `/cast ` followed by the full spell hyperlink, and `MacroFrameMixin:SaveMacro` stores `MacroFrameText:GetText()` verbatim (`Blizzard_MacroUI/Blizzard_MacroUI.lua:340-348`). Toys arrive as item links and become `/use <toy name>` when the toy has an item spell. Pets insert nothing.
- `MacroFrameText` is `letters="255"` with `countInvisibleLetters="true"` (`xml/Interface/AddOns/Blizzard_MacroUI/Blizzard_MacroUI.xml:121`), so hidden link escape codes count against 255.

Relevance: `Actions.lua:95-108` (`macroBodyProblem`) rejects any `|`, so a model-proposed body that carries a hyperlink is refused. That matches what is safe to store, since the macro frame's own talent path can save hyperlinks into a body.

### 1.5 Can an addon EditBox hold hyperlinks?

- VERIFIED: Blizzard inserts raw link strings into ordinary, non-chat EditBoxes: `CommunitiesFrame.ChatEditBox:Insert(text)` (`ChatFrameUtilOverrides.lua:52`), `MacroFrameText:Insert(link)` for recipe links with a letter-count check (`Blizzard_Professions/Blizzard_ProfessionsCrafting.lua:58-61`). The EditBox API has both `GetText` and `GetDisplayText` (`Doc/SimpleEditBoxAPIDocumentation.lua`), and `SetCountInvisibleLetters`, which only make sense if markup is held raw and rendered differently. `Insert` has `SecretArguments = "AllowedWhenUntainted"` and no other restriction (`SimpleEditBoxAPIDocumentation.lua:446-449`).
- INFERRED: an addon-created EditBox behaves the same (same widget type; no documented restriction). Gnomecaster's input (`UI.lua:310-315`, `InputBoxTemplate`, `SetMaxLetters(400)`) does not call `SetCountInvisibleLetters(true)`, so if letters are counted like `MacroFrameText` without that flag, link markup would not count against 400 while it does count against the 2400-byte beacon payload. To be checked in game.

### 1.6 Is `hooksecurefunc(ChatFrameUtil, "InsertLink", f)` the right hook?

VERIFIED facts:
- Every Blizzard caller looks the function up as a table field at call time (`ChatFrameUtil.InsertLink(`; 1.1), so a hook on the table field sees all of them.
- `ChatEdit_InsertLink` is only an alias captured at load, `ChatEdit_InsertLink = ChatFrameUtil.InsertLink` (`Blizzard_DeprecatedChatInfo/Deprecated_ChatFrame.lua:43`), inside a file that returns early unless the CVar `loadDeprecationFallbacks` is set (`:4-6`; default "1" in the 12.1.0 dump). A hook on `ChatFrameUtil.InsertLink` therefore misses third-party addons that still call `ChatEdit_InsertLink`; hooking both names covers them. No 12.1.5 Blizzard code calls `ChatEdit_InsertLink(` (grep count 0).
- A post-hook cannot change the return value. When no chat box is active and none of the special boxes has focus, the original returns `false` (`:77`); callers then do their own fallback: `HandleModifiedItemClick` continues to DRESSUP/EXPANDITEM (`ItemButtonTemplate.lua:383-397`), the loadout link opens chat (`ClassTalentsFrame.lua:555-556`), most callers ignore the result.
- If a chat edit box is active, the original already inserted the link there and focused it (`:56-61`) before the hook runs. A hook should insert only when its own box has focus, and can skip when `ChatFrameUtil.GetActiveWindow()` is non-nil to avoid a double insert.
- The hook receives plain spell names (not links) from the spellbook only while `MacroFrameText` has focus, and from mounts while `MacroFrame` is shown (1.1). Our box having focus means `MacroFrameText` does not, so spellbook clicks arrive as links; mount clicks arrive as names whenever the macro window is open.
- Alternative that was considered and rejected: `ChatFrameUtil.SetChatFocusOverride(editBox)` (`Blizzard_ChatFrameBase/Shared/ChatFrameUtil.lua:171-181`) redirects only `OpenChat`, which replaces text with `SetText` (`:433-441`), not `InsertLink`, and it writes a global (`CHAT_FOCUS_OVERRIDE`) that chat code reads.

INFERRED: `hooksecurefunc` leaves the original secure and runs the hook afterwards, so it does not taint `InsertLink` callers. This is the documented purpose of `hooksecurefunc` and Blizzard's own code uses it (14 call sites in 12.1.5 Lua, e.g. `Blizzard_PTRFeedback/Blizzard_PTRFeedback_Tooltips.lua:30`), but taint behaviour cannot be proven from source.

---

## 2. Validation APIs for macro content

"Doc flags" lists every `Requires*`, `Secret*`, `HasRestrictions` line of the entry. `SecretArguments = "AllowedWhenUntainted"` restricts passing secret values in from tainted code; it says nothing about returns. None of the functions below carries `SecretReturns` or a `SecretWhen*` flag except where noted, so per the docs none returns secret values (VERIFIED for documented ones). Undocumented globals: no flags exist to read (INFERRED unknown).

### 2.1 Spells (VERIFIED, `Doc/SpellDocumentation.lua`, `Doc/SpellBookDocumentation.lua`)

| API | Line | Flags | Use |
|---|---|---|---|
| `C_Spell.DoesSpellExist(spellIdentifier)` | Spell:22 | AllowedWhenUntainted | "true if the spell exists, regardless of whether the player has learned it" |
| `C_Spell.GetSpellInfo(spellIdentifier)` | Spell:375 | MayReturnNothing; AllowedWhenTainted | returns `SpellInfo`, nil if not found |
| `C_Spell.GetSpellName(spellIdentifier)` | Spell:477 | MayReturnNothing; AllowedWhenTainted | localized name from an ID |
| `C_Spell.GetSpellIDForSpellIdentifier(spellIdentifier)` | Spell:358 | MayReturnNothing; AllowedWhenTainted | ID from name or link |
| `C_Spell.GetSpellLink(spellIdentifier, glyphID)` | Spell:408 | MayReturnNothing; AllowedWhenTainted | |
| `C_Spell.IsSpellUsable(spellIdentifier)` | Spell:911 | AllowedWhenTainted | castable now |
| `C_Spell.GetOverrideSpell(...)` / `GetBaseSpell(...)` | Spell:165 / :66 | Untainted / Tainted | talent overrides |
| `C_Spell.GetSpellCharges` | Spell:250 | `SecretWhenCooldownsRestricted` | the one secret-returning entry in this list |
| `C_SpellBook.IsSpellKnown(spellID, spellBank)` | SpellBook:684 | AllowedWhenUntainted | "can also return true for spells that aren't in the spellbook" |
| `C_SpellBook.IsSpellInSpellBook(spellID, spellBank, includeOverrides)` | SpellBook:666 | AllowedWhenUntainted | "can also return true for spells that aren't known, such as override spells" |
| `C_SpellBook.IsSpellKnownOrInSpellBook(...)` | SpellBook:701 | AllowedWhenUntainted | |
| `C_SpellBook.FindSpellBookSlotForSpell(spellIdentifier, includeHidden, includeFlyouts, includeFutureSpells, includeOffSpec)` | SpellBook:63 | MayReturnNothing; AllowedWhenUntainted | find by name or ID |
| `C_SpellBook.GetSpellBookItemInfo` / `GetSpellBookItemLink` | SpellBook:270 / :304 | MayReturnNothing; AllowedWhenUntainted | |

`IsPlayerSpell`, `IsSpellKnown`, `IsSpellKnownOrOverridesKnown` exist only as deprecation fallbacks wrapping the `C_SpellBook` calls (`Blizzard_DeprecatedSpellBook/Deprecated_SpellBook.lua:11-26`), loaded only when `loadDeprecationFallbacks` is set (`:4-6`), and no 12.1.5 Blizzard code calls them. Use `C_SpellBook.IsSpellKnown(id, Enum.SpellBookSpellBank.Player)` instead (that is exactly what the fallback does, `:11-14`).

INFERRED: which spells `GetSpellInfo(name)` resolves by name (known only, or any) is C-side; the docs only say "nil if spell is not found". Validate names by round-tripping `GetSpellIDForSpellIdentifier(name)` then `C_SpellBook.IsSpellKnown(id, ...)`.

### 2.2 Items (VERIFIED, `Doc/ItemDocumentation.lua`, `Doc/ContainerDocumentation.lua`)

| API | Line | Flags |
|---|---|---|
| `C_Item.GetItemInfoInstant(itemInfo)` returns itemID, type, subtype, equipLoc, icon, classID, subClassID | 637 | MayReturnNothing; AllowedWhenUntainted |
| `C_Item.GetItemInfo(itemInfo)` (18 returns, name first) | 604 | MayReturnNothing; AllowedWhenUntainted |
| `C_Item.GetItemIDForItemInfo(itemInfo)` | 559 | AllowedWhenUntainted |
| `C_Item.GetItemNameByID(itemInfo)` | 824 | AllowedWhenUntainted |
| `C_Item.DoesItemExistByID(itemInfo)` | 124 | AllowedWhenUntainted |
| `C_Item.IsItemDataCachedByID` / `RequestLoadItemDataByID` | 1483 / 1673 | AllowedWhenUntainted |
| `C_Item.GetItemSpell(itemInfo)` returns spellName, spellID (on-use spell) | 948 | MayReturnNothing; AllowedWhenUntainted |
| `C_Item.IsEquippedItem(itemInfo)` | 1302 | AllowedWhenUntainted |
| `C_Item.GetItemCount(itemInfo, includeBank, includeUses, includeReagentBank, includeAccountBank)` | 429 | AllowedWhenUntainted |
| `C_Item.IsUsableItem(itemInfo)` | 1590 | AllowedWhenUntainted |
| `C_Container.GetContainerItemInfo(bag, slot)` / `GetContainerItemLink` / `GetContainerNumSlots` | Container:192 / 209 / 313 | AllowedWhenUntainted |

`GetInventoryItemID` and `GetInventoryItemLink` are undocumented globals that Blizzard calls (14 call sites of `GetInventoryItemID(`, e.g. `Blizzard_NewPlayerExperience/Blizzard_TutorialServices.lua:318`; `GetInventoryItemLink` in `PaperDollFrame.lua:1689`, `ChatFrameUtil.lua:1207`).

How Blizzard resolves macro item arguments: `SecureCmdItemParse(item)` (`Blizzard_ChatFrameBase/Shared/ChatFrameUtil.lua:1196-1210`) accepts `bag slot` or an inventory `slot` number, else passes the text through; `SecureCmdUseItem` (`:1212-1220`) ends in `C_Item.UseItemByName`. A validator can reuse `SecureCmdItemParse` for the numeric forms.

INFERRED: `ItemInfo` accepts ID, name or link (the type is not defined in the generated docs); lookup by name works only for items the client has cached, and `GetItemInfo` returns nothing until item data has loaded (the reason `RequestLoadItemDataByID` exists).

### 2.3 Conditionals: `SecureCmdOptionParse`

VERIFIED: undocumented global, called 69 times in 12.1.5 Lua (e.g. `Blizzard_ChatFrameBase/Mainline/SlashCommandsOverrides.lua:2-33`, `Blizzard_RestrictedAddOnEnvironment/SecureStateDriver.lua:96`). Usage shape: `local value, target = SecureCmdOptionParse(msg)` (`Blizzard_ChatFrameBase/Shared/SlashCommands.lua:822`), and a nil or empty first return means no clause matched (`SlashCommandsOverrides.lua:29-31`).

INFERRED: it evaluates conditionals against the current state and returns the chosen clause; nothing in Lua shows it reporting syntax errors, so it cannot be used as a syntax validator (a malformed conditional and a false one both yield nil, as far as the Lua callers reveal). A syntax check would have to be our own parser.

Related, VERIFIED: the list of secure slash commands is registered through `SlashCommandUtil.CheckAddSecureSlashCommand` (`Blizzard_ChatFrameBase/Shared/SlashCommands.lua:325`) with keys in `SLASH_COMMAND` (`:12`) and categories in `SLASH_COMMAND_CATEGORY` (`:174`); `Doc/SlashCommandDocumentation.lua` exists. That is a possible source of truth for `MACRO_COMMANDS` names; localized strings live in GlobalStrings (`SLASH_CAST1 = "/cast"`, line 18698 of the 12.1.0 enUS dump).

### 2.4 Macros

VERIFIED (undocumented globals, Blizzard call sites):
- `GetMacroInfo(index)` returns name, icon, body (`Blizzard_MacroUI/Blizzard_MacroUI.lua:172`, `Blizzard_ClickBindingUI/Blizzard_ClickBindingUI.lua:176`, `Blizzard_SharedXML/Mainline/SharedUIPanelTemplates.lua:1817`).
- `GetNumMacros()` (`Blizzard_MacroUI.lua:164`), `CreateMacro(name, icon, body, perCharacter)` (`Blizzard_MacroUI/Blizzard_MacroIconSelector.lua:109`), `EditMacro(index, name, icon, body)` (`Blizzard_MacroUI/Blizzard_MacroUI.lua:344`, `Blizzard_MacroUI/Blizzard_MacroIconSelector.lua:112`), `PickupMacro` (`Blizzard_RestrictedAddOnEnvironment/SecureHandlers.lua:145`).
- `C_Macro.GetMacroName(macroId)` documented (`Doc/UIMacrosDocumentation.lua:11`), `C_Macro.RunMacroText` and `SetMacroExecuteLineCallback` carry `HasRestrictions = true` (`:41-62`).
- `Constants.MacroConsts.MAX_ACCOUNT_MACROS = 120`, `MAX_CHARACTER_MACROS = 30` (`Doc/MacroConstantsDocumentation.lua:10-11`). `Actions.lua:72-76` falls back to 18 only when `Constants` is missing, so the live value is 30.
- Not called anywhere in 12.1.5 Lua: `GetMacroBody`, `GetMacroIndexByName` (grep count 0; the project already lists `GetMacroIndexByName` as unverified in `tools/wow_api.py`).

INFERRED: `CreateMacro`/`EditMacro` are blocked in combat (C side; consistent with the project's CLAUDE.md). Body limit: the frame's 255 counts letters including invisible ones; `Actions.lua:308` checks 255 bytes (`#v`), which is stricter for non-ASCII text. Whether `EditMacro` enforces bytes or letters is not visible in Lua.

### 2.5 Action slots

VERIFIED:
- `GetActionInfo(slot)` returns actionType, id, subType; undocumented global, 38 call sites (e.g. `Blizzard_TutorialManager/Blizzard_TutorialHelper.lua:198`).
- `C_ActionBar.HasAction(actionID)`: `RequiresValidActionSlot`, AllowedWhenUntainted (`Doc/ActionBarFrameDocumentation.lua:457`). The global `HasAction` is a deprecation fallback (`Blizzard_DeprecatedActionBar/Deprecated_ActionBar.lua:40-42`, gated at `:4`), as are `GetActionText` (`:14`) and others; use `C_ActionBar.GetActionText` (Doc ActionBar:244, MayReturnNothing, RequiresValidActionSlot), `C_ActionBar.GetActionTexture` (:261), `C_ActionBar.GetSpell` (:424), `C_ActionBar.FindSpellActionButtons(spellID)` (:66, AllowedWhenTainted).
- Secret returns on action bars apply only to cooldown data: `GetActionCharges`, `GetActionCooldown`, `GetActionDisplayCount`, `GetActionLossOfControlCooldownInfo`, `GetActionUseCount` (`SecretWhenCooldownsRestricted`).
- Placement: `PlaceAction` (`Blizzard_ActionBar/Shared/ActionButton.lua:1383`), `C_ActionBar.PutActionInSlot(slotID)` (Doc ActionBar:900), `PickupAction` (3 call sites).

### 2.6 Bindings

VERIFIED (undocumented globals with Blizzard call sites):
- `GetBindingKey(command)` (49 call sites, e.g. `Blizzard_MainMenuBarBagButtons/Mainline/MainMenuBarBagButtons.lua:248`), `GetBindingAction(key)` (14, e.g. `Blizzard_FrameXML/Mainline/StackSplitFrame.lua:172`), `GetBinding(index)` returns action, category, key1, key2 (`Blizzard_SettingsDefinitions_Frame/Keybindings.lua:24-25`), `GetNumBindings()`.
- `SetBinding(key, action, bindingContext)`: the 12.x settings UI passes a third `bindingContext` argument (`Blizzard_Settings_Shared/Blizzard_Keybindings.lua:71,138,156,160`); 36 bindings in Bindings.xml carry a `bindingContext` attribute (bindings.tsv).
- `SaveBindings(GetCurrentBindingSet())` (`Blizzard_Settings_Shared/Blizzard_SettingsPanel.lua:310`, `Blizzard_ClickBindingUI.lua:400`).
- Documented: `C_KeyBindings.GetBindingIndex(action)` (`Doc/KeyBindingsDocumentation.lua:64`), `C_KeyBindings.GetBindingByKey(action, context)` (:33), `C_KeyBindings.GetCustomBindingType(index)` (:79); `ActivateBindingContext`/`DeactivateBindingContext` have `HasRestrictions`.
- Not called in 12.1.5 Lua: `SetBindingClick`, `SetBindingSpell`, `SetBindingItem`, `SetBindingMacro` (grep count 0 each).

INFERRED: `SetBinding` is protected in combat (C side).

### 2.7 Combat state and CVars

- `InCombatLockdown()` global (14 Blizzard call sites) and documented `C_RestrictedActions.InCombatLockdown()` (`Doc/RestrictedActionsDocumentation.lua:45`). `C_RestrictedActions.CheckAllowProtectedFunctions(object, silent)` (:11) "Returns true if the calling context has permissions to call protected functions on the supplied object".
- `C_CVar.SetCVar(name, value)` returns `success` and is flagged `RequiresValidAndPublicCVar`, `RequiresNonReadOnlyCVar`, `RequiresNonSecureCVar`, `SecretArguments = "NotAllowed"` (`Doc/CVarDocumentation.lua:118-134`); `SetCVarBitfield` the same plus `RequiresIndexInRange` (:137-154). `C_CVar.GetCVarInfo(name)` returns `isSecure` and `isReadOnly` among others (:82-99). The global `SetCVar` is a Lua wrapper over `C_CVar.SetCVar` that converts booleans to "1"/"0" (`Blizzard_SharedXMLBase/CvarUtil.lua:9-15`).

Findings against the current addon (VERIFIED unless marked):
- `Actions.lua:391-393` calls `ns.SetCVar(a.name, a.value)` and returns `true` without checking the `success` return.
- Three entries of `CVAR_ALLOW` (`Actions.lua:16-22`) are flagged secure in the 12.1.0 dump: `ActionButtonUseKeyDown`, `SoftTargetEnemy`, `SoftTargetInteract`. With `RequiresNonSecureCVar`, an addon `SetCVar` on them likely fails (INFERRED: Blizzard's options panel sets the same CVars, so the requirement presumably applies to tainted callers only). Check at runtime with `C_CVar.GetCVarInfo(name)` (6th return).
- `nameplateShowFriends` (in `CVAR_ALLOW`) appears nowhere in the 12.1.5 Lua and is absent from the 12.1.0 dump, which has `nameplateShowFriendlyPlayers` and `nameplateShowFriendlyNpcs` instead (INFERRED that it no longer exists; the dump is one minor version older).
- `cameraDistanceMaxZoomFactor` exists in the dump but no 12.1.5 Lua and no options-panel setting references it; `autoQuestWatch` and `scriptErrors` are read by Blizzard code (`Blizzard_ObjectiveTracker/Blizzard_ObjectiveTracker.lua:23`, `Blizzard_ScriptErrorsFrame/Blizzard_ScriptErrorsFrame.lua:125`) but not registered in the panel. The other 10 entries are panel settings (see settings-cvars.tsv; `softTargetEnemy`, `softTargetInteract`, `autoSelfCast` only through proxy settings).

---

## 3. Exact lists

### 3.a Options-panel settings: `docs/research/settings-cvars.tsv`

Scope: every file under `Blizzard_SettingsDefinitions_Frame/` and `Blizzard_SettingsDefinitions_Shared/` (35 files including `Mainline/`), plus `Blizzard_Settings_Shared/Mainline/AudioOverrides.lua` and `GraphicsOverrides.lua`, which register panel settings too (`AudioOverrides.lua:8-9,43-44,71-72`; `GraphicsOverrides.lua:6-44`). `Blizzard_Settings_Shared/Blizzard_ImplementationReadme.lua` is example text and is excluded.

Registration functions (VERIFIED, `Blizzard_Settings_Shared/Blizzard_Settings.lua`): `RegisterCVarSetting` (:181, a `CVarSettingMixin` bound directly to a CVar), `SetupCVarCheckbox` (:575), `SetupCVarSlider` (:581), `SetupCVarDropdown` (:587), `SetupCVarColorSwatch` (:600) (all four call `RegisterCVarSetting`), `RegisterProxySetting` (:177, arbitrary getter and setter), `RegisterModifiedClickSetting` (:187), `SetupModifiedClickDropdown` (:593), `RegisterAddOnSetting` (:173, not used by the panel), `CreateCVarAccessorClosures` (:606, how proxies wrap a CVar).

Method: `scratchpad/settings2tsv.py` parses each call's arguments; literal CVar names are taken as written, local and global constants are resolved by assignment (e.g. `SUBTITLES_ENABLED_CVAR`, `EncounterTimelineIndicatorIconCVars.Enabled` at `Blizzard_EncounterTimeline/EncounterTimelineConstants.lua:165`). For each proxy the getter and setter bodies were extracted and scanned for CVar access; 20 proxies were classified by hand after reading their code (listed with notes in the TSV). Helper templates were expanded to their call sites: `CreateAdvancedQualitySetting` (Graphics.lua:60-68) through the 28 `addFunc` rows in GraphicsOverrides.lua, `AddCompatSettingsCheckbox` (Graphics.lua:1503-1524, 4 rows), and the action bar loop (ActionBars.lua:29-55, 7 rows). `CreateQualitySliderSetting` (Graphics.lua:70-82) has no caller in this build.

Columns: `cvar` (comma-separated when a proxy drives several), `setting_variable`, `kind`, `registration`, `file_line`, `panel_file`, `notes`, `in_cvar_dump_12_1_0`, `secure_flag`.

Counts (from the final TSV):

| kind | rows | meaning |
|---|---|---|
| `cvar` | 218 | setting bound directly to one CVar (218 distinct CVars, none registered twice) |
| `proxy-cvar` | 85 | proxy whose getter/setter reads and writes CVars (103 distinct CVars behind them) |
| `proxy-api` | 50 | proxy backed by a non-CVar API (voice chat, `C_CombatAudioAlert`, action bar toggles, guild and neighborhood invite flags, binding set, quest tracking filters, chat disable) |
| `modifiedclick` | 5 | modified-click bindings (`PICKUPACTION`, `MOUSEOVERCAST`, `SELFCAST`, `FOCUSCAST`, `AUTOLOOTTOGGLE`; not CVars) |
| `template` | 3 | helper definitions, excluded from the counts above |

Distinct CVars reachable from the panel: 321 (218 direct, 103 behind proxies, no overlap). Settings that are not CVars: 55 (50 proxy-api plus 5 modified-click).

Distinct CVars per panel file: Accessibility 15, ActionBars 2, Audio 27, AudioAssist 35, Colorblind 3, Combat 16, CombatWarnings (AdvancedOptions.lua) 18, Controls 21, Graphics 63, Interface 39, Languages 2, Mac 2, Mounts 11, Nameplates 36, Network 3, PingSystem 5, Social 17, Subtitles 3, Text 3 (sum 321).

Non-CVar settings per file: ActionBars 8, Audio 7, AudioAssist 28, Combat 3, Controls 1, Graphics 1, Interface 2, Keybindings 1, Social 4 (sum 55).

Cross-check against the 12.1.0 CVar dump: 15 panel CVars are not in it (all newer nameplate, encounter timeline and Mac settings, e.g. `nameplateInfoDisplay`, `encounterTimelineIconographyHiddenMask`), and 20 are flagged secure there: `ActionButtonUseKeyHeldSpell`, `colorblindSimulator`, `colorblindWeaknessFactor`, `enableMouseoverCast`, `encounterTimelineHideForOtherRoles`, `encounterWarningsHideIfNotTargetingPlayer`, `nameplateAuraScale`, `nameplateDebuffPadding`, `nameplateShowClassColor`, `nameplateShowEnemyMinus`, `nameplateShowFriendlyClassColor`, `nameplateShowOffscreen`, `nameplateShowSelf`, `nameplateSize`, `nameplateStyle`, `showTargetOfTarget`, `softTargetEnemy`, `softTargetInteract`, `uiscale`, `useUiScale`.

Limits of the list (INFERRED risk): many registrations are conditional (game rules, `C_CVar.GetCVar(...)` existence checks, Mac only, `RunSettingsCallback` gates). The TSV lists every registration in source, not what a given client shows. Mirrored initializers (`layout:AddMirroredInitializer`, e.g. Accessibility.lua:141-156) reuse settings registered elsewhere and are not listed twice.

### 3.b Key bindings: `docs/research/bindings.tsv`

Sources: `Blizzard_FrameXML/Bindings.xml` (see the provenance note at the top), `Blizzard_PingUI/Bindings.xml`, `Blizzard_GlueXML/Bindings.xml`, `Blizzard_Commentator/Bindings.xml`, `Blizzard_PTRFeedback/Bindings.xml` (all at the pinned commit). Parsed with expat (comments, including the commented-out `TARGETNEAREST` block, are ignored). Columns: `scope`, `kind`, `name`, `category`, `header`, `runOnUp`, `hidden`, `debug`, `bindingContext`, `default`, `action`, `file`, `line`, `category_label_enUS`, `name_label_enUS` (labels from the 12.1.0 enUS GlobalStrings).

Counts:
- In-game bindings (`scope=game`, FrameXML plus PingUI): 362 `<Binding>` entries, 362 distinct names; 20 `hidden="true"`, 18 `debug="true"` (342 neither hidden nor debug); 36 with a `bindingContext`. Plus 22 `<ModifiedClick>` entries.
- Login screen (glue) 5, commentator mode 57, PTR client 1.
- In-game bindings by category: TARGETING 44, INTERFACE 44, ACTIONBAR 43, HOUSING_SYSTEM 37, CAMERA 21, DEBUG 18, MOVEMENT 17, MISC 16, CHAT 14, ACTIONBAR2 to ACTIONBAR8 12 each (84), RAID_TARGET 9, VEHICLE 7, PING_SYSTEM 6, no category 2 (`TURNORACTION`, `CAMERAORSELECTORMOVE`, both hidden).
- 20 in-game bindings have no `BINDING_NAME_` string in the 12.1.0 GlobalStrings.

Authoritative runtime source (VERIFIED): `GetNumBindings()` and `GetBinding(i)`, which the keybinding panel iterates (`Blizzard_SettingsDefinitions_Frame/Keybindings.lua:24-25`). Addon `Bindings.xml` files add to the same list, so a runtime dump is the only complete list on a given client.

---

## 4. Talent loadout import (VERIFIED unless marked)

Path: Import dialog `ClassTalentLoadoutImportDialogMixin:OnAccept` (`Blizzard_PlayerSpells/ClassTalents/Blizzard_ClassTalentLoadoutImportDialog.lua:21-25`) calls `PlayerSpellsFrame.TalentsFrame:ImportLoadout(importText, loadoutName)`, which is `ClassTalentImportExportMixin:ImportLoadout` (`Blizzard_ClassTalentImportExport.lua:180-236`):
1. Refuses while inspecting (`:181-184`) and without a name (`:186-189`).
2. `ExportUtil.MakeImportDataStream(importText)`; reads the header: 8-bit serialization version, 16-bit specID, 128-bit tree hash (`ReadLoadoutHeader`, `:298-313`; format spec in the comment at `:1-48`).
3. Version must equal `C_Traits.GetLoadoutSerializationVersion()` (`:201`), specID must equal `PlayerUtil.GetCurrentSpecID()` (`:206`), hash must match `C_Traits.GetTreeHash(treeID)` unless all zero ("allow third-party sites to generate loadout strings with an empty tree hash", `:214-220`).
4. `ReadLoadoutContent`, then `ConvertToImportLoadoutEntryInfo(configID, treeID, content)` walks `C_Traits.GetTreeNodes(treeID)` and builds `{nodeID, ranksGranted, ranksPurchased, selectionEntryID}` entries (`:395-411`, per-node logic `:315-392`).
5. `C_ClassTalents.ImportLoadout(configID, entries, name, importText)` returns `success, importError` (`:227`; doc `Doc/ClassTalentsDocumentation.lua:207-224`, `SecretArguments = "AllowedWhenUntainted"`, no `HasRestrictions`; entry struct `:508-517`). `configID` is the frame's current config, `C_ClassTalents.GetActiveConfigID()` (`Blizzard_ClassTalentsFrame.lua:871`).

Import creates a saved loadout; it does not apply it. Applying goes through `C_ClassTalents.LoadConfig(configID, autoApply)` (`Blizzard_ClassTalentsFrame.lua:1104`, doc ClassTalents:253) and `C_ClassTalents.CommitConfig` (`:1155`), or by name/index with `C_ClassTalents.SwitchToLoadoutByName` / `ByIndex`, which are `HasRestrictions = true` (doc ClassTalents:343, :355). Those back the slash commands `/loadoutname` (`/lon`) and `/loadoutindex` (`/loi`) (`Blizzard_ChatFrame/Shared/ClassTalentHelper.lua:57-72`; strings from the 12.1.0 GlobalStrings), which a macro can use.

Preconditions visible in Lua:
- The import menu entry is disabled when `not C_ClassTalents.CanCreateNewConfig()` (`Blizzard_ClassTalentsFrame.lua:540-546`).
- The frame treats itself as locked when `C_ClassTalents.CanEditTalents()` is false and shows its error string (`:770-775`; doc ClassTalents:32 "could switch talents if they staged a proper loadout"). `C_ClassTalents.CanChangeTalents()` gates commits (`:1351-1361`).
- `Constants.TraitConsts.MAX_COMBAT_TRAIT_CONFIGS = 40` (`Doc/TraitConstantsDocumentation.lua:319`).

INFERRED: combat, rest-area and per-spec loadout limits are enforced in C behind `CanEditTalents`, `CanCreateNewConfig` and `ImportLoadout`'s error string; no Lua code tests combat or rest directly here. There are no `taint`, `securecall` or `issecure` mentions in `Blizzard_PlayerSpells` or `Blizzard_SharedTalentUI` (grep), and `ImportLoadout` has no `HasRestrictions` flag, so a direct call from addon code is not marked restricted. Calling `PlayerSpellsFrame.TalentsFrame:ImportLoadout` from addon code instead would run Blizzard's frame code from a tainted caller; prefer reproducing steps 2 to 5 with the `C_` APIs and `ExportUtil`. Server-side success arrives later (`OnTraitConfigCreateStarted`, `:233`).

---

## 5. Edit Mode (VERIFIED unless marked)

Docs (`Doc/EditModeManagerDocumentation.lua`): `ConvertLayoutInfoToString` (:11), `ConvertStringToLayoutInfo` (:26), `GetAccountSettings` (:42), `GetLayouts` (:51), `IsValidLayoutName` (:60), `OnEditModeExit` (:75), `OnLayoutAdded(index, activate, isImported)` (:79), `OnLayoutDeleted` (:91), `SaveLayouts(EditModeLayouts)` (:101), `SetAccountSetting` (:111), `SetActiveLayout(index)` (:122); event `EDIT_MODE_LAYOUTS_UPDATED(layoutInfo, reconcileLayouts)` (:136-143). All argument-taking functions are `SecretArguments = "AllowedWhenUntainted"`; none has `HasRestrictions`. Structures: `EditModeLayouts{layouts, activeLayout}`, `EditModeLayoutInfo{layoutName, layoutType, systems}`, `EditModeSystemInfo{system, systemIndex, anchorInfo, ...}` (:151-197).

Blizzard's import flow:
- Text to table: `EditModeImportLayoutDialogMixin:ProcessImportText` calls `C_EditMode.ConvertStringToLayoutInfo(text)` (`Blizzard_EditMode/Shared/EditModeDialogs.lua:357-360`). The dialog forces a new name ("we don't trust external text", `:319`, `:351`).
- Accept: `ImportLayoutFromDialog` then `ImportLayout` then `MakeNewLayout` (`EditModeManager.lua:1189-1190`, `:1548-1551`, `:1473-1495`): requires a non-empty name passing `C_EditMode.IsValidLayoutName`, sets `layoutType` and `layoutName`, inserts at the next index after the existing layouts of that type, `self:SaveLayouts()` (which is `C_EditMode.SaveLayouts(self.layoutInfo)` of the whole table, `:1561-1566`), then `C_EditMode.OnLayoutAdded(index, activate, true)`.
- Switch: `SelectLayout` calls `C_EditMode.SetActiveLayout(layoutIndex)` (`:1457-1463`).
- Export: `C_EditMode.ConvertLayoutInfoToString(activeLayoutInfo)` (`:1524-1528`). Chat hyperlinks for layouts are commented out (`:1530-1537`, `EditModeDialogs.lua:362-406`, and `-- EditModeLayout = "layout"` at `LinkUtil.lua:24`).

Preconditions: `Constants.EditModeConsts.EditModeMaxLayoutsPerType = 5` (`Doc/EditModeManagerConstantsDocumentation.lua:945`; checks at `EditModeManager.lua:930-936`, `:1226-1232`); duplicate names refused (`:1205-1212`); preset layouts cannot be deleted or renamed (`:1499`, `:1516`); `CanEnterEditMode` refuses under the `EditModeDisabled` game rule, NPE restriction, missing account settings, or blocking frames (`:1636-1655`).

Taint signals in Blizzard's own code: iteration over system frames goes through `secureexecuterange` (`:90`, `:108`, `:221`, `:280`, `:693`, `:705`, `:979`, `:1393`, `:1544`, `:1558`); `ClearSelectedSystem` uses a `CreateSecureDelegate` only when `issecure() or not InCombatLockdown()` (`:709-717`); `SetHasActiveChanges` copies its argument to "Clear taint off of the value passed in" (`:262-268`).

INFERRED: an addon that calls `C_EditMode.SaveLayouts` / `SetActiveLayout` directly lets Blizzard's `EDIT_MODE_LAYOUTS_UPDATED` handler (`:187-192`) re-apply layouts from an event, which is the less risky path; calling `EditModeManagerFrame` methods from addon code would run the protected frame repositioning from a tainted call stack, and action bars cannot be moved in combat. `SaveLayouts` replaces the full set, so a buggy table loses every user layout; read with `GetLayouts()` immediately before and change only by appending.

---

## 6. Cooldown Manager (VERIFIED unless marked)

Docs (`Doc/CooldownViewerDocumentation.lua`): `GetCooldownViewerCategorySet(category, allowUnlearned)` (:11), `GetCooldownViewerCooldownInfo(cooldownID)` (:27), `GetGroupBuffItems` (:43), `GetLayoutData()` returns a cstring (:52), `GetValidAlertTypes(cooldownID)` (:61), `IsCooldownViewerAvailable()` returns isAvailable, failureReason (:76), `SetLayoutData(data)` (:86, AllowedWhenUntainted, no `HasRestrictions`); events `COOLDOWN_VIEWER_DATA_LOADED`, `COOLDOWN_VIEWER_SPELL_OVERRIDE_UPDATED`, `COOLDOWN_VIEWER_TABLE_HOTFIXED`.

Data format (`Blizzard_CooldownViewer/CooldownViewerSettingsDataStoreSerialization.lua`):
- String = `<encodingVersion>|<payload>` (`:329-339`, `:364-373`); encoding version 1 is `C_EncodingUtil.SerializeCBOR`, `CompressString(..., Deflate)`, `EncodeBase64`, and the reverse on read (`:265-287`).
- Decoded table: field 1 save-format version (current 5, `:289-291`), field 2 active layout per spec, field 3 layouts keyed by class-and-spec tag, field 4 layout ID data (`:1-8`); per layout: cooldown order, category overrides, alert overrides, hidden group buffs, group buff visual alerts (`:10-14`). Readers exist for versions 1 to 5 (`:256-263`).
- The import/export string is the same format: export is `SerializeLayouts(layoutID)` for one layout (`CooldownViewerSettingsLayoutManager.lua:923-934`), import is `CreateLayoutsFromSerializedData(text)` with `isUserInput = true` so bad input fails softly (`:936-942`; `IsFailCondition` at `Serialization.lua:311-318`). The import dialog keeps only the first layout ("Only support single layout for now", `CooldownViewerSettingsDialogs.lua:39-46`) and blanks its name (`:32-37`).
- `GetLayoutData` / `SetLayoutData` hold the whole saved state (all layouts) (`Serialization.lua:57-79`); Blizzard reads it once after `VARIABLES_LOADED`, `PLAYER_ENTERING_WORLD` and `COOLDOWN_VIEWER_DATA_LOADED` (`CooldownViewerSettings.lua:840-854`) and writes it back on save (`CooldownViewerSettingsLayoutManager.lua:111-115`).
- Limits: 5 layouts per type (`GetMaxLayoutsForType`, `CooldownViewerSettingsLayoutManager.lua:890-892`), character layouts only (`:910-913`).

INFERRED: a direct `C_CooldownViewer.SetLayoutData` from addon code is not re-read by Blizzard's layout manager (no reload path besides the load-time `ReadData`), and the manager's next save overwrites it, so a reload would be needed after writing. Driving Blizzard's manager methods instead means tainted calls into code that guards secret aura data with `settablesecurity(..., DisallowTaintedAccess)` (`CooldownViewerSecure.lua:25-33`). Either way, this needs an in-game test before planning on it.

---

## 7. Equipment sets (VERIFIED unless marked)

Docs (`Doc/EquipmentManagerDocumentation.lua`): `CanUseEquipmentSets` (:22), `CreateEquipmentSet(name, icon)` (:35), `SaveEquipmentSet(setID, icon)` (:256), `ModifyEquipmentSet(setID, newName, newIcon)` (:234), `DeleteEquipmentSet` (:46), `UseEquipmentSet(setID)` returns setWasEquipped (:287), `GetEquipmentSetID(name)` (:103), `GetEquipmentSetIDs` (:119), `GetEquipmentSetInfo` (:128), `GetItemIDs` (:168), `GetItemLocations` (:184), `IgnoreSlotForSave` / `ClearIgnoredSlotsForSave` (:209 / :31), `EquipmentSetContainsLockedItems` (:56), `AssignSpecToEquipmentSet` (:11). None has `HasRestrictions` or secret-return flags. `CreateEquipmentSet` saves what is currently worn (INFERRED from Blizzard calling it with only name and icon, `Blizzard_UIPanels_Game/Mainline/PaperDollFrame.lua:2269`).

Restrictions in Lua: `MAX_EQUIPMENT_SETS_PER_PLAYER = 10` (`Blizzard_FrameXMLBase/Constants.lua:197`; enforced at `PaperDollFrame.lua:2263-2266`); Blizzard refuses to equip a set while it holds locked items or while casting (`Blizzard_FrameXML/Mainline/EquipmentManager.lua:259-266`); in combat only `INVSLOTS_EQUIPABLE_IN_COMBAT` slots change (`:268-270`). Macros already have `/equipset` (`Blizzard_ChatFrameBase/Shared/SlashCommands.lua:811-819`) and secure buttons have `type = "equipmentset"` (`Blizzard_FrameXML/SecureTemplates.lua:438-445`); both are in `MACRO_COMMANDS` already.

INFERRED: equipping is otherwise allowed from addon code out of combat (no restriction flag), and server-side item locks can make `UseEquipmentSet` fail silently.

---

## 8. Secure action buttons (VERIFIED unless marked)

- Template: `SecureActionButtonTemplate` inherits `SecureFrameTemplate`, mixin `SecureActionButtonMixin`, `OnClick = SecureActionButton_OnClick` (`xml/Interface/AddOns/Blizzard_FrameXML/SecureTemplates.xml`, from the pinned commit). Its comment: "for now AddOns won't be able to have isKeyPress or isSecureAction set". `InsecureActionButtonTemplate` runs the same handler only when `not InCombatLockdown()`.
- `type = "macro"`: `SECURE_ACTIONS.macro` runs `RunMacro(macro, button)` for a `macro` attribute (after `securecallfunction(SaveMacro)`), else `C_Macro.RunMacroText(macrotext, button)` (`Blizzard_FrameXML/SecureTemplates.lua:447-461`). `RunMacroText` is `HasRestrictions = true` (`Doc/UIMacrosDocumentation.lua:41-51`), so it runs only through the secure button.
- Length limit: none visible in Lua for `macrotext`; the only 255 in this area is the macro frame's EditBox (1.4). INFERRED: any limit is C-side.
- Key down handling (`SecureTemplates.lua:795-829`): `useOnKeyDown` is the button's `useOnKeyDown` attribute, or the CVar `ActionButtonUseKeyDown` when the attribute is nil (`:795-803`). For addon buttons `isKeyPress` and `isSecureAction` are nil, so `isSecureMousePress` is false and the action fires only on the down event when `useOnKeyDown` is true, only on the up event when false (`:811-814`). A button registered for `"AnyUp"` alone does nothing while `ActionButtonUseKeyDown` is on, unless it sets `useOnKeyDown` to false. Register `RegisterForClicks("AnyUp", "AnyDown")` or pin the attribute. `pressAndHoldAction` and `ActionButtonUseKeyHeldSpell` add a release action (`:812-825`).
- Creation: INFERRED. Creating the button and setting `type`/`macrotext` must happen out of combat (protected-frame attribute writes are blocked in combat on the C side; the standard rule, consistent with CLAUDE.md). The Lua only shows related combat gating inside the restricted environment (`Blizzard_RestrictedAddOnEnvironment/SecureHandlers.lua:435`, `Blizzard_RestrictedAddOnEnvironment/RestrictedFrames.lua:81`).

---

## Files written

- `research/blizzard-apis.md` (this report)
- `docs/research/settings-cvars.tsv`, `docs/research/bindings.tsv`
- `research/xml/...` (fetched XML at the pinned commit, and the rebuilt `Blizzard_FrameXML_Bindings_70391.xml`), `research/tly/` (townlong-yak viewer page), `research/ketho/` (CVar and GlobalStrings dumps), `research/tree.json` (GitHub tree listing of the commit)
- Scripts in `scratchpad/`: `settings2tsv.py`, `finalize_settings.py`, `bind2tsv.py`, `apidoc.py`
