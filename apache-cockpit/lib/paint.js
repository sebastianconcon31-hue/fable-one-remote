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
  // Every page draws from a data object (live values from a simulation, or the defaults below)
  // and a ui object (which edge labels are boxed, page options). The viewer repaints them live;
  // generate.mjs paints them once with the defaults.
  const GREEN = "#43f26e", CYAN = "#46e3ff", YELLOW = "#ffe14a", WHITE = "#f2f2ea", RED = "#ff4a3d", MAGENTA = "#ff5cf0", AMBER = "#ffc23d";

  const DEFAULTS = {
    hdg: 354, ias: 0, alt: 1150, ralt: 0, pitch: 0, roll: 0, vs: 0, slip: 0, vx: 0, vz: 0, tq: 18, nr: 101, fuel: 2450, time: "14:32:05", flt: "00:47",
    pos: [0, 0],
    eng: { tq: [18, 18], tgt: [612, 608], ng: [84.5, 84.7], np: [101, 101], nr: 101, oil: [62, 63], hyd: [3000, 3010], run: [true, true] },
    fuelTanks: { fwd: 1120, aft: 1330, boost: false, xfeed: "NORM", trans: "OFF", endurance: "1:55" },
    wpn: { arm: false, sel: "MSL", gun: 300, burst: 20, rkt: { LI: 19, RI: 19 }, msl: { LO: 4, RO: 4 }, gone: {}, code: "A 1688" },
    tsd: { scale: 25, ctr: false, frz: false, map: true },
    radios: [["VHF", "127.500", "TOWER"], ["UHF", "305.100", "GUARD"], ["FM1", "30.000", "BN CMD"], ["FM2", "51.500", "CO TAC"], ["HF", "3.050", ""]],
    rts: 0, iff: "M3 1200",
    wca: [],
    tedac: { power: "ON", sensor: "FLIR", flir: true, dtv: true, pol: "WHT", gain: 0.5, level: 0.5, fov: "M", az: 0, el: -1.5, range: 3420, lasing: false, laserArm: false, slaved: false, t: 0 },
    scratch: "",
    t: 0,
  };
  function withDefaults(d) {
    const out = { ...DEFAULTS, ...(d || {}) };
    for (const k of ["eng", "fuelTanks", "wpn", "tsd", "tedac"]) out[k] = { ...DEFAULTS[k], ...((d && d[k]) || {}) };
    return out;
  }

  // Edge labels: T1-T6 across the top, B1-B6 across the bottom, L1-L6 and R1-R6 down the sides.
  function edgeLabels(g, W, H, labels, color, boxed) {
    const px = H * 0.034;
    const atX = (i) => ((i + 0.5) / 6) * W;
    const atY = (i) => ((i + 0.5) / 6) * H;
    const put = (id, t, x, y, align) => {
      if (!t) return;
      text(g, t, x, y, px, { color, align });
      if (boxed && boxed.includes(id)) {
        g.font = font(px);
        const w = g.measureText(t).width + px * 0.8, h = px * 1.45;
        const bx = align === "left" ? x - px * 0.3 : align === "right" ? x - w + px * 0.3 : x - w / 2;
        g.strokeStyle = color;
        g.lineWidth = 2;
        g.strokeRect(bx, y - h / 2, w, h);
      }
    };
    (labels.top || []).forEach((t, i) => put(`T${i + 1}`, t, atX(i), H * 0.03, "center"));
    (labels.bottom || []).forEach((t, i) => put(`B${i + 1}`, t, atX(i), H * 0.97, "center"));
    (labels.left || []).forEach((t, i) => put(`L${i + 1}`, t, W * 0.014, atY(i), "left"));
    (labels.right || []).forEach((t, i) => put(`R${i + 1}`, t, W * 0.986, atY(i), "right"));
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
  const fmt = (v, n = 0) => (Math.round(v * 10 ** n) / 10 ** n).toFixed(n);
  const wrap360 = (a) => ((a % 360) + 360) % 360;

  function pageFLT(g, S, d) {
    const c = S / 2;
    // heading tape
    g.save();
    g.beginPath();
    g.rect(S * 0.18, S * 0.07, S * 0.64, S * 0.09);
    g.clip();
    for (let h0 = Math.floor((d.hdg - 40) / 5) * 5; h0 <= d.hdg + 40; h0 += 5) {
      const h = wrap360(h0);
      const x = c + (h0 - d.hdg) * S * 0.008;
      strokeLine(g, [[x, S * 0.15], [x, S * (h % 10 === 0 ? 0.125 : 0.137)]], GREEN, 2);
      if (h % 30 === 0) text(g, { 0: "N", 90: "E", 180: "S", 270: "W" }[h] || String(h / 10).padStart(2, "0"), x, S * 0.1, S * 0.035, { color: GREEN });
    }
    g.restore();
    g.fillStyle = "#000";
    g.fillRect(c - S * 0.045, S * 0.078, S * 0.09, S * 0.045);
    g.strokeStyle = GREEN;
    g.lineWidth = 2;
    g.strokeRect(c - S * 0.045, S * 0.078, S * 0.09, S * 0.045);
    text(g, String(Math.round(wrap360(d.hdg))).padStart(3, "0"), c, S * 0.1, S * 0.036, { color: GREEN });
    // horizon and pitch ladder
    g.save();
    g.beginPath();
    g.rect(S * 0.17, S * 0.2, S * 0.66, S * 0.56);
    g.clip();
    g.translate(c, c * 1.02);
    g.rotate((-d.roll * Math.PI) / 180);
    g.translate(0, d.pitch * S * 0.011);
    strokeLine(g, [[-S * 0.5, 0], [-S * 0.08, 0]], GREEN, 3);
    strokeLine(g, [[S * 0.08, 0], [S * 0.5, 0]], GREEN, 3);
    for (let p = -30; p <= 30; p += 10) {
      if (!p) continue;
      const y = -p * S * 0.011;
      strokeLine(g, [[-S * 0.12, y + (p < 0 ? -8 : 8)], [-S * 0.12, y], [-S * 0.04, y]], GREEN, 2, p < 0 ? [8, 6] : null);
      strokeLine(g, [[S * 0.04, y], [S * 0.12, y], [S * 0.12, y + (p < 0 ? -8 : 8)]], GREEN, 2, p < 0 ? [8, 6] : null);
      text(g, String(Math.abs(p)), -S * 0.15, y, S * 0.03, { color: GREEN });
      text(g, String(Math.abs(p)), S * 0.15, y, S * 0.03, { color: GREEN });
    }
    g.restore();
    strokeLine(g, [[c - S * 0.07, c], [c - S * 0.025, c], [c - S * 0.012, c + S * 0.02], [c, c], [c + S * 0.012, c + S * 0.02], [c + S * 0.025, c], [c + S * 0.07, c]], WHITE, 3);
    const boxT = (x, y, w, str, sub) => {
      g.fillStyle = "#000";
      g.fillRect(x, y, w, S * 0.055);
      g.strokeStyle = GREEN;
      g.lineWidth = 2;
      g.strokeRect(x, y, w, S * 0.055);
      text(g, str, x + w / 2, y + S * 0.028, S * 0.042, { color: GREEN, mono: true });
      if (sub) text(g, sub, x + w / 2, y + S * 0.075, S * 0.026, { color: GREEN });
    };
    boxT(S * 0.08, c - S * 0.03, S * 0.11, fmt(d.ias), "KTS");
    boxT(S * 0.8, c - S * 0.03, S * 0.13, fmt(d.alt), "BARO");
    text(g, "R " + fmt(d.ralt), S * 0.86, c + S * 0.12, S * 0.034, { color: GREEN, mono: true });
    // radar altitude bar (0-200 ft) and vertical speed (+-1000 fpm)
    strokeLine(g, [[S * 0.95, c - S * 0.2], [S * 0.95, c + S * 0.2]], GREEN, 2);
    for (let i = 0; i <= 8; i++) strokeLine(g, [[S * 0.94, c - S * 0.2 + i * S * 0.05], [S * 0.95, c - S * 0.2 + i * S * 0.05]], GREEN, 2);
    const rb = Math.max(0, Math.min(1, d.ralt / 200)) * S * 0.4;
    g.fillStyle = GREEN;
    g.fillRect(S * 0.952, c + S * 0.2 - rb, S * 0.012, rb);
    strokeLine(g, [[S * 0.215, c - S * 0.16], [S * 0.215, c + S * 0.16]], GREEN, 2);
    const vy = c - Math.max(-1, Math.min(1, d.vs / 1000)) * S * 0.16;
    g.beginPath();
    g.moveTo(S * 0.22, vy);
    g.lineTo(S * 0.24, vy - S * 0.012);
    g.lineTo(S * 0.24, vy + S * 0.012);
    g.fill();
    text(g, fmt(d.tq) + "%", S * 0.1, S * 0.2, S * 0.042, { color: d.tq > 100 ? YELLOW : GREEN, mono: true, align: "left" });
    text(g, "TQ", S * 0.1, S * 0.245, S * 0.028, { color: GREEN, align: "left" });
    text(g, "NR " + fmt(d.nr) + "%", S * 0.1, S * 0.73, S * 0.032, { color: d.nr < 95 && d.nr > 5 ? YELLOW : GREEN, mono: true, align: "left" });
    // hover box and velocity vector
    g.strokeStyle = GREEN;
    g.setLineDash([6, 6]);
    g.strokeRect(c - S * 0.06, S * 0.7, S * 0.12, S * 0.12);
    g.setLineDash([]);
    const k = S * 0.004;
    strokeLine(g, [[c, S * 0.76], [c + Math.max(-S * 0.1, Math.min(S * 0.1, -d.vx * k)), S * 0.76 - Math.max(-S * 0.1, Math.min(S * 0.1, d.vz * k))]], GREEN, 3);
    g.strokeStyle = GREEN;
    g.lineWidth = 2;
    g.strokeRect(c - S * 0.07, S * 0.87, S * 0.14, S * 0.03);
    g.beginPath();
    g.arc(c + Math.max(-1, Math.min(1, d.slip)) * S * 0.055, S * 0.885, S * 0.012, 0, Math.PI * 2);
    g.fillStyle = GREEN;
    g.fill();
    text(g, d.time, S * 0.9, S * 0.2, S * 0.03, { color: GREEN, mono: true, align: "right" });
    text(g, "FUEL " + fmt(d.fuel), S * 0.9, S * 0.73, S * 0.03, { color: d.fuel < 400 ? YELLOW : GREEN, mono: true, align: "right" });
  }

  // The map: fixed features in world metres (east = -X, north = +Z), drawn north up around the aircraft.
  let mapCache = null;
  function mapFeatures() {
    if (mapCache) return mapCache;
    const R = rng(42);
    const hills = [];
    for (let i = 0; i < 60; i++) hills.push([(R() - 0.5) * 60000, (R() - 0.5) * 60000, 1500 + R() * 5000, R() * 3, 0.6 + R() * 0.8]);
    const river = [];
    for (let i = -12; i <= 12; i++) river.push([i * 2500, 6000 + Math.sin(i * 0.7) * 3000 + (R() - 0.5) * 800]);
    mapCache = {
      hills, river,
      route: [[0, 0], [2000, 6500], [-1500, 12000], [2500, 17000], [8000, 19500]],
      threats: [[-9000, 15000, 5000, "ZSU", RED], [11000, 8000, 7000, "SA15", YELLOW]],
      targets: [[-3200, 16800], [-3500, 17200]],
    };
    return mapCache;
  }

  function pageTSD(g, S, d) {
    const f = mapFeatures();
    const range = d.tsd.scale * 1000; // metres from ownship to the top edge
    const own = d.tsd.ctr ? [S / 2, S / 2] : [S / 2, S * 0.66];
    const ppm = (own[1] - S * 0.06) / range;
    const [ox, oz] = d.pos;
    const P = (wx, wz) => [own[0] + (-(wx - ox)) * ppm, own[1] - (wz - oz) * ppm];
    if (d.tsd.map) {
      for (const [hx, hz, r, a, e] of f.hills) {
        const [x, y] = P(hx, hz);
        const rp = r * ppm;
        if (x < -rp || x > S + rp || y < -rp || y > S + rp) continue;
        const rg = g.createRadialGradient(x, y, 0, x, y, rp);
        rg.addColorStop(0, "rgba(120,92,48,0.4)");
        rg.addColorStop(1, "rgba(0,0,0,0)");
        g.fillStyle = rg;
        g.fillRect(x - rp, y - rp, rp * 2, rp * 2);
        g.strokeStyle = "rgba(170,140,90,0.35)";
        g.lineWidth = 1.2;
        for (let k = 1; k <= 3; k++) {
          g.beginPath();
          g.ellipse(x, y, (rp * k) / 3.2, (rp * k * e) / 3.2, a, 0, Math.PI * 2);
          g.stroke();
        }
      }
      strokeLine(g, f.river.map(([x, z]) => P(x, z)), "rgba(60,120,230,0.85)", 3);
    }
    const step = d.tsd.scale >= 50 ? 10000 : d.tsd.scale >= 25 ? 5000 : 2000;
    for (let gx = Math.floor((ox - range * 1.5) / step) * step; gx < ox + range * 1.5; gx += step) strokeLine(g, [P(gx, oz - range * 2), P(gx, oz + range * 2)], "rgba(120,120,120,0.22)", 1);
    for (let gz = Math.floor((oz - range * 1.5) / step) * step; gz < oz + range * 1.5; gz += step) strokeLine(g, [P(ox - range * 2, gz), P(ox + range * 2, gz)], "rgba(120,120,120,0.22)", 1);
    g.strokeStyle = WHITE;
    g.setLineDash([10, 8]);
    g.lineWidth = 1.5;
    g.beginPath();
    g.arc(own[0], own[1], (own[1] - S * 0.06) * 0.5, 0, Math.PI * 2);
    g.stroke();
    g.setLineDash([]);
    strokeLine(g, f.route.map(([x, z]) => P(x, z)), MAGENTA, 3);
    f.route.slice(1).forEach(([wx, wz], i) => {
      const [x, y] = P(wx, wz);
      g.strokeStyle = WHITE;
      g.lineWidth = 2;
      g.beginPath();
      g.arc(x, y, S * 0.016, 0, Math.PI * 2);
      g.stroke();
      text(g, `W0${i + 1}`, x + S * 0.045, y - S * 0.02, S * 0.03, { color: WHITE });
    });
    for (const [tx, tz, r, name, col] of f.threats) {
      const [x, y] = P(tx, tz);
      g.strokeStyle = col;
      g.lineWidth = 2;
      g.setLineDash([6, 5]);
      g.beginPath();
      g.arc(x, y, r * ppm, 0, Math.PI * 2);
      g.stroke();
      g.setLineDash([]);
      text(g, name, x, y, S * 0.03, { color: col });
    }
    for (const [tx, tz] of f.targets) {
      const [x, y] = P(tx, tz);
      strokeLine(g, [[x, y - 8], [x + 8, y], [x, y + 8], [x - 8, y], [x, y - 8]], RED, 2);
    }
    // ownship, pointing along the heading
    g.save();
    g.translate(own[0], own[1]);
    g.rotate((d.hdg * Math.PI) / 180);
    g.fillStyle = WHITE;
    g.beginPath();
    g.moveTo(0, -S * 0.03);
    g.lineTo(S * 0.012, S * 0.01);
    g.lineTo(0, S * 0.004);
    g.lineTo(-S * 0.012, S * 0.01);
    g.closePath();
    g.fill();
    strokeLine(g, [[-S * 0.03, -S * 0.008], [S * 0.03, -S * 0.008]], WHITE, 2);
    g.restore();
    text(g, "N", S * 0.92, S * 0.11, S * 0.04, { color: WHITE });
    strokeLine(g, [[S * 0.92, S * 0.2], [S * 0.92, S * 0.14]], WHITE, 2);
    text(g, d.tsd.frz ? "FRZ" : "NAV", S * 0.08, S * 0.1, S * 0.032, { color: CYAN, align: "left" });
    text(g, `${d.tsd.scale} KM`, S * 0.08, S * 0.88, S * 0.03, { color: CYAN, align: "left" });
    const wp = f.route[1];
    const dist = Math.hypot(wp[0] - ox, wp[1] - oz) / 1000;
    text(g, `W01 ${fmt(dist, 1)}KM`, S * 0.92, S * 0.88, S * 0.028, { color: CYAN, align: "right", mono: true });
  }

  function pageWPN(g, S, d) {
    const c = S / 2, w = d.wpn;
    text(g, "WPN", c, S * 0.1, S * 0.045, { color: WHITE });
    strokeLine(g, [[c, S * 0.24], [c, S * 0.62]], GREEN, 4);
    strokeLine(g, [[c - S * 0.33, S * 0.44], [c + S * 0.33, S * 0.44]], GREEN, 4);
    g.strokeStyle = GREEN;
    g.lineWidth = 3;
    g.strokeRect(c - S * 0.03, S * 0.2, S * 0.06, S * 0.1);
    // stations, as the crew sees them: left wing on the left
    const st = [["LO", -0.29, "msl"], ["LI", -0.15, "rkt"], ["RI", 0.15, "rkt"], ["RO", 0.29, "msl"]];
    for (const [id, dx, kind] of st) {
      const x = c + dx * S, y = S * 0.5;
      if (w.gone[id]) {
        text(g, "JETT", x, y + S * 0.03, S * 0.028, { color: YELLOW });
        continue;
      }
      if (kind === "msl") {
        const n = w.msl[id] ?? 0;
        [[-0.022, 0], [0.022, 0], [-0.022, 0.07], [0.022, 0.07]].forEach(([ox, oy], i) => {
          g.strokeStyle = GREEN;
          g.lineWidth = 2;
          if (i < n) {
            g.strokeRect(x + ox * S - S * 0.014, y + oy * S - S * 0.02, S * 0.028, S * 0.05);
            text(g, id[0], x + ox * S, y + oy * S + S * 0.005, S * 0.026, { color: GREEN });
          }
        });
      } else {
        g.strokeStyle = GREEN;
        g.lineWidth = 2;
        g.beginPath();
        g.arc(x, y + S * 0.035, S * 0.04, 0, Math.PI * 2);
        g.stroke();
        text(g, String(w.rkt[id] ?? 0), x, y + S * 0.035, S * 0.03, { color: GREEN });
      }
    }
    const sel = { GUN: `GUN  ${w.gun}  BURST ${w.burst}`, RKT: `RKT  ${(w.rkt.LI ?? 0) + (w.rkt.RI ?? 0)}`, MSL: `MSL  ${(w.msl.LO ?? 0) + (w.msl.RO ?? 0)}  SAL`, NONE: "NO WEAPON" }[w.sel];
    text(g, `GUN  ${w.gun}`, c, S * 0.17, S * 0.032, { color: GREEN, mono: true });
    text(g, sel, c, S * 0.7, S * 0.034, { color: WHITE, mono: true });
    text(g, "LASER CODE " + w.code, c, S * 0.77, S * 0.03, { color: GREEN, mono: true });
    const col = w.arm ? RED : YELLOW;
    g.strokeStyle = col;
    g.lineWidth = 2;
    g.strokeRect(c - S * 0.09, S * 0.83, S * 0.18, S * 0.05);
    text(g, w.arm ? "ARM" : "SAFE", c, S * 0.855, S * 0.036, { color: col });
  }

  function bar(g, x, y, w, h, frac, label, value, S, redAt = 0.12) {
    g.strokeStyle = WHITE;
    g.lineWidth = 2;
    g.strokeRect(x, y, w, h);
    const f = Math.max(0, Math.min(1, frac));
    g.fillStyle = f > 1 - redAt ? YELLOW : GREEN;
    g.fillRect(x + 2, y + h - (h - 4) * f - 2, w - 4, (h - 4) * f);
    strokeLine(g, [[x - 6, y + h * redAt], [x + w + 6, y + h * redAt]], RED, 3);
    text(g, label, x + w / 2, y + h + S * 0.035, S * 0.028, { color: WHITE });
    text(g, value, x + w / 2, y - S * 0.03, S * 0.03, { color: GREEN, mono: true });
  }

  function pageENG(g, S, d) {
    const e = d.eng;
    text(g, "ENG", S / 2, S * 0.1, S * 0.045, { color: WHITE });
    const top = S * 0.2, h = S * 0.36, w = S * 0.05;
    bar(g, S * 0.12, top, w, h, e.tq[0] / 120, "TQ1", fmt(e.tq[0]), S);
    bar(g, S * 0.2, top, w, h, e.tq[1] / 120, "TQ2", fmt(e.tq[1]), S);
    bar(g, S * 0.34, top, w, h, e.tgt[0] / 1000, "TGT1", fmt(e.tgt[0]), S);
    bar(g, S * 0.42, top, w, h, e.tgt[1] / 1000, "TGT2", fmt(e.tgt[1]), S);
    bar(g, S * 0.58, top, w, h, e.np[0] / 125, "NP", fmt(e.np[0]), S);
    bar(g, S * 0.66, top, w, h, e.nr / 125, "NR", fmt(e.nr), S);
    bar(g, S * 0.8, top, w, h, Math.max(e.ng[0], e.ng[1]) / 110, "NG", `${fmt(e.ng[0])}/${fmt(e.ng[1])}`, S);
    const rows = [
      ["OIL PSI", fmt(e.oil[0]), fmt(e.oil[1])],
      ["HYD PRI", fmt(e.hyd[0]), "UTIL " + fmt(e.hyd[1])],
      ["ENG 1/2", e.run[0] ? "RUN" : "OUT", e.run[1] ? "RUN" : "OUT"],
      ["FUEL", fmt(d.fuel) + " LB", "ENDR " + d.fuelTanks.endurance],
    ];
    rows.forEach(([a, b, c2], i) => {
      const y = S * 0.7 + i * S * 0.055;
      text(g, a, S * 0.12, y, S * 0.03, { color: WHITE, align: "left" });
      text(g, b, S * 0.48, y, S * 0.032, { color: b === "OUT" ? YELLOW : GREEN, align: "right", mono: true });
      text(g, c2, S * 0.88, y, S * 0.032, { color: c2 === "OUT" ? YELLOW : GREEN, align: "right", mono: true });
    });
  }

  function pageFUEL(g, S, d) {
    const f = d.fuelTanks;
    text(g, "FUEL", S / 2, S * 0.1, S * 0.045, { color: WHITE });
    const tank = (x, name, lb, max) => {
      g.strokeStyle = WHITE;
      g.lineWidth = 2;
      g.strokeRect(x, S * 0.25, S * 0.26, S * 0.34);
      const fr = Math.max(0, Math.min(1, lb / max));
      g.fillStyle = "rgba(67,242,110,0.35)";
      g.fillRect(x + 2, S * 0.25 + S * 0.34 * (1 - fr), S * 0.26 - 4, S * 0.34 * fr - 2);
      text(g, name, x + S * 0.13, S * 0.22, S * 0.032, { color: WHITE });
      text(g, fmt(lb), x + S * 0.13, S * 0.42, S * 0.045, { color: GREEN, mono: true });
    };
    tank(S * 0.14, "FWD", f.fwd, 1600);
    tank(S * 0.6, "AFT", f.aft, 2200);
    strokeLine(g, [[S * 0.4, S * 0.42], [S * 0.6, S * 0.42]], f.trans !== "OFF" ? CYAN : "rgba(242,242,234,0.4)", 3, f.trans !== "OFF" ? null : [6, 6]);
    if (f.trans !== "OFF") text(g, f.trans === "FWD" ? "<<" : ">>", S / 2, S * 0.39, S * 0.03, { color: CYAN });
    const rows = [["TOTAL", fmt(d.fuel) + " LB"], ["BOOST", f.boost ? "ON" : "OFF"], ["XFEED", f.xfeed], ["TRANSFER", f.trans], ["ENDURANCE", f.endurance]];
    rows.forEach(([a, b], i) => {
      const y = S * 0.68 + i * S * 0.05;
      text(g, a, S * 0.2, y, S * 0.03, { color: WHITE, align: "left" });
      text(g, b, S * 0.8, y, S * 0.032, { color: GREEN, align: "right", mono: true });
    });
  }

  function pageFCR(g, S, d) {
    const c = [S / 2, S * 0.86];
    const R = S * 0.7;
    g.strokeStyle = "rgba(67,242,110,0.6)";
    g.lineWidth = 1.5;
    for (const k of [0.25, 0.5, 0.75, 1]) {
      g.beginPath();
      g.arc(c[0], c[1], R * k, Math.PI * 1.25, Math.PI * 1.75);
      g.stroke();
    }
    strokeLine(g, [c, [c[0] + Math.cos(Math.PI * 1.25) * R, c[1] + Math.sin(Math.PI * 1.25) * R]], "rgba(67,242,110,0.6)", 1.5);
    strokeLine(g, [c, [c[0] + Math.cos(Math.PI * 1.75) * R, c[1] + Math.sin(Math.PI * 1.75) * R]], "rgba(67,242,110,0.6)", 1.5);
    const sweep = Math.PI * 1.25 + (0.5 + 0.5 * Math.sin(d.t * 1.1)) * Math.PI * 0.5;
    strokeLine(g, [c, [c[0] + Math.cos(sweep) * R, c[1] + Math.sin(sweep) * R]], GREEN, 3);
    const tg = [[0.55, -0.1, "T"], [0.62, -0.06, "T"], [0.4, 0.22, "W"], [0.8, 0.15, "U"], [0.3, -0.3, "A"]];
    tg.forEach(([r, a, s], i) => {
      const ang = Math.PI * 1.5 + a;
      const x = c[0] + Math.cos(ang) * R * r, y = c[1] + Math.sin(ang) * R * r;
      g.strokeStyle = i === 0 ? YELLOW : GREEN;
      g.lineWidth = 2;
      g.strokeRect(x - 9, y - 9, 18, 18);
      text(g, s, x, y, S * 0.028, { color: i === 0 ? YELLOW : GREEN });
    });
    text(g, "GTM  SGL  8 KM", S * 0.5, S * 0.12, S * 0.034, { color: GREEN });
    text(g, "NTS: T01", S * 0.08, S * 0.2, S * 0.03, { color: YELLOW, align: "left" });
  }

  function pageCOM(g, S, d) {
    text(g, "COM", S / 2, S * 0.1, S * 0.045, { color: WHITE });
    d.radios.forEach(([n, f, name], i) => {
      const y = ((i + 0.5) / 6) * S;
      const on = i === d.rts;
      text(g, (on ? "* " : "  ") + n, S * 0.14, y, S * 0.036, { color: on ? WHITE : GREEN, align: "left", mono: true });
      text(g, f, S * 0.5, y, S * 0.04, { color: GREEN, mono: true });
      text(g, name, S * 0.84, y, S * 0.03, { color: CYAN, align: "right" });
    });
    text(g, "IFF " + d.iff, S / 2, S * 0.92, S * 0.03, { color: GREEN, mono: true });
  }

  function menuGrid(g, S, title, items) {
    text(g, title, S / 2, S * 0.1, S * 0.05, { color: WHITE });
    g.strokeStyle = "rgba(67,242,110,0.35)";
    g.lineWidth = 1.5;
    g.strokeRect(S * 0.2, S * 0.2, S * 0.6, S * 0.6);
    items.forEach((t, i) => text(g, t, S / 2, S * 0.28 + i * S * 0.07, S * 0.034, { color: GREEN }));
  }

  // The FLIR / TV scene: a wide panorama painted once, then panned and zoomed.
  const panoCache = {};
  function panorama(S, dtv) {
    const key = S + (dtv ? "d" : "f");
    if (panoCache[key]) return panoCache[key];
    const W = S * 4, H = Math.round(S * 1.5), hz = S * 0.5;
    const { c, g } = canvas(W, H);
    const R = rng(dtv ? 11 : 9);
    const sky = g.createLinearGradient(0, 0, 0, hz);
    sky.addColorStop(0, dtv ? "#6d97c7" : "#1b1b1b");
    sky.addColorStop(1, dtv ? "#c9d7df" : "#3a3a3a");
    g.fillStyle = sky;
    g.fillRect(0, 0, W, hz);
    const gr = g.createLinearGradient(0, hz, 0, H);
    gr.addColorStop(0, dtv ? "#6f7a52" : "#5d5d5d");
    gr.addColorStop(1, dtv ? "#56603f" : "#7a7a7a");
    g.fillStyle = gr;
    g.fillRect(0, hz, W, H - hz);
    for (let i = 0; i < 1100; i++) {
      const y = hz + Math.pow(R(), 1.5) * (H - hz);
      const v = 70 + R() * 70;
      g.fillStyle = dtv ? `rgba(${60 + R() * 60},${70 + R() * 50},${40 + R() * 20},0.45)` : `rgba(${v},${v},${v},0.5)`;
      const w = S * (0.02 + R() * 0.12) * (0.5 + (y - hz) / S);
      g.fillRect(R() * W, y, w, w * 0.25);
    }
    for (let x = 0; x < W; x += 6) {
      const h = S * (0.01 + R() * 0.035);
      const v = 110 + R() * 50;
      g.fillStyle = dtv ? `rgb(${40 + R() * 30},${60 + R() * 30},${35})` : `rgb(${v},${v},${v})`;
      g.beginPath();
      g.ellipse(x, hz + 2, 8 + R() * 8, h, 0, 0, Math.PI * 2);
      g.fill();
    }
    g.strokeStyle = dtv ? "rgba(150,140,120,0.9)" : "rgba(150,150,150,0.8)";
    g.lineWidth = 7;
    g.beginPath();
    g.moveTo(W * 0.3, H);
    g.bezierCurveTo(W * 0.42, H * 0.75, W * 0.48, H * 0.55, W * 0.52, hz + 4);
    g.stroke();
    // one soft blur over the whole scene (a blur per shape is far too slow)
    const soft = canvas(W, H).c;
    const sg = soft.getContext("2d");
    sg.filter = "blur(3px)";
    sg.drawImage(c, 0, 0);
    g.clearRect(0, 0, W, H);
    g.drawImage(soft, 0, 0);
    const tank = (x, y, sc) => {
      g.fillStyle = dtv ? "#4c513b" : "#d8d8d8";
      g.fillRect(x - 22 * sc, y - 7 * sc, 44 * sc, 12 * sc);
      g.fillStyle = dtv ? "#3f4431" : "#f4f4f4";
      g.fillRect(x - 10 * sc, y - 13 * sc, 18 * sc, 7 * sc);
      g.fillRect(x + 6 * sc, y - 11 * sc, 26 * sc, 3 * sc);
      if (!dtv) {
        g.fillStyle = "#ffffff";
        g.fillRect(x - 21 * sc, y - 6 * sc, 9 * sc, 8 * sc);
      }
      g.fillStyle = dtv ? "#2a2c22" : "#9a9a9a";
      g.fillRect(x - 22 * sc, y + 4 * sc, 44 * sc, 4 * sc);
    };
    const ppd = W / 90;
    // targets at azimuths near 0, a degree or two below the horizon
    for (const [az, el, sc] of [[0, -1.5, 0.8], [2.1, -1.2, 0.55], [-1.8, -1.35, 0.6], [11, -2.5, 0.9], [-14, -3, 1.0]]) tank(W / 2 + az * ppd, hz - el * ppd, sc);
    panoCache[key] = { c, W, H, hz, ppd };
    return panoCache[key];
  }

  function tedacImage(g, W, H, d, sym = true) {
    const t = d.tedac;
    g.fillStyle = "#000";
    g.fillRect(0, 0, W, H);
    if (t.power === "OFF") return;
    const col = "#7dff8a";
    if (t.power === "STBY") {
      text(g, "TADS STBY", W / 2, H / 2, H * 0.05, { color: col });
      return;
    }
    const dtv = t.sensor === "DTV";
    if ((dtv && !t.dtv) || (!dtv && !t.flir)) {
      text(g, (dtv ? "DTV" : "FLIR") + " OFF", W / 2, H / 2, H * 0.05, { color: col });
      return;
    }
    const p = panorama(512, dtv);
    const zoom = { W: 1, M: 2.2, N: 5 }[t.fov] || 2.2;
    const sw = 512 / zoom, sh = (512 / zoom) * (H / W);
    let sx = p.W / 2 + t.az * p.ppd - sw / 2;
    let sy = p.hz - t.el * p.ppd - sh / 2;
    sx = Math.max(0, Math.min(p.W - sw, sx));
    sy = Math.max(0, Math.min(p.H - sh, sy));
    g.save();
    const f = [];
    if (!dtv) {
      f.push(`contrast(${(0.4 + t.gain * 1.6).toFixed(2)})`, `brightness(${(0.55 + t.level * 0.9).toFixed(2)})`);
      if (t.pol === "BLK") f.push("invert(1)");
    }
    g.filter = f.length ? f.join(" ") : "none";
    g.drawImage(p.c, sx, sy, sw, sh, 0, 0, W, H);
    g.restore();
    if (!sym) return;
    const cx = W / 2, cy = H / 2, s = Math.min(W, H);
    strokeLine(g, [[cx - s * 0.16, cy], [cx - s * 0.03, cy]], col, 2);
    strokeLine(g, [[cx + s * 0.03, cy], [cx + s * 0.16, cy]], col, 2);
    strokeLine(g, [[cx, cy - s * 0.14], [cx, cy - s * 0.03]], col, 2);
    strokeLine(g, [[cx, cy + s * 0.03], [cx, cy + s * 0.14]], col, 2);
    const gw = s * 0.09;
    for (const [qx, qy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
      strokeLine(g, [[cx + qx * gw, cy + qy * gw * 0.6], [cx + qx * gw, cy + qy * gw * 0.35]], col, 2);
      strokeLine(g, [[cx + qx * gw, cy + qy * gw * 0.6], [cx + qx * gw * 0.7, cy + qy * gw * 0.6]], col, 2);
    }
    text(g, `TADS  ${dtv ? "DTV" : "FLIR " + t.pol}`, W * 0.05, H * 0.06, s * 0.032, { color: col, align: "left" });
    text(g, t.fov, W * 0.95, H * 0.06, s * 0.036, { color: col, align: "right" });
    text(g, t.slaved ? "SLAVED" : "ACQ TADS", W * 0.05, H * 0.93, s * 0.03, { color: col, align: "left" });
    if (t.range) text(g, (t.lasing ? "*" : "") + Math.round(t.range), W * 0.95, H * 0.93, s * 0.036, { color: col, align: "right", mono: true });
    text(g, t.laserArm ? "LST  A" : "LASER SAFE", W * 0.95, H * 0.87, s * 0.03, { color: col, align: "right" });
    if (t.lasing && Math.floor(d.t * 4) % 2 === 0) text(g, "LRFD", W / 2, H * 0.22, s * 0.04, { color: col });
    // azimuth and elevation scales, with the sight's position on them
    strokeLine(g, [[W * 0.3, H * 0.13], [W * 0.7, H * 0.13]], col, 2);
    for (let i = 0; i <= 8; i++) strokeLine(g, [[W * 0.3 + (i * W * 0.4) / 8, H * 0.13], [W * 0.3 + (i * W * 0.4) / 8, H * (i % 4 === 0 ? 0.11 : 0.12)]], col, 2);
    g.fillStyle = col;
    g.fillRect(W * 0.5 + (t.az / 120) * W * 0.4 - 3, H * 0.14, 6, 10);
    strokeLine(g, [[W * 0.9, H * 0.3], [W * 0.9, H * 0.7]], col, 2);
    for (let i = 0; i <= 8; i++) strokeLine(g, [[W * 0.9, H * 0.3 + (i * H * 0.4) / 8], [W * (i % 4 === 0 ? 0.92 : 0.91), H * 0.3 + (i * H * 0.4) / 8]], col, 2);
    g.fillRect(W * 0.87, H * 0.5 - (t.el / 60) * H * 0.4 - 3, 10, 6);
  }

  function pageTEDAC(g, S, d) {
    tedacImage(g, S, S, d, true);
  }
  function pageVID(g, S, d) {
    tedacImage(g, S, S, d, true);
  }

  function pageEUFD(g, W, H, d) {
    g.fillStyle = "#020402";
    g.fillRect(0, 0, W, H);
    const rows = 7, lh = H / rows, px = lh * 0.72;
    const put = (t, x, row, col = "#9dff6e", inverse = false) => {
      if (inverse) {
        g.font = font(px, { mono: true, bold: false });
        const w = g.measureText(t).width;
        g.fillStyle = col;
        g.fillRect(x - 3, row * lh + 3, w + 6, lh - 6);
        text(g, t, x, (row + 0.5) * lh, px, { mono: true, bold: false, align: "left", color: "#020402" });
      } else text(g, t, x, (row + 0.5) * lh, px, { mono: true, bold: false, align: "left", color: col });
    };
    const wca = d.wca.slice(0, 5);
    wca.forEach((m, i) => put(m.text, 10, i, m.level === "A" ? "#6fbf5a" : "#b8ff8a", m.level === "W"));
    put(`FUEL ${fmt(d.fuel)} LB`, 10, 5);
    put(`${d.time}Z`, 10, 6);
    d.radios.forEach(([n, f], i) => put(`${i === d.rts ? "*" : " "}${n.padEnd(4)}${f.padStart(8)}`, W * 0.53, i));
    put(`IFF ${d.iff}`, W * 0.53, 5);
    put(`FLT ${d.flt}`, W * 0.53, 6);
    g.fillStyle = "rgba(0,0,0,0.18)";
    for (let y = 0; y < H; y += 3) g.fillRect(0, y, W, 1);
  }

  function pageKU(g, W, H, d) {
    g.fillStyle = "#050300";
    g.fillRect(0, 0, W, H);
    const cursor = Math.floor(d.t * 2) % 2 === 0 ? "_" : " ";
    text(g, (d.scratch || "") + cursor, 10, H / 2, H * 0.62, { mono: true, bold: false, align: "left", color: AMBER });
  }

  function pageADI(g, S, d) {
    const c = S / 2, R = S / 2;
    g.fillStyle = "#0b0b0b";
    g.fillRect(0, 0, S, S);
    g.save();
    g.beginPath();
    g.arc(c, c, R * 0.98, 0, Math.PI * 2);
    g.clip();
    g.translate(c, c);
    g.rotate((-d.roll * Math.PI) / 180);
    const k = R * 0.022; // pixels per degree of pitch
    g.translate(0, d.pitch * k);
    g.fillStyle = "#3f78b5";
    g.fillRect(-S, -S * 2, S * 2, S * 2);
    g.fillStyle = "#5b3a1f";
    g.fillRect(-S, 0, S * 2, S * 2);
    g.strokeStyle = "#f4f4ee";
    g.lineWidth = R * 0.03;
    g.beginPath();
    g.moveTo(-R, 0);
    g.lineTo(R, 0);
    g.stroke();
    for (let p = -60; p <= 60; p += 5) {
      if (!p) continue;
      const y = -p * k;
      const hw = R * (p % 10 === 0 ? (Math.abs(p) === 10 ? 0.28 : 0.4) : 0.12);
      g.lineWidth = R * (p % 10 === 0 ? 0.02 : 0.015);
      g.beginPath();
      g.moveTo(-hw, y);
      g.lineTo(hw, y);
      g.stroke();
      if (p % 10 === 0) {
        text(g, String(Math.abs(p)), -hw - R * 0.1, y, R * 0.11, { color: "#f4f4ee" });
        text(g, String(Math.abs(p)), hw + R * 0.1, y, R * 0.11, { color: "#f4f4ee" });
      }
    }
    g.restore();
    // fixed roll scale on the case
    g.strokeStyle = "#f4f4ee";
    for (const deg of [-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60]) {
      const a = ((deg - 90) * Math.PI) / 180;
      g.lineWidth = R * 0.025;
      g.beginPath();
      g.moveTo(c + Math.cos(a) * R * 0.82, c + Math.sin(a) * R * 0.82);
      g.lineTo(c + Math.cos(a) * R * (deg % 30 === 0 ? 0.96 : 0.9), c + Math.sin(a) * R * (deg % 30 === 0 ? 0.96 : 0.9));
      g.stroke();
    }
  }

  function pageCOMPASS(g, W, H, d) {
    g.fillStyle = "#101010";
    g.fillRect(0, 0, W, H);
    const labels = { 0: "N", 90: "E", 180: "S", 270: "W" };
    const span = 60, cx = W / 2;
    g.strokeStyle = "#f4f4ee";
    for (let h0 = Math.floor((d.hdg - span) / 5) * 5; h0 <= d.hdg + span; h0 += 5) {
      const x = cx + ((h0 - d.hdg) / span) * W * 0.5;
      const h = wrap360(h0);
      g.lineWidth = 2;
      g.beginPath();
      g.moveTo(x, H * 0.62);
      g.lineTo(x, H * (h % 10 === 0 ? 0.42 : 0.52));
      g.stroke();
      if (h % 30 === 0) text(g, labels[h] || String(h / 10), x, H * 0.24, H * 0.26, { color: "#f4f4ee" });
    }
    g.strokeStyle = "#e0a020";
    g.lineWidth = 3;
    g.beginPath();
    g.moveTo(cx, H * 0.05);
    g.lineTo(cx, H * 0.95);
    g.stroke();
  }

  // Page definitions: painter, edge labels, and which labels lead to other pages.
  const MENU_ITEMS = ["FLT", "TSD", "WPN", "FCR", "ENG", "FUEL", "VID", "COM", "A/C"];
  const PAGES = {
    FLT: { fn: pageFLT, labels: { top: ["", "HI", "LO", "", "SET", ""], left: ["", "", "ATT", "", "", ""], bottom: ["", "FLT", "", "", "", ""] } },
    TSD: { fn: pageTSD, color: CYAN, labels: { top: ["", "MAP", "SHOW", "", "UTIL", ""], left: ["", "RTE", "", "THRT", "", ""], right: ["", "", "CTR", "", "FRZ", ""], bottom: ["", "", "TSD", "SCALE", "", "ATK"] } },
    WPN: { fn: pageWPN, labels: { top: ["", "CHAN", "UTIL", "", "CODE", ""], left: ["", "GUN", "MSL", "RKT", "", "ATA"], right: ["", "TRAJ", "MODE", "LOAL", "", ""], bottom: ["", "", "", "WPN", "", ""] } },
    ENG: { fn: pageENG, labels: { top: ["", "ENG", "FUEL", "SYS", "PERF", ""], right: ["", "", "", "", "", "WCA"] }, nav: { T3: "FUEL" } },
    FUEL: { fn: pageFUEL, labels: { top: ["", "ENG", "FUEL", "", "", ""], left: ["", "BOOST", "", "", "", ""], right: ["", "XFEED", "", "", "", ""] }, nav: { T2: "ENG" } },
    FCR: { fn: pageFCR, labels: { top: ["", "GTM", "RMAP", "ATM", "TPM", ""], left: ["", "SCAN", "", "", "", ""], bottom: ["", "", "FCR", "", "", ""] } },
    VID: { fn: pageVID, labels: { top: ["", "TADS", "PNVS", "", "", ""], bottom: ["", "", "", "VID", "", ""] } },
    COM: { fn: pageCOM, labels: { left: ["VHF", "UHF", "FM1", "FM2", "HF", ""], bottom: ["", "", "", "", "COM", ""] } },
    AC: { fn: (g, S) => menuGrid(g, S, "A/C", ["ENG", "FLT", "FUEL", "PERF", "UTIL"]), labels: { top: ["", "ENG", "FLT", "FUEL", "PERF", "UTIL"], bottom: ["", "", "", "", "", "A/C"] }, nav: { T2: "ENG", T3: "FLT", T4: "FUEL" } },
    MENU: { fn: (g, S) => menuGrid(g, S, "MENU", MENU_ITEMS), labels: { left: ["FLT", "TSD", "WPN", "FCR", "ENG", "FUEL"], right: ["VID", "COM", "A/C", "", "", ""] }, nav: { L1: "FLT", L2: "TSD", L3: "WPN", L4: "FCR", L5: "ENG", L6: "FUEL", R1: "VID", R2: "COM", R3: "AC" } },
    TEDAC: { fn: pageTEDAC, labels: { left: ["W", "M", "N", "", "", ""], right: ["FLIR", "DTV", "", "", "", ""] }, color: "#7dff8a" },
    EUFD: { fn: pageEUFD, wide: true },
    KU: { fn: pageKU, wide: true },
    ADI: { fn: pageADI },
    COMPASS: { fn: pageCOMPASS, wide: true },
  };

  // Paint a page into a canvas. opts: { mode: "DAY" | "NT" | "MONO", contrast }
  function drawScreen(cv, page, data, ui = {}, opts = {}) {
    const g = cv.getContext("2d");
    const W = cv.width, H = cv.height;
    const d = withDefaults(data);
    const P = PAGES[page];
    g.save();
    g.fillStyle = "#000";
    g.fillRect(0, 0, W, H);
    if (P.wide) P.fn(g, W, H, d, ui);
    else P.fn(g, W, d, ui);
    if (P.labels) edgeLabels(g, W, H, P.labels, P.color || GREEN, ui.boxed || []);
    if (!P.wide && page !== "ADI") {
      const v = g.createRadialGradient(W / 2, H / 2, W * 0.35, W / 2, H / 2, W * 0.75);
      v.addColorStop(0, "rgba(0,0,0,0)");
      v.addColorStop(1, "rgba(0,0,0,0.35)");
      g.fillStyle = v;
      g.fillRect(0, 0, W, H);
    }
    if (opts.contrast && Math.abs(opts.contrast - 1) > 0.01) {
      const tmp = canvas(W, H).c;
      tmp.getContext("2d").drawImage(cv, 0, 0);
      g.filter = `contrast(${opts.contrast})`;
      g.drawImage(tmp, 0, 0);
      g.filter = "none";
    }
    if (opts.mode === "MONO") {
      g.globalCompositeOperation = "saturation";
      g.fillStyle = "#000";
      g.fillRect(0, 0, W, H);
      g.globalCompositeOperation = "multiply";
      g.fillStyle = "#6dff84";
      g.fillRect(0, 0, W, H);
    } else if (opts.mode === "NT") {
      g.globalCompositeOperation = "multiply";
      g.fillStyle = "#8a8a8a";
      g.fillRect(0, 0, W, H);
    }
    g.restore();
  }

  window.CockpitPaint = { drawScreen, PAGES, DEFAULTS, MENU_ITEMS };
  window.paintScreen = (spec) => {
    const { c } = canvas(spec.w || spec.size || 512, spec.h || spec.size || 512);
    drawScreen(c, spec.page, spec.data, spec.ui || {}, {});
    return c.toDataURL("image/png");
  };
})();
