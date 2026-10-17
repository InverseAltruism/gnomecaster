-- Frame templates for the mock, loaded by wowmock.lua. Each one builds the child keys and mixin
-- methods of Blizzard's XML (Blizzard_SharedXML at the commit pinned in tools/wow_api.py), so the
-- addon's real panel code runs against the same structure:
--   SharedUIPanelTemplates.xml  InsetFrameTemplate, PortraitFrameBaseTemplate,
--                               ButtonFrameBaseTemplate, ButtonFrameTemplate, UIPanelCloseButton*,
--                               UIPanelButtonTemplate
--   PortraitFrame.lua           TitledPanelMixin, PortraitFrameMixin
--   Dialog/DialogTemplates.xml  DialogBorderNoCenterTemplate, DialogBorderDarkTemplate
--   InputBox/InputBoxTemplates.xml  InputBoxTemplate
-- A template that is not modelled here is an error, so a typo fails a test instead of a player's
-- UI. M.missingTemplates[name] = "error" or "plain" plays a client without that template: what a
-- real client does then is not verified, so the addon must cope with both.
return function(M, Widget, newWidget)
	M.missingTemplates = {}

	local function frame(parent, kind) return newWidget(kind or "Frame", nil, parent) end
	local function texture(parent, file)
		local t = parent:CreateTexture()
		t.texture = file
		return t
	end
	local function fontString(parent, font)
		local s = parent:CreateFontString()
		s.font = font
		return s
	end

	local TitledPanelMixin = {
		GetTitleText = function(self) return self.TitleContainer.TitleText end,
		SetTitle = function(self, title) self:GetTitleText():SetText(title) end,
	}
	local PortraitFrameMixin = {
		GetPortrait = function(self) return self.PortraitContainer.portrait end,
		SetPortraitToAsset = function(self, file) self:GetPortrait():SetTexture(file) end,
	}
	local function mixin(f, ...)
		for _, m in ipairs({ ... }) do
			for k, v in pairs(m) do rawset(f, k, v) end
		end
	end

	local T = {}
	T.NineSlicePanelTemplate = function(f) end
	T.InsetFrameTemplate = function(f)
		f.layoutType = "InsetFrameTemplate"
		f.Bg = texture(f, "Interface\\FrameGeneral\\UI-Background-Marble")
		f.NineSlice = frame(f)
	end
	T.UIPanelCloseButtonNoScripts = function(f) end
	T.UIPanelCloseButton = function(f) end
	T.UIPanelCloseButtonDefaultAnchors = function(f) T.UIPanelCloseButton(f); f:SetPoint("TOPRIGHT", 1, 0) end
	T.UIPanelButtonTemplate = function(f) end
	T.InputBoxTemplate = function(f) end
	T.BackdropTemplate = function(f) end
	T.PortraitFrameBaseTemplate = function(f)
		f.layoutType = "PortraitFrameTemplate"
		f.NineSlice = frame(f)
		f.PortraitContainer = frame(f)
		f.PortraitContainer.portrait = texture(f.PortraitContainer)
		f.TitleContainer = frame(f)
		f.TitleContainer.TitleText = fontString(f.TitleContainer, "GameFontNormal")
		mixin(f, TitledPanelMixin, PortraitFrameMixin)
	end
	T.ButtonFrameBaseTemplate = function(f)
		T.PortraitFrameBaseTemplate(f)
		f.Bg = texture(f, "Interface\\FrameGeneral\\UI-Background-Rock")
		f.TopTileStreaks = texture(f)
		f.CloseButton = frame(f, "Button")
		T.UIPanelCloseButtonDefaultAnchors(f.CloseButton)
	end
	T.ButtonFrameTemplate = function(f)
		T.ButtonFrameBaseTemplate(f)
		f.Inset = frame(f)
		T.InsetFrameTemplate(f.Inset)
		f.Inset:SetPoint("TOPLEFT", 4, -60)
		f.Inset:SetPoint("BOTTOMRIGHT", -6, 26)
	end
	T.DialogBorderNoCenterTemplate = function(f) f.layoutType = "Dialog" end
	T.DialogBorderDarkTemplate = function(f)
		T.DialogBorderNoCenterTemplate(f)
		f.Bg = texture(f, "Interface\\DialogFrame\\UI-DialogBox-Background-Dark")
	end

	-- Keys a template adds (parts such as Inset, mixin methods such as SetTitle) read as nil on a
	-- frame without that template, as in the game; any other unknown method is still an error.
	local templateKeys = {}
	local before = #M.frames
	for _, build in pairs(T) do
		local probe = newWidget("Frame", nil, nil)
		build(probe)
		for k in pairs(probe) do if type(k) == "string" and k:match("^%u") then templateKeys[k] = true end end
	end
	for i = #M.frames, before + 1, -1 do M.frames[i] = nil end
	local index = Widget.__index
	Widget.__index = function(t, k)
		if templateKeys[k] then return nil end
		return index(t, k)
	end

	local function names(list)
		local out = {}
		for name in tostring(list):gmatch("[^,%s]+") do out[#out + 1] = name end
		return out
	end

	-- CreateFrame with a template: refuse unknown names before any frame exists, as a failed
	-- CreateFrame would; a "plain" missing template yields a frame without its parts.
	function M.CreateFrame(kind, name, parent, template)
		local apply = {}
		for _, t in ipairs(template and names(template) or {}) do
			local missing = M.missingTemplates[t]
			if missing == "error" then error("CreateFrame: unknown template " .. t, 3) end
			if not T[t] then error("template " .. t .. " is not modelled in tests/wowmock_templates.lua", 3) end
			if not missing then apply[#apply + 1] = t end
		end
		local w = newWidget(kind, name, parent)
		w.template = template
		for _, t in ipairs(apply) do T[t](w) end
		return w
	end

	-- What the panel tests read back: textures, atlases, alpha, anchors with their relative frame.
	function Widget:SetTexture(file) self.texture = file end
	function Widget:SetAtlas(atlas) self.atlas = atlas end
	function Widget:SetDesaturated(on) self.desaturated = on and true or false end
	function Widget:SetAlpha(a) self.alpha = a end
	function Widget:GetAlpha() return self.alpha or 1 end
	local setPoint, clearAllPoints = Widget.SetPoint, Widget.ClearAllPoints
	function Widget:SetPoint(p, rel, rp, x, y)
		setPoint(self, p, rel, rp, x, y)
		if type(rel) == "number" then rel, rp, x, y = nil, nil, rel, rp end
		self.points[p] = { rel = rel or self.parent, rp = rp or p, x = x or 0, y = y or 0 }
	end
	function Widget:ClearAllPoints()
		clearAllPoints(self)
		self.points = {}
	end

	-- Screen geometry in UIParent units: M.SetRect(frame, left, bottom, width, height).
	function M.SetRect(f, left, bottom, width, height) f.rect = { l = left, b = bottom, w = width, h = height } end
	function Widget:GetLeft() return self.rect and self.rect.l end
	function Widget:GetBottom() return self.rect and self.rect.b end
	function Widget:GetRight() return self.rect and self.rect.l + self.rect.w end
	function Widget:GetTop() return self.rect and self.rect.b + self.rect.h end
	function Widget:GetWidth() return self.rect and self.rect.w or rawget(self, "w") end
	function Widget:GetHeight() return self.rect and self.rect.h or rawget(self, "h") end
	function Widget:GetEffectiveScale() return self.effectiveScale or 1 end

	-- Atlases the client knows (C_Texture.GetAtlasInfo); tests remove one to play a client without it.
	M.atlases = { ["worldquest-icon-engineering"] = true }
	C_Texture = { GetAtlasInfo = function(name) if M.atlases[name] then return { width = 32, height = 32 } end end }
end
