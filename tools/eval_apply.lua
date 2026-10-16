-- Runs companion replies through the addon's Actions code (mocked WoW API) for
-- tools/eval_models.py and prints one JSON line per reply.
-- usage: lua5.1 eval_apply.lua <repo> <replies.lua>
local repo, file = arg[1], arg[2]
local M = dofile(repo .. "/tests/wowmock.lua")
M.addonsDir = repo .. "/addon"
local ns = M.LoadAddon(repo .. "/addon/Gnomecaster")
ns.db.autoApply = false

local lines, confirm
ns.UI.AddLine = function(text) lines[#lines + 1] = tostring(text) end
ns.UI.ShowConfirm = function(text) confirm = text end

local replies = dofile(file)
for i = 1, replies.n do
	lines, confirm, M.calls = {}, nil, {}
	local reply = replies[i]
	if type(reply) == "table" then
		local ok, err = pcall(ns.Actions.Handle, reply.actions)
		if not ok then lines[#lines + 1] = "(skipped lua_error: " .. tostring(err) .. ")" end
	end
	local skipped, calls = {}, {}
	for _, l in ipairs(lines) do
		local kind = l:match("%(skipped ([%w_]+):")
		if kind then skipped[#skipped + 1] = kind end
	end
	for _, c in ipairs(M.calls) do calls[#calls + 1] = c.name end
	print(ns.Json.Encode({ i = i, skipped = skipped, confirm = confirm or "", lines = lines, calls = calls }))
end
