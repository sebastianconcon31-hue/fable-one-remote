// Texture painter. It runs in a (headless) browser page, because a canvas
// draws text properly and Node on its own can't. generate.mjs hands it
// layouts; it hands back PNG data URLs.
//
//   paintAtlas(spec)   panel faces, key caps, gauges, lamps and small displays,
//                      packed into one image (plus an emissive image of just
//                      the lettering and lit parts)
//   paintScreen(spec)  one full display page: MPD FLT / TSD / WPN / ENG, TEDAC FLIR
(() => {
  const SANS = '"DejaVu Sans Condensed","Liberation Sans Narrow","Arial Narrow","Roboto Condensed",Arial,sans-serif';
  const MONO = '"DejaVu Sans Mono","Liberation Mono","Courier New",monospace';
  const INK = "#ecebe2";
  const PANEL = "#2b2e30";

  function rng(seed) {
    let a = seed >>> 0;
    return () => {
      a |= 0;
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function canvas(w, h, fill) {
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    const g = c.getContext("2d");
    if (fill) {
      g.fillStyle = fill;
      g.fillRect(0, 0, w, h);
    }
    return { c, g };
  }

  const font = (px, o = {}) => `${o.bold === false ? "" : "bold "}${Math.max(4, px).toFixed(1)}px ${o.mono ? MONO : SANS}`;

  // Draw on the colour image and, lit, on the emissive one.
  function both(g, e, fn) {
    fn(g, false);
    if (e) fn(e, true);
  }

  function text(g, str, x, y, px, o = {}) {
    g.save();
    g.font = font(px, o);
    g.textAlign = o.align || "center";
    g.textBaseline = o.base || "middle";
    g.fillStyle = o.color || INK;
    const lines = String(str).split("\n");
    const lh = px * (o.lh || 1.05);
    lines.forEach((l, i) => g.fillText(l, x, y + (i - (lines.length - 1) / 2) * lh));
    g.restore();
  }

  // --- panels -----------------------------------------------------------------------------------------------------
  function paintPanel(g, e, it) {
    const [X, Y, W, H] = it.rect;
    const s = W / it.m[0];
    const P = (x, y) => [X + x * s, Y + y * s];
    const R = rng(it.seed || 7);
    for (const ctx of [g, e].filter(Boolean)) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(X, Y, W, H);
      ctx.clip();
    }
    g.fillStyle = it.bg || PANEL;
    g.fillRect(X, Y, W, H);
    // Worn paint: a faint vertical wash and speckle.
    const grad = g.createLinearGradient(X, Y, X, Y + H);
    grad.addColorStop(0, "rgba(255,255,255,0.05)");
    grad.addColorStop(1, "rgba(0,0,0,0.14)");
    g.fillStyle = grad;
    g.fillRect(X, Y, W, H);
    for (let i = 0; i < (W * H) / 90; i++) {
      g.fillStyle = R() < 0.5 ? "rgba(255,255,255,0.025)" : "rgba(0,0,0,0.05)";
      g.fillRect(X + R() * W, Y + R() * H, 1 + R() * 2, 1 + R() * 2);
    }
    // A chipped edge here and there.
    g.strokeStyle = "rgba(160,160,150,0.18)";
    g.lineWidth = Math.max(1, s * 0.0008);
    g.strokeRect(X + 1, Y + 1, W - 2, H - 2);
    g.strokeStyle = "rgba(0,0,0,0.5)";
    g.strokeRect(X + 0.5, Y + 0.5, W - 1, H - 1);
    for (const [hx, hy, hw, hh] of it.holes || []) {
      g.fillStyle = "#050505";
      g.fillRect(...P(hx, hy), hw * s, hh * s);
    }
    // Quarter-turn fasteners in the corners.
    if (it.fasteners !== false && it.m[0] > 0.05 && it.m[1] > 0.035) {
      const inset = 0.0055;
      for (const [fx, fy] of [[inset, inset], [it.m[0] - inset, inset], [inset, it.m[1] - inset], [it.m[0] - inset, it.m[1] - inset]]) {
        const [cx, cy] = P(fx, fy);
        const r = 0.0026 * s;
        const rg = g.createRadialGradient(cx - r * 0.3, cy - r * 0.3, r * 0.1, cx, cy, r);
        rg.addColorStop(0, "#8d8f8c");
        rg.addColorStop(1, "#3b3d3c");
        g.fillStyle = rg;
        g.beginPath();
        g.arc(cx, cy, r, 0, Math.PI * 2);
        g.fill();
        g.strokeStyle = "#1a1b1a";
        g.lineWidth = r * 0.35;
        const a = R() * Math.PI;
        g.beginPath();
        g.moveTo(cx - Math.cos(a) * r * 0.8, cy - Math.sin(a) * r * 0.8);
        g.lineTo(cx + Math.cos(a) * r * 0.8, cy + Math.sin(a) * r * 0.8);
        g.stroke();
      }
    }
    const px = (m) => m * s;
    const tsize = it.textSize || 0.0042;
    if (it.title) {
      both(g, e, (c) => text(c, it.title, ...P(it.m[0] / 2, it.titleY ?? 0.0062), px(tsize * 1.05), { color: INK }));
    }
    for (const c of it.ctl || []) {
      const [cx, cy] = P(c.x, c.y);
      const ts = px(c.size || tsize);
      switch (c.k) {
        case "label":
          both(g, e, (ctx) => text(ctx, c.text, cx, cy, ts, { align: c.align || "center", color: c.color || INK }));
          break;
        case "box":
          both(g, e, (ctx) => {
            ctx.strokeStyle = INK;
            ctx.lineWidth = Math.max(1, px(0.0005));
            ctx.strokeRect(cx, cy, px(c.w), px(c.h));
          });
          if (c.text) {
            const tw = (() => {
              g.font = font(ts * 0.9);
              return g.measureText(c.text).width + ts * 0.6;
            })();
            g.fillStyle = it.bg || PANEL;
            g.fillRect(cx + px(c.w) / 2 - tw / 2, cy - ts * 0.6, tw, ts * 1.2);
            if (e) {
              e.fillStyle = "#000";
              e.fillRect(cx + px(c.w) / 2 - tw / 2, cy - ts * 0.6, tw, ts * 1.2);
            }
            both(g, e, (ctx) => text(ctx, c.text, cx + px(c.w) / 2, cy, ts * 0.9));
          }
          break;
        case "toggle": {
          both(g, e, (ctx) => {
            if (c.label) text(ctx, c.label, cx, cy - px(c.labelDy ?? 0.0125), ts, {});
            const pos = c.pos || [];
            const ps = ts * 0.78;
            if (pos.length === 2) {
              text(ctx, pos[0], cx + px(0.0062), cy - px(0.0045), ps, { align: "left" });
              text(ctx, pos[1], cx + px(0.0062), cy + px(0.0048), ps, { align: "left" });
            } else if (pos.length === 3) {
              text(ctx, pos[0], cx + px(0.0062), cy - px(0.0055), ps, { align: "left" });
              text(ctx, pos[1], cx + px(0.0062), cy, ps, { align: "left" });
              text(ctx, pos[2], cx + px(0.0062), cy + px(0.0055), ps, { align: "left" });
            }
          });
          // the nut's shadow ring
          g.fillStyle = "rgba(0,0,0,0.35)";
          g.beginPath();
          g.arc(cx + 1, cy + 1, px(0.0048), 0, Math.PI * 2);
          g.fill();
          if (c.guard) {
            g.fillStyle = "#b8231c";
            g.globalAlpha = 0.35;
            g.fillRect(cx - px(0.007), cy - px(0.009), px(0.014), px(0.018));
            g.globalAlpha = 1;
          }
          break;
        }
        case "knob": {
          const r = px(c.r || 0.007);
          const stops = c.stops || [];
          const span = c.span ?? 270;
          both(g, e, (ctx) => {
            ctx.strokeStyle = INK;
            ctx.lineWidth = Math.max(1, px(0.0005));
            const n = Math.max(stops.length, c.ticks || 0);
            for (let i = 0; i < n; i++) {
              const a = ((-span / 2 + (span * i) / Math.max(1, n - 1)) * Math.PI) / 180 - Math.PI / 2;
              ctx.beginPath();
              ctx.moveTo(cx + Math.cos(a) * (r + px(0.0012)), cy + Math.sin(a) * (r + px(0.0012)));
              ctx.lineTo(cx + Math.cos(a) * (r + px(0.0032)), cy + Math.sin(a) * (r + px(0.0032)));
              ctx.stroke();
            }
            stops.forEach((st, i) => {
              const a = ((-span / 2 + (span * i) / Math.max(1, stops.length - 1)) * Math.PI) / 180 - Math.PI / 2;
              const rr = r + px(0.0062);
              text(ctx, st, cx + Math.cos(a) * rr, cy + Math.sin(a) * rr, ts * 0.72, {});
            });
            if (c.arc) {
              ctx.beginPath();
              ctx.arc(cx, cy, r + px(0.0018), ((-span / 2 - 90) * Math.PI) / 180, ((span / 2 - 90) * Math.PI) / 180);
              ctx.stroke();
            }
            if (c.label) text(ctx, c.label, cx, cy + (c.labelDy != null ? px(c.labelDy) : r + px(stops.length ? 0.0105 : 0.006)), ts, {});
          });
          g.fillStyle = "rgba(0,0,0,0.45)";
          g.beginPath();
          g.arc(cx + 1.5, cy + 1.5, r * 1.05, 0, Math.PI * 2);
          g.fill();
          break;
        }
        case "pb": {
          if (c.label) both(g, e, (ctx) => text(ctx, c.label, cx, cy - px(c.h / 2 + 0.004), ts, {}));
          g.fillStyle = "#0c0c0c";
          g.fillRect(cx - px(c.w / 2 + 0.0012), cy - px(c.h / 2 + 0.0012), px(c.w + 0.0024), px(c.h + 0.0024));
          break;
        }
        case "slot": {
          g.fillStyle = "#080808";
          g.fillRect(cx - px(c.w / 2), cy - px(c.h / 2), px(c.w), px(c.h));
          both(g, e, (ctx) => {
            for (const mk of c.marks || []) {
              const my = cy - px(c.h / 2) + px(c.h) * mk.t;
              ctx.strokeStyle = INK;
              ctx.lineWidth = Math.max(1, px(0.0005));
              ctx.beginPath();
              ctx.moveTo(cx - px(c.w / 2) - px(0.004), my);
              ctx.lineTo(cx - px(c.w / 2) - px(0.001), my);
              ctx.moveTo(cx + px(c.w / 2) + px(0.001), my);
              ctx.lineTo(cx + px(c.w / 2) + px(0.004), my);
              ctx.stroke();
              text(ctx, mk.text, cx + (mk.side === "left" ? -1 : 1) * (px(c.w / 2) + px(0.0055)), my, ts * 0.85, { align: mk.side === "left" ? "right" : "left" });
            }
            if (c.label) text(ctx, c.label, cx, cy + px(c.h / 2 + 0.0055), ts, {});
          });
          break;
        }
        case "hazard": {
          hazard(g, cx, cy, px(c.w), px(c.h));
          break;
        }
        case "grille": {
          g.fillStyle = "#101112";
          g.fillRect(cx, cy, px(c.w), px(c.h));
          g.fillStyle = "#3a3d3f";
          for (let yy = 0; yy < px(c.h); yy += px(0.003)) g.fillRect(cx, cy + yy, px(c.w), px(0.0012));
          break;
        }
        case "screw": {
          g.fillStyle = "#6f716e";
          g.beginPath();
          g.arc(cx, cy, px(0.0018), 0, Math.PI * 2);
          g.fill();
          break;
        }
      }
    }
    for (const ctx of [g, e].filter(Boolean)) ctx.restore();
  }

  function hazard(g, x, y, w, h) {
    g.save();
    g.beginPath();
    g.rect(x, y, w, h);
    g.clip();
    g.fillStyle = "#e8b90c";
    g.fillRect(x, y, w, h);
    g.fillStyle = "#111";
    const st = Math.max(6, Math.min(w, h) * 0.35);
    for (let i = -h; i < w + h; i += st * 2) {
      g.beginPath();
      g.moveTo(x + i, y + h);
      g.lineTo(x + i + st, y + h);
      g.lineTo(x + i + st + h, y);
      g.lineTo(x + i + h, y);
      g.closePath();
      g.fill();
    }
    g.restore();
  }

  function paintCap(g, e, it) {
    const [X, Y, W, H] = it.rect;
    g.fillStyle = it.bg || "#1b1c1d";
    g.fillRect(X, Y, W, H);
    const edge = g.createLinearGradient(X, Y, X, Y + H);
    edge.addColorStop(0, "rgba(255,255,255,0.10)");
    edge.addColorStop(0.5, "rgba(255,255,255,0)");
    edge.addColorStop(1, "rgba(0,0,0,0.25)");
    g.fillStyle = edge;
    g.fillRect(X, Y, W, H);
    if (e) {
      e.fillStyle = it.glow ? it.bgGlow || "#000" : "#000";
      e.fillRect(X, Y, W, H);
    }
    if (!it.text) return;
    const lines = String(it.text).split("\n");
    const longest = Math.max(...lines.map((l) => l.length), 1);
    const px = Math.min(H * (it.fill || 0.62) / lines.length, (W * 1.55) / longest) * (it.scale || 1);
    both(g, e, (ctx, lit) => text(ctx, it.text, X + W / 2, Y + H / 2 + px * 0.04, px, { color: lit ? it.glowColor || it.fg || INK : it.fg || INK, lh: 1.0 }));
  }

  function paintFill(g, e, it) {
    const [X, Y, W, H] = it.rect;
    g.fillStyle = it.color;
    g.fillRect(X, Y, W, H);
    if (e) {
      e.fillStyle = it.emissive || "#000";
      e.fillRect(X, Y, W, H);
    }
  }

  function paintHazard(g, e, it) {
    const [X, Y, W, H] = it.rect;
    hazard(g, X, Y, W, H);
    if (e) {
      e.fillStyle = "#000";
      e.fillRect(X, Y, W, H);
    }
  }

  // --- gauges -----------------------------------------------------------------------------------------------------
  function paintGauge(g, e, it) {
    const [X, Y, W, H] = it.rect;
    const cx = X + W / 2, cy = Y + H / 2, R = W / 2;
    for (const ctx of [g, e].filter(Boolean)) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(X, Y, W, H);
      ctx.clip();
    }
    g.fillStyle = "#0b0b0b";
    g.fillRect(X, Y, W, H);
    e.fillStyle = "#000";
    e.fillRect(X, Y, W, H);
    const line = (ctx, a, r0, r1, w) => {
      ctx.lineWidth = w;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * r0, cy + Math.sin(a) * r0);
      ctx.lineTo(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1);
      ctx.stroke();
    };
    if (it.type === "ADI") {
      // The ball: sky over ground, with a pitch ladder. The aircraft symbol is a separate part in front.
      g.save();
      g.beginPath();
      g.arc(cx, cy, R * 0.98, 0, Math.PI * 2);
      g.clip();
      g.fillStyle = "#3f78b5";
      g.fillRect(X, Y, W, H / 2);
      g.fillStyle = "#5b3a1f";
      g.fillRect(X, cy, W, H / 2);
      g.restore();
      both(g, e, (ctx) => {
        ctx.strokeStyle = "#f4f4ee";
        ctx.fillStyle = "#f4f4ee";
        ctx.lineWidth = R * 0.03;
        ctx.beginPath();
        ctx.moveTo(cx - R * 0.95, cy);
        ctx.lineTo(cx + R * 0.95, cy);
        ctx.stroke();
        for (const p of [-20, -10, 10, 20]) {
          const yy = cy - p * R * 0.022;
          const hw = R * (Math.abs(p) === 10 ? 0.28 : 0.4);
          ctx.lineWidth = R * 0.02;
          ctx.beginPath();
          ctx.moveTo(cx - hw, yy);
          ctx.lineTo(cx + hw, yy);
          ctx.stroke();
          text(ctx, String(Math.abs(p)), cx - hw - R * 0.1, yy, R * 0.11, { color: "#f4f4ee" });
          text(ctx, String(Math.abs(p)), cx + hw + R * 0.1, yy, R * 0.11, { color: "#f4f4ee" });
        }
        for (const p of [-5, 5, -15, 15]) {
          const yy = cy - p * R * 0.022;
          ctx.lineWidth = R * 0.015;
          ctx.beginPath();
          ctx.moveTo(cx - R * 0.12, yy);
          ctx.lineTo(cx + R * 0.12, yy);
          ctx.stroke();
        }
        // roll scale
        for (const d of [-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60]) {
          const a = ((d - 90) * Math.PI) / 180;
          line(ctx, a, R * 0.8, R * (d % 30 === 0 ? 0.95 : 0.9), R * 0.025);
        }
      });
    } else if (it.type === "ASI") {
      both(g, e, (ctx) => {
        ctx.strokeStyle = "#f4f4ee";
        const a0 = -Math.PI / 2, span = Math.PI * 1.75;
        for (let v = 0; v <= 200; v += 5) {
          const a = a0 + (v / 200) * span;
          line(ctx, a, R * (v % 20 === 0 ? 0.74 : 0.82), R * 0.92, R * (v % 20 === 0 ? 0.035 : 0.02));
          if (v % 40 === 0 && v > 0) text(ctx, String(v), cx + Math.cos(a) * R * 0.58, cy + Math.sin(a) * R * 0.58, R * 0.17, { color: "#f4f4ee" });
        }
        text(ctx, "0", cx + Math.cos(a0) * R * 0.58, cy + Math.sin(a0) * R * 0.58, R * 0.17, { color: "#f4f4ee" });
        text(ctx, "KNOTS", cx, cy + R * 0.28, R * 0.11, { color: "#f4f4ee" });
        text(ctx, "AIRSPEED", cx, cy - R * 0.24, R * 0.1, { color: "#f4f4ee" });
        ctx.strokeStyle = "#e3342f";
        const ar = a0 + (197 / 200) * span;
        line(ctx, ar, R * 0.72, R * 0.94, R * 0.05);
      });
    } else if (it.type === "ALT") {
      both(g, e, (ctx) => {
        ctx.strokeStyle = "#f4f4ee";
        for (let v = 0; v < 50; v++) {
          const a = -Math.PI / 2 + (v / 50) * Math.PI * 2;
          line(ctx, a, R * (v % 5 === 0 ? 0.74 : 0.84), R * 0.93, R * (v % 5 === 0 ? 0.04 : 0.02));
          if (v % 5 === 0) text(ctx, String(v / 5), cx + Math.cos(a) * R * 0.6, cy + Math.sin(a) * R * 0.6, R * 0.19, { color: "#f4f4ee" });
        }
        text(ctx, "ALT", cx - R * 0.26, cy - R * 0.3, R * 0.1, { color: "#f4f4ee" });
        text(ctx, "100 FT", cx - R * 0.26, cy + R * 0.3, R * 0.09, { color: "#f4f4ee" });
      });
      // counter drum window
      g.fillStyle = "#000";
      g.fillRect(cx + R * 0.02, cy - R * 0.13, R * 0.5, R * 0.26);
      g.strokeStyle = "#777";
      g.strokeRect(cx + R * 0.02, cy - R * 0.13, R * 0.5, R * 0.26);
      both(g, e, (ctx) => text(ctx, "01850", cx + R * 0.27, cy, R * 0.16, { mono: true, color: "#f4f4ee" }));
      g.fillStyle = "#000";
      g.fillRect(cx - R * 0.2, cy + R * 0.45, R * 0.4, R * 0.18);
      both(g, e, (ctx) => text(ctx, "29.92", cx, cy + R * 0.54, R * 0.11, { mono: true, color: "#f4f4ee" }));
    } else if (it.type === "CLOCK") {
      both(g, e, (ctx) => {
        ctx.strokeStyle = "#f4f4ee";
        for (let v = 0; v < 60; v++) {
          const a = -Math.PI / 2 + (v / 60) * Math.PI * 2;
          line(ctx, a, R * (v % 5 === 0 ? 0.76 : 0.85), R * 0.93, R * (v % 5 === 0 ? 0.04 : 0.02));
          if (v % 5 === 0) text(ctx, String(v / 5 || 12), cx + Math.cos(a) * R * 0.6, cy + Math.sin(a) * R * 0.6, R * 0.17, { color: "#f4f4ee" });
        }
      });
    } else if (it.type === "COMPASS") {
      // A strip of the compass card, seen through a window.
      g.fillStyle = "#101010";
      g.fillRect(X, Y, W, H);
      both(g, e, (ctx) => {
        ctx.strokeStyle = "#f4f4ee";
        const labels = { 0: "N", 90: "E", 180: "S", 270: "W" };
        for (let d = -60; d <= 60; d += 5) {
          const hdg = (354 + d + 360) % 360;
          const xx = cx + (d / 60) * W * 0.5;
          const tall = hdg % 30 === 0 || Math.round(hdg) % 10 === 0;
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.moveTo(xx, Y + H * 0.62);
          ctx.lineTo(xx, Y + H * (tall ? 0.42 : 0.52));
          ctx.stroke();
        }
        for (let d = -60; d <= 60; d++) {
          const hdg = (((354 + d) % 360) + 360) % 360;
          if (hdg % 30 !== 0) continue;
          const xx = cx + (d / 60) * W * 0.5;
          text(ctx, labels[hdg] || String(hdg / 10), xx, Y + H * 0.24, H * 0.26, { color: "#f4f4ee" });
        }
        ctx.strokeStyle = "#e0a020";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(cx, Y + H * 0.05);
        ctx.lineTo(cx, Y + H * 0.95);
        ctx.stroke();
      });
    }
    for (const ctx of [g, e].filter(Boolean)) ctx.restore();
  }

  // --- small displays (EUFD, keyboard scratchpad) ------------------------------------------------------------------
  function paintText(g, e, it) {
    const [X, Y, W, H] = it.rect;
    g.fillStyle = it.bg || "#020402";
    g.fillRect(X, Y, W, H);
    if (e) {
      e.fillStyle = "#000";
      e.fillRect(X, Y, W, H);
    }
    const rows = it.rows || it.lines.length;
    const lh = (H - it.pad * 2) / rows;
    const px = lh * (it.size || 0.78);
    it.lines.forEach((ln, i) => {
      const segs = Array.isArray(ln) ? ln : [{ t: ln }];
      for (const sg of segs) {
        const x = X + it.pad + (sg.col || 0) * px * 0.6;
        both(g, e, (ctx) => text(ctx, sg.t, x, Y + it.pad + lh * (i + 0.5), px, { mono: true, bold: false, align: "left", color: sg.c || it.color || "#8dff7a" }));
      }
    });
    // Faint scanlines.
    g.fillStyle = "rgba(0,0,0,0.18)";
    for (let yy = Y; yy < Y + H; yy += 3) g.fillRect(X, yy, W, 1);
  }

  // The face of a 19-tube rocket pod.
  function paintPod(g, e, it) {
    const [X, Y, W, H] = it.rect;
    const cx = X + W / 2, cy = Y + H / 2, R = W / 2;
    g.fillStyle = "#353b30";
    g.fillRect(X, Y, W, H);
    const d = R * 0.31;
    const pts = [[0, 0]];
    for (let i = 0; i < 6; i++) pts.push([Math.cos((i * Math.PI) / 3) * d, Math.sin((i * Math.PI) / 3) * d]);
    for (let i = 0; i < 6; i++) pts.push([Math.cos((i * Math.PI) / 3) * d * 2, Math.sin((i * Math.PI) / 3) * d * 2]);
    for (let i = 0; i < 6; i++) pts.push([Math.cos((i * Math.PI) / 3 + Math.PI / 6) * d * 1.732, Math.sin((i * Math.PI) / 3 + Math.PI / 6) * d * 1.732]);
    for (const [px, py] of pts) {
      g.fillStyle = "#1a1c18";
      g.beginPath();
      g.arc(cx + px, cy + py, d * 0.46, 0, Math.PI * 2);
      g.fill();
      g.fillStyle = "#050505";
      g.beginPath();
      g.arc(cx + px, cy + py, d * 0.36, 0, Math.PI * 2);
      g.fill();
    }
    if (e) {
      e.fillStyle = "#000";
      e.fillRect(X, Y, W, H);
    }
  }

  const PAINTERS = { panel: paintPanel, cap: paintCap, fill: paintFill, hazard: paintHazard, gauge: paintGauge, text: paintText, pod: paintPod };

  window.paintAtlas = (spec) => {
    const { c, g } = canvas(spec.size, spec.size, "#1a1a1a");
    const em = spec.emissive ? canvas(spec.size, spec.size, "#000") : null;
    for (const it of spec.items) {
      const fn = PAINTERS[it.kind];
      if (!fn) throw new Error("no painter for " + it.kind);
      fn(g, em && em.g, it);
    }
    return { color: c.toDataURL("image/png"), emissive: em ? em.c.toDataURL("image/png") : null };
  };

  // --- full displays ------------------------------------------------------------------------------------------------
  const GREEN = "#43f26e", CYAN = "#46e3ff", YELLOW = "#ffe14a", WHITE = "#f2f2ea", RED = "#ff4a3d", MAGENTA = "#ff5cf0";

  function edgeLabels(g, S, labels, color = GREEN) {
    const px = S * 0.034;
    const at = (i) => ((i + 0.5) / 6) * S;
    (labels.top || []).forEach((t, i) => t && text(g, t, at(i), S * 0.03, px, { color }));
    (labels.bottom || []).forEach((t, i) => t && text(g, t, at(i), S * 0.97, px, { color }));
    (labels.left || []).forEach((t, i) => t && text(g, t, S * 0.012, at(i), px, { color, align: "left" }));
    (labels.right || []).forEach((t, i) => t && text(g, t, S * 0.988, at(i), px, { color, align: "right" }));
    // Selected-page cue, like the real thing: a box round one label.
    if (labels.boxed) {
      const [side, i] = labels.boxed;
      g.strokeStyle = color;
      g.lineWidth = 2;
      const w = S * 0.1, h = S * 0.045;
      const [bx, by] = side === "bottom" ? [at(i), S * 0.97] : side === "top" ? [at(i), S * 0.03] : side === "left" ? [S * 0.055, at(i)] : [S * 0.945, at(i)];
      g.strokeRect(bx - w / 2, by - h / 2, w, h);
    }
  }

  function strokeLine(g, pts, color, w, dash) {
    g.strokeStyle = color;
    g.lineWidth = w;
    g.setLineDash(dash || []);
    g.beginPath();
    pts.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y)));
    g.stroke();
    g.setLineDash([]);
  }

  function pageFLT(g, S) {
    const c = S / 2;
    // heading tape
    const hdg = 354;
    g.save();
    g.beginPath();
    g.rect(S * 0.18, S * 0.07, S * 0.64, S * 0.09);
    g.clip();
    for (let h0 = Math.floor((hdg - 40) / 5) * 5; h0 <= hdg + 40; h0 += 5) {
      const h = (h0 + 360) % 360;
      const x = c + (h0 - hdg) * S * 0.008;
      strokeLine(g, [[x, S * 0.15], [x, S * (h % 10 === 0 ? 0.125 : 0.137)]], GREEN, 2);
      if (h % 30 === 0) {
        const lbl = { 0: "N", 90: "E", 180: "S", 270: "W" }[h] || String(h / 10).padStart(2, "0");
        text(g, lbl, x, S * 0.1, S * 0.035, { color: GREEN });
      }
    }
    g.restore();
    g.fillStyle = "#000";
    g.fillRect(c - S * 0.045, S * 0.078, S * 0.09, S * 0.045);
    g.strokeStyle = GREEN;
    g.lineWidth = 2;
    g.strokeRect(c - S * 0.045, S * 0.078, S * 0.09, S * 0.045);
    text(g, String(hdg), c, S * 0.1, S * 0.036, { color: GREEN });
    // horizon and pitch ladder, banked a little
    g.save();
    g.translate(c, c * 1.02);
    g.rotate((-3 * Math.PI) / 180);
    g.beginPath();
    g.rect(-S * 0.33, -S * 0.3, S * 0.66, S * 0.56);
    g.clip();
    strokeLine(g, [[-S * 0.33, S * 0.02], [-S * 0.08, S * 0.02]], GREEN, 3);
    strokeLine(g, [[S * 0.08, S * 0.02], [S * 0.33, S * 0.02]], GREEN, 3);
    for (const p of [-20, -10, 10, 20]) {
      const y = S * 0.02 - p * S * 0.011;
      strokeLine(g, [[-S * 0.12, y + (p < 0 ? -8 : 8)], [-S * 0.12, y], [-S * 0.04, y]], GREEN, 2, p < 0 ? [8, 6] : null);
      strokeLine(g, [[S * 0.04, y], [S * 0.12, y], [S * 0.12, y + (p < 0 ? -8 : 8)]], GREEN, 2, p < 0 ? [8, 6] : null);
      text(g, String(Math.abs(p)), -S * 0.15, y, S * 0.03, { color: GREEN });
      text(g, String(Math.abs(p)), S * 0.15, y, S * 0.03, { color: GREEN });
    }
    g.restore();
    // aircraft reference
    strokeLine(g, [[c - S * 0.07, c], [c - S * 0.025, c], [c - S * 0.012, c + S * 0.02], [c, c], [c + S * 0.012, c + S * 0.02], [c + S * 0.025, c], [c + S * 0.07, c]], WHITE, 3);
    // flight path vector
    g.strokeStyle = GREEN;
    g.lineWidth = 2;
    g.beginPath();
    g.arc(c + S * 0.02, c + S * 0.035, S * 0.014, 0, Math.PI * 2);
    g.stroke();
    // airspeed / altitude boxes
    const boxT = (x, y, w, str, sub) => {
      g.fillStyle = "#000";
      g.fillRect(x, y, w, S * 0.055);
      g.strokeStyle = GREEN;
      g.lineWidth = 2;
      g.strokeRect(x, y, w, S * 0.055);
      text(g, str, x + w / 2, y + S * 0.028, S * 0.042, { color: GREEN, mono: true });
      if (sub) text(g, sub, x + w / 2, y + S * 0.075, S * 0.026, { color: GREEN });
    };
    boxT(S * 0.09, c - S * 0.03, S * 0.1, "112", "KTS");
    boxT(S * 0.8, c - S * 0.03, S * 0.12, "1850", "BARO");
    text(g, "R 145", S * 0.86, c + S * 0.12, S * 0.034, { color: GREEN, mono: true });
    // radar altitude bar
    strokeLine(g, [[S * 0.95, c - S * 0.2], [S * 0.95, c + S * 0.2]], GREEN, 2);
    for (let i = 0; i <= 8; i++) strokeLine(g, [[S * 0.94, c - S * 0.2 + i * S * 0.05], [S * 0.95, c - S * 0.2 + i * S * 0.05]], GREEN, 2);
    g.fillStyle = GREEN;
    g.fillRect(S * 0.952, c + S * 0.06, S * 0.012, S * 0.14);
    // vertical speed
    strokeLine(g, [[S * 0.215, c - S * 0.16], [S * 0.215, c + S * 0.16]], GREEN, 2);
    g.beginPath();
    g.moveTo(S * 0.22, c - S * 0.035);
    g.lineTo(S * 0.24, c - S * 0.045);
    g.lineTo(S * 0.24, c - S * 0.025);
    g.fill();
    // torque, rotor
    text(g, "74%", S * 0.1, S * 0.2, S * 0.042, { color: GREEN, mono: true, align: "left" });
    text(g, "TQ", S * 0.1, S * 0.245, S * 0.028, { color: GREEN, align: "left" });
    text(g, "NR 101%", S * 0.1, S * 0.73, S * 0.032, { color: GREEN, mono: true, align: "left" });
    // hover box and velocity vector
    g.strokeStyle = GREEN;
    g.setLineDash([6, 6]);
    g.strokeRect(c - S * 0.06, S * 0.7, S * 0.12, S * 0.12);
    g.setLineDash([]);
    strokeLine(g, [[c, S * 0.76], [c + S * 0.018, S * 0.715]], GREEN, 3);
    // slip ball
    g.strokeStyle = GREEN;
    g.strokeRect(c - S * 0.07, S * 0.87, S * 0.14, S * 0.03);
    g.beginPath();
    g.arc(c + S * 0.006, S * 0.885, S * 0.012, 0, Math.PI * 2);
    g.fillStyle = GREEN;
    g.fill();
    text(g, "14:32:05", S * 0.9, S * 0.2, S * 0.03, { color: GREEN, mono: true, align: "right" });
    text(g, "FUEL 2450", S * 0.9, S * 0.73, S * 0.03, { color: GREEN, mono: true, align: "right" });
  }

  function pageTSD(g, S) {
    const R = rng(42);
    // terrain: soft shaded relief and contours
    for (let i = 0; i < 26; i++) {
      const x = R() * S, y = R() * S, r = S * (0.05 + R() * 0.18);
      const rg = g.createRadialGradient(x, y, 0, x, y, r);
      rg.addColorStop(0, `rgba(${90 + R() * 40},${70 + R() * 30},${35},0.35)`);
      rg.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = rg;
      g.fillRect(x - r, y - r, r * 2, r * 2);
    }
    g.strokeStyle = "rgba(170,140,90,0.35)";
    g.lineWidth = 1.2;
    for (let i = 0; i < 14; i++) {
      const x = R() * S, y = R() * S;
      for (let k = 1; k <= 3; k++) {
        g.beginPath();
        g.ellipse(x, y, k * S * 0.03 * (1 + R()), k * S * 0.02 * (1 + R()), R() * 3, 0, Math.PI * 2);
        g.stroke();
      }
    }
    // river
    g.strokeStyle = "rgba(60,120,230,0.8)";
    g.lineWidth = 3;
    g.beginPath();
    g.moveTo(0, S * 0.62);
    g.bezierCurveTo(S * 0.25, S * 0.5, S * 0.45, S * 0.8, S * 0.7, S * 0.58);
    g.bezierCurveTo(S * 0.82, S * 0.48, S * 0.9, S * 0.52, S, S * 0.4);
    g.stroke();
    // grid
    g.strokeStyle = "rgba(120,120,120,0.25)";
    g.lineWidth = 1;
    for (let i = 1; i < 8; i++) {
      strokeLine(g, [[(i * S) / 8, 0], [(i * S) / 8, S]], "rgba(120,120,120,0.22)", 1);
      strokeLine(g, [[0, (i * S) / 8], [S, (i * S) / 8]], "rgba(120,120,120,0.22)", 1);
    }
    const own = [S * 0.5, S * 0.66];
    // range ring
    g.strokeStyle = WHITE;
    g.setLineDash([10, 8]);
    g.lineWidth = 1.5;
    g.beginPath();
    g.arc(own[0], own[1], S * 0.3, Math.PI * 1.02, Math.PI * 1.98);
    g.stroke();
    g.setLineDash([]);
    // route
    const wp = [[own[0], own[1]], [S * 0.46, S * 0.46], [S * 0.6, S * 0.3], [S * 0.5, S * 0.16], [S * 0.28, S * 0.12]];
    strokeLine(g, wp, MAGENTA, 3);
    wp.slice(1).forEach(([x, y], i) => {
      g.strokeStyle = WHITE;
      g.lineWidth = 2;
      g.beginPath();
      g.arc(x, y, S * 0.016, 0, Math.PI * 2);
      g.stroke();
      g.fillStyle = WHITE;
      g.fillRect(x - 2, y - 2, 4, 4);
      text(g, `W0${i + 1}`, x + S * 0.045, y - S * 0.02, S * 0.03, { color: WHITE });
    });
    // threats
    const threat = (x, y, r, name, col) => {
      g.strokeStyle = col;
      g.lineWidth = 2;
      g.setLineDash([6, 5]);
      g.beginPath();
      g.arc(x, y, r, 0, Math.PI * 2);
      g.stroke();
      g.setLineDash([]);
      text(g, name, x, y, S * 0.03, { color: col });
    };
    threat(S * 0.78, S * 0.22, S * 0.1, "ZSU", RED);
    threat(S * 0.2, S * 0.3, S * 0.14, "SA15", YELLOW);
    // targets
    for (const [x, y] of [[S * 0.7, S * 0.36], [S * 0.73, S * 0.39]]) {
      g.strokeStyle = RED;
      g.lineWidth = 2;
      g.beginPath();
      g.moveTo(x, y - 8);
      g.lineTo(x + 8, y);
      g.lineTo(x, y + 8);
      g.lineTo(x - 8, y);
      g.closePath();
      g.stroke();
    }
    // ownship
    g.fillStyle = WHITE;
    g.beginPath();
    g.moveTo(own[0], own[1] - S * 0.03);
    g.lineTo(own[0] + S * 0.012, own[1] + S * 0.01);
    g.lineTo(own[0], own[1] + S * 0.004);
    g.lineTo(own[0] - S * 0.012, own[1] + S * 0.01);
    g.closePath();
    g.fill();
    strokeLine(g, [[own[0] - S * 0.03, own[1] - S * 0.008], [own[0] + S * 0.03, own[1] - S * 0.008]], WHITE, 2);
    // north arrow + status
    text(g, "N", S * 0.92, S * 0.11, S * 0.04, { color: WHITE });
    strokeLine(g, [[S * 0.92, S * 0.2], [S * 0.92, S * 0.14]], WHITE, 2);
    text(g, "NAV", S * 0.08, S * 0.1, S * 0.032, { color: CYAN, align: "left" });
    text(g, "25 KM", S * 0.08, S * 0.88, S * 0.03, { color: CYAN, align: "left" });
    text(g, "W02 4.2KM 01:52", S * 0.92, S * 0.88, S * 0.028, { color: CYAN, align: "right", mono: true });
  }

  function pageWPN(g, S) {
    const c = S / 2;
    text(g, "WPN", c, S * 0.1, S * 0.045, { color: WHITE });
    // aircraft plan view
    strokeLine(g, [[c, S * 0.24], [c, S * 0.62]], GREEN, 4);
    strokeLine(g, [[c - S * 0.33, S * 0.44], [c + S * 0.33, S * 0.44]], GREEN, 4);
    g.strokeStyle = GREEN;
    g.lineWidth = 3;
    g.strokeRect(c - S * 0.03, S * 0.2, S * 0.06, S * 0.1);
    const pyl = [-0.29, -0.15, 0.15, 0.29];
    pyl.forEach((dx, i) => {
      const x = c + dx * S;
      const y = S * 0.5;
      if (i === 0 || i === 3) {
        // Hellfire rail: four rounds
        for (const [ox, oy] of [[-0.022, 0], [0.022, 0], [-0.022, 0.07], [0.022, 0.07]]) {
          g.strokeStyle = GREEN;
          g.lineWidth = 2;
          g.strokeRect(x + ox * S - S * 0.014, y + oy * S - S * 0.02, S * 0.028, S * 0.05);
          text(g, i === 0 ? "L" : "R", x + ox * S, y + oy * S + S * 0.005, S * 0.026, { color: GREEN });
        }
      } else {
        g.beginPath();
        g.arc(x, y + S * 0.035, S * 0.04, 0, Math.PI * 2);
        g.stroke();
        text(g, "19", x, y + S * 0.035, S * 0.03, { color: GREEN });
      }
    });
    text(g, "GUN  300", c, S * 0.17, S * 0.032, { color: GREEN, mono: true });
    text(g, "RKT  6PD", c, S * 0.68, S * 0.032, { color: GREEN, mono: true });
    text(g, "MSL  SAL SEL  PRI A  ALT B", c, S * 0.76, S * 0.032, { color: GREEN, mono: true });
    text(g, "LASER CODE A 1688", c, S * 0.81, S * 0.03, { color: GREEN, mono: true });
    g.strokeStyle = YELLOW;
    g.lineWidth = 2;
    g.strokeRect(c - S * 0.09, S * 0.855, S * 0.18, S * 0.05);
    text(g, "SAFE", c, S * 0.88, S * 0.036, { color: YELLOW });
  }

  function bar(g, x, y, w, h, frac, label, value, S) {
    g.strokeStyle = WHITE;
    g.lineWidth = 2;
    g.strokeRect(x, y, w, h);
    g.fillStyle = GREEN;
    g.fillRect(x + 2, y + h - (h - 4) * frac - 2, w - 4, (h - 4) * frac);
    strokeLine(g, [[x - 6, y + h * 0.12], [x + w + 6, y + h * 0.12]], RED, 3);
    text(g, label, x + w / 2, y + h + S * 0.035, S * 0.028, { color: WHITE });
    text(g, value, x + w / 2, y - S * 0.03, S * 0.03, { color: GREEN, mono: true });
  }

  function pageENG(g, S) {
    text(g, "ENG", S / 2, S * 0.1, S * 0.045, { color: WHITE });
    const top = S * 0.2, h = S * 0.36, w = S * 0.05;
    bar(g, S * 0.12, top, w, h, 0.62, "TQ1", "74", S);
    bar(g, S * 0.2, top, w, h, 0.63, "TQ2", "75", S);
    bar(g, S * 0.34, top, w, h, 0.71, "TGT1", "742", S);
    bar(g, S * 0.42, top, w, h, 0.7, "TGT2", "736", S);
    bar(g, S * 0.58, top, w, h, 0.8, "NP", "101", S);
    bar(g, S * 0.66, top, w, h, 0.8, "NR", "101", S);
    bar(g, S * 0.8, top, w, h, 0.77, "NG", "92.5", S);
    const rows = [
      ["OIL PSI", "62", "63"],
      ["HYD PRI", "3000", "UTIL 3010"],
      ["FUEL FWD", "1120", "AFT 1330"],
      ["TOTAL", "2450 LB", "ENDR 1:55"],
    ];
    rows.forEach(([a, b, c2], i) => {
      const y = S * 0.7 + i * S * 0.055;
      text(g, a, S * 0.12, y, S * 0.03, { color: WHITE, align: "left" });
      text(g, b, S * 0.48, y, S * 0.032, { color: GREEN, align: "right", mono: true });
      text(g, c2, S * 0.88, y, S * 0.032, { color: GREEN, align: "right", mono: true });
    });
  }

  function pageTEDAC(g, S) {
    const R = rng(9);
    // White-hot FLIR: cool sky, warmer ground, hot engines.
    const sky = g.createLinearGradient(0, 0, 0, S * 0.42);
    sky.addColorStop(0, "#1b1b1b");
    sky.addColorStop(1, "#3a3a3a");
    g.fillStyle = sky;
    g.fillRect(0, 0, S, S * 0.42);
    const gr = g.createLinearGradient(0, S * 0.42, 0, S);
    gr.addColorStop(0, "#5d5d5d");
    gr.addColorStop(1, "#7a7a7a");
    g.fillStyle = gr;
    g.fillRect(0, S * 0.42, S, S * 0.58);
    g.filter = "blur(3px)";
    for (let i = 0; i < 260; i++) {
      const y = S * 0.42 + Math.pow(R(), 1.5) * S * 0.58;
      const v = 70 + R() * 70;
      g.fillStyle = `rgba(${v},${v},${v},0.5)`;
      const w = S * (0.02 + R() * 0.12) * (0.5 + (y / S));
      g.fillRect(R() * S, y, w, w * 0.25);
    }
    // tree line along the horizon
    for (let x = 0; x < S; x += 6) {
      const h = S * (0.01 + R() * 0.035);
      const v = 110 + R() * 50;
      g.fillStyle = `rgb(${v},${v},${v})`;
      g.beginPath();
      g.ellipse(x, S * 0.425, 8 + R() * 8, h, 0, 0, Math.PI * 2);
      g.fill();
    }
    // a road
    g.strokeStyle = "rgba(150,150,150,0.8)";
    g.lineWidth = 7;
    g.beginPath();
    g.moveTo(S * 0.05, S);
    g.bezierCurveTo(S * 0.35, S * 0.7, S * 0.55, S * 0.55, S * 0.62, S * 0.43);
    g.stroke();
    g.filter = "none";
    // vehicles
    const tank = (x, y, sc) => {
      g.fillStyle = "#d8d8d8";
      g.fillRect(x - 22 * sc, y - 7 * sc, 44 * sc, 12 * sc);
      g.fillStyle = "#f4f4f4";
      g.fillRect(x - 10 * sc, y - 13 * sc, 18 * sc, 7 * sc);
      g.fillRect(x + 6 * sc, y - 11 * sc, 26 * sc, 3 * sc);
      g.fillStyle = "#ffffff";
      g.fillRect(x - 21 * sc, y - 6 * sc, 9 * sc, 8 * sc);
      g.fillStyle = "#9a9a9a";
      g.fillRect(x - 22 * sc, y + 4 * sc, 44 * sc, 4 * sc);
    };
    g.filter = "blur(1px)";
    tank(S * 0.5, S * 0.52, 1.4);
    tank(S * 0.66, S * 0.48, 0.9);
    tank(S * 0.36, S * 0.5, 1.0);
    g.filter = "none";
    // symbology
    const col = "#7dff8a";
    strokeLine(g, [[S / 2 - S * 0.16, S / 2], [S / 2 - S * 0.03, S / 2]], col, 2);
    strokeLine(g, [[S / 2 + S * 0.03, S / 2], [S / 2 + S * 0.16, S / 2]], col, 2);
    strokeLine(g, [[S / 2, S / 2 - S * 0.14], [S / 2, S / 2 - S * 0.03]], col, 2);
    strokeLine(g, [[S / 2, S / 2 + S * 0.03], [S / 2, S / 2 + S * 0.14]], col, 2);
    g.strokeStyle = col;
    g.lineWidth = 2;
    const gw = S * 0.09;
    for (const [sx, sy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
      strokeLine(g, [[S / 2 + sx * gw, S / 2 + sy * gw * 0.6], [S / 2 + sx * gw, S / 2 + sy * gw * 0.35]], col, 2);
      strokeLine(g, [[S / 2 + sx * gw, S / 2 + sy * gw * 0.6], [S / 2 + sx * gw * 0.7, S / 2 + sy * gw * 0.6]], col, 2);
    }
    text(g, "TADS  FLIR  WHT", S * 0.05, S * 0.06, S * 0.032, { color: col, align: "left" });
    text(g, "M", S * 0.95, S * 0.06, S * 0.036, { color: col, align: "right" });
    text(g, "ACQ TADS", S * 0.05, S * 0.93, S * 0.03, { color: col, align: "left" });
    text(g, "*3420", S * 0.95, S * 0.93, S * 0.036, { color: col, align: "right", mono: true });
    text(g, "LST  A", S * 0.95, S * 0.87, S * 0.03, { color: col, align: "right" });
    // azimuth / elevation scales
    strokeLine(g, [[S * 0.3, S * 0.13], [S * 0.7, S * 0.13]], col, 2);
    for (let i = 0; i <= 8; i++) strokeLine(g, [[S * 0.3 + (i * S * 0.4) / 8, S * 0.13], [S * 0.3 + (i * S * 0.4) / 8, S * (i % 4 === 0 ? 0.11 : 0.12)]], col, 2);
    g.fillStyle = col;
    g.fillRect(S * 0.53, S * 0.14, 6, 10);
    strokeLine(g, [[S * 0.9, S * 0.3], [S * 0.9, S * 0.7]], col, 2);
    for (let i = 0; i <= 8; i++) strokeLine(g, [[S * 0.9, S * 0.3 + (i * S * 0.4) / 8], [S * (i % 4 === 0 ? 0.92 : 0.91), S * 0.3 + (i * S * 0.4) / 8]], col, 2);
  }

  const PAGES = {
    FLT: { fn: pageFLT, labels: { top: ["", "HI", "LO", "", "SET", ""], left: ["", "", "ATT", "", "", ""], right: ["", "", "", "", "", ""], bottom: ["", "FLT", "", "", "", ""], boxed: ["bottom", 1] } },
    TSD: { fn: pageTSD, labels: { top: ["", "MAP", "SHOW", "", "UTIL", ""], left: ["", "RTE", "", "THRT", "", ""], right: ["", "", "CTR", "", "FRZ", ""], bottom: ["", "", "TSD", "", "", "ATK"], boxed: ["bottom", 2] }, color: CYAN },
    WPN: { fn: pageWPN, labels: { top: ["", "CHAN", "UTIL", "", "CODE", ""], left: ["", "GUN", "MSL", "RKT", "", "ATA"], right: ["", "TRAJ", "MODE", "LOAL", "", ""], bottom: ["", "", "", "WPN", "", ""], boxed: ["left", 2] } },
    ENG: { fn: pageENG, labels: { top: ["", "ENG", "", "SYS", "PERF", ""], left: ["", "", "", "", "", ""], right: ["", "", "", "", "", "WCA"], bottom: ["", "", "", "", "", ""], boxed: ["top", 1] } },
    TEDAC: { fn: pageTEDAC, labels: null },
  };

  window.paintScreen = (spec) => {
    const S = spec.size || 512;
    const { c, g } = canvas(S, S, "#000");
    const page = PAGES[spec.page];
    page.fn(g, S);
    if (page.labels) edgeLabels(g, S, page.labels, page.color || GREEN);
    // A trace of glass: slight vignette.
    const v = g.createRadialGradient(S / 2, S / 2, S * 0.35, S / 2, S / 2, S * 0.75);
    v.addColorStop(0, "rgba(0,0,0,0)");
    v.addColorStop(1, "rgba(0,0,0,0.35)");
    g.fillStyle = v;
    g.fillRect(0, 0, S, S);
    return c.toDataURL("image/png");
  };
})();
