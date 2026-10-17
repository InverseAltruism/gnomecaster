#!/usr/bin/env python3
"""Evaluate AI models on Gnomecaster's real request path.

Every scenario in eval_scenarios.py goes through the companion's Brain (the same system
prompt, parsing and sanitizing a player gets), then through the addon's Actions code in
Lua 5.1 to see which actions the addon would accept. Replies are scored by the scenario
checks; latency, tokens and the provider-reported cost are recorded.

  GNOMECASTER_API_KEY=... python3 tools/eval_models.py --model anthropic/claude-haiku-5.5

Options:
  --base-url URL   OpenAI-compatible endpoint (default https://openrouter.ai/api/v1)
  --model ID       model to evaluate; repeat for several
  --extra JSON     extra request fields, e.g. '{"reasoning": {"effort": "low"}}'
  --only IDS       comma-separated scenario ids to run
  --max-cost USD   stop starting requests once reported cost passes this (default 1.0)
  --jobs N         parallel requests per model (default 4)
  --out DIR        write the raw results as JSON into DIR
  --no-search      do not offer OpenRouter's web search (on by default there, as in the app)
  --no-key         the endpoint needs no API key (a local model)
Needs LUA=<lua5.1 interpreter>: every reply is checked against the addon's own code.
Without GNOMECASTER_API_KEY (and without --no-key) it stops before the first request.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import pathlib
import statistics
import subprocess
import sys
import tempfile
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "companion"))
import eval_scenarios as sc  # noqa: E402
from gnomecaster import config  # noqa: E402
from gnomecaster.brain import Brain  # noqa: E402
from gnomecaster.conversation import key_of  # noqa: E402
from gnomecaster.game import ADDON_DIR  # noqa: E402
from gnomecaster.model import ModelClient  # noqa: E402
from gnomecaster.slots import lua_value  # noqa: E402


def packet(scenario, text, last=None):
    """A request as the addon sends it; every turn of a scenario is one conversation."""
    p = {"t": "ask", "sid": "eval", "conv": "eval-" + scenario["id"][:11], "text": text, "ctx": scenario["ctx"]}
    if last:
        p["last"] = last
    return p


def run_one(base, model, key, extra, scenario, search=None):
    """One scenario through the companion's own Brain and ModelClient, recording each HTTP attempt.
    Earlier turns with a scripted reply go straight into the memory; the others ask the model."""
    attempts = []
    if "openrouter.ai" in base:
        extra = {**extra, "usage": {"include": True}}     # OpenRouter reports the cost per request
    client = ModelClient(base, model, key, extra, observer=attempts.append, web_search=config.web_search(base, search))
    brain = Brain(client, ADDON_DIR)
    started = time.time()
    for turn in scenario.get("turns", []):
        if "reply" in turn:
            brain.memory.add(key_of(packet(scenario, turn["text"])), turn["text"], turn["reply"])
        else:
            brain.answer(packet(scenario, turn["text"], turn.get("last")))
    reply = brain.answer(packet(scenario, scenario["text"], scenario.get("last")))
    seconds = time.time() - started
    cost = sum(((a.get("usage") or {}).get("cost") or 0) for a in attempts)
    searched = any(a.get("searched") for a in attempts)
    return {"scenario": scenario["id"], "seconds": seconds, "reply": reply, "attempts": attempts, "cost": cost,
            "searched": searched}


def preflight(args, key, scenarios):
    """Everything that can fail without spending money, checked before the first request."""
    if not os.environ.get("LUA"):
        sys.exit("set LUA to a Lua 5.1 interpreter: every reply is checked against the addon's own code")
    ids = [s["id"] for s in sc.SCENARIOS]
    if len(ids) != len(set(ids)):
        sys.exit("eval_scenarios.py has duplicate scenario ids")
    if not scenarios:
        sys.exit("no scenario matches --only")
    if not key and not args.no_key:
        sys.exit(f"GNOMECASTER_API_KEY is not set, so no request was sent ({len(scenarios)} scenarios ready). "
                 "Set it, or pass --no-key for an endpoint that needs none.")


def addon_check(results):
    """Feeds every reply through the addon's Actions code; returns one outcome per result."""
    lua = os.environ["LUA"]             # preflight made sure it is set
    parts = []
    for i, r in enumerate(results, 1):
        try:
            parts.append(f"[{i}]={lua_value(r['reply'])}")
            r["serialize_error"] = None
        except Exception as e:  # noqa: BLE001 - this is the companion crash path; record it
            r["serialize_error"] = f"{type(e).__name__}: {e}"
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="ascii") as f:
        f.write("return {n=%d,%s}\n" % (len(results), ",".join(parts)))
        path = f.name
    try:
        out = subprocess.run([lua, str(ROOT / "tools" / "eval_apply.lua"), str(ROOT), path],
                             capture_output=True, text=True, timeout=120)
    finally:
        os.unlink(path)
    outcomes = [None] * len(results)
    for line in out.stdout.splitlines():
        o = json.loads(line)
        o["skipped"] = o.get("skipped") or []
        outcomes[o["i"] - 1] = o
    if out.returncode:
        print("eval_apply.lua failed:", out.stderr[:400], file=sys.stderr)
    return outcomes


def score(result, outcome, scenario):
    checks = []
    for name, hard, fn in sc.COMMON + scenario["checks"]:
        try:
            ok = bool(fn(result["reply"], outcome))
        except Exception:  # noqa: BLE001 - a check that cannot evaluate counts as failed
            ok = False
        checks.append({"name": name, "hard": hard, "ok": ok})
    if result.get("serialize_error"):
        checks.append({"name": "reply can be written as Lua (" + result["serialize_error"] + ")", "hard": True, "ok": False})
    return checks


def pct(values, q):
    if not values:
        return float("nan")
    values = sorted(values)
    return values[min(len(values) - 1, int(round(q * (len(values) - 1))))]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="https://openrouter.ai/api/v1")
    ap.add_argument("--model", action="append", required=True)
    ap.add_argument("--extra", default="{}")
    ap.add_argument("--only", default="")
    ap.add_argument("--max-cost", type=float, default=1.0)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--out")
    ap.add_argument("--no-search", action="store_true")
    ap.add_argument("--no-key", action="store_true")
    args = ap.parse_args(argv)
    key = os.environ.get("GNOMECASTER_API_KEY", "")
    extra = json.loads(args.extra)
    wanted = {s for s in args.only.split(",") if s}
    scenarios = [s for s in sc.SCENARIOS if not wanted or s["id"] in wanted]
    preflight(args, key, scenarios)
    search = False if args.no_search else None
    by_id = {s["id"]: s for s in scenarios}
    spent, lock, report = 0.0, threading.Lock(), {}

    for model in args.model:
        results = []

        def job(scenario):
            nonlocal spent
            with lock:
                if spent >= args.max_cost:
                    return {"scenario": scenario["id"], "skipped": "budget"}
            r = run_one(args.base_url, model, key, extra, scenario, search)
            with lock:
                spent += r["cost"]
            return r

        with cf.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            for r in pool.map(job, scenarios):
                results.append(r)
        done = [r for r in results if "skipped" not in r]
        for r, outcome in zip(done, addon_check(done)):
            r["addon"] = outcome
            r["checks"] = score(r, outcome, by_id[r["scenario"]])
            r["pass"] = all(c["ok"] for c in r["checks"] if c["hard"])
        report[model] = results

        secs = [r["seconds"] for r in done]
        cost = sum(r["cost"] for r in done)
        fallbacks = sum(1 for r in done if r["reply"].get("error"))
        retries = sum(1 for r in done if len(r["attempts"]) > 1)
        usage = [a.get("usage") or {} for r in done for a in r["attempts"] if a.get("usage")]
        print(f"\n=== {model}  {' '.join(f'{k}={v}' for k, v in extra.items())}")
        print(f"  hard pass: {sum(r['pass'] for r in done)}/{len(done)}   model errors: {fallbacks}"
              f"   retried (JSON mode, search, errors): {retries}   searched the web: "
              f"{sum(r['searched'] for r in done)}   skipped for budget: {len(results) - len(done)}")
        kinds = sorted({r["reply"].get("error") for r in done if r["reply"].get("error")})
        if kinds:
            print(f"  error kinds: {', '.join(kinds)}")
        if secs:
            print(f"  latency s: p50 {pct(secs, .5):.1f}  p90 {pct(secs, .9):.1f}  max {max(secs):.1f}"
                  f"   over 20 s: {sum(s > 20 for s in secs)}   over 55 s: {sum(s > 55 for s in secs)}")
        if usage:
            print(f"  tokens/request: in {statistics.mean(u.get('prompt_tokens', 0) for u in usage):.0f}"
                  f"  out {statistics.mean(u.get('completion_tokens', 0) for u in usage):.0f}"
                  f"   cost: ${cost:.4f} total, ${cost / max(1, len(done)):.5f}/request")
        for r in done:
            failed = [c["name"] for c in r["checks"] if not c["ok"] and c["hard"]]
            soft = [c["name"] for c in r["checks"] if not c["ok"] and not c["hard"]]
            mark = "PASS" if r["pass"] else "FAIL"
            note = ("; failed: " + "; ".join(failed)) if failed else ""
            note += ("; soft misses: " + "; ".join(soft)) if soft else ""
            print(f"  {mark} {r['scenario']:20} {r['seconds']:5.1f}s{note}")
    print(f"\nreported cost this run: ${spent:.4f}")
    if args.out:
        out = pathlib.Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        name = time.strftime("eval-%Y%m%d-%H%M%S.json")
        (out / name).write_text(json.dumps({"extra": extra, "results": report}, indent=1, default=str), encoding="utf-8")
        print(f"raw results: {out / name}")


if __name__ == "__main__":
    main()
