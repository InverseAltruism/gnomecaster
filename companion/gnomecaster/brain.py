"""Turns a request from the game into a reply: the model when one is set up, else the demo.

The model sees the conversation so far (conversation.Memory) and the game's report on its
previous actions; every exchange goes into the transcript when there is one.
"""
from __future__ import annotations

import datetime
import pathlib
import time

from . import demo, prompt
from .conversation import Memory, key_of
from .model import ModelClient, ModelError
from .slots import text_safe
from .transcript import Transcript, request_of

QUESTION_LIMIT = 2000               # characters of the player's text sent on; the beacon carries less


class Brain:
    def __init__(self, client: ModelClient | None, addon_dir: pathlib.Path, transcript: Transcript | None = None,
                 memory: Memory | None = None):
        self.client = client
        self.lists = prompt.addon_lists(addon_dir)
        self.transcript = transcript
        self.memory = memory or Memory()
        self.check_note: str | None = None      # result of the last connection check
        self.check_ok: bool | None = None

    @property
    def system(self) -> str:
        """The system prompt for the next question; it names web search only while it is offered."""
        return self._system(self.client)

    def _system(self, client: ModelClient | None) -> str:
        return prompt.system_prompt(*self.lists, search=bool(client and client.web_search))

    def describe(self) -> str:
        if not self.client:
            return "offline demo (no AI model set up)"
        return f"{self.client.model} at {self.client.host}"

    def run_check(self) -> bool:
        if not self.client:
            return False
        try:
            self.check_note, self.check_ok = self.client.check(), True
        except ModelError as e:
            self.check_note, self.check_ok = e.message, False
        return self.check_ok

    def status(self) -> str:
        if not self.client:
            return "No AI model is set up, so answers come from the offline demo. Connect one in the Gnomecaster app."
        if self.check_ok is None:
            return f"Using {self.describe()} (connection not checked)."
        if self.check_ok:
            return f"Using {self.describe()}: {self.check_note}."
        return f"The AI connection has a problem: {self.check_note}"

    def answer(self, packet: dict) -> dict:
        # read once: the window thread replaces self.client when the settings change
        client = self.client
        started = time.monotonic()
        record = {"time": datetime.datetime.now().isoformat(timespec="seconds"), "conv": key_of(packet),
                  "request": request_of(packet),
                  "kind": packet.get("t"), "question": text_safe(str(packet.get("text") or ""))[:QUESTION_LIMIT],
                  "ctx": packet.get("ctx") or {}, "last": prompt.last_results(packet), "raw": None,
                  "searched": False, "sources": [], "model": client.model if client else "demo"}
        try:
            reply = self._reply(packet, record, client)
        except Exception as e:
            record.update(reply=None, error=f"internal: {type(e).__name__}")
            raise
        else:
            record.update(reply=reply, error=reply.get("error"))
        finally:
            record["seconds"] = round(time.monotonic() - started, 2)
            if self.transcript is not None:
                self.transcript.write(record, client.key if client else "")
        return reply

    def _reply(self, packet: dict, record: dict, client: ModelClient | None) -> dict:
        if packet.get("t") == "selftest":
            self.run_check()                    # fresh: the key may have changed since startup
            reply = {"say": "Companion here. " + self.status()}
            if self.client and self.check_ok is False:
                reply["error"] = "setup"
            return reply
        if not client:
            return demo.answer(record["question"], record["ctx"])
        key = record["conv"]
        messages = [{"role": "system", "content": self._system(client)}, *self.memory.history(key),
                    {"role": "user", "content": prompt.user_message({**packet, "text": record["question"]}, record["last"])}]
        try:
            done = client.chat(messages, search=True)
            record.update(raw=done.text, searched=done.searched, sources=done.sources)
            reply = prompt.sanitize(prompt.parse_reply(done.text))
        except ModelError as e:
            return {"say": e.message, "error": e.kind}
        self.memory.add(key, record["question"], reply)
        return reply
