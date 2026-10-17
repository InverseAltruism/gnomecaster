"""tools/eval_models.py without spending money: it stops before any request when no key is
set, runs multi-turn scenarios through the real Brain, and its checks tell the owner's bad
answers from good ones."""
import contextlib
import io
import json
import os
import pathlib
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "companion"))

import eval_models  # noqa: E402
import eval_scenarios as sc  # noqa: E402
from test_companion import FakeServer, completion  # noqa: E402

BY_ID = {s["id"]: s for s in sc.SCENARIOS}


def passes(scenario_id, reply):
    return all(fn(reply, None) for _, hard, fn in BY_ID[scenario_id]["checks"] if hard)


class WithoutAKey(unittest.TestCase):
    def run_main(self, env, *argv):
        err = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stderr(err), \
                self.assertRaises(SystemExit) as stop, mock.patch.object(eval_models, "run_one") as run_one:
            eval_models.main(["--model", "m", *argv])
        run_one.assert_not_called()
        return str(stop.exception)

    def test_stops_before_the_first_request(self):
        message = self.run_main({"LUA": "lua5.1"})
        self.assertEqual(message, f"GNOMECASTER_API_KEY is not set, so no request was sent ({len(sc.SCENARIOS)} "
                                  "scenarios ready). Set it, or pass --no-key for an endpoint that needs none.")

    def test_needs_lua_first(self):
        self.assertIn("set LUA", self.run_main({"GNOMECASTER_API_KEY": "k"}))

    def test_an_unknown_scenario_is_named(self):
        self.assertEqual(self.run_main({"LUA": "lua5.1", "GNOMECASTER_API_KEY": "k"}, "--only", "nope"),
                         "no scenario matches --only")


class MultiTurn(unittest.TestCase):
    def test_a_scripted_turn_is_remembered_and_only_the_last_is_asked(self):
        s = FakeServer([{"body": completion(json.dumps({"say": "An.", "actions": [
            {"type": "setting", "name": "nameplateShowEnemies", "value": "1"}]}))}])
        self.addCleanup(s.close)
        r = eval_models.run_one(s.url, "m", "k", {}, BY_ID["de_nameplates_yes"])
        [post] = s.posts()
        roles = [m["role"] for m in post["body"]["messages"]]
        self.assertEqual(roles, ["system", "user", "assistant", "user"])
        self.assertIn("Soll ich", post["body"]["messages"][2]["content"])
        self.assertTrue(post["body"]["messages"][3]["content"].endswith("PLAYER:\nja"))
        self.assertNotIn("tools", post["body"])                 # the fake server is not OpenRouter
        self.assertTrue(passes("de_nameplates_yes", r["reply"]))
        self.assertFalse(r["searched"])

    def test_the_game_report_is_sent(self):
        s = FakeServer([{"body": completion('{"say": "ok"}')}])
        self.addCleanup(s.close)
        eval_models.run_one(s.url, "m", "k", {}, BY_ID["de_goto_retry"])
        self.assertIn("goto: not done, no place called Atal Aman found; close: Atal'Aman",
                      s.posts()[0]["body"]["messages"][-1]["content"])


class Checks(unittest.TestCase):
    def test_the_owners_bad_answers_fail(self):
        self.assertFalse(passes("de_nameplates_yes", {"say": "Wozu sagst du ja?"}))
        self.assertFalse(passes("de_worldboss", {"say": "Das kann ich noch nicht nachschlagen."}))
        # in game it refused; a goto by name with kind "quest" still finds the dungeon (places scenario)
        self.assertFalse(passes("de_dungeon_route", {"say": "Ich kann die Route noch nicht anzeigen."}))
        self.assertFalse(passes("de_dungeon_route", {"say": "x", "actions": [
            {"type": "goto", "name": "Atal'Aman", "kind": "dungeon"}]}))
        self.assertFalse(passes("de_delve", {"say": "x", "actions": [
            {"type": "waypoint", "map": 1, "x": 0.5, "y": 0.5}, {"type": "goto", "name": "Atal'Aman", "kind": "delve"}]}))

    def test_good_answers_pass(self):
        self.assertTrue(passes("de_worldboss", {"say": "x", "actions": [{"type": "goto", "name": "Kael", "kind": "boss"}]}))
        self.assertTrue(passes("de_delve", {"say": "x", "actions": [{"type": "goto", "name": "Atal'Aman", "kind": "delve"}]}))
        self.assertTrue(passes("de_dungeon_route", {"say": "x", "actions": [
            {"type": "goto", "name": "Terrasse der Magier", "kind": "dungeon"}]}))
        self.assertTrue(passes("quest_nav", {"say": "x", "actions": [
            {"type": "goto", "name": "The Sunwell's Echo", "kind": "quest", "quest": 91001}]}))
        self.assertTrue(passes("de_autoloot", {"say": "An.", "actions": [
            {"type": "setting", "name": "autoLootDefault", "value": "1"}]}))
        self.assertTrue(passes("de_trap_macro", {"say": "x", "actions": [
            {"type": "macro", "name": "Eisfalle", "body": "#showtooltip\n/cast [@target,harm] Eisfalle"}]}))

    def test_scenario_ids_are_unique(self):
        ids = [s["id"] for s in sc.SCENARIOS]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
