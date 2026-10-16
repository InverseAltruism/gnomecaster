-- Gnomecaster core: namespace, saved settings, helpers, slash commands.
local ADDON, ns = ...

ns.VERSION = "0.1.0"
ns.PROTOCOL = 1
ns.NUM_SLOTS = 60          -- must match the number of Gnomecaster_InboxNN folders
ns.PREFIX = "|cff66ccffGnomecaster|r"

-- Random per-UI-load id, so replies meant for an earlier session are ignored.
ns.sessionId = string.format("%06x%06x", math.random(0, 0xFFFFFF), (time() or 0) % 0xFFFFFF)

function ns.Print(msg)
	DEFAULT_CHAT_FRAME:AddMessage(ns.PREFIX .. ": " .. tostring(msg))
end

-- Midnight (12.x) "secret values": addon code may not compare, branch on or
-- do math with them. Everything we send out goes through these guards.
function ns.IsSecret(v)
	return issecretvalue ~= nil and issecretvalue(v) == true
end

function ns.Plain(v)
	if ns.IsSecret(v) then return nil end
	return v
end

-- A plain (non-secret) string, cut to n bytes with "..." appended; nil otherwise.
function ns.Trim(s, n)
	if type(s) ~= "string" or ns.IsSecret(s) then return nil end
	if #s > n then return s:sub(1, n) .. "..." end
	return s
end

-- Text from the model or other addons is shown literally: "|" starts WoW's colour, link
-- and texture codes, so it is doubled before display.
function ns.Escape(s)
	return (tostring(s):gsub("|", "||"))
end

function ns.InCombat()
	return InCombatLockdown ~= nil and InCombatLockdown() == true
end

ns.GetCVar = (C_CVar and C_CVar.GetCVar) or GetCVar
ns.SetCVar = (C_CVar and C_CVar.SetCVar) or SetCVar
ns.LoadAddOn = (C_AddOns and C_AddOns.LoadAddOn) or LoadAddOn
ns.IsAddOnLoaded = (C_AddOns and C_AddOns.IsAddOnLoaded) or IsAddOnLoaded

local defaults = {
	autoApply = false,   -- apply macro/bar/keybind changes without asking
}

local events = CreateFrame("Frame")
events:RegisterEvent("ADDON_LOADED")
events:SetScript("OnEvent", function(self, event, name)
	if name ~= ADDON then return end
	GnomecasterDB = GnomecasterDB or {}
	for k, v in pairs(defaults) do
		if GnomecasterDB[k] == nil then GnomecasterDB[k] = v end
	end
	ns.db = GnomecasterDB
	self:UnregisterEvent("ADDON_LOADED")
end)

-- Key binding (Esc > Options > Keybindings > AddOns > Gnomecaster)
BINDING_HEADER_GNOMECASTER = "Gnomecaster"
BINDING_NAME_GNOMECASTER_TOGGLE = "Open Gnomecaster and start typing"

function GnomecasterToggle()
	ns.UI.Toggle(true)
end

local function help()
	ns.Print("commands:")
	ns.Print("  /gc  - open the panel (or bind a key in Keybindings > AddOns)")
	ns.Print("  /gc <question or request>  - ask directly")
	ns.Print("  /gc test  - full round trip test with the companion")
	ns.Print("  /gc ping  - only send (tests the screenshot channel)")
	ns.Print("  /gc poll  - only receive (tests the reply slots, use with 'companion write-test')")
	ns.Print("  /gc probe - check the ready-signal for the next slot")
	ns.Print("  /gc status")
	ns.Print("  /gc auto on|off  - apply changes without confirming")
end

SLASH_GNOMECASTER1 = "/gc"
SLASH_GNOMECASTER2 = "/gnomecaster"
SlashCmdList.GNOMECASTER = function(input)
	input = (input or ""):gsub("^%s+", ""):gsub("%s+$", "")
	local cmd = input:lower()
	if cmd == "" then
		ns.UI.Toggle(true)
	elseif cmd == "help" then
		help()
	elseif cmd == "test" then
		ns.UI.Toggle(false)
		ns.Request.Send("selftest", "round trip test")
	elseif cmd == "ping" then
		ns.Request.Send("ping", "screenshot channel test")
	elseif cmd == "poll" then
		ns.Inbox.DebugPoll()
	elseif cmd == "probe" then
		ns.Inbox.DebugProbe()
	elseif cmd == "status" then
		ns.Inbox.DebugStatus()
	elseif cmd == "auto on" or cmd == "auto off" then
		ns.db.autoApply = (cmd == "auto on")
		ns.Print("auto-apply is now " .. (ns.db.autoApply and "ON" or "OFF"))
	else
		ns.UI.Toggle(false)
		ns.Request.Send("ask", input)
	end
end
