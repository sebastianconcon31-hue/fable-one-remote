// Cockpit parts: materials, textured panels and their switches, displays,
// gauges, seats and flight controls. Each builder takes the build context,
// a parent Node and a Frame, and adds geometry in world space.
import { v3, Frame, Material, quad, poly, box, lathe, cyl, rod, sphere, rbox, bezel, ribbon, tube, bezier, extrude } from "./geo.mjs";

export const deg = Math.PI / 180;

export function materials() {
  const m = (name, o) => new Material(name, o);
  return {
    paint: m("Interior_Paint", { color: "#353a3d", rough: 0.78 }),
    dark: m("Interior_Black", { color: "#1a1c1e", rough: 0.86 }),
    floor: m("Floor_Nonslip", { color: "#25282a", rough: 0.96 }),
    frame: m("Canopy_Frame", { color: "#2b2f31", rough: 0.62 }),
    glass: m("Canopy_Glass", { color: "#c4d6e2", alpha: 0.13, rough: 0.04, blend: true, doubleSided: true }),
    metal: m("Metal", { color: "#9ea1a4", metal: 1, rough: 0.34 }),
    darkMetal: m("Metal_Dark", { color: "#4a4e52", metal: 0.85, rough: 0.45 }),
    rubber: m("Rubber", { color: "#151515", rough: 0.93 }),
    plastic: m("Plastic_Black", { color: "#1f2021", rough: 0.55 }),
    cushion: m("Seat_Cushion", { color: "#4c5042", rough: 0.96 }),
    armor: m("Seat_Armor", { color: "#5f625a", rough: 0.58 }),
    webbing: m("Harness", { color: "#6b6545", rough: 0.9 }),
    red: m("Paint_Red", { color: "#a3211b", rough: 0.5 }),
    panels: m("Panels", { color: "#ffffff", rough: 0.72, map: "panels", emissiveMap: "panels_emissive", emissive: "#86b881" }),
    displays: m("Displays", { color: "#404040", rough: 0.28, map: "displays", emissiveMap: "displays", emissive: "#ffffff" }),
    ext: m("Exterior_Paint", { color: "#40463a", rough: 0.72 }),
    extDark: m("Exterior_Dark", { color: "#24281f", rough: 0.7 }),
    sensor: m("Sensor_Glass", { color: "#17202a", metal: 0.4, rough: 0.07 }),
    rotor: m("Rotor_Blade", { color: "#2d2e2c", rough: 0.6 }),
  };
}

export function makeCtx(pa, da) {
  return { M: materials(), pa, da, seed: 1, regions: new Map(), screens: [], screenMats: new Map() };
}

// A named patch of an atlas, allocated once. lit: the display atlas (self-lit).
export function region(ctx, lit, key, wpx, hpx, item) {
  const k = (lit ? "D:" : "P:") + key;
  if (!ctx.regions.has(k)) ctx.regions.set(k, (lit ? ctx.da : ctx.pa).alloc(wpx, hpx, item).uv);
  return ctx.regions.get(k);
}
export const whiteUV = (ctx) => region(ctx, false, "white", 8, 8, { kind: "fill", color: "#f2f2ea", emissive: "#cfd6c8" });
export const darkUV = (ctx) => region(ctx, false, "dark", 8, 8, { kind: "fill", color: "#161718" });
export const darkLitUV = (ctx) => region(ctx, true, "dark", 8, 8, { kind: "fill", color: "#111111" });
export const orangeUV = (ctx) => region(ctx, false, "orange", 8, 8, { kind: "fill", color: "#f08a17", emissive: "#7a4208" });
export const hazardUV = (ctx) => region(ctx, false, "hazard", 96, 48, { kind: "hazard" });
const allFaces = (uv) => ({ pz: uv, nz: uv, px: uv, nx: uv, py: uv, ny: uv });

// A key cap legend. Lit ones go on the display atlas and glow.
export function capUV(ctx, text, w, h, o = {}) {
  const ppm = o.ppm || 5200;
  const key = `cap:${text}|${w}|${h}|${o.fg}|${o.bg}|${o.glowColor}|${o.fill}`;
  return region(ctx, !!o.lit, key, w * ppm, h * ppm, { kind: "cap", text, fg: o.fg, bg: o.bg, glow: o.lit, glowColor: o.glowColor, fill: o.fill });
}

export function screenMaterial(ctx, name, page) {
  if (!ctx.screenMats.has(name)) {
    const key = "screen_" + name;
    ctx.screens.push({ key, page });
    ctx.screenMats.set(name, new Material("Screen_" + name, { color: "#262626", rough: 0.22, map: key, emissiveMap: key, emissive: "#ffffff" }));
  }
  return ctx.screenMats.get(name);
}

// Frame whose local +Y runs along `F`'s normal: for knobs and nuts on a panel.
const outOf = (F) => Frame.upAlong(F.o, F.z, F.x);

// ---- panels ------------------------------------------------------------------------------------------------------------
// spec: { w, h, title, ctl: [...], ppm, holes, bg, textSize }
// ctl entries are placed from the panel's top-left, in metres (y down):
//   { k: "toggle", x, y, label, pos: ["ON","OFF"], state: 1 | 0 | -1, guard }
//   { k: "knob", x, y, r, label, stops: [...], sel, style: "bar" }
//   { k: "pb", x, y, w, h, text, lit, fg, bg, label }
//   { k: "tee", x, y, label }    a striped pull handle
//   { k: "label" | "box" | "slot" | "hazard" | "grille" | "screw", ... }   painted only
export function panel(ctx, node, F, spec) {
  const ppm = spec.ppm || 2000;
  const paintCtl = (spec.ctl || []).map((c) => ({ ...c }));
  const r = ctx.pa.alloc(spec.w * ppm, spec.h * ppm, {
    kind: "panel", m: [spec.w, spec.h], title: spec.title, ctl: paintCtl, holes: spec.holes, seed: ctx.seed++, bg: spec.bg, fasteners: spec.fasteners, textSize: spec.textSize, titleY: spec.titleY,
  });
  quad(node.g(ctx.M.panels), F, spec.w, spec.h, { uv: r.uv });
  box(node.g(ctx.M.dark), F.move(0, 0, -0.003), [spec.w, spec.h, 0.0059], { skip: "pz" });
  for (const c of spec.ctl || []) control(ctx, node, F, spec, c);
  return r;
}

function control(ctx, node, F, spec, c) {
  const P = F.move(-spec.w / 2 + c.x, spec.h / 2 - c.y, 0);
  switch (c.k) {
    case "toggle":
      toggle(ctx, node, P, c.state ?? (c.pos && c.pos.length === 3 ? 0 : 1), c.guard);
      break;
    case "knob":
      knob(ctx, node, P, c);
      break;
    case "pb":
      pushButton(ctx, node, P, c);
      break;
    case "tee":
      teeHandle(ctx, node, P);
      break;
  }
}

export function toggle(ctx, node, P, state, guard) {
  const M = ctx.M;
  const ax = outOf(P);
  cyl(node.g(M.metal), ax.move(0, 0.0015, 0), 0.0045, 0.003, 6);
  cyl(node.g(M.metal), ax.move(0, 0.0045, 0), 0.0027, 0.003, 10, { capBottom: false });
  const a = state * 26 * deg;
  const dir = v3.add(v3.mul(P.z, Math.cos(a)), v3.mul(P.y, Math.sin(a)));
  const base = P.point([0, 0, 0.0055]);
  const tip = v3.add(base, v3.mul(dir, 0.0155));
  rod(node.g(M.metal), base, tip, 0.0014, 8, { r2: 0.001, capBottom: false });
  sphere(node.g(M.metal), Frame.at(tip), 0.0021, 8);
  if (guard) {
    // A red guard, lifted.
    const G = P.move(0, 0.0105, 0.0085).rotX(-70 * deg);
    box(node.g(M.red), G, [0.014, 0.017, 0.0016]);
    box(node.g(M.red), P.move(0.0068, 0.003, 0.004), [0.0014, 0.012, 0.008]);
    box(node.g(M.red), P.move(-0.0068, 0.003, 0.004), [0.0014, 0.012, 0.008]);
  }
}

export function knob(ctx, node, P, c) {
  const M = ctx.M;
  const r = c.r || 0.007;
  const ax = outOf(P);
  cyl(node.g(M.plastic), ax.move(0, 0.001, 0), r * 1.14, 0.002, 20);
  const stops = c.stops || [];
  const span = (c.span ?? 270) * deg;
  const sel = c.sel ?? (stops.length ? Math.floor((stops.length - 1) / 2) : 0);
  const ang = stops.length > 1 ? -span / 2 + (span * sel) / (stops.length - 1) : (c.angle ?? 0) * deg;
  const d = [Math.sin(ang), Math.cos(ang)];
  const dirW = P.dir([d[0], d[1], 0]);
  if (c.style === "bar") {
    cyl(node.g(M.plastic), ax.move(0, 0.004, 0), r * 0.55, 0.006, 12);
    const B = Frame.facing(P.point([0, 0, 0.0085]), P.z, dirW);
    rbox(node.g(M.plastic), B, [r * 0.62, r * 2.3, 0.0085], 0.0015, 2);
    quad(node.g(M.panels), Frame.facing(P.point([d[0] * r * 0.55, d[1] * r * 0.55, 0.01279]), P.z, dirW), 0.0011, r * 0.9, { uv: whiteUV(ctx) });
  } else {
    const h = c.tall ? 0.017 : 0.012;
    lathe(node.g(M.plastic), ax, [[0, 0.002], [r * 0.84, 0.002], [r * 0.8, h], [r * 0.66, h + 0.0015], [0, h + 0.0015]], 16);
    quad(node.g(M.panels), Frame.facing(P.point([d[0] * r * 0.38, d[1] * r * 0.38, h + 0.0016]), P.z, dirW), 0.0011, r * 0.62, { uv: whiteUV(ctx) });
  }
}

export function pushButton(ctx, node, P, c) {
  const M = ctx.M;
  const w = c.w || 0.012, h = c.h || 0.012;
  const lit = !!c.lit;
  const uv = c.text != null ? capUV(ctx, c.text, w, h, { lit, fg: c.fg, bg: c.bg, glowColor: c.glowColor, fill: c.fill }) : lit ? darkLitUV(ctx) : darkUV(ctx);
  const side = lit ? darkLitUV(ctx) : darkUV(ctx);
  box(node.g(lit ? M.displays : M.panels), P.move(0, 0, c.depth ?? 0.0045), [w, h, 0.005], { uv, uvs: { nz: side, px: side, nx: side, py: side, ny: side } });
  bezel(node.g(M.plastic), P.move(0, 0, 0.0018), w + 0.0036, h + 0.0036, w + 0.0006, h + 0.0006, 0.0036, { r: 0.0012, ri: 0.0004, seg: 2 });
}

export function teeHandle(ctx, node, P) {
  const M = ctx.M;
  rod(node.g(M.metal), P.point([0, 0, 0]), P.point([0, 0, 0.022]), 0.0035, 10);
  box(node.g(M.panels), P.move(0, 0, 0.027), [0.05, 0.013, 0.011], { uv: hazardUV(ctx), uvs: allFaces(hazardUV(ctx)) });
}

// A block of keys. keys: [{ x, y, w, h, text }] in the frame's plane (metres from centre, y up).
function keys(ctx, node, F, list, o = {}) {
  for (const k of list) {
    const P = F.move(k.x, k.y, 0);
    const uv = k.text ? capUV(ctx, k.text, k.w, k.h, { fg: o.fg, bg: o.bg, fill: o.fill }) : darkUV(ctx);
    box(node.g(ctx.M.panels), P.move(0, 0, (o.depth ?? 0.005) / 2), [k.w, k.h, o.depth ?? 0.005], { uv, uvs: { nz: darkUV(ctx), px: darkUV(ctx), nx: darkUV(ctx), py: darkUV(ctx), ny: darkUV(ctx) } });
  }
}

// ---- multipurpose display (MPD) -------------------------------------------------------------------------------------------
// F: the panel surface at the display's centre, +Z toward the crew.
export function mpd(ctx, parent, F, name, page) {
  const M = ctx.M;
  const node = parent.child(name, F);
  const W = 0.25, H = 0.27, D = 0.034, S = 0.2, OFF = 0.012;
  box(node.g(M.dark), F.move(0, 0, (D - 0.004) / 2), [W - 0.004, H - 0.004, D - 0.004], { skip: "pz" });
  const faceCtl = [
    { k: "label", x: 0.022, y: 0.0045, text: "BRT", size: 0.0034 },
    { k: "label", x: W - 0.022, y: 0.0045, text: "VID", size: 0.0034 },
    { k: "label", x: 0.013, y: H - 0.0045, text: "DAY NT MONO", size: 0.0026, align: "left" },
    { k: "label", x: W - 0.013, y: H - 0.0045, text: "MENU", size: 0.003, align: "right" },
  ];
  const faceUV = region(ctx, false, "mpd-face", W * 1500, H * 1500, { kind: "panel", m: [W, H], ctl: faceCtl, fasteners: false, bg: "#25282a", seed: 3 });
  bezel(node.g(M.panels), F.move(0, 0, D - 0.002), W, H, S + 0.006, S + 0.006, 0.004, { r: 0.01, ri: 0.002, uv: faceUV, off: [0, OFF] });
  const scr = node.child(name + "_Screen", F.move(0, OFF, D - 0.0062), { screen: page, size_m: [S, S], note: "UV 0-1; swap the material's texture for a live render target" });
  quad(scr.g(screenMaterial(ctx, name, page)), scr.frame, S + 0.01, S + 0.01, { uv: [0, 0, 1, 1] });
  const btn = [];
  const along = (i) => ((i + 0.5) / 6) * S - S / 2;
  const Fk = F.move(0, 0, D);
  for (let i = 0; i < 6; i++) {
    btn.push({ x: along(i), y: OFF + S / 2 + 0.0105, w: 0.017, h: 0.0105 });
    btn.push({ x: along(i), y: OFF - S / 2 - 0.0105, w: 0.017, h: 0.0105 });
    btn.push({ x: -S / 2 - 0.0105, y: OFF + along(i), w: 0.0105, h: 0.017 });
    btn.push({ x: S / 2 + 0.0105, y: OFF + along(i), w: 0.0105, h: 0.017 });
  }
  keys(ctx, node, Fk, btn, { depth: 0.0055 });
  const fab = ["FCR", "WPN", "TSD", "VID", "COM", "A/C"].map((t, i) => ({ x: -0.08 + i * 0.032, y: -H / 2 + 0.0125, w: 0.025, h: 0.0115, text: t }));
  fab.push({ x: W / 2 - 0.013, y: -H / 2 + 0.0125, w: 0.017, h: 0.0115, text: "M" });
  keys(ctx, node, Fk, fab, { depth: 0.0055 });
  // Brightness and video rockers, and the mode knob.
  for (const sx of [-1, 1]) {
    const R = Fk.move(sx * (W / 2 - 0.013), H / 2 - 0.018, 0.003);
    rbox(node.g(M.plastic), R, [0.011, 0.022, 0.006], 0.002, 2);
    rbox(node.g(M.plastic), R.move(0, 0.0055, 0.003).rotX(-12 * deg), [0.009, 0.008, 0.003], 0.001, 1);
  }
  knob(ctx, node, Fk.move(-W / 2 + 0.013, -H / 2 + 0.0125, -0.001), { r: 0.0055 });
  return node;
}

// ---- up-front display (EUFD) and keyboard unit (KU) ---------------------------------------------------------------------------
export function eufd(ctx, parent, F, name, lines) {
  const M = ctx.M;
  const node = parent.child(name, F);
  const W = 0.2, H = 0.1, D = 0.026;
  const WW = 0.14, WH = 0.058, off = [0.004, 0.006];
  box(node.g(M.dark), F.move(0, 0, (D - 0.004) / 2), [W - 0.004, H - 0.004, D - 0.004], { skip: "pz" });
  const ctl = [
    { k: "label", x: 0.012, y: 0.012, text: "WCA", size: 0.0028 },
    { k: "label", x: 0.012, y: 0.042, text: "IDM", size: 0.0028 },
    { k: "label", x: 0.012, y: 0.072, text: "RTS", size: 0.0028 },
    { k: "label", x: W / 2 + off[0], y: H - 0.0105, text: "STBY     PRESET     ENTER     SWAP", size: 0.0028 },
    { k: "label", x: W - 0.01, y: 0.006, text: "BRT", size: 0.0026 },
  ];
  const face = ctx.pa.alloc(W * 2000, H * 2000, { kind: "panel", m: [W, H], ctl, fasteners: false, bg: "#25282a", seed: ctx.seed++ });
  bezel(node.g(M.panels), F.move(0, 0, D - 0.002), W, H, WW, WH, 0.004, { r: 0.006, ri: 0.0015, uv: face.uv, off });
  const disp = region(ctx, true, "eufd:" + name, WW * 5200, WH * 5200, { kind: "text", lines, pad: 10, rows: 7, size: 0.8, color: "#9dff6e" });
  quad(node.g(M.displays), F.move(off[0], off[1], D - 0.006), WW + 0.004, WH + 0.004, { uv: disp });
  const Fk = F.move(0, 0, D);
  const k = [];
  for (let i = 0; i < 3; i++) k.push({ x: -W / 2 + 0.012, y: H / 2 - 0.02 - i * 0.03, w: 0.009, h: 0.02 });
  for (let i = 0; i < 4; i++) k.push({ x: -0.045 + i * 0.033 + off[0], y: -H / 2 + 0.0065, w: 0.018, h: 0.0075 });
  for (let i = 0; i < 3; i++) k.push({ x: W / 2 - 0.012, y: H / 2 - 0.028 - i * 0.026, w: 0.009, h: 0.016 });
  keys(ctx, node, Fk, k, { depth: 0.005 });
  knob(ctx, node, Fk.move(W / 2 - 0.01, H / 2 - 0.013, -0.001), { r: 0.0045 });
  return node;
}

export function keyboard(ctx, parent, F, name, scratch) {
  const M = ctx.M;
  const node = parent.child(name, F);
  const W = 0.19, H = 0.118, D = 0.018;
  box(node.g(M.dark), F.move(0, 0, D / 2 - 0.002), [W, H, D - 0.004], { skip: "pz" });
  const face = ctx.pa.alloc(W * 1600, H * 1600, { kind: "panel", m: [W, H], ctl: [{ k: "label", x: W - 0.012, y: H - 0.0045, text: "KU", size: 0.003 }], fasteners: false, bg: "#25282a", seed: ctx.seed++ });
  const padW = 0.15, padH = 0.016, padY = H / 2 - 0.013;
  bezel(node.g(M.panels), F.move(0, 0, D - 0.004), W, H, padW, padH, 0.004, { r: 0.006, ri: 0.001, uv: face.uv, off: [0, padY] });
  const disp = region(ctx, true, "ku:" + name, padW * 5200, padH * 5200, { kind: "text", lines: [scratch], pad: 6, rows: 1, size: 0.82, color: "#ffc23d" });
  quad(node.g(M.displays), F.move(0, padY, D - 0.0065), padW + 0.003, padH + 0.003, { uv: disp });
  const rows = [
    ["A", "B", "C", "D", "E", "F", "1", "2", "3"],
    ["G", "H", "I", "J", "K", "L", "4", "5", "6"],
    ["M", "N", "O", "P", "Q", "R", "7", "8", "9"],
    ["S", "T", "U", "V", "W", "X", ".", "0", "/"],
    ["Y", "Z", "SPC", "BKS", "CLR", "ENT", "+", "-", "*"],
  ];
  const list = [];
  rows.forEach((row, r) => {
    row.forEach((t, c) => {
      const x = -0.0795 + c * 0.0182 + (c >= 6 ? 0.0055 : 0);
      list.push({ x, y: padY - 0.0205 - r * 0.0168, w: 0.0148, h: 0.0118, text: t });
    });
  });
  keys(ctx, node, F.move(0, 0, D - 0.004), list, { depth: 0.006 });
  return node;
}

// ---- standby instruments ---------------------------------------------------------------------------------------------------------
// F at the instrument's centre on the panel face. Needles and the ADI ball are their own nodes, pivoted, so they can be driven.
export function gauge(ctx, parent, F, name, type, d) {
  const M = ctx.M;
  const node = parent.child(name, F);
  const plate = d + 0.016;
  // mounting plate, the face just in front of it, needles, then bezel and glass
  rbox(node.g(M.plastic), F.move(0, 0, 0.003), [plate, plate, 0.006], 0.003, 2);
  const ax = outOf(F);
  lathe(node.g(M.plastic), ax, [[d / 2, 0.006], [d / 2 + 0.0035, 0.006], [d / 2 + 0.0035, 0.0095], [d / 2 + 0.001, 0.0108], [d / 2, 0.0108]], 32);
  const circle = (r, n = 40) => [...Array(n)].map((_, i) => [Math.cos((i / n) * Math.PI * 2) * r, Math.sin((i / n) * Math.PI * 2) * r]);
  const faceUV = region(ctx, false, "gauge:" + type, 256, 256, { kind: "gauge", type });
  const faceNode = type === "ADI" ? node.child(name + "_Ball", F, { drive: "roll about local Z (and pitch by UV scroll)" }) : node;
  poly(faceNode.g(M.panels), F.move(0, 0, 0.0064), circle(d / 2 + 0.0005), { uv: faceUV });
  if (type === "ADI") {
    const o = orangeUV(ctx);
    box(node.g(M.panels), F.move(-d * 0.2, -0.001, 0.0084), [d * 0.22, 0.0022, 0.0012], { uv: o, uvs: allFaces(o) });
    box(node.g(M.panels), F.move(d * 0.2, -0.001, 0.0084), [d * 0.22, 0.0022, 0.0012], { uv: o, uvs: allFaces(o) });
    box(node.g(M.panels), F.move(0, -0.001, 0.0084), [0.003, 0.003, 0.0012], { uv: o, uvs: allFaces(o) });
    poly(node.g(M.panels), F.move(0, d * 0.34, 0.0084), [[0, 0.004], [-0.003, -0.002], [0.003, -0.002]], { uv: o });
  } else if (type === "ASI" || type === "ALT" || type === "CLOCK") {
    // Airspeed and altitude needles rest at zero (12 o'clock) so they can be driven with absolute angles.
    const hands = type === "ALT" ? [[0.43, 0.0016, 0], [0.26, 0.0028, 0]] : type === "CLOCK" ? [[0.4, 0.0014, 0.2], [0.28, 0.0022, 2.1]] : [[0.4, 0.0018, 0]];
    hands.forEach(([len, w, rot], i) => {
      const nd = node.child(`${name}_Needle${hands.length > 1 ? i + 1 : ""}`, F.move(0, 0, 0.0074 + i * 0.0005).rotZ(-rot), { drive: "rotate about local Z; clockwise is negative" });
      quad(nd.g(M.panels), nd.frame.move(0, (len * d) / 2 - 0.004, 0), w, len * d + 0.006, { uv: whiteUV(ctx) });
    });
    cyl(node.g(M.plastic), ax.move(0, 0.0086, 0), 0.0026, 0.001, 12);
  }
  poly(node.g(M.glass), F.move(0, 0, 0.0105), circle(d / 2 + 0.001, 32));
  return node;
}

// ---- armoured crew seat -------------------------------------------------------------------------------------------------------------
// srp: the seat reference point - on the floor, centred, at the seat back.
export function seat(ctx, parent, name, srp) {
  const M = ctx.M;
  const S = Frame.at(srp);
  const node = parent.child(name, S);
  const at = (x, y, z) => S.point([x, y, z]);
  // bucket and base
  box(node.g(M.darkMetal), S.move(0, 0.12, 0.2), [0.34, 0.03, 0.36]);
  for (const sx of [-1, 1]) {
    box(node.g(M.darkMetal), S.move(sx * 0.15, 0.06, 0.2), [0.03, 0.12, 0.4]);
    box(node.g(M.metal), S.move(sx * 0.15, 0.012, 0.2), [0.045, 0.024, 0.46]);
  }
  box(node.g(M.armor), S.move(0, 0.24, 0.22), [0.43, 0.14, 0.46]);
  rbox(node.g(M.cushion), S.move(0, 0.33, 0.235), [0.39, 0.075, 0.43], 0.03, 3);
  // back: armoured shell, cushion, head pad
  const back = S.move(0, 0.34, -0.02).rotX(-12 * deg);
  box(node.g(M.armor), back.move(0, 0.36, -0.035), [0.45, 0.8, 0.045]);
  rbox(node.g(M.cushion), back.move(0, 0.31, 0.03), [0.38, 0.58, 0.075], 0.03, 3);
  rbox(node.g(M.cushion), back.move(0, 0.71, 0.025), [0.24, 0.14, 0.06], 0.025, 3);
  // side armour wings
  const wing = [[-0.07, 0.17], [0.44, 0.17], [0.44, 0.33], [0.26, 0.44], [0.12, 0.95], [-0.09, 1.02]];
  for (const sx of [-1, 1]) {
    const W = new Frame(at(sx * 0.226, 0, 0), [0, 0, 1], [0, 1, 0], [-1, 0, 0]);
    extrude(node.g(M.armor), W, wing, 0.026);
  }
  // energy absorbers behind the back
  for (const sx of [-1, 1]) {
    rod(node.g(M.metal), at(sx * 0.17, 0.05, -0.12), at(sx * 0.17, 0.95, -0.2), 0.022, 12);
    rod(node.g(M.darkMetal), at(sx * 0.17, 0.35, -0.13), at(sx * 0.17, 0.75, -0.18), 0.03, 12);
  }
  // harness: shoulder straps over the back cushion, lap belts, crotch strap, rotary buckle
  const buckle = at(0, 0.382, 0.3);
  const onBack = () => back.dir([0, 0, 1]);
  for (const sx of [-1, 1]) {
    const path = bezier([at(sx * 0.09, 1.02, -0.07), at(sx * 0.085, 0.99, 0.03), at(sx * 0.07, 0.62, 0.1), at(sx * 0.05, 0.42, 0.12), at(sx * 0.02, 0.39, 0.27)], 14);
    ribbon(node.g(M.webbing), path, 0.045, 0.004, (p, i) => (i < 11 ? onBack(p) : [0, 1, 0]));
    const lap = bezier([at(sx * 0.22, 0.34, 0.06), at(sx * 0.2, 0.38, 0.2), at(sx * 0.05, 0.383, 0.29)], 8);
    ribbon(node.g(M.webbing), lap, 0.045, 0.004, [0, 1, 0]);
  }
  ribbon(node.g(M.webbing), bezier([at(0, 0.33, 0.44), at(0, 0.385, 0.4), at(0, 0.383, 0.33)], 6), 0.045, 0.004, [0, 1, 0]);
  cyl(node.g(M.metal), Frame.at(buckle), 0.036, 0.012, 20);
  cyl(node.g(M.darkMetal), Frame.at(v3.add(buckle, [0, 0.008, 0])), 0.022, 0.006, 16);
  // inertia reel lock handle, on the left
  rod(node.g(M.metal), at(0.24, 0.3, 0.3), at(0.25, 0.34, 0.38), 0.004, 8);
  rbox(node.g(M.plastic), Frame.at(at(0.25, 0.345, 0.39)), [0.018, 0.014, 0.03], 0.004, 2);
  return node;
}

// ---- flight controls --------------------------------------------------------------------------------------------------------------------
// The cyclic pivots at `base`; its node's local X is pitch, Z roll.
export function cyclic(ctx, parent, name, base, o = {}) {
  const M = ctx.M;
  const node = parent.child(name, Frame.at(base), { control: "cyclic", pivot: "gimbal at the base; rotate local X for pitch, local Z for roll" });
  const len = o.len ?? 0.52, lean = o.lean ?? 0.06;
  const B = Frame.at(base);
  lathe(node.g(M.rubber), B, [[0, 0], [0.075, 0], [0.074, 0.018], [0.058, 0.045], [0.04, 0.07], [0.026, 0.1], [0.018, 0.13], [0, 0.13]], 18, { smooth: true });
  const top = v3.add(base, [0, len, lean]);
  const axis = v3.norm(v3.sub(top, base));
  const g0 = v3.add(base, v3.mul(axis, len - 0.15));
  rod(node.g(M.metal), v3.add(base, [0, 0.1, 0]), g0, 0.011, 12);
  const G = Frame.upAlong(g0, axis, [1, 0, 0]);
  // grip
  lathe(node.g(M.plastic), G, [[0, -0.01], [0.017, -0.01], [0.019, 0.02], [0.022, 0.06], [0.021, 0.1], [0.02, 0.118], [0, 0.118]], 16, { smooth: true });
  // head, leaning forward, with trim hat, weapons hat and a button
  const H = G.move(0, 0.13, 0.008).rotX(18 * deg);
  rbox(node.g(M.plastic), H, [0.042, 0.04, 0.05], 0.012, 3);
  cyl(node.g(M.metal), Frame.upAlong(H.point([0.0, 0.021, -0.008]), H.y, H.x), 0.006, 0.006, 10);
  cyl(node.g(M.darkMetal), Frame.upAlong(H.point([0.012, 0.018, -0.018]), v3.norm(v3.add(H.y, v3.mul(H.z, -0.6))), H.x), 0.005, 0.007, 10);
  cyl(node.g(M.red), Frame.upAlong(H.point([-0.013, 0.019, -0.012]), H.y, H.x), 0.004, 0.005, 10);
  // trigger and guard
  const T = G.move(0, 0.085, 0.024);
  box(node.g(M.metal), T.rotX(-15 * deg), [0.012, 0.03, 0.006]);
  tube(node.g(M.plastic), bezier([G.point([0, 0.05, 0.02]), G.point([0, 0.06, 0.055]), G.point([0, 0.11, 0.05]), G.point([0, 0.12, 0.024])], 8), 0.003, 6);
  return node;
}

// The collective pivots at `pivot` and runs to `grip`; its node's local X is the lift axis.
export function collective(ctx, parent, name, pivot, grip, o = {}) {
  const M = ctx.M;
  const dir = v3.norm(v3.sub(grip, pivot));
  const node = parent.child(name, Frame.at(pivot), { control: "collective", pivot: "rotate about local X to raise and lower" });
  const side = o.side ?? 1;
  cyl(node.g(M.darkMetal), Frame.upAlong(pivot, [1, 0, 0], [0, 1, 0]), 0.03, 0.05, 16);
  rod(node.g(M.metal), pivot, grip, 0.016, 12);
  // grip sleeve
  const g1 = v3.add(grip, v3.mul(dir, 0.14));
  rod(node.g(M.rubber), v3.sub(grip, v3.mul(dir, 0.05)), g1, 0.021, 14);
  // switch box on the end, angled up
  const Hb = Frame.along(v3.add(g1, [0, 0.022, 0.0]), dir, [0, 1, 0]);
  rbox(node.g(M.plastic), Hb.move(0.03, 0.01, 0), [0.075, 0.05, 0.055], 0.01, 2);
  for (const [dx, dz] of [[0.012, 0.012], [0.036, -0.012], [0.05, 0.014]]) {
    const P = Frame.facing(Hb.point([dx, 0.036, dz]), Hb.y, Hb.x);
    toggle(ctx, node, P, 1);
  }
  cyl(node.g(M.red), Frame.upAlong(Hb.point([0.062, 0.0, side * 0.03]), v3.mul(Hb.z, side), Hb.y), 0.006, 0.006, 10);
  cyl(node.g(M.metal), Frame.upAlong(Hb.point([0.07, 0.028, 0]), v3.norm(v3.add(Hb.x, Hb.y)), Hb.z), 0.007, 0.012, 10);
  // friction knob near the pivot
  cyl(node.g(M.plastic), Frame.upAlong(v3.add(pivot, v3.mul(dir, 0.12)), [0, 1, 0], [1, 0, 0]).move(0, 0.03, 0), 0.012, 0.02, 12);
  return node;
}

// A pair of tail rotor pedals. Each pedal is its own node, hinged at the top of its arm.
export function pedals(ctx, parent, name, center, o = {}) {
  const M = ctx.M;
  const spread = o.spread ?? 0.125;
  const out = [];
  // the adjuster bar they hang from
  rod(parent.g(M.darkMetal), v3.add(center, [spread + 0.07, 0.24, 0.1]), v3.add(center, [-spread - 0.07, 0.24, 0.1]), 0.012, 10);
  for (const sx of [1, -1]) {
    const hinge = v3.add(center, [sx * spread, 0.24, 0.1]);
    const nd = parent.child(`${name}_${sx > 0 ? "Left" : "Right"}`, Frame.at(hinge), { control: "pedal", pivot: "rotate about local X; or slide along Z" });
    rod(nd.g(M.darkMetal), hinge, v3.add(center, [sx * spread, 0.05, 0.02]), 0.01, 10);
    const pad = Frame.facing(v3.add(center, [sx * spread, 0.04, 0.0]), [0, 0.5, -0.87], [0, 0, 1]);
    rbox(nd.g(M.darkMetal), pad, [0.09, 0.15, 0.018], 0.006, 2);
    for (let i = 0; i < 5; i++) box(nd.g(M.rubber), pad.move(0, -0.06 + i * 0.03, 0.01), [0.08, 0.008, 0.004]);
    box(nd.g(M.darkMetal), pad.move(0, -0.075, 0.02), [0.09, 0.008, 0.03]);
    out.push(nd);
  }
  return out;
}

// Levers in a quadrant. `F`: the quadrant panel's top-left corner (+X right, +Y forward along the slots, +Z up).
// Each lever: [name, x, knob colour, y where its tip sits, y of its hinge under the panel].
export function powerLevers(ctx, parent, F, levers) {
  const M = ctx.M;
  const out = [];
  levers.forEach(([name, x, knobColor, tipY, hingeY]) => {
    const hinge = F.point([x, hingeY, -0.06]);
    const nd = parent.child(name, Frame.at(hinge), { control: "lever", pivot: "rotate about local X to move along the slot" });
    const tip = F.point([x, tipY, 0.07]);
    rod(nd.g(M.metal), hinge, tip, 0.0045, 10);
    const K = Frame.upAlong(tip, v3.norm(v3.sub(tip, hinge)), F.x);
    rbox(nd.g(knobColor === "red" ? M.red : M.plastic), K.move(0, 0.012, 0), [0.036, 0.026, 0.02], 0.007, 2);
    out.push(nd);
  });
  return out;
}
