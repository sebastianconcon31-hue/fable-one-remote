// Talking to Fable One on the PC from any browser, through an encrypted relay.
// The PC side is voice-launcher/web_relay.py; the key derivation, topic names
// and wire format here must match it exactly.
//
// ntfy.sh carries the messages but can read none of them: each one is
// AES-256-GCM sealed with a key derived from the pairing code, and the topic
// names are derived from the code too. Nothing here needs an account, a port,
// or a server of Sebastian's own - which is what lets a school Chromebook reach
// a PC behind a home router.

const FableRelay = (() => {
  const RELAY = "https://ntfy.sh";
  const SALT = "fable-one-relay-v1";
  const ITERATIONS = 200000;
  const enc = new TextEncoder();
  const dec = new TextDecoder();

  const normalise = (code) => String(code || "").toUpperCase().replace(/[^A-Z0-9]/g, "");

  function b64(bytes) {
    let s = "";
    for (const b of bytes) s += String.fromCharCode(b);
    return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function unb64(text) {
    const s = text.replace(/-/g, "+").replace(/_/g, "/");
    const bin = atob(s + "=".repeat((4 - (s.length % 4)) % 4));
    return Uint8Array.from(bin, (c) => c.charCodeAt(0));
  }

  async function derive(code) {
    const base = await crypto.subtle.importKey("raw", enc.encode(normalise(code)), "PBKDF2", false, ["deriveBits"]);
    const seed = new Uint8Array(await crypto.subtle.deriveBits(
      { name: "PBKDF2", hash: "SHA-256", salt: enc.encode(SALT), iterations: ITERATIONS }, base, 384));
    const tid = Array.from(seed.slice(32), (b) => b.toString(16).padStart(2, "0")).join("").slice(0, 24);
    const key = await crypto.subtle.importKey("raw", seed.slice(0, 32), "AES-GCM", false, ["encrypt", "decrypt"]);
    return { key, up: `fable1-${tid}-up`, down: `fable1-${tid}-down` };
  }

  async function seal(key, payload, topic) {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const ct = new Uint8Array(await crypto.subtle.encrypt(
      { name: "AES-GCM", iv, additionalData: enc.encode(topic) }, key, enc.encode(JSON.stringify(payload))));
    const out = new Uint8Array(12 + ct.length);
    out.set(iv);
    out.set(ct, 12);
    return b64(out);
  }

  async function open(key, text, topic) {
    try {
      const raw = unb64(text.trim());
      const plain = await crypto.subtle.decrypt(
        { name: "AES-GCM", iv: raw.slice(0, 12), additionalData: enc.encode(topic) }, key, raw.slice(12));
      return JSON.parse(dec.decode(plain));
    } catch (e) {
      return null; // not sealed with our key - ignore it
    }
  }

  const newId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;

  // status: "connecting" | "online" | "offline" | "relay-down"
  class Client {
    constructor(code, { onStatus = () => {}, onAck = () => {}, onReply = () => {} } = {}) {
      this.code = code;
      this.on = { onStatus, onAck, onReply };
      this.pending = new Map(); // id -> {parts: []}
      this.lastId = null;
      this.source = null;
      this.status = null;
      this.pingTimer = null;
      this.pongDeadline = null;
      this.stopped = false;
    }

    setStatus(s, detail) {
      this.status = s;
      this.on.onStatus(s, detail);
    }

    async start() {
      this.setStatus("connecting");
      this.keys = await derive(this.code);
      this.subscribe();
      this.ping();
      // Once a minute is well inside ntfy's anonymous limit (a burst of 60,
      // then one request per 5 seconds) and still notices a PC going to sleep.
      this.pingTimer = setInterval(() => this.ping(), 60000);
    }

    stop() {
      this.stopped = true;
      clearInterval(this.pingTimer);
      clearTimeout(this.pongDeadline);
      if (this.source) this.source.close();
    }

    subscribe() {
      if (this.stopped) return;
      // No "since" on the first connect: only replies to what this page sends.
      // After a drop, resume from the last message seen so nothing is lost.
      const since = this.lastId ? `?since=${this.lastId}` : "";
      const src = new EventSource(`${RELAY}/${this.keys.down}/sse${since}`);
      this.source = src;
      src.onmessage = (e) => this.onEvent(e.data);
      src.onerror = () => {
        src.close();
        if (this.status !== "offline") this.setStatus("relay-down", "Can't reach the relay (ntfy.sh). Retrying...");
        setTimeout(() => this.subscribe(), 4000);
      };
      src.onopen = () => {
        if (this.status === "relay-down") this.ping();
      };
    }

    async onEvent(data) {
      let event;
      try {
        event = JSON.parse(data);
      } catch (e) {
        return;
      }
      if (event.event !== "message") return;
      this.lastId = event.id;
      const msg = await open(this.keys.key, event.message || "", this.keys.down);
      if (!msg) return;
      if (msg.kind === "pong") {
        clearTimeout(this.pongDeadline);
        this.setStatus("online", msg.host || "");
      } else if (msg.kind === "ack" && this.pending.has(msg.id)) {
        this.setStatus("online");
        this.on.onAck(msg.id);
      } else if (msg.kind === "reply" && this.pending.has(msg.id)) {
        const entry = this.pending.get(msg.id);
        entry.parts[msg.part || 0] = msg.text || "";
        const n = msg.parts || 1;
        if (entry.parts.filter((p) => p !== undefined).length >= n) {
          this.pending.delete(msg.id);
          this.on.onReply(msg.id, entry.parts.join(""));
        }
      }
    }

    async publish(payload) {
      const body = await seal(this.keys.key, { v: 1, at: Date.now(), ...payload }, this.keys.up);
      const res = await fetch(`${RELAY}/${this.keys.up}`, { method: "POST", body });
      if (!res.ok) throw new Error(res.status === 429 ? "relay rate limit - wait a minute" : `relay said ${res.status}`);
    }

    async ping() {
      if (!this.keys) return;
      clearTimeout(this.pongDeadline);
      this.pongDeadline = setTimeout(() => {
        this.setStatus("offline", "Your PC didn't answer. It's off or asleep, or Fable One isn't running.");
      }, 12000);
      try {
        await this.publish({ kind: "ping", id: newId() });
      } catch (e) {
        this.setStatus("relay-down", String(e.message || e));
      }
    }

    // Returns the command id. The reply arrives through onReply.
    async send(text) {
      const id = newId();
      this.pending.set(id, { parts: [] });
      await this.publish({ kind: "cmd", id, text });
      return id;
    }
  }

  return { Client, normalise };
})();
