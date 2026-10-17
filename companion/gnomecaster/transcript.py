"""Every exchange with the model, one JSON line each, so the player can see what was sent
and answered: <folder>/YYYY-MM-DD.jsonl in local time, kept for KEEP_DAYS days.

Writing never raises: a full disk or a locked file must not cost the player the answer.
"""
from __future__ import annotations

import datetime
import json
import logging
import pathlib
import re
import threading
import time

from .model import redact

log = logging.getLogger("gnomecaster")
KEEP_DAYS = 14
MAX_LIST = 200                      # entries one getHistory call returns at most
NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})\.jsonl$")


class Transcript:
    def __init__(self, folder: pathlib.Path, clock=time.time):
        self.folder = folder
        self.clock = clock
        self._lock = threading.Lock()
        self._pruned: str | None = None     # the day old files were last removed

    def _day(self) -> datetime.date:
        return datetime.datetime.fromtimestamp(self.clock()).date()

    def _prune(self, today: datetime.date) -> None:
        cutoff = today - datetime.timedelta(days=KEEP_DAYS - 1)
        for p in self.folder.glob("*.jsonl"):
            m = NAME.match(p.name)
            try:
                if m and datetime.date.fromisoformat(m.group(1)) < cutoff:
                    p.unlink()
            except (ValueError, OSError):
                continue

    def write(self, record: dict, secret: str = "") -> None:
        """Appends one exchange. The whole line is redacted, so no field can carry the key."""
        try:
            line = redact(json.dumps(record, ensure_ascii=False, default=str), secret)
            today = self._day()
            with self._lock:
                self.folder.mkdir(parents=True, exist_ok=True)
                if self._pruned != today.isoformat():
                    self._prune(today)
                    self._pruned = today.isoformat()
                with open(self.folder / f"{today.isoformat()}.jsonl", "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception:  # noqa: BLE001 - the answer matters more than its record
            log.exception("could not write the transcript")

    def recent(self, limit: int) -> list[dict]:
        """The latest exchanges, newest first."""
        limit = max(0, min(MAX_LIST, limit))
        out: list[dict] = []
        with self._lock:
            files = sorted((p for p in self.folder.glob("*.jsonl") if NAME.match(p.name)), reverse=True) \
                if self.folder.is_dir() else []
            for p in files:
                try:
                    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError:
                    continue
                for line in reversed(lines):
                    if len(out) >= limit:
                        return out
                    try:
                        item = json.loads(line)
                    except ValueError:
                        continue                # a line cut short by a crash
                    if isinstance(item, dict):
                        out.append(item)
        return out
