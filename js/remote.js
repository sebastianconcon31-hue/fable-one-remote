// Fable One Remote: the phone's line to Fable One on the PC.
//
// Every message goes through the encrypted relay the Chromebook page uses
// (relay.js here, voice-launcher/web_relay.py on the PC), so the PC runs it
// exactly like a spoken command - Fable One's own router, rules and gates,
// with destructive commands refused remotely. The page holds no secret of its
// own: the pairing code comes from a pairing link or is typed in once, and is
// kept only on the phone.
//
// Made for the hand: hold the orb to talk (it buzzes when it starts
// listening), the latest answer sits on a card that tilts with the phone, the
// whole conversation is a swipe up, and the chips are real commands.
(() => {
  const F = window.Fable;
  const $ = (id) => document.getElementById(id);
  const input = $("input");
  const KEYS = { code: "fable.remote.code", chat: "fable.remote.chat", theme: "fable.remote.theme", unpaired: "fable.remote.unpaired", held: "fable.remote.held", graphics: "fable.remote.graphics" };
  const REPLY_TIMEOUT_MS = 90000;
  // Things Fable One on the PC really does (its CAPABILITIES_SPEECH).
  const CHIPS = ["Status check", "What's on my screen?", "Pause the music", "Turn the volume up", "Take a screenshot", "Recap my day", "What can you do?"];
  const buzz = (pattern) => navigator.vibrate && navigator.vibrate(pattern);

  // --- theme -----------------------------------------------------------------------------------------
  function applyTheme(theme) {
    const t = ["mono", "light", "blue", "paper"].includes(theme) ? theme : "mono";
    document.documentElement.dataset.fable = t;
    F.store.set(KEYS.theme, t);
    document.querySelectorAll("#themes button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.theme === t)));
    requestAnimationFrame(() => {
      document.querySelector('meta[name="theme-color"]').content = getComputedStyle(document.documentElement).getPropertyValue("--ground").trim();
      F.bus.emit("theme");
    });
  }
  applyTheme(F.store.get(KEYS.theme, "mono"));
  document.querySelectorAll("#themes button").forEach((b) => b.addEventListener("click", () => applyTheme(b.dataset.theme)));

  // --- graphics: Auto, Full or Light (scene.js has the steps) ---------------------------------------
  const DETAIL = { full: "full", high: "high", light: "light", lightest: "the lightest" };
  function showGraphics() {
    const info = F.orb.graphicsInfo();
    if (!info) {
      $("gfx-now").textContent = "This phone can't draw the 3D orb, so it shows a still one.";
      return;
    }
    const rate = info.fps ? `, ${info.fps} frames a second` : "";
    $("gfx-now").textContent = info.mode === "auto"
      ? `Auto picks the most this phone can draw smoothly. Now: ${DETAIL[info.tier] || info.tier} detail${rate}.`
      : `Now: ${DETAIL[info.tier] || info.tier} detail${rate}.`;
  }
  function applyGraphics(choice) {
    const mode = ["auto", "full", "light"].includes(choice) ? choice : "auto";
    F.store.set(KEYS.graphics, mode);
    F.orb.setGraphics(mode);
    document.querySelectorAll("#graphics button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.gfx === mode)));
    showGraphics();
  }
  applyGraphics(F.store.get(KEYS.graphics, "auto"));
  document.querySelectorAll("#graphics button").forEach((b) => b.addEventListener("click", () => applyGraphics(b.dataset.gfx)));

  // --- the conversation -------------------------------------------------------------------------------
  let chat = F.store.getJSON(KEYS.chat, []);
  const save = () => F.store.setJSON(KEYS.chat, chat.slice(-100));
  const clock = (at) => new Date(at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

  function historyBubble(kind, text, at) {
    const el = document.createElement("div");
    el.className = `msg ${kind}`;
    el.textContent = text;
    if (at && kind !== "note") {
      const t = document.createElement("time");
      t.textContent = clock(at);
      el.appendChild(t);
    }
    $("log").appendChild(el);
    return el;
  }

  function renderHistory() {
    $("log").innerHTML = "";
    if (!chat.length) historyBubble("note", "Nothing yet. Hold the orb and talk, or type below.");
    for (const m of chat) historyBubble(m.from === "me" ? "me" : m.error ? "fable error" : "fable", m.text, m.at);
    requestAnimationFrame(() => ($("log").scrollTop = $("log").scrollHeight));
  }

  // Fable One asks before running a plan ("... Go ahead, sir?") and takes
  // "go ahead" or "cancel" as the answer (main.py CONFIRM_YES/NO_PATTERN).
  const ASKS_TO_CONFIRM = /go ahead,?\s*(sir)?\s*\?\s*$/i;

  // Plan steps arrive as code - "1. ask_hermes(task: 'x')". Show them as words.
  function readable(text) {
    return String(text).replace(/^(\s*\d+\.\s+)([a-z_]+)\((.*)\)\s*$/gim, (whole, num, name, args) => {
      const title = name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
      const values = [...args.matchAll(/[a-z_]+:\s*('([^']*)'|"([^"]*)"|[^,]+)/gi)].map((m) => (m[2] ?? m[3] ?? m[1]).trim());
      return `${num}${title}${values.length ? `: ${values.join(", ")}` : ""}`;
    });
  }

  // The card shows the latest exchange.
  function showCard({ asked = "", answer = "", at = 0, working = false, fresh = false }) {
    $("asked").innerHTML = asked ? `You: <b></b>` : "";
    if (asked) $("asked").querySelector("b").textContent = asked;
    const box = $("answer");
    if (working) {
      box.innerHTML = '<span class="typing" aria-label="Fable One is working"><b></b><b></b><b></b></span>';
    } else {
      box.textContent = readable(answer);
      box.classList.toggle("fresh", fresh);
      box.scrollTop = 0;
    }
    // A question waiting for a yes or no gets two buttons.
    const confirm = $("confirm");
    confirm.hidden = working || !ASKS_TO_CONFIRM.test(answer);
    $("card").classList.toggle("working", working);
    $("card-time").textContent = at ? clock(at) : "";
  }

  function cardFromHistory() {
    const lastMe = [...chat].reverse().find((m) => m.from === "me");
    const lastFable = [...chat].reverse().find((m) => m.from !== "me");
    if (!lastFable && !lastMe) {
      showCard({ answer: "Hi. I'm Fable One, on your PC. Hold the orb and talk, tap a command below, or type." });
      return;
    }
    showCard({ asked: lastMe ? lastMe.text : "", answer: lastFable ? lastFable.text : "", at: (lastFable || lastMe).at });
  }

  function remember(from, text, extra = {}) {
    chat.push({ from, text, at: Date.now(), ...extra });
    save();
  }

  // --- the connection ---------------------------------------------------------------------------------------
  let client = null;
  let host = "";
  const waiting = new Map(); // command id -> { timer, spoken }

  const STATUS = {
    connecting: () => "Connecting...",
    online: () => (host ? `PC online - ${host}` : "PC online"),
    offline: () => "PC not answering",
    "relay-down": () => "No connection",
  };

  function onStatus(state, detail) {
    if (state === "online" && detail) host = detail;
    const el = $("status");
    const was = el.dataset.state;
    el.dataset.state = state;
    $("status-text").textContent = STATUS[state] ? STATUS[state]() : state;
    $("sheet-host").textContent = host ? `Paired with Fable One on ${host}.` : "Talking to Fable One on your PC.";
    if (state === "offline" && was !== "offline") {
      F.orb.flash();
      buzz([30, 60, 30]);
    }
  }

  function onAck(id) {
    if (waiting.has(id)) F.orb.setState("thinking");
  }

  function onReply(id, text) {
    const w = waiting.get(id);
    if (!w) return;
    waiting.delete(id);
    clearTimeout(w.timer);
    remember("fable", text);
    showCard({ asked: chat.filter((m) => m.from === "me").slice(-1)[0]?.text || "", answer: text, at: Date.now(), fresh: true });
    renderHistory();
    F.orb.burst();
    buzz([12, 50, 12]);
    speak(text, w.spoken);
  }

  function connect(code) {
    if (client) client.stop();
    client = new FableRelay.Client(code, { onStatus, onAck, onReply });
    client.start();
  }

  async function send(raw, spoken = false) {
    const text = String(raw || "").trim();
    if (!text) return;
    if (!client) return showPair();
    remember("me", text);
    renderHistory();
    showCard({ asked: text, working: true });
    F.orb.send();
    F.orb.setState("thinking");
    buzz(12);
    try {
      const id = await client.send(text);
      const timer = setTimeout(() => {
        if (!waiting.has(id)) return;
        waiting.delete(id);
        const why = "No answer from your PC after 90 seconds. It may be asleep, or Fable One isn't running.";
        remember("fable", why, { error: true });
        showCard({ asked: text, answer: why, at: Date.now(), fresh: true });
        renderHistory();
        F.orb.flash();
        F.orb.setState("idle");
      }, REPLY_TIMEOUT_MS);
      waiting.set(id, { timer, spoken });
    } catch (e) {
      const why = `Couldn't send: ${e.message || e}`;
      remember("fable", why, { error: true });
      showCard({ asked: text, answer: why, at: Date.now(), fresh: true });
      renderHistory();
      F.orb.flash();
      F.orb.setState("idle");
    }
  }

  // --- speaking the answer (when you talked) ------------------------------------------------------------------
  const native = window.FableNative || null; // the Android app's bridge, when there
  function speak(text, spoken) {
    const words = text.replace(/https?:\/\/\S+/g, "the link");
    if (spoken && native) {
      native.speak(words);
      return;
    }
    if (spoken && window.speechSynthesis) {
      F.orb.setState("speaking");
      const u = new SpeechSynthesisUtterance(words);
      u.onboundary = () => F.orb.setLevel(0.5 + Math.random() * 0.4);
      u.onend = u.onerror = () => F.orb.setState("idle");
      speechSynthesis.cancel();
      speechSynthesis.speak(u);
      return;
    }
    F.orb.setState("speaking");
    setTimeout(() => waiting.size === 0 && F.orb.setState("idle"), 1400);
  }

  // --- talking: hold the orb, or tap the mic ---------------------------------------------------------------------
  // Android's Chrome hands back each growing version of a sentence as its own
  // result ("why", "why did", "why did the chicken..."). Joining them sent
  // "whywhy didwhy did the chicken..." to the PC (seen in its log, 2026-09-26).
  // So pieces are merged: a longer version replaces the shorter one, a piece
  // already said is dropped, and only genuinely new words are added.
  function mergeSpeech(said, piece) {
    const a = String(said || "").trim();
    const b = String(piece || "").trim();
    if (!a) return b;
    if (!b) return a;
    const la = a.toLowerCase();
    const lb = b.toLowerCase();
    if (lb.startsWith(la)) return b;
    if (la.startsWith(lb) || la.endsWith(lb)) return a;
    return `${a} ${b}`;
  }

  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null;
  let listening = false;

  function setListening(on) {
    listening = on;
    $("mic").classList.toggle("live", on);
    $("hint").classList.toggle("live", on);
    $("hint").textContent = on ? "Listening - let go to send" : "Hold the orb to talk";
    F.orb.setState(on ? "listening" : waiting.size ? "thinking" : "idle");
  }

  window.FableNativeEvents = {
    on(type, text) {
      if (type === "start") setListening(true);
      else if (type === "level") F.orb.setLevel(parseFloat(text) || 0);
      else if (type === "partial") {
        input.value = text;
        grow();
      } else if (type === "final" || type === "error") {
        setListening(false);
        if (type === "final" && text.trim()) {
          input.value = "";
          grow();
          send(text, true);
        } else if (text === "not-allowed") {
          showCard({ answer: "I need the microphone to hear you. Allow it in the phone's settings for Fable One." });
        }
      } else if (type === "speaking") F.orb.setState("speaking");
      else if (type === "spoke") F.orb.setState("idle");
    },
  };

  function startListening() {
    if (listening) return;
    if (native) {
      native.stopSpeaking();
      native.listen();
      return;
    }
    if (!Recognition) {
      showCard({ answer: "This phone's browser can't do speech here. Use the microphone on your keyboard instead." });
      return;
    }
    if (window.speechSynthesis) speechSynthesis.cancel();
    rec = new Recognition();
    rec.lang = navigator.language || "en-US";
    rec.interimResults = true;
    // One sentence at a time: continuous mode on Android repeats itself.
    rec.continuous = false;
    let finalText = "";
    rec.onstart = () => setListening(true);
    rec.onresult = (event) => {
      let finals = "";
      let interim = "";
      for (let i = 0; i < event.results.length; i++) {
        const piece = event.results[i][0].transcript;
        if (event.results[i].isFinal) finals = mergeSpeech(finals, piece);
        else interim = mergeSpeech(interim, piece);
      }
      finalText = finals;
      input.value = mergeSpeech(finals, interim);
      grow();
      F.orb.setLevel(0.6);
    };
    rec.onend = () => {
      rec = null;
      setListening(false);
      const text = (finalText || input.value).trim();
      if (text) {
        input.value = "";
        grow();
        send(text, true);
      }
    };
    rec.onerror = (e) => {
      if (e.error === "not-allowed") showCard({ answer: "The microphone is blocked. Allow it for this app in Chrome's site settings." });
    };
    rec.start();
  }

  function stopListening() {
    if (native) native.stopListening();
    else if (rec) rec.stop();
  }

  F.bus.on("scene-hold-start", () => {
    buzz(25);
    F.store.set(KEYS.held, "1");
    startListening();
  });
  F.bus.on("scene-hold-end", stopListening);
  F.bus.on("scene-tap", () => {
    if (listening) return stopListening();
    if (!F.store.get(KEYS.held)) {
      $("hint").textContent = "Hold it down while you talk";
      setTimeout(() => !listening && ($("hint").textContent = "Hold the orb to talk"), 2200);
    }
  });
  $("mic").addEventListener("click", () => (listening ? stopListening() : startListening()));
  $("confirm-yes").addEventListener("click", (e) => {
    e.stopPropagation();
    send("go ahead");
  });
  $("confirm-no").addEventListener("click", (e) => {
    e.stopPropagation();
    send("cancel");
  });

  // --- the chat box -------------------------------------------------------------------------------------------------------
  function grow() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 110)}px`;
    $("send").disabled = !input.value.trim();
  }
  input.addEventListener("input", () => {
    grow();
    F.orb.tap();
  });
  // While the keyboard is up the scene draws less, so typing stays quick.
  input.addEventListener("focus", () => F.orb.typing(true));
  input.addEventListener("blur", () => F.orb.typing(false));
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      $("composer").requestSubmit();
    }
  });
  $("composer").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value;
    input.value = "";
    grow();
    input.blur();
    send(text);
  });

  $("chips").innerHTML = CHIPS.map((c) => `<button class="chip glass" type="button">${F.escapeHtml(c)}</button>`).join("");
  $("chips").querySelectorAll(".chip").forEach((chip) => chip.addEventListener("click", () => send(chip.textContent)));

  // --- the card tilts with the phone ----------------------------------------------------------------------------------------
  // The sensor fires about 60 times a second; the card is restyled at most 20
  // times, only when the angle really changed, and its transition smooths the
  // steps. At the lightest graphics it stays still.
  let base = null;
  let tiltAt = 0;
  let tiltWas = "";
  const card = $("card");
  window.addEventListener("deviceorientation", (e) => {
    if (e.beta === null || e.gamma === null) return;
    if (!base) base = { beta: e.beta, gamma: e.gamma };
    base.beta += (e.beta - base.beta) * 0.01;
    base.gamma += (e.gamma - base.gamma) * 0.01;
    const now = performance.now();
    if (now - tiltAt < 50) return;
    tiltAt = now;
    const still = document.documentElement.dataset.gfx === "lightest";
    const x = still ? 0 : Math.max(-8, Math.min(8, -(e.beta - base.beta) * 0.35));
    const y = still ? 0 : Math.max(-10, Math.min(10, (e.gamma - base.gamma) * 0.45));
    const next = `rotateX(${x.toFixed(1)}deg) rotateY(${y.toFixed(1)}deg)`;
    if (next !== tiltWas) card.style.transform = tiltWas = next;
  });

  // --- sheets: history (swipe up), pairing, menu ------------------------------------------------------------------------------
  const scrim = $("scrim");
  const sheets = ["history", "pair", "sheet"];
  // The scene stops drawing while a sheet covers it.
  function openSheet(id) {
    sheets.forEach((s) => ($(s).hidden = s !== id));
    scrim.hidden = false;
    if (id === "history") renderHistory();
    if (id === "sheet") showGraphics();
    F.orb.cover(true);
  }
  function closeSheets() {
    if (!$("pair").hidden && !F.store.get(KEYS.code)) return; // pairing can't be skipped
    sheets.forEach((s) => ($(s).hidden = true));
    scrim.hidden = true;
    F.orb.cover(false);
  }
  const showPair = () => {
    openSheet("pair");
    setTimeout(() => $("code").focus(), 300);
  };
  $("card").addEventListener("click", () => openSheet("history"));
  $("open-history").addEventListener("click", () => openSheet("history"));
  $("close-history").addEventListener("click", closeSheets);
  $("menu").addEventListener("click", () => openSheet("sheet"));
  $("close-sheet").addEventListener("click", closeSheets);
  scrim.addEventListener("click", closeSheets);

  // Swipe up on the card opens the history; swipe down on a sheet's top closes it.
  let swipe = null;
  $("card").addEventListener("touchstart", (e) => (swipe = { y: e.touches[0].clientY }), { passive: true });
  $("card").addEventListener("touchend", (e) => {
    if (swipe && swipe.y - e.changedTouches[0].clientY > 40) openSheet("history");
    swipe = null;
  });
  document.querySelectorAll(".sheet .grip, .sheet h2").forEach((grip) => {
    let start = null;
    grip.addEventListener("touchstart", (e) => (start = e.touches[0].clientY), { passive: true });
    grip.addEventListener("touchend", (e) => {
      if (start !== null && e.changedTouches[0].clientY - start > 50) closeSheets();
      start = null;
    });
  });

  // --- pairing ---------------------------------------------------------------------------------------------------------------------
  function tryPair(raw) {
    const code = FableRelay.normalise(raw);
    const result = $("pair-result");
    if (code.length !== 16) {
      result.textContent = "The code has 16 letters and numbers.";
      result.className = "result bad";
      return;
    }
    result.textContent = "Checking with your PC...";
    result.className = "result";
    const probe = new FableRelay.Client(code, {
      onStatus: (state, detail) => {
        if (state === "online") {
          probe.stop();
          F.store.set(KEYS.code, code);
          F.store.del(KEYS.unpaired);
          host = detail || host;
          result.textContent = `Paired${host ? ` with ${host}` : ""}.`;
          result.className = "result ok";
          buzz([10, 40, 10]);
          setTimeout(() => {
            closeSheets();
            connect(code);
          }, 700);
        } else if (state === "offline" || state === "relay-down") {
          probe.stop();
          result.textContent = "No answer. Check the code, and that Fable One is running on your PC.";
          result.className = "result bad";
        }
      },
    });
    probe.start();
  }
  $("pair-go").addEventListener("click", () => tryPair($("code").value));
  $("code").addEventListener("keydown", (e) => e.key === "Enter" && tryPair($("code").value));

  $("clear").addEventListener("click", () => {
    chat = [];
    save();
    renderHistory();
    cardFromHistory();
    closeSheets();
  });
  let unpairArmed = false;
  $("unpair").addEventListener("click", () => {
    if (!unpairArmed) {
      unpairArmed = true;
      $("unpair").textContent = "Tap again to unpair";
      setTimeout(() => {
        unpairArmed = false;
        $("unpair").textContent = "Unpair this phone";
      }, 4000);
      return;
    }
    F.store.del(KEYS.code);
    F.store.set(KEYS.unpaired, "1");
    if (client) client.stop();
    client = null;
    host = "";
    onStatus("connecting");
    $("status-text").textContent = "Not paired";
    showPair();
  });

  // --- start ------------------------------------------------------------------------------------------------------------------------
  // A pairing link: .../#pair=CODE. The part after # never leaves the phone
  // (browsers don't send it to the website), and it's wiped from the address
  // bar and history as soon as it's read.
  const fromLink = /^#pair=([A-Za-z0-9-]{16,24})$/.exec(location.hash);
  if (fromLink) {
    F.store.set(KEYS.code, FableRelay.normalise(fromLink[1]));
    F.store.del(KEYS.unpaired);
    history.replaceState(null, "", location.pathname + location.search);
  }
  // The owner's Android app is built already paired (js/paired.js); the
  // public website never is.
  const builtIn = window.FABLE_PAIRED && !F.store.get(KEYS.unpaired) ? FableRelay.normalise(window.FABLE_PAIRED) : "";

  renderHistory();
  cardFromHistory();
  grow();
  const saved = F.store.get(KEYS.code) || builtIn;
  if (saved) connect(saved);
  else {
    $("status-text").textContent = "Not paired";
    showPair();
  }
  if (F.store.get(KEYS.held)) $("hint").textContent = "Hold the orb to talk";
  if ("serviceWorker" in navigator && location.protocol === "https:" && !native) {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
})();
