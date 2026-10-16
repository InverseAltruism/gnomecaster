-- Gathers what the assistant needs to know, straight from the game client
-- (always current for the patch the player is on). Every section is wrapped
-- in pcall so a missing API on one game flavor never breaks the request.
local _, ns = ...

local Context = {}
ns.Context = Context

local floor = math.floor
local P = function(v) return ns.Plain(v) end

local function trim(s, n)
	if type(s) ~= "string" or ns.IsSecret(s) then return nil end
	if #s > n then return s:sub(1, n) .. "..." end
	return s
end

local function round4(v)
	if type(v) ~= "number" or ns.IsSecret(v) then return nil end
	return floor(v * 10000 + 0.5) / 10000
end

local function section(ctx, key, fn)
	local ok, value = pcall(fn)
	if ok and value ~= nil then ctx[key] = value end
end

local function collectGame()
	local version, build, _, toc = GetBuildInfo()
	return { version = version, build = build, toc = toc, project = WOW_PROJECT_ID, locale = GetLocale() }
end

local function collectPlayer()
	local _, classFile = UnitClass("player")
	local _, raceFile = UnitRace("player")
	local p = {
		class = P(classFile), race = P(raceFile),
		level = P(UnitLevel("player")), faction = P(UnitFactionGroup("player")),
	}
	local getSpec = (C_SpecializationInfo and C_SpecializationInfo.GetSpecialization) or GetSpecialization
	local getSpecInfo = (C_SpecializationInfo and C_SpecializationInfo.GetSpecializationInfo) or GetSpecializationInfo
	if getSpec and getSpecInfo then
		local idx = P(getSpec())
		if type(idx) == "number" and idx > 0 then
			local _, name = getSpecInfo(idx)
			p.spec = P(name)
		end
	end
	p.combat = ns.InCombat()
	return p
end

local function collectLocation()
	local loc = {
		zone = trim(GetZoneText and GetZoneText(), 60),
		subzone = trim(GetSubZoneText and GetSubZoneText(), 60),
	}
	local inInstance, instanceType = IsInInstance()
	if P(inInstance) then loc.instance = P(instanceType) end
	if C_Map and C_Map.GetBestMapForUnit then
		local mapID = P(C_Map.GetBestMapForUnit("player"))
		if type(mapID) == "number" then
			loc.mapID = mapID
			local info = C_Map.GetMapInfo(mapID)
			if info then loc.map = trim(info.name, 60) end
			-- nil inside instances (addons have not had positions there since 7.1)
			local pos = C_Map.GetPlayerMapPosition(mapID, "player")
			if pos then
				local x, y = pos:GetXY()
				loc.x, loc.y = round4(x), round4(y)
			end
		end
	end
	return loc
end

local function collectTarget()
	local exists = UnitExists("target")
	if ns.IsSecret(exists) or not exists then return nil end
	return {
		name = trim(P(UnitName("target")), 60),
		level = P(UnitLevel("target")),
		hostile = P(UnitCanAttack("player", "target")),
		dead = P(UnitIsDead("target")),
		player = P(UnitIsPlayer("target")),
	}
end

local function objectivesModern(questID)
	local list = {}
	local objs = C_QuestLog.GetQuestObjectives and C_QuestLog.GetQuestObjectives(questID)
	if objs then
		for _, o in ipairs(objs) do
			local text = trim(o.text, 70)
			if text and text ~= "" then list[#list + 1] = text end
		end
	end
	return #list > 0 and list or nil
end

local function collectQuests(max, withObjectives)
	local list = {}
	if C_QuestLog and C_QuestLog.GetNumQuestLogEntries and C_QuestLog.GetInfo then
		for i = 1, C_QuestLog.GetNumQuestLogEntries() do
			local info = C_QuestLog.GetInfo(i)
			if info and not info.isHeader and not info.isHidden and info.questID then
				local q = { id = info.questID, title = trim(info.title, 70), level = info.level }
				if C_QuestLog.IsComplete and C_QuestLog.IsComplete(info.questID) then q.done = true end
				if withObjectives then q.obj = objectivesModern(info.questID) end
				list[#list + 1] = q
				if #list >= max then break end
			end
		end
	elseif GetNumQuestLogEntries and GetQuestLogTitle then
		for i = 1, GetNumQuestLogEntries() do
			local title, level, _, isHeader, _, isComplete, _, questID = GetQuestLogTitle(i)
			if title and not isHeader then
				local q = { id = questID, title = trim(title, 70), level = level }
				if isComplete == 1 then q.done = true end
				if withObjectives and GetNumQuestLeaderBoards then
					local objs = {}
					for j = 1, GetNumQuestLeaderBoards(i) do
						local text = trim(GetQuestLogLeaderBoard(j, i), 70)
						if text then objs[#objs + 1] = text end
					end
					if #objs > 0 then q.obj = objs end
				end
				list[#list + 1] = q
				if #list >= max then break end
			end
		end
	end
	return #list > 0 and list or nil
end

-- The quest the player is following, plus where the game says to go next.
local function collectFocus()
	if not (C_SuperTrack and C_SuperTrack.GetSuperTrackedQuestID) then return nil end
	local questID = P(C_SuperTrack.GetSuperTrackedQuestID())
	if type(questID) ~= "number" or questID == 0 then return nil end
	local focus = { quest = questID }
	if C_QuestLog.GetTitleForQuestID then focus.title = trim(C_QuestLog.GetTitleForQuestID(questID), 70) end
	focus.obj = objectivesModern(questID)
	if C_QuestLog.GetNextWaypoint then
		local mapID, x, y = C_QuestLog.GetNextWaypoint(questID)
		if mapID then focus.next = { map = mapID, x = round4(x), y = round4(y) } end
	end
	return focus
end

-- level 1 = everything, higher levels drop detail to fit the screenshot channel
function Context.Collect(level)
	level = level or 1
	local ctx = {}
	section(ctx, "game", collectGame)
	section(ctx, "player", collectPlayer)
	section(ctx, "location", collectLocation)
	section(ctx, "target", collectTarget)
	section(ctx, "focus", collectFocus)
	if level <= 3 then
		local max = (level == 1 and 12) or (level == 2 and 8) or 4
		section(ctx, "quests", function() return collectQuests(max, level == 1) end)
	end
	if level <= 4 then
		section(ctx, "errors", function()
			local e = ns.Errors.Snapshot()
			return next(e) and e or nil
		end)
	end
	return ctx
end
