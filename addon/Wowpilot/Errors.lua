-- Collects recent Lua errors, blocked actions and red UI error messages so the
-- assistant can explain them without the player copying anything.
local _, ns = ...

local Errors = { lua = {}, blocked = {}, ui = {} }
ns.Errors = Errors

local function push(list, item, max)
	for _, existing in ipairs(list) do
		if existing.msg == item.msg then
			existing.n = (existing.n or 1) + 1
			return
		end
	end
	table.insert(list, 1, item)
	if #list > max then table.remove(list) end
end

local function plainString(s, maxLen)
	if type(s) ~= "string" or ns.IsSecret(s) then return nil end
	if #s > maxLen then s = s:sub(1, maxLen) .. "..." end
	return s
end

function Errors.RecordLua(msg)
	msg = plainString(msg, 400)
	if msg then push(Errors.lua, { msg = msg, t = time() }, 5) end
end

-- Wrap whatever error handler is active (Blizzard's or BugGrabber's).
local previous = geterrorhandler()
seterrorhandler(function(msg, ...)
	pcall(Errors.RecordLua, msg)
	if previous then return previous(msg, ...) end
end)

-- If BugGrabber loads after us it replaces the handler; listen to it too.
local function hookBugGrabber()
	if BugGrabber and BugGrabber.RegisterCallback and not Errors.bugGrabberHooked then
		Errors.bugGrabberHooked = true
		pcall(BugGrabber.RegisterCallback, Errors, "BugGrabber_BugGrabbed", function(_, err)
			if type(err) == "table" then Errors.RecordLua(err.message) end
		end)
	end
end

local f = CreateFrame("Frame")
local function tryRegister(event)
	pcall(f.RegisterEvent, f, event)  -- unknown events error on some flavors
end
tryRegister("ADDON_ACTION_BLOCKED")
tryRegister("ADDON_ACTION_FORBIDDEN")
tryRegister("UI_ERROR_MESSAGE")
tryRegister("PLAYER_LOGIN")

f:SetScript("OnEvent", function(_, event, a, b)
	if event == "PLAYER_LOGIN" then
		hookBugGrabber()
	elseif event == "ADDON_ACTION_BLOCKED" or event == "ADDON_ACTION_FORBIDDEN" then
		local who, what = plainString(a, 60), plainString(b, 120)
		if who or what then
			push(Errors.blocked, { msg = (who or "?") .. " tried " .. (what or "?"), kind = event, t = time() }, 5)
		end
	elseif event == "UI_ERROR_MESSAGE" then
		local text = plainString(b, 160)
		if text then push(Errors.ui, { msg = text, t = time() }, 5) end
	end
end)

function Errors.Snapshot()
	local out = {}
	if #Errors.lua > 0 then out.lua = Errors.lua end
	if #Errors.blocked > 0 then out.blocked = Errors.blocked end
	if #Errors.ui > 0 then out.ui = Errors.ui end
	return out
end
