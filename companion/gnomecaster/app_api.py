"""The calls the desktop window makes; desktop/ui/api.js is the other side of this contract.

pywebview hands the page every public method of this object, and of its public attributes
recursively, so everything that is not a call for the page starts with an underscore. Each
call takes one dict and returns JSON. None raises: failures come back as {ok: False, message}
in words for the player, and the traceback goes to the log.
"""
from __future__ import annotations

import functools
import logging
import pathlib
import threading
import webbrowser

from . import __version__, config, game, oauth, service, winsys
from .brain import Brain
from .model import ModelClient, ModelError

log = logging.getLogger("gnomecaster")
KEY_PROVIDERS = ("openrouter", "openai", "ollama")      # the choices in the window's key form, in order


def _preferred(games: list[dict]) -> dict | None:
    """The version selected when the player hasn't chosen: Retail when installed."""
    return next((g for g in games if g["name"] == "Retail"), games[0] if games else None)


def _call(fn):
    """Turns any unexpected exception into a message for the player."""
    @functools.wraps(fn)
    def wrapper(self, args=None):
        try:
            return fn(self, args if isinstance(args, dict) else {})
        except Exception as e:  # noqa: BLE001 - the window must always get an answer
            log.exception("%s failed", fn.__name__)
            return {"ok": False, "message": f"Something went wrong ({type(e).__name__}). The log folder has details."}
    return wrapper


class Api:
    def __init__(self, *, config_path: pathlib.Path | None = None, emit=lambda event: None,
                 on_companion=lambda running: None, choose_folder=lambda: None, autostart_command: str = "",
                 system=winsys, sign_in=oauth.sign_in, credit=oauth.credit, presets=config.PRESETS,
                 open_browser=webbrowser.open):
        self._path = config_path or config.config_path()
        self._emit = emit
        self._choose_folder = choose_folder
        self._autostart_command = autostart_command
        self._system = system
        self._sign_in = sign_in
        self._credit = credit
        self._presets = presets
        self._open_browser = open_browser
        self._lock = threading.RLock()
        self._sign_in_cancel: threading.Event | None = None
        self._check = self._unchecked()
        self._data = self._load()
        self._brain = Brain(self._client(), game.ADDON_DIR)
        self._companion = service.Companion(on_event=self._emit_safe, on_change=on_companion)

    # ------------------------------------------------------------------ internals

    def _load(self) -> dict:
        try:
            return config.load_file(self._path)
        except config.ConfigError as e:
            log.warning("%s; starting with fresh settings", e)
            broken = self._path.with_suffix(".broken.json")
            try:
                self._path.replace(broken)
            except OSError:
                pass
            return {}

    def _save(self) -> None:
        with self._lock:
            config.save_file(self._data, self._path)

    def _emit_safe(self, event: dict) -> None:
        try:
            self._emit(event)
        except Exception:  # noqa: BLE001 - a closed window must not break the caller
            log.exception("could not send an event to the window")

    def _client(self) -> ModelClient | None:
        d = self._data
        if not (d.get("base_url") and d.get("model")):
            return None
        return ModelClient(d["base_url"], d["model"], d.get("api_key", ""),
                           d.get("extra") if isinstance(d.get("extra"), dict) else None)

    def _rebuild(self) -> None:
        """The settings changed: answer with the new model from the next question on."""
        self._brain.client = self._client()
        self._check = self._unchecked()

    @staticmethod
    def _unchecked() -> dict:
        return {"ok": None, "note": "", "credit": None, "fix": None}

    def _tested(self, client: ModelClient) -> dict:
        """Asks the test question; the result as the window shows it. `fix` names a problem the
        window offers a button for."""
        openrouter = client.base == self._presets["openrouter"]["base_url"].rstrip("/")
        try:
            note = client.check()
        except ModelError as e:
            if e.kind == "credit" and openrouter:
                return {"ok": False, "note": "Your OpenRouter account is out of credit. Add credit, then test again.",
                        "credit": None, "fix": "credit"}
            return {"ok": False, "note": e.message, "credit": None, "fix": None}
        credit = self._credit(client.key) if openrouter and client.key else None
        return {"ok": True, "note": "Test question " + note, "credit": credit, "fix": None}

    def _games(self) -> list[dict]:
        roots = list(self._data.get("roots") or [])
        if self._data.get("wow"):
            roots.append(self._data["wow"])
        return self._system.find_games(roots)

    def _selected(self, games: list[dict], wanted: str | None = None) -> dict | None:
        wanted = wanted or self._data.get("wow")
        for g in games:
            if g["id"] == wanted:
                return g
        return None if wanted else _preferred(games)

    def _run_check(self) -> tuple[bool, str]:
        client = self._brain.client
        if client is None:
            return False, "No AI connected."
        result = self._tested(client)
        if client is self._brain.client:        # still the current settings
            self._check = result
        return result["ok"], result["note"]

    def _check_later(self) -> None:
        def work():
            self._run_check()
            self._emit_safe({"type": "state"})
        threading.Thread(target=work, name="check", daemon=True).start()

    def _start_companion(self) -> bool:
        games = self._games()
        g = self._selected(games)
        if g is None:
            return False
        self._companion.start(pathlib.Path(g["path"]), self._brain)
        return True

    def _restart_if_running(self) -> None:
        if self._companion.running:
            self._start_companion()

    def _account(self) -> str:
        d = self._data
        provider = d.get("provider", "")
        if provider == "ollama":
            return "Using Ollama on this PC"
        if d.get("account") == "oauth":
            return "Signed in with OpenRouter"
        label = {"openrouter": "OpenRouter", "openai": "OpenAI"}.get(provider, provider or "a custom endpoint")
        return f"Using your own {label} key"

    def _connect(self, provider: str, key: str, account: str, keep_failed: bool = False,
                 cancel: threading.Event | None = None) -> tuple[bool, str]:
        """Tries the provider with this key and saves it when the test question works, or
        always with keep_failed: a key from sign-in is valid, and a failed test then usually
        means the account has no credit yet, which the player can fix and test again."""
        preset = self._presets[provider]
        same = self._data.get("provider") == provider
        models = [m["id"] for m in config.models_for(provider)]
        model = self._data.get("model") if same and self._data.get("model") in models else preset["model"]
        client = ModelClient(preset["base_url"], model, key)
        result = self._tested(client)
        if not result["ok"] and not keep_failed:
            return False, result["note"]
        with self._lock:
            if cancel is not None and cancel.is_set():  # a newer sign-in, or quitting, replaced this one
                return False, "Sign-in was cancelled."
            self._data.update({"provider": provider, "base_url": preset["base_url"], "model": model,
                               "api_key": key, "account": account})
            self._data.pop("extra", None)
            self._save()
            self._rebuild()
        self._check = result
        return result["ok"], result["note"]

    def _start(self) -> None:
        """Called by the app once the window exists: resume listening and test the connection."""
        if self._data.get("setup_done"):
            self._start_companion()
        if self._brain.client is not None:
            self._check_later()

    def _stop(self) -> None:
        """The app is quitting: nothing waits for a question in progress."""
        if self._sign_in_cancel is not None:
            self._sign_in_cancel.set()
        self._companion.stop(wait=False)

    # ------------------------------------------------------------------ calls from the window

    @_call
    def getState(self, args):
        d = self._data
        games = self._games()
        g = self._selected(games)
        ai = None
        if self._brain.client is not None:
            pending = self._check["ok"] is None
            ai = {"provider": d.get("provider", ""), "model": d.get("model", ""), "account": self._account(),
                  "ok": self._check["ok"], "note": "Checking the connection" if pending else self._check["note"],
                  "credit": self._check["credit"], "needsCredit": self._check["fix"] == "credit"}
        return {"version": __version__, "setupDone": bool(d.get("setup_done")), "games": games,
                "game": g["id"] if g else None, "ai": ai,
                "companion": {"running": self._companion.running, "since": self._companion.since},
                "settings": {"autostart": self._system.autostart_enabled(), "tray": d.get("tray", True) is not False},
                "models": config.models_for(d.get("provider") or "openrouter"),
                "providers": [{"id": p, "name": self._presets[p]["name"], "key": self._presets[p]["key"],
                               "keyPage": bool(self._presets[p].get("key_url"))} for p in KEY_PROVIDERS],
                "activity": list(self._companion.activity)}

    @_call
    def chooseGameFolder(self, args):
        chosen = self._choose_folder()
        if not chosen:
            return {"ok": False, "message": "No folder chosen."}
        path = pathlib.Path(chosen)
        root = game.game_root(path)
        found = self._system.flavors_in(root)
        if not found:
            return {"ok": False, "message": "That folder has no World of Warcraft game in it. Choose the folder "
                                            "that contains _retail_ or _classic_."}
        pick = next((f for f in found if f["path"] == str(path)), None) or _preferred(found)
        with self._lock:
            roots = [r for r in self._data.get("roots") or [] if r != str(root)]
            self._data["roots"] = roots + [str(root)]
            self._data["wow"] = pick["id"]
            self._save()
        self._restart_if_running()
        return {"ok": True, "message": f"Found {', '.join(f['name'] for f in found)}."}

    @_call
    def selectGame(self, args):
        g = self._selected(self._games(), str(args.get("id") or ""))
        if g is None:
            return {"ok": False, "message": "That game folder is no longer there."}
        with self._lock:
            self._data["wow"] = g["id"]
            self._save()
        self._restart_if_running()
        return {"ok": True}

    @_call
    def installAddon(self, args):
        g = self._selected(self._games(), str(args.get("id") or "") or None)
        if g is None:
            return {"ok": False, "message": "Choose the World of Warcraft folder first."}
        before = g["addon"]
        try:
            done = game.install(pathlib.Path(g["path"]))
        except game.InstallError as e:
            return {"ok": False, "message": str(e)}
        if before == "missing":
            message = "Installed. If World of Warcraft is running, restart it: new addons load only when the game starts."
        else:
            message = "Updated. If World of Warcraft is running, type /reload in the game."
        if done.old:
            message += f" The folder also holds {len(done.old)} folders of the old Wowpilot prototype; delete them."
        self._restart_if_running()
        return {"ok": True, "message": message}

    @_call
    def signIn(self, args):
        with self._lock:                        # only the latest sign-in may finish
            if self._sign_in_cancel is not None:
                self._sign_in_cancel.set()
            cancel = self._sign_in_cancel = threading.Event()
        try:
            key = self._sign_in(cancel=cancel)
        except oauth.SignInError as e:
            return {"ok": False, "message": str(e)}
        ok, note = self._connect("openrouter", key, "oauth", keep_failed=True, cancel=cancel)
        if not ok and cancel.is_set():
            return {"ok": False, "message": "Sign-in was cancelled."}
        if not ok:
            return {"ok": False, "message": f"Signed in, but the test question failed. {note}"}
        return {"ok": True, "message": f"Connected. {note}."}

    @_call
    def cancelSignIn(self, args):
        """The player gave up on the browser step; the waiting signIn call answers at once."""
        with self._lock:
            if self._sign_in_cancel is not None:
                self._sign_in_cancel.set()
        return {"ok": True}

    @_call
    def saveKey(self, args):
        provider = str(args.get("provider") or "")
        key = str(args.get("key") or "").strip()
        if provider not in KEY_PROVIDERS:
            return {"ok": False, "message": "Choose a provider."}
        if self._presets[provider]["key"] and not key:
            return {"ok": False, "message": "Paste a key first."}
        ok, note = self._connect(provider, key, "key")
        return {"ok": ok, "message": f"Connected. {note}." if ok else note}

    @_call
    def setModel(self, args):
        wanted = str(args.get("id") or "")
        if wanted not in [m["id"] for m in config.models_for(self._data.get("provider") or "openrouter")]:
            return {"ok": False, "message": "That model isn't offered here."}
        with self._lock:
            self._data["model"] = wanted
            self._save()
            self._rebuild()
        self._check_later()
        return {"ok": True}

    @_call
    def checkConnection(self, args):
        ok, note = self._run_check()
        self._emit_safe({"type": "state"})
        return {"ok": ok, "message": note}

    @_call
    def finishSetup(self, args):
        if not self._start_companion():
            return {"ok": False, "message": "Choose the World of Warcraft folder first."}
        with self._lock:
            self._data["setup_done"] = True
            self._save()
        return {"ok": True}

    @_call
    def setCompanion(self, args):
        if args.get("running"):
            if not self._start_companion():
                return {"ok": False, "message": "Choose the World of Warcraft folder first."}
        else:
            self._companion.stop()
        return {"ok": True}

    @_call
    def setSetting(self, args):
        name, value = args.get("name"), bool(args.get("value"))
        if name == "autostart":
            if not self._system.set_autostart(value, self._autostart_command):
                return {"ok": False, "message": "Windows didn't accept the change."}
        elif name == "tray":
            with self._lock:
                self._data["tray"] = value
                self._save()
        else:
            return {"ok": False, "message": "Unknown setting."}
        return {"ok": True}

    @_call
    def openKeyPage(self, args):
        url = self._presets.get(str(args.get("provider") or ""), {}).get("key_url")
        if not url:
            return {"ok": False, "message": "This provider needs no key."}
        self._open_browser(url)
        return {"ok": True}

    @_call
    def openCredits(self, args):
        self._open_browser(oauth.CREDITS_URL)
        return {"ok": True}

    @_call
    def openLogs(self, args):
        self._system.open_folder(self._system.data_dir() / "logs")
        return {"ok": True}

    @property
    def _tray(self) -> bool:
        return self._data.get("tray", True) is not False
