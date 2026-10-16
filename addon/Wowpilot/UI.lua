-- The in-game panel: answers, a confirm bar for changes, and a text box.
local _, ns = ...

local UI = {}
ns.UI = UI

local panel, log, input, status, confirm, confirmText, reloadButton

local function savePosition(f)
	local point, _, relPoint, x, y = f:GetPoint()
	ns.db.pos = { point, relPoint, x, y }
end

local function build()
	panel = CreateFrame("Frame", "WowpilotPanel", UIParent, "BackdropTemplate")
	panel:SetSize(440, 320)
	local pos = ns.db and ns.db.pos
	if pos then panel:SetPoint(pos[1], UIParent, pos[2], pos[3], pos[4]) else panel:SetPoint("RIGHT", -60, 40) end
	panel:SetFrameStrata("HIGH")
	panel:SetClampedToScreen(true)
	panel:SetMovable(true)
	panel:EnableMouse(true)
	panel:RegisterForDrag("LeftButton")
	panel:SetScript("OnDragStart", panel.StartMoving)
	panel:SetScript("OnDragStop", function(self) self:StopMovingOrSizing(); savePosition(self) end)
	panel:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1 })
	panel:SetBackdropColor(0.04, 0.05, 0.07, 0.92)
	panel:SetBackdropBorderColor(0.25, 0.55, 0.85, 0.9)
	tinsert(UISpecialFrames, "WowpilotPanel") -- Escape closes it

	local title = panel:CreateFontString(nil, "OVERLAY", "GameFontNormal")
	title:SetPoint("TOPLEFT", 10, -8)
	title:SetText("Wowpilot")

	status = panel:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
	status:SetPoint("TOPRIGHT", -30, -10)

	local close = CreateFrame("Button", nil, panel, "UIPanelCloseButton")
	close:SetPoint("TOPRIGHT", 2, 2)

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
	input:SetPoint("BOTTOMRIGHT", -12, 10)
	input:SetHeight(24)
	input:SetAutoFocus(false)
	input:SetMaxLetters(400)
	input:SetScript("OnEnterPressed", function(self)
		local text = self:GetText():gsub("^%s+", ""):gsub("%s+$", "")
		self:SetText("")
		if text ~= "" then ns.Request.Send("ask", text) end
	end)
	input:SetScript("OnEscapePressed", function(self) self:ClearFocus() end)

	-- Confirm bar for macro / bar / keybind / setting changes
	confirm = CreateFrame("Frame", nil, panel, "BackdropTemplate")
	confirm:SetPoint("BOTTOMLEFT", panel, "TOPLEFT", 0, 4)
	confirm:SetPoint("BOTTOMRIGHT", panel, "TOPRIGHT", 0, 4)
	confirm:SetHeight(80)
	confirm:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1 })
	confirm:SetBackdropColor(0.08, 0.07, 0.03, 0.95)
	confirm:SetBackdropBorderColor(0.9, 0.7, 0.2, 0.9)
	confirm:Hide()
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

	UI.AddLine("|cff88ccffAsk me anything, or tell me what to set up.|r Examples: \"take me to my quest\", \"mouseover Rejuvenation macro on slot 5 bound to Shift-E\", \"why did I get that error?\"")
end

function UI.Ensure()
	if not panel then build() end
end

function UI.Toggle(focus)
	UI.Ensure()
	if panel:IsShown() and focus and not input:HasFocus() then
		C_Timer.After(0, function() input:SetFocus() end) -- next frame, so the key itself isn't typed
		return
	end
	if panel:IsShown() and not focus then return end
	if panel:IsShown() then panel:Hide() return end
	panel:Show()
	if focus then C_Timer.After(0, function() input:SetFocus() end) end
end

function UI.AddLine(text, r, g, b)
	UI.Ensure()
	log:AddMessage(text, r or 1, g or 1, b or 1)
end

function UI.SetStatus(text)
	UI.Ensure()
	status:SetText(text or "")
end

function UI.ShowConfirm(text)
	UI.Ensure()
	confirmText:SetText(text)
	confirm:SetHeight(math.max(60, confirmText:GetStringHeight() + 44))
	confirm:Show()
end

function UI.HideConfirm()
	if confirm then confirm:Hide() end
end

function UI.ShowReload(show)
	UI.Ensure()
	if show then reloadButton:Show() else reloadButton:Hide() end
end
