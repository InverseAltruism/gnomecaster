// The one contract between the interface and the app's backend.
// Every call returns a promise; the backend pushes events through `onEvent`.
// In a browser without a backend (development, tests) a mock with the same contract is used,
// selected by ?mock=<scenario> in the URL: fresh, nogame, busy, aiproblem or live.
//
// getHistory({limit}) answers {ok, items} with the saved transcripts, newest first. Each item:
// time, conv, question, ctx (the game context the addon sent), last ([{type, ok, say}]: how the
// previous answer's actions went), raw (the model's text), reply ({say, actions}), error,
// seconds, model, searched (whether the model searched the web). All of it is game or model
// text: the page shows it only through textContent.
"use strict";

window.GC = (function () {
  const listeners = [];
  const emit = (event) => listeners.forEach((fn) => fn(event));

  function bridge() {
    // pywebview exposes its Python API here once ready
    if (window.pywebview && window.pywebview.api) {
      const api = window.pywebview.api;
      return (name, args) => api[name](args || {});
    }
    return null;
  }

  // ------------------------------------------------------------------ mock backend

  // What the addon sends with a question (Context.lua), for the mock transcripts.
  const ZULAMAN = {
    game: { version: "12.0.5", build: "64210", toc: 120005, project: 1, locale: "enUS" },
    player: { class: "DRUID", race: "NightElf", level: 88, faction: "Alliance", spec: "Restoration", combat: false },
    location: { zone: "Zul'Aman", subzone: "Amani Pass", mapID: 2437, map: "Zul'Aman", x: 0.4512, y: 0.6203 },
    focus: { quest: 86721, title: "The Sunwell's Echo", obj: ["Speak to Magister Ilyndra"], next: { map: 2393, x: 0.381, y: 0.552 } },
    quests: [
      { id: 86721, title: "The Sunwell's Echo", level: 88, obj: ["Speak to Magister Ilyndra"] },
      { id: 86655, title: "Troll Trouble", level: 87, done: true },
      { id: 86702, title: "Hexed Hides", level: 88, obj: ["Amani hides: 4/8"] },
      { id: 86690, title: "A Bridge Too Old", level: 88, obj: ["Repair the rope bridge"] },
      { id: 86711, title: "Whispers in the Canopy", level: 88, obj: ["Listen at the shrine: 1/3"] },
    ],
  };
  const withTarget = (ctx, target) => Object.assign(JSON.parse(JSON.stringify(ctx)), { target });
  const deDE = (ctx) => { const c = JSON.parse(JSON.stringify(ctx)); c.game.locale = "deDE"; c.player.spec = "Wiederherstellung"; return c; };

  const LIVE_TRANSCRIPT = {
    time: "2026-10-17T18:50:12", conv: "c41", request: "m1:9", question: "mark my target with skull",
    ctx: withTarget(ZULAMAN, { name: "Amani Hexxer", level: 88, hostile: true, dead: false, player: false }),
    last: [], raw: '{"say": "Marked your target with a skull.", "actions": [{"type": "mark", "icon": 8, "unit": "target"}]}',
    reply: { say: "Marked your target with a skull.", actions: [{ type: "mark", icon: 8, unit: "target" }] },
    error: null, seconds: 1.9, model: "openai/gpt-6-luna", searched: false,
  };

  function mockHistory(scenario) {
    if (scenario !== "busy" && scenario !== "aiproblem") return [];
    const items = [
      {
        time: "2026-10-17T18:44:09", conv: "c40", request: "m1:4", question: "markiere atal aman delve auf der map",
        ctx: deDE(ZULAMAN), last: [{ type: "waypoint", ok: true, say: "Wegpunkt gesetzt" }],
        raw: '{"say": "Ich habe den Eingang der Tiefe Atal\'Aman auf deiner Karte markiert: im Südosten von Zul\'Aman, hinter der Brücke.", "actions": [{"type": "waypoint", "map": 2437, "x": 0.634, "y": 0.718, "title": "Atal\'Aman (Tiefe)"}]}',
        reply: { say: "Ich habe den Eingang der Tiefe Atal'Aman auf deiner Karte markiert: im Südosten von Zul'Aman, hinter der Brücke.",
          actions: [{ type: "waypoint", map: 2437, x: 0.634, y: 0.718, title: "Atal'Aman (Tiefe)" }] },
        error: null, seconds: 4.8, model: "openai/gpt-6-luna", searched: true,
      },
      {
        time: "2026-10-17T18:41:30", conv: "c39", request: "m1:3", question: "what was that error?",
        ctx: Object.assign(JSON.parse(JSON.stringify(ZULAMAN)), { errors: { lua: [
          { msg: "Interface/AddOns/Foo/Foo.lua:12: attempt to index field 'db' (a nil value)", t: 1792255270, n: 3 },
        ], ui: [{ msg: "You can't do that yet", t: 1792255262 }] } }),
        last: [],
        raw: '{"say": "The error came from the addon Foo, in Foo.lua at line 12: it tried to read a value that was empty at that moment. Update Foo, or disable it to see whether the error stops.", "actions": []}',
        reply: { say: "The error came from the addon Foo, in Foo.lua at line 12: it tried to read a value that was empty at that moment. Update Foo, or disable it to see whether the error stops.", actions: [] },
        error: null, seconds: 3.1, model: "openai/gpt-6-luna", searched: false,
      },
      {
        time: "2026-10-17T18:39:02", conv: "c38", request: "m1:2", question: "take me to my quest", ctx: ZULAMAN, last: [],
        raw: '{"say": "Marked the next step of The Sunwell\'s Echo: speak to Magister Ilyndra.", "actions": [{"type": "waypoint", "map": 2393, "x": 0.381, "y": 0.552, "title": "The Sunwell\'s Echo"}]}',
        reply: { say: "Marked the next step of The Sunwell's Echo: speak to Magister Ilyndra.",
          actions: [{ type: "waypoint", map: 2393, x: 0.381, y: 0.552, title: "The Sunwell's Echo" }] },
        error: null, seconds: 2.6, model: "openai/gpt-6-luna", searched: false,
      },
      {
        time: "2026-10-17T18:37:44", conv: "c37", request: "m1:1", question: "mouseover rejuvenation macro on slot 5, bound to shift-e", ctx: ZULAMAN, last: [],
        raw: '{"say": "Here\'s a mouseover Rejuvenation macro on slot 5, bound to Shift-E.", "actions": [{"type": "macro", "name": "Rejuv", "body": "#showtooltip\\n/cast [@mouseover,help,nodead][] Rejuvenation"}, {"type": "bar", "slot": 5, "macro": "Rejuv"}, {"type": "bind", "key": "SHIFT-E", "macro": "Rejuv"}]}',
        reply: { say: "Here's a mouseover Rejuvenation macro on slot 5, bound to Shift-E.", actions: [
          { type: "macro", name: "Rejuv", body: "#showtooltip\n/cast [@mouseover,help,nodead][] Rejuvenation" },
          { type: "bar", slot: 5, macro: "Rejuv" }, { type: "bind", key: "SHIFT-E", macro: "Rejuv" }] },
        error: null, seconds: 2.9, model: "openai/gpt-6-luna", searched: false,
      },
    ];
    if (scenario === "aiproblem") {
      items.unshift({
        time: "2026-10-17T18:46:51", conv: "c41", request: "m1:5", question: "where do i train flying?", ctx: ZULAMAN, last: [], raw: "",
        reply: { say: "Your account at openrouter.ai is out of credit. Add credit there, then try again.", actions: [] },
        error: "OpenRouter answered 402: insufficient credits", seconds: 0.4, model: "openai/gpt-6-luna", searched: false,
      });
    }
    return items;
  }

  function mock(scenario) {
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    let cancelled = false;
    const state = {
      version: "1.1.0",
      setupDone: scenario !== "fresh" && scenario !== "nogame",
      games: scenario === "nogame" ? [] : [
        { id: "retail", name: "Retail", path: "C:\\Program Files (x86)\\World of Warcraft\\_retail_", addon: scenario === "fresh" ? "missing" : "current" },
        { id: "classic_era", name: "Classic Era", path: "C:\\Program Files (x86)\\World of Warcraft\\_classic_era_", addon: "missing" },
      ],
      game: "retail",
      ai: scenario === "fresh" || scenario === "nogame" ? null : {
        provider: "openrouter", model: "openai/gpt-6-luna", account: "Signed in with OpenRouter",
        ok: scenario !== "aiproblem", note: scenario === "aiproblem" ? "Your OpenRouter account is out of credit. Add credit, then test again." : "Test question answered in 1.4 s",
        credit: scenario === "aiproblem" ? null : "$2.69 of $3.00 left", needsCredit: scenario === "aiproblem",
      },
      companion: { running: true, since: "18:02" },
      settings: { autostart: true, tray: true },
      providers: [
        { id: "openrouter", name: "OpenRouter", key: true, keyPage: true },
        { id: "openai", name: "OpenAI", key: true, keyPage: true },
        { id: "ollama", name: "Ollama (a model on this PC)", key: false, keyPage: false },
      ],
      models: [
        { id: "openai/gpt-6-luna", name: "GPT-6 Luna", detail: "Quick answers, very low cost.", recommended: true },
        { id: "anthropic/claude-haiku-5.5", name: "Claude Haiku 5.5", detail: "Quickest answers, low cost." },
        { id: "google/gemini-3.8-flash", name: "Gemini 3.8 Flash", detail: "Quick answers, several times the cost." },
        { id: "deepseek/deepseek-v4.1-flash", name: "DeepSeek V4.1 Flash", detail: "Lowest cost; some answers are slow." },
      ],
      activity: scenario === "busy" || scenario === "aiproblem" ? [
        { id: 4, time: "18:44", request: "m1:4", question: "markiere atal aman delve auf der map", answer: "Ich habe den Eingang der Tiefe Atal'Aman auf deiner Karte markiert: im Südosten von Zul'Aman, hinter der Brücke.", actions: ["Waypoint: Atal'Aman (Tiefe) (63.4, 71.8)"], seconds: 4.8, model: "openai/gpt-6-luna" },
        { id: 3, time: "18:41", request: "m1:3", question: "what was that error?", answer: "The error came from the addon Foo, in Foo.lua at line 12: it tried to read a value that was empty at that moment. Update Foo, or disable it to see whether the error stops.", actions: [], seconds: 3.1, model: "openai/gpt-6-luna" },
        { id: 2, time: "18:39", request: "m1:2", question: "take me to my quest", answer: "Marked the next step of The Sunwell's Echo: speak to Magister Ilyndra.", actions: ["Waypoint: The Sunwell's Echo (38.1, 55.2)"], seconds: 2.6, model: "openai/gpt-6-luna" },
        { id: 1, time: "18:37", request: "m1:1", question: "mouseover rejuvenation macro on slot 5, bound to shift-e", answer: "Here's a mouseover Rejuvenation macro on slot 5, bound to Shift-E. Shift-E currently steers your character, so the game asks before replacing it.", actions: ["Macro “Rejuv”", "“Rejuv” on action slot 5", "Shift-E bound to “Rejuv”"], seconds: 2.9, model: "openai/gpt-6-luna" },
      ] : [],
    };
    if (scenario === "aiproblem") {
      state.activity.unshift({ id: 5, time: "18:46", request: "m1:5", question: "where do i train flying?", answer: "Your account at openrouter.ai is out of credit. Add credit there, then try again.", actions: [], error: true, seconds: 0.4 });
    }
    // The transcripts the companion saved for those questions, newest first (getHistory).
    const history = mockHistory(scenario);
    const calls = {
      async getState() { await wait(60); return JSON.parse(JSON.stringify(state)); },
      async chooseGameFolder() { await wait(300); return { ok: false, message: "No folder chosen." }; },
      async selectGame({ id }) { state.game = id; return { ok: true }; },
      async installAddon() {
        await wait(900);
        state.games.forEach((g) => { if (g.id === state.game) g.addon = "current"; });
        return { ok: true, message: "Installed. If World of Warcraft is running, restart it so the addon loads." };
      },
      async signIn() {
        cancelled = false;
        for (let i = 0; i < 16 && !cancelled; i++) await wait(100);
        if (cancelled) return { ok: false, message: "Sign-in was cancelled." };
        state.ai = { provider: "openrouter", model: "openai/gpt-6-luna", account: "Signed in with OpenRouter", ok: true, note: "Test question answered in 1.3 s", credit: "$3.00 left" };
        return { ok: true, message: "Connected. Test question answered in 1.3 s." };
      },
      async cancelSignIn() { cancelled = true; return { ok: true }; },
      async saveKey({ provider, key }) {
        await wait(900);
        if (!key) return { ok: false, message: "Paste a key first." };
        state.ai = { provider, model: "openai/gpt-6-luna", account: "Using your own key", ok: true, note: "Test question answered in 1.6 s" };
        return { ok: true, message: "Connected. Test question answered in 1.6 s." };
      },
      async setModel({ id }) { if (state.ai) state.ai.model = id; return { ok: true }; },
      async checkConnection() { await wait(900); return state.ai && state.ai.ok ? { ok: true, message: "Test question answered in 1.2 s" } : { ok: false, message: state.ai ? state.ai.note : "No AI connected." }; },
      async finishSetup() { state.setupDone = true; return { ok: true }; },
      async setCompanion({ running }) { state.companion.running = running; return { ok: true }; },
      async setSetting({ name, value }) { state.settings[name] = value; return { ok: true }; },
      async openLogs() { return { ok: true }; },
      async openCredits() { return { ok: true }; },
      async openKeyPage() { return { ok: true }; },
      async openTranscripts() { return { ok: true }; },
      async getHistory({ limit }) {
        await wait(150);
        return { ok: true, items: JSON.parse(JSON.stringify(history.slice(0, Math.max(0, limit | 0) || history.length))) };
      },
    };
    // A question arriving from the game a few seconds after the dashboard opens.
    if (scenario === "live") {
      setTimeout(() => emit({ type: "question", entry: { id: 9, time: "18:50", request: "m1:9", question: "mark my target with skull", pending: true } }), 1800);
      setTimeout(() => {
        history.unshift(LIVE_TRANSCRIPT);
        emit({ type: "answer", entry: { id: 9, time: "18:50", request: "m1:9", question: "mark my target with skull", answer: "Marked your target with a skull.", actions: ["Skull on your target"], seconds: 1.9, model: "openai/gpt-6-luna" } });
      }, 3800);
    }
    return (name, args) => calls[name](args || {});
  }

  let call = bridge();
  const params = new URLSearchParams(location.search);
  if (!call && params.has("mock")) call = mock(params.get("mock") || "busy");

  return {
    ready() {
      if (call) return Promise.resolve();
      // pywebview injects its API after the page loads
      return new Promise((resolve) => window.addEventListener("pywebviewready", () => { call = bridge(); resolve(); }, { once: true }));
    },
    call: (name, args) => call(name, args),
    onEvent: (fn) => listeners.push(fn),
    emit,                                   // the backend calls GC.emit(event) to push events
  };
})();
