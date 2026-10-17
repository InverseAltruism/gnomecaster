// Gnomecaster desktop interface: the setup wizard, the dashboard and settings.
"use strict";

(function () {
  const $ = (id) => document.getElementById(id);
  const app = $("app");
  let state = null;
  let step = "game";
  let focusAfterMove = false;
  let signInAttempt = 0;           // a sign-in's result counts only while it is the latest attempt

  // ---------------------------------------------------------------- helpers

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "text") node.textContent = v;
      else if (k === "class") node.className = v;
      else if (v !== undefined && v !== null && v !== false) node.setAttribute(k, v === true ? "" : v);
    }
    for (const child of children || []) if (child) node.append(child);
    return node;
  }

  function setStatus(node, text, kind) {
    node.textContent = text || "";
    node.className = "status-line" + (kind ? " " + kind : "");
    node.hidden = !text;
  }

  // One API-key form (setup and settings have one each), opened by `opener`. The providers
  // come from the app; a provider without keys (Ollama) shows no key field. `onToggle` runs
  // after the form opens or closes.
  function wireKeyForm(prefix, opener, status, onConnected, onToggle = () => {}) {
    const form = $(prefix + "key-form"), provider = $(prefix + "key-provider"), value = $(prefix + "key-value");
    const keyField = form.querySelector("[data-key-field]"), keyPage = form.querySelector("[data-key-page]");
    const chosen = () => state.providers.find((p) => p.id === provider.value) || {};
    const sync = () => { keyField.hidden = !chosen().key; keyPage.hidden = !chosen().keyPage; };
    const close = () => { form.hidden = true; opener.hidden = false; value.value = ""; onToggle(); };
    provider.addEventListener("change", sync);
    keyPage.addEventListener("click", () => GC.call("openKeyPage", { provider: provider.value }));
    const cancel = form.querySelector("[data-cancel]");
    cancel.addEventListener("click", () => { close(); setStatus(status, "", ""); opener.focus(); });
    opener.addEventListener("click", () => {
      provider.replaceChildren(...state.providers.map((p) => el("option", { value: p.id, text: p.name })));
      sync();
      form.hidden = false;
      opener.hidden = true;
      onToggle();
      (keyField.hidden ? provider : value).focus();
    });
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      // while the key is being tested the form stays as it is: no cancelling, no edits
      const fields = [cancel, provider, value];
      fields.forEach((f) => { f.disabled = true; });
      busy(form.querySelector("button[type=submit]"), async () => {
        try {
          const r = await GC.call("saveKey", { provider: provider.value, key: value.value.trim() });
          if (!r.ok) { setStatus(status, r.message, "error"); return; }
          close();
          setStatus(status, "", "");
          await refresh();
          onConnected(r);
        } finally {
          fields.forEach((f) => { f.disabled = false; });
        }
      });
    });
  }

  async function busy(button, work) {
    button.classList.add("busy");
    button.disabled = true;
    try { return await work(); } finally { button.classList.remove("busy"); button.disabled = false; }
  }

  // A call that failed inside the app answers {ok: false, message} instead of the state.
  async function refresh() {
    const s = await GC.call("getState");
    if (!s || s.ok === false || !Array.isArray(s.games)) throw new Error((s && s.message) || "The app did not answer.");
    state = s;
    return state;
  }

  // ---------------------------------------------------------------- setup

  const STEPS = ["game", "addon", "ai"];

  function showStep(name) {
    step = name;
    document.querySelectorAll(".pane").forEach((p) => p.classList.toggle("active", p.dataset.pane === name));
    const index = STEPS.indexOf(name);
    document.querySelectorAll("#steps li").forEach((li, i) => {
      li.classList.toggle("current", i === index);
      li.classList.toggle("done", index === -1 || i < index);
    });
    // move the spark beside the current step (or past the last one when done)
    const items = document.querySelectorAll("#steps li");
    const target = items[Math.min(index === -1 ? items.length - 1 : index, items.length - 1)];
    const trail = document.querySelector(".spark-trail");
    if (target && trail) {
      const circle = target.querySelector(".step-num").getBoundingClientRect();
      const y = circle.top + circle.height / 2 - trail.getBoundingClientRect().top;
      trail.style.setProperty("--spark-y", y + "px");
    }
    // focus follows the wizard for keyboard users, but not on the very first screen
    if (focusAfterMove) {
      const focusable = document.querySelector(`.pane[data-pane="${name}"] .btn.primary:not(:disabled)`);
      if (focusable) setTimeout(() => focusable.focus({ preventScroll: true }), 60);
    }
    focusAfterMove = true;
    document.querySelectorAll(".steps-mini .bar").forEach((bar, i) => bar.classList.toggle("on", index === -1 || i <= index));
    $("steps-mini-text").textContent = index === -1 ? "All set" : `Step ${index + 1} of ${STEPS.length}`;
  }

  function renderGames() {
    const list = $("game-list");
    list.replaceChildren();
    state.games.forEach((g) => {
      const input = el("input", { type: "radio", name: "game", value: g.id, checked: g.id === state.game });
      input.addEventListener("change", async () => { await GC.call("selectGame", { id: g.id }); state.game = g.id; renderAddonPane(); });
      list.append(el("label", { class: "choice" }, [input, el("span", { class: "title", text: g.name }), el("span", { class: "detail", text: g.path })]));
    });
    $("game-missing").hidden = state.games.length > 0;
    $("game-next").disabled = !state.games.length;
    // with nothing found, choosing the folder is the step's one action
    $("choose-folder").classList.toggle("primary", !state.games.length);
    $("choose-folder").classList.toggle("ghost", state.games.length > 0);
  }

  function selectedGame() {
    return state.games.find((g) => g.id === state.game) || state.games[0];
  }

  function renderAddonPane() {
    const g = selectedGame();
    if (!g) return;
    // a long path may wrap only after a backslash, never inside a folder name
    const parts = (g.path + "\\Interface\\AddOns").split("\\");
    $("addon-path").replaceChildren(...parts.flatMap((part, i) => (i ? ["\\", el("wbr"), part] : [part])));
    $("addon-target").classList.toggle("done", g.addon === "current");
    const status = $("addon-status");
    if (g.addon === "current") setStatus(status, "Installed and up to date.", "ok");
    else if (g.addon === "outdated") setStatus(status, "An older version is installed. Update it to get the latest fixes.", "warn");
    else setStatus(status, "", "");
    $("install-addon").textContent = g.addon === "current" ? "Continue" : g.addon === "outdated" ? "Update addon" : "Install addon";
  }

  function renderModels(list, selectEl) {
    const models = state.models;
    if (list) {
      list.querySelectorAll(".choice").forEach((c) => c.remove());
      models.forEach((m) => {
        const input = el("input", { type: "radio", name: "model", value: m.id, checked: state.ai && state.ai.model === m.id });
        input.addEventListener("change", () => GC.call("setModel", { id: m.id }).then(() => { state.ai.model = m.id; }));
        const title = el("span", { class: "title", text: m.name }, [m.recommended ? el("span", { class: "badge", text: "Recommended" }) : null]);
        list.append(el("label", { class: "choice" }, [input, title, el("span", { class: "detail", text: m.detail })]));
      });
    }
    if (selectEl) {
      selectEl.replaceChildren(...models.map((m) => el("option", { value: m.id, text: m.name + (m.recommended ? " (recommended)" : ""), selected: state.ai && state.ai.model === m.id })));
    }
  }

  const AI_LEAD = "OpenRouter gives one account access to many AI models. You pay OpenRouter directly; a typical question costs under a tenth of a cent.";

  function renderAiPane() {
    const connected = !!(state.ai && state.ai.ok);
    $("ai-lead").textContent = connected ? "Choose the model that answers your questions. You can change it later in Settings." : AI_LEAD;
    const failed = !!(state.ai && state.ai.ok === false);     // a saved key whose test question failed
    $("ai-connect").hidden = connected;
    $("ai-models").hidden = !connected;
    $("ai-next").disabled = !connected;
    // The key form stands in for signing in, so while it is open its Connect is the only
    // action; while a sign-in waits, only its Cancel is
    const keying = !$("key-form").hidden, waiting = !$("sign-in-wait").hidden;
    $("sign-in").hidden = keying || waiting;
    $("ai-failed").hidden = !failed || keying || waiting;
    if (state.ai && state.ai.ok === null) setStatus($("ai-error"), "Checking the saved connection…", "");
    $("ai-credit").hidden = !(failed && state.ai.needsCredit);
    // with a saved key that failed its test, fixing that comes first; signing in again is the fallback
    $("sign-in").textContent = failed ? "Sign in again" : "Sign in with OpenRouter";
    $("sign-in").classList.toggle("primary", !failed);
    $("sign-in").classList.toggle("ghost", failed);
    if (failed) setStatus($("ai-error"), state.ai.note, "error");
    if (connected) {
      setStatus($("ai-error"), "", "");
      $("ai-connected").textContent = state.ai.account + ". " + state.ai.note + ".";
      renderModels($("model-list"));
    }
  }

  function wireSetup() {
    $("game-next").addEventListener("click", () => { renderAddonPane(); showStep("addon"); });
    $("choose-folder").addEventListener("click", () => busy($("choose-folder"), async () => {
      const r = await GC.call("chooseGameFolder");
      if (r.ok) { await refresh(); renderGames(); }
    }));
    document.querySelectorAll("[data-back]").forEach((b) => b.addEventListener("click", () => showStep(b.dataset.back)));
    $("install-addon").addEventListener("click", () => {
      const g = selectedGame();
      if (g.addon === "current") { renderAiPane(); showStep("ai"); return; }
      busy($("install-addon"), async () => {
        const r = await GC.call("installAddon", { id: g.id });
        await refresh();
        renderAddonPane();
        setStatus($("addon-status"), r.message, r.ok ? "ok" : "error");
      });
    });
    // Puts the AI step back as the app's state says, after a sign-in ends or is cancelled.
    const endSignIn = () => {
      $("sign-in-wait").hidden = true;
      $("use-key").hidden = !$("key-form").hidden;
      renderAiPane();
    };
    $("sign-in").addEventListener("click", async () => {
      const mine = ++signInAttempt;
      setStatus($("ai-error"), "", "");
      [$("sign-in"), $("use-key"), $("key-form"), $("ai-failed")].forEach((n) => { n.hidden = true; });
      $("sign-in-wait").hidden = false;
      const r = await GC.call("signIn");
      if (mine !== signInAttempt) return;     // cancelled, or a newer attempt took over
      await refresh();
      endSignIn();
      if (!r.ok) setStatus($("ai-error"), r.message, "error");
    });
    // Cancel answers at once; the backend's sign-in winds down behind it
    $("sign-in-cancel").addEventListener("click", () => {
      signInAttempt++;
      endSignIn();
      $("sign-in").focus();
      GC.call("cancelSignIn");
    });
    $("ai-credit").addEventListener("click", () => GC.call("openCredits"));
    $("ai-retest").addEventListener("click", () => busy($("ai-retest"), async () => {
      const r = await GC.call("checkConnection");
      await refresh();
      renderAiPane();
      if (!r.ok) setStatus($("ai-error"), r.message, "error");
    }));
    wireKeyForm("", $("use-key"), $("ai-error"), () => renderAiPane(), () => renderAiPane());
    $("ai-next").addEventListener("click", () => busy($("ai-next"), async () => {
      const r = await GC.call("finishSetup");
      if (!r.ok) { setStatus($("ai-error"), r.message, "error"); return; }
      showStep("done");
    }));
    $("open-main").addEventListener("click", async () => { await refresh(); showMain(); });
  }

  // ---------------------------------------------------------------- dashboard

  function renderRail() {
    const g = selectedGame();
    $("game-value").textContent = g ? g.name : "Not found";
    const note = $("game-note");
    $("update-addon").hidden = !g || g.addon === "current";
    if (!g) { note.textContent = "Choose the game folder in settings."; note.className = "rail-note warn"; }
    else if (g.addon === "current") { note.textContent = "Addon installed"; note.className = "rail-note"; }
    else { note.textContent = g.addon === "outdated" ? "A newer addon is ready to install" : "Addon not installed"; note.className = "rail-note warn"; }

    const ai = state.ai;
    const aiProblem = !ai || ai.ok === false;   // ok is null while the connection is being checked
    $("ai-value").textContent = ai ? (state.models.find((m) => m.id === ai.model) || { name: ai.model }).name : "Not connected";
    // a problem's details and fixes are in the alert above the questions; the rail only says so
    $("ai-note").textContent = !ai ? "Not connected." : ai.ok === false ? "Not answering right now." : [ai.note, ai.credit].filter(Boolean).join(". ");
    $("ai-note").className = "rail-note" + (aiProblem ? " error" : "");
    renderAlert(ai, aiProblem);

    const c = state.companion;
    $("companion-value").textContent = c.running ? "On" : "Paused";
    $("companion-note").textContent = c.running ? "Since " + c.since + ". Keep it running while you play." : "Questions asked in the game while paused get no answer.";
    $("toggle-companion").textContent = c.running ? "Pause" : "Resume";
    $("toggle-companion").classList.toggle("primary", !c.running);

    const live = $("live");
    const problem = aiProblem || !g || g.addon !== "current";
    live.dataset.state = !c.running ? "paused" : problem ? "problem" : "listening";
    $("live-text").textContent = !c.running ? "Paused" : problem ? "Needs attention" : "Listening for questions";
  }

  // The AI problem, at the top of the feed where the questions fail, with what fixes it.
  function renderAlert(ai, problem) {
    $("feed-alert").hidden = !problem;
    if (!problem) return;
    $("feed-alert-text").textContent = ai ? ai.note : "No AI is connected, so questions from the game get no answer.";
    $("alert-credit").hidden = !(ai && ai.needsCredit);
    $("alert-check").hidden = !ai;
  }

  function entryNode(e) {
    const q = el("div", { class: "entry-q" }, [el("span", { class: "who", text: "You" }), el("span", { class: "text", text: e.question }), el("time", { text: e.time })]);
    const node = el("li", { class: "entry" + (e.error ? " error" : ""), "data-id": e.id }, [q]);
    if (e.pending) {
      const dots = el("span", { class: "dots", "aria-hidden": "true" }, [el("i"), el("i"), el("i")]);
      node.append(el("p", { class: "entry-a thinking" }, [dots, document.createTextNode("Thinking")]));
    }
    else {
      node.append(el("p", { class: "entry-a", text: e.answer }));
      // what the answer asked the game to do; whether it happened, and when, the game decides
      if (e.actions && e.actions.length) node.append(el("ul", { class: "entry-actions" }, e.actions.map((a) => el("li", { text: a }))));
      const model = e.model && (state.models.find((m) => m.id === e.model) || { name: e.model }).name;
      const took = e.seconds ? e.seconds.toFixed(1) + " s" : "";
      if (took) node.append(el("p", { class: "entry-meta", text: e.error ? `Failed after ${took}` : `Answered in ${took}` + (model ? ` by ${model}` : "") }));
    }
    return node;
  }

  function renderFeed() {
    const list = $("feed-list");
    list.replaceChildren(...state.activity.map(entryNode));
    $("feed-empty").hidden = state.activity.length > 0;
    $("feed-title").hidden = state.activity.length === 0;
  }

  function flare() {
    const live = $("live");
    live.classList.remove("flare");
    void live.offsetWidth;          // restart the animation
    live.classList.add("flare");
  }

  function onEvent(event) {
    if (!state) return;
    if (event.type === "question" || event.type === "answer") {
      const i = state.activity.findIndex((e) => e.id === event.entry.id);
      if (i >= 0) state.activity[i] = event.entry; else state.activity.unshift(event.entry);
      renderFeed();
      const node = document.querySelector(`.entry[data-id="${event.entry.id}"]`);
      if (node) node.classList.add(event.type === "question" ? "new" : "answered");
      if (event.type === "question") flare();
    } else if (event.type === "state") {
      refresh().then(() => {
        renderRail();
        renderSettings();
        if (app.dataset.screen === "setup" && step === "ai") renderAiPane();   // a check finished in the background
      }).catch(() => {});   // keep what is shown; the next state event or click refreshes again
    }
  }

  function showMain() {
    app.dataset.screen = "main";
    renderRail();
    renderFeed();
    renderSettings();
  }

  // ---------------------------------------------------------------- settings

  function renderSettings() {
    renderModels(null, $("settings-model"));
    $("settings-account").textContent = state.ai ? state.ai.account + "." + (state.ai.credit ? " " + state.ai.credit + "." : "") : "No AI connected.";
    $("settings-reconnect").textContent = state.ai && state.ai.account.startsWith("Signed in") ? "Switch account" : "Sign in with OpenRouter";
    const g = selectedGame();
    $("settings-game").textContent = g ? g.name + ": " + g.path : "No game folder chosen.";
    $("settings-autostart").checked = !!state.settings.autostart;
    $("settings-tray").checked = !!state.settings.tray;
    $("settings-version").textContent = "Gnomecaster " + state.version;
  }

  // Examples go into the game's chat, so a click copies one (WoW's chat box takes Ctrl+V).
  async function copyExample(text) {
    let ok = false;
    try { await navigator.clipboard.writeText(text); ok = true; } catch (e) {
      const area = el("textarea", { class: "offscreen" });
      area.value = text;
      document.body.append(area);
      area.select();
      ok = document.execCommand("copy");
      area.remove();
    }
    const note = $("copied");
    note.textContent = ok ? `Copied. Paste it into the game's chat with Ctrl+V.` : "Couldn't copy; type it in the game's chat.";
    note.classList.add("show");
    clearTimeout(copyExample.timer);
    copyExample.timer = setTimeout(() => note.classList.remove("show"), 3200);
  }

  function openDrawer(open) {
    const drawer = $("drawer"), scrim = $("scrim");
    if (open) {
      drawer.hidden = false; scrim.hidden = false;
      requestAnimationFrame(() => { drawer.classList.add("open"); scrim.classList.add("open"); });
      setTimeout(() => $("close-settings").focus(), 50);
    } else {
      drawer.classList.remove("open"); scrim.classList.remove("open");
      setTimeout(() => { drawer.hidden = true; scrim.hidden = true; $("open-settings").focus(); }, 300);
    }
  }

  function wireMain() {
    $("open-settings").addEventListener("click", () => openDrawer(true));
    $("close-settings").addEventListener("click", () => openDrawer(false));
    $("scrim").addEventListener("click", () => openDrawer(false));
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("drawer").hidden) openDrawer(false); });
    $("toggle-companion").addEventListener("click", async () => {
      await GC.call("setCompanion", { running: !state.companion.running });
      await refresh(); renderRail();
    });
    $("update-addon").addEventListener("click", () => busy($("update-addon"), async () => {
      await GC.call("installAddon", { id: state.game }); await refresh(); renderRail();
    }));
    $("alert-credit").addEventListener("click", () => GC.call("openCredits"));
    $("alert-settings").addEventListener("click", () => openDrawer(true));
    $("alert-check").addEventListener("click", () => busy($("alert-check"), async () => {
      const r = await GC.call("checkConnection");
      await refresh(); renderRail();
      if (!r.ok) $("feed-alert-text").textContent = r.message;
    }));
    document.querySelectorAll(".example").forEach((b) => b.addEventListener("click", () => copyExample(b.textContent)));
    $("settings-model").addEventListener("change", (e) => GC.call("setModel", { id: e.target.value }).then(refresh).then(renderRail));
    $("settings-check").addEventListener("click", () => busy($("settings-check"), async () => {
      const r = await GC.call("checkConnection");
      setStatus($("settings-ai-status"), r.message, r.ok ? "ok" : "error");
      await refresh(); renderRail();
    }));
    $("settings-reconnect").addEventListener("click", () => busy($("settings-reconnect"), async () => {
      const r = await GC.call("signIn");
      setStatus($("settings-ai-status"), r.message, r.ok ? "ok" : "error");
      await refresh(); renderRail(); renderSettings();
    }));
    wireKeyForm("settings-", $("settings-use-key"), $("settings-ai-status"), (r) => {
      setStatus($("settings-ai-status"), r.message, "ok");
      renderRail(); renderSettings();
    });
    $("settings-reinstall").addEventListener("click", () => busy($("settings-reinstall"), async () => {
      const r = await GC.call("installAddon", { id: state.game });
      await refresh(); renderRail(); renderSettings();
      setStatus($("settings-ai-status"), r.message, r.ok ? "ok" : "error");
    }));
    $("settings-folder").addEventListener("click", () => busy($("settings-folder"), async () => {
      const r = await GC.call("chooseGameFolder");
      if (r.ok) { await refresh(); renderRail(); renderSettings(); }
    }));
    $("settings-autostart").addEventListener("change", (e) => GC.call("setSetting", { name: "autostart", value: e.target.checked }));
    $("settings-tray").addEventListener("change", (e) => GC.call("setSetting", { name: "tray", value: e.target.checked }));
    $("settings-logs").addEventListener("click", () => GC.call("openLogs"));
  }

  // ---------------------------------------------------------------- start

  function showFatal(message) {
    $("fatal-text").textContent = message;
    app.dataset.screen = "error";
  }

  async function start() {
    await GC.ready();
    try {
      await refresh();
    } catch (e) {
      showFatal(e.message);
      return;
    }
    wireSetup();
    wireMain();
    GC.onEvent(onEvent);
    if (state.setupDone) showMain();
    else {
      renderGames();
      showStep("game");
      app.dataset.screen = "setup";
    }
    document.body.dataset.ready = "true";       // the build's smoke test waits for this
  }

  start();
})();
