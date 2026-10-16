-- Minimal JSON encoder (WoW has no JSON library). Secret values become null.
local _, ns = ...

local Json = {}
ns.Json = Json

local format, byte, gsub, concat, sort = string.format, string.byte, string.gsub, table.concat, table.sort
local floor, huge = math.floor, math.huge

local escapes = {
	['"'] = '\\"', ['\\'] = '\\\\', ['\b'] = '\\b', ['\f'] = '\\f',
	['\n'] = '\\n', ['\r'] = '\\r', ['\t'] = '\\t',
}

local function escapeChar(c)
	return escapes[c] or format("\\u%04x", byte(c))
end

local encode

local function encodeString(s)
	return '"' .. gsub(s, '[%c"\\]', escapeChar) .. '"'
end

local function encodeNumber(n)
	if n ~= n or n == huge or n == -huge then return "null" end
	if n == floor(n) and n > -1e15 and n < 1e15 then
		return format("%d", n)
	end
	return format("%.6g", n)
end

local function isArray(t)
	local n = #t
	if n == 0 then return false end
	for k in pairs(t) do
		if type(k) ~= "number" or k < 1 or k > n or k ~= floor(k) then return false end
	end
	return true
end

encode = function(v, depth)
	if ns.IsSecret(v) then return "null" end
	local tv = type(v)
	if tv == "string" then return encodeString(v) end
	if tv == "number" then return encodeNumber(v) end
	if tv == "boolean" then return v and "true" or "false" end
	if tv ~= "table" or depth > 8 then return "null" end
	local out = {}
	if isArray(v) then
		for i = 1, #v do out[i] = encode(v[i], depth + 1) end
		return "[" .. concat(out, ",") .. "]"
	end
	local keys = {}
	for k in pairs(v) do
		local tk = type(k)
		if (tk == "string" or tk == "number") and not ns.IsSecret(k) then keys[#keys + 1] = tostring(k) end
	end
	sort(keys)
	for _, k in ipairs(keys) do
		local val = v[k]
		if val == nil then val = v[tonumber(k)] end
		if val ~= nil then
			out[#out + 1] = encodeString(k) .. ":" .. encode(val, depth + 1)
		end
	end
	return "{" .. concat(out, ",") .. "}"
end

function Json.Encode(v)
	return encode(v, 0)
end
