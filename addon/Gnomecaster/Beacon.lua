-- Outbound channel: addons cannot reach the network or write files while
-- playing, but they can take a screenshot. We draw the request as a grid of
-- coloured cells in the top-left corner for two frames, call Screenshot(),
-- and the companion app decodes the picture the game writes to disk.
--
-- Layout (protocol v1):
--   row 0      : marker M M C C Y Y M M (magenta, cyan, yellow) at both ends,
--                black between; the distance between them gives the cell size
--   rows 1..n  : data, 3 bits per cell (red, green, blue each on/off),
--                GRID_W cells per row, most significant bit first
--   data bytes : "GC", version, length (2 bytes), adler32 (4 bytes), json
local _, ns = ...

local Beacon = {}
ns.Beacon = Beacon

local GRID_W = 96         -- cells per row
local CELL = 3            -- physical pixels per cell
local MAX_BYTES = 2400    -- payload limit (about 72 rows)
Beacon.MAX_BYTES = MAX_BYTES

local floor, char, byte = math.floor, string.char, string.byte

local MARKER = { 5, 5, 3, 3, 6, 6, 5, 5 }  -- colour indices: r*4 + g*2 + b
local ROW0 = {}
for i = 1, GRID_W do ROW0[i] = 0 end
for i = 1, #MARKER do
	ROW0[i] = MARKER[i]
	ROW0[GRID_W - #MARKER + i] = MARKER[i]
end

local frame, background
local pool, used = {}, 0
local busy = false
local restoreFormat

local function adler32(s)
	local a, b = 1, 0
	for i = 1, #s do
		a = (a + byte(s, i)) % 65521
		b = (b + a) % 65521
	end
	return b * 65536 + a
end
Beacon.adler32 = adler32

local function u32(n)
	return char(floor(n / 16777216) % 256, floor(n / 65536) % 256, floor(n / 256) % 256, n % 256)
end

function Beacon.Pack(json)
	local len = #json
	return "GC" .. char(ns.PROTOCOL, floor(len / 256), len % 256) .. u32(adler32(json)) .. json
end

-- bytes -> list of colour indices (0..7)
function Beacon.ToCells(data)
	local cells, acc, nbits = {}, 0, 0
	for i = 1, #data do
		local v = byte(data, i)
		for bit = 7, 0, -1 do
			acc = acc * 2 + floor(v / 2 ^ bit) % 2
			nbits = nbits + 1
			if nbits == 3 then
				cells[#cells + 1] = acc
				acc, nbits = 0, 0
			end
		end
	end
	if nbits > 0 then
		while nbits < 3 do acc = acc * 2; nbits = nbits + 1 end
		cells[#cells + 1] = acc
	end
	return cells
end

local function ensureFrame()
	if frame then return end
	frame = CreateFrame("Frame", "GnomecasterBeacon", UIParent)
	frame:SetFrameStrata("TOOLTIP")
	frame:SetIgnoreParentScale(true)
	frame:Hide()
	background = frame:CreateTexture(nil, "BACKGROUND")
	background:SetAllPoints(frame)
	background:SetColorTexture(0, 0, 0, 1)
	-- if these events don't exist on some client, fall back to a short wait
	Beacon.hasEvents = pcall(frame.RegisterEvent, frame, "SCREENSHOT_SUCCEEDED")
	pcall(frame.RegisterEvent, frame, "SCREENSHOT_FAILED")
	frame:SetScript("OnEvent", function(_, event)
		if busy then Beacon.Finish(event == "SCREENSHOT_SUCCEEDED") end
	end)
end

local function getTexture()
	used = used + 1
	local tex = pool[used]
	if not tex then
		tex = frame:CreateTexture(nil, "ARTWORK")
		pool[used] = tex
	end
	tex:Show()
	return tex
end

local function drawRun(col, row, length, colour)
	local tex = getTexture()
	tex:ClearAllPoints()
	tex:SetPoint("TOPLEFT", frame, "TOPLEFT", col * CELL, -row * CELL)
	tex:SetSize(length * CELL, CELL)
	tex:SetColorTexture(floor(colour / 4) % 2, floor(colour / 2) % 2, colour % 2, 1)
end

-- Draw one row of cells, merging neighbours of the same colour into one texture.
local function drawRow(row, cells, first, last)
	local runStart, runColour = first, cells[first]
	for i = first + 1, last + 1 do
		local c = cells[i]
		if i > last or c ~= runColour then
			if runColour ~= 0 then  -- black is the background already
				drawRun(runStart - first, row, i - runStart, runColour)
			end
			runStart, runColour = i, c
		end
	end
end

function Beacon.Render(data)
	ensureFrame()
	for i = 1, used do pool[i]:Hide() end
	used = 0
	local cells = Beacon.ToCells(data)
	local rows = math.ceil(#cells / GRID_W)
	-- 1 UI unit = 1 physical pixel
	local _, physicalHeight = GetPhysicalScreenSize()
	frame:SetScale(768 / physicalHeight)
	frame:ClearAllPoints()
	frame:SetPoint("TOPLEFT", UIParent, "TOPLEFT", 0, 0)
	frame:SetSize(GRID_W * CELL, (rows + 1) * CELL)
	drawRow(0, ROW0, 1, GRID_W)
	for r = 1, rows do
		local first = (r - 1) * GRID_W + 1
		drawRow(r, cells, first, math.min(first + GRID_W - 1, #cells))
	end
	return rows
end

function Beacon.IsBusy()
	return busy
end

-- Draw `data`, wait two frames so it is on screen, take the screenshot.
function Beacon.Send(json, onDone)
	if busy then return false, "busy" end
	if #json > MAX_BYTES then return false, "request too large" end
	busy = true
	Beacon.onDone = onDone
	Beacon.Render(Beacon.Pack(json))
	-- PNG is lossless; JPEG can blur the cells.
	local format = ns.GetCVar("screenshotFormat")
	if format ~= "png" and format ~= "tga" then
		restoreFormat = format
		ns.SetCVar("screenshotFormat", "png")
	end
	frame:Show()
	local frames = 0
	frame:SetScript("OnUpdate", function(self)
		frames = frames + 1
		if frames == 2 then
			self:SetScript("OnUpdate", nil)
			Screenshot()
			if not Beacon.hasEvents then
				local token = Beacon.token
				C_Timer.After(0.6, function()
					if busy and Beacon.token == token then Beacon.Finish(true) end
				end)
			end
		end
	end)
	Beacon.token = (Beacon.token or 0) + 1
	local token = Beacon.token
	C_Timer.After(3, function()
		if busy and Beacon.token == token then Beacon.Finish(false) end
	end)
	return true
end

function Beacon.Finish(ok)
	busy = false
	frame:SetScript("OnUpdate", nil)
	frame:Hide()
	if restoreFormat then
		ns.SetCVar("screenshotFormat", restoreFormat)
		restoreFormat = nil
	end
	-- hide the "Screen captured" banner for our own screenshots
	if ActionStatus and ActionStatus.Hide then pcall(ActionStatus.Hide, ActionStatus) end
	local cb = Beacon.onDone
	Beacon.onDone = nil
	if cb then cb(ok) end
end
