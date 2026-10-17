-- Finds places by name in the game's own map data, in the client's language: dungeon and raid
-- entrances, delves, world bosses and other world quests, flight points, area POIs, zones and
-- the quests in the log. The search reads the player's map, its continent and that
-- continent's zones, then other continents of the same world while the budget lasts. Each
-- data source runs under pcall, so an API missing on one game flavor only removes that source.
local _, ns = ...

local Places = {}
ns.Places = Places

local floor, min, max = math.floor, math.min, math.max
local plain = ns.Plain

-- Enum values from Blizzard's API documentation, for flavors without the Enum table.
local ENUM = Enum or {}
local MAP_TYPE = ENUM.UIMapType or {}
local CONTINENT = MAP_TYPE.Continent or 2
local ZONE = MAP_TYPE.Zone or 3
local TAG = ENUM.QuestTagType or {}
local TAG_NORMAL, TAG_WORLD_BOSS = TAG.Normal or 2, TAG.WorldBoss or 18
local EPIC = (ENUM.WorldQuestQuality and ENUM.WorldQuestQuality.Epic) or 2
local FLIGHT = ENUM.FlightPathFaction or {}
local FLIGHT_HORDE, FLIGHT_ALLIANCE = FLIGHT.Horde or 1, FLIGHT.Alliance or 2

-- One search reads at most MAX_MAPS maps and starts no new map after BUDGET_MS: a large or
-- slow world costs the client a short hitch, not a freeze.
local MAX_MAPS = 80
local BUDGET_MS = 30
Places.MAX_MAPS = MAX_MAPS

Places.KINDS = { dungeon = true, raid = true, delve = true, boss = true, quest = true,
	flight = true, poi = true, zone = true, any = true }
local RELATED = { dungeon = "raid", raid = "dungeon" }

-- Match quality. A best match needs MIN_BEST; close matches shown instead need MIN_CLOSE.
local EXACT, PREFIX, WORDS, PART, CONTAINS, FUZZY = 1000, 800, 700, 600, 550, 450
local MIN_BEST, MIN_CLOSE = 300, 150
local SAME_KIND, RELATED_KIND = 250, 125     -- the asked-for kind outranks one tier of match

local function now()
	if debugprofilestop then return debugprofilestop() end
	return GetTime() * 1000
end

-- Names ------------------------------------------------------------------

-- Latin letters with accents (UTF-8, U+00C0 to U+00FF) fold to their base letters.
local FOLD = {}
for base, letters in pairs({
	a = "ÀÁÂÃÄÅàáâãäå", ae = "Ææ", c = "Çç", d = "Ðð", e = "ÈÉÊËèéêë", i = "ÌÍÎÏìíîï",
	n = "Ññ", o = "ÒÓÔÕÖØòóôõöø", u = "ÙÚÛÜùúûü", y = "Ýýÿ", ss = "ß", th = "Þþ",
}) do
	for ch in letters:gmatch("[\192-\223][\128-\191]") do FOLD[ch] = base end
end

-- Words in lower case without accents; apostrophes, dashes and spaces only separate words.
-- Other UTF-8 letters (Cyrillic, Hangul, Han) are kept as they are.
local function normalize(s)
	s = s:gsub("[\192-\223][\128-\191]", FOLD)
	s = s:gsub("\226[\128\129][\128-\191]", " "):gsub("\194[\128-\191]", " "):lower()
	local words = {}
	for w in s:gmatch("[%w\128-\255]+") do words[#words + 1] = w end
	return { words = words, compact = table.concat(words) }
end
Places.Normalize = normalize

-- Edit distance, giving up (limit + 1) once it must exceed limit.
local function distance(a, b, limit)
	local la, lb = #a, #b
	if math.abs(la - lb) > limit then return limit + 1 end
	local prev = {}
	for j = 0, lb do prev[j] = j end
	for i = 1, la do
		local cur, ca, rowBest = { [0] = i }, a:byte(i), i
		for j = 1, lb do
			local v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + ((ca == b:byte(j)) and 0 or 1))
			cur[j] = v
			if v < rowBest then rowBest = v end
		end
		if rowBest > limit then return limit + 1 end
		prev = cur
	end
	return prev[lb]
end

local function startsAWord(words, w)
	for _, nw in ipairs(words) do
		if nw:sub(1, #w) == w then return true end
	end
	return false
end

local function closeWord(words, w)
	for _, nw in ipairs(words) do
		if nw == w or (#w >= 3 and nw:sub(1, #w) == w) or (#w >= 5 and distance(w, nw, 1) <= 1) then return true end
	end
	return false
end

-- How well name n matches what the player typed (q), from EXACT down to 0.
local function match(q, n)
	local qc, nc = q.compact, n.compact
	if qc == nc then return EXACT end
	if #qc >= 3 and nc:sub(1, #qc) == qc then return PREFIX end
	local all = #q.words > 0
	for _, w in ipairs(q.words) do
		if not startsAWord(n.words, w) then all = false; break end
	end
	if all then return WORDS end
	if #qc >= 3 and nc:find(qc, 1, true) then return PART end
	if #nc >= 5 and qc:find(nc, 1, true) then return CONTAINS end      -- "atal aman delve"
	local limit = max(1, floor(#qc / 4))
	local d = distance(qc, nc, limit)
	local score = d <= limit and (FUZZY - 50 * d) or 0
	local hits = 0
	for _, w in ipairs(q.words) do
		if closeWord(n.words, w) then hits = hits + 1 end
	end
	if hits > 0 and hits * 2 >= #q.words then score = max(score, floor(400 * hits / #q.words)) end
	return score
end
Places.Match = function(query, name) return match(normalize(query), normalize(name)) end

-- Maps -------------------------------------------------------------------

local function mapInfo(mapID)
	local info = C_Map.GetMapInfo(mapID)
	if not info then return nil end
	local id, kind = plain(info.mapID) or mapID, plain(info.mapType)
	return { mapID = id, name = ns.Trim(info.name, 60), mapType = type(kind) == "number" and kind or nil,
		parentMapID = plain(info.parentMapID) }
end

-- The map and its parents up to the continent (or to the top, outside any continent).
function Places.Ancestors(mapID)
	local list = {}
	local info = mapID and mapInfo(mapID)
	while info and #list < 8 do
		list[#list + 1] = info
		if not info.mapType or info.mapType <= CONTINENT then break end
		if type(info.parentMapID) ~= "number" or info.parentMapID == 0 then break end
		info = mapInfo(info.parentMapID)
	end
	return list
end

local function playerMap()
	local mapID = C_Map and C_Map.GetBestMapForUnit and plain(C_Map.GetBestMapForUnit("player"))
	return type(mapID) == "number" and mapID or nil
end

local function children(mapID, mapType)
	local ok, list = pcall(C_Map.GetMapChildrenInfo, mapID, mapType, true)
	return ok and type(list) == "table" and list or {}
end

local function canPin(mapID)
	if C_Map.CanSetUserWaypointOnMap then return plain(C_Map.CanSetUserWaypointOnMap(mapID)) == true end
	local info = mapInfo(mapID)
	return info ~= nil and info.mapType ~= nil and info.mapType >= ZONE
end

-- A point a user waypoint can hold. Places read on a map that takes none (a continent) move
-- onto the zone under them, through that zone's rectangle on the continent.
function Places.Pinnable(mapID, x, y)
	if canPin(mapID) then return mapID, x, y end
	if not C_Map.GetMapInfoAtPosition then return nil end
	local zone = C_Map.GetMapInfoAtPosition(mapID, x, y)
	local zoneID = zone and plain(zone.mapID)
	if type(zoneID) ~= "number" or zoneID == mapID or not canPin(zoneID) then return nil end
	local left, right, top, bottom = C_Map.GetMapRectOnMap(zoneID, mapID)
	left, right, top, bottom = plain(left), plain(right), plain(top), plain(bottom)
	if type(left) ~= "number" or type(right) ~= "number" or type(top) ~= "number" or type(bottom) ~= "number"
		or right <= left or bottom <= top then
		return nil
	end
	return zoneID, (x - left) / (right - left), (y - top) / (bottom - top)
end

-- Sources ----------------------------------------------------------------
-- Each reads one map and hands every place to s.add(kind, id, name, mapID, x, y, questID).
-- Positions are fractions of that map, as the API returns them for the map it was asked about.

local function xy(pos)
	if not pos then return nil end
	local x, y = pos:GetXY()
	x, y = plain(x), plain(y)
	if type(x) == "number" and type(y) == "number" then return x, y end
	return nil
end

local function isRaid(entrance)
	local journalID = plain(entrance.journalInstanceID)
	if EJ_GetInstanceInfo and journalID then
		local raid = plain(select(12, EJ_GetInstanceInfo(journalID)))
		if raid ~= nil then return raid == true end
	end
	return plain(entrance.atlasName) == "Raid"
end

local function entrances(s, mapID)
	if not (C_EncounterJournal and C_EncounterJournal.GetDungeonEntrancesForMap) then return end
	for _, e in ipairs(C_EncounterJournal.GetDungeonEntrancesForMap(mapID) or {}) do
		local x, y = xy(e.position)
		local poiID = plain(e.areaPoiID)
		if poiID then s.seenPoi[poiID] = true end
		s.add(isRaid(e) and "raid" or "dungeon", plain(e.journalInstanceID), e.name, mapID, x, y)
	end
end

local function areaPoi(mapID, poiID)
	local info = C_AreaPoiInfo.GetAreaPOIInfo(mapID, poiID)
	if not info then return nil end
	return info.name, xy(info.position)
end

local function delves(s, mapID)
	if not (C_AreaPoiInfo and C_AreaPoiInfo.GetDelvesForMap) then return end
	for _, poiID in ipairs(C_AreaPoiInfo.GetDelvesForMap(mapID) or {}) do
		poiID = plain(poiID)
		if poiID then
			s.seenPoi[poiID] = true
			local name, x, y = areaPoi(mapID, poiID)
			s.add("delve", poiID, name, mapID, x, y)
		end
	end
end

-- World bosses are world quests tagged WorldBoss, or (the older way) elite epic world quests,
-- as Blizzard's QuestUtils tells them apart.
local function isWorldBoss(questID)
	local tag = C_QuestLog.GetQuestTagInfo and C_QuestLog.GetQuestTagInfo(questID)
	if not tag then return false end
	local kind = plain(tag.worldQuestType)
	if kind == TAG_WORLD_BOSS then return true end
	return kind == TAG_NORMAL and plain(tag.isElite) == true and plain(tag.quality) == EPIC
end

local function taskQuests(s, mapID)
	if not (C_TaskQuest and C_TaskQuest.GetQuestsOnMap) then return end
	for _, t in ipairs(C_TaskQuest.GetQuestsOnMap(mapID) or {}) do
		local questID = plain(t.questID)
		if questID then
			local title = C_TaskQuest.GetQuestInfoByQuestID(questID)
			s.add(isWorldBoss(questID) and "boss" or "quest", questID, title, mapID, plain(t.x), plain(t.y), questID)
		end
	end
end

local function flightPoints(s, mapID)
	if not (C_TaxiMap and C_TaxiMap.GetTaxiNodesForMap) then return end
	local faction = plain(UnitFactionGroup("player"))
	for _, n in ipairs(C_TaxiMap.GetTaxiNodesForMap(mapID) or {}) do
		local side = plain(n.faction)
		-- as Blizzard's flight map: a faction's nodes only for that faction
		if not ((side == FLIGHT_HORDE and faction ~= "Horde") or (side == FLIGHT_ALLIANCE and faction ~= "Alliance")) then
			local x, y = xy(n.position)
			s.add("flight", plain(n.nodeID), n.name, mapID, x, y)
		end
	end
end

local function areaPois(s, mapID)
	if not (C_AreaPoiInfo and C_AreaPoiInfo.GetAreaPOIForMap) then return end
	for _, poiID in ipairs(C_AreaPoiInfo.GetAreaPOIForMap(mapID) or {}) do
		poiID = plain(poiID)
		if poiID and not s.seenPoi[poiID] then
			local name, x, y = areaPoi(mapID, poiID)
			s.add("poi", poiID, name, mapID, x, y)
		end
	end
end

local function zoneItself(s, mapID)
	local info = mapInfo(mapID)
	if info and info.mapType and info.mapType >= ZONE and canPin(mapID) then
		s.add("zone", mapID, info.name, mapID, 0.5, 0.5)
	end
end

-- Entrances and delves come first: their area POIs are then not listed again as plain POIs.
local SOURCES = { entrances, delves, taskQuests, flightPoints, areaPois, zoneItself }

local function readMap(s, mapID)
	for _, source in ipairs(SOURCES) do pcall(source, s, mapID) end
end

local function questLog(s)
	if not (C_QuestLog and C_QuestLog.GetNumQuestLogEntries and C_QuestLog.GetInfo) then return end
	for i = 1, C_QuestLog.GetNumQuestLogEntries() do
		local info = C_QuestLog.GetInfo(i)
		if info and not plain(info.isHeader) and not plain(info.isHidden) then
			local questID = plain(info.questID)
			if questID then s.add("quest", questID, info.title, nil, nil, nil, questID) end
		end
	end
end

-- Search -----------------------------------------------------------------

local function newSearch(name, kind)
	local s = { q = normalize(name), kind = kind, found = {}, byKey = {}, seenPoi = {}, visited = {},
		maps = 0, started = now(), best = 0 }
	function s.add(placeKind, id, placeName, mapID, x, y, questID)
		placeName = ns.Trim(placeName, 80)
		if not placeName or placeName == "" then return end
		if mapID and not (x and y) then return end
		local key = placeKind .. ":" .. tostring(id or placeName)
		if s.byKey[key] then return end
		local quality = match(s.q, normalize(placeName))
		if quality < MIN_CLOSE then return end
		local bonus = (s.kind == placeKind and SAME_KIND) or (RELATED[s.kind] == placeKind and RELATED_KIND) or 0
		local c = { name = placeName, kind = placeKind, map = mapID, x = x, y = y, quest = questID,
			quality = quality, score = quality + bonus, order = #s.found + 1 }
		s.byKey[key] = c
		s.found[#s.found + 1] = c
		if quality > s.best then s.best = quality end
	end
	return s
end

-- False once the map or time budget is spent.
local function visit(s, mapID)
	if type(mapID) ~= "number" or s.visited[mapID] then return true end
	if s.maps >= MAX_MAPS or now() - s.started > BUDGET_MS then return false end
	s.visited[mapID] = true
	s.maps = s.maps + 1
	readMap(s, mapID)
	return true
end

-- Zones first, so places they list keep zone positions; the continent's own lists then add
-- what no zone lists.
local function visitContinent(s, continentID)
	for _, child in ipairs(children(continentID, ZONE)) do
		if not visit(s, plain(child.mapID)) then return false end
	end
	return visit(s, continentID)
end

-- The player's map and the zones above it, the continent's zones and the continent, then
-- (while nothing matches well) the other continents of the same world.
local function scan(s)
	local chain = Places.Ancestors(playerMap())
	for _, info in ipairs(chain) do
		if info.mapType ~= CONTINENT and not visit(s, info.mapID) then return end
	end
	local top = chain[#chain]
	if not (top and top.mapType == CONTINENT) then return end
	if not visitContinent(s, top.mapID) then return end
	if s.best >= PART or type(top.parentMapID) ~= "number" then return end
	for _, other in ipairs(children(top.parentMapID, CONTINENT)) do
		local otherID = plain(other.mapID)
		if otherID ~= top.mapID and not visitContinent(s, otherID) then return end
	end
end

local function zoneName(mapID)
	local info = mapID and mapInfo(mapID)
	return info and info.name or nil
end
Places.MapName = zoneName

-- A place the player can be sent to: quests through the quest arrow, the rest through a pin.
local function resolve(c)
	local place = { name = c.name, kind = c.kind, quest = c.quest, exact = c.quality >= EXACT }
	if c.map then
		place.map, place.x, place.y = Places.Pinnable(c.map, c.x, c.y)
		if not place.map then
			if not c.quest then return nil end
			place.zone = zoneName(c.map)
		else
			place.zone = zoneName(place.map)
		end
	end
	return place
end

-- Finds `name` (what the player or the model called it) of `kind` (Places.KINDS; anything
-- else counts as "any"). Returns { place = {name, kind, zone, map, x, y, quest, exact} or
-- nil, others = up to 3 {name, kind, zone}, maps = maps read, ms = time taken }. place.map is a
-- map that takes a user waypoint; quests carry place.quest and may have no map.
function Places.Find(name, kind)
	kind = Places.KINDS[kind] and kind or "any"
	local s = newSearch(name, kind)
	local result = { others = {}, maps = 0, ms = 0 }
	if s.q.compact == "" then return result end
	pcall(questLog, s)
	pcall(scan, s)
	result.maps, result.ms = s.maps, now() - s.started
	table.sort(s.found, function(a, b)
		if a.score ~= b.score then return a.score > b.score end
		return a.order < b.order
	end)
	for _, c in ipairs(s.found) do
		if not result.place and c.quality >= MIN_BEST then
			result.place = resolve(c)
		elseif #result.others < 3 then
			result.others[#result.others + 1] = { name = c.name, kind = c.kind, zone = zoneName(c.map) }
		end
	end
	return result
end

-- Names near the player for the request context, so the model knows what goto can find:
-- { delve = {...}, dungeon = {...}, raid = {...}, boss = {...}, poi = {...} } with at most
-- `limit` names in all; the player's own map first, then its continent's lists.
local NEARBY_KINDS = { "delve", "dungeon", "raid", "boss", "poi" }
local NEARBY = { delve = true, dungeon = true, raid = true, boss = true, poi = true }

function Places.Nearby(limit)
	local chain = Places.Ancestors(playerMap())
	local byKind, seen = {}, {}
	local s = { seenPoi = {} }
	function s.add(kind, _, name)
		name = ns.Trim(name, 40)
		if not (NEARBY[kind] and name and name ~= "") or seen[kind .. name] then return end
		seen[kind .. name] = true
		byKind[kind] = byKind[kind] or {}
		table.insert(byKind[kind], name)
	end
	local own, top = chain[1], chain[#chain]
	if own then
		for _, source in ipairs({ entrances, delves, taskQuests, areaPois }) do pcall(source, s, own.mapID) end
	end
	-- one call per source for the whole continent (whatever Blizzard's continent map shows)
	if top and top ~= own and top.mapType == CONTINENT then
		for _, source in ipairs({ entrances, delves, taskQuests }) do pcall(source, s, top.mapID) end
	end
	local out, count = {}, 0
	for _, kind in ipairs(NEARBY_KINDS) do
		for _, name in ipairs(byKind[kind] or {}) do
			if count >= limit then break end
			out[kind] = out[kind] or {}
			table.insert(out[kind], name)
			count = count + 1
		end
	end
	return count > 0 and out or nil
end
