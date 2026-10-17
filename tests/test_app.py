"""The desktop app's backend: the calls the window makes (desktop/ui/api.js), against a fake
game folder, a fake OpenRouter sign-in and a fake model server. pywebview and pystray are
replaced by small fakes; the window itself is checked in a browser (docs/PROGRESS.md)."""
import functools
import json
import os
import pathlib
import re
import socket
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "companion"))

from gnomecaster import __version__, app, app_api, config, game, oauth, serve, service, winsys  # noqa: E402
from gnomecaster.brain import Brain  # noqa: E402
from test_companion import FakeServer, beacon_png, completion  # noqa: E402
from test_oauth import FakeOpenRouter  # noqa: E402

LUNA = config.MODELS["openrouter"][0]["id"]


class FakeSystem:
    """winsys with the real folder search, and autostart and Explorer recorded in memory."""
    find_games = staticmethod(winsys.find_games)
    flavors_in = staticmethod(winsys.flavors_in)

    def __init__(self, data: pathlib.Path):
        self.autostart = None
        self.opened = []
        self.data = data

    def autostart_enabled(self):
        return self.autostart is not None

    def set_autostart(self, on, command):
        self.autostart = command if on else None
        return True

    def data_dir(self):
        return self.data

    def open_folder(self, path):
        self.opened.append(path)


class AppCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.config = self.tmp / "config.json"
        self.wow = self.tmp / "World of Warcraft"
        for flavor in ("_retail_", "_classic_era_"):
            (self.wow / flavor).mkdir(parents=True)
        self.retail = str(self.wow / "_retail_")
        self.events = []
        self.event = threading.Event()
        self.companion_changes = []
        self.chosen = None
        self.system = FakeSystem(self.tmp / "data")
        self.presets = {k: dict(v) for k, v in config.PRESETS.items()}
        # a World of Warcraft installed on the machine running the tests must not count
        for patch in (mock.patch.object(winsys, "registry_wow_root", return_value=None),
                      mock.patch.object(game, "GUESSES", [])):
            patch.start()
            self.addCleanup(patch.stop)

    def api(self, **kw):
        def emit(event):
            self.events.append(event)
            self.event.set()
        options = dict(config_path=self.config, emit=emit, on_companion=self.companion_changes.append,
                       choose_folder=lambda: self.chosen, autostart_command='"Gnomecaster.exe" --background',
                       system=self.system, presets=self.presets)
        options.update(kw)
        api = app_api.Api(**options)
        self.addCleanup(api._stop)
        return api

    def saved(self):
        return json.loads(self.config.read_text())

    def model_server(self, *script):
        s = FakeServer(script, models=[m["id"] for m in config.MODELS["openrouter"]])
        self.addCleanup(s.close)
        self.presets["openrouter"]["base_url"] = s.url
        return s

    def openrouter(self, **kw):
        fake = FakeOpenRouter(**kw)
        self.addCleanup(fake.close)
        sign_in = functools.partial(oauth.sign_in, open_browser=fake.browser(), auth_url=fake.url + "/auth",
                                    exchange_url=fake.url + "/api/v1/auth/keys")
        credit = functools.partial(oauth.credit, key_url=fake.url + "/api/v1/key")
        return fake, sign_in, credit


class Contract(unittest.TestCase):
    def test_the_window_and_the_backend_offer_the_same_calls(self):
        source = (ROOT / "desktop" / "ui" / "api.js").read_text()
        mock_calls = set(re.findall(r"^\s+async (\w+)\(", source, re.M))
        used = set(re.findall(r'GC\.call\("(\w+)"', (ROOT / "desktop" / "ui" / "app.js").read_text()))
        public = {n for n in dir(app_api.Api) if not n.startswith("_")}
        self.assertEqual(public, mock_calls)
        self.assertLessEqual(used, public)

    def test_nothing_else_is_exposed_to_the_page(self):
        # pywebview exposes public attributes recursively; only the calls may be public
        with tempfile.TemporaryDirectory() as d:
            api = app_api.Api(config_path=pathlib.Path(d) / "c.json", system=FakeSystem(pathlib.Path(d)))
            exposed = {n for n in dir(api) if not n.startswith("_")}
            self.assertTrue(all(callable(getattr(api, n)) for n in exposed))
            self.assertEqual(exposed, {n for n in dir(app_api.Api) if not n.startswith("_")})

    def test_the_installer_closes_the_app_by_the_mutex_it_holds(self):
        iss = (ROOT / "packaging" / "gnomecaster.iss").read_text()
        self.assertEqual(re.search(r'^#define AppMutex "([^"]+)"', iss, re.M).group(1), app.MUTEX)

    def test_the_installer_closes_the_app_only_once_the_player_has_chosen(self):
        # Inno checks AppMutex, and runs InitializeSetup and InitializeUninstall, before the
        # player has confirmed anything; PrepareToInstall and usAppMutexCheck come after
        iss = (ROOT / "packaging" / "gnomecaster.iss").read_text()
        self.assertIsNone(re.search(r"^AppMutex=", iss, re.M))
        calls = {m.group(1) for m in re.finditer(r"^(?:function|procedure) (\w+)[^\n]*\n(?:(?!^(?:function|procedure) ).*\n)*?.*\bCloseRunning\b", iss, re.M)}
        self.assertEqual(calls, {"PrepareToInstall", "CurUninstallStepChanged"})
        self.assertIn("usAppMutexCheck) and not CloseRunning", iss)

    def test_the_installer_shows_its_own_images_in_dark_mode(self):
        iss = (ROOT / "packaging" / "gnomecaster.iss").read_text()
        directives = dict(re.findall(r"^(Wizard\w*ImageFile\w*)=(.+)$", iss, re.M))
        self.assertEqual(directives, {"WizardImageFile": "{#SideImages}", "WizardSmallImageFile": "{#SmallImages}",
                                      "WizardImageFileDynamicDark": "{#SideImages}",
                                      "WizardSmallImageFileDynamicDark": "{#SmallImages}"})
        for name in ("SideImages", "SmallImages"):
            files = re.search(rf'^#define {name} "([^"]+)"', iss, re.M).group(1).split(",")
            self.assertTrue(files)
            for f in files:
                self.assertTrue((ROOT / "packaging" / f.replace("\\", "/")).is_file(), f)

    def test_addon_and_app_share_one_version(self):
        toc = (ROOT / "addon" / "Gnomecaster" / "Gnomecaster.toc").read_text()
        self.assertEqual(re.search(r"^## Version: (\S+)", toc, re.M).group(1), __version__)


class Setup(AppCase):
    def test_fresh_start(self):
        state = self.api().getState()
        self.assertEqual((state["setupDone"], state["games"], state["game"], state["ai"]), (False, [], None, None))
        self.assertEqual(state["version"], __version__)
        self.assertEqual([m["id"] for m in state["models"]][0], LUNA)
        self.assertFalse(state["companion"]["running"])

    def test_the_game_found_by_itself_is_preselected(self):
        with mock.patch.object(winsys, "registry_wow_root", return_value=self.wow):
            state = self.api().getState()
        self.assertEqual(len(state["games"]), 2)
        self.assertEqual(state["game"], self.retail)

    def test_a_folder_without_the_game_is_refused(self):
        api = self.api()
        self.chosen = str(self.tmp)
        r = api.chooseGameFolder()
        self.assertFalse(r["ok"])
        self.assertIn("_retail_", r["message"])
        self.assertFalse(self.config.exists())

    def test_choosing_the_game_folder_lists_versions_and_prefers_retail(self):
        api = self.api()
        self.chosen = str(self.wow)
        self.assertTrue(api.chooseGameFolder()["ok"])
        state = api.getState()
        self.assertEqual(sorted(g["name"] for g in state["games"]), ["Classic Era", "Retail"])
        self.assertEqual(state["game"], self.retail)
        self.assertEqual(self.saved()["roots"], [str(self.wow)])
        # the choice survives a restart of the app
        self.assertEqual(self.api().getState()["game"], self.retail)

    def test_choosing_a_version_folder_selects_that_version(self):
        api = self.api()
        self.chosen = str(self.wow / "_classic_era_")
        self.assertTrue(api.chooseGameFolder()["ok"])
        self.assertEqual(api.getState()["game"], str(self.wow / "_classic_era_"))

    def test_select_game_accepts_only_listed_versions(self):
        api = self.api()
        self.chosen = str(self.wow)
        api.chooseGameFolder()
        self.assertFalse(api.selectGame({"id": str(self.tmp)})["ok"])
        self.assertTrue(api.selectGame({"id": str(self.wow / "_classic_era_")})["ok"])
        self.assertEqual(api.getState()["game"], str(self.wow / "_classic_era_"))

    def test_install_then_update(self):
        api = self.api()
        self.chosen = str(self.wow)
        api.chooseGameFolder()
        r = api.installAddon({"id": self.retail})
        self.assertTrue(r["ok"])
        self.assertTrue(r["message"].startswith("Installed."))
        self.assertEqual({g["id"]: g["addon"] for g in api.getState()["games"]},
                         {self.retail: "current", str(self.wow / "_classic_era_"): "missing"})
        core = self.wow / "_retail_" / "Interface" / "AddOns" / "Gnomecaster" / "Core.lua"
        core.write_text("-- changed")
        retail = next(g for g in api.getState()["games"] if g["id"] == self.retail)
        self.assertEqual(retail["addon"], "outdated")
        r = api.installAddon({})            # defaults to the selected version
        self.assertTrue(r["message"].startswith("Updated."))
        self.assertNotEqual(core.read_text(), "-- changed")

    def test_install_points_at_the_old_prototype(self):
        (self.wow / "_retail_" / "Interface" / "AddOns" / "Wowpilot").mkdir(parents=True)
        api = self.api()
        self.chosen = str(self.wow)
        api.chooseGameFolder()
        self.assertIn("Wowpilot", api.installAddon({})["message"])

    @unittest.skipIf(sys.platform == "win32" or os.geteuid() == 0, "POSIX permissions, not as root")
    def test_a_refused_install_says_so(self):
        addons = self.wow / "_retail_" / "Interface" / "AddOns"
        addons.mkdir(parents=True)
        addons.chmod(0o500)
        self.addCleanup(addons.chmod, 0o700)
        api = self.api()
        self.chosen = str(self.wow)
        api.chooseGameFolder()
        r = api.installAddon({})
        self.assertFalse(r["ok"])
        self.assertIn("refused", r["message"])

    def test_install_without_a_game(self):
        self.assertFalse(self.api().installAddon({})["ok"])


class Connect(AppCase):
    def test_sign_in_connects_and_the_key_never_reaches_the_page(self):
        self.model_server({"body": completion('{"say": "ok"}')})
        fake, sign_in, credit = self.openrouter(key_data={"limit": 5, "limit_remaining": 4.5, "usage": 0.5})
        api = self.api(sign_in=sign_in, credit=credit)
        r = api.signIn()
        self.assertTrue(r["ok"], r)
        self.assertRegex(r["message"], r"^Connected\. Test question answered in \d+\.\d s\.$")
        saved = self.saved()
        self.assertEqual((saved["provider"], saved["account"], saved["api_key"], saved["model"]),
                         ("openrouter", "oauth", "sk-or-v1-fresh", LUNA))
        state = api.getState()
        self.assertEqual((state["ai"]["ok"], state["ai"]["account"], state["ai"]["credit"]),
                         (True, "Signed in with OpenRouter", "$4.50 of $5.00 left"))
        self.assertNotIn("sk-or-v1-fresh", json.dumps(state))

    def test_sign_in_without_credit_keeps_the_key_to_test_again(self):
        server = self.model_server({"status": 402, "body": {"error": {"message": "Insufficient credits", "code": 402}}},
                                   {"body": completion('{"say": "ok"}')})
        _, sign_in, credit = self.openrouter()
        api = self.api(sign_in=sign_in, credit=credit)
        r = api.signIn()
        self.assertFalse(r["ok"])
        self.assertEqual(r["message"], "Signed in, but the test question failed. Your OpenRouter account is "
                                       "out of credit. Add credit, then test again.")
        self.assertEqual(self.saved()["api_key"], "sk-or-v1-fresh")
        self.assertEqual((api.getState()["ai"]["ok"], api.getState()["ai"]["needsCredit"]), (False, True))
        opened = []
        api._open_browser = opened.append
        api.openCredits()
        self.assertEqual(opened, ["https://openrouter.ai/credits"])
        r = api.checkConnection()           # after adding credit
        self.assertTrue(r["ok"], r)
        self.assertEqual((api.getState()["ai"]["ok"], api.getState()["ai"]["needsCredit"]), (True, False))
        self.assertEqual(server.posts()[-1]["auth"], "Bearer sk-or-v1-fresh")

    def test_a_cancelled_sign_in_changes_nothing(self):
        fake = FakeOpenRouter()
        self.addCleanup(fake.close)
        sign_in = functools.partial(oauth.sign_in, open_browser=fake.browser(approve=False),
                                    auth_url=fake.url + "/auth", exchange_url=fake.url + "/api/v1/auth/keys")
        api = self.api(sign_in=sign_in)
        r = api.signIn()
        self.assertFalse(r["ok"])
        self.assertIn("cancelled", r["message"])
        self.assertFalse(self.config.exists())
        self.assertIsNone(api.getState()["ai"])

    def test_a_new_sign_in_cancels_the_one_still_waiting(self):
        started = threading.Event()
        cancels = []

        def slow_sign_in(cancel):
            cancels.append(cancel)
            started.set()
            cancel.wait(10)
            raise oauth.SignInError("Sign-in was cancelled.")
        api = self.api(sign_in=slow_sign_in)
        first = threading.Thread(target=api.signIn)
        first.start()
        started.wait(5)
        started.clear()
        second = threading.Thread(target=api.signIn)
        second.start()
        started.wait(5)
        self.assertTrue(cancels[0].is_set())
        self.assertFalse(cancels[1].is_set())
        api._stop()                         # quitting cancels the second
        first.join(5)
        second.join(5)
        self.assertTrue(cancels[1].is_set())

    def test_out_of_credit_elsewhere_offers_no_openrouter_button(self):
        s = FakeServer([{"status": 402, "body": {"error": {"message": "quota", "code": 402}}}], models=["gpt-6-luna"])
        self.addCleanup(s.close)
        self.presets["openai"]["base_url"] = s.url
        config.save_file({"provider": "openai", "base_url": s.url, "model": "gpt-6-luna", "api_key": "k"}, self.config)
        api = self.api()
        r = api.checkConnection()
        self.assertIn("out of credit", r["message"])
        self.assertNotIn("OpenRouter", r["message"])
        self.assertFalse(api.getState()["ai"]["needsCredit"])

    def test_a_replaced_sign_in_does_not_overwrite_the_newer_one(self):
        server = self.model_server({"body": completion('{"say": "ok"}'), "delay": 1.5},
                                   {"body": completion('{"say": "ok"}')})
        keys = iter(["sk-or-v1-first", "sk-or-v1-second"])
        api = self.api(sign_in=lambda cancel: next(keys), credit=lambda key: None)
        results = {}
        first = threading.Thread(target=lambda: results.setdefault("first", api.signIn()))
        first.start()
        deadline = time.monotonic() + 10
        while not server.posts() and time.monotonic() < deadline:   # the first is testing its key
            time.sleep(0.05)
        results["second"] = api.signIn()
        first.join(10)
        self.assertTrue(results["second"]["ok"], results)
        self.assertEqual(results["first"], {"ok": False, "message": "Sign-in was cancelled."})
        self.assertEqual(self.saved()["api_key"], "sk-or-v1-second")

    def test_the_player_can_cancel_a_sign_in_waiting_on_the_browser(self):
        waiting = threading.Event()

        def browser_step(cancel):
            waiting.set()
            if cancel.wait(10):
                raise oauth.SignInError("Sign-in was cancelled.")
            return "sk-or-v1-late"
        api = self.api(sign_in=browser_step)
        result = {}
        t = threading.Thread(target=lambda: result.setdefault("r", api.signIn()))
        t.start()
        self.assertTrue(waiting.wait(5))
        started = time.monotonic()
        self.assertEqual(api.cancelSignIn(), {"ok": True})
        t.join(5)
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual(result["r"], {"ok": False, "message": "Sign-in was cancelled."})
        self.assertFalse(self.config.exists())
        self.assertEqual(api.cancelSignIn(), {"ok": True})        # nothing waiting: harmless

    def test_key_pages_and_the_provider_list(self):
        opened = []
        api = self.api(open_browser=opened.append)
        providers = api.getState()["providers"]
        self.assertEqual([p["id"] for p in providers], ["openrouter", "openai", "ollama"])
        self.assertEqual([p["key"] for p in providers], [True, True, False])
        self.assertEqual(api.openKeyPage({"provider": "openrouter"}), {"ok": True})
        self.assertFalse(api.openKeyPage({"provider": "ollama"})["ok"])
        self.assertFalse(api.openKeyPage({"provider": "https://evil.example"})["ok"])
        self.assertEqual(opened, ["https://openrouter.ai/keys"])

    def test_a_rejected_key_is_not_saved(self):
        self.model_server({"status": 401, "body": {"error": {"message": "No auth credentials found"}}})
        api = self.api()
        r = api.saveKey({"provider": "openrouter", "key": "sk-or-v1-wrong"})
        self.assertFalse(r["ok"])
        self.assertIn("rejected the API key", r["message"])
        self.assertNotIn("sk-or-v1-wrong", r["message"])
        self.assertFalse(self.config.exists())

    def test_a_working_key_is_saved(self):
        self.model_server({"body": completion('{"say": "ok"}')})
        api = self.api()
        r = api.saveKey({"provider": "openrouter", "key": " sk-or-v1-mine "})
        self.assertTrue(r["ok"], r)
        self.assertEqual((self.saved()["api_key"], self.saved()["account"]), ("sk-or-v1-mine", "key"))
        self.assertEqual(api.getState()["ai"]["account"], "Using your own OpenRouter key")

    def test_save_key_checks_its_input(self):
        api = self.api()
        self.assertEqual(api.saveKey({"provider": "openrouter", "key": ""})["message"], "Paste a key first.")
        self.assertFalse(api.saveKey({"provider": "custom", "key": "k"})["ok"])
        self.assertFalse(self.config.exists())

    def test_only_offered_models_can_be_chosen_and_each_is_checked(self):
        self.model_server({"body": completion('{"say": "ok"}')}, {"body": completion('{"say": "ok"}')})
        api = self.api()
        api.saveKey({"provider": "openrouter", "key": "k"})
        self.assertFalse(api.setModel({"id": "someone/else"})["ok"])
        other = config.MODELS["openrouter"][1]["id"]
        self.event.clear()
        self.assertTrue(api.setModel({"id": other})["ok"])
        self.assertEqual(self.saved()["model"], other)
        self.assertTrue(self.event.wait(10))        # the check in the background reports back
        self.assertEqual(self.events[-1], {"type": "state"})
        state = api.getState()
        self.assertEqual((state["ai"]["model"], state["ai"]["ok"]), (other, True))

    def test_the_connection_is_checked_at_start(self):
        self.model_server({"body": completion('{"say": "ok"}')})
        config.save_file({"provider": "openrouter", "base_url": self.presets["openrouter"]["base_url"],
                          "model": LUNA, "api_key": "k", "account": "key"}, self.config)
        api = self.api()
        self.assertIsNone(api.getState()["ai"]["ok"])
        self.assertEqual(api.getState()["ai"]["note"], "Checking the connection")
        api._start()
        self.assertTrue(self.event.wait(10))
        self.assertIs(api.getState()["ai"]["ok"], True)


class Running(AppCase):
    def ready_game(self, api):
        self.chosen = str(self.wow)
        api.chooseGameFolder()
        api.installAddon({})

    def test_questions_from_the_game_appear_in_the_window(self):
        api = self.api()
        self.ready_game(api)
        api.finishSetup()
        self.assertTrue(api.getState()["companion"]["running"])
        self.assertEqual(self.companion_changes, [True])
        shots = self.wow / "_retail_" / "Screenshots"
        beacon_png(shots / "WoWScrnShot_1.png", {"t": "ask", "rid": 4, "sid": "s", "slot": 1, "text": "mark skull", "ctx": {}})
        inbox = self.wow / "_retail_" / "Interface" / "AddOns" / "Gnomecaster_Inbox01" / "inbox.lua"
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not (inbox.exists() and '["rid"]=4' in inbox.read_text()):
            time.sleep(0.1)
        self.assertIn('["rid"]=4', inbox.read_text())
        kinds = [(e["type"], e["entry"].get("pending", False)) for e in self.events if e["type"] != "state"]
        self.assertEqual(kinds, [("question", True), ("answer", False)])
        answer = self.events[-1]["entry"]
        self.assertEqual(answer["question"], "mark skull")
        self.assertTrue(answer["answer"].startswith("(demo)"))
        self.assertEqual(api.getState()["activity"], [answer])
        [item] = api.getHistory({"limit": 5})["items"]
        self.assertEqual((item["question"], item["conv"], item["model"]), ("mark skull", "sid:s", "demo"))
        self.assertTrue(item["reply"]["say"].startswith("(demo)"))
        api.setCompanion({"running": False})
        self.assertFalse(api.getState()["companion"]["running"])
        self.assertEqual(self.companion_changes, [True, False])

    def test_setup_resumes_listening_after_a_restart(self):
        api = self.api()
        self.ready_game(api)
        api.finishSetup()
        api._stop()
        again = self.api()
        self.assertFalse(again.getState()["companion"]["running"])
        again._start()
        self.assertTrue(again.getState()["companion"]["running"])

    def test_setup_is_finished_only_when_listening_started(self):
        api = self.api()
        r = api.finishSetup()
        self.assertFalse(r["ok"])
        self.assertFalse(self.config.exists() and self.saved().get("setup_done"))
        self.ready_game(api)
        self.assertEqual(api.finishSetup(), {"ok": True})
        self.assertTrue(self.saved()["setup_done"])

    def test_cannot_listen_without_a_game(self):
        r = self.api().setCompanion({"running": True})
        self.assertFalse(r["ok"])


def companion_threads(before=()):
    return [t for t in threading.enumerate() if t.name == "companion" and t.is_alive() and t not in before]


class Lifecycle(AppCase):
    def flavor(self):
        flavor = self.wow / "_retail_"
        for n in range(1, 61):
            (flavor / "Interface" / "AddOns" / f"Gnomecaster_Inbox{n:02d}").mkdir(parents=True, exist_ok=True)
        return flavor

    def test_two_starts_at_once_leave_one_worker(self):
        from gnomecaster.slots import Slots
        real = Slots.clear_probes

        def slow(slots, start=1):           # widens the window between stopping and starting
            time.sleep(0.3)
            real(slots, start)
        companion = service.Companion()
        flavor = self.flavor()
        before = set(companion_threads())
        with mock.patch.object(Slots, "clear_probes", slow):
            starters = [threading.Thread(target=companion.start, args=(flavor, Brain(None, game.ADDON_DIR)))
                        for _ in range(2)]
            for t in starters:
                t.start()
            for t in starters:
                t.join(10)
        self.assertEqual(len(companion_threads(before)), 1)
        companion.stop()
        self.assertEqual(companion_threads(before), [])

    def test_a_question_asked_right_after_start_is_answered_however_late_the_thread_runs(self):
        # The worker thread may first run after the game took the screenshot (seen on a
        # loaded machine); the folder must already have been looked at when start() returns.
        written, answered = threading.Event(), threading.Event()
        real = serve.Watcher

        def late_watcher(folder):
            if threading.current_thread().name == "companion":
                written.wait(10)            # this thread got to run only after the screenshot
            return real(folder)

        class Answers:
            client = None

            def answer(self, packet):
                answered.set()
                return {"say": "x"}
        companion = service.Companion()
        flavor = self.flavor()
        with mock.patch.object(serve, "Watcher", late_watcher):
            companion.start(flavor, Answers())
            beacon_png(flavor / "Screenshots" / "WoWScrnShot_5.png", {"t": "ask", "rid": 5, "sid": "s", "slot": 1, "text": "hi", "ctx": {}})
            written.set()
            self.assertTrue(answered.wait(10))
        companion.stop()

    def test_pausing_waits_for_the_question_in_progress(self):
        entered, release = threading.Event(), threading.Event()

        class Slow:
            client = None

            def answer(self, packet):
                entered.set()
                release.wait(10)
                return {"say": "late answer"}
        companion = service.Companion()
        flavor = self.flavor()
        before = set(companion_threads())
        companion.start(flavor, Slow())
        beacon_png(flavor / "Screenshots" / "WoWScrnShot_9.png", {"t": "ask", "rid": 7, "sid": "s", "slot": 1, "text": "hi", "ctx": {}})
        self.assertTrue(entered.wait(10))
        stopper = threading.Thread(target=companion.stop)
        stopper.start()
        stopper.join(0.5)
        self.assertTrue(stopper.is_alive())          # still answering
        release.set()
        stopper.join(10)
        self.assertFalse(stopper.is_alive())
        self.assertEqual(companion_threads(before), [])
        inbox = flavor / "Interface" / "AddOns" / "Gnomecaster_Inbox01" / "inbox.lua"
        self.assertIn("late answer", inbox.read_text())

    def test_quitting_the_app_does_not_wait_for_an_answer(self):
        entered, release = threading.Event(), threading.Event()

        class Stuck:
            client = None

            def answer(self, packet):
                entered.set()
                release.wait(10)
                return {"say": "x"}
        api = self.api()
        flavor = self.flavor()
        api._companion.start(flavor, Stuck())
        beacon_png(flavor / "Screenshots" / "WoWScrnShot_7.png", {"t": "ask", "rid": 6, "sid": "s", "slot": 1, "text": "hi", "ctx": {}})
        self.assertTrue(entered.wait(10))
        self.addCleanup(api._companion._thread.join, 10)
        self.addCleanup(release.set)
        started = time.monotonic()
        api._stop()
        self.assertLess(time.monotonic() - started, 1)

    def test_quitting_does_not_wait(self):
        entered, release = threading.Event(), threading.Event()

        class Stuck:
            client = None

            def answer(self, packet):
                entered.set()
                release.wait(10)
                return {"say": "x"}
        companion = service.Companion()
        flavor = self.flavor()
        companion.start(flavor, Stuck())
        beacon_png(flavor / "Screenshots" / "WoWScrnShot_8.png", {"t": "ask", "rid": 8, "sid": "s", "slot": 1, "text": "hi", "ctx": {}})
        self.assertTrue(entered.wait(10))
        worker = companion._thread
        self.addCleanup(worker.join, 10)
        self.addCleanup(release.set)            # cleanups run last-registered first: release, then join
        started = time.monotonic()
        companion.stop(wait=False)
        self.assertLess(time.monotonic() - started, 1)
        self.assertFalse(companion.running)


class Robustness(AppCase):
    def test_a_broken_settings_file_starts_fresh_and_is_kept(self):
        self.config.write_text("{not json")
        with self.assertLogs("gnomecaster", "WARNING"):
            state = self.api().getState()
        self.assertFalse(state["setupDone"])
        self.assertEqual(self.config.with_suffix(".broken.json").read_text(), "{not json")

    def test_every_call_answers_even_when_something_breaks(self):
        api = self.api()
        with mock.patch.object(self.system, "find_games", side_effect=RuntimeError("disk gone")), \
                self.assertLogs("gnomecaster", "ERROR") as logged:
            r = api.getState()
        self.assertIn("disk gone", "\n".join(logged.output))
        self.assertEqual(r["ok"], False)
        self.assertIn("RuntimeError", r["message"])

    def test_a_crash_while_answering_is_shown_as_an_error(self):
        events = []
        companion = service.Companion(on_event=events.append)

        class Broken:
            def answer(self, packet):
                raise ValueError("boom")
        observed = service._Observed(Broken(), companion)
        with self.assertRaises(ValueError):
            observed.answer({"t": "ask", "text": "hi"})
        self.assertEqual(events[-1]["type"], "answer")
        self.assertTrue(events[-1]["entry"]["error"])
        self.assertNotIn("pending", events[-1]["entry"])

    def test_settings_autostart_and_tray(self):
        api = self.api()
        self.assertTrue(api.setSetting({"name": "autostart", "value": True})["ok"])
        self.assertEqual(self.system.autostart, '"Gnomecaster.exe" --background')
        self.assertTrue(api.getState()["settings"]["autostart"])
        self.assertTrue(api._tray)
        api.setSetting({"name": "tray", "value": False})
        self.assertFalse(api._tray)
        self.assertFalse(api.getState()["settings"]["tray"])
        self.assertFalse(api.setSetting({"name": "api_key", "value": "x"})["ok"])

    def test_open_logs(self):
        self.api().openLogs()
        self.assertEqual(self.system.opened, [self.tmp / "data" / "logs"])

    def test_open_transcripts(self):
        self.assertEqual(self.api().openTranscripts({"path": "/etc"}), {"ok": True})
        self.assertEqual(self.system.opened, [self.tmp / "data" / "transcripts"])


class History(AppCase):
    def connected(self, *script):
        server = self.model_server({"body": completion('{"say": "ok"}')}, *script)
        api = self.api()
        self.assertTrue(api.saveKey({"provider": "openrouter", "key": "sk-or-v1-history-key"})["ok"])
        return api, server

    def test_questions_and_answers_newest_first_without_the_key(self):
        api, _ = self.connected({"body": completion('{"say": "first"}')}, {"body": completion('{"say": "second"}')})
        for n, text in enumerate(("one", "two sk-or-v1-history-key"), 1):
            api._brain.answer({"t": "ask", "rid": n, "sid": "s", "conv": "c", "text": text, "ctx": {"zone": "Z"}})
        r = api.getHistory({"limit": 10})
        self.assertTrue(r["ok"])
        self.assertEqual([i["reply"]["say"] for i in r["items"]], ["second", "first"])
        self.assertEqual(r["items"][1]["ctx"], {"zone": "Z"})
        self.assertNotIn("sk-or-v1-history-key", json.dumps(r))
        self.assertEqual(len(api.getHistory({"limit": 1})["items"]), 1)
        self.assertEqual(len(api.getHistory({"limit": "junk"})["items"]), 2)
        self.assertEqual(api.getHistory({"limit": -3})["items"], [])

    def test_nothing_yet(self):
        self.assertEqual(self.api().getHistory({}), {"ok": True, "items": []})

    def test_web_search_follows_the_provider_and_the_setting(self):
        api, _ = self.connected()
        self.assertFalse(api._brain.client.web_search)           # the fake server is not openrouter.ai
        api._data.update(base_url="https://openrouter.ai/api/v1")
        api._rebuild()
        self.assertTrue(api._brain.client.web_search)
        api._data["web_search"] = False
        api._rebuild()
        self.assertFalse(api._brain.client.web_search)


class Smoke(unittest.TestCase):
    def test_only_a_rendered_screen_passes(self):
        self.assertTrue(app.smoke_passed({"ready": "true", "screen": "setup"}))
        self.assertTrue(app.smoke_passed({"ready": "true", "screen": "main"}))
        self.assertFalse(app.smoke_passed({"ready": "", "screen": "setup"}))     # set before rendering failed
        self.assertFalse(app.smoke_passed({"ready": "", "screen": "error"}))
        self.assertFalse(app.smoke_passed({"ready": "", "screen": "loading"}))


class WindowSize(unittest.TestCase):
    @staticmethod
    def screen(w, h, taskbar=48):
        area = types.SimpleNamespace(X=0, Y=0, Width=w, Height=h - taskbar)      # WinForms WorkingArea
        return types.SimpleNamespace(x=0, y=0, width=w, height=h, frame=area)

    def test_centred_in_the_work_area_above_the_taskbar(self):
        # measured in the Windows test VM: 1280 x 800 with a 48 px taskbar
        w, h, x, y = app.window_geometry([self.screen(1280, 800)])
        self.assertEqual((w, h), (1040, 691))
        self.assertEqual((x, y), (120, 30))
        self.assertLessEqual(y + h, 752)                                          # bottom above the taskbar

    def test_fits_small_and_large_screens(self):
        self.assertEqual(app.window_geometry([self.screen(1920, 1080)])[:2], (1040, 700))
        self.assertEqual(app.window_geometry([self.screen(1093, 614)])[:2], (1005, 540))   # 1366 x 768 at 125 %
        self.assertEqual(app.window_geometry([]), (1040, 700, None, None))

    def test_without_a_work_area_the_whole_screen_counts(self):
        w, h, x, y = app.window_geometry([types.SimpleNamespace(x=0, y=0, width=1920, height=1080)])
        self.assertEqual((w, h, x, y), (1040, 700, 440, 190))


class Removal(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        self.wow = self.root / "World of Warcraft"
        self.addons = self.wow / "_retail_" / "Interface" / "AddOns"
        for name in ("Gnomecaster", "Gnomecaster_Inbox01", "Gnomecaster_Inbox60", "GnomecasterFan", "WeakAuras",
                     "Gnomecaster_Inbox61"):
            (self.addons / name).mkdir(parents=True)

    def test_only_our_folders_are_removed(self):
        removed = game.remove(self.wow / "_retail_")
        self.assertEqual(removed, ["Gnomecaster", "Gnomecaster_Inbox01", "Gnomecaster_Inbox60"])
        self.assertEqual(sorted(p.name for p in self.addons.iterdir()), ["GnomecasterFan", "Gnomecaster_Inbox61", "WeakAuras"])

    def test_remove_everything(self):
        settings = self.root / "Roaming" / "Gnomecaster" / "config.json"
        config.save_file({"api_key": "k", "roots": [str(self.wow)], "wow": str(self.wow / "_retail_")}, settings)
        data = self.root / "Local" / "Gnomecaster"
        (data / "logs").mkdir(parents=True)
        with mock.patch.object(winsys, "registry_wow_root", return_value=None), mock.patch.object(game, "GUESSES", []):
            removed = app.remove_everything(settings, data)
        self.assertFalse(settings.exists())
        self.assertFalse(data.exists())
        self.assertFalse((self.addons / "Gnomecaster").exists())
        self.assertTrue((self.addons / "WeakAuras").exists())
        self.assertEqual(len(removed), 5)

    def test_a_folder_not_named_gnomecaster_is_never_deleted(self):
        settings = self.root / "elsewhere" / "settings.json"          # GNOMECASTER_CONFIG pointing anywhere
        config.save_file({"api_key": "k"}, settings)
        with mock.patch.object(winsys, "registry_wow_root", return_value=None), mock.patch.object(game, "GUESSES", []):
            app.remove_everything(settings, self.root / "Local" / "data")
        self.assertTrue(settings.exists())


class Folders(unittest.TestCase):
    def test_version_folders(self):
        for name in ("_retail_", "_classic_era_", "_xptr_"):
            self.assertTrue(game.is_flavor(pathlib.Path("/w") / name))
        for name in ("World of Warcraft", "_", "__", "_retail", "Interface"):
            self.assertFalse(game.is_flavor(pathlib.Path("/w") / name))
        self.assertEqual(game.game_root(pathlib.Path("/w/_retail_")), pathlib.Path("/w"))
        self.assertEqual(game.game_root(pathlib.Path("/w")), pathlib.Path("/w"))

    def test_retail_is_listed_first(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("_anniversary_", "_xptr_", "_classic_era_", "_retail_", "_classic_", "_beta_", "Data"):
                (pathlib.Path(d) / name).mkdir()
            self.assertEqual([pathlib.Path(f["path"]).name for f in winsys.flavors_in(pathlib.Path(d))],
                             ["_retail_", "_classic_", "_classic_era_", "_anniversary_", "_beta_", "_xptr_"])


class Describe(unittest.TestCase):
    def test_actions_read_as_the_player_sees_them(self):
        self.assertEqual(service.describe({"type": "waypoint", "x": 0.381, "y": 0.552, "title": "Quest"}),
                         "Waypoint: Quest (38.1, 55.2)")
        self.assertEqual(service.describe({"type": "waypoint", "x": 38.1, "y": 55.2}), "Waypoint: Gnomecaster (38.1, 55.2)")
        self.assertEqual(service.describe({"type": "macro", "name": "Rejuv"}), "Macro \u201cRejuv\u201d")
        self.assertEqual(service.describe({"type": "bind", "key": "SHIFT-E", "macro": "Rejuv"}), "Shift-E bound to \u201cRejuv\u201d")
        self.assertEqual(service.describe({"type": "bind", "key": "CTRL-ALT-F1", "macro": "X"}), "Ctrl-Alt-F1 bound to \u201cX\u201d")
        self.assertEqual(service.describe({"type": "mark", "icon": 8}), "Skull on your target")
        self.assertEqual(service.describe({"type": "mark", "icon": 1, "unit": "focus"}), "Star on your focus")
        self.assertEqual(service.describe({"type": "mark", "icon": 0}), "Marker cleared from your target")
        self.assertEqual(service.describe({"type": "goto", "name": "Atal'Aman", "kind": "delve"}),
                         "Map pin: “Atal'Aman”")


class FakeWinreg(types.ModuleType):
    HKEY_LOCAL_MACHINE, HKEY_CURRENT_USER, KEY_SET_VALUE, REG_SZ = "HKLM", "HKCU", 2, 1

    def __init__(self, values):
        super().__init__("winreg")
        self.values = values                # (hive, key, name) -> value

    class _Key:
        def __init__(self, reg, hive, key):
            self.reg, self.where = reg, (hive, key)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def OpenKey(self, hive, key, *a):
        if not any((hive, key) == k[:2] for k in self.values) and hive == self.HKEY_LOCAL_MACHINE:
            raise FileNotFoundError(key)
        return self._Key(self, hive, key)

    def QueryValueEx(self, k, name):
        try:
            return self.values[k.where + (name,)], self.REG_SZ
        except KeyError:
            raise FileNotFoundError(name) from None

    def SetValueEx(self, k, name, reserved, kind, value):
        self.values[k.where + (name,)] = value

    def DeleteValue(self, k, name):
        if self.values.pop(k.where + (name,), None) is None:
            raise FileNotFoundError(name)


class Windows(unittest.TestCase):
    """winsys's Windows branches against an in-memory registry (paths use / so they parse here)."""

    def registry(self, values):
        reg = FakeWinreg(values)
        patches = [mock.patch.object(sys, "platform", "win32"), mock.patch.dict(sys.modules, {"winreg": reg})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return reg

    def test_the_registry_names_a_version_folder_whose_parent_is_the_game(self):
        self.registry({("HKLM", winsys.WOW_KEYS[0], "InstallPath"): "/games/World of Warcraft/_retail_/"})
        self.assertEqual(winsys.registry_wow_root(), pathlib.Path("/games/World of Warcraft"))

    def test_the_second_key_is_tried(self):
        self.registry({("HKLM", winsys.WOW_KEYS[1], "InstallPath"): "/games/World of Warcraft"})
        self.assertEqual(winsys.registry_wow_root(), pathlib.Path("/games/World of Warcraft"))

    def test_no_registry_entry(self):
        self.registry({})
        self.assertIsNone(winsys.registry_wow_root())

    def test_autostart_round_trip(self):
        reg = self.registry({})
        self.assertFalse(winsys.autostart_enabled())
        self.assertTrue(winsys.set_autostart(True, '"C:/Gnomecaster/Gnomecaster.exe" --background'))
        self.assertEqual(reg.values[("HKCU", winsys.RUN_KEY, "Gnomecaster")], '"C:/Gnomecaster/Gnomecaster.exe" --background')
        self.assertTrue(winsys.set_autostart(False, ""))
        self.assertFalse(winsys.autostart_enabled())
        self.assertTrue(winsys.set_autostart(False, ""))     # already off


class SingleInstance(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = pathlib.Path(tmp.name)

    def test_a_second_start_shows_the_first(self):
        shown = threading.Event()
        first = app.SingleInstance(self.folder)
        first.listen(shown.set)
        self.addCleanup(first.close)
        self.assertTrue(app.SingleInstance(self.folder).ask_running_to_show())
        self.assertTrue(shown.wait(5))

    def test_a_stale_file_does_not_count(self):
        self.assertFalse(app.SingleInstance(self.folder).ask_running_to_show())      # no file
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        self.addCleanup(listener.close)
        (self.folder / "instance.json").write_text(json.dumps({"port": listener.getsockname()[1], "token": "old"}))
        threading.Thread(target=lambda: listener.accept()[0].close(), daemon=True).start()
        self.assertFalse(app.SingleInstance(self.folder).ask_running_to_show())

    def test_closing_removes_the_file(self):
        first = app.SingleInstance(self.folder)
        first.listen(lambda: None)
        first.close()
        self.assertFalse((self.folder / "instance.json").exists())

    def test_closing_keeps_another_instances_file(self):
        first, second = app.SingleInstance(self.folder), app.SingleInstance(self.folder)
        first.listen(lambda: None)
        second.listen(lambda: None)                 # wrote the file after the first
        self.addCleanup(second.close)
        first.close()
        self.assertTrue(app.SingleInstance(self.folder).ask_running_to_show())

    def test_the_first_by_the_mutex_starts(self):
        self.assertFalse(app.defer_to_running(app.SingleInstance(self.folder), True))

    def test_the_mutex_outranks_a_stale_listener(self):
        shown = threading.Event()
        stale = app.SingleInstance(self.folder)
        stale.listen(shown.set)
        self.addCleanup(stale.close)
        self.assertFalse(app.defer_to_running(app.SingleInstance(self.folder), True))
        self.assertFalse(shown.wait(0.5))

    def test_a_later_start_exits_even_before_the_first_answers(self):
        started = time.monotonic()
        self.assertTrue(app.defer_to_running(app.SingleInstance(self.folder), False, wait=0.3))
        self.assertGreaterEqual(time.monotonic() - started, 0.3)

    def test_without_a_mutex_a_running_instance_is_asked(self):
        lone = app.SingleInstance(self.folder)
        self.assertFalse(app.defer_to_running(lone, None))
        running = app.SingleInstance(self.folder)
        running.listen(lambda: None)
        self.addCleanup(running.close)
        self.assertTrue(app.defer_to_running(app.SingleInstance(self.folder), None))

    def test_a_second_start_claims_the_mutex_and_shows_the_first(self):
        shown = threading.Event()
        running = app.SingleInstance(self.folder)
        running.listen(shown.set)
        self.addCleanup(running.close)
        claims = []

        def claim(name):
            claims.append(name)
            return False

        def no_window(*a, **k):
            raise AssertionError("a second start must not open a window")
        with mock.patch.object(winsys, "claim_instance", claim), \
                mock.patch.object(winsys, "data_dir", return_value=self.folder), \
                mock.patch.object(app, "setup_logging", return_value=self.folder / "log"), \
                mock.patch.object(app, "Shell", no_window):
            self.assertEqual(app.main([]), 0)
        self.assertEqual(claims, ["Gnomecaster.Running"])
        self.assertTrue(shown.wait(5))

    def test_quit_asks_the_running_app_and_waits_for_it(self):
        running = app.SingleInstance(self.folder)
        quits = []

        def on_quit():
            quits.append(1)
            threading.Timer(0.4, running.close).start()     # quitting takes a moment
        running.listen(lambda: None, on_quit)
        started = time.monotonic()
        self.assertTrue(app.quit_running(app.SingleInstance(self.folder)))
        self.assertEqual(quits, [1])
        self.assertGreaterEqual(time.monotonic() - started, 0.3)
        self.assertFalse((self.folder / "instance.json").exists())

    def test_quit_waits_until_the_process_lets_go_of_the_mutex(self):
        running = app.SingleInstance(self.folder)
        running.listen(lambda: None, running.close)          # the file goes at once
        exits_at = time.monotonic() + 0.6                    # the process a moment later
        probes = []

        def held(name):
            probes.append(name)
            return time.monotonic() < exits_at
        with mock.patch.object(winsys, "instance_held", held):
            self.assertTrue(app.quit_running(app.SingleInstance(self.folder)))
        self.assertGreaterEqual(time.monotonic(), exits_at)
        self.assertEqual(set(probes), {app.MUTEX})

    def test_quit_does_not_wait_past_its_limit(self):
        running = app.SingleInstance(self.folder)
        running.listen(lambda: None, running.close)
        started = time.monotonic()
        with mock.patch.object(winsys, "instance_held", return_value=True):
            self.assertTrue(app.quit_running(app.SingleInstance(self.folder), wait=0.5))
        self.assertLess(time.monotonic() - started, 3)

    def test_quit_with_nothing_running(self):
        self.assertFalse(app.quit_running(app.SingleInstance(self.folder), wait=1))

    def test_the_quit_command_line(self):
        running = app.SingleInstance(self.folder)
        quits = []
        running.listen(lambda: None, lambda: (quits.append(1), running.close()))
        with mock.patch.object(winsys, "data_dir", return_value=self.folder), \
                mock.patch.object(app, "Shell", side_effect=AssertionError("--quit must not open a window")):
            self.assertEqual(app.main(["--quit"]), 0)
        self.assertEqual(quits, [1])

    @unittest.skipUnless(sys.platform == "win32", "a real Windows mutex")
    def test_the_windows_mutex_admits_one(self):
        name = f"Gnomecaster.Test.{os.getpid()}"
        self.assertIs(winsys.claim_instance(name), True)
        self.assertIs(winsys.claim_instance(name), False)

    @unittest.skipUnless(sys.platform == "win32", "a real Windows mutex")
    def test_the_windows_mutex_shows_who_holds_it(self):
        name = f"Gnomecaster.Test.Held.{os.getpid()}"
        self.assertIs(winsys.instance_held(name), False)
        winsys.claim_instance(name)
        self.assertIs(winsys.instance_held(name), True)

    @unittest.skipIf(sys.platform == "win32", "elsewhere there is no mutex to ask")
    def test_without_windows_the_mutex_has_no_answer(self):
        self.assertIsNone(winsys.instance_held(app.MUTEX))


class FakeWindow:
    def __init__(self):
        self.hidden = False
        self.destroyed = False

    def hide(self):
        self.hidden = True

    def destroy(self):
        self.destroyed = True


class FakeIcon:
    def __init__(self):
        self.notes, self.stopped, self.menu_updates = [], False, 0

    def notify(self, message, title=None):
        self.notes.append(title)

    def stop(self):
        self.stopped = True

    def update_menu(self):
        self.menu_updates += 1


class Shell(unittest.TestCase):
    """Closing to the tray and quitting, with pywebview and pystray replaced by fakes."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patch = mock.patch.dict(sys.modules, {"webview": types.ModuleType("webview")})
        patch.start()
        self.addCleanup(patch.stop)
        with mock.patch.dict(os.environ, {"GNOMECASTER_CONFIG": str(pathlib.Path(tmp.name) / "c.json")}):
            self.shell = app.Shell(background=False)
        self.shell.window, self.shell.icon = FakeWindow(), FakeIcon()

    def test_closing_the_window_keeps_running_in_the_tray(self):
        self.assertIs(self.shell.on_closing(), False)       # only a literal False cancels the close
        self.assertTrue(self.shell.window.hidden)
        self.assertFalse(self.shell.icon.stopped)
        self.shell.on_closing()
        self.assertEqual(self.shell.icon.notes, ["Still running"])     # explained once

    def test_closing_quits_when_the_tray_is_off(self):
        self.shell.api._data["tray"] = False
        self.assertTrue(self.shell.on_closing())
        self.assertTrue(self.shell.icon.stopped)

    def test_closing_quits_without_a_tray_icon(self):
        self.shell.icon = None
        self.assertTrue(self.shell.on_closing())

    def test_quit_from_the_tray(self):
        self.shell.quit()
        self.assertTrue(self.shell.window.destroyed)
        self.assertTrue(self.shell.on_closing())            # destroy fires closing
        self.assertTrue(self.shell.icon.stopped)
        self.assertIsNone(self.shell.events.get_nowait())   # the event pump is told to end

    def test_the_tray_menu_follows_the_companion(self):
        self.shell.update_tray(True)
        self.assertEqual(self.shell.icon.menu_updates, 1)


if __name__ == "__main__":
    unittest.main()
