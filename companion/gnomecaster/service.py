"""The companion as a background service for the desktop app: the request loop in a thread,
reporting each question and answer to the window as it happens."""
from __future__ import annotations

import logging
import pathlib
import threading
import time

from . import serve
from .slots import Slots, find_probe_font

log = logging.getLogger("gnomecaster")
KEEP = 50                           # activity entries kept for the window
MARKERS = [None, "Star", "Circle", "Diamond", "Triangle", "Moon", "Square", "Cross", "Skull"]


def key_name(key) -> str:
    """SHIFT-E as the game's settings show it: Shift-E."""
    parts = str(key or "").split("-")
    mods = {"SHIFT": "Shift", "CTRL": "Ctrl", "ALT": "Alt", "META": "Meta"}
    return "-".join([mods.get(p.upper(), p.title()) for p in parts[:-1]] + parts[-1:])


def describe(action: dict) -> str:
    """One action the answer asked of the game, as the window lists it. Whether it happened
    is the game's decision (the confirm bar, auto-apply, a changed target), so no status."""
    t = action.get("type")
    if t == "macro":
        return f'Macro \u201c{action.get("name")}\u201d'
    if t == "bar":
        return f'\u201c{action.get("macro")}\u201d on action slot {action.get("slot")}'
    if t == "bind":
        return f'{key_name(action.get("key"))} bound to \u201c{action.get("macro")}\u201d'
    if t == "setting":
        return f'Setting {action.get("name")} = {action.get("value")}'
    if t == "waypoint":
        x, y, where = action.get("x"), action.get("y"), ""
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            scale = 100 if x <= 1 and y <= 1 else 1     # the addon accepts fractions or percentages
            where = f" ({x * scale:.1f}, {y * scale:.1f})"
        return f'Waypoint: {action.get("title") or "Gnomecaster"}{where}'
    if t == "mark":
        icon, unit = action.get("icon"), action.get("unit") or "target"
        if icon == 0:
            return f"Marker cleared from your {unit}"
        marker = MARKERS[icon] if isinstance(icon, int) and 0 < icon < len(MARKERS) else f"Marker {icon}"
        return f"{marker} on your {unit}"
    if t == "track_quest":
        return f'Following quest {action.get("quest")}'
    if t == "goto":
        return f'Map pin: \u201c{action.get("name")}\u201d'
    return str(t)


class _Observed:
    """Wraps the brain to report questions and answers without touching the request loop."""

    def __init__(self, brain, service: "Companion"):
        self.brain = brain
        self.service = service

    def __getattr__(self, name):
        return getattr(self.brain, name)

    def answer(self, packet: dict) -> dict:
        kind = packet.get("t")
        question = "/gc test" if kind == "selftest" else str(packet.get("text") or "")
        entry = {"id": self.service.next_id(), "time": time.strftime("%H:%M"), "question": question, "pending": True}
        self.service.record("question", entry)
        started = time.monotonic()
        done = {k: v for k, v in entry.items() if k != "pending"}
        try:
            reply = self.brain.answer(packet)
        except Exception as e:
            done.update({"answer": f"The companion hit an internal error ({type(e).__name__}); details are in the log.",
                         "actions": [], "seconds": round(time.monotonic() - started, 1), "error": True})
            self.service.record("answer", done)
            raise                       # serve.handle answers the game and logs the traceback
        done.update({"answer": reply.get("say", ""), "actions": [describe(a) for a in reply.get("actions") or []],
                     "seconds": round(time.monotonic() - started, 1), "error": bool(reply.get("error"))})
        client = getattr(self.brain, "client", None)
        if client is not None and not done["error"]:
            done["model"] = client.model
        self.service.record("answer", done)
        return reply


class Companion:
    def __init__(self, on_event=lambda event: None, on_change=lambda running: None):
        self.on_event = on_event
        self.on_change = on_change          # started or stopped (the tray menu shows which)
        self.activity: list[dict] = []
        self.since: str | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._ids = 0
        self._lock = threading.Lock()
        self._life = threading.RLock()      # one start or stop at a time: the window calls from many threads

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def next_id(self) -> int:
        with self._lock:
            self._ids += 1
            return self._ids

    def record(self, kind: str, entry: dict) -> None:
        with self._lock:
            for i, e in enumerate(self.activity):
                if e["id"] == entry["id"]:
                    self.activity[i] = entry
                    break
            else:
                self.activity.insert(0, entry)
            del self.activity[KEEP:]
        try:
            self.on_event({"type": kind, "entry": entry})
        except Exception:  # noqa: BLE001 - a closed window must not stop the companion
            log.exception("could not show an event in the window")

    def start(self, flavor: pathlib.Path, brain, interval: float = 0.15) -> None:
        """Starts answering questions from the game installed at `flavor`, after the
        previous worker has finished its current question."""
        with self._life:
            self._halt(wait=True)
            self._launch(flavor, brain, interval)

    def stop(self, wait: bool = True) -> None:
        """Stops answering. With wait, returns once the question in progress is answered
        (at most the model deadline), so no two workers ever write replies at once."""
        with self._life:
            self._halt(wait)

    def _launch(self, flavor: pathlib.Path, brain, interval: float) -> None:
        slots = Slots(flavor / "Interface" / "AddOns", find_probe_font(None))
        slots.clear_probes()
        shots = flavor / "Screenshots"
        shots.mkdir(parents=True, exist_ok=True)
        observed = _Observed(brain, self)
        self._stop = threading.Event()
        stop = self._stop
        # Taken before the thread starts: every screenshot that appears after start() returns
        # is new to the watcher, however late the thread gets to run.
        watcher = serve.Watcher(shots)

        def loop():
            log.info("listening in %s", shots)
            while not stop.is_set():
                for p in watcher.ready():
                    serve.process(p, watcher, slots, observed, log.info)
                stop.wait(interval)
            log.info("stopped listening")

        self.since = time.strftime("%H:%M")
        self._thread = threading.Thread(target=loop, name="companion", daemon=True)
        self._thread.start()
        self._changed()

    def _halt(self, wait: bool) -> None:
        if self._thread is None:
            return
        self._stop.set()
        if wait:
            self._thread.join()
        self._thread = None
        self.since = None
        self._changed()

    def _changed(self) -> None:
        try:
            self.on_change(self.running)
        except Exception:  # noqa: BLE001 - the tray is optional
            log.exception("could not report the companion's state")
