-- The in-game panel: the conversation, a confirm bar for changes, and the input line.
-- Nothing here can be seen from the test machine, so every widget call is checked against
-- Blizzard's API documentation by tools/wow_api.py, and the test mock rejects any other.
local _, ns = ...

local UI = {}
ns.UI = UI

local FADE = 0.15            -- seconds for the panel and the confirm bar to fade
local MIN_W, MIN_H, MAX_W, MAX_H = 320, 200, 900, 700
local KEEP_LINES = 80        -- conversation lines kept across reloads
local HISTORY = 30           -- earlier questions reachable with the arrow keys
local MAX_LETTERS = 400
local GRIP = "Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-"   -- the chat frame's own resize grip

local panel, log, input, placeholder, counter, status, busyDot, confirm, confirmText, reloadButton
local fadeIn, fadeOut, confirmIn, pulse

local function db()
	return ns.db or {}
end

local function fade(frame, from, to, onFinished)
	local group = frame:CreateAnimationGroup()
	local alpha = group:CreateAnimation("Alpha")
	alpha:SetFromAlpha(from)
	alpha:SetToAlpha(to)
	alpha:SetDuration(FADE)
	alpha:SetSmoothing(to > from and "OUT" or "IN")
	group:SetToFinalAlpha(true)
	if onFinished then group:SetScript("OnFinished", onFinished) end
	return group
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
	panel:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1 })
	panel:SetBackdropColor(0.04, 0.05, 0.07, 0.92)
	panel:SetBackdropBorderColor(0.25, 0.55, 0.85, 0.9)
	panel:Hide()
	tinsert(UISpecialFrames, "GnomecasterPanel") -- Escape closes it
	fadeIn = fade(panel, 0, 1)
	fadeOut = fade(panel, 1, 0, function() panel:Hide(); panel:SetAlpha(1) end)

	local title = panel:CreateFontString(nil, "OVERLAY", "GameFontNormal")
	title:SetPoint("TOPLEFT", 10, -8)
	title:SetText("Gnomecaster")

	busyDot = panel:CreateTexture(nil, "OVERLAY")
	busyDot:SetSize(6, 6)
	busyDot:SetPoint("LEFT", title, "RIGHT", 6, 0)
	busyDot:SetColorTexture(0.4, 0.8, 1, 1)
	busyDot:Hide()
	pulse = busyDot:CreateAnimationGroup()
	pulse:SetLooping("BOUNCE")
	local glow = pulse:CreateAnimation("Alpha")
	glow:SetFromAlpha(1)
	glow:SetToAlpha(0.2)
	glow:SetDuration(0.6)
	glow:SetSmoothing("IN_OUT")

	status = panel:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
	status:SetPoint("TOPRIGHT", -30, -10)

	local close = CreateFrame("Button", nil, panel, "UIPanelCloseButton")
	close:SetPoint("TOPRIGHT", 2, 2)
	close:SetScript("OnClick", function() UI.Hide() end)

	log = CreateFrame("ScrollingMessageFrame", nil, panel)
	log:SetPoint("TOPLEFT", 10, -28)
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
		UI.AddLine("|cff88ccffAsk me anything, or tell me what to set up.|r Examples: \"take me to my quest\", \"mouseover Rejuvenation macro on slot 5 bound to Shift-E\", \"why did I get that error?\"")
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

function UI.AddLine(text, r, g, b)
	UI.Ensure()
	log:AddMessage(text, r or 1, g or 1, b or 1)
	log:ScrollToBottom()
	remember(text)
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
