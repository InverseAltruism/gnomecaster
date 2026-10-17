-- Gathers what the assistant needs to know, straight from the game client
-- (always current for the patch the player is on). Every section is wrapped
-- in pcall so a missing API on one game flavor never breaks the request.
local _, ns = ...

local Context = {}
ns.Context = Context

local floor = math.floor
local P = function(v) return ns.Plain(v) end

local trim = ns.Trim

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
			local within = {}         -- the zone and continent around this map
			for i, parent in ipairs(ns.Places.Ancestors(mapID)) do
				if i > 1 and parent.name then within[#within + 1] = parent.name end
			end
			if #within > 0 then loc.within = within end
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

-- Quest levels only say something when they differ from the player's (Retail scales most).
local function addLevel(q, level, playerLevel)
	level = P(level)
	if type(level) == "number" and level > 0 and level ~= playerLevel then q.level = level end
end

-- The `n` quests nearest to the player on this continent, nearest first, leaving out `skip`.
local function nearest(list, n, skip)
	local scored = {}
	if n > 0 and C_QuestLog.GetDistanceSqToQuest then
		for _, q in ipairs(list) do
			if q.id ~= skip then
				local d, onContinent = C_QuestLog.GetDistanceSqToQuest(q.id)
				d = P(d)
				if type(d) == "number" and P(onContinent) then scored[#scored + 1] = { q = q, d = d } end
			end
		end
		table.sort(scored, function(a, b) return a.d < b.d end)
	end
	local out = {}
	for i = 1, math.min(n, #scored) do out[i] = scored[i].q end
	return out
end

-- The quest log in its own order: id, title, the log's zone header, done, and objectives for
-- the `opts.objectives` nearest quests (the followed quest has its own in focus).
local function questsModern(opts, playerLevel)
	local list, header = {}, nil
	for i = 1, C_QuestLog.GetNumQuestLogEntries() do
		local info = C_QuestLog.GetInfo(i)
		if info and P(info.isHeader) then
			header = trim(info.title, 40)
		elseif info and not P(info.isHidden) and P(info.questID) then
			local q = { id = P(info.questID), title = trim(info.title, 70) }
			if opts.zones then q.zone = header end
			addLevel(q, info.level, playerLevel)
			if C_QuestLog.IsComplete and P(C_QuestLog.IsComplete(q.id)) then q.done = true end
			list[#list + 1] = q
			if #list >= opts.quests then break end
		end
	end
	local followed = C_SuperTrack and C_SuperTrack.GetSuperTrackedQuestID and P(C_SuperTrack.GetSuperTrackedQuestID())
	for _, q in ipairs(nearest(list, opts.objectives or 0, followed)) do q.obj = objectivesModern(q.id) end
	return list
end

-- Classic flavors: the same from the old quest log; objectives for the first quests.
local function questsClassic(opts, playerLevel)
	local list, header = {}, nil
	for i = 1, GetNumQuestLogEntries() do
		local title, level, _, isHeader, _, isComplete, _, questID = GetQuestLogTitle(i)
		if title and isHeader then
			header = trim(title, 40)
		elseif title then
			local q = { id = questID, title = trim(title, 70) }
			if opts.zones then q.zone = header end
			addLevel(q, level, playerLevel)
			if isComplete == 1 then q.done = true end
			if #list < (opts.objectives or 0) and GetNumQuestLeaderBoards then
				local objs = {}
				for j = 1, GetNumQuestLeaderBoards(i) do
					local text = trim(GetQuestLogLeaderBoard(j, i), 70)
					if text then objs[#objs + 1] = text end
				end
				if #objs > 0 then q.obj = objs end
			end
			list[#list + 1] = q
			if #list >= opts.quests then break end
		end
	end
	return list
end

local function collectQuests(opts)
	local playerLevel = P(UnitLevel("player"))
	local list
	if C_QuestLog and C_QuestLog.GetNumQuestLogEntries and C_QuestLog.GetInfo then
		list = questsModern(opts, playerLevel)
	elseif GetNumQuestLogEntries and GetQuestLogTitle then
		list = questsClassic(opts, playerLevel)
	end
	return list and #list > 0 and list or nil
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

-- Detail levels, from everything down to the bare minimum. Request.lua tries them in order
-- until the packet fits the screenshot channel. Place names (what goto can find) outlast
-- quest zones and objectives. `last` caps each action result's text.
local LEVELS = {
	{ quests = 40, zones = true, objectives = 3, places = 10, errors = true, last = 120 },
	{ quests = 40, zones = true, objectives = 1, places = 10, errors = true, last = 120 },
	{ quests = 40, places = 10, errors = true, last = 120 },
	{ quests = 25, places = 5, errors = true, last = 120 },
	{ quests = 12, errors = true, last = 40 },
	{ errors = true, last = 40 },
	{ last = 40 },
}
Context.LEVELS = LEVELS

function Context.Collect(level)
	local opts = LEVELS[level or 1] or LEVELS[#LEVELS]
	local ctx = {}
	section(ctx, "game", collectGame)
	section(ctx, "player", collectPlayer)
	section(ctx, "location", collectLocation)
	section(ctx, "target", collectTarget)
	section(ctx, "focus", collectFocus)
	if opts.quests then section(ctx, "quests", function() return collectQuests(opts) end) end
	if opts.places then section(ctx, "places", function() return ns.Places.Nearby(opts.places) end) end
	if opts.errors then
		section(ctx, "errors", function()
			local e = ns.Errors.Snapshot()
			return next(e) and e or nil
		end)
	end
	return ctx
end
