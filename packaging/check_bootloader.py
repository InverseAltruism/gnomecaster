#!/usr/bin/env python3
"""Fails unless the installed PyInstaller's Windows bootloader was compiled on this machine.

Compares PyInstaller/bootloader/Windows-64bit-intel/runw.exe (the one a windowed app is
built on) with the copy inside PyInstaller's own Windows wheel on PyPI, whose download is
checked against packaging/requirements-build.txt. Equal files mean the stock bootloader is
in use, the one antivirus heuristics see in many unrelated programs.
"""
from __future__ import annotations

import hashlib
import io
import json
import pathlib
import re
import sys
import urllib.request
import zipfile

import PyInstaller

HERE = pathlib.Path(__file__).resolve().parent
MEMBER = "PyInstaller/bootloader/Windows-64bit-intel/runw.exe"


def main() -> int:
    installed = pathlib.Path(PyInstaller.__file__).parent / "bootloader" / "Windows-64bit-intel" / "runw.exe"
    if not installed.is_file():
        print(f"No Windows bootloader at {installed}: run this on the Windows build machine.")
        return 1
    version = PyInstaller.__version__
    locked = (HERE / "requirements-build.txt").read_text()
    block = re.search(rf"^pyinstaller=={re.escape(version)} \\\n((?:\s+--hash=sha256:\w+(?: \\)?\n)+)", locked, re.M | re.I)
    if not block:
        print(f"PyInstaller {version} is not the version in requirements-build.txt")
        return 1
    allowed = set(re.findall(r"sha256:(\w+)", block.group(1)))
    with urllib.request.urlopen(f"https://pypi.org/pypi/pyinstaller/{version}/json", timeout=30) as r:
        files = json.load(r)["urls"]
    wheel = next(f for f in files if f["filename"].endswith("-win_amd64.whl"))
    with urllib.request.urlopen(wheel["url"], timeout=120) as r:
        data = r.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest not in allowed:
        print(f"{wheel['filename']} has sha256 {digest}, which requirements-build.txt does not list")
        return 1
    stock = zipfile.ZipFile(io.BytesIO(data)).read(MEMBER)
    here = installed.read_bytes()
    print(f"installed runw.exe {hashlib.sha256(here).hexdigest()}\nstock runw.exe     {hashlib.sha256(stock).hexdigest()}")
    if here == stock:
        print("The bootloader is PyInstaller's stock build: it was not compiled here.")
        return 1
    print("The bootloader was compiled on this machine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
