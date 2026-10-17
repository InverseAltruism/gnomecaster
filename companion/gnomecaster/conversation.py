"""What the model remembers of a conversation: the last exchanges per player conversation.

The addon names a conversation in `conv` (kept across /reload, renewed by /gc new); older
addons send only `sid`, which changes with every UI load. Only text and the proposed actions
are kept: the game context of earlier turns is stale and would cost tokens on every question.
The request loop runs in a thread while the window reads state, so every access is locked.
"""
from __future__ import annotations

import json
import re
import threading
import time
from collections import OrderedDict

TURNS = 10                          # exchanges kept per conversation
IDLE = 30 * 60.0                    # seconds without a question before a conversation is forgotten
MAX_KEYS = 32                       # conversations kept at once; the least recently used goes first
KEY_CHARS = 16                      # the addon's conv is at most 16 characters
TEXT_LIMIT = 500                    # characters kept of each remembered question
KEY_SAFE = re.compile(r"[^A-Za-z0-9_.:-]")


def key_of(packet: dict) -> str | None:
    """The conversation a request belongs to: its conv, else its UI session, else none."""
    for field in ("conv", "sid"):
        value = packet.get(field)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            cleaned = KEY_SAFE.sub("", str(value))[:KEY_CHARS]
            if cleaned:
                return f"{field}:{cleaned}"
    return None


def _assistant(reply: dict) -> str:
    """The model's own answer format, compact: what it said and the actions it proposed."""
    kept = {"say": reply.get("say", "")}
    if reply.get("actions"):
        kept["actions"] = reply["actions"]
    return json.dumps(kept, ensure_ascii=False, separators=(",", ":"))


class Memory:
    def __init__(self, turns: int = TURNS, idle: float = IDLE, max_keys: int = MAX_KEYS, clock=time.monotonic):
        self.turns = turns
        self.idle = idle
        self.max_keys = max_keys
        self.clock = clock
        self._lock = threading.Lock()
        self._convs: OrderedDict[str, tuple[float, list[tuple[str, str]]]] = OrderedDict()

    def _expire(self, now: float) -> None:
        for key in [k for k, (seen, _) in self._convs.items() if now - seen > self.idle]:
            del self._convs[key]

    def history(self, key: str | None) -> list[dict]:
        """Earlier exchanges of this conversation as chat messages, oldest first."""
        if key is None:
            return []
        with self._lock:
            self._expire(self.clock())
            turns = list(self._convs.get(key, (0.0, []))[1])
        messages = []
        for question, answer in turns:
            messages += [{"role": "user", "content": "PLAYER:\n" + question},
                         {"role": "assistant", "content": answer}]
        return messages

    def add(self, key: str | None, question: str, reply: dict) -> None:
        if key is None:
            return
        with self._lock:
            now = self.clock()
            self._expire(now)
            turns = self._convs.pop(key, (now, []))[1]
            turns.append((question[:TEXT_LIMIT], _assistant(reply)))
            del turns[:-self.turns]
            self._convs[key] = (now, turns)
            while len(self._convs) > self.max_keys:
                self._convs.popitem(last=False)

    def __len__(self) -> int:
        with self._lock:
            return len(self._convs)
