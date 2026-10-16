-- One request = context + text -> screenshot -> companion -> reply slot.
local _, ns = ...

local Request = {}
ns.Request = Request

local rid = 0
local waiting = false
local thinkingTicker

local function stopThinking()
	if thinkingTicker then thinkingTicker:Cancel(); thinkingTicker = nil end
	ns.UI.SetStatus("")
end

-- Build the packet, dropping detail until it fits the screenshot channel.
local function buildPacket(kind, text)
	for level = 1, 5 do
		local packet = {
			v = ns.PROTOCOL, t = kind, sid = ns.sessionId, rid = rid,
			slot = ns.Inbox.next, slots = ns.NUM_SLOTS, text = text,
			ctx = ns.Context.Collect(level),
		}
		local json = ns.Json.Encode(packet)
		if #json <= ns.Beacon.MAX_BYTES then return json end
	end
	return nil
end

local function onReply(msg, seconds, how, slot)
	waiting = false
	stopThinking()
	if type(msg.say) == "string" and msg.say ~= "" then
		ns.UI.AddLine(msg.say)
	end
	if msg.t == "selftest" then
		ns.UI.AddLine(string.format("|cff66ff66Round trip OK|r in %.1fs via %s (slot %d, %d left).",
			seconds, how, slot, ns.Inbox.Remaining()))
	end
	ns.Actions.Handle(msg.actions)
	if ns.Inbox.Remaining() <= 3 then
		ns.UI.AddLine("|cffffaa00Reply slots are almost used up for this session. Reload your UI to refresh them.|r")
		ns.UI.ShowReload(true)
	end
end

local function onFail(reason)
	waiting = false
	stopThinking()
	if reason == "exhausted" then
		ns.UI.AddLine("|cffffaa00All reply slots are used for this session. Click Reload UI to continue.|r")
		ns.UI.ShowReload(true)
	else
		ns.UI.AddLine("|cffff5555No answer:|r " .. tostring(reason))
	end
end

function Request.Send(kind, text)
	ns.UI.Ensure()
	if waiting then
		ns.UI.AddLine("|cff888888Still working on the last one...|r")
		return
	end
	if ns.InCombat() and kind ~= "selftest" then
		ns.UI.AddLine("|cff888888Wowpilot pauses in combat. Ask again when combat ends.|r")
		return
	end
	if ns.Inbox.Remaining() <= 0 then
		onFail("exhausted")
		return
	end
	rid = rid + 1
	local thisRid = rid
	local json = buildPacket(kind, text)
	if not json then
		ns.UI.AddLine("|cffff5555That request is too long.|r")
		return
	end
	if kind == "ask" then ns.UI.AddLine("|cffaaaaaaYou:|r " .. text) end

	waiting = true
	ns.Inbox.PreCheck()
	local started = GetTime()
	thinkingTicker = C_Timer.NewTicker(0.5, function()
		ns.UI.SetStatus(string.format("thinking... %ds", GetTime() - started))
	end)

	local ok, err = ns.Beacon.Send(json, function(captured)
		if not captured then
			onFail("the game didn't take the screenshot")
			return
		end
		if kind == "ping" then
			waiting = false
			stopThinking()
			ns.UI.AddLine(string.format("Ping sent (%d bytes). Check the companion window for the decoded request.", #json))
			return
		end
		ns.Inbox.Await(thisRid, onReply, onFail)
	end)
	if not ok then onFail(err) end
end
