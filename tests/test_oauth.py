"""Sign in with OpenRouter (OAuth PKCE), against a fake OpenRouter that checks the cryptography."""
import hashlib
import base64
import http.server
import json
import pathlib
import socket
import sys
import threading
import unittest
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "companion"))

from gnomecaster import oauth  # noqa: E402


def lan_address():
    """This machine's address on its network, or None. Connecting a UDP socket sends nothing."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 9))     # TEST-NET-1: never routed anywhere real
            address = s.getsockname()[0]
        except OSError:
            return None
    return None if address.startswith("127.") else address


class FakeOpenRouter:
    """Issues one code per approval and swaps it for a key only with the matching verifier."""

    def __init__(self, exchange_status=200, key_data=None):
        self.codes = {}                 # code -> code_challenge
        self.exchange_status = exchange_status
        self.key_data = key_data
        self.exchanges = []
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, status, obj):
                body = json.dumps(obj).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                server.exchanges.append(body)
                challenge = server.codes.pop(body.get("code"), None)
                digest = base64.urlsafe_b64encode(hashlib.sha256(body.get("code_verifier", "").encode()).digest()).rstrip(b"=").decode()
                if server.exchange_status != 200:
                    self._json(server.exchange_status, {"error": {"message": "Invalid code", "code": server.exchange_status}})
                elif challenge is None or digest != challenge:
                    self._json(403, {"error": {"message": "Invalid code or code_verifier", "code": 403}})
                else:
                    self._json(200, {"key": "sk-or-v1-fresh", "user_id": "user_1"})

            def do_GET(self):
                self._json(200, {"data": server.key_data or {}})

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def browser(self, approve=True, state=None):
        """Plays the player's browser: OpenRouter's page, then the redirect back to the app."""
        def open_browser(url):
            q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).items()}
            self.last_auth = q
            back = {"state": state if state is not None else q["state"]}
            if approve:
                back["code"] = "code-123"
                self.codes["code-123"] = q["code_challenge"]

            def redirect():
                urllib.request.urlopen(q["callback_url"] + "?" + urllib.parse.urlencode(back), timeout=10).read()
            threading.Thread(target=redirect, daemon=True).start()
            return True
        return open_browser


class SignIn(unittest.TestCase):
    def setUp(self):
        self.fake = FakeOpenRouter()
        self.addCleanup(self.fake.close)

    def sign_in(self, browser, **kw):
        return oauth.sign_in(open_browser=browser, auth_url=self.fake.url + "/auth",
                             exchange_url=self.fake.url + "/api/v1/auth/keys", **kw)

    def test_approval_yields_a_key(self):
        key = self.sign_in(self.fake.browser())
        self.assertEqual(key, "sk-or-v1-fresh")
        q = self.fake.last_auth
        self.assertEqual(q["code_challenge_method"], "S256")
        self.assertEqual(q["key_label"], "Gnomecaster")
        self.assertTrue(q["callback_url"].startswith("http://127.0.0.1:"))
        self.assertEqual(self.fake.exchanges[0]["code_challenge_method"], "S256")

    def test_the_callback_listener_is_loopback_only(self):
        lan = lan_address()
        if lan is None:
            self.skipTest("this machine has no network address besides loopback")
        reachable = []
        approve = self.fake.browser()

        def browser(url):
            port = urllib.parse.urlsplit(dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))["callback_url"]).port
            try:
                socket.create_connection((lan, port), timeout=2).close()
                reachable.append(True)
            except OSError:
                reachable.append(False)
            return approve(url)
        self.sign_in(browser)
        self.assertEqual(urllib.parse.urlsplit(self.fake.last_auth["callback_url"]).hostname, "127.0.0.1")
        self.assertEqual(reachable, [False])

    def test_an_idle_connection_does_not_block_the_redirect(self):
        idle = []
        approve = self.fake.browser()

        def browser(url):                   # like a browser preconnect: a socket that never sends
            callback = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))["callback_url"]
            idle.append(socket.create_connection(("127.0.0.1", urllib.parse.urlsplit(callback).port)))
            return approve(url)
        result = {}
        t = threading.Thread(target=lambda: result.setdefault("key", self.sign_in(browser, wait=20)), daemon=True)
        t.start()
        t.join(8)
        for s in idle:
            s.close()
        self.assertFalse(t.is_alive(), "sign-in waited on the idle connection")
        self.assertEqual(result.get("key"), "sk-or-v1-fresh")

    def test_denial_connects_nothing(self):
        with self.assertRaisesRegex(oauth.SignInError, "cancelled in the browser"):
            self.sign_in(self.fake.browser(approve=False))
        self.assertEqual(self.fake.exchanges, [])

    def test_a_forged_callback_is_ignored(self):
        with self.assertRaisesRegex(oauth.SignInError, "didn't match"):
            self.sign_in(self.fake.browser(state="attacker"))
        self.assertEqual(self.fake.exchanges, [])

    def test_a_refused_exchange_says_start_again(self):
        self.fake.exchange_status = 400
        with self.assertRaisesRegex(oauth.SignInError, "Start it again"):
            self.sign_in(self.fake.browser())

    def test_no_browser(self):
        with self.assertRaisesRegex(oauth.SignInError, "Couldn't open your web browser"):
            self.sign_in(lambda url: False, wait=5)

    def test_walking_away_times_out(self):
        with self.assertRaisesRegex(oauth.SignInError, "took too long"):
            self.sign_in(lambda url: True, wait=0.5)

    def test_the_app_can_cancel(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaisesRegex(oauth.SignInError, "cancelled"):
            self.sign_in(lambda url: True, cancel=cancel, wait=5)


class Credit(unittest.TestCase):
    def test_limit_and_remaining(self):
        fake = FakeOpenRouter(key_data={"limit": 3, "limit_remaining": 2.6912, "usage": 0.31})
        self.addCleanup(fake.close)
        self.assertEqual(oauth.credit("k", key_url=fake.url + "/api/v1/key"), "$2.69 of $3.00 left")

    def test_no_limit(self):
        fake = FakeOpenRouter(key_data={"limit": None, "limit_remaining": None, "usage": 0.31})
        self.addCleanup(fake.close)
        self.assertEqual(oauth.credit("k", key_url=fake.url + "/api/v1/key"), "$0.31 used, no limit set")

    def test_unreachable_is_quiet(self):
        self.assertIsNone(oauth.credit("k", key_url="http://127.0.0.1:9/api/v1/key"))


if __name__ == "__main__":
    unittest.main()
