// The one contract between the interface and the app's backend.
// Every call returns a promise; the backend pushes events through `onEvent`.
// In a browser without a backend (development, tests) a mock with the same contract is used,
// selected by ?mock=<scenario> in the URL.
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
  function mock(scenario) {
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    let cancelled = false;
    const state = {
      version: "1.0.0",
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
        { id: 3, time: "18:41", question: "what was that error?", answer: "The error came from the addon Foo, in Foo.lua at line 12: it tried to read a value that was empty at that moment. Update Foo, or disable it to see whether the error stops.", actions: [], seconds: 3.1, model: "openai/gpt-6-luna" },
        { id: 2, time: "18:39", question: "take me to my quest", answer: "Marked the next step of The Sunwell's Echo: speak to Magister Ilyndra.", actions: ["Waypoint: The Sunwell's Echo (38.1, 55.2)"], seconds: 2.6, model: "openai/gpt-6-luna" },
        { id: 1, time: "18:37", question: "mouseover rejuvenation macro on slot 5, bound to shift-e", answer: "Here's a mouseover Rejuvenation macro on slot 5, bound to Shift-E. Shift-E currently steers your character, so the game asks before replacing it.", actions: ["Macro \u201cRejuv\u201d", "\u201cRejuv\u201d on action slot 5", "Shift-E bound to \u201cRejuv\u201d"], seconds: 2.9, model: "openai/gpt-6-luna" },
      ] : scenario === "aiproblem" ? [] : [],
    };
    if (scenario === "aiproblem") {
      state.activity.unshift({ id: 4, time: "18:44", question: "where do i train flying?", answer: "Your account at openrouter.ai is out of credit. Add credit there, then try again.", actions: [], error: true, seconds: 0.4 });
    }
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
    };
    // A question arriving from the game a few seconds after the dashboard opens.
    if (scenario === "live") {
      setTimeout(() => emit({ type: "question", entry: { id: 9, time: "18:50", question: "mark my target with skull", pending: true } }), 1800);
      setTimeout(() => emit({ type: "answer", entry: { id: 9, time: "18:50", question: "mark my target with skull", answer: "Marked your target with a skull.", actions: ["Skull on your target"], seconds: 1.9, model: "openai/gpt-6-luna" } }), 3800);
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
