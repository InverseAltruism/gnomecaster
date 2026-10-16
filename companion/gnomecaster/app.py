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
import socket
import sys
import threading
import time

from . import __version__, winsys
from .app_api import Api

log = logging.getLogger("gnomecaster")
MUTEX = "Gnomecaster.Running"           # also the installer's AppMutex (packaging/gnomecaster.iss)


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

    def ask_running_to_show(self) -> bool:
        try:
            info = json.loads(self.file.read_text(encoding="utf-8"))
            with socket.create_connection(("127.0.0.1", int(info["port"])), timeout=2) as s:
                s.sendall((info["token"] + "\n").encode())
                return s.recv(16).startswith(b"shown")
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def listen(self, on_show) -> None:
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
                        if conn.recv(64).decode(errors="replace").strip() == token:
                            on_show()
                            conn.sendall(b"shown")
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
                self.icon.notify("Gnomecaster keeps answering from the tray. Quit it from the tray icon's menu.",
                                 "Still running")
            except Exception:  # noqa: BLE001 - notifications are optional
                pass
        return False                            # cancels the close

    def quit(self) -> None:
        self.quitting = True
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
        self.window = self.webview.create_window(
            "Gnomecaster", str(resource("desktop", "ui", "index.html")), js_api=self.api, width=1040, height=700,
            min_size=(720, 520), hidden=self.background and self.icon is not None, background_color="#160F33")
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
    args = ap.parse_args(argv)
    if sys.platform == "win32":                 # taskbar grouping and the name on notifications
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("InverseAltruism.Gnomecaster")
    claimed = winsys.claim_instance(MUTEX)
    folder = winsys.data_dir()
    logfile = setup_logging(folder / "logs")
    log.info("Gnomecaster %s starting, log %s", __version__, logfile)
    instance = SingleInstance(folder)
    if defer_to_running(instance, claimed):
        log.info("already running: asked the other window to show")
        return 0
    shell = Shell(background=args.background, smoke_dir=args.smoke_test)
    instance.listen(shell.show)
    try:
        shell.run()
    finally:
        instance.close()
        log.info("Gnomecaster stopped")
    return 0
