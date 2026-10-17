-- One request = context + text -> screenshot -> companion -> reply slot.
local _, ns = ...

local Request = {}
ns.Request = Request

local rid = 0
local waiting = false
local statusTicker

-- What the status line says while a question is out.
local STAGES = {
	sending = "sending",
	waiting = "waiting for the companion",
	thinking = "thinking",
	silent = "no word from the companion",
}

local function stopStatus()
	if statusTicker then statusTicker:Cancel(); statusTicker = nil end
	ns.UI.SetBusy(false)
end

local function startStatus(stage)
	local started = GetTime()
	local state = { stage = stage }
	local function update()
		local dots = string.rep(".", 1 + math.floor((GetTime() - started) * 2.5) % 3)
		ns.UI.SetStatus(string.format("%s%s %ds", STAGES[state.stage], dots, GetTime() - started))
	end
	stopStatus()
	ns.UI.SetBusy(true)
	update()
	statusTicker = C_Timer.NewTicker(0.2, update)
	return state
end

-- The conversation key lets the companion tell one conversation from the next. It is kept
-- in the saved variables, so it survives /reload; /gc new starts another. Those are shared
-- by the account, so each character has its own key.
local function newKey()
	return string.format("%04x%06x%06x", (time() or 0) % 0x10000, math.random(0, 0xFFFFFF), math.random(0, 0xFFFFFF))
end

local function character()
	local guid = ns.Plain(UnitGUID("player"))
	if type(guid) == "string" and guid ~= "" then return guid end
	return "name:" .. tostring(ns.Plain(UnitName("player")))
end

function Request.Conversation()
	if type(ns.db.convs) ~= "table" then ns.db.convs = {} end
	ns.db.conv = nil                               -- the account-wide key of earlier builds
	local who = character()
	local key = ns.db.convs[who]
	if type(key) ~= "string" or key == "" or #key > 16 then
		key = newKey()
		ns.db.convs[who] = key
	end
	return key
end

function Request.NewConversation()
	Request.Conversation()
	ns.db.convs[character()] = newKey()
	ns.Actions.ClearResults()
	ns.UI.Reveal()
	ns.UI.AddLine("|cff888888New conversation: the assistant starts over from here.|r")
end

-- The packet as JSON, dropping detail until it fits the screenshot channel; nil when even
-- the least detail is too much. Questions also carry what became of the last answer's actions.
function Request.BuildPacket(kind, text)
	for level, opts in ipairs(ns.Context.LEVELS) do
		local packet = {
			v = ns.PROTOCOL, t = kind, sid = ns.sessionId, rid = rid,
			slot = ns.Inbox.next, slots = ns.NUM_SLOTS, text = text,
			conv = Request.Conversation(),
			last = kind == "ask" and ns.Actions.Results(opts.last) or nil,
			ctx = ns.Context.Collect(level),
		}
		local json = ns.Json.Encode(packet)
		if #json <= ns.Beacon.MAX_BYTES then return json, level end
	end
	return nil
end

local function onReply(msg, seconds, how, slot, request)
	waiting = false
	stopStatus()
	ns.UI.Reveal()
	if type(msg.say) == "string" and msg.say ~= "" then
		-- error replies (bad key, rate limit, ...) stand out; the text is the companion's advice
		ns.UI.Say((msg.error and "|cffffaa00" or "") .. ns.Escape(msg.say) .. (msg.error and "|r" or ""))
	end
	if msg.t == "selftest" then
		ns.UI.AddLine(string.format("|cff66ff66Round trip OK|r in %.1fs via %s (slot %d, %d left).",
			seconds, how, slot, ns.Inbox.Remaining()))
	end
	ns.Actions.Handle(msg.actions, request)
	if ns.Inbox.Remaining() <= ns.Inbox.LowMark() then
		ns.UI.AddLine("|cffffaa00Reply slots are almost used up for this session. Reload your UI to refresh them.|r")
		ns.UI.ShowReload(true)
	end
end

local function onFail(reason)
	waiting = false
	stopStatus()
	ns.UI.Reveal()
	if reason == "exhausted" then
		ns.UI.AddLine("|cffffaa00All reply slots are used for this session. Click Reload UI to continue.|r")
		ns.UI.ShowReload(true)
	else
		ns.UI.AddLine("|cffff5555No answer:|r " .. tostring(reason))
	end
end

-- Returns true when the question went out; false when it was refused (the reason is shown).
function Request.Send(kind, text)
	ns.UI.Ensure()
	if waiting then
		ns.UI.AddLine("|cff888888Still working on the last one...|r")
		return false
	end
	if ns.InCombat() and kind ~= "selftest" then
		ns.UI.AddLine("|cff888888Gnomecaster pauses in combat. Ask again when combat ends.|r")
		return false
	end
	ns.Inbox.SkipLoaded()
	if ns.Inbox.Remaining() <= 0 then
		onFail("exhausted")
		return false
	end
	rid = rid + 1
	local thisRid = rid
	local json = Request.BuildPacket(kind, text)
	if not json then
		ns.UI.AddLine("|cffff5555That request is too long.|r")
		return false
	end
	if kind == "ask" then ns.UI.AddLine("|cffaaaaaaYou:|r " .. ns.Escape(text)) end

	-- what the game looked like when the question was asked, for checking the answer later
	local hasTarget = UnitExists("target") and true or false
	local request = { hasTarget = hasTarget, targetName = hasTarget and ns.Plain(UnitName("target")) or nil,
		targetGuid = hasTarget and ns.Plain(UnitGUID("target")) or nil }
	waiting = true
	ns.Inbox.PreCheck()
	local status = startStatus("sending")

	local ok, err = ns.Beacon.Send(json, function(captured)
		if not captured then
			onFail("the game didn't take the screenshot")
			return
		end
		if kind == "ask" then ns.Actions.ClearResults() end
		if kind == "ping" then
			waiting = false
			stopStatus()
			ns.UI.Reveal()
			ns.UI.AddLine(string.format("Ping sent (%d bytes). Check the companion window for the decoded request.", #json))
			return
		end
		status.stage = "waiting"
		ns.Inbox.Await(thisRid, function(msg, seconds, how, slot)
			onReply(msg, seconds, how, slot, request)
		end, onFail, function()
			status.stage = "thinking"
		end, function()
			status.stage = "silent"
			ns.UI.Reveal()
			ns.UI.AddLine("|cffffaa00The companion hasn't picked up your question yet. Is the Gnomecaster "
				.. "app running on your PC?|r Still waiting for an answer.")
		end)
	end)
	if not ok then onFail(err) end
	return true
end
