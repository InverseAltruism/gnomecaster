#!/usr/bin/env python3
"""
Wowpilot companion (prototype)

Reads requests that the Wowpilot addon draws into screenshots, asks an AI
model (or an offline demo brain), and writes the reply into the addon's
load-on-demand reply slots. It never touches the game process: it only reads
screenshot files the game writes and writes files inside the AddOns folder.

Commands
  install     copy the addon into the game:      --wow "<WoW folder or _retail_ folder>"
  run         keep running while you play:       --wow "..."
  write-test  write a test reply (for /wp poll): --wow "..." [--slot N]
  decode      decode one screenshot (debugging): decode path/to/WoWScrnShot.png

AI model (optional; any OpenAI-compatible endpoint)
  WOWPILOT_BASE_URL   https://openrouter.ai/api/v1 | https://api.openai.com/v1 |
                      http://localhost:11434/v1 (Ollama) | ...
  WOWPILOT_API_KEY    your key (not needed for a local model)
  WOWPILOT_MODEL      model name at that endpoint
Without these, an offline demo brain answers a few fixed request types.

Requires Python 3.9+ and Pillow:  pip install pillow
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
import zlib

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("Pillow is missing. Install it with:  pip install pillow")

GRID_W = 96
NUM_SLOTS = 60
PROTOCOL = 1
MARKER = [5, 5, 3, 3, 6, 6, 5, 5]   # colour index = r*4 + g*2 + b
HEADER_LEN = 9                      # "WP", version, length(2), adler32(4)
PROBE_AHEAD = 6                     # how many slots get a ready-signal font
PROBE_LIFETIME = 8.0                # seconds before ready-signals are cleared again
MIN_NOT_READY = 0.75                # keep signals "not ready" at least this long per request
SCREENSHOT_EXT = {".png", ".jpg", ".jpeg", ".tga"}
ADDON_DIR = pathlib.Path(__file__).resolve().parent.parent / "addon"

# --------------------------------------------------------------------------
# Screenshot decoding
# --------------------------------------------------------------------------

def _cls(p) -> int:
    return (4 if p[0] >= 128 else 0) | (2 if p[1] >= 128 else 0) | (1 if p[2] >= 128 else 0)


def _marker_at(px, w, h, x, y, cell) -> bool:
    cy = int(y + cell / 2)
    if cy >= h:
        return False
    for i, want in enumerate(MARKER):
        cx = int(x + (i + 0.5) * cell)
        if cx >= w or _cls(px[cx, cy]) != want:
            return False
    return True


def find_markers(img, limit: int = 640):
    """Yield (x, y, cell_size) for each place that looks like a beacon's first row.
    A candidate needs the marker at both ends of row 0, so noise can't fake one."""
    w, h = img.size
    px = img.load()
    span = GRID_W - len(MARKER)
    for y in range(min(h, limit)):
        for x in range(min(w, limit)):
            if _cls(px[x, y]) != 5:
                continue
            if (x > 0 and _cls(px[x - 1, y]) == 5) or (y > 0 and _cls(px[x, y - 1]) == 5):
                continue
            run = 1
            while x + run < w and run < 64 and _cls(px[x + run, y]) == 5:
                run += 1
            if run < 2:
                continue
            # the run length is only accurate to about a pixel: try nearby cell sizes
            rough = None
            for k in range(-4, 5):
                c = run / 2.0 + k * 0.125
                if c >= 1 and _marker_at(px, w, h, x, y, c):
                    rough = c
                    break
            if rough is None:
                continue
            # the same marker ends row 0; the distance between the two gives the exact size
            cy = int(y + rough / 2)
            lo, hi = int(x + span * (rough - 0.6)), min(w - 1, int(x + span * (rough + 0.6)))
            for x2 in range(max(lo, x + 1), hi):
                if _cls(px[x2, cy]) == 5 and _cls(px[x2 - 1, cy]) != 5:
                    cell = (x2 - x) / span
                    if _marker_at(px, w, h, x2, y, cell):
                        yield x, y, cell
                        break


def find_marker(img, limit: int = 640):
    return next(find_markers(img, limit), None)


def _cells_to_bytes(cells, nbytes: int) -> bytes:
    bits = []
    for c in cells:
        bits.extend(((c >> 2) & 1, (c >> 1) & 1, c & 1))
    out = bytearray()
    for i in range(nbytes):
        v = 0
        for b in bits[i * 8:(i + 1) * 8]:
            v = (v << 1) | b
        out.append(v)
    return bytes(out)


def decode_image(path) -> dict | None:
    """Decode a Wowpilot request from a screenshot. None if there is no beacon."""
    with Image.open(path) as im:
        img = im.convert("RGB")
    px = img.load()
    w, h = img.size
    problem = None
    for x0, y0, cell in find_markers(img):
        try:
            packet = _decode_at(px, w, h, x0, y0, cell)
        except ValueError as e:
            problem = problem or e
            continue
        if packet is not None:
            return packet
    if problem:
        raise problem
    return None


def _decode_at(px, w, h, x0, y0, cell):
    def read(n):
        cells = []
        for i in range(n):
            r, c = 1 + i // GRID_W, i % GRID_W
            x, y = int(x0 + (c + 0.5) * cell), int(y0 + (r + 0.5) * cell)
            if x >= w or y >= h:
                raise ValueError("beacon is cut off at the screen edge")
            cells.append(_cls(px[x, y]))
        return cells

    head = _cells_to_bytes(read(-(-HEADER_LEN * 8 // 3)), HEADER_LEN)
    if head[:2] != b"WP":
        return None
    if head[2] != PROTOCOL:
        raise ValueError(f"addon speaks protocol {head[2]}, companion speaks {PROTOCOL}")
    length = head[3] * 256 + head[4]
    checksum = int.from_bytes(head[5:9], "big")
    total = HEADER_LEN + length
    data = _cells_to_bytes(read(-(-total * 8 // 3)), total)
    payload = data[HEADER_LEN:]
    if zlib.adler32(payload) != checksum:
        raise ValueError("checksum mismatch (screenshot scaled, filtered or JPEG-compressed?)")
    return json.loads(payload.decode("utf-8", errors="replace"))


# --------------------------------------------------------------------------
# Writing replies into the reply slots
# --------------------------------------------------------------------------

def lua_str(s: str) -> str:
    out = ['"']
    for b in s.encode("utf-8"):
        if b == 0x5C:
            out.append("\\\\")
        elif b == 0x22:
            out.append('\\"')
        elif b == 0x0A:
            out.append("\\n")
        elif 0x20 <= b < 0x7F:
            out.append(chr(b))
        else:
            out.append("\\%03d" % b)   # keeps the file plain ASCII
    out.append('"')
    return "".join(out)


def lua_value(v) -> str:
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v) if v == v and abs(v) != float("inf") else "0"
    if isinstance(v, str):
        return lua_str(v)
    if isinstance(v, (list, tuple)):
        return "{" + ",".join(lua_value(x) for x in v) + "}"
    if isinstance(v, dict):
        return "{" + ",".join(f"[{lua_str(str(k))}]={lua_value(x)}" for k, x in v.items() if x is not None) + "}"
    return "nil"


def atomic_write(path: pathlib.Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    for _ in range(40):            # the game may have the file open for a moment
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05)
    os.replace(tmp, path)


def find_probe_font(explicit: str | None) -> bytes | None:
    """Any small valid TrueType font works as the 'ready' signal."""
    candidates = []
    if explicit:
        candidates.append(pathlib.Path(explicit))
    windir = pathlib.Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    candidates += [windir / n for n in ("marlett.ttf", "wingding.ttf", "webdings.ttf", "arial.ttf")]
    candidates += [pathlib.Path(p) for p in (
        "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Geneva.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )]
    existing = [c for c in candidates if c.is_file()]
    if explicit and existing and existing[0] == pathlib.Path(explicit):
        return existing[0].read_bytes()
    if not existing:
        return None
    return min(existing, key=lambda c: c.stat().st_size).read_bytes()


class Slots:
    def __init__(self, addons_dir: pathlib.Path, font: bytes | None):
        self.addons = addons_dir
        self.font = font
        self.generation = 0
        self.lock = threading.Lock()

    def dir(self, n: int) -> pathlib.Path:
        return self.addons / f"Wowpilot_Inbox{n:02d}"

    def check(self) -> None:
        missing = [n for n in range(1, NUM_SLOTS + 1) if not self.dir(n).is_dir()]
        if missing:
            raise SystemExit(f"Reply slots missing in {self.addons} (e.g. {self.dir(missing[0]).name}). "
                             "Run the 'install' command first, then restart the game.")

    def clear_probes(self, start: int = 1) -> None:
        for n in range(max(1, start), NUM_SLOTS + 1):
            p = self.dir(n) / "ready.ttf"
            if p.exists() and p.stat().st_size:
                atomic_write(p, b"")

    def deliver(self, start: int, msg: dict, keep_probe: bool = False, not_before: float = 0.0) -> None:
        start = max(1, min(NUM_SLOTS, start))
        content = ("-- written by Wowpilot companion\nWowpilotInbox(" + lua_value(msg) + ")\n").encode("ascii")
        # The addon trusts a ready signal only after seeing it "not ready" first,
        # so keep the cleared state visible for a moment on very fast answers.
        if not_before:
            time.sleep(max(0.0, not_before - time.time()))
        with self.lock:
            self.generation += 1
            gen = self.generation
            for n in range(start, NUM_SLOTS + 1):
                atomic_write(self.dir(n) / "inbox.lua", content)
            if self.font:
                for n in range(start, min(NUM_SLOTS, start + PROBE_AHEAD - 1) + 1):
                    atomic_write(self.dir(n) / "ready.ttf", self.font)
        if self.font and not keep_probe:
            def expire():
                with self.lock:
                    if self.generation == gen:
                        self.clear_probes(start)
            t = threading.Timer(PROBE_LIFETIME, expire)
            t.daemon = True
            t.start()


# --------------------------------------------------------------------------
# The brain: an AI model, or an offline demo
# --------------------------------------------------------------------------

SYSTEM_PROMPT = """You are Wowpilot, a helper that lives inside World of Warcraft.
You receive GAME CONTEXT read live from the player's client and a request.

Reply with ONE JSON object only:
{"say": "<short plain-text answer, max ~600 characters>", "actions": [ ... ]}

Actions (include only what the player asked for; the addon asks them to confirm changes):
- {"type":"waypoint","map":<uiMapID>,"x":<0-1>,"y":<0-1>,"title":"<label>"}
- {"type":"track_quest","quest":<questID>}       (Blizzard's arrow follows that quest)
- {"type":"mark","icon":<1-8>,"unit":"target"}     (1 star 2 circle 3 diamond 4 triangle 5 moon 6 square 7 cross 8 skull)
- {"type":"macro","name":"<max 16 chars>","body":"<max 255 chars, lines separated by \\n>","char":false}
- {"type":"bar","macro":"<macro name>","slot":<1-180>}   (slots 1-12 are the main bar)
- {"type":"bind","key":"<e.g. SHIFT-E, CTRL-1, F5>","macro":"<macro name>"}
- {"type":"setting","name":"<console variable>","value":"<value>"}

Rules:
- Ground every fact in the GAME CONTEXT. ctx.focus.next is where the game itself says
  the followed quest's next step is. If something is not in the context (NPC locations,
  quest givers, drop sources, patch changes), say you can't look that up yet. Never
  invent coordinates, IDs or patch facts.
- ctx.game.project 1 = Retail (Midnight); other values are Classic flavors or WoW Forever.
  Spells, talents and rules differ per version.
- Macros: start with #showtooltip, keep under 255 characters, only use spells of the
  player's class/spec, prefer conditionals like [@mouseover,help,nodead][@target,help,nodead][@player].
- Addons cannot cast, target or move for the player and nothing can change in combat.
  Never suggest automation; just set things up for the player to press.
- ctx.errors holds the latest Lua errors, blocked actions and red error messages.
  When asked about errors, explain the most likely cause and the fix in plain words.
"""

ACTION_TYPES = {"waypoint", "track_quest", "mark", "macro", "bar", "bind", "setting"}


def sanitize(obj) -> dict:
    if not isinstance(obj, dict):
        return {"say": str(obj)[:1500]}
    say = obj.get("say")
    out = {"say": (say if isinstance(say, str) else "")[:1500]}
    actions = []
    for a in obj.get("actions") or []:
        if isinstance(a, dict) and a.get("type") in ACTION_TYPES:
            clean = {k: v for k, v in a.items()
                     if isinstance(k, str) and isinstance(v, (str, int, float, bool))}
            actions.append(clean)
    if actions:
        out["actions"] = actions[:12]
    return out


def parse_json_loose(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


RAID_ICONS = {"star": 1, "circle": 2, "diamond": 3, "triangle": 4, "moon": 5, "square": 6, "cross": 7, "x": 7, "skull": 8}


def offline_answer(text: str, ctx: dict) -> dict:
    """Tiny rule-based stand-in so the whole pipeline can be tested without a model."""
    t = text.lower()
    loc = ctx.get("location") or {}
    focus = ctx.get("focus") or {}

    m = re.search(r"(\d{1,2}(?:\.\d+)?)\s*[, ]\s*(\d{1,2}(?:\.\d+)?)", t)
    if m and any(w in t for w in ("way", "go to", "take me", "coord")) and loc.get("mapID"):
        x, y = float(m.group(1)), float(m.group(2))
        return {"say": f"Arrow set to {x:.1f}, {y:.1f} in {loc.get('map', 'this zone')}.",
                "actions": [{"type": "waypoint", "map": loc["mapID"], "x": x / 100, "y": y / 100, "title": "Wowpilot"}]}

    if "quest" in t:
        if focus:
            title = focus.get("title") or f"quest {focus.get('quest')}"
            say = f"You're following \"{title}\"."
            if focus.get("obj"):
                say += " Objectives: " + "; ".join(focus["obj"]) + "."
            actions = []
            nxt = focus.get("next")
            if nxt:
                actions.append({"type": "waypoint", "map": nxt["map"], "x": nxt["x"], "y": nxt["y"], "title": title})
                say += " Arrow is on the next step."
            else:
                say += " The game gives no location for the next step."
            return {"say": say, "actions": actions}
        quests = ctx.get("quests") or []
        if quests:
            names = ", ".join(q.get("title", "?") for q in quests[:6])
            return {"say": f"Your quests: {names}. Click one in the quest log to follow it, then ask again."}
        return {"say": "Your quest log looks empty."}

    for word, icon in RAID_ICONS.items():
        if re.search(rf"\b{word}\b", t) and ("mark" in t or word == "skull"):
            return {"say": f"Marked your target with {word}.", "actions": [{"type": "mark", "icon": icon}]}

    if "macro" in t:
        m = re.search(r"macro (?:for |with )?(?:a |an )?(?:mouseover )?([a-z' ]+?)(?:\s+(?:macro|on|bound|bind|to|in|at)\b|[,.!]|$)", t)
        spell = (m.group(1).strip().title() if m else "").replace("Mouseover ", "")
        if not spell:
            return {"say": "Which spell should the macro cast?"}
        harmful = any(w in t for w in ("harm", "attack", "damage", "dps", "enemy"))
        cond = "[@mouseover,harm,nodead][]" if harmful else "[@mouseover,help,nodead][@target,help,nodead][@player]"
        name = spell[:16]
        actions = [{"type": "macro", "name": name, "body": f"#showtooltip\n/cast {cond} {spell}"}]
        sm = re.search(r"slot (\d{1,3})", t)
        if sm:
            actions.append({"type": "bar", "macro": name, "slot": int(sm.group(1))})
        km = re.search(r"(?:bind(?:ed)?|bound|key)\s+(?:it\s+)?(?:to\s+)?((?:(?:shift|ctrl|alt)[- ]?)*(?:f\d{1,2}|[a-z0-9]))\b", t)
        if km:
            key = re.sub(r"(shift|ctrl|alt)[- ]?", lambda g: g.group(1).upper() + "-", km.group(1)).upper()
            actions.append({"type": "bind", "key": key, "macro": name})
        return {"say": f"Here's a {'mouseover attack' if harmful else 'mouseover help'} macro for {spell}.", "actions": actions}

    if "error" in t:
        errs = ctx.get("errors") or {}
        for kind, label in (("lua", "Lua error"), ("blocked", "Blocked action"), ("ui", "Game message")):
            if errs.get(kind):
                return {"say": f"Latest {label}: {errs[kind][0].get('msg')}. (Connect an AI model and I'll explain it.)"}
        return {"say": "I haven't seen any errors this session."}

    if "where am i" in t:
        if loc:
            pos = f" at {loc['x'] * 100:.1f}, {loc['y'] * 100:.1f}" if loc.get("x") is not None else ""
            return {"say": f"You're in {loc.get('subzone') or loc.get('zone') or loc.get('map')}{pos}."}

    return {"say": "No AI model connected yet (set WOWPILOT_BASE_URL / WOWPILOT_API_KEY / WOWPILOT_MODEL). "
                   "Offline demo understands: 'take me to my quest', 'way 45.2 63.1', 'mark skull', "
                   "'macro for Rejuvenation on slot 5 bind to shift-e', 'what was that error', 'where am I'."}


class Brain:
    def __init__(self):
        self.base = os.environ.get("WOWPILOT_BASE_URL", "").rstrip("/")
        self.key = os.environ.get("WOWPILOT_API_KEY", "")
        self.model = os.environ.get("WOWPILOT_MODEL", "")

    @property
    def online(self) -> bool:
        return bool(self.base and self.model)

    def describe(self) -> str:
        return f"{self.model} at {self.base}" if self.online else "offline demo (no model configured)"

    def _post(self, body: dict) -> dict:
        headers = {"Content-Type": "application/json", "X-Title": "Wowpilot"}
        if self.key:
            headers["Authorization"] = "Bearer " + self.key
        req = urllib.request.Request(self.base + "/chat/completions", data=json.dumps(body).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)

    def _ask_model(self, packet: dict) -> dict:
        user = ("GAME CONTEXT (live from the client):\n" + json.dumps(packet.get("ctx") or {}, ensure_ascii=False)
                + "\n\nPLAYER:\n" + str(packet.get("text") or ""))
        body = {"model": self.model, "temperature": 0.2,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
                "response_format": {"type": "json_object"}}
        try:
            data = self._post(body)
        except urllib.error.HTTPError as e:
            if e.code != 400:
                raise
            body.pop("response_format")       # some endpoints don't support JSON mode
            data = self._post(body)
        return sanitize(parse_json_loose(data["choices"][0]["message"]["content"]))

    def answer(self, packet: dict) -> dict:
        kind = packet.get("t")
        if kind == "selftest":
            return {"say": f"Companion here ({self.describe()})."}
        ctx = packet.get("ctx") or {}
        if self.online:
            try:
                return self._ask_model(packet)
            except Exception as e:  # noqa: BLE001 - show the player what went wrong
                fallback = offline_answer(str(packet.get("text") or ""), ctx)
                fallback["say"] = f"(AI request failed: {e}) " + fallback.get("say", "")
                return fallback
        return offline_answer(str(packet.get("text") or ""), ctx)


# --------------------------------------------------------------------------
# Game folder handling and commands
# --------------------------------------------------------------------------

GUESSES = [r"C:\Program Files (x86)\World of Warcraft", r"C:\Program Files\World of Warcraft",
           r"D:\World of Warcraft", r"D:\Games\World of Warcraft", "/Applications/World of Warcraft"]
FLAVORS = ["_retail_", "_classic_", "_classic_era_", "_anniversary_"]


def resolve_flavor(path: str | None) -> pathlib.Path:
    candidates = [pathlib.Path(path).expanduser()] if path else [pathlib.Path(g) for g in GUESSES]
    for p in candidates:
        if (p / "Interface").is_dir() or (p.name.startswith("_") and p.name.endswith("_") and p.is_dir()):
            return p
        for sub in FLAVORS:
            if (p / sub).is_dir():
                print(f"Using {p / sub} (pass the flavor folder itself to pick another)")
                return p / sub
    raise SystemExit("Couldn't find World of Warcraft. Pass --wow with the game folder, "
                     'e.g. --wow "C:\\Program Files (x86)\\World of Warcraft\\_retail_"')


def cmd_install(args) -> None:
    flavor = resolve_flavor(args.wow)
    dest = flavor / "Interface" / "AddOns"
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    for src in sorted(ADDON_DIR.iterdir()):
        if src.is_dir() and src.name.startswith("Wowpilot"):
            shutil.copytree(src, dest / src.name, dirs_exist_ok=True)
            count += 1
    print(f"Installed {count} folders into {dest}. Restart the game (new addons need a restart).")


def handle(packet: dict, slots: Slots, brain: Brain) -> None:
    kind, rid, slot = packet.get("t"), packet.get("rid"), int(packet.get("slot") or 1)
    print(f"<- {kind} #{rid} (reply slot {slot}): {str(packet.get('text') or '')[:100]}")
    if kind == "ping":
        print(json.dumps(packet, indent=2, ensure_ascii=False))
        return
    started = time.time()
    with slots.lock:
        slots.generation += 1          # cancels pending clears from the previous answer
        slots.clear_probes(slot)
    reply = brain.answer(packet)
    reply.update({"sid": packet.get("sid"), "rid": rid, "t": kind, "written": time.strftime("%H:%M:%S")})
    slots.deliver(slot, reply, not_before=started + MIN_NOT_READY)
    print(f"-> answered in {time.time() - started:.1f}s: {reply.get('say', '')[:120]}"
          + (f"  [+{len(reply['actions'])} action(s)]" if reply.get("actions") else ""))


def cmd_run(args) -> None:
    flavor = resolve_flavor(args.wow)
    shots = flavor / "Screenshots"
    slots = Slots(flavor / "Interface" / "AddOns", None if args.no_probe else find_probe_font(args.font))
    slots.check()
    slots.clear_probes()
    brain = Brain()
    shots.mkdir(exist_ok=True)
    print(f"Wowpilot companion watching {shots}")
    print(f"  brain: {brain.describe()}")
    print(f"  ready-signal font: {'yes' if slots.font else 'none found (timed polling only)'}")
    print("  In game: /wp test   (Ctrl+C here to stop)")
    seen = {p.name for p in shots.iterdir()}
    sizes: dict[str, int] = {}
    while True:
        try:
            files = sorted((p for p in shots.iterdir() if p.suffix.lower() in SCREENSHOT_EXT and p.name not in seen),
                           key=lambda p: p.stat().st_mtime)
        except FileNotFoundError:
            files = []
        for p in files:
            try:
                size = p.stat().st_size
            except FileNotFoundError:
                continue
            if size == 0 or sizes.get(p.name) != size:   # still being written
                sizes[p.name] = size
                continue
            seen.add(p.name)
            sizes.pop(p.name, None)
            try:
                packet = decode_image(p)
            except Exception as e:  # noqa: BLE001
                print(f"!! {p.name}: {e}")
                continue
            if packet is None:
                continue          # a normal screenshot: leave it alone
            try:
                p.unlink()
            except OSError:
                pass
            handle(packet, slots, brain)
        time.sleep(0.15)


def cmd_write_test(args) -> None:
    flavor = resolve_flavor(args.wow)
    slots = Slots(flavor / "Interface" / "AddOns", None if args.no_probe else find_probe_font(args.font))
    slots.check()
    stamp = time.strftime("%H:%M:%S")
    slots.deliver(args.slot, {"sid": "*", "rid": 0, "say": f"Inbox test OK - written by the companion at {stamp}",
                              "written": stamp}, keep_probe=True)
    print(f"Test reply written to slots {args.slot}-{NUM_SLOTS}"
          + (" with ready-signal." if slots.font else " (without ready-signal)."))
    if slots.font:
        print("In game: /wp probe  (should now say true)  then  /wp poll  (should show the test text)")
    else:
        print("In game: /wp poll  (should show the test text)")


def cmd_decode(args) -> None:
    packet = decode_image(args.file)
    print(json.dumps(packet, indent=2, ensure_ascii=False) if packet else "No Wowpilot beacon in that image.")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Wowpilot companion (prototype)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("install", "run", "write-test"):
        sp = sub.add_parser(name)
        sp.add_argument("--wow", help="WoW folder or flavor folder (e.g. ...\\World of Warcraft\\_retail_)")
        if name != "install":
            sp.add_argument("--font", help="TrueType font used as the ready-signal (optional)")
            sp.add_argument("--no-probe", action="store_true", help="disable the ready-signal experiment")
        if name == "write-test":
            sp.add_argument("--slot", type=int, default=1, help="first slot to write (see /wp status)")
    sp = sub.add_parser("decode")
    sp.add_argument("file")
    args = ap.parse_args(argv)
    {"install": cmd_install, "run": cmd_run, "write-test": cmd_write_test, "decode": cmd_decode}[args.cmd](args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nbye")
