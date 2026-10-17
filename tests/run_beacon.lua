-- The request plate: real Beacon.lua on the mocked WoW API. Each plate is dumped, rendered
-- through gamma, brightness, scaling (and for the classic style JPEG) by beacon_matrix.py and
-- decoded by the real companion code.
-- usage: lua51 run_beacon.lua <addonsDir> <workDir>
local addonsDir, work = arg[1], arg[2]
local M = dofile(work .. "/wowmock.lua")
M.addonsDir = addonsDir
math.randomseed(42)
local ns = M.LoadAddon(addonsDir .. "/Gnomecaster")
local Beacon = ns.Beacon

local function check(cond, label)
	print((cond and "PASS " or "FAIL ") .. label)
	if not cond then
		for _, l in ipairs(M.chat) do print("   | " .. tostring(l)) end
		os.exit(1)
	end
end

local function readDump(path)
	local f = assert(io.open(path))
	local w, h = f:read("*l"):match("^(%d+) (%d+)$")
	local d = { w = tonumber(w), h = tonumber(h), rects = {}, texts = {} }
	for line in f:lines() do
		local kind, rest = line:match("^(%a+) (.*)$")
		local v = {}
		for n in rest:gmatch("%S+") do v[#v + 1] = n end
		if kind == "rect" then
			d.rects[#d.rects + 1] = { x = tonumber(v[1]), y = tonumber(v[2]), w = tonumber(v[3]), h = tonumber(v[4]),
				r = tonumber(v[5]), g = tonumber(v[6]), b = tonumber(v[7]) }
		else
			d.texts[#d.texts + 1] = { x = tonumber(v[1]), y = tonumber(v[2]), text = v[6] }
		end
	end
	f:close()
	return d
end

-- Send one request through the plate; returns the dump and whether every condition decoded.
local shots = 0
local function send(label, how)
	shots = shots + 1
	local json = ns.Json.Encode({ v = ns.PROTOCOL, t = "ping", rid = shots, text = label .. string.rep(" and more words", 40) })
	local dump, expected = work .. "/plate" .. shots .. ".txt", work .. "/plate" .. shots .. ".json"
	local f = assert(io.open(expected, "w")); f:write(json); f:close()
	local decoded, captured
	M.onScreenshot = function()
		M.DumpBeacon(dump)
		decoded = os.execute(string.format('python3 "%s/beacon_matrix.py" "%s" "%s" "%s" %s', work, dump, expected,
			label, how or "")) == 0
		C_Timer.After(0.05, function() M.Fire("SCREENSHOT_SUCCEEDED") end)
	end
	assert(Beacon.Send(json, function(ok) captured = ok end), "beacon busy")
	M.Advance(0.5)
	check(captured == true and not _G.GnomecasterBeacon.shown, label .. ": screenshot taken, plate hidden again")
	return readDump(dump), decoded
end

local function said(pattern)
	for _, l in ipairs(M.chat) do if tostring(l):find(pattern) then return true end end
	return false
end

local GOLD = "0.96 0.7 0.23"
local function colour(r) return string.format("%g %g %g", r.r, r.g, r.b) end
-- Facts about a dump: the plate (first rect), gold lines, cells, all in whole pixels?
local function survey(d)
	local s = { plate = d.rects[1], gold = 0, cells = {}, whole = true, onScreen = true }
	for i, r in ipairs(d.rects) do
		if colour(r) == GOLD then s.gold = s.gold + 1 elseif i > 1 then s.cells[#s.cells + 1] = r end
		for _, v in ipairs({ r.x, r.y, r.w, r.h }) do if v ~= math.floor(v) then s.whole = false end end
		if r.x < 0 or r.y < 0 or r.x + r.w > d.w or r.y + r.h > d.h then s.onScreen = false end
	end
	return s
end
local function levelsAre(cells, a, b)
	for _, c in ipairs(cells) do
		for _, v in ipairs({ c.r, c.g, c.b }) do if v ~= a and v ~= b then return false end end
	end
	return #cells > 0
end
local function inside(cells, x0, y0, x1, y1)
	for _, c in ipairs(cells) do
		if c.x < x0 or c.y < y0 or c.x + c.w > x1 or c.y + c.h > y1 then return false end
	end
	return true
end

-- 1. The default: a dim, framed plate; without a place from the panel it sits in the corner.
check(Beacon.Style() == "dim" and ns.db.beacon == "dim", "the dim plate is the default")
local d, decoded = send("dim_corner")
local s = survey(d)
check(decoded, "the dim plate decodes in the corner")
check(s.plate.x == 0 and s.plate.y == 0 and colour(s.plate) == "0.08 0.08 0.08", "without an anchor the plate's top-left is the screen's")
check(levelsAre(s.cells, 0.08, 0.45), "every cell uses only the dim off and on levels")
check(s.gold == 4 and #d.texts == 1 and d.texts[1].text == "Gnomecaster", "a gold line frames the plate, captioned Gnomecaster")
check(inside(s.cells, s.plate.x + 4, s.plate.y + 4, s.plate.x + s.plate.w - 4, s.plate.y + s.plate.h - 4)
	and d.texts[1].y + 12 <= s.cells[1].y, "the frame and caption stay outside the cells")
check(s.whole and s.onScreen, "every edge on a whole pixel, all on screen")
local cellH = s.cells[1].h
check(cellH == 3, "cells are 3 physical pixels")

-- 2. Beside the panel: UI.BeaconAnchor(w, h) gets the plate's size and returns the frame whose
-- top-left the plate's top-left goes to.
local asked
local anchor = CreateFrame("Frame", nil, UIParent)
local rect = { left = 700.3, top = 600.6, scale = 0.9 }
anchor.GetLeft = function() return rect.left end
anchor.GetTop = function() return rect.top end
anchor.GetEffectiveScale = function() return rect.scale end
ns.UI.BeaconAnchor = function(w, h) asked = { w, h }; return anchor end
d, decoded = send("dim_panel")
s = survey(d)
local k = 0.9 * 1080 / 768
check(asked and asked[1] == s.plate.w and asked[2] == s.plate.h, "BeaconAnchor is asked with the plate's full size in physical pixels")
check(s.plate.x == math.floor(700.3 * k + 0.5) and s.plate.y == 1080 - math.floor(600.6 * k + 0.5),
	"the plate's top-left sits on the anchor's, rounded to a physical pixel")
check(s.whole and decoded, "the plate beside the panel is pixel-snapped and decodes")

rect.left, rect.top = 1500, 60
d, decoded = send("dim_clamped", "--plain")
s = survey(d)
check(s.onScreen and s.plate.x + s.plate.w == 1920 and s.plate.y + s.plate.h == 1080 and decoded,
	"an anchor near the bottom-right edge keeps the whole plate on screen")

-- 3. No usable place: the corner, as before, and never an error.
local function corner(label)
	d = send(label, "--plain")
	return d.rects[1].x == 0 and d.rects[1].y == 0
end
anchor:Hide()
check(corner("dim_hidden_anchor"), "a hidden anchor frame falls back to the corner")
anchor:Show()
rect.left = nil
check(corner("dim_no_position"), "an anchor without a position falls back to the corner")
rect.left = M.SECRET
check(corner("dim_secret_position"), "a secret position falls back to the corner")
anchor.GetLeft = function() error("no rect") end
check(corner("dim_anchor_error"), "an error while placing falls back to the corner")
ns.UI.BeaconAnchor = function() return nil end
check(corner("dim_no_anchor"), "no anchor (panel closed) falls back to the corner")

-- 4. A 4K screen: cells stay 3 physical pixels, the plate still decodes.
local physical = GetPhysicalScreenSize
GetPhysicalScreenSize = function() return 3840, 2160 end
anchor.GetLeft = function() return rect.left end
rect.left, rect.top, rect.scale = 300, 500, 1
ns.UI.BeaconAnchor = function() return anchor end
d, decoded = send("dim_4k")
s = survey(d)
check(d.w == 3840 and s.cells[1].h == 3 and s.plate.x == math.floor(300 * 2160 / 768 + 0.5) and decoded,
	"on a 3840x2160 screen the plate keeps 3 pixel cells, sits by the anchor and decodes")
GetPhysicalScreenSize = physical

-- 5. /gc beacon switches styles and remembers the choice.
M.chat = {}
SlashCmdList.GNOMECASTER("help")
check(said("/gc beacon dim|classic"), "/gc help lists /gc beacon")
M.chat = {}
SlashCmdList.GNOMECASTER("beacon")
check(said("beacon style: dim"), "/gc beacon names the style in use")
SlashCmdList.GNOMECASTER("beacon classic")
check(GnomecasterDB.beacon == "classic" and Beacon.Style() == "classic", "/gc beacon classic is saved for the next session")
rect.left = 700
d, decoded = send("classic", "--jpeg")
s = survey(d)
check(s.plate.x == 0 and s.plate.y == 0 and colour(s.plate) == "0 0 0" and s.gold == 0 and #d.texts == 0,
	"the classic plate is the proven look: black, unframed, in the corner even with a panel")
check(levelsAre(s.cells, 0, 1), "classic cells are full intensity")
check(decoded, "the classic plate decodes, JPEG included")

local sent
local send0 = ns.Request.Send
ns.Request.Send = function(kind, text) sent = { kind, text } end
SlashCmdList.GNOMECASTER("beacon of light macro")
ns.Request.Send = send0
check(sent and sent[1] == "ask" and sent[2] == "beacon of light macro" and Beacon.Style() == "classic",
	"a question that starts with 'beacon' is still a question")
SlashCmdList.GNOMECASTER("beacon dim")
check(Beacon.Style() == "dim", "/gc beacon dim switches back")
ns.db.beacon = "neon"
check(Beacon.Style() == "dim", "an unknown saved style draws the dim plate")

print("beacon tests done")
