"""The offline demo: a few fixed request types answered without any AI model.

Used only when no model is set up, so the whole pipeline can be tried for free. Every
answer says it comes from the demo. When a model is set up and fails, the player gets the
error instead: keyword rules must not guess at what a failed model would have done.
"""
from __future__ import annotations

import re

RAID_ICONS = {"star": 1, "circle": 2, "diamond": 3, "triangle": 4, "moon": 5, "square": 6, "cross": 7, "x": 7, "skull": 8}


def offline_answer(text: str, ctx: dict) -> dict:
    """Tiny rule-based stand-in so the whole pipeline can be tested without a model."""
    t = text.lower()
    loc = ctx.get("location") or {}
    focus = ctx.get("focus") or {}

    m = re.search(r"(\d{1,2}(?:\.\d+)?)\s*[, ]\s*(\d{1,2}(?:\.\d+)?)", t)
    if m and any(w in t for w in ("way", "go to", "take me", "coord")) and loc.get("mapID"):
        x, y = float(m.group(1)), float(m.group(2))
        return {"say": f"Arrow set to {x:.1f}, {y:.1f} in {loc.get('map', 'this zone')}.",
                "actions": [{"type": "waypoint", "map": loc["mapID"], "x": x / 100, "y": y / 100, "title": "Gnomecaster"}]}

    if "quest" in t:
        if focus:
            title = focus.get("title") or f"quest {focus.get('quest')}"
            say = f"You're following \"{title}\"."
            if focus.get("obj"):
                say += " Objectives: " + "; ".join(focus["obj"]) + "."
            actions = []
            nxt = focus.get("next")
            if nxt:
                actions.append({"type": "waypoint", "map": nxt["map"], "x": nxt["x"], "y": nxt["y"], "title": title})
                say += " Arrow is on the next step."
            else:
                say += " The game gives no location for the next step."
            return {"say": say, "actions": actions}
        quests = ctx.get("quests") or []
        if quests:
            names = ", ".join(q.get("title", "?") for q in quests[:6])
            return {"say": f"Your quests: {names}. Click one in the quest log to follow it, then ask again."}
        return {"say": "Your quest log looks empty."}

    for word, icon in RAID_ICONS.items():
        if re.search(rf"\b{word}\b", t) and ("mark" in t or word == "skull"):
            return {"say": f"Marked your target with {word}.", "actions": [{"type": "mark", "icon": icon}]}

    if "macro" in t:
        m = re.search(r"macro (?:for |with )?(?:a |an )?(?:mouseover )?([a-z' ]+?)(?:\s+(?:macro|on|bound|bind|to|in|at)\b|[,.!]|$)", t)
        spell = (m.group(1).strip().title() if m else "").replace("Mouseover ", "")
        if not spell:
            return {"say": "Which spell should the macro cast?"}
        harmful = any(w in t for w in ("harm", "attack", "damage", "dps", "enemy"))
        cond = "[@mouseover,harm,nodead][]" if harmful else "[@mouseover,help,nodead][@target,help,nodead][@player]"
        name = spell[:16]
        actions = [{"type": "macro", "name": name, "body": f"#showtooltip\n/cast {cond} {spell}"}]
        sm = re.search(r"slot (\d{1,3})", t)
        if sm:
            actions.append({"type": "bar", "macro": name, "slot": int(sm.group(1))})
        km = re.search(r"(?:bind(?:ed)?|bound|key)\s+(?:it\s+)?(?:to\s+)?((?:(?:shift|ctrl|alt)[- ]?)*(?:f\d{1,2}|[a-z0-9]))\b", t)
        if km:
            key = re.sub(r"(shift|ctrl|alt)[- ]?", lambda g: g.group(1).upper() + "-", km.group(1)).upper()
            actions.append({"type": "bind", "key": key, "macro": name})
        return {"say": f"Here's a {'mouseover attack' if harmful else 'mouseover help'} macro for {spell}.", "actions": actions}

    if "error" in t:
        errs = ctx.get("errors") or {}
        for kind, label in (("lua", "Lua error"), ("blocked", "Blocked action"), ("ui", "Game message")):
            if errs.get(kind):
                return {"say": f"Latest {label}: {errs[kind][0].get('msg')}. (Connect an AI model and I'll explain it.)"}
        return {"say": "I haven't seen any errors this session."}

    if "where am i" in t:
        if loc:
            pos = f" at {loc['x'] * 100:.1f}, {loc['y'] * 100:.1f}" if loc.get("x") is not None else ""
            return {"say": f"You're in {loc.get('subzone') or loc.get('zone') or loc.get('map')}{pos}."}

    return {"say": "No AI model is set up yet; connect one in the Gnomecaster app. "
                   "The demo understands: 'take me to my quest', 'way 45.2 63.1', 'mark skull', "
                   "'macro for Rejuvenation on slot 5 bind to shift-e', 'what was that error', 'where am I'."}


def answer(text: str, ctx: dict) -> dict:
    reply = offline_answer(text, ctx)
    reply["say"] = "(demo) " + reply.get("say", "")
    return reply
