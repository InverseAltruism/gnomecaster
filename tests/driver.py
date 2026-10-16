"""Plays the companion's part in two steps so the test can put game time between them:
  receive <image> <addons> <probe>  -> decode, clear ready signals, compute the answer
  deliver <image> <addons> <probe>  -> write the answer into the reply slots
"""
import importlib.util
import json
import os
import pathlib
import sys
import time

COMPANION = os.environ.get("WOWPILOT_COMPANION") or str(pathlib.Path(__file__).resolve().parent.parent / "companion" / "wowpilot_companion.py")
spec = importlib.util.spec_from_file_location("companion", COMPANION)
companion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(companion)

step, image, addons_dir, probe = sys.argv[1:5]
slots = companion.Slots(pathlib.Path(addons_dir), b"FAKEFONTDATA" if probe == "1" else None)
state = pathlib.Path(image + ".reply.json")

if step == "receive":
    packet = companion.decode_image(image)
    pathlib.Path(image + ".json").write_text(json.dumps(packet, indent=1))
    slots.clear_probes(int(packet.get("slot") or 1))
    reply = companion.Brain().answer(packet)
    reply.update({"sid": packet.get("sid"), "rid": packet.get("rid"), "t": packet.get("t"), "written": time.strftime("%H:%M:%S")})
    state.write_text(json.dumps({"slot": packet.get("slot"), "reply": reply}))
    print(f"   companion <- {packet.get('t')} #{packet.get('rid')} slot {packet.get('slot')}: {packet.get('text')}")
else:
    data = json.loads(state.read_text())
    slots.deliver(int(data["slot"]), data["reply"], keep_probe=True)
    print(f"   companion -> {data['reply'].get('say', '')[:90]}")
