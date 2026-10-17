-- Map data for the mock (loaded by wowmock.lua): the API shapes are copied from Blizzard's
-- 12.1.5 documentation (MapDocumentation, EncounterJournalDocumentation, AreaPoiInfoDocumentation,
-- QuestTaskInfoDocumentation, TaxiMapDocumentation, QuestLogDocumentation). The world is a
-- German client's, made up for the tests: the map IDs, coordinates and the world boss are
-- invented; the place names follow the game's German names where they are known.
local M = MOCK
local record = M.record

Enum = Enum or {}
Enum.UIMapType = { Cosmic = 0, World = 1, Continent = 2, Zone = 3, Dungeon = 4, Micro = 5, Orphan = 6 }
Enum.QuestTagType = { Normal = 2, WorldBoss = 18 }
Enum.WorldQuestQuality = { Common = 0, Rare = 1, Epic = 2 }
Enum.FlightPathFaction = { Neutral = 0, Horde = 1, Alliance = 2 }

local function vec(x, y) return { x = x, y = y, GetXY = function(self) return self.x, self.y end } end
M.vec = vec

-- rect = where the map lies on its parent: left, right, top, bottom
M.maps = {
	[946] = { name = "Kosmos", mapType = 0, parent = 0 },
	[947] = { name = "Azeroth", mapType = 1, parent = 946 },
	[2537] = { name = "Quel'Thalas", mapType = 2, parent = 947 },
	[2395] = { name = "Immersangwald", mapType = 3, parent = 2537, rect = { 0.30, 0.60, 0.40, 0.80 } },
	[2393] = { name = "Silbermond", mapType = 3, parent = 2395, rect = { 0.55, 0.75, 0.15, 0.45 } },
	[2437] = { name = "Zul'Aman", mapType = 3, parent = 2537, rect = { 0.60, 0.95, 0.40, 0.80 } },
	[2424] = { name = "Insel von Quel'Danas", mapType = 3, parent = 2537, rect = { 0.35, 0.55, 0.00, 0.20 } },
	[2274] = { name = "Khaz Algar", mapType = 2, parent = 947 },
	[2339] = { name = "Dornogal", mapType = 3, parent = 2274, rect = { 0.10, 0.30, 0.10, 0.30 } },
	[2214] = { name = "Die Klingenden Tiefen", mapType = 3, parent = 2274, rect = { 0.40, 0.70, 0.40, 0.70 } },
}
M.playerMap = 2395

-- per map: what the API returns for that map, positions in that map's coordinates
M.entrances = {
	[2424] = { { areaPoiID = 7001, position = vec(0.61, 0.31), name = "Terrasse der Magister", description = "",
		atlasName = "Dungeon", journalInstanceID = 249 } },
	[2537] = {
		{ areaPoiID = 7001, position = vec(0.472, 0.062), name = "Terrasse der Magister", description = "",
			atlasName = "Dungeon", journalInstanceID = 249 },
		-- only on the continent's list: finding it means moving it onto the zone under it
		{ areaPoiID = 7002, position = vec(0.47, 0.06), name = "Sonnenbrunnenplateau", description = "",
			atlasName = "Raid", journalInstanceID = 752 },
	},
	[2437] = { { areaPoiID = 7003, position = vec(0.30, 0.55), name = "Zul'Aman", description = "",
		atlasName = "Dungeon", journalInstanceID = 77 } },
	[2214] = { { areaPoiID = 7004, position = vec(0.45, 0.30), name = "Die Steingewölbe", description = "",
		atlasName = "Dungeon", journalInstanceID = 1269 } },
}
M.raids = { [752] = true }

M.delves = { [2437] = { 8001 }, [2395] = { 8002 }, [2537] = { 8001, 8002 } }
M.pois = {
	[2437] = { [8001] = { name = "Atal'Aman", position = vec(0.432, 0.610) } },
	[2395] = { [8002] = { name = "Kluft der Ewigkeit", position = vec(0.20, 0.30) } },
	[2537] = { [8001] = { name = "Atal'Aman", position = vec(0.751, 0.644) },
		[8002] = { name = "Kluft der Ewigkeit", position = vec(0.36, 0.52) } },
	[2393] = { [9001] = { name = "Gegenstandsaufwertung", position = vec(0.48, 0.62) },
		[9002] = { name = "Große Schatzkammer", position = vec(0.40, 0.55) } },
}
-- GetAreaPOIForMap: every POI on the map, delves included (Places must not list them twice)
M.areaPoiLists = { [2437] = { 8001 }, [2393] = { 9001, 9002 } }

M.tasks = {
	[2437] = { { questID = 92001, mapID = 2437, x = 0.71, y = 0.22, numObjectives = 1, isQuestStart = false,
		isDaily = false, isCombatAllyQuest = false, isMeta = false, inProgress = false, isMapIndicatorQuest = false },
		{ questID = 92002, mapID = 2437, x = 0.40, y = 0.40, numObjectives = 1, isQuestStart = false,
		isDaily = false, isCombatAllyQuest = false, isMeta = false, inProgress = false, isMapIndicatorQuest = false } },
	[2537] = { { questID = 92001, mapID = 2437, childDepth = 1, x = 0.8485, y = 0.488, numObjectives = 1, isQuestStart = false,
		isDaily = false, isCombatAllyQuest = false, isMeta = false, inProgress = false, isMapIndicatorQuest = false } },
	[2395] = { { questID = 92003, mapID = 2395, x = 0.66, y = 0.71, numObjectives = 1, isQuestStart = false,
		isDaily = false, isCombatAllyQuest = false, isMeta = false, inProgress = false, isMapIndicatorQuest = false } },
}
M.taskTitles = { [92001] = "Kul'thar der Zornige", [92002] = "Trollplage", [92003] = "Ruinenhüter" }
M.questTags = {
	[92001] = { tagName = "Weltboss", tagID = 0, worldQuestType = 18 },
	[92002] = { tagName = "Weltquest", tagID = 0, worldQuestType = 2, quality = 0 },
	[92003] = { tagName = "Weltquest", tagID = 0, worldQuestType = 2, quality = 2, isElite = true },  -- the older world boss marking
}

M.taxi = {
	[2393] = { { nodeID = 82, position = vec(0.52, 0.44), name = "Silbermond, Immersangwald", atlasName = "TaxiNode_Neutral",
		faction = 0, textureKit = "", isUndiscovered = false } },
	[2395] = { { nodeID = 83, position = vec(0.30, 0.60), name = "Faltruuns Rast", atlasName = "TaxiNode_Horde",
		faction = 1, textureKit = "", isUndiscovered = false } },
}

-- The clock Places measures its budget with stands still, so a busy test machine cannot cut a
-- search short; every map call advances it by M.msPerCall.
M.fakeMs, M.msPerCall, M.mapReads = 0, 0, 0
function debugprofilestop() return M.fakeMs end
local function cost() M.fakeMs = M.fakeMs + M.msPerCall end

function C_Map.GetBestMapForUnit() return M.playerMap end
function C_Map.GetMapInfo(id)
	local m = M.maps[id]
	if not m then return nil end
	return { mapID = id, name = m.name, mapType = m.mapType, parentMapID = m.parent, flags = 0 }
end
function C_Map.GetMapChildrenInfo(id, mapType, allDescendants)
	local out = {}
	local function under(childID)
		local p = M.maps[childID] and M.maps[childID].parent
		while p and p ~= 0 do
			if p == id then return true end
			if not allDescendants then return false end
			p = M.maps[p] and M.maps[p].parent
		end
		return false
	end
	local ids = {}
	for childID in pairs(M.maps) do ids[#ids + 1] = childID end
	table.sort(ids)
	for _, childID in ipairs(ids) do
		local m = M.maps[childID]
		if under(childID) and (mapType == nil or m.mapType == mapType) then out[#out + 1] = C_Map.GetMapInfo(childID) end
	end
	return out
end
function C_Map.CanSetUserWaypointOnMap(id) return M.maps[id] ~= nil and M.maps[id].mapType >= 3 end
function C_Map.GetMapRectOnMap(id, topID)
	local m = M.maps[id]
	if m and m.parent == topID and m.rect then return m.rect[1], m.rect[2], m.rect[3], m.rect[4] end
end
function C_Map.GetMapInfoAtPosition(id, x, y)
	for childID, m in pairs(M.maps) do
		local r = m.rect
		if m.parent == id and r and x >= r[1] and x <= r[2] and y >= r[3] and y <= r[4] then return C_Map.GetMapInfo(childID) end
	end
end

C_EncounterJournal = {}
function C_EncounterJournal.GetDungeonEntrancesForMap(id)
	cost()
	M.mapReads = M.mapReads + 1
	return M.entrances[id] or {}
end
-- EJ_GetInstanceInfo: name, description, bgImage, buttonImage1, loreImage, buttonImage2, dungeonAreaMapID,
-- link, shouldDisplayDifficulty, mapID, covenantID, isRaid (the 12th, as Blizzard's map pins read it)
function EJ_GetInstanceInfo(id) return "?", "", 0, 0, 0, 0, 0, "", true, 0, 0, M.raids[id] == true end

C_AreaPoiInfo = {}
function C_AreaPoiInfo.GetDelvesForMap(id) cost() return M.delves[id] or {} end
function C_AreaPoiInfo.GetAreaPOIForMap(id) cost() return M.areaPoiLists[id] or {} end
function C_AreaPoiInfo.GetAreaPOIInfo(mapID, poiID)
	local p = M.pois[mapID] and M.pois[mapID][poiID]
	if not p then return nil end
	return { areaPoiID = poiID, position = p.position, name = p.name, shouldGlow = false, isPrimaryMapForPOI = true,
		isAlwaysOnFlightmap = false, highlightWorldQuestsOnHover = false, highlightVignettesOnHover = false,
		isCurrentEvent = false, isSuppressible = false, isLocked = false }
end

C_TaskQuest = {}
function C_TaskQuest.GetQuestsOnMap(id) cost() return M.tasks[id] or {} end
function C_TaskQuest.GetQuestInfoByQuestID(id) return M.taskTitles[id] end
function C_TaskQuest.GetQuestZoneID(id)
	for _, list in pairs(M.tasks) do
		for _, t in ipairs(list) do if t.questID == id then return t.mapID end end
	end
end
function C_TaskQuest.GetQuestLocation(id, mapID)
	for _, t in ipairs(M.tasks[mapID] or {}) do if t.questID == id then return t.x, t.y end end
end
function C_QuestLog.GetQuestTagInfo(id) return M.questTags[id] end

C_TaxiMap = {}
function C_TaxiMap.GetTaxiNodesForMap(id) cost() return M.taxi[id] or {} end

M.questDistance = {}
function C_QuestLog.GetDistanceSqToQuest(id)
	local d = M.questDistance[id]
	if d then return d, true end
end
function C_QuestLog.GetLogIndexForQuestID(id)
	for i, q in ipairs(M.quests) do if q.questID == id then return i + 1 end end
end
