-- Minimal WoW API mock: enough to run the Gnomecaster addon in plain Lua 5.1.
-- Records what the addon does so tests can assert on it.
local M = { now = 1000, frames = {}, timers = {}, calls = {}, chat = {}, cvars = { screenshotFormat = "jpeg" } }
_G.MOCK = M

local function record(name, ...) M.calls[#M.calls + 1] = { name = name, args = { ... } } end
M.record = record

-- generic widget ---------------------------------------------------------
local Widget = {}
Widget.__index = function(t, k)
	local v = rawget(Widget, k)
	if v ~= nil then return v end
	return function() end  -- unknown method: no-op
end

local function newWidget(kind, name, parent)
	local w = setmetatable({ kind = kind, name = name, parent = parent, scripts = {}, events = {}, shown = true,
		points = {}, children = {}, regions = {}, text = "" }, Widget)
	M.frames[#M.frames + 1] = w
	if name then _G[name] = w end
	if parent and parent.children then parent.children[#parent.children + 1] = w end
	return w
end

function Widget:CreateTexture() local t = newWidget("Texture", nil, nil); self.regions[#self.regions + 1] = t; return t end
function Widget:CreateFontString() local t = newWidget("FontString", nil, nil); return t end
function Widget:RegisterEvent(e)
	if e == "SOME_UNKNOWN_EVENT" or (M.noScreenshotEvents and e:find("^SCREENSHOT")) then error("unknown event " .. e) end
	self.events[e] = true
end
function Widget:UnregisterEvent(e) self.events[e] = nil end
function Widget:SetScript(k, f) self.scripts[k] = f end
function Widget:GetScript(k) return self.scripts[k] end
function Widget:Show() self.shown = true end
function Widget:Hide() self.shown = false end
function Widget:IsShown() return self.shown end
function Widget:SetPoint(p, rel, rp, x, y)
	if type(rel) == "number" then x, y, rel, rp = rel, rp, nil, nil end
	self.point = { p = p, x = x or 0, y = y or 0 }
end
function Widget:ClearAllPoints() self.point = nil end
function Widget:SetSize(w, h) self.w, self.h = w, h end
function Widget:SetHeight(h) self.h = h end
function Widget:SetScale(s) self.scale = s end
function Widget:SetColorTexture(r, g, b, a) self.color = { r, g, b } end
function Widget:SetText(t) self.text = t end
function Widget:GetText() return self.text end
function Widget:GetStringHeight() return 14 end
function Widget:HasFocus() return self.focus == true end
function Widget:SetFocus() self.focus = true end
function Widget:ClearFocus() self.focus = false end
function Widget:AddMessage(text) M.chat[#M.chat + 1] = text end
function Widget:GetPoint() return "CENTER", nil, "CENTER", 0, 0 end
function Widget:SetFont(path)
	if self.kind ~= "EditBox" then return end
	local rel = path:gsub("\\", "/"):gsub("^Interface/AddOns/", "")
	local f = io.open(M.addonsDir .. "/" .. rel, "rb")
	if not f then return nil end
	local size = f:seek("end")
	f:close()
	if M.fontCache and M.fontCache[path] ~= nil then return M.fontCache[path] end
	local ok = size > 0 or nil
	if M.cacheFonts then M.fontCache = M.fontCache or {}; M.fontCache[path] = ok end
	return ok
end

function CreateFrame(kind, name, parent, template) return newWidget(kind, name, parent) end
UIParent = newWidget("Frame", "UIParent")
WorldFrame = newWidget("Frame", "WorldFrame")
DEFAULT_CHAT_FRAME = newWidget("ScrollingMessageFrame", "DEFAULT_CHAT_FRAME")
ChatFontNormal = {}
UISpecialFrames = {}
tinsert = table.insert
SlashCmdList = {}
ActionStatus = newWidget("Frame", "ActionStatus")

-- events / time ----------------------------------------------------------
function M.Fire(event, ...)
	for _, f in ipairs(M.frames) do
		if f.events[event] and f.scripts.OnEvent then f.scripts.OnEvent(f, event, ...) end
	end
end

function GetTime() return M.now end
function time() return 1760000000 end

C_Timer = {}
function C_Timer.After(d, fn) M.timers[#M.timers + 1] = { at = M.now + d, fn = fn } end
function C_Timer.NewTicker(d, fn)
	local t = { every = d, at = M.now + d, fn = fn, ticker = true }
	function t:Cancel() self.cancelled = true end
	M.timers[#M.timers + 1] = t
	return t
end

function M.Advance(seconds, step)
	step = step or 0.05
	local target = M.now + seconds
	while M.now < target - 1e-9 do
		M.now = M.now + step
		for _, f in ipairs(M.frames) do
			if f.shown and f.scripts.OnUpdate then f.scripts.OnUpdate(f, step) end
		end
		local due = {}
		for i = #M.timers, 1, -1 do
			local t = M.timers[i]
			if t.cancelled then table.remove(M.timers, i)
			elseif M.now >= t.at - 1e-9 then
				if t.ticker then t.at = t.at + t.every else table.remove(M.timers, i) end
				due[#due + 1] = t
			end
		end
		for _, t in ipairs(due) do if not t.cancelled then t.fn(t) end end
	end
end

-- game state -------------------------------------------------------------
WOW_PROJECT_ID = 1
function GetBuildInfo() return "12.1.5", "66666", "Oct 14 2026", 120105 end
function GetLocale() return "enUS" end
function UnitClass() return "Druid", "DRUID" end
function UnitRace() return "Night Elf", "NightElf" end
function UnitLevel() return 90 end
function UnitFactionGroup() return "Alliance" end
function GetSpecialization() return 4 end
function GetSpecializationInfo(i) return 105, "Restoration" end
M.combat = false
function InCombatLockdown() return M.combat end
function GetZoneText() return "Eversong Woods" end
function GetSubZoneText() return "Silvermoon City" end
function IsInInstance() return false, "none" end
function UnitExists(u) return u == "target" or u == "player" end
M.SECRET = setmetatable({}, { __tostring = function() return "<secret>" end,
	__concat = function() error("attempt to concatenate a secret value") end,
	__eq = function() error("compare secret") end, __lt = function() error("compare secret") end,
	__le = function() error("compare secret") end, __len = function() error("len secret") end })
function issecretvalue(v) return v == M.SECRET or rawequal(v, M.SECRET) end
function UnitName(u) if u == "target" then return M.targetName or "Training Dummy" end return "Tester" end
function UnitCanAttack() return true end
function UnitIsDead() return false end
function UnitIsPlayer() return false end
function GetPhysicalScreenSize() return 1920, 1080 end

C_Map = {}
function C_Map.GetBestMapForUnit() return 2395 end
function C_Map.GetMapInfo(id) return { name = "Eversong Woods" } end
function C_Map.GetPlayerMapPosition() return { GetXY = function() return 0.45231, 0.61877 end } end
function C_Map.CanSetUserWaypointOnMap() return true end
function C_Map.SetUserWaypoint(p) record("SetUserWaypoint", p.map, p.x, p.y) return true end
UiMapPoint = { CreateFromCoordinates = function(map, x, y) return { map = map, x = x, y = y } end }
C_SuperTrack = {}
function C_SuperTrack.SetSuperTrackedUserWaypoint(v) record("SetSuperTrackedUserWaypoint", v) end
function C_SuperTrack.GetSuperTrackedQuestID() return M.focusQuest or 0 end
function C_SuperTrack.SetSuperTrackedQuestID(id) record("SetSuperTrackedQuestID", id) end

C_QuestLog = {}
M.quests = {
	{ questID = 91001, title = "The Sunwell's Echo", level = 80 },
	{ questID = 91002, title = "Lost Supplies", level = 80 },
}
function C_QuestLog.GetNumQuestLogEntries() return #M.quests + 1 end
function C_QuestLog.GetInfo(i)
	if i == 1 then return { isHeader = true, title = "Eversong Woods" } end
	return M.quests[i - 1]
end
function C_QuestLog.IsComplete(id) return id == 91002 end
function C_QuestLog.GetQuestObjectives(id)
	if id == 91001 then return { { text = "Speak to Magister Ilyndra" }, { text = "0/6 Arcane Shards" } } end
	return {}
end
function C_QuestLog.GetTitleForQuestID(id) return id == 91001 and "The Sunwell's Echo" or nil end
function C_QuestLog.GetNextWaypoint(id) if id == 91001 then return 2395, 0.3812, 0.5521 end end

local errHandler = function(msg) M.lastError = msg end
function geterrorhandler() return errHandler end
function seterrorhandler(f) errHandler = f end
function M.RaiseError(msg) errHandler(msg) end

C_CVar = { GetCVar = function(k) return M.cvars[k] end, SetCVar = function(k, v) M.cvars[k] = v; record("SetCVar", k, v) end }

function Screenshot() record("Screenshot"); if M.onScreenshot then M.onScreenshot() end end

C_AddOns = {}
M.loaded = {}
function C_AddOns.LoadAddOn(name)
	if M.loaded[name] then return true end
	M.loaded[name] = true
	record("LoadAddOn", name)
	local chunk, err = loadfile(M.addonsDir .. "/" .. name .. "/inbox.lua")
	if not chunk then error(err) end
	chunk()
	return true
end

M.macros = {}
function GetMacroIndexByName(n) for i, m in ipairs(M.macros) do if m.name == n then return i end end return 0 end
function GetNumMacros() return #M.macros, 0 end
function CreateMacro(name, icon, body, perChar)
	if M.combat then error("protected") end
	M.macros[#M.macros + 1] = { name = name, icon = icon, body = body }
	record("CreateMacro", name, icon, body, perChar)
	return #M.macros
end
function EditMacro(i, name, icon, body) M.macros[i].body = body; record("EditMacro", i, name, body) end
function ClearCursor() end
function PickupMacro(n) record("PickupMacro", n) end
function PlaceAction(slot) record("PlaceAction", slot) end
function SetBindingMacro(key, name) record("SetBindingMacro", key, name) return true end
function SaveBindings(set) record("SaveBindings", set) end
function GetCurrentBindingSet() return 1 end
function GetBindingAction(key) return key == "SHIFT-E" and "MOVEANDSTEER" or "" end
function SetRaidTarget(u, i) record("SetRaidTarget", u, i) end
function GetFileIDFromPath() return 135000 end
function ReloadUI() record("ReloadUI") end
MAX_ACCOUNT_MACROS, MAX_CHARACTER_MACROS = 120, 18

-- load the addon ---------------------------------------------------------
function M.LoadAddon(dir)
	local ns = {}
	local toc = assert(io.open(dir .. "/Gnomecaster.toc")):read("*a")
	for line in toc:gmatch("[^\n]+") do
		if line:match("%.lua$") then
			local chunk = assert(loadfile(dir .. "/" .. line))
			chunk("Gnomecaster", ns)
		end
	end
	M.Fire("ADDON_LOADED", "Gnomecaster")
	M.Fire("PLAYER_LOGIN")
	return ns
end

-- dump the beacon as rectangles in physical pixels
function M.DumpBeacon(path)
	local beacon = _G.GnomecasterBeacon
	assert(beacon and beacon.shown, "beacon not shown at screenshot time")
	local _, physH = GetPhysicalScreenSize()
	local unit = beacon.scale * physH / 768   -- pixels per UI unit (should be 1)
	local out = assert(io.open(path, "w"))
	out:write(string.format("%d %d\n", beacon.w * unit + 0.5, beacon.h * unit + 0.5))
	for _, t in ipairs(beacon.regions) do
		local pt, col = rawget(t, "point"), rawget(t, "color")
		if t.shown and col and pt then
			out:write(string.format("%g %g %g %g %d %d %d\n", pt.x * unit, -pt.y * unit,
				(rawget(t, "w") or beacon.w) * unit, (rawget(t, "h") or beacon.h) * unit, col[1], col[2], col[3]))
		end
	end
	out:close()
end

return M
