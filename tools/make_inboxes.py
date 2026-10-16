#!/usr/bin/env python3
"""Generate the Gnomecaster_InboxNN load-on-demand reply slots next to the main addon."""
import pathlib
import sys

NUM_SLOTS = 60
INTERFACE = "120105, 120100, 50504, 20506, 11509, 16001"

TOC = """## Interface: {iface}
## Title: Gnomecaster Inbox {n:02d}
## Notes: Reply slot used by Gnomecaster. Keep enabled.
## LoadOnDemand: 1
## Dependencies: Gnomecaster
## Group: Gnomecaster
## IconTexture: Interface\\AddOns\\Gnomecaster\\Media\\icon

inbox.lua
"""

PLACEHOLDER = "-- Gnomecaster reply slot (empty until the companion writes a reply)\n"


def main(out_dir: str) -> None:
    root = pathlib.Path(out_dir)
    for n in range(1, NUM_SLOTS + 1):
        name = f"Gnomecaster_Inbox{n:02d}"
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.toc").write_text(TOC.format(iface=INTERFACE, n=n), encoding="utf-8")
        (d / "inbox.lua").write_text(PLACEHOLDER, encoding="utf-8")
        (d / "ready.ttf").write_bytes(b"")  # must exist at login; companion fills it when a reply is ready
    print(f"wrote {NUM_SLOTS} inbox slots to {root}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(pathlib.Path(__file__).resolve().parent.parent / "addon"))
