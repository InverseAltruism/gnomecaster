"""Pins the knowledge the Lua addon and the Python companion must share.

The two halves talk only through screenshots and files, so nothing at runtime notices when
one side changes a constant the other relies on. These tests read both sides and compare.
"""
import importlib.util
import pathlib
import re
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
ADDON = ROOT / "addon" / "Gnomecaster"
sys.path.insert(0, str(ROOT / "companion"))

from gnomecaster import prompt, protocol, slots  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


make_inboxes = load("make_inboxes", ROOT / "tools" / "make_inboxes.py")


def lua(file):
    return (ADDON / file).read_text(encoding="utf-8")


def lua_number(file, pattern):
    return int(re.search(pattern, lua(file)).group(1))


def lua_list(file, name):
    block = re.search(rf"local {name}\s*=\s*\{{([^}}]*)\}}", lua(file)).group(1)
    return [int(n) for n in re.findall(r"-?\d+", block)]


class Contract(unittest.TestCase):
    def test_slot_count(self):
        lua_slots = lua_number("Core.lua", r"ns\.NUM_SLOTS\s*=\s*(\d+)")
        folders = sorted(p.name for p in (ROOT / "addon").glob("Gnomecaster_Inbox*") if p.is_dir())
        self.assertEqual(lua_slots, protocol.NUM_SLOTS)
        self.assertEqual(lua_slots, make_inboxes.NUM_SLOTS)
        self.assertEqual(folders, [f"Gnomecaster_Inbox{n:02d}" for n in range(1, lua_slots + 1)])

    def test_protocol_and_magic(self):
        self.assertEqual(lua_number("Core.lua", r"ns\.PROTOCOL\s*=\s*(\d+)"), protocol.PROTOCOL)
        magic = re.search(r'local MAGIC\s*=\s*"([^"]*)"', lua("Beacon.lua")).group(1)
        self.assertEqual(magic.encode("ascii"), protocol.MAGIC)

    def test_grid(self):
        self.assertEqual(lua_number("Beacon.lua", r"local GRID_W\s*=\s*(\d+)"), protocol.GRID_W)
        self.assertEqual(lua_list("Beacon.lua", "MARKER"), protocol.MARKER)

    def test_action_types(self):
        handlers = set(re.findall(r"^handlers\.(\w+)\s*=", lua("Actions.lua"), re.M))
        self.assertEqual(handlers, prompt.ACTION_TYPES)

    def test_ready_signal_covers_every_slot_the_addon_can_reach(self):
        # The addon spends at most one slot per timed poll while it waits, so the reply can
        # land at most len(BLIND) slots past the one the request named.
        blind = lua_list("Inbox.lua", "BLIND")
        self.assertGreaterEqual(slots.PROBE_AHEAD, len(blind) + 1)

    def test_interface_versions(self):
        toc = (ADDON / "Gnomecaster.toc").read_text(encoding="utf-8")
        interface = re.search(r"^## Interface:\s*(.+)$", toc, re.M).group(1).strip()
        self.assertEqual(interface, make_inboxes.INTERFACE)

    def test_committed_slots_match_the_generator(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_inboxes.main(tmp)
            generated = {p.relative_to(tmp): p.read_bytes() for p in pathlib.Path(tmp).rglob("*") if p.is_file()}
        # a Windows checkout may turn LF into CRLF (git's core.autocrlf); the generator must not
        committed = {p.relative_to(ROOT / "addon"): p.read_bytes().replace(b"\r\n", b"\n")
                     for p in (ROOT / "addon").glob("Gnomecaster_Inbox*/*") if p.is_file()}
        self.assertEqual(sorted(map(str, committed)), sorted(map(str, generated)))
        for path, data in generated.items():
            self.assertEqual(committed[path], data, f"{path} differs from tools/make_inboxes.py output")


if __name__ == "__main__":
    unittest.main()
