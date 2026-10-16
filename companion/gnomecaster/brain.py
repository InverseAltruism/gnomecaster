"""Turns a request from the game into a reply: the model when one is set up, else the demo."""
from __future__ import annotations

import pathlib

from . import demo, prompt
from .model import ModelClient, ModelError


class Brain:
    def __init__(self, client: ModelClient | None, addon_dir: pathlib.Path):
        self.client = client
        self.system = prompt.system_prompt(*prompt.addon_lists(addon_dir))
        self.check_note: str | None = None      # result of the last connection check
        self.check_ok: bool | None = None

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
        if packet.get("t") == "selftest":
            self.run_check()                    # fresh: the key may have changed since startup
            reply = {"say": "Companion here. " + self.status()}
            if self.client and self.check_ok is False:
                reply["error"] = "setup"
            return reply
        if not self.client:
            return demo.answer(str(packet.get("text") or ""), packet.get("ctx") or {})
        try:
            content = self.client.complete([{"role": "system", "content": self.system},
                                            {"role": "user", "content": prompt.user_message(packet)}])
            return prompt.sanitize(prompt.parse_reply(content))
        except ModelError as e:
            return {"say": e.message, "error": e.kind}
