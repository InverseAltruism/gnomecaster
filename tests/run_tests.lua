-- End-to-end tests: real addon code + mocked WoW API + real companion code.
-- usage: lua51 run_tests.lua <scenario> <addonsDir> <workDir>
local scenario, addonsDir, work = arg[1], arg[2], arg[3]
local M = dofile(work .. "/wowmock.lua")
M.addonsDir = addonsDir
math.randomseed(42)

local probe = (scenario ~= "noprobe" and scenario ~= "fontcache") and "1" or "0"
if scenario == "noevents" then M.noScreenshotEvents = true end
if scenario == "fontcache" then M.cacheFonts = true; probe = "1" end
local jpeg = scenario == "jpeg" and "92" or "-"
local scale = scenario == "scaled" and "1.25" or "1.0"
local shotN = 0

M.onScreenshot = function()
	shotN = shotN + 1
	local dump = work .. "/beacon_" .. scenario .. shotN .. ".txt"
	local png = work .. "/WoWScrnShot_" .. scenario .. shotN .. (jpeg ~= "-" and ".jpg" or ".png")
	M.DumpBeacon(dump)
	assert(os.execute(string.format("python3 %s/render.py %s %s %s %s", work, dump, png, jpeg, scale)) == 0, "render failed")
	C_Timer.After(0.05, function() M.Fire("SCREENSHOT_SUCCEEDED") end)
	-- companion notices the file, decodes it and clears ready signals...
	C_Timer.After(0.5, function()
		M.companionOk = os.execute(string.format("python3 %s/driver.py receive %s %s %s", work, png, addonsDir, probe)) == 0
	end)
	-- ...and the "model" answers a bit later
	C_Timer.After(M.answerDelay or 1.6, function()
		os.execute(string.format("python3 %s/driver.py deliver %s %s %s", work, png, addonsDir, probe))
	end)
end

local ns = M.LoadAddon(addonsDir .. "/Wowpilot")
local function has(name, a1, a2, a3)
	for _, c in ipairs(M.calls) do
		if c.name == name and (a1 == nil or c.args[1] == a1) and (a2 == nil or c.args[2] == a2) and (a3 == nil or c.args[3] == a3) then return c end
	end
end
local function chatDump() for _, l in ipairs(M.chat) do print("   | " .. tostring(l)) end end
local function check(cond, label)
	print((cond and "PASS " or "FAIL ") .. label)
	if not cond then chatDump(); os.exit(1) end
end

local function ask(text, wait)
	M.chat = {}
	SlashCmdList.WOWPILOT(text)
	M.Advance(wait or 12, 0.05)
end

if scenario == "macro" or scenario == "noevents" or scenario == "noprobe" or scenario == "jpeg" or scenario == "scaled" or scenario == "fontcache" then
	M.RaiseError("Interface/AddOns/Foo/Foo.lua:12: attempt to index a nil value")
	ask("macro for rejuvenation on slot 5 bind to shift-e")
	check(M.companionOk, "companion decoded the screenshot and wrote a reply")
	check(has("Screenshot"), "addon took a screenshot")
	check(M.cvars.screenshotFormat == "jpeg", "screenshot format restored afterwards")
	check(not _G.WowpilotBeacon.shown, "beacon hidden again")
	check(has("LoadAddOn"), "reply slot loaded")
	local pending = false
	for _, l in ipairs(M.chat) do if tostring(l):find("mouseover help macro") then pending = true end end
	check(pending, "answer text shown in panel")
	check(not has("CreateMacro"), "nothing changed before confirming")
	ns.Actions.Apply()
	local cm = has("CreateMacro", "Rejuvenation")
	check(cm ~= nil, "macro created after Apply")
	check(cm and cm.args[3] == "#showtooltip\n/cast [@mouseover,help,nodead][@target,help,nodead][@player] Rejuvenation", "macro body correct")
	check(has("PlaceAction", 5), "macro placed on action slot 5")
	check(has("SetBindingMacro", "SHIFT-E", "Rejuvenation"), "SHIFT-E bound to the macro")
	local loads = 0
	for _, c in ipairs(M.calls) do if c.name == "LoadAddOn" then loads = loads + 1 end end
	print(string.format("     slots used: %d, ready-signal state: %s", loads, ns.Inbox.probeState))
	-- decoded request contained the context and the recorded error
	local f = assert(io.open(work .. "/WoWScrnShot_" .. scenario .. "1" .. (jpeg ~= "-" and ".jpg" or ".png") .. ".json"))
	local decoded = f:read("*a"); f:close()
	check(decoded:find("Restoration", 1, true) and decoded:find("attempt to index a nil value", 1, true) and decoded:find("The Sunwell", 1, true), "request carried spec, quest log and the Lua error")

	-- second request in the same session
	M.calls = {}
	M.focusQuest = 91001
	ask("take me to my quest")
	local wp = has("SetUserWaypoint", 2395)
	check(wp and math.abs(wp.args[2] - 0.3812) < 1e-6 and math.abs(wp.args[3] - 0.5521) < 1e-6, "quest arrow set to the game's next waypoint")
	check(has("SetSuperTrackedUserWaypoint", true), "navigation arrow switched on")
	print(string.format("     next free slot: %d, ready-signal state: %s", ns.Inbox.next, ns.Inbox.probeState))
	for _, l in ipairs(M.chat) do if tostring(l):find("Round trip") then print("     " .. l) end end

	-- third request: built-in self test, reports how the reply arrived
	M.calls = {}
	ask("test")
	local rt
	for _, l in ipairs(M.chat) do if tostring(l):find("Round trip OK") then rt = l end end
	check(rt ~= nil, "self test round trip")
	print("     " .. tostring(rt))
	if scenario == "macro" then check(rt:find("ready%-signal"), "ready signal delivered without spending extra slots") end
	if scenario == "noprobe" or scenario == "fontcache" then check(rt:find("timed poll"), "fell back to timed polling") end
end

if scenario == "secret" then
	M.targetName = M.SECRET
	ask("where am i")
	check(M.companionOk, "request with a secret target name still decodes")
	local f = assert(io.open(work .. "/WoWScrnShot_secret1.png.json")); local decoded = f:read("*a"); f:close()
	check(not decoded:find("secret", 1, true) and not decoded:find("Training", 1, true), "secret value left out of the request")
	local said = false
	for _, l in ipairs(M.chat) do if tostring(l):find("Silvermoon City") then said = true end end
	check(said, "answer arrived")
end

if scenario == "combat" then
	M.combat = true
	ask("macro for rejuvenation")
	check(not has("Screenshot"), "no request sent in combat")
end

print("scenario " .. scenario .. " done")
