// Shared plumbing for every other file: where we are running, storage that
// never throws, a tiny event bus, and the markdown renderer for replies.
//
// Everything hangs off window.Fable so the same files work both inlined into
// one HTML file and loaded as separate scripts (the extension, whose pages may
// not run inline script, and the desktop app).
window.Fable = window.Fable || {};

(() => {
  const F = window.Fable;

  // The extension build runs as a chrome-extension:// page with the tabs and
  // debugger APIs. The single file runs from file:// where chrome.runtime
  // exists but has no id. The desktop app's preload adds window.fableDesktop.
  F.IS_EXT = Boolean(window.chrome && chrome.runtime && chrome.runtime.id && chrome.tabs);
  F.IS_DESKTOP = Boolean(window.fableDesktop);
  F.edition = Object.assign({ id: "personal", owner: true, where: "file", defaults: {} }, window.FABLE_EDITION || {});
  // Pages opened from files share one storage in a browser, so each edition
  // keeps its own: a friends' copy tried on the owner's browser must not pick
  // up the owner's name, key or notes.
  F.PREFIX = F.edition.id === "friends" ? "fable.one." : "fable.app.";

  // localStorage can be missing or throw (private windows, blocked site data).
  // The app must still run, just without remembering anything.
  F.store = {
    get(key, fallback = null) {
      try {
        const value = localStorage.getItem(key);
        return value === null ? fallback : value;
      } catch (e) {
        return fallback;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(key, String(value));
      } catch (e) {
        // nothing to do - the setting just won't survive a reload
      }
    },
    del(key) {
      try {
        localStorage.removeItem(key);
      } catch (e) {}
    },
    getJSON(key, fallback) {
      try {
        const raw = localStorage.getItem(key);
        return raw ? JSON.parse(raw) : fallback;
      } catch (e) {
        return fallback;
      }
    },
    setJSON(key, value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
      } catch (e) {}
    },
  };

  // Settings with their defaults in one place, so nothing reads a raw key.
  const DEFAULTS = {
    key: "",
    name: "",
    theme: "mono",
    voice: "",
    rate: "1.05",
    speak: "voice", // voice | always | never
    convo: "on",
    stt: "auto", // auto | chrome | whisper
    askFirst: "off",
    city: "",
    omniUrl: "",
    omniModel: "auto",
    omniKey: "",
    brainMode: "auto", // auto (OmniRoute when it answers, else Groq) | groq
    micId: "", // "" = automatic: the default, unless it's silent
    units: "auto", // auto | f | c
  };
  // Each edition sets its own starting values (edition.js).
  Object.assign(DEFAULTS, F.edition.defaults || {});

  F.settings = {
    get(name) {
      return F.store.get(F.PREFIX + name, DEFAULTS[name]);
    },
    set(name, value) {
      F.store.set(F.PREFIX + name, value);
      F.bus.emit("setting", { name, value });
    },
  };

  const listeners = {};
  F.bus = {
    on(event, fn) {
      (listeners[event] = listeners[event] || []).push(fn);
    },
    emit(event, data) {
      for (const fn of listeners[event] || []) {
        try {
          fn(data);
        } catch (e) {
          console.error(`[Fable] ${event} listener failed`, e);
        }
      }
    },
  };

  F.sleep = (ms, signal) =>
    new Promise((resolve, reject) => {
      const timer = setTimeout(resolve, ms);
      if (signal) {
        signal.addEventListener("abort", () => {
          clearTimeout(timer);
          reject(new DOMException("stopped", "AbortError"));
        }, { once: true });
      }
    });

  F.escapeHtml = (text) =>
    String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  F.normaliseUrl = (raw) => {
    const url = String(raw || "").trim();
    if (!url) return "";
    if (/^https?:\/\//i.test(url)) return url;
    return `https://${url.replace(/^\/+/, "")}`;
  };

  // --- markdown ---------------------------------------------------------------
  // Replies are markdown-ish. This renders the parts the model actually uses -
  // paragraphs, lists, headings, code, bold, italics, links - and nothing
  // else. Everything is escaped first, so a reply can never inject markup.

  function inline(text) {
    let out = F.escapeHtml(text);
    const codes = [];
    out = out.replace(/`([^`]+)`/g, (_, code) => {
      codes.push(code);
      return `\u0000${codes.length - 1}\u0000`;
    });
    out = out
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      .replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>')
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      // Italics only between word boundaries, so maths like 2*3*4 stays maths.
      .replace(/(^|[\s(])\*([^*\s][^*]*?)\*(?=[\s.,;:!?)]|$)/g, "$1<em>$2</em>")
      .replace(/【[^】]*】/g, ""); // gpt-oss search citations: meaningless outside Groq
    return out.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[Number(i)]}</code>`);
  }

  F.renderMarkdown = (source) => {
    const lines = String(source || "").replace(/\r/g, "").split("\n");
    const html = [];
    let list = null; // "ul" | "ol"
    let para = [];
    const flushPara = () => {
      if (para.length) html.push(`<p>${para.map(inline).join("<br>")}</p>`);
      para = [];
    };
    const closeList = () => {
      if (list) html.push(`</${list}>`);
      list = null;
    };
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (/^\s*```/.test(line)) {
        flushPara();
        closeList();
        const code = [];
        i++;
        while (i < lines.length && !/^\s*```/.test(lines[i])) code.push(lines[i++]);
        html.push(`<pre><code>${F.escapeHtml(code.join("\n"))}</code></pre>`);
        continue;
      }
      const heading = line.match(/^\s*(#{1,4})\s+(.*)$/);
      const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
      const numbered = line.match(/^\s*(\d+)[.)]\s+(.*)$/);
      if (heading) {
        flushPara();
        closeList();
        html.push(`<h4>${inline(heading[2])}</h4>`);
      } else if (bullet || numbered) {
        flushPara();
        const kind = bullet ? "ul" : "ol";
        if (list !== kind) {
          closeList();
          html.push(numbered && numbered[1] !== "1" ? `<ol start="${numbered[1]}">` : `<${kind}>`);
          list = kind;
        }
        html.push(`<li>${inline(bullet ? bullet[1] : numbered[2])}</li>`);
      } else if (/^\s*\|.*\|\s*$/.test(line)) {
        // A table: render it as a real one rather than a row of pipes.
        flushPara();
        closeList();
        const rows = [];
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(lines[i++]);
        i--;
        const cells = (row) => row.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        const body = rows.filter((r) => !/^\s*\|[\s:|-]+\|\s*$/.test(r));
        html.push(
          "<table>" +
            body
              .map((r, n) => `<tr>${cells(r).map((c) => (n === 0 ? `<th>${inline(c)}</th>` : `<td>${inline(c)}</td>`)).join("")}</tr>`)
              .join("") +
            "</table>"
        );
      } else if (!line.trim()) {
        flushPara();
        closeList();
      } else {
        closeList();
        para.push(line);
      }
    }
    flushPara();
    closeList();
    return html.join("");
  };

  // What the voice should say: the words, without the markup.
  F.plainText = (source) =>
    String(source || "")
      .replace(/```[\s\S]*?```/g, " (code on screen) ")
      .replace(/【[^】]*】/g, "")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      .replace(/https?:\/\/\S+/g, "the link")
      .replace(/[*_`#>|]/g, "")
      .replace(/^\s*[-•]\s+/gm, "")
      .replace(/\s+/g, " ")
      .trim();

  F.fmtClock = (seconds) => {
    const s = Math.max(0, Math.round(seconds));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const r = s % 60;
    const two = (n) => String(n).padStart(2, "0");
    return h ? `${h}:${two(m)}:${two(r)}` : `${m}:${two(r)}`;
  };

  F.fmtSpan = (seconds) => {
    const s = Math.round(seconds);
    const parts = [];
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const r = s % 60;
    if (h) parts.push(`${h} hour${h === 1 ? "" : "s"}`);
    if (m) parts.push(`${m} minute${m === 1 ? "" : "s"}`);
    if (r || !parts.length) parts.push(`${r} second${r === 1 ? "" : "s"}`);
    return parts.join(" ");
  };
})();
