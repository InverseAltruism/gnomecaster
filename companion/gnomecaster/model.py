"""Talking to an OpenAI-compatible chat completions endpoint (OpenRouter, OpenAI, Ollama...).

Every failure becomes a ModelError whose message is written for the player, and no question
takes longer than the deadline: the addon stops waiting after 60 seconds.
"""
from __future__ import annotations

import difflib
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .slots import text_safe

DEADLINE = 40.0                     # seconds per question, retries included
READ_TIMEOUT = 30.0                 # per socket operation, inside the deadline
KEY_LIKE = re.compile(r"\b(sk|key|pk)[-_][A-Za-z0-9_-]{8,}")


class ModelError(Exception):
    def __init__(self, kind: str, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.retry_after = retry_after


def _with_deadline(fn, seconds: float):
    """Runs fn in a daemon thread and stops waiting after `seconds`. urllib timeouts apply
    per socket operation, so a server that trickles bytes could otherwise run for minutes."""
    box = {}

    def target():
        try:
            box["value"] = fn()
        except BaseException as e:  # noqa: BLE001 - re-raised in the caller's thread
            box["error"] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(max(0.0, seconds))
    if t.is_alive():
        raise TimeoutError
    if "error" in box:
        raise box["error"]
    return box["value"]


class ModelClient:
    def __init__(self, base_url: str, model: str, api_key: str = "", extra: dict | None = None,
                 deadline: float = DEADLINE, observer=None):
        self.base = base_url.rstrip("/")
        self.model = model
        self.key = api_key
        self.extra = dict(extra or {})
        self.deadline = deadline
        self.observer = observer        # called with a dict per HTTP attempt (tools/eval_models.py)
        self.json_mode = True           # turned off for the session after the endpoint rejects it

    @property
    def host(self) -> str:
        return urllib.parse.urlsplit(self.base).netloc or self.base

    def _local(self) -> bool:
        return self.host.split(":")[0] in ("localhost", "127.0.0.1", "::1")

    def _open(self, method: str, path: str, body: dict | None, timeout: float) -> dict:
        headers = {"Content-Type": "application/json", "X-Title": "Gnomecaster"}
        if self.key:
            headers["Authorization"] = "Bearer " + self.key
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            # Read the error body here, inside the deadline thread: a server can send error
            # headers at once and then trickle the body.
            try:
                e.body_text = e.read(4000).decode("utf-8", "replace")
            except Exception:  # noqa: BLE001 - the status code alone still explains it
                e.body_text = ""
            raise

    def _clean(self, text: str) -> str:
        """Provider text shown to the player: no lone surrogates and never the API key."""
        text = text_safe(str(text))
        if self.key:
            text = text.replace(self.key, "<your key>")
        return KEY_LIKE.sub("<key>", text)

    # ---------------------------------------------------------------- errors

    def _http_error(self, e: urllib.error.HTTPError) -> ModelError:
        detail = ""
        try:
            payload = json.loads(getattr(e, "body_text", "") or "{}")
            err = payload.get("error") if isinstance(payload, dict) else None
            detail = (err.get("message") if isinstance(err, dict) else str(err or "")) or ""
        except Exception:  # noqa: BLE001 - the status code alone still explains it
            pass
        retry = None
        try:
            retry = float(e.headers.get("Retry-After")) if e.headers and e.headers.get("Retry-After") else None
        except ValueError:
            retry = None
        return self._status_error(e.code, detail, retry)

    def _status_error(self, code: int, detail: str = "", retry: float | None = None) -> ModelError:
        detail = self._clean(detail).strip()[:200]
        suffix = f" ({detail})" if detail else ""
        if code in (401, 403):
            return ModelError("auth", f"{self.host} rejected the API key{suffix}. Connect again in the Gnomecaster app.")
        if code == 402:
            return ModelError("credit", f"Your account at {self.host} is out of credit{suffix}. Add credit there, then try again.")
        if code == 404:
            return ModelError("model", f"The model '{self.model}' is not available at {self.host}{suffix}. "
                                       "Choose another model in the Gnomecaster app.")
        if code in (408, 504):
            return ModelError("timeout", f"{self.host} timed out. Try again.")
        if code == 429:
            seconds = max(1, round(retry)) if retry else 0
            wait = f" Try again in {seconds} second{'s' if seconds != 1 else ''}," if seconds else " Try again in a moment,"
            return ModelError("rate_limit", f"The model is busy right now (rate limited).{wait} "
                                            "or choose another model in the Gnomecaster app.", retry)
        if 500 <= code < 600:
            return ModelError("provider", f"{self.host} had a problem (HTTP {code}){suffix}. Try again in a moment.")
        return ModelError("refused", f"{self.host} refused the request (HTTP {code}){suffix}.")

    def _network_error(self, e: urllib.error.URLError) -> ModelError:
        reason = getattr(e, "reason", e)
        if isinstance(reason, ConnectionRefusedError) and self._local():
            return ModelError("network", f"Nothing is answering at {self.base}. Is Ollama (or your local "
                                         "model server) running?")
        return ModelError("network", f"Can't reach {self.host} ({self._clean(reason)}). Check your internet connection.")

    # ---------------------------------------------------------------- answers

    def _content(self, data) -> str:
        if not isinstance(data, dict):
            raise ModelError("format", f"{self.host} sent an answer this companion cannot read.")
        err = data.get("error")
        if err:
            code = err.get("code") if isinstance(err, dict) else None
            msg = err.get("message", "") if isinstance(err, dict) else str(err)
            raise self._status_error(code if isinstance(code, int) else 502, msg)
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ModelError("provider", f"{self.host} returned no answer. Try again.")
        choice = choices[0]
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        finish = choice.get("finish_reason")
        content = message.get("content")
        if isinstance(content, list):
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        if finish == "error":
            raise ModelError("provider", "The model stopped with an error partway through. Try again.")
        if finish == "content_filter":
            raise ModelError("filtered", f"{self.host}'s content filter blocked that answer.")
        if not isinstance(content, str) or not content.strip():
            if message.get("reasoning") or message.get("reasoning_content"):
                raise ModelError("empty", "The model only thought it over and gave no answer. Try again, "
                                          "or choose another model in the Gnomecaster app.")
            raise ModelError("empty", "The model returned an empty answer. Try again.")
        return content

    def _record(self, **fields):
        if self.observer:
            self.observer(fields)

    def complete(self, messages: list[dict]) -> str:
        """The text of the model's answer. Raises ModelError; never runs past the deadline."""
        started = time.monotonic()
        attempt = 0
        while True:
            attempt += 1
            remaining = self.deadline - (time.monotonic() - started)
            if remaining < 1:
                raise ModelError("timeout", f"The model took longer than {self.deadline:.0f} seconds. "
                                            "Try again, or choose a faster model in the Gnomecaster app.")
            body = {"model": self.model, "messages": messages, "temperature": 0.2, **self.extra}
            if self.json_mode:
                body["response_format"] = {"type": "json_object"}
            t0 = time.monotonic()
            try:
                data = _with_deadline(lambda: self._open("POST", "/chat/completions", body, min(READ_TIMEOUT, remaining)),
                                      remaining)
            except TimeoutError:
                self._record(status=None, error="deadline", seconds=time.monotonic() - t0, json_mode=self.json_mode)
                raise ModelError("timeout", f"The model took longer than {self.deadline:.0f} seconds. "
                                            "Try again, or choose a faster model in the Gnomecaster app.") from None
            except urllib.error.HTTPError as e:
                err = self._http_error(e)
                self._record(status=e.code, error=err.message, seconds=time.monotonic() - t0, json_mode=self.json_mode)
                if e.code == 400 and self.json_mode:
                    self.json_mode = False      # this endpoint or model rejects JSON mode; the prompt still asks for JSON
                    continue
                if err.kind in ("rate_limit", "provider") and attempt == 1:
                    wait = min(err.retry_after or 2.0, 5.0)
                    if self.deadline - (time.monotonic() - started) > wait + 8:
                        time.sleep(wait)
                        continue
                raise err from None
            except urllib.error.URLError as e:
                self._record(status=None, error=str(e), seconds=time.monotonic() - t0, json_mode=self.json_mode)
                raise self._network_error(e) from None
            except (TimeoutError, OSError) as e:
                self._record(status=None, error=str(e), seconds=time.monotonic() - t0, json_mode=self.json_mode)
                raise ModelError("timeout", f"{self.host} stopped responding. Try again.") from None
            except ValueError:
                self._record(status=200, error="unreadable body", seconds=time.monotonic() - t0, json_mode=self.json_mode)
                raise ModelError("format", f"{self.host} sent an answer this companion cannot read.") from None
            choice = (data.get("choices") or [{}])[0] if isinstance(data, dict) and isinstance(data.get("choices"), list) else {}
            message = choice.get("message") if isinstance(choice, dict) and isinstance(choice.get("message"), dict) else {}
            self._record(status=200, seconds=time.monotonic() - t0, json_mode=self.json_mode,
                         usage=data.get("usage") if isinstance(data, dict) else None,
                         finish=choice.get("finish_reason") if isinstance(choice, dict) else None,
                         content=message.get("content"), reasoning_chars=len(str(message.get("reasoning") or "")))
            try:
                return self._content(data)
            except ModelError as err:
                if err.kind == "provider" and attempt == 1 and self.deadline - (time.monotonic() - started) > 10:
                    continue
                raise

    def check(self) -> str:
        """Confirms the endpoint, key and model work. Returns a short success note; raises ModelError."""
        try:
            listing = _with_deadline(lambda: self._open("GET", "/models", None, 15), 20)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise self._http_error(e) from None
            listing = None              # some servers have no model list; the test question decides
        except urllib.error.URLError as e:
            raise self._network_error(e) from None
        except TimeoutError:
            raise ModelError("network", f"{self.host} did not answer within 20 seconds.") from None
        ids = [m.get("id") for m in (listing or {}).get("data", []) if isinstance(m, dict)] if isinstance(listing, dict) else []
        if ids and self.model not in ids:
            near = difflib.get_close_matches(self.model, ids, n=3, cutoff=0.6)
            hint = f" Did you mean: {', '.join(near)}?" if near else ""
            if self._local():
                hint += f" For Ollama, run: ollama pull {self.model}"
            raise ModelError("model", f"The model '{self.model}' is not available at {self.host}.{hint}")
        started = time.monotonic()
        self.complete([{"role": "user", "content": 'Reply with exactly this JSON: {"say": "ok"}'}])
        return f"answered in {time.monotonic() - started:.1f} s"
