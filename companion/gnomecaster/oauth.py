"""Sign in with OpenRouter: OAuth PKCE, so players do not have to copy an API key by hand.

The flow (https://openrouter.ai/docs/guides/overview/auth/oauth, read 2026-10-16): open
openrouter.ai/auth in the browser with a callback on 127.0.0.1 and a SHA-256 code challenge;
OpenRouter redirects back with a one-time code (valid 10 minutes); POST it with the code
verifier to /api/v1/auth/keys to receive an ordinary API key. No client registration exists.
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import secrets
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

AUTH_URL = "https://openrouter.ai/auth"
EXCHANGE_URL = "https://openrouter.ai/api/v1/auth/keys"
KEY_URL = "https://openrouter.ai/api/v1/key"
CREDITS_URL = "https://openrouter.ai/credits"   # linked from OpenRouter's error docs for 402
WAIT_SECONDS = 600                  # the code itself expires after 10 minutes

DONE_PAGE = """<!doctype html><meta charset="utf-8"><title>Gnomecaster</title>
<body style="font:16px/1.5 system-ui,sans-serif;background:#160f33;color:#ede9ff;display:grid;place-items:center;height:100vh;margin:0">
<div style="max-width:28rem;text-align:center"><h1 style="font-size:1.5rem">{title}</h1><p>{text}</p></div></body>"""


class SignInError(Exception):
    pass


def challenge_for(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class _Callback(http.server.BaseHTTPRequestHandler):
    timeout = 10                        # a connection that sends no request (a browser preconnect) is dropped

    def log_message(self, *a):
        pass

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        if url.path != "/callback":
            self.send_error(404)
            return
        query = urllib.parse.parse_qs(url.query)
        self.server.result = {k: v[0] for k, v in query.items()}
        ok = "code" in self.server.result
        page = DONE_PAGE.format(
            title="You're signed in" if ok else "Sign-in was cancelled",
            text="Return to Gnomecaster; it finishes the setup by itself. You can close this tab."
            if ok else "Nothing was connected. Start the sign-in again in Gnomecaster when you're ready.")
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.server.done.set()


def sign_in(open_browser=webbrowser.open, auth_url: str = AUTH_URL, exchange_url: str = EXCHANGE_URL,
            wait: float = WAIT_SECONDS, cancel: threading.Event | None = None) -> str:
    """Runs the whole flow and returns the new API key. Raises SignInError with a message
    for the player. `cancel` lets the app abort a sign-in the player walked away from."""
    verifier = secrets.token_urlsafe(64)          # 86 characters from the unreserved set
    state = secrets.token_urlsafe(24)
    # threaded, so an idle connection cannot hold up the browser's real redirect
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Callback)
    server.daemon_threads = True
    server.result, server.done = None, threading.Event()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        callback = f"http://127.0.0.1:{server.server_port}/callback"
        url = auth_url + "?" + urllib.parse.urlencode({
            "callback_url": callback, "code_challenge": challenge_for(verifier),
            "code_challenge_method": "S256", "state": state, "key_label": "Gnomecaster"})
        if not open_browser(url):
            raise SignInError("Couldn't open your web browser. Use an API key instead.")
        waited = 0.0
        while not server.done.wait(0.25):
            waited += 0.25
            if waited >= wait:
                raise SignInError("Sign-in took too long. Start it again when you're ready.")
            if cancel is not None and cancel.is_set():
                raise SignInError("Sign-in was cancelled.")
        result = server.result or {}
    finally:
        server.shutdown()
        server.server_close()
    if "code" not in result:
        raise SignInError("Sign-in was cancelled in the browser. Nothing was connected.")
    if result.get("state") != state:
        raise SignInError("The sign-in reply didn't match this request, so it was ignored. Start the sign-in again.")
    body = json.dumps({"code": result["code"], "code_verifier": verifier, "code_challenge_method": "S256"}).encode()
    req = urllib.request.Request(exchange_url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except urllib.error.HTTPError:
        # OpenRouter's codes here differ from its docs; any refusal means: start again
        raise SignInError("OpenRouter didn't accept the sign-in. Start it again.") from None
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise SignInError(f"Couldn't reach OpenRouter to finish signing in ({e}).") from None
    key = data.get("key") if isinstance(data, dict) else None
    if not isinstance(key, str) or not key:
        raise SignInError("OpenRouter's reply had no key. Start the sign-in again.")
    return key


def credit(key: str, key_url: str = KEY_URL) -> str | None:
    """A short note on the key's spending, e.g. "$2.69 of $3.00 left", or None."""
    req = urllib.request.Request(key_url, headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = (json.load(r) or {}).get("data") or {}
    except (urllib.error.URLError, OSError, ValueError):
        return None
    limit, left, used = data.get("limit"), data.get("limit_remaining"), data.get("usage")
    if isinstance(limit, (int, float)) and isinstance(left, (int, float)):
        return f"${left:.2f} of ${limit:.2f} left"
    if isinstance(used, (int, float)):
        return f"${used:.2f} used, no limit set"
    return None
