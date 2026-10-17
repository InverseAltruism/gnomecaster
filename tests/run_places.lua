-- Scenarios for places, goto, action results and the conversation key (run by run_tests.lua).
--   places        Places.Find and the goto action on the mock world (wowmock_places.lua)
--   conversation  what the next request carries: `last`, `conv`, the quest log, its size
return function(t)
	local M, ns, check, has, ask, work = t.M, t.ns, t.check, t.has, t.ask, t.work

	local function said(pattern)
		for _, l in ipairs(M.chat) do if tostring(l):find(pattern) then return l end end
		return nil
	end
	local function count(name)
		local n = 0
		for _, c in ipairs(M.calls) do if c.name == name then n = n + 1 end end
		return n
	end
	local function near(a, b) return type(a) == "number" and math.abs(a - b) < 1e-3 end
	local function handle(list)
		M.chat, M.calls = {}, {}
		ns.Actions.Handle(list, { hasTarget = false })
	end
	local function pinAt(map, x, y)
		local wp = has("SetUserWaypoint", map)
		return wp ~= nil and near(wp.args[2], x) and near(wp.args[3], y)
	end

	-- A small JSON reader for the packets the companion decoded (python's json.dumps output).
	local function decodeJson(s)
		local i = 1
		local value
		local function ws() i = s:find("[^ \t\r\n]", i) or #s + 1 end
		local function utf8(cp)
			if cp < 0x80 then return string.char(cp) end
			if cp < 0x800 then return string.char(0xC0 + math.floor(cp / 64), 0x80 + cp % 64) end
			return string.char(0xE0 + math.floor(cp / 4096), 0x80 + math.floor(cp / 64) % 64, 0x80 + cp % 64)
		end
		local function str()
			local out = {}
			i = i + 1
			while true do
				local c = s:sub(i, i)
				if c == '"' then i = i + 1; return table.concat(out) end
				if c == "\\" then
					local e = s:sub(i + 1, i + 1)
					if e == "u" then
						out[#out + 1] = utf8(tonumber(s:sub(i + 2, i + 5), 16)); i = i + 6
					else
						out[#out + 1] = ({ n = "\n", t = "\t", r = "\r", b = "\b", f = "\f" })[e] or e; i = i + 2
					end
				else
					out[#out + 1] = c; i = i + 1
				end
			end
		end
		value = function()
			ws()
			local c = s:sub(i, i)
			if c == "{" then
				local obj = {}
				i = i + 1; ws()
				if s:sub(i, i) == "}" then i = i + 1; return obj end
				while true do
					ws(); local k = str(); ws(); i = i + 1
					obj[k] = value(); ws()
					local d = s:sub(i, i); i = i + 1
					if d == "}" then return obj end
				end
			elseif c == "[" then
				local arr = {}
				i = i + 1; ws()
				if s:sub(i, i) == "]" then i = i + 1; return arr end
				while true do
					arr[#arr + 1] = value(); ws()
					local d = s:sub(i, i); i = i + 1
					if d == "]" then return arr end
				end
			elseif c == '"' then return str()
			elseif s:sub(i, i + 3) == "true" then i = i + 4; return true
			elseif s:sub(i, i + 4) == "false" then i = i + 5; return false
			elseif s:sub(i, i + 3) == "null" then i = i + 4; return nil
			end
			local num = s:match("^-?[%d%.eE+-]+", i)
			i = i + #num
			return tonumber(num)
		end
		return value()
	end

	-- the newest request the companion decoded in this scenario
	local function lastPacket()
		local found
		for n = 1, 200 do
			local f = io.open(work .. "/WoWScrnShot_" .. t.scenario .. n .. ".png.json")
			if not f then break end
			found = f:read("*a")
			f:close()
		end
		return found and decodeJson(found)
	end

	if t.scenario == "places" then
		M.onScreenshot = nil
		M.playerMap = 2393            -- Silbermond
		local P = ns.Places

		check(P.Normalize("Atal'Aman").compact == P.Normalize("atal aman").compact
			and P.Normalize("Große Schatzkammer").compact == "grosseschatzkammer"
			and P.Normalize("Die Steingewölbe").compact == P.Normalize("die steingewolbe").compact,
			"names compare without case, accents, apostrophes or spaces")
		check(P.Match("Atal'Aman", "Atal'Aman") > P.Match("Atal", "Atal'Aman")
			and P.Match("Atal", "Atal'Aman") > P.Match("Aman", "Atal'Aman")
			and P.Match("Aman", "Atal'Aman") > P.Match("Atel Amann", "Atal'Aman")
			and P.Match("Atel Amann", "Atal'Aman") > 0 and P.Match("Zangarmarsch", "Atal'Aman") == 0,
			"exact beats prefix beats a word match beats a typo; unrelated names do not match")

		-- the owner's requests from the first in-game test
		handle({ { type = "goto", name = "atal aman", kind = "delve" } })
		check(pinAt(2437, 0.432, 0.610) and has("SetSuperTrackedUserWaypoint", true),
			"goto finds the delve Atal'Aman from \"atal aman\" and pins it in Zul'Aman")
		check(said("Map pin: Atal'Aman %(delve%) in Zul'Aman at 43%.2, 61%.0"), "the panel says what was found, in which zone and where")
		check(not said("Other matches"), "an exact match lists no other matches")

		handle({ { type = "goto", name = "Terrasse der Magier", kind = "dungeon" } })
		check(pinAt(2424, 0.61, 0.31), "goto finds the dungeon \"Terrasse der Magister\" from \"Terrasse der Magier\"")
		check(said("Terrasse der Magister %(dungeon%) in Insel von Quel'Danas"), "the dungeon's zone is named")
		-- the player said "quest", and models pass that on (openai/gpt-6-luna did, 2026-10-17)
		handle({ { type = "goto", name = "Terrasse der Magier", kind = "quest" } })
		check(pinAt(2424, 0.61, 0.31), "a wrong kind still finds the dungeon by its name")

		handle({ { type = "goto", name = "Sonnenbrunnen", kind = "raid" } })
		check(pinAt(2424, 0.6, 0.3), "a raid listed only on the continent is moved onto the zone under it")

		handle({ { type = "goto", name = "atal aman delve" } })
		check(pinAt(2437, 0.432, 0.610), "extra words around the name still find it")

		handle({ { type = "goto", name = "steingewolbe", kind = "dungeon" } })
		check(pinAt(2214, 0.45, 0.30) and said("in Die Klingenden Tiefen"), "a dungeon on another continent is found when nothing here matches")

		handle({ { type = "goto", name = "Aufwertung", kind = "poi" } })
		check(pinAt(2393, 0.48, 0.62) and said("Gegenstandsaufwertung"), "a city service pin is found by part of its name")

		handle({ { type = "goto", name = "Zul'Aman", kind = "zone" } })
		check(pinAt(2437, 0.5, 0.5) and said("%(zone%)"), "the asked-for kind decides between a zone and a dungeon of the same name")
		handle({ { type = "goto", name = "Zul'Aman", kind = "dungeon" } })
		check(pinAt(2437, 0.30, 0.55) and said("%(dungeon%)"), "...and the dungeon when that is asked for")

		handle({ { type = "goto", name = "Silbermond", kind = "flight" } })
		check(pinAt(2393, 0.52, 0.44) and said("%(flight%)"), "a flight point outranks the zone of the same name when flight is asked for")
		handle({ { type = "goto", name = "Faltruuns Rast", kind = "flight" } })
		check(not has("SetUserWaypoint"), "another faction's flight point is not offered, as on Blizzard's map")

		local result = P.Find("Atal'Aman", "any")
		local poiTwice = false
		for _, o in ipairs(result.others) do if o.name == "Atal'Aman" and o.kind == "poi" then poiTwice = true end end
		check(result.place and result.place.kind == "delve" and not poiTwice, "a delve also listed as an area POI counts once")
		check(result.maps == 5, "a good match on this continent reads its five maps and stops (" .. result.maps .. " maps)")

		-- not found: close matches, or a plain answer
		handle({ { type = "goto", name = "Zul Gurub" } })
		check(not has("SetUserWaypoint") and said("Couldn't do") and said("close matches: Zul'Aman"),
			"an unknown name sets nothing and lists close matches")
		handle({ { type = "goto", name = "Xyzzy" } })
		check(not has("SetUserWaypoint") and said("couldn't find it near you"), "a name like nothing says so")

		-- quests: the quest arrow, not a pin
		handle({ { type = "goto", quest = 91001 } })
		check(has("SetSuperTrackedQuestID", 91001) and not has("SetUserWaypoint"), "goto with a quest in the log super-tracks it")
		check(said("Following quest: The Sunwell's Echo in Immersangwald at 38%.1, 55%.2"), "and names the quest and where it leads")
		handle({ { type = "goto", quest = 92001 } })
		check(has("SetSuperTrackedQuestID", 92001), "a world quest that is up is super-tracked too")
		-- GetQuestLocation may return nothing (MayReturnNothing in Blizzard's docs)
		local location, nextStep = C_TaskQuest.GetQuestLocation, C_QuestLog.GetNextWaypoint
		C_TaskQuest.GetQuestLocation, C_QuestLog.GetNextWaypoint = function() end, function() end
		local ok, err = pcall(handle, { { type = "goto", quest = 92001 }, { type = "waypoint", map = 2393, x = 0.5, y = 0.5 } })
		check(ok, "a world quest without a position raises no error (" .. tostring(err) .. ")")
		check(has("SetSuperTrackedQuestID", 92001) and has("SetUserWaypoint", 2393),
			"it is followed, and the reply's other actions still run")
		check(ns.Places.Pinnable(2424, nil, nil) == nil and ns.Places.Pinnable(2393, nil, 0.5) == nil,
			"no map comes back without coordinates")
		C_TaskQuest.GetQuestLocation, C_QuestLog.GetNextWaypoint = location, nextStep
		handle({ { type = "goto", quest = 99999 } })
		check(not has("SetSuperTrackedQuestID") and said("neither in your quest log"), "an unknown quest ID says so")
		handle({ { type = "goto", quest = 99999, name = "Sunwell's Echo", kind = "quest" } })
		check(has("SetSuperTrackedQuestID", 91001), "an unknown quest ID falls back to the name, found in the quest log")
		handle({ { type = "goto", name = "Kul'thar", kind = "boss" } })
		check(has("SetSuperTrackedQuestID", 92001) and said("Following boss: Kul'thar der Zornige"), "a world boss is found by name")
		handle({ { type = "goto", name = "Ruinenhüter", kind = "boss" } })
		check(said("Following boss: Ruinenhüter"), "an elite epic world quest counts as a world boss, as in Blizzard's QuestUtils")

		-- validation
		handle({ { type = "goto", name = string.rep("a", 81) } })
		check(said("skipped goto: needs a place name or a quest ID") and not has("SetUserWaypoint"), "an over-long name is refused")
		handle({ { type = "goto", name = "Atal'Aman", kind = "Teleporter" } })
		check(pinAt(2437, 0.432, 0.610), "an unknown kind counts as any")
		handle({ { type = "goto", name = "Zul'Aman", kind = "ZONE" } })
		check(pinAt(2437, 0.5, 0.5), "kinds are read in any case")

		-- TomTom present, absent, broken
		check(_G.TomTom == nil, "no TomTom in the mock so far")
		handle({ { type = "goto", name = "Atal'Aman", kind = "delve" } })
		check(not said("TomTom"), "without TomTom only Blizzard's pin is set")
		_G.TomTom = { AddWaypoint = function(self, map, x, y, opts)
			M.record("TomTom", map, x, y, opts.title, opts.from)
			return { map, x, y }
		end }
		handle({ { type = "goto", name = "Atal'Aman", kind = "delve" } })
		local tt = has("TomTom", 2437)
		check(tt and near(tt.args[2], 0.432) and near(tt.args[3], 0.610) and tt.args[4] == "Atal'Aman" and pinAt(2437, 0.432, 0.610),
			"with TomTom loaded both TomTom and Blizzard get the waypoint")
		check(said("also in TomTom"), "the panel says TomTom has it too")
		handle({ { type = "goto", quest = 91001 } })
		check(has("TomTom", 2395) and has("SetSuperTrackedQuestID", 91001), "a followed quest's next step goes to TomTom too")
		_G.TomTom.AddWaypoint = function() error("TomTom broke") end
		handle({ { type = "goto", name = "Atal'Aman", kind = "delve" } })
		check(pinAt(2437, 0.432, 0.610) and not said("Couldn't do") and not said("TomTom"), "a failing TomTom leaves Blizzard's pin and the action intact")
		handle({ { type = "waypoint", map = 2395, x = 0.4, y = 0.5 } })
		check(has("SetUserWaypoint", 2395) and not said("Couldn't do"), "plain waypoints survive a failing TomTom as well")
		_G.TomTom = nil

		-- the search is bounded
		local before = M.mapReads
		M.msPerCall = 20
		result = P.Find("Xyzzy", "any")
		M.msPerCall = 0
		check(result.maps <= 2 and M.mapReads - before <= 2, "a slow client stops the search after the time budget (" .. result.maps .. " maps)")
		for id = 50001, 50300 do M.maps[id] = { name = "Leere " .. id, mapType = 3, parent = 2274 } end
		result = P.Find("Xyzzy", "any")
		check(result.maps == P.MAX_MAPS, "a huge world stops the search at " .. P.MAX_MAPS .. " maps (" .. result.maps .. ")")
		for id = 50001, 50300 do M.maps[id] = nil end
		local clock = os.clock()
		result = P.Find("Xyzzy", "any")
		print(string.format("     a search of every mock map took %.1f ms of CPU here (plain Lua 5.1, not the game)", (os.clock() - clock) * 1000))
		check(result.maps > 6 and result.maps < P.MAX_MAPS, "a normal world is searched to the end (" .. result.maps .. " maps)")

		-- a source that fails on some game flavor removes only itself
		local entrances = C_EncounterJournal.GetDungeonEntrancesForMap
		C_EncounterJournal.GetDungeonEntrancesForMap = function() error("not on this flavor") end
		result = P.Find("atal aman", "delve")
		local ctx = ns.Context.Collect(1)
		C_EncounterJournal.GetDungeonEntrancesForMap = entrances
		check(result.place and result.place.name == "Atal'Aman" and ctx.places and ctx.places.delve and ctx.quests,
			"a failing API leaves the other sources, the context and the quest log working")

		-- what the request tells the model about the surroundings
		ctx = ns.Context.Collect(1)
		check(ctx.location.within and ctx.location.within[1] == "Immersangwald" and ctx.location.within[2] == "Quel'Thalas",
			"the request names the zone and continent around the player")
		local places = ctx.places or {}
		local function listed(kind, name)
			for _, n in ipairs(places[kind] or {}) do if n == name then return true end end
		end
		check(listed("delve", "Atal'Aman") and listed("dungeon", "Terrasse der Magister") and listed("raid", "Sonnenbrunnenplateau")
			and listed("boss", "Kul'thar der Zornige") and listed("poi", "Gegenstandsaufwertung"),
			"the request lists delves, dungeons, raids, world bosses and the city's pins near the player")
		local total = 0
		for _, list in pairs(ns.Context.Collect(4).places or {}) do total = total + #list end
		check(total == 5, "less detail lists fewer places (" .. total .. ")")
		check(ns.Context.Collect(5).places == nil, "and then none")
	end

	if t.scenario == "conversation" then
		local function lastBy(packet, typ, pattern)
			for _, e in ipairs(packet.last or {}) do
				if e.type == typ and (not pattern or tostring(e.say):find(pattern)) then return e end
			end
		end

		-- results of one answer's actions, in the next question
		local confirm
		ns.UI.ShowConfirm = function(text) confirm = text end
		local longName = "A|B " .. string.rep("lang", 18)
		ns.Actions.Handle({
			{ type = "goto", name = "atal aman", kind = "delve" },
			{ type = "goto", name = longName },
			{ type = "macro", name = "Heal", body = "#showtooltip\n/cast Rejuvenation" },
			{ type = "bind", key = "SHIFT-E", macro = "Heal" },
			{ type = "teleport", where = "home" },
			{ type = "mark", icon = 99 },
		}, { hasTarget = false })
		ask("where am i")
		local p = lastPacket()
		check(p and p.t == "ask", "the companion decoded the question")
		local found, missing = lastBy(p, "goto", "Atal'Aman"), lastBy(p, "goto", "^Go to \"A|B lang")
		check(found and found.ok == true and found.say:find("Zul'Aman"), "a goto that worked is reported ok, with what it found")
		check(missing and missing.ok == false, "a goto that found nothing is reported failed, in plain text")
		check(missing and #missing.say == 120 and missing.say:sub(-3) == "...", "a long result is cut to 120 bytes")
		local waiting = lastBy(p, "macro")
		check(waiting and waiting.ok == false and waiting.say:find("waiting for the player to click Apply"), "a change waiting for Apply is reported as such")
		local bind = lastBy(p, "bind", "replaces MOVEANDSTEER")
		check(bind and not bind.say:find("|c", 1, true) and not bind.say:find("|r", 1, true), "results carry no colour codes")
		check(lastBy(p, "teleport", "^skipped") and lastBy(p, "mark", "^skipped"), "skipped actions are reported with the reason")
		local short = true
		for _, e in ipairs(p.last or {}) do if #e.say > 120 then short = false end end
		check(#(p.last or {}) == 6 and short, "six results, 120 bytes each at most")

		ask("where am i")
		check(lastPacket().last == nil, "results are sent once")
		ns.Actions.Apply()
		ask("where am i")
		local applied = lastBy(lastPacket(), "macro")
		check(applied and applied.ok == true and applied.say:find("^applied: Create macro \"Heal\""), "after Apply the next question says it was applied")

		ns.Actions.Handle({ { type = "setting", name = "autoLootDefault", value = "1" } }, { hasTarget = false })
		ns.Actions.Cancel()
		ask("where am i")
		local declined = lastBy(lastPacket(), "setting")
		check(declined and declined.ok == false and declined.say:find("^declined by the player"), "a cancelled change is reported declined")

		ns.Actions.Handle({ { type = "setting", name = "autoLootDefault", value = "1" } }, { hasTarget = false })
		ns.Actions.Handle({ { type = "setting", name = "chatBubbles", value = "0" } }, { hasTarget = false })
		local dropped = false
		for _, e in ipairs(ns.lastResults) do if e.say:find("^dropped, a newer answer replaced it: Set autoLootDefault") then dropped = true end end
		check(dropped, "a change replaced by a newer answer before Apply is reported dropped")
		ns.Actions.Cancel()

		local many = {}
		for i = 1, 9 do many[i] = { type = "mark", icon = 90 + i } end
		ns.Actions.Handle(many, { hasTarget = false })
		check(#ns.lastResults == 6, "at most six results are kept")
		ns.Actions.ClearResults()

		-- the reload warning comes early enough for the next wait: timed polls spend a slot each
		ns.Inbox.probeState = "unknown"
		check(ns.Inbox.LowMark() == 6, "without a working ready signal the warning comes at 6 slots left")
		ns.Inbox.probeState = "works"
		check(ns.Inbox.LowMark() == 3, "with it, at 3")
		local remaining, lowMark = ns.Inbox.Remaining, ns.Inbox.LowMark
		ns.Inbox.Remaining, ns.Inbox.LowMark = function() return 5 end, function() return 6 end
		M.chat = {}
		ask("where am i")
		check(said("almost used up"), "an answer with fewer slots left than the next wait may need warns")
		ns.Inbox.Remaining, ns.Inbox.LowMark = remaining, lowMark

		-- the conversation key
		ask("where am i")
		local conv = lastPacket().conv
		check(type(conv) == "string" and #conv >= 8 and #conv <= 16 and conv == ns.Request.Conversation(), "the question carries a conversation key (" .. tostring(conv) .. ")")
		ask("where am i")
		check(lastPacket().conv == conv, "the key stays the same for the next question")

		-- /reload: saved variables come back from disk as a new table
		local function copy(v)
			if type(v) ~= "table" then return v end
			local out = {}
			for k, x in pairs(v) do out[k] = copy(x) end
			return out
		end
		GnomecasterDB = copy(GnomecasterDB)
		ns = M.LoadAddon(work .. "/AddOns/Gnomecaster")
		check(ns.Request.Conversation() == conv, "the key survives a reload")
		-- the saved variables are account-wide; another character must not continue this talk
		M.playerGuid = "Player-1-00000002"
		check(ns.Request.Conversation() ~= conv, "another character has its own conversation")
		M.playerGuid = "Player-1-00000001"
		check(ns.Request.Conversation() == conv, "and switching back resumes this one")
		ask("where am i")
		check(lastPacket().conv == conv, "and the first question after the reload carries it")

		M.chat = {}
		ns.Actions.Handle({ { type = "mark", icon = 99 } }, { hasTarget = false })
		SlashCmdList.GNOMECASTER("new")
		check(ns.Request.Conversation() ~= conv and #ns.Request.Conversation() <= 16, "/gc new makes a new key")
		check(said("New conversation"), "and says so in the panel")
		ask("where am i")
		p = lastPacket()
		check(p.conv == ns.Request.Conversation(), "the next question carries the new key")
		check(p.last == nil, "and nothing from the conversation before")
		M.chat = {}
		SlashCmdList.GNOMECASTER("help")
		check(said("/gc new"), "/gc help lists /gc new")

		-- a quest log in German, as on the owner's client: quest headers every seven quests
		local titles = {
			"Die Rückkehr des Sonnenkönigs", "Schatten über Silbermond", "Ein Funke Hoffnung", "Die Verlorenen von Zul'Aman",
			"Unruhe im Immersangwald", "Botschaft für die Magister", "Das Erbe der Hochgeborenen", "Wächter des Sonnenbrunnens",
			"Fragmente der Leere", "Eine Klinge für Quel'Danas", "Der Fall von Atal'Aman", "Kräuter für die Heilerin",
			"Verschollene Späher", "Die Amani erheben sich", "Splitter des Zorns", "Die Prüfung des Waldläufers",
			"Ein Bündnis aus Not", "Gefangene der Trolle", "Das Lied der Phönixe", "Echo der Verlassenen",
			"Rückeroberung der Brücke", "Der letzte Wachposten", "Arkane Störungen", "Geschenke für Lor'themar",
			"Ruf der Weltenwanderer",
		}
		for i = 26, 40 do titles[i] = "Zusätzliche Aufgabe Nummer " .. i end
		local headers = { "Immersangwald", "Zul'Aman", "Insel von Quel'Danas", "Kampagne", "Silbermond", "Weltquests" }
		local log = {}
		local function fill(n)
			log = {}
			for i = 1, n do
				if i % 7 == 1 then log[#log + 1] = { isHeader = true, title = headers[(i - 1) / 7 + 1] } end
				log[#log + 1] = { questID = 93000 + i, title = titles[i], level = i <= 25 and 90 or 88 }
				M.questDistance[93000 + i] = i * 1000
			end
		end
		local real = { C_QuestLog.GetNumQuestLogEntries, C_QuestLog.GetInfo, C_QuestLog.GetQuestObjectives }
		C_QuestLog.GetNumQuestLogEntries = function() return #log end
		C_QuestLog.GetInfo = function(i) return log[i] end
		C_QuestLog.GetQuestObjectives = function(id)
			return { { text = "0/8 Amani-Speerwerfer besiegt" }, { text = "Sprecht mit Waldläuferin Lyanis" } }
		end
		M.focusQuest = 91001
		M.playerMap = 2393
		M.RaiseError("Interface/AddOns/WeakAuras/WeakAuras.lua:2471: attempt to index field 'region' (a nil value)")

		local QUESTION = "Zeige mir eine Route zur Quest Terrasse der Magier"
		local function measure(n, question)
			fill(n)
			local sizes = {}
			for level in ipairs(ns.Context.LEVELS) do sizes[level] = #ns.Json.Encode(ns.Context.Collect(level)) end
			local json, level = ns.Request.BuildPacket("ask", question)
			print(string.format("     %d quests, %d-byte question: ctx bytes by level %s; packet %d bytes at level %d (limit %d)",
				n, #question, table.concat(sizes, ", "), json and #json or -1, level or -1, ns.Beacon.MAX_BYTES))
			return json, level
		end

		local json, level = measure(10, QUESTION)
		check(json and level == 1, "ten quests fit with every detail")
		ask(QUESTION)
		local quests = lastPacket().ctx.quests or {}
		check(#quests == 10 and quests[1].zone == "Immersangwald" and quests[8].zone == "Zul'Aman", "each quest names its zone header")
		check(quests[1].level == nil, "a quest at the player's level leaves its level out")
		local withObj = 0
		for _, q in ipairs(quests) do if q.obj then withObj = withObj + 1 end end
		check(withObj == 3 and quests[1].obj and quests[2].obj and quests[3].obj, "objectives only for the three nearest quests")

		json, level = measure(25, QUESTION)
		check(json and #json <= ns.Beacon.MAX_BYTES, "25 quests with German titles still fit the screenshot channel")
		ask(QUESTION)
		p = lastPacket()
		quests = p.ctx.quests or {}
		check(#quests == 25 and quests[1].title == "Die Rückkehr des Sonnenkönigs" and quests[24].title == "Geschenke für Lor'themar",
			"all 25 quests arrive, German titles intact")
		check(p.ctx.places and p.ctx.places.delve, "and the places near the player still come along")

		json, level = measure(40, string.rep("Wo finde ich das? ", 12))
		check(json and #json <= ns.Beacon.MAX_BYTES, "40 quests and a long question still fit, at less detail")
		fill(40)
		local packet = ns.Context.Collect(3)        -- the level that keeps all 40
		check(packet.quests and packet.quests[26].level == 88, "a quest of another level keeps its level")
		C_QuestLog.GetNumQuestLogEntries, C_QuestLog.GetInfo, C_QuestLog.GetQuestObjectives = real[1], real[2], real[3]
	end
end
