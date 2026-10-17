-- Executes what the assistant asked for, using only normal addon APIs.
-- Every action is checked here again: the model and the companion are not trusted.
-- Navigation runs at once; changes to macros, bars, keys and settings wait for the
-- player's confirmation unless auto-apply is on, and a binding that would replace an
-- existing one always asks. Nothing changes in combat: Blizzard blocks it there.
local _, ns = ...

local Actions = {}
ns.Actions = Actions

local DEFAULT_ICON = 134400 -- question mark; #showtooltip macros show the spell icon
local floor = math.floor

-- Console variables the assistant may change. The companion reads this table to tell the
-- model which settings exist, so it is the only list.
local CVAR_ALLOW = {
	autoLootDefault = true, nameplateShowEnemies = true, nameplateShowFriends = true,
	nameplateShowAll = true, Sound_EnableMusic = true, Sound_EnableAmbience = true,
	cameraDistanceMaxZoomFactor = true, autoQuestWatch = true, showTutorials = true,
	scriptErrors = true, ActionButtonUseKeyDown = true, softTargetEnemy = true,
	softTargetInteract = true, autoSelfCast = true, chatBubbles = true,
}

-- The only lines a macro from the assistant may contain: these metas and slash commands.
-- No /run, /script or /click, and no plain text (WoW would say it in chat). The companion
-- reads this table for the model's instructions too.
local MACRO_COMMANDS = {
	["#showtooltip"] = true, ["#show"] = true,
	["/cast"] = true, ["/use"] = true, ["/castsequence"] = true, ["/castrandom"] = true, ["/userandom"] = true,
	["/stopcasting"] = true, ["/cancelqueuedspell"] = true, ["/stopspelltarget"] = true,
	["/startattack"] = true, ["/stopattack"] = true, ["/cancelaura"] = true, ["/cancelform"] = true,
	["/dismount"] = true, ["/target"] = true, ["/targetexact"] = true, ["/targetenemy"] = true,
	["/targetfriend"] = true, ["/targetlasttarget"] = true, ["/cleartarget"] = true, ["/focus"] = true,
	["/clearfocus"] = true, ["/assist"] = true, ["/petattack"] = true, ["/petfollow"] = true,
	["/petstay"] = true, ["/petpassive"] = true, ["/petdefensive"] = true, ["/petassist"] = true,
	["/equip"] = true, ["/equipslot"] = true, ["/equipset"] = true, ["/usetoy"] = true,
	["/targetmarker"] = true, ["/tm"] = true, ["/worldmarker"] = true, ["/wm"] = true,
	["/clearworldmarker"] = true, ["/cwm"] = true, ["/summonpet"] = true, ["/randompet"] = true,
	["/randomfavoritepet"] = true, ["/dismisspet"] = true, ["/stopmacro"] = true,
	["/changeactionbar"] = true, ["/swapactionbar"] = true,
}

local function str(v, maxLen)
	if type(v) ~= "string" or v == "" then return nil end
	if maxLen and #v > maxLen then return nil end
	return v
end

local function num(v, lo, hi)
	if type(v) ~= "number" or v ~= v then return nil end
	if lo and v < lo then return nil end
	if hi and v > hi then return nil end
	return v
end

local function int(v, lo, hi)
	local n = num(v, lo, hi)
	if n and n == floor(n) then return n end
	return nil
end

local E = ns.Escape

local function iconFor(name)
	if type(name) == "number" then return name end
	if type(name) == "string" and GetFileIDFromPath then
		return GetFileIDFromPath("Interface\\Icons\\" .. name) or DEFAULT_ICON
	end
	return DEFAULT_ICON
end

local function macroLimits()
	local consts = Constants and Constants.MacroConsts
	return (consts and consts.MAX_ACCOUNT_MACROS) or MAX_ACCOUNT_MACROS or 120,
		(consts and consts.MAX_CHARACTER_MACROS) or MAX_CHARACTER_MACROS or 18
end

-- GetMacroIndexByName and SetBindingMacro are long-standing, but Blizzard's 12.1.5 UI
-- neither documents nor calls them; GetMacroInfo and SetBinding it does. Prefer the
-- former when present.
local function macroIndex(name)
	if GetMacroIndexByName then return GetMacroIndexByName(name) or 0 end
	local maxAccount = macroLimits()
	local numAccount, numChar = GetNumMacros()
	for i = 1, numAccount do
		if GetMacroInfo(i) == name then return i end
	end
	for i = maxAccount + 1, maxAccount + numChar do
		if GetMacroInfo(i) == name then return i end
	end
	return 0
end

local function bindMacro(key, name)
	if SetBindingMacro then return SetBindingMacro(key, name) end
	return SetBinding(key, "MACRO " .. name)
end

local function macroBodyProblem(body)
	if body:find("|", 1, true) then return "contains an escape sequence" end
	for line in (body .. "\n"):gmatch("([^\n]*)\n") do
		local text = line:match("^%s*(.-)%s*$")
		if text ~= "" then
			local cmd = text:match("^([#/]%S*)")
			if not cmd then return "has a line WoW would say in chat" end
			if not MACRO_COMMANDS[cmd:lower()] then return "uses " .. cmd .. ", which the assistant may not use" end
		end
	end
	return nil
end

-- TomTom (optional addon) takes TomTom:AddWaypoint(uiMapID, x, y, opts) with x and y from 0 to
-- 1, as its TomTom.lua defines it and current HandyNotes plugins call it. Its errors stay its own.
local function addTomTom(map, x, y, title)
	if not (TomTom and TomTom.AddWaypoint) then return false end
	return (pcall(TomTom.AddWaypoint, TomTom, map, x, y, { title = E(title), from = "Gnomecaster", persistent = false }))
end

-- Blizzard's map pin and arrow, plus TomTom's waypoint when it is installed.
-- Returns whether each of the two was set.
local function setPin(map, x, y, title)
	local blizzard = false
	if C_Map and C_Map.SetUserWaypoint and UiMapPoint then
		if not C_Map.CanSetUserWaypointOnMap or C_Map.CanSetUserWaypointOnMap(map) then
			C_Map.SetUserWaypoint(UiMapPoint.CreateFromCoordinates(map, x, y))
			if C_SuperTrack and C_SuperTrack.SetSuperTrackedUserWaypoint then
				C_SuperTrack.SetSuperTrackedUserWaypoint(true)
			end
			blizzard = true
		end
	end
	return blizzard, addTomTom(map, x, y, title)
end

local function firstLine(text)
	return (text:match("^[^\n]*"))
end

local handlers = {}

handlers.waypoint = {
	instant = true,
	order = 6,
	check = function(a)
		a.map = int(a.map, 1, 1e7)
		local x, y = num(a.x, 0, 100), num(a.y, 0, 100)
		if not (a.map and x and y) then return false, "needs a map and two coordinates" end
		if x > 1 and y > 1 then
			x, y = x / 100, y / 100     -- both given as map percentages
		elseif x > 1 or y > 1 then
			return false, "mixes two coordinate scales"
		end
		a.x, a.y = x, y
		a.title = str(a.title, 80) or "Gnomecaster"
		return true
	end,
	describe = function(a)
		return string.format("Waypoint: %s (%.1f, %.1f)", E(a.title), a.x * 100, a.y * 100)
	end,
	run = function(a)
		local blizzard, tomtom = setPin(a.map, a.x, a.y, a.title)
		if not (blizzard or tomtom) then return false, "waypoints are not allowed on this map" end
		return true
	end,
}

-- What a goto found, by action, kept apart from the action's fields (those come from the model).
local reached = setmetatable({}, { __mode = "k" })

local function questTitle(questID)
	local title = C_QuestLog.GetTitleForQuestID and C_QuestLog.GetTitleForQuestID(questID)
	if not ns.Trim(title, 80) and C_TaskQuest and C_TaskQuest.GetQuestInfoByQuestID then
		title = C_TaskQuest.GetQuestInfoByQuestID(questID)
	end
	return ns.Trim(title, 80)
end

-- A quest in the log, or a world quest that is up; nil for any other quest ID.
local function questPlace(questID)
	local inLog = C_QuestLog.GetLogIndexForQuestID and ns.Plain(C_QuestLog.GetLogIndexForQuestID(questID))
	local zone = not inLog and C_TaskQuest and C_TaskQuest.GetQuestZoneID and ns.Plain(C_TaskQuest.GetQuestZoneID(questID))
	if not inLog and type(zone) ~= "number" then return nil end
	local place = { quest = questID, kind = "quest", name = questTitle(questID) or ("quest " .. questID), exact = true }
	if zone then
		local x, y = C_TaskQuest.GetQuestLocation(questID, zone)
		place.map, place.x, place.y = ns.Places.Pinnable(zone, ns.Plain(x), ns.Plain(y))
	end
	return place
end

-- Where the game itself says the quest's next step is.
local function nextWaypoint(questID)
	if not C_QuestLog.GetNextWaypoint then return nil end
	local map, x, y = C_QuestLog.GetNextWaypoint(questID)
	map, x, y = ns.Plain(map), ns.Plain(x), ns.Plain(y)
	if type(map) == "number" and type(x) == "number" and type(y) == "number" then return map, x, y end
	return nil
end

-- Quests go through the quest arrow, other places through a map pin.
local function travel(place)
	if place.quest and C_SuperTrack and C_SuperTrack.SetSuperTrackedQuestID then
		C_SuperTrack.SetSuperTrackedQuestID(place.quest)
		local map, x, y = nextWaypoint(place.quest)
		if map then place.map, place.x, place.y = map, x, y end
		place.tomtom = place.map ~= nil and addTomTom(place.map, place.x, place.y, place.name)
		return true
	end
	if not place.map then return false, "the game gives no position for it" end
	local blizzard, tomtom = setPin(place.map, place.x, place.y, place.name)
	place.tomtom = tomtom
	if not (blizzard or tomtom) then return false, "the game allows no waypoint there" end
	return true
end

local function placeList(list)
	local parts = {}
	for _, p in ipairs(list) do
		parts[#parts + 1] = E(p.name) .. " (" .. p.kind .. (p.zone and (", " .. E(p.zone)) or "") .. ")"
	end
	return table.concat(parts, "; ")
end

-- `goto` is a plain name in Lua 5.1, which WoW runs (it became a keyword in 5.2).
handlers.goto = {
	instant = true,
	order = 6,
	check = function(a)
		a.name = str(a.name, 80)
		a.kind = type(a.kind) == "string" and a.kind:lower() or "any"
		if not ns.Places.KINDS[a.kind] then a.kind = "any" end
		a.quest = int(a.quest, 1)
		return (a.name or a.quest) ~= nil, "needs a place name or a quest ID"
	end,
	describe = function(a)
		local found = reached[a]
		local p = found and found.place
		if not p then return "Go to " .. (a.name and ("\"" .. E(a.name) .. "\"") or ("quest " .. a.quest)) end
		local line = (p.quest and ("Following " .. p.kind .. ": ") or "Map pin: ") .. E(p.name)
			.. ((not p.quest and (" (" .. p.kind .. ")")) or "")
		if p.zone then line = line .. " in " .. E(p.zone) end
		if p.map then line = line .. string.format(" at %.1f, %.1f", p.x * 100, p.y * 100) end
		if p.tomtom then line = line .. ", also in TomTom" end
		if not p.exact and #found.others > 0 then
			line = line .. "\n|cffbbbbbbOther matches: " .. placeList(found.others) .. "|r"
		end
		return line
	end,
	run = function(a)
		local found = { others = {} }
		reached[a] = found
		found.place = a.quest and questPlace(a.quest)
		if not found.place and a.name then
			local result = ns.Places.Find(a.name, a.kind)
			found.place, found.others = result.place, result.others
		end
		local p = found.place
		if not p then
			if #found.others > 0 then return false, "couldn't find it; close matches: " .. placeList(found.others) end
			if not a.name then return false, "that quest is neither in your quest log nor up as a world quest" end
			return false, "couldn't find it near you or on this continent"
		end
		local ok, why = travel(p)
		if ok and p.map then p.zone = ns.Places.MapName(p.map) or p.zone end
		return ok, why
	end,
}

handlers.track_quest = {
	instant = true,
	order = 7,
	check = function(a)
		a.quest = int(a.quest, 1)
		return a.quest ~= nil, "needs a quest ID"
	end,
	describe = function(a) return "Follow quest " .. a.quest end,
	run = function(a)
		if not (C_SuperTrack and C_SuperTrack.SetSuperTrackedQuestID) then
			return false, "the quest arrow is not available in this game version"
		end
		C_SuperTrack.SetSuperTrackedQuestID(a.quest)
		return true
	end,
}

handlers.mark = {
	instant = true,
	order = 5,
	check = function(a)
		a.icon = int(a.icon, 0, 8)
		a.unit = (a.unit == "focus" or a.unit == "mouseover" or a.unit == "player") and a.unit or "target"
		return a.icon ~= nil, "needs a marker from 0 to 8"
	end,
	describe = function(a)
		return "Mark " .. a.unit .. " with icon " .. a.icon .. (a.targetChanged and " |cffff8800(your target changed)|r" or "")
	end,
	run = function(a)
		if not UnitExists(a.unit) then return false, "no " .. a.unit end
		SetRaidTarget(a.unit, a.icon)
		return true
	end,
}

handlers.macro = {
	order = 1,
	check = function(a)
		a.name = str(a.name, 16)
		a.body = str(a.body, 255)
		a.char = a.char == true
		if not (a.name and a.body) then return false, "needs a name (16 characters at most) and a body (255 at most)" end
		local problem = macroBodyProblem(a.body)
		if problem then return false, problem end
		return true
	end,
	describe = function(a)
		local verb = macroIndex(a.name) > 0 and "Update macro" or "Create macro"
		return verb .. " \"" .. E(a.name) .. "\":\n|cffbbbbbb" .. E(a.body) .. "|r"
	end,
	run = function(a)
		local index = macroIndex(a.name)
		if index > 0 then
			EditMacro(index, a.name, a.icon and iconFor(a.icon) or nil, a.body)
			return true
		end
		local maxAccount, maxChar = macroLimits()
		local numAccount, numChar = GetNumMacros()
		if a.char and numChar >= maxChar then return false, "character macro slots are full" end
		if not a.char and numAccount >= maxAccount then return false, "account macro slots are full" end
		CreateMacro(a.name, iconFor(a.icon), a.body, a.char)
		return true
	end,
}

handlers.bar = {
	order = 2,
	check = function(a)
		a.macro = str(a.macro, 16)
		a.slot = int(a.slot, 1, 180)
		return a.macro ~= nil and a.slot ~= nil, "needs a macro name and a slot from 1 to 180"
	end,
	describe = function(a) return "Put \"" .. E(a.macro) .. "\" on action slot " .. a.slot end,
	run = function(a)
		if macroIndex(a.macro) == 0 then return false, "macro \"" .. E(a.macro) .. "\" not found" end
		local place = PlaceAction or (C_ActionBar and C_ActionBar.PutActionInSlot)
		if not place then return false, "action bar placement not available" end
		ClearCursor()
		PickupMacro(a.macro)
		place(a.slot)
		ClearCursor()
		return true
	end,
}

handlers.bind = {
	order = 3,
	check = function(a)
		a.key = str(a.key, 32)
		a.macro = str(a.macro, 16)
		if not (a.key and a.key:match("^[%w%-]+$") and a.macro) then return false, "needs a key such as SHIFT-E and a macro name" end
		a.key = a.key:upper()
		return true
	end,
	-- Replacing an existing binding (a movement key, say) always asks, even with auto-apply.
	replaces = function(a)
		local current = GetBindingAction(a.key)
		if current and current ~= "" and current ~= "MACRO " .. a.macro then return current end
		return nil
	end,
	describe = function(a, h)
		local current = h.replaces(a)
		return "Bind " .. E(a.key) .. " to \"" .. E(a.macro) .. "\"" .. (current and (" |cffff8800(replaces " .. E(current) .. ")|r") or "")
	end,
	run = function(a)
		if not bindMacro(a.key, a.macro) then return false, "could not bind " .. E(a.key) end
		SaveBindings(GetCurrentBindingSet())
		return true
	end,
}

handlers.setting = {
	order = 4,
	check = function(a)
		a.name = str(a.name, 64)
		if type(a.value) == "boolean" then a.value = a.value and "1" or "0" end
		if type(a.value) == "number" then a.value = tostring(a.value) end
		a.value = str(a.value, 32)
		if not (a.name and CVAR_ALLOW[a.name]) then return false, "only certain game settings may be changed" end
		return a.value ~= nil, "needs a value"
	end,
	describe = function(a) return "Set " .. a.name .. " = " .. E(a.value) end,
	run = function(a)
		ns.SetCVar(a.name, a.value)
		return true
	end,
}

Actions.MACRO_COMMANDS = MACRO_COMMANDS
Actions.CVAR_ALLOW = CVAR_ALLOW

local pending -- changes waiting for Apply

local function describe(a)
	local h = handlers[a.type]
	return h.describe(a, h)
end

-- What became of each action, for the next request's `last`. An entry is reported once in
-- every state it reaches (waiting for Apply, then applied, failed or declined); the newest
-- MAX_RESULTS are kept.
local MAX_RESULTS, RESULT_BYTES = 6, 120
ns.lastResults = {}
local resultOf = setmetatable({}, { __mode = "k" })

-- Panel text as plain text: colour codes removed, doubled pipes single again.
local function plainText(text)
	return (text:gsub("||", "\1"):gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", ""):gsub("\1", "|"))
end

local function note(a, ok, say)
	local entry = resultOf[a]
	if not entry then
		entry = { type = ns.Trim(tostring(a.type), 24) }
		resultOf[a] = entry
	end
	entry.ok, entry.say = ok, plainText(say)
	for i, e in ipairs(ns.lastResults) do
		if e == entry then table.remove(ns.lastResults, i); break end
	end
	table.insert(ns.lastResults, entry)
	while #ns.lastResults > MAX_RESULTS do table.remove(ns.lastResults, 1) end
end

-- The entries not reported yet, with `say` cut to sayBytes; nil when there are none.
function Actions.Results(sayBytes)
	local out = {}
	for i, e in ipairs(ns.lastResults) do
		out[i] = { type = e.type, ok = e.ok, say = ns.Trim(e.say, (sayBytes or RESULT_BYTES) - 3) }
	end
	return #out > 0 and out or nil
end

function Actions.ClearResults()
	ns.lastResults = {}
end

-- `applied`: the player confirmed these, so the result names what they saw before running.
local function runList(list, applied)
	local okCount, problems, doneList = 0, {}, {}
	for _, a in ipairs(list) do
		local before = applied and firstLine(describe(a))
		local ok, success, err = pcall(handlers[a.type].run, a)
		local text = before or firstLine(describe(a))
		if ok and success then
			okCount = okCount + 1
			doneList[#doneList + 1] = a
			note(a, true, (applied and "applied: " or "") .. text)
		else
			local problem = text .. ": " .. tostring(ok and err or success)
			problems[#problems + 1] = problem
			note(a, false, problem)
		end
	end
	for _, p in ipairs(problems) do ns.UI.AddLine("|cffff5555Couldn't do|r " .. p) end
	return okCount, problems, doneList
end

local function noteAll(list, prefix)
	for _, a in ipairs(list or {}) do note(a, false, prefix .. firstLine(describe(a))) end
end

-- True when the unit a mark would hit is not the one the player had targeted when asking.
-- GUIDs identify a unit; names are the fallback when the game hides the GUID.
local function targetChanged(request)
	if not request then return false end
	local exists = UnitExists("target") and true or false
	if exists ~= request.hasTarget then return true end
	if not exists then return false end
	local guid = ns.Plain(UnitGUID("target"))
	if guid and request.targetGuid then return guid ~= request.targetGuid end
	return ns.Plain(UnitName("target")) ~= request.targetName
end

-- Validates the actions and splits them into instant ones and changes that need Apply.
-- `request` holds what the game looked like when the question was asked (the target).
function Actions.Handle(list, request)
	if type(list) ~= "table" then return end
	local instant, changes = {}, {}
	local needsConfirm = false
	for _, a in ipairs(list) do
		local h = type(a) == "table" and type(a.type) == "string" and handlers[a.type]
		if h then
			a.targetChanged = nil           -- set only here, never taken from the model
			local ok, why = h.check(a)
			if ok then
				if a.type == "mark" and a.unit == "target" and targetChanged(request) then
					a.targetChanged = true
				end
				if a.targetChanged or (h.replaces and h.replaces(a)) then needsConfirm = true end
				if h.instant and not a.targetChanged then instant[#instant + 1] = a else changes[#changes + 1] = a end
			else
				ns.UI.AddLine("|cff888888(skipped " .. a.type .. ": " .. E(why or "invalid") .. ")|r")
				note(a, false, "skipped: " .. (why or "invalid"))
			end
		elseif type(a) == "table" then
			ns.UI.AddLine("|cff888888(skipped " .. E(tostring(a.type)) .. ": not something Gnomecaster can do)|r")
			note(a, false, "skipped: not something Gnomecaster can do")
		end
	end
	table.sort(changes, function(x, y) return handlers[x.type].order < handlers[y.type].order end)

	if #instant > 0 then
		local _, _, doneList = runList(instant)
		for _, a in ipairs(doneList) do ns.UI.AddLine("|cff66ff66>|r " .. describe(a)) end
	end
	if #changes == 0 then return end
	if ns.db.autoApply and not needsConfirm then
		Actions.Apply(changes)
	else
		noteAll(pending, "dropped, a newer answer replaced it: ")
		pending = changes
		noteAll(changes, "waiting for the player to click Apply: ")
		local lines = {}
		for _, a in ipairs(changes) do lines[#lines + 1] = "- " .. describe(a) end
		ns.UI.ShowConfirm(table.concat(lines, "\n"))
	end
end

local waitFrame
function Actions.Apply(list)
	list = list or pending
	pending = nil
	ns.UI.HideConfirm()
	if not list then return end
	if ns.InCombat() then
		ns.UI.AddLine("In combat: I'll apply this when combat ends.")
		noteAll(list, "applies when combat ends: ")
		waitFrame = waitFrame or CreateFrame("Frame")
		waitFrame:RegisterEvent("PLAYER_REGEN_ENABLED")
		waitFrame:SetScript("OnEvent", function(self)
			self:UnregisterEvent("PLAYER_REGEN_ENABLED")
			Actions.Apply(list)
		end)
		return
	end
	local done = runList(list, true)
	if done > 0 then
		ns.UI.AddLine(string.format("|cff66ff66Done:|r %d change%s applied.", done, done == 1 and "" or "s"))
	end
end

function Actions.Cancel()
	noteAll(pending, "declined by the player: ")
	pending = nil
	ns.UI.HideConfirm()
	ns.UI.AddLine("|cff888888Cancelled.|r")
end
