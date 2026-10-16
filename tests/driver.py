"""Plays the companion's part in two steps so the test can put game time between them:
  receive <image> <addons> <probe>  -> decode, mark the slots 'not ready', compute the answer
  deliver <image> <addons> <probe>  -> write the answer into the reply slots
Both steps use the companion's own code (serve.respond, Slots.deliver).
"""
import json
import os
import pathlib
import sys

ENTRY = pathlib.Path(os.environ.get("GNOMECASTER_COMPANION")
                     or pathlib.Path(__file__).resolve().parent.parent / "companion" / "gnomecaster_companion.py")
sys.path.insert(0, str(ENTRY.parent))

from gnomecaster import config, protocol, serve  # noqa: E402
from gnomecaster.cli import make_brain  # noqa: E402
from gnomecaster.slots import Slots  # noqa: E402

step, image, addons_dir, probe = sys.argv[1:5]
slots = Slots(pathlib.Path(addons_dir), b"FAKEFONTDATA" if probe == "1" else None)
state = pathlib.Path(image + ".reply.json")

if step == "receive":
    packet = protocol.decode_image(image)
    pathlib.Path(image + ".json").write_text(json.dumps(packet, indent=1))
    reply = serve.respond(packet, slots, make_brain(config.resolve()))
    state.write_text(json.dumps({"slot": serve.slot_of(packet), "reply": reply}))
    print(f"   companion <- {packet.get('t')} #{packet.get('rid')} slot {packet.get('slot')}: {packet.get('text')}")
else:
    data = json.loads(state.read_text())
    slots.deliver(int(data["slot"]), data["reply"], keep_probe=True)
    print(f"   companion -> {data['reply'].get('say', '')[:90]}")
