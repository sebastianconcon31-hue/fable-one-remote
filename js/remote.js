// Fable One Remote: the phone's chat with Fable One on the PC.
//
// Every message goes through the same encrypted relay the Chromebook page
// uses (relay.js here, voice-launcher/web_relay.py on the PC), so the PC runs
// it exactly like a spoken command - Fable One's own router, rules and gates,
// with destructive commands refused remotely. This page holds no secret of its
// own: the pairing code is typed in once and kept only on the phone.
(() => {
  const F = window.Fable;
  const $ = (id) => document.getElementById(id);
  const log = $("log");
  const input = $("input");
  const KEYS = { code: "fable.remote.code", chat: "fable.remote.chat", theme: "fable.remote.theme" };
  const REPLY_TIMEOUT_MS = 90000;

  // --- theme -----------------------------------------------------------------------------
  function applyTheme(theme) {
    const t = ["mono", "light", "blue", "paper"].includes(theme) ? theme : "mono";
    document.documentElement.dataset.fable = t;
    F.store.set(KEYS.theme, t);
    document.querySelectorAll("#themes button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.theme === t)));
    requestAnimationFrame(() => {
      const ground = getComputedStyle(document.documentElement).getPropertyValue("--ground").trim();
      document.querySelector('meta[name="theme-color"]').content = ground;
      F.bus.emit("theme");
    });
  }
  applyTheme(F.store.get(KEYS.theme, "mono"));
  document.querySelectorAll("#themes button").forEach((b) => b.addEventListener("click", () => applyTheme(b.dataset.theme)));

  // --- the conversation -------------------------------------------------------------------------
  let chat = F.store.getJSON(KEYS.chat, []);
  const save = () => F.store.setJSON(KEYS.chat, chat.slice(-80));
  const clock = (at) => new Date(at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

  function scrollDown() {
    requestAnimationFrame(() => (log.scrollTop = log.scrollHeight));
  }

  function bubble(kind, text, at) {
    const el = document.createElement("div");
    el.className = `msg ${kind}`;
    el.textContent = text;
    if (at && kind !== "note") {
      const t = document.createElement("time");
      t.textContent = clock(at);
      el.appendChild(t);
    }
    log.appendChild(el);
    scrollDown();
    return el;
  }

  function typing() {
    const el = document.createElement("div");
    el.className = "msg fable";
    el.innerHTML = '<span class="typing" aria-label="Fable One is working"><b></b><b></b><b></b></span>';
    log.appendChild(el);
    scrollDown();
    return el;
  }

  function render() {
    log.innerHTML = "";
    if (!chat.length) bubble("note", "Message Fable One on your PC. It runs what you ask and answers here.");
    for (const m of chat) bubble(m.from === "me" ? "me" : "fable", m.text, m.at);
  }

  function remember(from, text) {
    chat.push({ from, text, at: Date.now() });
    save();
  }

  // --- the connection --------------------------------------------------------------------------------
  let client = null;
  let host = "";
  const waiting = new Map(); // command id -> { el, spoken, timer }

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
      bubble("note", "Your PC isn't answering - it's off or asleep, or Fable One isn't running. Messages will work again once it's back.");
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
    w.el.remove();
    bubble("fable", text, Date.now());
    remember("fable", text);
    F.orb.burst();
    if (w.spoken && window.speechSynthesis) {
      F.orb.setState("speaking");
      const u = new SpeechSynthesisUtterance(text.replace(/https?:\/\/\S+/g, "the link"));
      u.onboundary = () => F.orb.setLevel(0.5 + Math.random() * 0.4);
      u.onend = () => F.orb.setState("idle");
      u.onerror = () => F.orb.setState("idle");
      speechSynthesis.cancel();
      speechSynthesis.speak(u);
    } else {
      F.orb.setState("speaking");
      setTimeout(() => waiting.size === 0 && F.orb.setState("idle"), 1400);
    }
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
    bubble("me", text, Date.now());
    remember("me", text);
    const el = typing();
    F.orb.setState("thinking");
    F.orb.tap();
    try {
      const id = await client.send(text);
      const timer = setTimeout(() => {
        if (!waiting.has(id)) return;
        waiting.delete(id);
        el.remove();
        bubble("fable error", "No answer from your PC after 90 seconds. It may be asleep, or Fable One isn't running.", Date.now());
        F.orb.flash();
        F.orb.setState("idle");
      }, REPLY_TIMEOUT_MS);
      waiting.set(id, { el, spoken, timer });
    } catch (e) {
      el.remove();
      bubble("fable error", `Couldn't send: ${e.message || e}`, Date.now());
      F.orb.flash();
      F.orb.setState("idle");
    }
  }

  // --- the chat box ---------------------------------------------------------------------------------------
  function grow() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
    $("send").disabled = !input.value.trim();
  }
  input.addEventListener("input", () => {
    grow();
    F.orb.tap();
  });
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
    send(text);
  });

  // Talk: the phone's own speech recognition; the words go to the PC as text.
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null;
  function toggleMic() {
    if (!Recognition) {
      bubble("note", "This browser can't do speech here - use the microphone on your keyboard instead.");
      return;
    }
    if (rec) return rec.stop();
    rec = new Recognition();
    rec.lang = navigator.language || "en-US";
    rec.interimResults = true;
    let finalText = "";
    rec.onstart = () => {
      $("mic").classList.add("live");
      F.orb.setState("listening");
    };
    rec.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) finalText += event.results[i][0].transcript;
        else interim += event.results[i][0].transcript;
      }
      input.value = (finalText + " " + interim).trim();
      grow();
      F.orb.setLevel(0.6);
    };
    rec.onend = () => {
      $("mic").classList.remove("live");
      rec = null;
      const text = finalText.trim();
      if (text) {
        input.value = "";
        grow();
        send(text, true);
      } else {
        F.orb.setState("idle");
      }
    };
    rec.onerror = (e) => {
      if (e.error === "not-allowed") bubble("note", "The microphone is blocked for this app. Allow it in the phone's app settings.");
    };
    rec.start();
  }
  $("mic").addEventListener("click", toggleMic);
  F.bus.on("orb-click", toggleMic);

  // --- pairing ------------------------------------------------------------------------------------------------
  const scrim = $("scrim");
  function showPair() {
    scrim.hidden = false;
    $("pair").hidden = false;
    setTimeout(() => $("code").focus(), 300);
  }
  function hideSheets() {
    scrim.hidden = true;
    $("pair").hidden = true;
    $("sheet").hidden = true;
  }

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
          host = detail || host;
          result.textContent = `Paired${host ? ` with ${host}` : ""}.`;
          result.className = "result ok";
          setTimeout(() => {
            hideSheets();
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

  // --- menu ------------------------------------------------------------------------------------------------------
  $("menu").addEventListener("click", () => {
    scrim.hidden = false;
    $("sheet").hidden = false;
  });
  $("close-sheet").addEventListener("click", hideSheets);
  scrim.addEventListener("click", () => {
    if (!$("pair").hidden && !F.store.get(KEYS.code)) return; // pairing can't be skipped
    hideSheets();
  });
  $("clear").addEventListener("click", () => {
    chat = [];
    save();
    render();
    hideSheets();
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
    if (client) client.stop();
    client = null;
    host = "";
    hideSheets();
    onStatus("connecting");
    $("status-text").textContent = "Not paired";
    showPair();
  });

  // --- start --------------------------------------------------------------------------------------------------------
  render();
  grow();
  const saved = F.store.get(KEYS.code);
  if (saved) connect(saved);
  else {
    $("status-text").textContent = "Not paired";
    showPair();
  }
  if ("serviceWorker" in navigator && location.protocol === "https:") {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
})();
