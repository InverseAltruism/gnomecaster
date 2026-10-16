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

local ns = M.LoadAddon(addonsDir .. "/Gnomecaster")
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
	SlashCmdList.GNOMECASTER(text)
	M.Advance(wait or 12, 0.05)
end

local statuses = {}
local setStatus = ns.UI.SetStatus
ns.UI.SetStatus = function(text) statuses[#statuses + 1] = text; return setStatus(text) end
local function sawStatus(pattern)
	for _, s in ipairs(statuses) do if tostring(s):find(pattern) then return true end end
	return false
end

if scenario == "macro" or scenario == "noevents" or scenario == "noprobe" or scenario == "jpeg" or scenario == "scaled" or scenario == "fontcache" then
	M.RaiseError("Interface/AddOns/Foo/Foo.lua:12: attempt to index a nil value")
	ask("macro for rejuvenation on slot 5 bind to shift-e")
	check(M.companionOk, "companion decoded the screenshot and wrote a reply")
	check(has("Screenshot"), "addon took a screenshot")
	check(M.cvars.screenshotFormat == "jpeg", "screenshot format restored afterwards")
	check(not _G.GnomecasterBeacon.shown, "beacon hidden again")
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
	if scenario == "macro" then
		check(rt:find("ready%-signal"), "ready signal delivered without spending extra slots")
		check(sawStatus("^thinking"), "the companion's acknowledgement turns the status to thinking")
		-- signals are known to work now; with the companion gone, say so within seconds, not after 60
		M.onScreenshot = function() C_Timer.After(0.05, function() M.Fire("SCREENSHOT_SUCCEEDED") end) end
		M.chat = {}
		SlashCmdList.GNOMECASTER("where am i")
		M.Advance(8, 0.05)
		local early, failed = false, false
		for _, l in ipairs(M.chat) do
			if tostring(l):find("hasn't picked up your question yet") then early = true end
			if tostring(l):find("No answer") then failed = true end
		end
		check(early and not failed, "a silent companion is reported after the grace period, and the question keeps waiting")
		M.Advance(56, 0.25)
		failed = false
		for _, l in ipairs(M.chat) do if tostring(l):find("No answer") then failed = true end end
		check(failed, "with no companion at all, the question ends after 60 seconds as before")
	end
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

-- Actions on their own: what the addon accepts from a model, with no screenshot round trip.
if scenario == "actions" then
	local confirm
	ns.UI.ShowConfirm = function(text) confirm = text end
	local function handle(list, request)
		M.chat, M.calls, confirm = {}, {}, nil
		ns.Actions.Handle(list, request)
	end
	local function said(pattern)
		for _, l in ipairs(M.chat) do if tostring(l):find(pattern) then return true end end
		return false
	end
	local function macro(body) return { { type = "macro", name = "Test", body = body } } end

	handle(macro("#showtooltip\n/run DeleteCursorItem()"))
	check(confirm == nil and said("skipped macro: uses /run"), "a macro with /run is refused, with the reason")
	handle(macro("#showtooltip\n/cast Rejuvenation\nHello everyone"))
	check(confirm == nil and said("say in chat"), "a macro line that WoW would say in chat is refused")
	handle(macro("#showtooltip\n/cast |cff00ff00Rejuvenation|r"))
	check(confirm == nil and said("escape sequence"), "a macro with | codes is refused")
	handle(macro("#showtooltip\n/CAST [@mouseover,help,nodead][] Rejuvenation"))
	check(confirm ~= nil and confirm:find("Create macro"), "a normal macro waits for Apply (commands in any case)")

	handle({ { type = "waypoint", map = 2395, x = 0.5, y = 63.1 } })
	check(not has("SetUserWaypoint") and said("mixes two coordinate scales"), "mixed coordinate scales are refused")
	handle({ { type = "waypoint", map = 2395, x = 45.2, y = 63.1 } })
	local wp = has("SetUserWaypoint")
	check(wp and math.abs(wp.args[2] - 0.452) < 1e-9 and math.abs(wp.args[3] - 0.631) < 1e-9, "map percentages are converted")
	handle({ { type = "bar", macro = "Test", slot = 5.5 }, { type = "mark", icon = 2.5 } })
	check(confirm == nil and not has("SetRaidTarget") and said("skipped bar") and said("skipped mark"), "non-integer slots and icons are refused")
	handle({ { type = "setting", name = "graphicsQuality", value = "10" } })
	check(confirm == nil and said("only certain game settings"), "settings outside the allowlist are refused")

	-- retail allows 30 character macros (Constants.MacroConsts); the old fallback assumed 18
	M.macros = {}
	for i = 1, 20 do M.macros[i] = { name = "C" .. i, body = "/cast X", perChar = true } end
	ns.Actions.Apply({ { type = "macro", name = "Char21", body = "#showtooltip\n/cast Regrowth", char = true } })
	check(has("CreateMacro", "Char21"), "a 21st character macro is created (retail limit is 30)")

	-- fallbacks when the long-standing helpers are missing
	local saved = { GetMacroIndexByName, SetBindingMacro }
	GetMacroIndexByName, SetBindingMacro = nil, nil
	M.calls = {}
	ns.Actions.Apply({ { type = "macro", name = "C3", body = "#showtooltip\n/cast Lifebloom" },
		{ type = "bind", key = "F5", macro = "C3" } })
	check(has("EditMacro", 120 + 3), "without GetMacroIndexByName an existing character macro is found via GetMacroInfo")
	check(has("SetBinding", "F5", "MACRO C3"), "without SetBindingMacro the binding goes through SetBinding")
	GetMacroIndexByName, SetBindingMacro = saved[1], saved[2]

	-- a binding that replaces an existing one asks even with auto-apply
	ns.db.autoApply = true
	handle({ { type = "bind", key = "SHIFT-E", macro = "C3" } })
	check(confirm ~= nil and confirm:find("replaces MOVEANDSTEER") and not has("SetBindingMacro"), "replacing a binding asks even with auto-apply")
	handle({ { type = "bind", key = "F6", macro = "C3" } })
	check(confirm == nil and has("SetBindingMacro", "F6", "C3"), "a free key is bound at once with auto-apply")
	ns.db.autoApply = false

	-- a mark waits for confirmation when the target changed while the model was thinking
	local asked = { hasTarget = true, targetName = "Training Dummy", targetGuid = M.targetGuid }
	handle({ { type = "mark", icon = 8 } }, asked)
	check(has("SetRaidTarget", "target", 8) and not confirm, "a mark on the same target runs at once")
	handle({ { type = "mark", icon = 8 } }, { hasTarget = true, targetName = "Training Dummy", targetGuid = "Creature-0-1-2-3-31146-0000000002" })
	check(not has("SetRaidTarget") and confirm and confirm:find("your target changed"), "another unit with the same name counts as a changed target")
	handle({ { type = "mark", icon = 8 } }, { hasTarget = false })
	check(not has("SetRaidTarget") and confirm, "a target picked after asking counts as a changed target")
	-- fields the model sends that the addon uses internally are ignored
	handle({ { type = "waypoint", map = 2395, x = 0.4, y = 0.5, targetChanged = true },
		{ type = "setting", name = "autoLootDefault", value = "1" } })
	check(has("SetUserWaypoint") and confirm and confirm:find("autoLootDefault"), "a model-supplied targetChanged flag changes nothing")

	-- model text is shown literally
	handle({ { type = "waypoint", map = 2395, x = 0.4, y = 0.5, title = "|TInterface\\Icons\\X:0|t Spoof" } })
	check(said("||TInterface"), "model text cannot inject textures or colours into the panel")
end

-- The panel: opening, closing, input handling and what it keeps across reloads.
if scenario == "ui" then
	M.onScreenshot = nil        -- no companion: these checks never need a reply
	local UI = ns.UI
	local panel = _G.GnomecasterPanel
	UI.Toggle(true)
	panel = _G.GnomecasterPanel
	M.Advance(0.1)
	local input
	for _, f in ipairs(M.frames) do if f.kind == "EditBox" and f.parent == panel then input = f end end
	check(panel.shown and input.focus, "the key binding opens the panel and focuses the input")
	UI.Toggle(true)
	check(not panel.shown, "pressing it again while typing closes the panel")
	UI.Toggle(true)
	M.Advance(0.1)

	M.combat = true
	input:SetText("macro for rejuvenation")
	input.scripts.OnEnterPressed(input)
	check(input:GetText() == "macro for rejuvenation" and not input.history, "a refused question stays in the box")
	M.combat = false
	input.scripts.OnEnterPressed(input)
	check(input:GetText() == "" and input.history and input.history[1] == "macro for rejuvenation", "a sent question leaves the box and joins the history")
	check(ns.db.history[1] == "macro for rejuvenation", "the history is saved for the next session")
	local busy
	for _, f in ipairs(M.frames) do if f.kind == "AnimationGroup" and f.looping == "BOUNCE" then busy = f end end
	check(busy and busy.playing, "the busy indicator pulses while a question is out")

	input.scripts.OnEnterPressed(input)
	check(input:GetText() == "" and not input.focus, "Enter on an empty box just leaves the box")
	local placeholder
	for _, f in ipairs(M.frames) do if f.kind == "FontString" and tostring(f.text):find("^Ask Gnomecaster") then placeholder = f end end
	check(placeholder and placeholder.shown, "the placeholder shows in an empty, unfocused box")

	UI.Hide()
	check(not panel.shown, "the close button hides the panel")
	UI.Reveal()
	check(panel.shown and not input.focus, "an arriving answer reveals the panel without stealing focus")
	UI.AddLine("an answer to keep")
	check(ns.db.log[#ns.db.log] == "an answer to keep", "the conversation is saved across reloads")

	-- if the game keeps loaded reply slots loaded across /reload, they are skipped, not wasted
	ns.Inbox.next = 1
	M.loaded["Gnomecaster_Inbox01"], M.loaded["Gnomecaster_Inbox02"], M.loaded["Gnomecaster_Inbox03"] = true, true, true
	M.chat = {}
	SlashCmdList.GNOMECASTER("status")
	local status
	for _, l in ipairs(M.chat) do if tostring(l):find("next slot") then status = l end end
	check(ns.Inbox.next == 4 and status and status:find("next slot 4"), "slots already loaded are skipped, and /gc status shows it")
end

-- A real model through the whole pipeline (not in run_all.sh: needs GNOMECASTER_* settings
-- and spends money). Prints what the panel shows; checks only that every answer arrived.
if scenario == "live" then
	M.RaiseError("Interface/AddOns/Foo/Foo.lua:12: attempt to index a nil value")
	M.focusQuest = 91001
	local confirm
	ns.UI.ShowConfirm = function(text) confirm = text end
	for _, q in ipairs({ "test", "macro for rejuvenation on slot 5 bind to shift-e", "take me to my quest",
		"what was that error?", "max out my graphics settings" }) do
		confirm = nil
		ask(q)
		print("   >> " .. q)
		local answered = false
		for _, l in ipairs(M.chat) do
			local line = tostring(l):gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", ""):gsub("||", "|")
			if not line:find("^You:") then print("      panel: " .. line); answered = true end
		end
		if confirm then print("      confirm bar: " .. confirm:gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", ""):gsub("\n", " / ")) end
		check(answered and not tostring(M.chat[#M.chat]):find("No answer"), "answer arrived for: " .. q)
	end
end

print("scenario " .. scenario .. " done")
