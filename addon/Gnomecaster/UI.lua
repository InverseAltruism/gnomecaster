-- The in-game panel: the conversation, a confirm bar for changes, and the input line.
-- Nothing here can be seen from the test machine, so every widget call is checked against
-- Blizzard's API documentation by tools/wow_api.py, and the test mock rejects any other.
local _, ns = ...

local UI = {}
ns.UI = UI

local FADE = 0.18            -- seconds for the panel and the confirm bar to fade in or out
local RISE = 8               -- pixels the panel rises while it fades in
local MEDIA = "Interface\\AddOns\\Gnomecaster\\Media\\"
local ANSWER = "|cfff5b33bGnomecaster:|r "                     -- brand gold, as in the desktop app
-- Answers type themselves out: characters per second, and the shortest and longest reveal
local TYPE_RATE, TYPE_MIN, TYPE_MAX = 220, 0.25, 1.4
local MIN_W, MIN_H, MAX_W, MAX_H = 320, 200, 900, 700
local KEEP_LINES = 80        -- conversation lines kept across reloads
local HISTORY = 30           -- earlier questions reachable with the arrow keys
local MAX_LETTERS = 400
local GRIP = "Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-"   -- the chat frame's own resize grip

local panel, log, input, placeholder, counter, status, busyDot, confirm, confirmText, reloadButton
local fadeIn, fadeOut, confirmIn, pulse
local typer = { queue = {} }   -- the answer being typed out, and lines waiting behind it

local function db()
	return ns.db or {}
end

local function fade(frame, from, to, onFinished, rise)
	local group = frame:CreateAnimationGroup()
	local order = 1
	if rise then
		-- start lower, then glide up to the anchor while fading in (the two moves cancel out)
		local down = group:CreateAnimation("Translation")
		down:SetOffset(0, -rise)
		down:SetDuration(0)
		down:SetOrder(1)
		local up = group:CreateAnimation("Translation")
		up:SetOffset(0, rise)
		up:SetDuration(FADE)
		up:SetSmoothing("OUT")
		up:SetOrder(2)
		order = 2
	end
	local alpha = group:CreateAnimation("Alpha")
	alpha:SetFromAlpha(from)
	alpha:SetToAlpha(to)
	alpha:SetDuration(FADE)
	alpha:SetSmoothing(to > from and "OUT" or "IN")
	alpha:SetOrder(order)
	group:SetToFinalAlpha(true)
	if onFinished then group:SetScript("OnFinished", onFinished) end
	return group
end

-- An answer split into pieces that are shown whole: escape sequences (colours, textures,
-- links) and UTF-8 characters, so a partly typed line never shows a broken code or byte.
local function pieces(text)
	local out, i, n = {}, 1, #text
	while i <= n do
		local c, j = text:byte(i), i
		if c == 124 then                                    -- "|"
			local k = text:sub(i + 1, i + 1)
			if k == "c" then j = i + 9                      -- |cAARRGGBB
			elseif k == "T" then j = select(2, text:find("|t", i + 2, true)) or n
			elseif k == "A" then j = select(2, text:find("|a", i + 2, true)) or n
			elseif k == "H" then
				local stop = text:find("|h", i + 2, true)
				stop = stop and text:find("|h", stop + 2, true)
				j = stop and stop + 1 or n
			else j = i + 1 end                              -- |r, ||, |n
		elseif c >= 240 then j = i + 3
		elseif c >= 224 then j = i + 2
		elseif c >= 192 then j = i + 1 end
		j = math.min(j, n)
		out[#out + 1] = text:sub(i, j)
		i = j + 1
	end
	return out
end

local function append(text, r, g, b)
	log:AddMessage(text, r or 1, g or 1, b or 1)
	log:ScrollToBottom()
end

local function retype(text)
	local tag = typer.tag
	log:TransformMessages(function(_, _, _, _, t) return t == tag end,
		function(_, r, g, b, t) return text, r, g, b, t end)
end

local startTyping

-- Shows the whole answer and lets the lines that waited behind it through.
local function finishTyping()
	if not typer.tag then return end
	retype(typer.full)
	typer.tag = nil
	typer.driver:SetScript("OnUpdate", nil)
	while #typer.queue > 0 and not typer.tag do
		local item = table.remove(typer.queue, 1)
		if item.answer then startTyping(item.text, item.r, item.g, item.b) else append(item.text, item.r, item.g, item.b) end
	end
end

local function typeStep()
	local share = math.min(1, (GetTime() - typer.started) / typer.duration)
	local count = math.floor(#typer.pieces * share)
	if count ~= typer.shown then
		typer.shown = count
		retype(ANSWER .. table.concat(typer.pieces, "", 1, count) .. "|r")
	end
	if share >= 1 then finishTyping() end
end

startTyping = function(text, r, g, b)
	typer.full = ANSWER .. text
	if not log.TransformMessages then                   -- a client without it shows the line at once
		append(typer.full, r, g, b)
		return
	end
	typer.pieces = pieces(text)
	typer.duration = math.max(TYPE_MIN, math.min(TYPE_MAX, #typer.pieces / TYPE_RATE))
	typer.started, typer.shown, typer.tag = GetTime(), 0, {}
	log:AddMessage(ANSWER, r or 1, g or 1, b or 1, typer.tag)
	log:ScrollToBottom()
	typer.driver = typer.driver or CreateFrame("Frame")
	typer.driver:SetScript("OnUpdate", typeStep)
end

local function savePosition()
	local point, _, relPoint, x, y = panel:GetPoint()
	db().pos = { point, relPoint, x, y }
	db().size = { panel:GetWidth(), panel:GetHeight() }
end

local function remember(text)
	local saved = db()
	saved.log = saved.log or {}
	saved.log[#saved.log + 1] = text
	while #saved.log > KEEP_LINES do table.remove(saved.log, 1) end
end

local function updateInputHints()
	local n = #(input:GetText() or "")
	placeholder:SetShown(n == 0 and not input:HasFocus())
	counter:SetShown(n >= MAX_LETTERS - 100)
	counter:SetText(MAX_LETTERS - n .. " left")
end

local function submit(self)
	local text = self:GetText():gsub("^%s+", ""):gsub("%s+$", "")
	if text == "" then
		self:ClearFocus()
		return
	end
	-- Only a question that went out leaves the box; a refused one stays to be sent again.
	if ns.Request.Send("ask", text) then
		self:AddHistoryLine(text)
		local saved = db()
		saved.history = saved.history or {}
		saved.history[#saved.history + 1] = text
		while #saved.history > HISTORY do table.remove(saved.history, 1) end
		self:SetText("")
	end
	updateInputHints()
end

local function build()
	panel = CreateFrame("Frame", "GnomecasterPanel", UIParent, "BackdropTemplate")
	local size = db().size
	panel:SetSize(size and size[1] or 440, size and size[2] or 320)
	local pos = db().pos
	if pos then panel:SetPoint(pos[1], UIParent, pos[2], pos[3], pos[4]) else panel:SetPoint("RIGHT", -60, 40) end
	panel:SetFrameStrata("HIGH")
	panel:SetClampedToScreen(true)
	panel:SetMovable(true)
	panel:SetResizable(true)
	-- SetResizeBounds is documented for retail 12.1.5; the Classic flavors in the TOC are not
	-- checked here, and a panel without bounds beats a Lua error on opening it.
	if panel.SetResizeBounds then panel:SetResizeBounds(MIN_W, MIN_H, MAX_W, MAX_H) end
	panel:EnableMouse(true)
	panel:RegisterForDrag("LeftButton")
	panel:SetScript("OnDragStart", panel.StartMoving)
	panel:SetScript("OnDragStop", function(self) self:StopMovingOrSizing(); savePosition() end)
	-- the desktop app's night violet, with a violet edge
	panel:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1 })
	panel:SetBackdropColor(0.07, 0.05, 0.17, 0.94)
	panel:SetBackdropBorderColor(0.45, 0.31, 0.88, 0.75)
	panel:Hide()
	tinsert(UISpecialFrames, "GnomecasterPanel") -- Escape closes it
	fadeIn = fade(panel, 0, 1, nil, RISE)
	fadeOut = fade(panel, 1, 0, function() panel:Hide(); panel:SetAlpha(1) end)

	local icon = panel:CreateTexture(nil, "OVERLAY")
	icon:SetSize(16, 16)
	icon:SetPoint("TOPLEFT", 9, -7)
	icon:SetTexture(MEDIA .. "icon")

	local title = panel:CreateFontString(nil, "OVERLAY", "GameFontNormal")
	title:SetPoint("LEFT", icon, "RIGHT", 6, 0)
	title:SetText("Gnomecaster")

	local rule = panel:CreateTexture(nil, "ARTWORK")
	rule:SetHeight(1)
	rule:SetPoint("TOPLEFT", 8, -28)
	rule:SetPoint("TOPRIGHT", -8, -28)
	rule:SetColorTexture(1, 1, 1, 0.08)

	-- the spark from the icon, glowing while a question is out
	busyDot = panel:CreateTexture(nil, "OVERLAY")
	busyDot:SetSize(14, 14)
	busyDot:SetPoint("LEFT", title, "RIGHT", 4, 0)
	busyDot:SetTexture(MEDIA .. "spark")
	busyDot:SetBlendMode("ADD")
	busyDot:Hide()
	pulse = busyDot:CreateAnimationGroup()
	pulse:SetLooping("BOUNCE")
	local glow = pulse:CreateAnimation("Alpha")
	glow:SetFromAlpha(1)
	glow:SetToAlpha(0.25)
	glow:SetDuration(0.7)
	glow:SetSmoothing("IN_OUT")

	status = panel:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
	status:SetPoint("TOPRIGHT", -30, -10)

	local close = CreateFrame("Button", nil, panel, "UIPanelCloseButton")
	close:SetPoint("TOPRIGHT", 2, 2)
	close:SetScript("OnClick", function() UI.Hide() end)

	log = CreateFrame("ScrollingMessageFrame", nil, panel)
	log:SetPoint("TOPLEFT", 10, -34)
	log:SetPoint("BOTTOMRIGHT", -10, 44)
	log:SetFontObject(ChatFontNormal)
	log:SetJustifyH("LEFT")
	log:SetFading(false)
	log:SetMaxLines(400)
	log:SetIndentedWordWrap(false)
	log:EnableMouseWheel(true)
	log:SetScript("OnMouseWheel", function(self, delta)
		if delta > 0 then self:ScrollUp() else self:ScrollDown() end
	end)

	input = CreateFrame("EditBox", nil, panel, "InputBoxTemplate")
	input:SetPoint("BOTTOMLEFT", 16, 10)
	input:SetPoint("BOTTOMRIGHT", -28, 10)
	input:SetHeight(24)
	input:SetAutoFocus(false)
	input:SetMaxLetters(MAX_LETTERS)
	input:SetAltArrowKeyMode(false)       -- Up and Down walk through earlier questions
	input:SetHistoryLines(HISTORY)
	for _, line in ipairs(db().history or {}) do input:AddHistoryLine(line) end
	input:SetScript("OnEnterPressed", submit)
	input:SetScript("OnEscapePressed", function(self) self:ClearFocus() end)
	input:SetScript("OnTextChanged", updateInputHints)
	input:SetScript("OnEditFocusGained", updateInputHints)
	input:SetScript("OnEditFocusLost", updateInputHints)

	placeholder = input:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
	placeholder:SetPoint("LEFT", 2, 0)
	placeholder:SetText("Ask Gnomecaster, or tell it what to set up...")
	counter = input:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
	counter:SetPoint("RIGHT", -4, 0)

	local grip = CreateFrame("Button", nil, panel)
	grip:SetSize(16, 16)
	grip:SetPoint("BOTTOMRIGHT", -2, 2)
	grip:SetNormalTexture(GRIP .. "Up")
	grip:SetHighlightTexture(GRIP .. "Highlight")
	grip:SetPushedTexture(GRIP .. "Down")
	grip:SetScript("OnMouseDown", function() panel:StartSizing("BOTTOMRIGHT") end)
	grip:SetScript("OnMouseUp", function() panel:StopMovingOrSizing(); savePosition() end)

	-- Confirm bar for macro / bar / keybind / setting changes
	confirm = CreateFrame("Frame", nil, panel, "BackdropTemplate")
	confirm:SetPoint("BOTTOMLEFT", panel, "TOPLEFT", 0, 4)
	confirm:SetPoint("BOTTOMRIGHT", panel, "TOPRIGHT", 0, 4)
	confirm:SetHeight(80)
	confirm:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1 })
	confirm:SetBackdropColor(0.08, 0.07, 0.03, 0.95)
	confirm:SetBackdropBorderColor(0.9, 0.7, 0.2, 0.9)
	confirm:Hide()
	confirmIn = fade(confirm, 0, 1)
	confirmText = confirm:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
	confirmText:SetPoint("TOPLEFT", 10, -8)
	confirmText:SetPoint("TOPRIGHT", -10, -8)
	confirmText:SetJustifyH("LEFT")
	local apply = CreateFrame("Button", nil, confirm, "UIPanelButtonTemplate")
	apply:SetSize(90, 22)
	apply:SetPoint("BOTTOMRIGHT", -10, 8)
	apply:SetText("Apply")
	apply:SetScript("OnClick", function() ns.Actions.Apply() end)
	local cancel = CreateFrame("Button", nil, confirm, "UIPanelButtonTemplate")
	cancel:SetSize(90, 22)
	cancel:SetPoint("RIGHT", apply, "LEFT", -6, 0)
	cancel:SetText("Cancel")
	cancel:SetScript("OnClick", function() ns.Actions.Cancel() end)

	reloadButton = CreateFrame("Button", nil, panel, "UIPanelButtonTemplate")
	reloadButton:SetSize(120, 22)
	reloadButton:SetPoint("BOTTOMRIGHT", -10, 40)
	reloadButton:SetText("Reload UI")
	reloadButton:SetScript("OnClick", function() ReloadUI() end)
	reloadButton:Hide()

	local saved = db().log
	if saved and #saved > 0 then
		for _, line in ipairs(saved) do log:AddMessage(line, 0.7, 0.7, 0.7) end
	else
		UI.AddLine("|cfff5b33bAsk me anything, or tell me what to set up.|r Examples: \"take me to my quest\", \"mouseover Rejuvenation macro on slot 5 bound to Shift-E\", \"why did I get that error?\"")
	end
	updateInputHints()
end

function UI.Ensure()
	if not panel then build() end
end

local function show(focus)
	if not panel:IsShown() or fadeOut:IsPlaying() then
		fadeOut:Stop()
		panel:SetAlpha(0)
		panel:Show()
		fadeIn:Play()
	end
	if focus then C_Timer.After(0, function() input:SetFocus() end) end -- next frame, so the key itself isn't typed
end

function UI.Hide()
	finishTyping()
	if panel and panel:IsShown() and not fadeOut:IsPlaying() then
		input:ClearFocus()
		fadeIn:Stop()
		fadeOut:Play()
	end
end

-- From the key binding or /gc: open and focus; focus if open; close if already focused.
function UI.Toggle(focus)
	UI.Ensure()
	if panel:IsShown() and not fadeOut:IsPlaying() then
		if not focus then return end
		if input:HasFocus() then UI.Hide() else show(true) end
		return
	end
	show(focus)
end

-- Shows the panel if it is hidden, without taking keyboard focus.
function UI.Reveal()
	UI.Ensure()
	if not panel:IsShown() or fadeOut:IsPlaying() then show(false) end
end

-- A line waits while an answer is typing, so lines stay in the order they were added.
function UI.AddLine(text, r, g, b)
	UI.Ensure()
	remember(text)
	if typer.tag then
		typer.queue[#typer.queue + 1] = { text = text, r = r, g = g, b = b }
	else
		append(text, r, g, b)
	end
end

-- An answer from the companion: labelled, and typed out unless the client cannot.
function UI.Say(text, r, g, b)
	UI.Ensure()
	remember(ANSWER .. text)
	if typer.tag then
		typer.queue[#typer.queue + 1] = { text = text, r = r, g = g, b = b, answer = true }
	else
		startTyping(text, r, g, b)
	end
end

function UI.SetStatus(text)
	UI.Ensure()
	status:SetText(text or "")
end

function UI.SetBusy(busy)
	UI.Ensure()
	if busy then
		busyDot:Show()
		if not pulse:IsPlaying() then pulse:Play() end
	else
		pulse:Stop()
		busyDot:Hide()
		status:SetText("")
	end
end

function UI.ShowConfirm(text)
	UI.Ensure()
	confirmText:SetText(text)
	confirm:SetHeight(math.max(60, confirmText:GetStringHeight() + 44))
	if not confirm:IsShown() then
		confirm:SetAlpha(0)
		confirm:Show()
		confirmIn:Play()
	end
end

function UI.HideConfirm()
	if confirm then
		confirmIn:Stop()
		confirm:Hide()
	end
end

function UI.ShowReload(show)
	UI.Ensure()
	reloadButton:SetShown(show and true or false)
end
