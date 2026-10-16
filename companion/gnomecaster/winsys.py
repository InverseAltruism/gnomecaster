"""What the desktop app needs from the operating system, kept apart so the rest stays portable.

Windows specifics: the World of Warcraft install recorded in the registry, the per-user Run
key for "Start with Windows", and opening folders in Explorer. Elsewhere these fall back to
folder guesses and no-ops, which is what the tests on Linux exercise.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

from . import game

# Blizzard's installer records the game here (WeakAuras Companion reads the same value; it
# points at a flavor folder such as _retail_, whose parent is the game folder).
WOW_KEYS = (r"SOFTWARE\WOW6432Node\Blizzard Entertainment\World of Warcraft",
            r"SOFTWARE\Blizzard Entertainment\World of Warcraft")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "Gnomecaster"
FLAVOR_NAMES = {"_retail_": "Retail", "_classic_": "Classic", "_classic_era_": "Classic Era",
                "_anniversary_": "Anniversary", "_ptr_": "Retail test realm", "_xptr_": "Retail test realm 2",
                "_beta_": "Beta", "_classic_ptr_": "Classic test realm"}


def registry_wow_root() -> pathlib.Path | None:
    if sys.platform != "win32":
        return None
    import winreg
    for key in WOW_KEYS:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
                value, _ = winreg.QueryValueEx(k, "InstallPath")
        except OSError:
            continue
        return game.game_root(pathlib.Path(str(value).rstrip("\\/")))
    return None


def flavors_in(root: pathlib.Path) -> list[dict]:
    """The game versions installed in a game folder, as the interface lists them."""
    found = []
    try:
        subdirs = sorted(p for p in root.iterdir() if p.is_dir())
    except OSError:
        return found
    for sub in subdirs:
        if game.is_flavor(sub):
            name = FLAVOR_NAMES.get(sub.name, sub.name.strip("_").replace("_", " ").title())
            found.append({"id": str(sub), "name": name, "path": str(sub)})     # two installs may share a name
    return found


def find_games(extra_roots: list[str] = ()) -> list[dict]:
    """Every installed game version: the registry first, then any folder the player chose,
    then the usual install locations. Each entry carries whether the addon is installed."""
    roots, seen, games = [], set(), []
    reg = registry_wow_root()
    if reg:
        roots.append(reg)
    roots += [pathlib.Path(r) for r in extra_roots if r]
    roots += [pathlib.Path(g) for g in game.GUESSES]
    for root in map(game.game_root, roots):     # a version folder lists its siblings too
        key = str(root).lower()
        if key in seen or not root.is_dir():
            continue
        seen.add(key)
        for f in flavors_in(root):
            f["addon"] = game.addon_status(pathlib.Path(f["path"]))
            games.append(f)
    return games


def autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_NAME)
        return True
    except OSError:
        return False


def set_autostart(on: bool, command: str) -> bool:
    """Adds or removes the per-user Run entry. Returns whether it is now as asked."""
    if sys.platform != "win32":
        return False
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass
    return autostart_enabled() == on


ERROR_ALREADY_EXISTS = 183
_held: list[int] = []                   # mutex handles stay open until the process exits


def claim_instance(name: str) -> bool | None:
    """Creates the named mutex that marks the app as running in this Windows session, which
    is atomic where checking a file or port is not. True: this process is the first; False:
    another one holds it; None: no answer (not Windows, or the call failed)."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    handle = kernel32.CreateMutexW(None, False, name)
    if not handle:
        return None
    _held.append(handle)
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS


def data_dir() -> pathlib.Path:
    """Where the app keeps logs and its instance file (not the settings, see config.py)."""
    if sys.platform == "win32":
        base = pathlib.Path(os.environ.get("LOCALAPPDATA") or pathlib.Path.home() / "AppData" / "Local")
        return base / "Gnomecaster"
    return pathlib.Path(os.environ.get("XDG_STATE_HOME") or pathlib.Path.home() / ".local" / "state") / "gnomecaster"


def open_folder(path: pathlib.Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - opens Explorer on our own folder
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
