"""The reply channel: writing answers into the addon's load-on-demand reply slots.

The addon loads the next unused Gnomecaster_InboxNN slot to read a reply; each slot loads
once per UI session. A reply is written into every slot from the one the request named,
so slots the addon spends by polling early still lead it to the answer.
"""
from __future__ import annotations

import math
import os
import pathlib
import re
import threading
import time

from .protocol import NUM_SLOTS

# The addon's timed polls (BLIND in Inbox.lua) can spend at most 8 slots while one request
# waits, so the slot that receives the reply is at most 8 past the one the request named.
PROBE_AHEAD = 9                     # slots that get the ready signal per reply
PROBE_LIFETIME = 8.0                # seconds before ready signals are cleared again
MIN_NOT_READY = 0.75                # keep signals "not ready" at least this long per request


SURROGATE = re.compile("[\ud800-\udfff]")


def text_safe(s: str) -> str:
    """Replaces lone UTF-16 surrogates, which JSON allows and UTF-8 cannot encode, with U+FFFD."""
    return SURROGATE.sub("\ufffd", s)


def lua_str(s: str) -> str:
    """A Lua string literal in plain ASCII."""
    out = ['"']
    for b in text_safe(s).encode("utf-8"):
        if b == 0x5C:
            out.append("\\\\")
        elif b == 0x22:
            out.append('\\"')
        elif b == 0x0A:
            out.append("\\n")
        elif 0x20 <= b < 0x7F:
            out.append(chr(b))
        else:
            out.append("\\%03d" % b)
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
        return repr(v) if math.isfinite(v) else "nil"
    if isinstance(v, str):
        return lua_str(v)
    if isinstance(v, (list, tuple)):
        return "{" + ",".join(lua_value(x) for x in v) + "}"
    if isinstance(v, dict):
        kept = [(k, x) for k, x in v.items() if x is not None and not (isinstance(x, float) and not math.isfinite(x))]
        return "{" + ",".join(f"[{lua_str(str(k))}]={lua_value(x)}" for k, x in kept) + "}"
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
        return self.addons / f"Gnomecaster_Inbox{n:02d}"

    @property
    def ack(self) -> pathlib.Path:
        """Filled while a request is being answered, so the addon knows it was picked up."""
        return self.addons / "Gnomecaster" / "ack.ttf"

    def _set_ack(self, on: bool) -> None:
        if self.font and self.ack.parent.is_dir():
            atomic_write(self.ack, self.font if on else b"")

    def missing(self) -> list[int]:
        return [n for n in range(1, NUM_SLOTS + 1) if not self.dir(n).is_dir()]

    def clear_probes(self, start: int = 1) -> None:
        for n in range(max(1, start), NUM_SLOTS + 1):
            p = self.dir(n) / "ready.ttf"
            if p.exists() and p.stat().st_size:
                atomic_write(p, b"")
        if start <= 1 and self.ack.exists() and self.ack.stat().st_size:
            atomic_write(self.ack, b"")

    def begin_request(self, start: int) -> None:
        """A request arrived: cancel pending clears and show 'not ready' from `start` on."""
        with self.lock:
            self.generation += 1
            self.clear_probes(start)
            self._set_ack(True)

    def deliver(self, start: int, msg: dict, keep_probe: bool = False, not_before: float = 0.0) -> None:
        start = max(1, min(NUM_SLOTS, start))
        content = ("-- written by Gnomecaster companion\nGnomecasterInbox(" + lua_value(msg) + ")\n").encode("ascii")
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
            self._set_ack(False)
        if self.font and not keep_probe:
            def expire():
                with self.lock:
                    if self.generation == gen:
                        self.clear_probes(start)
            t = threading.Timer(PROBE_LIFETIME, expire)
            t.daemon = True
            t.start()
