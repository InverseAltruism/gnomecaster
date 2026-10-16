-- Inbound channel: the game only reads addon files when an addon loads.
-- Load-on-demand addons are read from disk the moment LoadAddOn is called,
-- so we ship NUM_SLOTS empty "inbox" addons. The companion writes each reply
-- into the inbox files, and we load the next unused slot to receive it.
-- Each slot can be loaded once per session; /reload resets them.
--
-- Ready signal (experimental): each slot has a ready.ttf that is empty until
-- the reply is written. EditBox:SetFont() reports whether a font file is
-- valid, so we can check readiness without spending a slot. If the client
-- caches font files this will not work, and we fall back to timed polling.
local _, ns = ...

local Inbox = {}
ns.Inbox = Inbox

Inbox.next = 1
Inbox.probeState = "unknown"   -- "unknown" until the ready signal delivers once, then "works"
local delivered

function GnomecasterInbox(msg)    -- called by the generated inbox.lua files
	delivered = msg or false
end

local function slotName(i)
	return string.format("Gnomecaster_Inbox%02d", i)
end
Inbox.SlotName = slotName

function Inbox.Remaining()
	return ns.NUM_SLOTS - Inbox.next + 1
end

-- Load the next slot. Returns msg (table, or false/nil if empty), slot, error.
function Inbox.LoadNext()
	local i = Inbox.next
	if i > ns.NUM_SLOTS then return nil, i, "exhausted" end
	Inbox.next = i + 1
	delivered = nil
	local ok, reason = ns.LoadAddOn(slotName(i))
	local msg = delivered
	delivered = nil
	if not ok then return nil, i, "could not load " .. slotName(i) .. " (" .. tostring(reason) .. ")" end
	return msg, i
end

local probeBox
function Inbox.Probe(i)
	if i > ns.NUM_SLOTS then return false end
	if not probeBox then
		probeBox = CreateFrame("EditBox", nil, UIParent)
		probeBox:SetAutoFocus(false)
		probeBox:Hide()
	end
	local path = "Interface\\AddOns\\" .. slotName(i) .. "\\ready.ttf"
	local ok, valid = pcall(probeBox.SetFont, probeBox, path, 12, "")
	return (ok and valid) and true or false
end

local ticker
local function stop()
	if ticker then ticker:Cancel(); ticker = nil end
end

-- Seconds after sending at which we try a slot blindly (each try spends one slot).
local BLIND = { 3, 6, 10, 15, 22, 32, 45, 60 }
local BLIND_WHEN_PROBE_WORKS = { 12, 22, 35, 50, 60 }

-- A slot's ready signal only counts when we saw it go from "not ready" to
-- "ready" while waiting. The companion clears the signals when it receives a
-- request, so a working signal always flips; a cached font never does, and
-- then timed polling takes over by itself.
local seenNotReady = {}

function Inbox.PreCheck()
	seenNotReady = {}
	if not Inbox.Probe(Inbox.next) then seenNotReady[Inbox.next] = true end
end

-- Wait for the reply to request `rid`.
-- onReply(msg, seconds, how, slot) / onFail(reason)
function Inbox.Await(rid, onReply, onFail)
	stop()
	local start = GetTime()
	local schedule = (Inbox.probeState == "works") and BLIND_WHEN_PROBE_WORKS or BLIND
	local blindIndex = 1

	ticker = C_Timer.NewTicker(0.25, function()
		local elapsed = GetTime() - start
		local how
		local i = Inbox.next
		if Inbox.Probe(i) then
			if seenNotReady[i] then how = "ready-signal" end
		else
			seenNotReady[i] = true
		end
		-- The companion clears the signal within a second of our screenshot. If it
		-- never read "not ready", the client is caching fonts: poll normally.
		if schedule ~= BLIND and elapsed >= 3 and not seenNotReady[i] then
			schedule, Inbox.probeState = BLIND, "unknown"
			blindIndex = 1
			while BLIND[blindIndex] and BLIND[blindIndex] < elapsed do blindIndex = blindIndex + 1 end
		end
		if not how and schedule[blindIndex] and elapsed >= schedule[blindIndex] then
			blindIndex = blindIndex + 1
			how = "timed poll"
		end
		if how then
			local msg, slot, err = Inbox.LoadNext()
			if err then
				stop()
				onFail(err)
				return
			end
			if type(msg) == "table" and msg.sid == ns.sessionId and msg.rid == rid then
				stop()
				if how == "ready-signal" then
					Inbox.probeState = "works"
				elseif Inbox.probeState == "works" then
					Inbox.probeState = "unknown"  -- signal missed this time; poll normally next time
				end
				onReply(msg, elapsed, how, slot)
				return
			end
			-- stale or empty slot: spent, keep waiting
		end
		if elapsed > 62 then
			stop()
			onFail("no reply after 60 seconds - is the companion app running?")
		end
	end)
end

function Inbox.Cancel()
	stop()
end

-- /gc poll : load the next slot and show what is in it (pair with `companion write-test`)
function Inbox.DebugPoll()
	local msg, slot, err = Inbox.LoadNext()
	if err then ns.Print("poll: " .. err) return end
	if type(msg) == "table" then
		ns.Print(string.format("poll: slot %d delivered: %s", slot, tostring(msg.say)))
		if msg.written then ns.Print("  written by companion at " .. tostring(msg.written)) end
	else
		ns.Print(string.format("poll: slot %d was empty (no test message written yet?)", slot))
	end
end

function Inbox.DebugProbe()
	local i = Inbox.next
	ns.Print(string.format("probe: slot %d ready-signal = %s (state: %s)", i, tostring(Inbox.Probe(i)), Inbox.probeState))
end

function Inbox.DebugStatus()
	ns.Print(string.format("session %s, next slot %d, %d slots left, ready-signal: %s",
		ns.sessionId, Inbox.next, Inbox.Remaining(), Inbox.probeState))
end
