"""Unit tests for the companion: model connection, replies, the request loop and settings.

A local fake OpenAI-compatible server plays the AI provider, including the failures seen
with real providers: rate limits, rejected keys, answers that stop halfway, reasoning-only
answers, servers that stall or trickle bytes.
"""
import contextlib
import http.server
import io
import json
import os
import pathlib
import stat
import sys
import tempfile
import threading
import time
import unittest
import zlib
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "companion"))

from gnomecaster import cli, config, demo, prompt, protocol, serve  # noqa: E402
from gnomecaster.brain import Brain  # noqa: E402
from gnomecaster.game import ADDON_DIR  # noqa: E402
from gnomecaster.model import ModelClient, ModelError  # noqa: E402
from gnomecaster.slots import Slots, lua_value  # noqa: E402

GOOD = {"say": "Here is your macro.", "actions": [
    {"type": "macro", "name": "Rejuv", "body": "#showtooltip\n/cast [@mouseover,help,nodead][] Rejuvenation"}]}


def completion(content, finish="stop", **message):
    return {"choices": [{"message": {"content": content, **message}, "finish_reason": finish}]}


class FakeServer:
    """Answers each request with the next scripted response: a dict with status, body, headers,
    delay (seconds before answering) and trickle (seconds between body bytes)."""

    def __init__(self, script, models=None):
        self.script = list(script)
        self.models = models
        self.requests = []
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                server.requests.append({"method": "GET", "path": self.path, "auth": self.headers.get("Authorization")})
                if server.models is None:
                    self._send({"status": 404, "body": {"error": {"message": "no listing"}}})
                else:
                    self._send({"status": 200, "body": {"data": [{"id": m} for m in server.models]}})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                server.requests.append({"method": "POST", "path": self.path, "body": body,
                                        "auth": self.headers.get("Authorization")})
                self._send(server.script.pop(0) if server.script else {"status": 500, "body": {}})

            def _send(self, r):
                time.sleep(r.get("delay", 0))
                raw = r["body"] if isinstance(r.get("body"), bytes) else json.dumps(r.get("body", {})).encode()
                try:
                    self.send_response(r.get("status", 200))
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    for k, v in (r.get("headers") or {}).items():
                        self.send_header(k, v)
                    self.end_headers()
                    if r.get("trickle"):
                        for b in raw:
                            self.wfile.write(bytes([b]))
                            self.wfile.flush()
                            time.sleep(r["trickle"])
                    else:
                        self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/v1"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def posts(self):
        return [r for r in self.requests if r["method"] == "POST"]


class ServerCase(unittest.TestCase):
    def serve(self, *script, models=None):
        s = FakeServer(script, models)
        self.addCleanup(s.close)
        return s

    def client(self, server, deadline=10.0):
        return ModelClient(server.url, "test-model", "sk-test", deadline=deadline)

    def ask(self, server, deadline=10.0):
        return Brain(self.client(server, deadline), ADDON_DIR).answer({"t": "ask", "text": "macro", "ctx": {}})


class ModelConnection(ServerCase):
    def test_answer_with_actions(self):
        s = self.serve({"body": completion(json.dumps(GOOD))})
        reply = self.ask(s)
        self.assertEqual(reply["actions"][0]["type"], "macro")
        self.assertNotIn("error", reply)
        self.assertEqual(s.posts()[0]["auth"], "Bearer sk-test")
        self.assertEqual(s.posts()[0]["body"]["response_format"], {"type": "json_object"})

    def test_json_mode_refused_once_then_remembered(self):
        s = self.serve({"status": 400, "body": {"error": {"message": "response_format not supported"}}},
                       {"body": completion(json.dumps(GOOD))}, {"body": completion(json.dumps(GOOD))})
        client = self.client(s)
        brain = Brain(client, ADDON_DIR)
        self.assertIn("actions", brain.answer({"t": "ask", "text": "x", "ctx": {}}))
        self.assertIn("actions", brain.answer({"t": "ask", "text": "x", "ctx": {}}))
        sent = ["response_format" in r["body"] for r in s.posts()]
        self.assertEqual(sent, [True, False, False])

    def test_reasoning_in_think_tags_is_ignored(self):
        content = '<think>Maybe {"say": "draft"} or a macro {with braces}</think>' + json.dumps(GOOD)
        reply = self.ask(self.serve({"body": completion(content)}))
        self.assertEqual(reply["say"], GOOD["say"])

    def test_actions_only_inside_think_never_run(self):
        content = '<think>{"say":"draft","actions":[{"type":"mark","icon":8}]}</think>Sorry, I cannot help.'
        reply = self.ask(self.serve({"body": completion(content)}))
        self.assertNotIn("actions", reply)
        self.assertEqual(reply["say"], "Sorry, I cannot help.")

    def test_reasoning_only_answer(self):
        reply = self.ask(self.serve({"body": completion(None, reasoning="thinking...")}))
        self.assertEqual(reply["error"], "empty")
        self.assertIn("only thought", reply["say"])

    def test_stopped_with_error_is_retried_once_then_reported(self):
        s = self.serve({"body": completion("Here's a macro. Mouseo", finish="error")},
                       {"body": completion("Here's a", finish="error")})
        reply = self.ask(s, deadline=30)
        self.assertEqual(reply["error"], "provider")
        self.assertEqual(len(s.posts()), 2)

    def test_rejected_key(self):
        reply = self.ask(self.serve({"status": 401, "body": {"error": {"message": "User not found."}}}))
        self.assertEqual(reply["error"], "auth")
        self.assertIn("API key", reply["say"])
        self.assertNotIn("actions", reply)

    def test_rate_limit_waits_and_retries(self):
        s = self.serve({"status": 429, "headers": {"Retry-After": "1"}, "body": {}},
                       {"body": completion(json.dumps(GOOD))})
        started = time.monotonic()
        reply = self.ask(s, deadline=30)
        self.assertIn("actions", reply)
        self.assertGreaterEqual(time.monotonic() - started, 0.9)

    def test_rate_limit_reported_with_wait_time(self):
        s = self.serve({"status": 429, "headers": {"Retry-After": "1"}, "body": {}},
                       {"status": 429, "headers": {"Retry-After": "1"}, "body": {}})
        reply = self.ask(s, deadline=30)
        self.assertEqual(reply["error"], "rate_limit")
        self.assertIn("Try again in 1 second,", reply["say"])

    def test_error_envelope_with_http_200(self):
        reply = self.ask(self.serve({"body": {"error": {"code": 402, "message": "Insufficient credits"}}}))
        self.assertEqual(reply["error"], "credit")

    def test_deadline_holds_against_a_stalled_server(self):
        s = self.serve({"delay": 6, "body": completion(json.dumps(GOOD))})
        started = time.monotonic()
        reply = self.ask(s, deadline=2.0)
        self.assertLess(time.monotonic() - started, 3.0)
        self.assertEqual(len(s.posts()), 1)
        self.assertEqual(reply["error"], "timeout")

    def test_deadline_holds_against_a_trickling_server(self):
        # One byte every 0.2 s never trips a per-read socket timeout; only the overall deadline stops it.
        s = self.serve({"trickle": 0.2, "body": completion(json.dumps(GOOD))})
        started = time.monotonic()
        reply = self.ask(s, deadline=2.0)
        self.assertLess(time.monotonic() - started, 3.0)
        self.assertEqual(len(s.posts()), 1)
        self.assertEqual(reply["error"], "timeout")

    def test_deadline_holds_while_reading_an_error_body(self):
        # error headers arrive at once, the body trickles: the body is read under the deadline too
        s = self.serve({"status": 401, "trickle": 0.2, "body": completion(json.dumps(GOOD))})
        started = time.monotonic()
        reply = self.ask(s, deadline=2.0)
        self.assertLess(time.monotonic() - started, 3.0)
        self.assertNotIn("actions", reply)

    def test_an_echoed_key_is_never_shown(self):
        s = self.serve({"status": 401, "body": {"error": {"message": "Invalid key sk-test (also sk-or-v1-abcdef123456)"}}})
        reply = self.ask(s)
        self.assertNotIn("sk-test", reply["say"])
        self.assertNotIn("sk-or-v1-abcdef123456", reply["say"])
        self.assertIn("<your key>", reply["say"])

    def test_local_server_not_running(self):
        with socket_port() as port:
            pass                        # the port is free again: nothing listens there
        client = ModelClient(f"http://127.0.0.1:{port}/v1", "llama3.1", "")
        with self.assertRaises(ModelError) as e:
            client.complete([{"role": "user", "content": "hi"}])
        self.assertEqual(e.exception.kind, "network")
        self.assertIn("Ollama", e.exception.message)

    def test_check_finds_a_missing_model(self):
        s = self.serve(models=["openai/gpt-6-luna", "anthropic/claude-haiku-5.5"])
        client = ModelClient(s.url, "openai/gpt-6-lune", "sk-test")
        with self.assertRaises(ModelError) as e:
            client.check()
        self.assertIn("openai/gpt-6-luna", e.exception.message)
        self.assertEqual(s.posts(), [])

    def test_check_asks_one_real_question(self):
        s = self.serve({"body": completion('{"say": "ok"}')}, models=["test-model"])
        self.assertIn("answered in", self.client(s).check())
        self.assertEqual(len(s.posts()), 1)


@contextlib.contextmanager
def socket_port():
    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        yield sock.getsockname()[1]


class Replies(ServerCase):
    def test_failed_model_proposes_no_demo_actions(self):
        reply = self.ask(self.serve({"status": 401, "body": {}}))
        self.assertNotIn("actions", reply)

    def test_demo_without_a_model(self):
        reply = Brain(None, ADDON_DIR).answer({"t": "ask", "text": "mark skull", "ctx": {}})
        self.assertTrue(reply["say"].startswith("(demo) "))

    def test_selftest_reports_a_broken_connection(self):
        # one rejection for the startup check, one for the fresh check /gc test makes
        s = self.serve({"status": 401, "body": {}}, {"status": 401, "body": {}}, models=None)
        brain = Brain(self.client(s), ADDON_DIR)
        self.assertFalse(brain.run_check())
        reply = brain.answer({"t": "selftest"})
        self.assertEqual(reply["error"], "setup")
        self.assertIn("API key", reply["say"])

    def test_selftest_checks_the_connection_again(self):
        s = self.serve({"body": completion('{"say": "ok"}')}, {"status": 401, "body": {}}, models=None)
        brain = Brain(self.client(s), ADDON_DIR)
        self.assertTrue(brain.run_check())              # at startup the key worked
        reply = brain.answer({"t": "selftest"})         # since then it was revoked
        self.assertEqual(reply["error"], "setup")
        self.assertIn("API key", reply["say"])

    def test_selftest_in_demo_mode_says_so(self):
        self.assertIn("offline demo", Brain(None, ADDON_DIR).answer({"t": "selftest"})["say"])

    def test_prompt_lists_the_addons_settings_and_forbids_scripts(self):
        cvars, commands = prompt.addon_lists(ADDON_DIR)
        text = prompt.system_prompt(cvars, commands)
        self.assertIn("autoLootDefault", cvars)
        for name in cvars:
            self.assertIn(name, text)
        self.assertIn("Never use /run", text)

    def test_sanitize_drops_junk_without_raising(self):
        self.assertEqual(prompt.sanitize({"say": "x", "actions": 1}), {"say": "x"})
        self.assertEqual(prompt.sanitize({"say": "x", "actions": [{"type": []}, "mark", None]}), {"say": "x"})
        kept = prompt.sanitize({"say": "x", "actions": [{"type": "waypoint", "map": 1, "x": float("nan"),
                                                          "y": 0.5, "nested": {"a": 1}}]})
        self.assertEqual(kept["actions"], [{"type": "waypoint", "map": 1, "y": 0.5}])
        with self.assertRaises(ModelError):
            prompt.sanitize({})

    def test_citation_links_are_dropped_from_the_answer(self):
        # searched answers cite in markdown, which the panel would show as raw text; the sources
        # stay in the transcript
        say = ("Cuzolth upgrades gear in the Bazaar (/way 48.6, 62). ([icy-veins.com](https://www.icy-veins.com/wow/x)) "
               "See [Wowhead](https://www.wowhead.com/npc=1) too.")
        self.assertEqual(prompt.sanitize({"say": say})["say"],
                         "Cuzolth upgrades gear in the Bazaar (/way 48.6, 62). See Wowhead too.")
        self.assertEqual(prompt.sanitize({"say": "[1] is fine (really)"})["say"], "[1] is fine (really)")

    def test_prose_before_an_object_without_say_is_the_answer(self):
        # without JSON mode (searching), openai/gpt-6-luna wrote this on 2026-10-17
        text = ("Der Kartenname lautet offenbar „Atal'Aman“. Ich versuche es damit erneut."
                '{"actions":[{"type":"goto","name":"Atal\'Aman","kind":"delve"}]}')
        reply = prompt.sanitize(prompt.parse_reply(text))
        self.assertEqual(reply["say"], "Der Kartenname lautet offenbar „Atal'Aman“. Ich versuche es damit erneut.")
        self.assertEqual(reply["actions"], [{"type": "goto", "name": "Atal'Aman", "kind": "delve"}])
        kept = prompt.parse_reply('Draft below. {"say": "the real answer"}')
        self.assertEqual(kept["say"], "the real answer")
        two = prompt.parse_reply('Draft {"actions": []} final {"actions": [{"type": "mark", "icon": 8}]}')
        self.assertNotIn("say", two)                    # never another object's JSON as the answer

    def test_prose_without_json_is_the_answer(self):
        text = "Fireball is a Mage spell, so I haven't made a macro."
        self.assertEqual(prompt.sanitize(prompt.parse_reply(text)), {"say": text})
        with self.assertRaises(ModelError):
            prompt.parse_reply('{"say": "broken json')

    def test_long_macro_names_are_shortened_consistently(self):
        reply = prompt.sanitize({"say": "x", "actions": [
            {"type": "macro", "name": "Mouseover Moonfire", "body": "#showtooltip\n/cast Moonfire"},
            {"type": "bar", "macro": "Mouseover Moonfire", "slot": 5},
            {"type": "bind", "key": "F5", "macro": "Mouseover Moonfire"},
            {"type": "macro", "name": "Verjüngungszauber", "body": "/cast X"}]})
        names = [a.get("name") or a.get("macro") for a in reply["actions"]]
        self.assertEqual(names[:3], ["Mouseover Moonfi"] * 3)
        self.assertLessEqual(len(names[3].encode("utf-8")), 16)
        self.assertEqual(names[3], "Verjüngungszaub")

    def test_unknown_action_fields_are_dropped(self):
        reply = prompt.sanitize({"say": "x", "actions": [{"type": "waypoint", "map": 1, "x": 0.4, "y": 0.5,
                                                         "targetChanged": True, "order": 1}]})
        self.assertEqual(reply["actions"], [{"type": "waypoint", "map": 1, "x": 0.4, "y": 0.5}])

    def test_shortened_macro_names_stay_distinct(self):
        reply = prompt.sanitize({"say": "x", "actions": [
            {"type": "macro", "name": "Healing Mouseover One", "body": "/cast A"},
            {"type": "macro", "name": "Healing Mouseover Two", "body": "/cast B"},
            {"type": "bar", "macro": "Healing Mouseover Two", "slot": 6}]})
        one, two, bar = reply["actions"]
        self.assertNotEqual(one["name"], two["name"])
        self.assertEqual(bar["macro"], two["name"])
        self.assertTrue(all(len(a["name"].encode()) <= 16 for a in (one, two)))

    def test_parse_reply_takes_the_last_answer_object(self):
        text = 'First {"say": "draft"} then the final one:\n```json\n{"say": "final"}\n```'
        self.assertEqual(prompt.parse_reply(text)["say"], "final")

    def test_lone_surrogate_cannot_break_the_reply_file(self):
        reply = prompt.sanitize(json.loads('{"say": "Here you go \\ud83d"}'))
        self.assertIn('\\239\\191\\189', lua_value(reply))     # U+FFFD in UTF-8
        lua_value({"say": json.loads('"\\ud83d"')})             # raw, unsanitized: must not raise either

    def test_nan_becomes_nil_not_zero(self):
        self.assertEqual(lua_value({"x": float("nan")}), "{}")


def beacon_png(path, packet):
    """Draws a request the way Beacon.lua does (an independent encoder for the decoder test)."""
    from PIL import Image
    payload = json.dumps(packet).encode()
    data = protocol.MAGIC + bytes([protocol.PROTOCOL, len(payload) // 256, len(payload) % 256]) \
        + zlib.adler32(payload).to_bytes(4, "big") + payload
    bits = "".join(f"{b:08b}" for b in data)
    bits += "0" * (-len(bits) % 3)
    cells = [int(bits[i:i + 3], 2) for i in range(0, len(bits), 3)]
    row0 = protocol.MARKER + [0] * (protocol.GRID_W - 2 * len(protocol.MARKER)) + protocol.MARKER
    rows = [row0] + [cells[i:i + protocol.GRID_W] for i in range(0, len(cells), protocol.GRID_W)]
    img = Image.new("RGB", (640, 480), (40, 90, 40))
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            colour = ((v >> 2 & 1) * 255, (v >> 1 & 1) * 255, (v & 1) * 255)
            for dy in range(3):
                for dx in range(3):
                    img.putpixel((c * 3 + dx, r * 3 + dy), colour)
    img.save(path)


class RequestLoop(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        self.shots = self.root / "Screenshots"
        self.shots.mkdir()
        self.addons = self.root / "AddOns"
        for n in range(1, protocol.NUM_SLOTS + 1):
            (self.addons / f"Gnomecaster_Inbox{n:02d}").mkdir(parents=True)
        self.slots = Slots(self.addons, None)
        self.log = []

    def finished(self, watcher):
        watcher.ready()                 # first sighting records the size
        return watcher.ready()          # second sighting with the same size: finished

    def test_beacon_screenshot_is_answered_and_deleted(self):
        watcher = serve.Watcher(self.shots)
        beacon_png(self.shots / "WoWScrnShot_1.png", {"t": "ask", "rid": 3, "sid": "s", "slot": 2, "text": "mark skull", "ctx": {}})
        [p] = self.finished(watcher)
        self.assertEqual(serve.process(p, watcher, self.slots, Brain(None, ADDON_DIR), self.log.append), "request")
        self.assertFalse(p.exists())
        reply = (self.addons / "Gnomecaster_Inbox02" / "inbox.lua").read_text(encoding="utf-8")
        self.assertIn('["rid"]=3', reply)
        self.assertFalse((self.addons / "Gnomecaster_Inbox01" / "inbox.lua").exists())

    def test_ordinary_screenshot_is_left_alone(self):
        from PIL import Image
        watcher = serve.Watcher(self.shots)
        Image.new("RGB", (640, 480), (200, 30, 200)).save(self.shots / "WoWScrnShot_2.png")
        [p] = self.finished(watcher)
        self.assertEqual(serve.process(p, watcher, self.slots, Brain(None, ADDON_DIR), self.log.append), "ignored")
        self.assertTrue(p.exists())

    def test_truncated_screenshot_is_retried(self):
        watcher = serve.Watcher(self.shots)
        full = self.root / "full.png"
        beacon_png(full, {"t": "ask", "rid": 1, "sid": "s", "slot": 1, "text": "x", "ctx": {}})
        target = self.shots / "WoWScrnShot_3.png"
        target.write_bytes(full.read_bytes()[:200])
        [p] = self.finished(watcher)
        self.assertEqual(serve.process(p, watcher, self.slots, Brain(None, ADDON_DIR), self.log.append), "error")
        target.write_bytes(full.read_bytes())
        [p] = self.finished(watcher)
        self.assertEqual(serve.process(p, watcher, self.slots, Brain(None, ADDON_DIR), self.log.append), "request")

    def test_a_reply_that_could_not_be_written_is_retried(self):
        watcher = serve.Watcher(self.shots)
        beacon_png(self.shots / "WoWScrnShot_4.png", {"t": "ask", "rid": 5, "sid": "s", "slot": 1, "text": "x", "ctx": {}})
        real = Slots.deliver
        calls = []

        def flaky(slots_self, *a, **k):
            calls.append(1)
            if len(calls) == 1:
                raise PermissionError("locked by a virus scanner")
            return real(slots_self, *a, **k)

        with mock.patch.object(Slots, "deliver", flaky):
            [p] = self.finished(watcher)
            self.assertEqual(serve.process(p, watcher, self.slots, Brain(None, ADDON_DIR), self.log.append), "error")
            self.assertTrue(p.exists())
            [p] = self.finished(watcher)
            self.assertEqual(serve.process(p, watcher, self.slots, Brain(None, ADDON_DIR), self.log.append), "request")
        self.assertFalse(p.exists())
        self.assertIn('["rid"]=5', (self.addons / "Gnomecaster_Inbox01" / "inbox.lua").read_text(encoding="utf-8"))

    def test_handle_never_raises(self):
        class Broken:
            def answer(self, packet):
                raise RuntimeError("boom")
        written = serve.handle({"t": "ask", "rid": 9, "sid": "s", "slot": 1}, self.slots, Broken(), self.log.append)
        self.assertTrue(written)
        self.assertIn("internal error", (self.addons / "Gnomecaster_Inbox01" / "inbox.lua").read_text(encoding="utf-8"))


class Settings(ServerCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = pathlib.Path(tmp.name) / "config.json"
        env = {k: v for k, v in os.environ.items() if not k.startswith("GNOMECASTER_")}
        env["GNOMECASTER_CONFIG"] = str(self.path)
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_environment_overrides_the_file(self):
        config.save_file({"base_url": "https://a.example/v1", "model": "file-model", "api_key": "k"})
        os.environ["GNOMECASTER_MODEL"] = "env-model"
        s = config.resolve()
        self.assertEqual((s.base_url, s.model, s.api_key), ("https://a.example/v1", "env-model", "k"))

    def test_ollama_is_reached_where_it_listens(self):
        # Ollama binds 127.0.0.1:11434 unless OLLAMA_HOST says otherwise (its envconfig.Host)
        self.assertEqual(config.PRESETS["ollama"]["base_url"], "http://127.0.0.1:11434/v1")

    def test_settings_from_1_0_0_reach_ollama_where_it_listens(self):
        config.save_file({"provider": "ollama", "base_url": "http://localhost:11434/v1", "model": "llama3.1"})
        self.assertEqual(config.load_file()["base_url"], "http://127.0.0.1:11434/v1")
        self.assertEqual(config.resolve().base_url, "http://127.0.0.1:11434/v1")
        for own in ({"provider": "custom", "base_url": "http://localhost:11434/v1", "model": "m"},
                    {"provider": "custom", "base_url": "http://localhost:8080/v1", "model": "m"}):
            config.save_file(own)                                   # an address the player chose
            self.assertEqual(config.load_file()["base_url"], own["base_url"])

    @unittest.skipIf(sys.platform == "win32", "POSIX permissions")
    def test_settings_file_is_private(self):
        config.save_file({"api_key": "k"})
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_setup_checks_saves_and_never_prints_the_key(self):
        s = self.serve({"body": completion('{"say": "ok"}')}, models=["test-model"])
        os.environ["TEST_KEY"] = "sk-secret-123"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.main(["setup", "--provider", "custom", "--base-url", s.url, "--model", "test-model",
                      "--key-env", "TEST_KEY", "--wow", "/nonexistent", "--yes"])
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual((saved["model"], saved["api_key"]), ("test-model", "sk-secret-123"))
        self.assertIn("OK: answered in", out.getvalue())
        self.assertNotIn("sk-secret-123", out.getvalue())

    def test_setup_refuses_to_save_a_broken_connection(self):
        s = self.serve({"status": 401, "body": {}}, models=None)
        os.environ["TEST_KEY"] = "bad"
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            cli.main(["setup", "--provider", "custom", "--base-url", s.url, "--model", "m",
                      "--key-env", "TEST_KEY", "--wow", "/nonexistent", "--yes"])
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
