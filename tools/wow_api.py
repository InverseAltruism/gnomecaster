#!/usr/bin/env python3
"""Check the addon's WoW API use against Blizzard's own UI source.

Nothing here can run the game client, so this is how the addon's calls are verified.
Two sources, both from the game's UI code mirrored at github.com/Gethe/wow-ui-source and
pinned to one commit:
  - the generated API documentation (Blizzard_APIDocumentationGenerated): every widget
    method, namespaced function, documented global and event of the C API;
  - the Lua UI code itself: a global that Blizzard's UI calls exists in that build, and a
    method that a FrameXML mixin defines exists on frames using that mixin.

  python3 tools/wow_api.py check          scan addon/Gnomecaster; exit 1 on unverified calls
  python3 tools/wow_api.py mock-methods   regenerate tests/wow_api_methods.lua for the mock

Needs LUA=<lua5.1 interpreter> and git. The documentation files are Lua tables, loaded in
an empty environment so they cannot reach os or io. Downloads are cached under
~/.cache/gnomecaster.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.request

# Game build 12.1.5.70391 (Retail), mirrored 2026-10-13.
COMMIT = "18c6d677b605b312f3d813d498404631fb941977"
REPO = "Gethe/wow-ui-source"
DOC_DIR = "Interface/AddOns/Blizzard_APIDocumentationGenerated"
ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE_ROOT = pathlib.Path(os.environ.get("XDG_CACHE_HOME", pathlib.Path.home() / ".cache")) / "gnomecaster"
DOCS = CACHE_ROOT / "wow-api" / COMMIT
SOURCE = CACHE_ROOT / "wow-ui-source"

LUA_STRING_METHODS = {"byte", "char", "find", "format", "gmatch", "gsub", "len", "lower", "match",
                      "rep", "reverse", "sub", "upper"}
LUA_GLOBALS = {"assert", "error", "ipairs", "next", "pairs", "pcall", "print", "rawequal", "rawget",
               "rawset", "select", "setmetatable", "getmetatable", "tonumber", "tostring", "type",
               "unpack", "xpcall", "time", "date"}
# Mixins whose methods the addon uses: through templates or intrinsic frame types (widgets),
# or on objects the API returns (C_Map.GetPlayerMapPosition returns a Vector2D).
WIDGET_MIXINS = {"BackdropTemplateMixin", "ScrollingMessageFrameMixin"}
MIXINS_USED = WIDGET_MIXINS | {"Vector2DMixin"}
# Calls that cannot be verified against the retail source, each guarded in the addon.
KNOWN_UNVERIFIED = {
    "AddWaypoint": "TomTom (optional third-party addon); called only when TomTom.AddWaypoint exists",
    "GetQuestLogTitle": "Classic quest log; called only when C_QuestLog.GetInfo is missing",
    "GetMacroIndexByName": "long-standing macro API; used when present, else a GetMacroInfo scan",
    "SetBindingMacro": "long-standing binding API; used when present, else SetBinding(key, \"MACRO name\")",
}

DOC_LOADER = r"""
local dir = arg[1]
local collected = {}
local proxy
proxy = setmetatable({}, { __index = function() return proxy end, __call = function() return proxy end })
local env = setmetatable({ APIDocumentation = { AddDocumentationTable = function(_, t) collected[#collected + 1] = t end } },
	{ __index = function() return proxy end })
for name in io.lines(dir .. "/files.txt") do
	local chunk = loadfile(dir .. "/" .. name)
	if chunk then setfenv(chunk, env); pcall(chunk) end
end
for _, t in ipairs(collected) do
	local ns = type(t.Namespace) == "string" and t.Namespace or ""
	print(table.concat({ "DOC", tostring(t.Name), tostring(t.Type), ns }, "\t"))
	for _, f in ipairs(type(t.Functions) == "table" and t.Functions or {}) do
		if type(f.Name) == "string" then print(table.concat({ "FN", tostring(t.Name), tostring(t.Type), ns, f.Name }, "\t")) end
	end
	for _, e in ipairs(type(t.Events) == "table" and t.Events or {}) do
		if type(e.LiteralName) == "string" then print("EV\t" .. e.LiteralName) end
	end
end
"""


def fetch_docs() -> pathlib.Path:
    if (DOCS / "files.txt").exists():
        return DOCS
    DOCS.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(f"https://api.github.com/repos/{REPO}/git/trees/{COMMIT}?recursive=1", timeout=60) as r:
        tree = json.load(r)
    names = sorted(p["path"].rsplit("/", 1)[1] for p in tree["tree"]
                   if p["path"].startswith(DOC_DIR + "/") and p["path"].endswith(".lua"))

    def get(name):
        with urllib.request.urlopen(f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/{DOC_DIR}/{name}", timeout=60) as r:
            (DOCS / name).write_bytes(r.read())

    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(get, names))
    (DOCS / "files.txt").write_text("\n".join(names) + "\n")
    return DOCS


def fetch_source() -> pathlib.Path:
    """Sparse checkout of the UI's Lua files at COMMIT (about 45 MB)."""
    if not (SOURCE / ".git").exists():
        subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout",
                        f"https://github.com/{REPO}.git", str(SOURCE)], check=True)
        subprocess.run(["git", "-C", str(SOURCE), "sparse-checkout", "set", "--no-cone", "/Interface/AddOns/**/*.lua"], check=True)
    head = subprocess.run(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != COMMIT:
        subprocess.run(["git", "-C", str(SOURCE), "checkout", "-q", COMMIT], check=True)
    return SOURCE


def build_index() -> dict:
    index_file = DOCS / "index-v3.json"
    if index_file.exists():
        return json.loads(index_file.read_text())
    lua = os.environ.get("LUA") or sys.exit("set LUA to a Lua 5.1 interpreter")
    docs = fetch_docs()
    (docs / "loader.lua").write_text(DOC_LOADER)
    out = subprocess.run([lua, str(docs / "loader.lua"), str(docs)], capture_output=True, text=True, check=True).stdout
    methods, namespaces, documented, events, ndocs = set(), {}, set(), set(), 0
    for line in out.splitlines():
        parts = line.split("\t")
        if parts[0] == "DOC":
            ndocs += 1
        elif parts[0] == "FN":
            _, _doc, kind, ns, fn = parts
            if kind == "ScriptObject":
                methods.add(fn)
            elif ns:
                namespaces.setdefault(ns, set()).add(fn)
            else:
                documented.add(fn)
        elif parts[0] == "EV":
            events.add(parts[1])
    src = fetch_source() / "Interface" / "AddOns"
    called, mixin_methods = set(), {}
    for path in src.rglob("*.lua"):
        text = path.read_text(encoding="utf-8", errors="replace")
        called.update(re.findall(r"(?<![\w.:])([A-Za-z_]\w*)\s*\(", text))
        for mixin, method in re.findall(r"^function\s+(\w+Mixin):(\w+)\s*\(", text, re.M):
            mixin_methods.setdefault(mixin, set()).add(method)
    result = {"commit": COMMIT, "docs": ndocs, "methods": sorted(methods),
              "namespaces": {k: sorted(v) for k, v in sorted(namespaces.items())},
              "documented_globals": sorted(documented), "events": sorted(events),
              "called_by_blizzard": sorted(called),
              "mixin_methods": {k: sorted(v) for k, v in sorted(mixin_methods.items()) if k in MIXINS_USED}}
    index_file.write_text(json.dumps(result, indent=1))
    return result


def strip_lua(src: str) -> str:
    """Removes comments and string literals so only code is scanned."""
    src = re.sub(r"--\[\[.*?\]\]", "", src, flags=re.S)
    src = re.sub(r"--[^\n]*", "", src)
    return re.sub(r'"(\\.|[^"\\])*"|\'(\\.|[^\'\\])*\'', '""', src)


def addon_files():
    return sorted((ROOT / "addon" / "Gnomecaster").glob("*.lua"))


def check(index) -> int:
    files = addon_files()
    widget_methods = set(index["methods"]).union(*map(set, index["mixin_methods"].values()))
    globals_ok = set(index["documented_globals"]) | set(index["called_by_blizzard"]) | LUA_GLOBALS
    own, calls = set(), []
    for path in files:
        code = strip_lua(path.read_text(encoding="utf-8"))
        own.update(re.findall(r"\bfunction\s+(?:[\w.]+[.:])?(\w+)\s*\(", code))
        own.update(re.findall(r"\blocal\s+function\s+(\w+)", code))
        for names in re.findall(r"\blocal\s+(\w+(?:\s*,\s*\w+)*)", code):
            own.update(n.strip() for n in names.split(","))
        for params in re.findall(r"\bfunction\b[\w.:\s]*\(([^)]*)\)", code):
            own.update(n.strip() for n in params.split(",") if n.strip() and n.strip() != "...")
        for i, line in enumerate(code.splitlines(), 1):
            for m in re.finditer(r":(\w+)\s*\(", line):
                calls.append((path, i, "method", m.group(1)))
            for m in re.finditer(r"\b(C_\w+)\.(\w+)", line):
                calls.append((path, i, "namespace", f"{m.group(1)}.{m.group(2)}"))
            for m in re.finditer(r"(?<![\w.:])([A-Za-z]\w*)\s*\(", line):
                if m.group(1) not in ("function", "if", "elseif", "while", "until", "return", "and", "or", "not", "local"):
                    calls.append((path, i, "global", m.group(1)))
    errors, warnings = [], {}
    for path, line, kind, name in calls:
        where = f"{path.relative_to(ROOT)}:{line}"
        if kind == "method":
            if name in widget_methods or name in LUA_STRING_METHODS or name in own:
                continue
            if name in KNOWN_UNVERIFIED:
                warnings.setdefault(name, KNOWN_UNVERIFIED[name])
            else:
                errors.append(f"{where}: :{name}() is neither documented nor defined by {sorted(MIXINS_USED)}")
        elif kind == "namespace":
            ns, fn = name.split(".")
            if fn not in index["namespaces"].get(ns, []):
                errors.append(f"{where}: {name} is not documented")
        elif kind == "global" and name not in globals_ok and name not in own and not name.startswith("C_"):
            if name in KNOWN_UNVERIFIED:
                warnings.setdefault(name, KNOWN_UNVERIFIED[name])
            else:
                errors.append(f"{where}: {name}() is neither documented nor called anywhere in Blizzard's UI")
    events = set(re.findall(r'(?:RegisterEvent|tryRegister)\s*\(\s*(?:\w+\s*,\s*)?"([A-Z_]+)"',
                            "\n".join(p.read_text(encoding="utf-8") for p in files)))
    errors += [f"event {e} is not documented" for e in sorted(events - set(index["events"]))]
    print(f"Blizzard UI at {COMMIT[:12]}: {index['docs']} API documents ({len(index['methods'])} widget methods, "
          f"{sum(map(len, index['namespaces'].values()))} namespaced functions, {len(index['events'])} events) "
          f"and {len(index['called_by_blizzard'])} globals called by its Lua")
    print(f"addon: {len(calls)} calls in {len(files)} files, {len(events)} events registered")
    for e in errors:
        print("  UNVERIFIED", e)
    for name, why in sorted(warnings.items()):
        print(f"  known, guarded: {name}: {why}")
    print("OK: every call is documented or used by Blizzard's UI" if not errors else f"{len(errors)} unverified calls")
    return 1 if errors else 0


def mock_methods(index) -> None:
    out = ROOT / "tests" / "wow_api_methods.lua"
    names = sorted(set(index["methods"]).union(*(set(v) for k, v in index["mixin_methods"].items() if k in WIDGET_MIXINS)))
    body = ",\n".join(f'\t["{n}"] = true' for n in names)
    out.write_text(f"-- Generated by tools/wow_api.py from Blizzard's UI source at {COMMIT[:12]}: the documented\n"
                   f"-- widget methods plus those of {', '.join(sorted(WIDGET_MIXINS))}. The mock rejects any other.\n"
                   f"return {{\n{body},\n}}\n")
    print(f"wrote {out.relative_to(ROOT)} ({len(names)} methods)")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    index = build_index()
    if cmd == "check":
        sys.exit(check(index))
    elif cmd == "mock-methods":
        mock_methods(index)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
