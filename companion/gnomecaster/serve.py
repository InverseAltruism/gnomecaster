"""The request loop: notice new screenshots, decode requests, answer them, write the replies."""
from __future__ import annotations

import json
import pathlib
import time
import traceback

from . import protocol
from .slots import MIN_NOT_READY

DECODE_TRIES = 3                    # a screenshot that fails to decode is retried this often


def slot_of(packet: dict) -> int:
    try:
        return int(packet.get("slot") or 1)
    except (TypeError, ValueError):
        return 1


def respond(packet: dict, slots, brain) -> dict:
    """Marks the reply slots 'not ready' and computes the reply for one request."""
    slots.begin_request(slot_of(packet))
    reply = brain.answer(packet)
    reply.update({"sid": packet.get("sid"), "rid": packet.get("rid"), "t": packet.get("t"),
                  "written": time.strftime("%H:%M:%S")})
    return reply


def handle(packet: dict, slots, brain, log=print) -> bool:
    """Answers one request. Never raises: one bad request must not stop the companion.
    Returns whether the reply was written."""
    started = time.time()
    try:
        reply = respond(packet, slots, brain)
    except Exception as e:  # noqa: BLE001 - reported to the player and logged, then the loop goes on
        log("!! internal error while answering:\n" + traceback.format_exc())
        reply = {"say": f"The companion hit an internal error ({type(e).__name__}); details are in the Gnomecaster log.",
                 "error": "internal", "sid": packet.get("sid"), "rid": packet.get("rid"), "t": packet.get("t")}
    try:
        slots.deliver(slot_of(packet), reply, not_before=started + MIN_NOT_READY)
    except Exception as e:  # noqa: BLE001 - e.g. a file locked by a virus scanner; the addon times out
        log(f"!! could not write the reply into the reply slots: {e}")
        return False
    actions = reply.get("actions") or []
    try:
        log(f"-> answered in {time.time() - started:.1f}s: {str(reply.get('say', ''))[:120]}"
            + (f"  [+{len(actions)} action(s)]" if actions else ""))
    except Exception:  # noqa: BLE001 - a console that cannot print the text must not stop the loop
        pass
    return True


class Watcher:
    """Finds screenshots that appeared since start and have finished being written."""

    def __init__(self, folder: pathlib.Path):
        self.folder = folder
        self.seen = {p.name for p in folder.iterdir()} if folder.is_dir() else set()
        self.sizes: dict[str, int] = {}
        self.tries: dict[str, int] = {}

    def ready(self) -> list[pathlib.Path]:
        try:
            files = sorted((p for p in self.folder.iterdir()
                            if p.suffix.lower() in protocol.SCREENSHOT_EXT and p.name not in self.seen),
                           key=lambda p: p.stat().st_mtime)
        except FileNotFoundError:
            return []
        out = []
        for p in files:
            try:
                size = p.stat().st_size
            except FileNotFoundError:
                continue
            if size == 0 or self.sizes.get(p.name) != size:      # still being written
                self.sizes[p.name] = size
                continue
            out.append(p)
        return out

    def done(self, p: pathlib.Path) -> None:
        self.seen.add(p.name)
        self.sizes.pop(p.name, None)
        self.tries.pop(p.name, None)

    def failed(self, p: pathlib.Path) -> bool:
        """Records a decode failure; True once the file should be given up on."""
        self.tries[p.name] = self.tries.get(p.name, 0) + 1
        self.sizes.pop(p.name, None)
        if self.tries[p.name] >= DECODE_TRIES:
            self.done(p)
            return True
        return False


def process(p: pathlib.Path, watcher: Watcher, slots, brain, log=print) -> str:
    """Handles one finished screenshot: 'request', 'ping', 'ignored' or 'error'. A screenshot
    whose reply could not be written is tried again a few times, like an unreadable one."""
    try:
        packet = protocol.decode_image(p)
    except Exception as e:  # noqa: BLE001 - truncated or unreadable image: retried a few times
        if watcher.failed(p):
            log(f"!! {p.name}: {e}")
        return "error"
    if packet is None:
        watcher.done(p)
        return "ignored"            # a normal screenshot: left alone
    kind = packet.get("t")
    log(f"<- {kind} #{packet.get('rid')} (reply slot {slot_of(packet)}): {str(packet.get('text') or '')[:100]}")
    if kind == "ping":
        log(json.dumps(packet, indent=2, ensure_ascii=False))
    elif not handle(packet, slots, brain, log):
        if watcher.failed(p):
            log(f"!! gave up on {p.name}: its reply could not be written")
        return "error"
    watcher.done(p)
    try:
        p.unlink()
    except OSError:
        pass
    return "ping" if kind == "ping" else "request"


def run_forever(shots: pathlib.Path, slots, brain, log=print, interval: float = 0.15) -> None:
    watcher = Watcher(shots)
    while True:
        for p in watcher.ready():
            process(p, watcher, slots, brain, log)
        time.sleep(interval)
