"""Command line: setup, install, run, check, write-test, decode."""
from __future__ import annotations

import argparse
import getpass
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import time

from . import config, game, protocol, serve, winsys
from .brain import Brain
from .model import ModelClient, ModelError
from .slots import Slots, find_probe_font
from .transcript import Transcript

USAGE = """Gnomecaster companion: answers the questions you type in the game.

  start       do whatever is missing (Pillow, setup, addon install), then run
  setup       connect an AI model and find the game
  install     copy the addon into the game
  run         keep running while you play
  check       test the AI connection
  write-test  write a test reply (for /gc poll)
  decode      decode one screenshot (debugging)
"""


def make_brain(settings: config.Settings, transcripts: pathlib.Path | None = None) -> Brain:
    client = ModelClient(settings.base_url, settings.model, settings.api_key, settings.extra,
                         web_search=settings.web_search) if settings.has_model else None
    return Brain(client, game.ADDON_DIR, Transcript(transcripts) if transcripts else None)


def ask(question: str, default: str = "") -> str:
    try:
        answer = input(f"{question}{f' [{default}]' if default else ''}: ").strip()
    except EOFError:
        answer = ""
    return answer or default


def cmd_setup(args) -> None:
    current = config.load_file()
    path = config.config_path()
    print(f"Gnomecaster setup. Settings are saved in {path}\n")
    names = list(config.PRESETS) + ["none"]
    provider = args.provider
    if not provider and not args.yes:
        print("Which AI should answer your questions?")
        for i, name in enumerate(names, 1):
            label = config.PRESETS[name]["label"] if name in config.PRESETS else "None: offline demo only"
            print(f"  {i}) {label}")
        default = str(names.index(current["provider"]) + 1) if current.get("provider") in names else "1"
        choice = ask("Choice", default)
        provider = names[int(choice) - 1] if choice.isdigit() and 1 <= int(choice) <= len(names) else choice
    provider = provider or current.get("provider") or "openrouter"
    if provider not in names:
        raise SystemExit(f"Unknown provider '{provider}'. Choose one of: {', '.join(names)}")

    data = {"provider": provider, "base_url": "", "model": "", "api_key": ""}
    if provider != "none":
        preset = config.PRESETS[provider]
        same = current.get("provider") == provider
        base_default = (current.get("base_url") if same else "") or preset["base_url"]
        data["base_url"] = args.base_url or (base_default if args.yes or preset["base_url"] else ask("Endpoint URL", base_default))
        model_default = (current.get("model") if same else "") or preset["model"]
        data["model"] = args.model or (model_default if args.yes else ask("Model", model_default))
        if preset["key"]:
            key = ""
            if args.key_env:
                key = os.environ.get(args.key_env, "")
                if not key:
                    raise SystemExit(f"The environment variable {args.key_env} is empty.")
            elif args.key_stdin:
                key = sys.stdin.readline().strip()
            elif not args.yes:
                hint = f" ({preset['key_hint']})" if preset["key_hint"] else ""
                keep = " Press Enter to keep the current one." if same and current.get("api_key") else ""
                print(f"Paste your API key{hint}. Typing is hidden.{keep}")
                key = getpass.getpass("API key: ").strip()
            data["api_key"] = key or (current.get("api_key", "") if same else "")
            if not data["api_key"]:
                raise SystemExit("An API key is needed for this provider.")
    if not data["model"] and provider != "none":
        raise SystemExit("A model name is needed.")

    found = game.find_flavor(args.wow or current.get("wow") or None)
    wow_default = str(found) if found else ""
    data["wow"] = args.wow or (wow_default if args.yes else ask("World of Warcraft folder", wow_default))
    if data["wow"] and not game.find_flavor(data["wow"]):
        print(f"  note: no game files found in {data['wow']}; check the folder before installing.")
    elif data["wow"]:
        data["wow"] = str(game.find_flavor(data["wow"]))

    if provider != "none" and not args.no_check:
        print(f"\nChecking {data['model']} at {data['base_url']} ...")
        try:
            note = ModelClient(data["base_url"], data["model"], data["api_key"]).check()
            print(f"  OK: {note}")
        except ModelError as e:
            print(f"  PROBLEM: {e.message}")
            if args.yes or ask("Save these settings anyway? (y/N)", "n").lower() not in ("y", "yes"):
                raise SystemExit("Nothing saved.")
    saved = config.save_file(data, path)
    print(f"\nSaved to {saved}.")
    print("Next: install the addon (python gnomecaster_companion.py install), restart the game, then run "
          "python gnomecaster_companion.py run")


def cmd_start(args) -> None:
    """One command for players: fills in whatever is missing, then runs."""
    if importlib.util.find_spec("PIL") is None:
        requirements = pathlib.Path(__file__).resolve().parents[1] / "requirements.txt"
        print("Pillow (an image library the companion needs) is not installed.")
        if ask("Install it now? (Y/n)", "y").lower() not in ("y", "yes"):
            raise SystemExit(f'Install it yourself with:  "{sys.executable}" -m pip install -r "{requirements}"')
        if subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(requirements)]).returncode != 0:
            raise SystemExit("Installing Pillow failed; see the messages above.")
    if not config.config_path().exists():
        print("First start: a few questions to connect an AI model.\n")
        cmd_setup(argparse.Namespace(provider=None, base_url=None, model=None, key_env=None, key_stdin=False,
                                     wow=None, yes=False, no_check=False))
        print()
    settings = config.resolve()
    flavor = game.resolve_flavor(settings.wow or None)
    status = game.addon_status(flavor)
    if status != "current":
        for note in install(flavor, restart=False):     # the advice below depends on the status
            print(note)
        if status == "missing":
            print("The addon is new: restart the game completely (a /reload is not enough), then come back here.")
        else:
            print("The addon was updated: type /reload in the game.")
    cmd_run(argparse.Namespace(wow=None, font=None, no_probe=False, no_check=False))


def install(flavor: pathlib.Path, restart: bool = True) -> list[str]:
    try:
        return game.install_notes(game.install(flavor), restart)
    except game.InstallError as e:
        hint = " If it still fails, run this command from a terminal opened with 'Run as administrator'." \
            if e.denied else ""
        raise SystemExit(str(e) + hint) from None


def cmd_install(args) -> None:
    settings = config.resolve(args.wow)
    for note in install(game.resolve_flavor(settings.wow or None)):
        print(note)


def cmd_check(args) -> None:
    settings = config.resolve()
    if not settings.has_model:
        raise SystemExit("No AI model is set up. Run setup first.")
    brain = make_brain(settings)
    print(f"Checking {brain.describe()} ...")
    ok = brain.run_check()
    print(("OK: " if ok else "PROBLEM: ") + str(brain.check_note))
    sys.exit(0 if ok else 1)


def cmd_run(args) -> None:
    settings = config.resolve(args.wow)
    flavor = game.resolve_flavor(settings.wow or None)
    protocol.require_pillow()
    slots = Slots(flavor / "Interface" / "AddOns", None if args.no_probe else find_probe_font(args.font))
    missing = slots.missing()
    if missing:
        raise SystemExit(f"Reply slots missing in {slots.addons} (e.g. {slots.dir(missing[0]).name}). "
                         "Run the install command first, then restart the game.")
    slots.clear_probes()
    transcripts = winsys.data_dir() / "transcripts"
    brain = make_brain(settings, transcripts)
    shots = flavor / "Screenshots"
    shots.mkdir(exist_ok=True)
    print(f"Gnomecaster companion watching {shots}")
    print(f"  AI: {brain.describe()}" + (", may search the web" if brain.client and brain.client.web_search else ""))
    print(f"  transcripts: {transcripts}")
    print(f"  ready signal font: {'yes' if slots.font else 'none found (timed polling only)'}")
    if brain.client and not args.no_check:
        print("  checking the AI connection ...")
        ok = brain.run_check()
        print(f"  {'OK' if ok else 'PROBLEM'}: {brain.check_note}")
    print("  In game: /gc test   (Ctrl+C here to stop)")
    serve.run_forever(shots, slots, brain)


def cmd_write_test(args) -> None:
    settings = config.resolve(args.wow)
    flavor = game.resolve_flavor(settings.wow or None)
    slots = Slots(flavor / "Interface" / "AddOns", None if args.no_probe else find_probe_font(args.font))
    missing = slots.missing()
    if missing:
        raise SystemExit("Reply slots are missing. Run the install command first, then restart the game.")
    stamp = time.strftime("%H:%M:%S")
    slots.deliver(args.slot, {"sid": "*", "rid": 0, "say": f"Inbox test OK - written by the companion at {stamp}",
                              "written": stamp}, keep_probe=True)
    print(f"Test reply written to slots {args.slot}-60" + (" with ready signal." if slots.font else " (without ready signal)."))
    print("In game: /gc probe  (should now say true)  then  /gc poll  (should show the test text)" if slots.font
          else "In game: /gc poll  (should show the test text)")


def cmd_decode(args) -> None:
    packet = protocol.decode_image(args.file)
    print(json.dumps(packet, indent=2, ensure_ascii=False) if packet else "No Gnomecaster beacon in that image.")


def main(argv=None) -> None:
    # The companion's window is its log: print each line at once, also when piped or logged.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True, errors="replace")
    ap = argparse.ArgumentParser(prog="gnomecaster_companion.py", description=USAGE,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="command")
    sub.add_parser("start", help="do whatever is missing (Pillow, setup, addon install), then run")
    sp = sub.add_parser("setup", help="connect an AI model and find the game")
    sp.add_argument("--provider", choices=list(config.PRESETS) + ["none"])
    sp.add_argument("--base-url")
    sp.add_argument("--model")
    sp.add_argument("--key-env", metavar="VAR", help="read the API key from this environment variable")
    sp.add_argument("--key-stdin", action="store_true", help="read the API key from standard input")
    sp.add_argument("--wow", help="game folder")
    sp.add_argument("--yes", action="store_true", help="no questions: use flags, current settings and defaults")
    sp.add_argument("--no-check", action="store_true", help="save without testing the connection")
    for name, helptext in (("install", "copy the addon into the game"), ("run", "keep running while you play"),
                           ("write-test", "write a test reply (for /gc poll)")):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("--wow", help="game folder or flavor folder (e.g. ...\\World of Warcraft\\_retail_)")
        if name != "install":
            sp.add_argument("--font", help="TrueType font used as the ready signal (optional)")
            sp.add_argument("--no-probe", action="store_true", help="disable the ready signal")
        if name == "run":
            sp.add_argument("--no-check", action="store_true", help="skip the AI connection check at start")
        if name == "write-test":
            sp.add_argument("--slot", type=int, default=1, help="first slot to write (see /gc status)")
    sub.add_parser("check", help="test the AI connection")
    sp = sub.add_parser("decode", help="decode one screenshot (debugging)")
    sp.add_argument("file")
    args = ap.parse_args(argv)
    try:
        {"start": cmd_start, "setup": cmd_setup, "install": cmd_install, "run": cmd_run, "check": cmd_check,
         "write-test": cmd_write_test, "decode": cmd_decode}[args.cmd](args)
    except config.ConfigError as e:
        raise SystemExit(str(e)) from None
