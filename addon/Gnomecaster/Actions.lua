-- Executes what the assistant asked for, using only normal addon APIs.
-- Every action is checked here again (the model and the companion are not
-- trusted). Navigation runs at once; changes to macros, bars, keys and
-- settings wait for the player's confirmation unless auto-apply is on.
-- Nothing runs in combat: Blizzard blocks these functions there anyway.
local _, ns = ...

local Actions = {}
ns.Actions = Actions

local DEFAULT_ICON = 134400 -- question mark; #showtooltip macros show the spell icon

local CVAR_ALLOW = {
	autoLootDefault = true, nameplateShowEnemies = true, nameplateShowFriends = true,
	nameplateShowAll = true, Sound_EnableMusic = true, Sound_EnableAmbience = true,
	cameraDistanceMaxZoomFactor = true, autoQuestWatch = true, showTutorials = true,
	scriptErrors = true, ActionButtonUseKeyDown = true, softTargetEnemy = true,
	softTargetInteract = true, autoSelfCast = true, chatBubbles = true,
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

local function iconFor(name)
	if type(name) == "number" then return name end
	if type(name) == "string" and GetFileIDFromPath then
		return GetFileIDFromPath("Interface\\Icons\\" .. name) or DEFAULT_ICON
	end
	return DEFAULT_ICON
end

local handlers = {}

handlers.waypoint = {
	instant = true,
	check = function(a)
		a.map = num(a.map, 1)
		a.x, a.y = num(a.x, 0, 100), num(a.y, 0, 100)
		if not (a.map and a.x and a.y) then return false end
		if a.x > 1 or a.y > 1 then a.x, a.y = a.x / 100, a.y / 100 end
		a.title = str(a.title, 80) or "Gnomecaster"
		return true
	end,
	describe = function(a)
		return string.format("Waypoint: %s (%.1f, %.1f)", a.title, a.x * 100, a.y * 100)
	end,
	run = function(a)
		local done = false
		if C_Map and C_Map.SetUserWaypoint and UiMapPoint then
			if not C_Map.CanSetUserWaypointOnMap or C_Map.CanSetUserWaypointOnMap(a.map) then
				C_Map.SetUserWaypoint(UiMapPoint.CreateFromCoordinates(a.map, a.x, a.y))
				if C_SuperTrack and C_SuperTrack.SetSuperTrackedUserWaypoint then
					C_SuperTrack.SetSuperTrackedUserWaypoint(true)
				end
				done = true
			end
		end
		if TomTom and TomTom.AddWaypoint then
			TomTom:AddWaypoint(a.map, a.x, a.y, { title = a.title, from = "Gnomecaster", persistent = false })
			done = true
		end
		if not done then return false, "waypoints are not allowed on this map" end
		return true
	end,
}

handlers.track_quest = {
	instant = true,
	check = function(a) a.quest = num(a.quest, 1) return a.quest ~= nil end,
	describe = function(a) return "Follow quest " .. a.quest end,
	run = function(a)
		if not (C_SuperTrack and C_SuperTrack.SetSuperTrackedQuestID) then
			return false, "quest tracking arrow not available in this game version"
		end
		C_SuperTrack.SetSuperTrackedQuestID(a.quest)
		return true
	end,
}

handlers.mark = {
	instant = true,
	check = function(a)
		a.icon = num(a.icon, 0, 8)
		a.unit = (a.unit == "focus" or a.unit == "mouseover" or a.unit == "player") and a.unit or "target"
		return a.icon ~= nil
	end,
	describe = function(a) return "Mark " .. a.unit .. " with icon " .. a.icon end,
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
		return a.name ~= nil and a.body ~= nil
	end,
	describe = function(a)
		local exists = GetMacroIndexByName(a.name)
		local verb = (exists and exists > 0) and "Update macro" or "Create macro"
		return verb .. " \"" .. a.name .. "\":\n|cffbbbbbb" .. a.body .. "|r"
	end,
	run = function(a)
		local index = GetMacroIndexByName(a.name)
		if index and index > 0 then
			EditMacro(index, a.name, a.icon and iconFor(a.icon) or nil, a.body)
			return true
		end
		local numAccount, numChar = GetNumMacros()
		if a.char and numChar >= (MAX_CHARACTER_MACROS or 18) then return false, "character macro slots are full" end
		if not a.char and numAccount >= (MAX_ACCOUNT_MACROS or 120) then return false, "account macro slots are full" end
		CreateMacro(a.name, iconFor(a.icon), a.body, a.char)
		return true
	end,
}

handlers.bar = {
	order = 2,
	check = function(a)
		a.macro = str(a.macro, 16)
		a.slot = num(a.slot, 1, 180)
		return a.macro ~= nil and a.slot ~= nil
	end,
	describe = function(a) return "Put \"" .. a.macro .. "\" on action slot " .. a.slot end,
	run = function(a)
		if (GetMacroIndexByName(a.macro) or 0) == 0 then return false, "macro \"" .. a.macro .. "\" not found" end
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
		return a.key ~= nil and a.key:match("^[%w%-]+$") ~= nil and a.macro ~= nil
	end,
	describe = function(a)
		local current = GetBindingAction(a.key)
		local note = (current and current ~= "") and (" |cffff8800(replaces " .. current .. ")|r") or ""
		return "Bind " .. a.key .. " to \"" .. a.macro .. "\"" .. note
	end,
	run = function(a)
		if not SetBindingMacro(a.key, a.macro) then return false, "could not bind " .. a.key end
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
		return a.name ~= nil and CVAR_ALLOW[a.name] == true and a.value ~= nil
	end,
	describe = function(a) return "Set " .. a.name .. " = " .. a.value end,
	run = function(a)
		ns.SetCVar(a.name, a.value)
		return true
	end,
}

local pending -- confirmed changes waiting for Apply

local function runList(list)
	local okCount, problems, doneList = 0, {}, {}
	for _, a in ipairs(list) do
		local ok, success, err = pcall(handlers[a.type].run, a)
		if ok and success then
			okCount = okCount + 1
			doneList[#doneList + 1] = a
		else
			problems[#problems + 1] = handlers[a.type].describe(a):match("^[^\n]*") .. ": " .. tostring(ok and err or success)
		end
	end
	for _, p in ipairs(problems) do ns.UI.AddLine("|cffff5555Couldn't do|r " .. p) end
	return okCount, problems, doneList
end

-- Validate and split into instant actions and changes needing confirmation.
function Actions.Handle(list)
	if type(list) ~= "table" then return end
	local instant, changes = {}, {}
	for _, a in ipairs(list) do
		local h = type(a) == "table" and handlers[a.type]
		if h and h.check(a) then
			if h.instant then instant[#instant + 1] = a else changes[#changes + 1] = a end
		elseif type(a) == "table" then
			ns.UI.AddLine("|cff888888(skipped an action I couldn't verify: " .. tostring(a.type) .. ")|r")
		end
	end
	table.sort(changes, function(x, y) return handlers[x.type].order < handlers[y.type].order end)

	if #instant > 0 then
		local _, _, doneList = runList(instant)
		for _, a in ipairs(doneList) do ns.UI.AddLine("|cff66ff66>|r " .. handlers[a.type].describe(a)) end
	end
	if #changes == 0 then return end
	if ns.db.autoApply then
		Actions.Apply(changes)
	else
		pending = changes
		local lines = {}
		for _, a in ipairs(changes) do lines[#lines + 1] = "- " .. handlers[a.type].describe(a) end
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
		ns.UI.AddLine("In combat - I'll apply this when combat ends.")
		waitFrame = waitFrame or CreateFrame("Frame")
		waitFrame:RegisterEvent("PLAYER_REGEN_ENABLED")
		waitFrame:SetScript("OnEvent", function(self)
			self:UnregisterEvent("PLAYER_REGEN_ENABLED")
			Actions.Apply(list)
		end)
		return
	end
	local done, problems = runList(list)
	if done > 0 then
		ns.UI.AddLine(string.format("|cff66ff66Done:|r %d change%s applied.", done, done == 1 and "" or "s"))
	end
end

function Actions.Cancel()
	pending = nil
	ns.UI.HideConfirm()
	ns.UI.AddLine("|cff888888Cancelled.|r")
end
