"""Finding the World of Warcraft folder and installing the addon into it."""
from __future__ import annotations

import dataclasses
import filecmp
import pathlib
import shutil
import sys


def _addon_dir() -> pathlib.Path:
    if getattr(sys, "frozen", False):   # the desktop app: PyInstaller unpacks data under _MEIPASS
        return pathlib.Path(sys._MEIPASS) / "addon"
    return pathlib.Path(__file__).resolve().parents[2] / "addon"


ADDON_DIR = _addon_dir()
GUESSES = [r"C:\Program Files (x86)\World of Warcraft", r"C:\Program Files\World of Warcraft",
           r"D:\World of Warcraft", r"D:\Games\World of Warcraft", "/Applications/World of Warcraft"]
FLAVORS = ["_retail_", "_classic_", "_classic_era_", "_anniversary_"]


def is_flavor(path: pathlib.Path) -> bool:
    """A game version folder inside the game folder, such as _retail_ or _classic_era_."""
    return len(path.name) > 2 and path.name.startswith("_") and path.name.endswith("_")


def game_root(path: pathlib.Path) -> pathlib.Path:
    """The game folder, also when given one of its version folders."""
    return path.parent if is_flavor(path) else path


def find_flavor(path: str | None) -> pathlib.Path | None:
    """The game flavor folder (e.g. ..._retail_) for a game or flavor folder, or a guess."""
    candidates = [pathlib.Path(path).expanduser()] if path else [pathlib.Path(g) for g in GUESSES]
    for p in candidates:
        if (p / "Interface").is_dir() or (is_flavor(p) and p.is_dir()):
            return p
        for sub in FLAVORS:
            if (p / sub).is_dir():
                return p / sub
    return None


def resolve_flavor(path: str | None) -> pathlib.Path:
    found = find_flavor(path)
    if found is None:
        raise SystemExit("Couldn't find World of Warcraft. Run setup, or pass --wow with the game folder, "
                         'e.g. --wow "C:\\Program Files (x86)\\World of Warcraft\\_retail_"')
    return found


def addon_status(flavor: pathlib.Path) -> str:
    """'missing', 'outdated' or 'current' for the addon and its reply slots in the game."""
    dest = flavor / "Interface" / "AddOns"
    if not (dest / "Gnomecaster").is_dir():
        return "missing"
    for src in sorted(ADDON_DIR.iterdir()):
        if not (src.is_dir() and src.name.startswith("Gnomecaster")):
            continue
        for f in src.rglob("*"):
            target = dest / f.relative_to(ADDON_DIR)
            if f.is_file() and f.name != "ack.ttf" and f.name != "ready.ttf" and f.name != "inbox.lua":
                if not target.is_file() or not filecmp.cmp(f, target, shallow=False):
                    return "outdated"
            elif f.is_file() and not target.exists():
                return "outdated"
    return "current"


class InstallError(Exception):
    def __init__(self, message: str, denied: bool = False):
        super().__init__(message)
        self.denied = denied            # Windows refused the write: permissions, or the game held a file


@dataclasses.dataclass
class Installed:
    dest: pathlib.Path
    count: int                          # addon folders copied
    old: list[str]                      # folders left by the Wowpilot prototype


def install(flavor: pathlib.Path) -> Installed:
    """Copies the addon and its reply slots into the game. Raises InstallError."""
    if not (ADDON_DIR / "Gnomecaster").is_dir():
        raise InstallError(f"The addon files are missing next to the companion ({ADDON_DIR}). Download the whole "
                           "Gnomecaster folder, not only the companion script.")
    dest = flavor / "Interface" / "AddOns"
    try:
        dest.mkdir(parents=True, exist_ok=True)
        count = 0
        for src in sorted(ADDON_DIR.iterdir()):
            if src.is_dir() and src.name.startswith("Gnomecaster"):
                shutil.copytree(src, dest / src.name, dirs_exist_ok=True)
                count += 1
    except PermissionError as e:
        raise InstallError(f"Windows refused to write into {dest} ({e.filename}). Close the game and try again.",
                           denied=True) from None
    except OSError as e:
        raise InstallError(f"Couldn't copy the addon into {dest} ({e}).") from None
    old = sorted(p.name for p in dest.glob("Wowpilot*") if p.is_dir())
    return Installed(dest, count, old)


def remove(flavor: pathlib.Path) -> list[str]:
    """Deletes the addon and its reply slots from a game version, nothing else: only folders
    named Gnomecaster or Gnomecaster_Inbox01 to 60. Returns the names removed."""
    addons = flavor / "Interface" / "AddOns"
    ours = {"Gnomecaster"} | {f"Gnomecaster_Inbox{n:02d}" for n in range(1, 61)}
    removed = []
    for folder in sorted(addons.glob("Gnomecaster*")) if addons.is_dir() else []:
        if folder.name in ours and folder.is_dir() and not folder.is_symlink():
            shutil.rmtree(folder)
            removed.append(folder.name)
    return removed


def install_notes(done: Installed, restart: bool = True) -> list[str]:
    notes = [f"Installed {done.count} folders into {done.dest}."]
    if done.old:
        notes.append(f"Found {len(done.old)} folders of the old Wowpilot prototype in {done.dest}; delete them "
                     "(Wowpilot and Wowpilot_Inbox01 to 60). This companion ignores their requests.")
    if restart:
        notes.append("Restart the game completely: new addons need a restart, not just /reload.")
    return notes
