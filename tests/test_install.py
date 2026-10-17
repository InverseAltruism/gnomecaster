"""Installing the addon into a game folder: what an update adds, keeps and removes."""
import os
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "companion"))

from gnomecaster import game, protocol  # noqa: E402


def slot(n):
    return f"Gnomecaster_Inbox{n:02d}"


class Update(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        self.flavor = self.root / "World of Warcraft" / "_retail_"
        self.addons = self.flavor / "Interface" / "AddOns"
        self.addons.mkdir(parents=True)

    def names(self):
        return sorted(p.name for p in self.addons.iterdir())

    def old_install(self, slots=game.MOST_SLOTS_EVER):
        """What an older release left in the game: the addon and `slots` reply slots."""
        for name in ["Gnomecaster"] + [slot(n) for n in range(1, slots + 1)]:
            (self.addons / name).mkdir()
            (self.addons / name / "inbox.lua").write_text("-- old")

    def test_this_version_ships_fewer_slots_than_the_old_ones(self):
        self.assertLess(protocol.NUM_SLOTS, game.MOST_SLOTS_EVER)

    def test_a_fresh_install_holds_exactly_the_current_slots(self):
        done = game.install(self.flavor)
        self.assertEqual(self.names(), ["Gnomecaster"] + [slot(n) for n in range(1, protocol.NUM_SLOTS + 1)])
        self.assertEqual(done.count, protocol.NUM_SLOTS + 1)
        self.assertEqual(done.removed, [])
        self.assertEqual(game.addon_status(self.flavor), "current")

    def test_an_update_removes_the_slots_this_version_no_longer_ships(self):
        self.old_install()
        self.assertEqual(game.addon_status(self.flavor), "outdated")
        done = game.install(self.flavor)
        self.assertEqual(done.removed, [slot(n) for n in range(protocol.NUM_SLOTS + 1, game.MOST_SLOTS_EVER + 1)])
        self.assertEqual(self.names(), ["Gnomecaster"] + [slot(n) for n in range(1, protocol.NUM_SLOTS + 1)])
        self.assertEqual(game.addon_status(self.flavor), "current")
        self.assertIn(f"Removed {len(done.removed)} reply slot folders", " ".join(game.install_notes(done)))

    def test_leftover_slots_alone_make_the_addon_outdated(self):
        game.install(self.flavor)
        (self.addons / slot(protocol.NUM_SLOTS + 1)).mkdir()
        self.assertEqual(game.addon_status(self.flavor), "outdated")

    def test_an_update_never_touches_folders_that_are_not_ours(self):
        self.old_install()
        others = ["GnomecasterFan", slot(game.MOST_SLOTS_EVER + 1), "Gnomecaster_Inbox21_backup", "WeakAuras"]
        for name in others:
            (self.addons / name).mkdir(exist_ok=True)
        (self.addons / "Gnomecaster_Inbox22.txt").write_text("a file, not a folder")
        game.install(self.flavor)
        for name in others + ["Gnomecaster_Inbox22.txt"]:
            self.assertTrue((self.addons / name).exists(), name)

    @unittest.skipIf(sys.platform == "win32", "symlinks need extra rights on Windows")
    def test_a_link_named_like_an_old_slot_is_not_followed(self):
        outside = self.root / "player data"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep")
        os.symlink(outside, self.addons / slot(protocol.NUM_SLOTS + 1))
        game.install(self.flavor)
        self.assertTrue((outside / "keep.txt").exists())
        self.assertTrue((self.addons / slot(protocol.NUM_SLOTS + 1)).is_symlink())

    def test_uninstall_removes_old_slots_too(self):
        self.old_install()
        (self.addons / "WeakAuras").mkdir()
        removed = game.remove(self.flavor)
        self.assertEqual(len(removed), game.MOST_SLOTS_EVER + 1)
        self.assertEqual(self.names(), ["WeakAuras"])


if __name__ == "__main__":
    unittest.main()
