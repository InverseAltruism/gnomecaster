#!/usr/bin/env python3
"""Gnomecaster companion. Start with:  python gnomecaster_companion.py setup

Requires Python 3.10+ and Pillow (requirements.txt). See README.md.
"""
import pathlib
import sys

if sys.version_info < (3, 10):
    sys.exit(f"Gnomecaster needs Python 3.10 or newer; this is {sys.version.split()[0]}. "
             "Install a current Python from https://www.python.org/downloads/")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from gnomecaster.cli import main  # noqa: E402

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nbye")
