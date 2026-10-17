"""The desktop app: one window (desktop/ui) and a tray icon around the companion.

Closing the window keeps Gnomecaster in the tray, so questions from the game are still
answered; Quit in the tray menu ends it. A second start shows the running app instead.
"""
from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import pathlib
import queue
import secrets
import shutil
import socket
import sys
import threading
import time

from . import __version__, config, game, winsys
from .app_api import Api

log = logging.getLogger("gnomecaster")
MUTEX = "Gnomecaster.Running"           # the installer closes the app by it (packaging/gnomecaster.iss)


def resource(*parts: str) -> pathlib.Path:
    """A file shipped with the app: under _MEIPASS when built, else in the source tree."""
    base = pathlib.Path(sys._MEIPASS) if getattr(sys, "frozen", False) else pathlib.Path(__file__).resolve().parents[2]
    return base.joinpath(*parts)


def setup_logging(folder: pathlib.Path) -> pathlib.Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "gnomecaster.log"
    handler = logging.handlers.RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    return path


class SingleInstance:
    """The running app listens on a loopback port named in instance.json; a later start asks
    it to show its window and exits. Which process is first is decided by the Windows mutex
    (winsys.claim_instance); the port only carries the request to show. The token keeps a
    stale file from reaching an unrelated program that took the port since."""

    def __init__(self, folder: pathlib.Path):
        self.file = folder / "instance.json"
        self.server: socket.socket | None = None
        self.token: str | None = None

    def ask(self, command: str = "show") -> bool:
        """Sends "show" or "quit" to the running app; True when it acknowledged."""
        try:
            info = json.loads(self.file.read_text(encoding="utf-8"))
            with socket.create_connection(("127.0.0.1", int(info["port"])), timeout=2) as s:
                s.sendall(f"{info['token']} {command}\n".encode())
                return s.recv(16).startswith(b"ok")
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def ask_running_to_show(self) -> bool:
        return self.ask("show")

    def listen(self, on_show, on_quit=lambda: None) -> None:
        token = self.token = secrets.token_hex(16)
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(4)
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps({"port": self.server.getsockname()[1], "token": token, "pid": os.getpid()}),
                             encoding="utf-8")

        def serve():
            while True:
                try:
                    conn, _ = self.server.accept()
                except OSError:
                    return                      # closed at exit
                with conn:
                    conn.settimeout(2)
                    try:
                        sent, _, command = conn.recv(80).decode(errors="replace").strip().partition(" ")
                        if sent == token and command in ("show", "quit"):
                            conn.sendall(b"ok")
                            (on_quit if command == "quit" else on_show)()
                    except OSError:
                        pass

        threading.Thread(target=serve, name="instance", daemon=True).start()

    def close(self) -> None:
        if self.server is not None:
            self.server.close()
        try:
            if json.loads(self.file.read_text(encoding="utf-8")).get("token") == self.token:
                self.file.unlink()              # only our own: another instance may have written it since
        except (OSError, ValueError, AttributeError):
            pass


def defer_to_running(instance: SingleInstance, claimed: bool | None, wait: float = 10.0) -> bool:
    """True when another Gnomecaster is running; it has been asked to show its window.
    claimed is winsys.claim_instance's answer. Without one (not Windows) the check is a
    best effort; with False this process exits even if the other never answers, because it
    may still be starting."""
    if claimed is None:
        return instance.ask_running_to_show()
    if claimed:
        return False
    deadline = time.monotonic() + wait
    while not instance.ask_running_to_show() and time.monotonic() < deadline:
        time.sleep(0.25)
    return True


SIZE, MIN_SIZE = (1040, 700), (760, 540)


def window_geometry(screens) -> tuple[int, int, int | None, int | None]:
    """Width, height and position: the full size where it fits, else most of the main screen,
    centred in its work area (the screen without the taskbar). A 1366 x 768 laptop at 125 %
    scaling has about 1093 x 614 logical pixels. Windows' own placement can put a tall window
    under the taskbar, so the position is set; None leaves it to the system."""
    width, height, x, y = SIZE[0], SIZE[1], None, None
    try:
        main = screens[0]
        area = getattr(main, "frame", None)       # on Windows, the WinForms WorkingArea
        if area is not None and hasattr(area, "Width"):
            ax, ay, aw, ah = int(area.X), int(area.Y), int(area.Width), int(area.Height)
        else:
            ax, ay, aw, ah = int(main.x), int(main.y), int(main.width), int(main.height)
        width, height = min(width, int(aw * 0.92)), min(height, int(ah * 0.92))
        width, height = max(MIN_SIZE[0], width), max(MIN_SIZE[1], height)
        x, y = ax + max(0, (aw - width) // 2), ay + max(0, (ah - height) // 2)
    except (IndexError, AttributeError, TypeError, ValueError):
        pass
    return width, height, x, y


def quit_running(instance: "SingleInstance", wait: float = 15.0) -> bool:
    """For the installer and uninstaller: asks a running Gnomecaster to quit and waits until its
    process has exited. Setup checks the mutex right after this returns, and the process still
    holds it for a moment after removing its instance file. True when one was running."""
    if not instance.ask("quit"):
        return False
    deadline = time.monotonic() + wait
    while (instance.file.exists() or winsys.instance_held(MUTEX)) and time.monotonic() < deadline:
        time.sleep(0.2)
    return True


def remove_everything(config_path: pathlib.Path, folder: pathlib.Path) -> list[str]:
    """For the uninstaller, when the player asks: the addon from every game version the app
    knows, then the settings (with the API key) and the logs. Returns what was removed."""
    removed = []
    try:
        data = config.load_file(config_path)
    except config.ConfigError:
        data = {}
    roots = list(data.get("roots") or []) + ([data["wow"]] if data.get("wow") else [])
    for g in winsys.find_games(roots):
        for name in game.remove(pathlib.Path(g["path"])):
            removed.append(f"{g['path']}\\Interface\\AddOns\\{name}")
    for target in (config_path.parent, folder):
        if target.is_dir() and target.name.lower() == "gnomecaster":
            shutil.rmtree(target, ignore_errors=True)
            removed.append(str(target))
    return removed


PAGE_PROBE = ("JSON.stringify({ready: document.body.dataset.ready || '', "
              "screen: document.getElementById('app').dataset.screen || ''})")


def smoke_passed(page: dict) -> bool:
    """The page rendered a screen from the backend's state (app.js sets ready last)."""
    return page.get("ready") == "true" and page.get("screen") in ("setup", "main")


def autostart_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --background'
    return f'"{sys.executable}" "{pathlib.Path(sys.argv[0]).resolve()}" --background'


class Shell:
    """Owns the window, the tray icon and the order of shutting down."""

    def __init__(self, background: bool, smoke_dir: pathlib.Path | None = None):
        import webview                          # imported here: the tests import this module without it
        self.webview = webview
        self.events: queue.Queue = queue.Queue()
        self.quitting = False
        self.stopped = False
        self.tray_hint_shown = False
        self.icon = None
        self.background = background
        self.smoke_dir = smoke_dir
        self.window = None
        self.api = Api(emit=self.events.put, on_companion=self.update_tray, choose_folder=self.choose_folder,
                       autostart_command=autostart_command())

    # the companion only queues its events; this one thread delivers them to the page in order
    def pump(self) -> None:
        self.window.events.loaded.wait()
        while True:
            event = self.events.get()
            if event is None:
                return
            try:
                self.window.evaluate_js("GC.emit(" + json.dumps(event) + ")")
            except Exception:  # noqa: BLE001 - the page may be reloading; the next getState catches up
                log.exception("could not deliver an event to the window")

    def on_loaded(self) -> None:
        log.info("window loaded")

    def choose_folder(self) -> str | None:
        picked = self.window.create_file_dialog(self.webview.FileDialog.FOLDER)
        return picked[0] if picked else None

    def show(self) -> None:
        if self.window is not None:             # a second start can arrive before the window exists
            self.window.show()
            self.window.restore()

    def on_closing(self):
        if self.quitting or self.icon is None or not self.api._tray:
            self.quitting = True
            self.shutdown()
            return True
        self.window.hide()
        if self.icon is not None and not self.tray_hint_shown:
            self.tray_hint_shown = True
            try:
                self.icon.notify("Gnomecaster keeps answering in the background. Its icon is under the arrow "
                                 "next to the clock; right-click it to open or quit.", "Still running")
            except Exception:  # noqa: BLE001 - notifications are optional
                pass
        return False                            # cancels the close

    def quit(self) -> None:
        self.quitting = True
        if self.window is None:                 # asked to quit before the window exists
            self.shutdown()
            return
        self.window.destroy()                   # fires closing, which shuts down

    def shutdown(self) -> None:
        if self.stopped:
            return
        self.stopped = True
        self.api._stop()
        self.events.put(None)
        if self.icon is not None:
            self.icon.stop()                    # its Windows thread is not a daemon: the process waits for it

    def update_tray(self, running: bool) -> None:
        if self.icon is not None:
            self.icon.update_menu()             # the Windows menu is built once, not on each right-click

    def start_tray(self) -> None:
        import pystray
        from PIL import Image
        image = Image.open(resource("assets", "brand", "png", "icon-64.png"))

        def toggle(icon, item):
            def work():                         # pausing waits for a question in progress
                self.api.setCompanion({"running": not self.api._companion.running})
                self.events.put({"type": "state"})
            threading.Thread(target=work, name="tray-toggle", daemon=True).start()

        menu = pystray.Menu(
            pystray.MenuItem("Open Gnomecaster", lambda icon, item: self.show(), default=True),
            pystray.MenuItem("Answer questions", toggle, checked=lambda item: self.api._companion.running),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit Gnomecaster", lambda icon, item: self.quit()))
        self.icon = pystray.Icon("Gnomecaster", image, "Gnomecaster", menu)
        self.icon.run_detached()

    def run(self) -> None:
        try:
            self.start_tray()
        except Exception:  # noqa: BLE001 - without a tray the window still works; closing it quits
            log.exception("no tray icon")
            self.icon = None
        try:
            screens = self.webview.screens
        except Exception:  # noqa: BLE001 - the default size is a fine fallback
            screens = []
        width, height, x, y = window_geometry(screens)
        self.window = self.webview.create_window(
            "Gnomecaster", str(resource("desktop", "ui", "index.html")), js_api=self.api, width=width, height=height,
            x=x, y=y, min_size=MIN_SIZE, hidden=self.background and self.icon is not None, background_color="#160F33")
        self.window.events.closing += self.on_closing
        self.window.events.loaded += self.on_loaded
        threading.Thread(target=self.pump, name="events", daemon=True).start()
        try:
            self.webview.start(self.after_start, private_mode=True)
        finally:
            self.shutdown()

    def after_start(self) -> None:
        self.api._start()
        if self.smoke_dir is not None:
            threading.Thread(target=self.smoke_test, name="smoke", daemon=True).start()

    def smoke_test(self) -> None:
        """For the build: proves the packaged app opens its window, runs the page and reaches
        the backend, then records what the window shows and quits."""
        out = {"version": __version__, "ok": False}
        try:
            if not self.window.events.loaded.wait(90):
                raise RuntimeError("the page did not load within 90 s")
            deadline = time.monotonic() + 30
            page = {"ready": "", "screen": "loading"}
            while not page["ready"] and page["screen"] != "error" and time.monotonic() < deadline:
                time.sleep(0.5)
                page = json.loads(self.window.evaluate_js(PAGE_PROBE))
            out.update(page, ok=smoke_passed(page), tray=self.icon is not None,
                       title=self.window.evaluate_js("document.title"))
            time.sleep(1.5)                     # let the entrance animation finish before the picture
            if sys.platform == "win32":
                from PIL import ImageGrab
                w = self.window
                ImageGrab.grab(bbox=(w.x, w.y, w.x + w.width, w.y + w.height), all_screens=True).save(
                    self.smoke_dir / "window.png")
        except Exception as e:  # noqa: BLE001 - reported in the result file
            out["error"] = f"{type(e).__name__}: {e}"
        (self.smoke_dir / "smoke.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        self.quit()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="Gnomecaster")
    ap.add_argument("--background", action="store_true", help="start in the tray (used when starting with Windows)")
    ap.add_argument("--smoke-test", metavar="FOLDER", type=pathlib.Path, help=argparse.SUPPRESS)
    ap.add_argument("--quit", action="store_true", help="ask a running Gnomecaster to quit (the installer uses it)")
    ap.add_argument("--remove-everything", action="store_true",
                    help="remove the addon from the game, the settings and the logs (the uninstaller uses it)")
    args = ap.parse_args(argv)
    folder = winsys.data_dir()
    if args.quit or args.remove_everything:        # no window, no log file, no instance claim
        quit_running(SingleInstance(folder))
        if args.remove_everything:
            remove_everything(config.config_path(), folder)
        return 0
    if sys.platform == "win32":                 # taskbar grouping and the name on notifications
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("InverseAltruism.Gnomecaster")
    claimed = winsys.claim_instance(MUTEX)
    logfile = setup_logging(folder / "logs")
    log.info("Gnomecaster %s starting, log %s", __version__, logfile)
    instance = SingleInstance(folder)
    if defer_to_running(instance, claimed):
        log.info("already running: asked the other window to show")
        return 0
    shell = Shell(background=args.background, smoke_dir=args.smoke_test)
    instance.listen(shell.show, shell.quit)
    try:
        shell.run()
    finally:
        instance.close()
        log.info("Gnomecaster stopped")
    return 0
