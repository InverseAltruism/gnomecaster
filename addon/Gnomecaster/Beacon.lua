-- Outbound channel: addons cannot reach the network or write files while
-- playing, but they can take a screenshot. We draw the request as a plate of
-- coloured cells for two frames, call Screenshot(), and the companion app
-- decodes the picture the game writes to disk.
--
-- Layout (protocol v1):
--   row 0      : marker M M C C Y Y M M (magenta, cyan, yellow) at both ends,
--                off cells between; the distance between them gives the cell size
--   rows 1..n  : data, 3 bits per cell (red, green, blue each on/off),
--                GRID_W cells per row, most significant bit first
--   data bytes : "GC", version, length (2 bytes), adler32 (4 bytes), json
--
-- Styles (/gc beacon): "dim" draws every channel at two muted levels on a framed,
-- captioned plate next to the panel; "classic" is the first look proven in the
-- game: full intensity on black in the top-left corner. The companion measures
-- the off and on levels from the marker, so it reads either.
local _, ns = ...

local Beacon = {}
ns.Beacon = Beacon

local MAGIC = "GC"        -- first two bytes of every packet
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

-- Channel levels for off and on. The dim levels keep the plate a dark panel; the companion
-- needs on and off apart by its margin (protocol.MARGIN) after the game's gamma and brightness.
local STYLES = {
	dim = { off = 0.08, on = 0.45, framed = true },
	classic = { off = 0, on = 1 },
}
local DEFAULT_STYLE = "dim"
-- The frame of a dim plate, in physical pixels. It lies outside the cells and is drawn in
-- the brand gold and the off level only: in both, blue is the lowest channel or no channel
-- is, so the companion cannot read any of it as magenta or cyan marker cells.
local BORDER = 1          -- gold line around the plate
local PAD = 3             -- off-level margin between the line and the cells
local GOLD = { 0.96, 0.70, 0.23 }

local frame, background, caption
local edges = {}
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

local function u32(n)
	return char(floor(n / 16777216) % 256, floor(n / 65536) % 256, floor(n / 256) % 256, n % 256)
end

function Beacon.Pack(json)
	local len = #json
	return MAGIC .. char(ns.PROTOCOL, floor(len / 256), len % 256) .. u32(adler32(json)) .. json
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

function Beacon.Style()
	local name = ns.db and ns.db.beacon
	return STYLES[name] and name or DEFAULT_STYLE
end

-- /gc beacon [dim|classic]: "" shows the style in use.
function Beacon.Command(arg)
	if STYLES[arg] then ns.db.beacon = arg end
	ns.Print("beacon style: " .. Beacon.Style() .. (Beacon.Style() == "classic"
		and " (bright square in the top-left corner)" or " (dim plate next to the panel)"))
end

local function ensureFrame()
	if frame then return end
	frame = CreateFrame("Frame", "GnomecasterBeacon", UIParent)
	frame:SetFrameStrata("TOOLTIP")
	frame:SetIgnoreParentScale(true)
	frame:Hide()
	background = frame:CreateTexture(nil, "BACKGROUND")
	for i = 1, 4 do
		edges[i] = frame:CreateTexture(nil, "BORDER")
		edges[i]:SetColorTexture(GOLD[1], GOLD[2], GOLD[3], 1)
	end
	caption = frame:CreateFontString(nil, "OVERLAY", "GameFontNormal")
	caption:SetText("Gnomecaster")
	caption:SetTextColor(GOLD[1], GOLD[2], GOLD[3], 1)
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

-- Every region sits at whole physical pixels from the frame's top-left corner.
local function put(region, x, y, w, h)
	region:ClearAllPoints()
	region:SetPoint("TOPLEFT", frame, "TOPLEFT", x, -y)
	region:SetSize(w, h)
end

local function level(style, on)
	return on and style.on or style.off
end

local function drawRun(style, col, row, length, colour)
	local tex = getTexture()
	put(tex, col * CELL, row * CELL, length * CELL, CELL)
	tex:SetColorTexture(level(style, colour >= 4), level(style, floor(colour / 2) % 2 == 1),
		level(style, colour % 2 == 1), 1)
end

-- Draw one row of cells, merging neighbours of the same colour into one texture.
local function drawRow(style, row, cells, first, last)
	local runStart, runColour = first, cells[first]
	for i = first + 1, last + 1 do
		local c = cells[i]
		if i > last or c ~= runColour then
			if runColour ~= 0 then  -- colour 0 is the background already
				drawRun(style, runStart - first, row, i - runStart, runColour)
			end
			runStart, runColour = i, c
		end
	end
end

local function plainNumber(v)
	v = ns.Plain(v)
	return type(v) == "number" and v or nil
end

local function clamp(v, lo, hi)
	return math.max(lo, math.min(v, hi))
end

-- The top-left corner of a w x h plate at the top-left corner of `anchor`, kept on screen, in
-- whole physical pixels from the screen's top-left so that every cell edge falls on a pixel
-- edge. nil when the anchor has no position.
local function placeAt(anchor, w, h, physW, physH)
	if ns.Plain(anchor:IsShown()) ~= true then return nil end
	local scale = plainNumber(anchor:GetEffectiveScale())
	local left, top = plainNumber(anchor:GetLeft()), plainNumber(anchor:GetTop())
	if not (scale and left and top) then return nil end
	local k = scale * physH / 768             -- physical pixels per unit of the anchor
	return clamp(floor(left * k + 0.5), 0, physW - w), clamp(physH - floor(top * k + 0.5), 0, physH - h)
end

-- Where the outer plate goes: where UI.BeaconAnchor(w, h) says (beside the panel), else the
-- top-left corner. The classic style keeps the proven corner.
local function place(style, w, h, physW, physH)
	local anchor = style.framed and ns.UI and ns.UI.BeaconAnchor and ns.UI.BeaconAnchor(w, h)
	if anchor then
		local ok, x, y = pcall(placeAt, anchor, w, h, physW, physH)
		if ok and x then return x, y end
	end
	return 0, 0
end

function Beacon.Render(data)
	ensureFrame()
	for i = 1, used do pool[i]:Hide() end
	used = 0
	local style = STYLES[Beacon.Style()]
	local cells = Beacon.ToCells(data)
	local rows = math.ceil(#cells / GRID_W)
	local gridW, gridH = GRID_W * CELL, (rows + 1) * CELL
	-- 1 UI unit = 1 physical pixel
	local physW, physH = GetPhysicalScreenSize()
	frame:SetScale(768 / physH)
	-- the frame is the cell grid; a framed plate adds a caption above it and a margin around
	local side, head = 0, 0
	local captionSize = math.max(10, floor(physH / 90 + 0.5))
	if style.framed then
		side, head = BORDER + PAD, BORDER + captionSize + 6
	end
	local plateW, plateH = gridW + 2 * side, gridH + head + side
	local x, y = place(style, plateW, plateH, physW, physH)
	frame:ClearAllPoints()
	frame:SetPoint("TOPLEFT", UIParent, "TOPLEFT", x + side, -(y + head))
	frame:SetSize(gridW, gridH)
	put(background, -side, -head, plateW, plateH)
	background:SetColorTexture(style.off, style.off, style.off, 1)
	if style.framed then
		put(edges[1], -side, -head, plateW, BORDER)
		put(edges[2], -side, gridH + side - BORDER, plateW, BORDER)
		put(edges[3], -side, -head, BORDER, plateH)
		put(edges[4], gridW + side - BORDER, -head, BORDER, plateH)
		local file = caption:GetFont()
		if file then caption:SetFont(file, captionSize, "") end
		caption:ClearAllPoints()
		caption:SetPoint("TOPLEFT", frame, "TOPLEFT", 0, head - BORDER - 3)
	end
	for i = 1, 4 do edges[i]:SetShown(style.framed == true) end
	caption:SetShown(style.framed == true)
	drawRow(style, 0, ROW0, 1, GRID_W)
	for r = 1, rows do
		local first = (r - 1) * GRID_W + 1
		drawRow(style, r, cells, first, math.min(first + GRID_W - 1, #cells))
	end
	return rows
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
