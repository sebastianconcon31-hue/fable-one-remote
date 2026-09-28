// Cockpit parts: materials, textured panels and their controls, displays,
// gauges, seats and flight controls. Each builder takes the build context,
// a parent Node and a Frame, and adds geometry in world space.
//
// Every control a crew member can operate is its own node (see `operable`),
// pivoted where it moves, with glTF extras that say how it moves:
//
//   control    toggle | rotary | button | key | rocker | guard | handle | lever | stick | collective | pedal | door | trigger
//   label      what it's called on the panel, e.g. "FUEL · BOOST"
//   fn         what it does, for a simulation to hook onto
//   motion     rotate | translate | stick, about/along `axis` (node-local)
//   positions  named positions, with `angles` (rad about axis) or `travel` (m along axis); `state` is the current one
//   min, max, value   continuous travel: angle = min + (max - min) * value
//   momentary / spring   positions that spring back, and where to
//   rest       the node's local rotation and translation at angle / travel zero
//
// With ctx.interactive false the same geometry is merged into its station
// instead (a lighter file for when nothing needs to move).
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
    // Lit legends: the same atlas, glowing (lit) or not (unlit). A lit button switches between the two.
    displays: m("Displays", { color: "#404040", rough: 0.28, map: "displays", emissiveMap: "displays", emissive: "#ffffff" }),
    displaysUnlit: m("Displays_Unlit", { color: "#303030", rough: 0.28, map: "displays" }),
    ext: m("Exterior_Paint", { color: "#40463a", rough: 0.72 }),
    extDark: m("Exterior_Dark", { color: "#24281f", rough: 0.7 }),
    sensor: m("Sensor_Glass", { color: "#17202a", metal: 0.4, rough: 0.07 }),
    rotor: m("Rotor_Blade", { color: "#2d2e2c", rough: 0.6 }),
    navRed: m("Light_Nav_Red", { color: "#5a1010", rough: 0.3, emissive: "#ff2a1a" }),
    navGreen: m("Light_Nav_Green", { color: "#0f4a1a", rough: 0.3, emissive: "#2aff5a" }),
    navWhite: m("Light_Nav_White", { color: "#6a6a6a", rough: 0.3, emissive: "#ffffff" }),
    beacon: m("Light_Anticollision", { color: "#4a1010", rough: 0.3, emissive: "#000000" }),
  };
}

export function makeCtx(pa, da, o = {}) {
  return {
    M: materials(), pa, da, seed: 1, regions: new Map(), screens: [], screenMats: new Map(),
    interactive: o.interactive ?? true, station: "", names: new Set(), controls: [],
  };
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
const mid = (uv) => [(uv[0] + uv[2]) / 2, (uv[1] + uv[3]) / 2];
const allFaces = (uv) => ({ pz: uv, nz: uv, px: uv, nx: uv, py: uv, ny: uv });

// A key cap legend. Lit ones go on the display atlas.
export function capUV(ctx, text, w, h, o = {}) {
  const ppm = o.ppm || 5200;
  const key = `cap:${text}|${w}|${h}|${o.fg}|${o.bg}|${o.glowColor}|${o.fill}`;
  return region(ctx, !!o.lit, key, w * ppm, h * ppm, { kind: "cap", text, fg: o.fg, bg: o.bg, glow: o.lit, glowColor: o.glowColor, fill: o.fill });
}

// A display with its own material and a 0-1 UV map, painted at w x h pixels.
export function screenMaterial(ctx, name, page, w = 512, h = 512) {
  if (!ctx.screenMats.has(name)) {
    const key = "screen_" + name;
    ctx.screens.push({ key, page, w, h });
    ctx.screenMats.set(name, new Material("Screen_" + name, { color: "#262626", rough: 0.22, map: key, emissiveMap: key, emissive: "#ffffff" }));
  }
  return ctx.screenMats.get(name);
}

export const slug = (s) => String(s).toUpperCase().replace(/\//g, " ").replace(/[^A-Z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "X";

// An operable part: its own node, posed in its current state, with its rest pose and motion in extras.
// Returns the node to build the moving geometry into (the parent itself in the static build).
export function operable(ctx, parent, name, rest, pose, entry) {
  if (!ctx.interactive) return parent;
  let n = name, i = 2;
  while (ctx.names.has(n)) n = `${name}_${i++}`;
  ctx.names.add(n);
  const node = parent.child(n, pose);
  node.restFrame = rest;
  node.extras = entry;
  ctx.controls.push({ node: n, station: ctx.station || undefined, ...entry });
  return node;
}

// Frame whose local +Y runs along `F`'s normal: for knobs and nuts on a panel.
const outOf = (F) => Frame.upAlong(F.o, F.z, F.x);

// ---- panels ------------------------------------------------------------------------------------------------------------
// spec: { w, h, title, name, ctl: [...], ppm, holes, bg, textSize }
// ctl entries are placed from the panel's top-left, in metres (y down):
//   { k: "toggle", x, y, label, pos: ["ON","OFF"], state (index, top first), spring, guard, fn }
//   { k: "knob", x, y, r, label, stops: [...], sel, style: "bar", value, fn }
//   { k: "pb", x, y, w, h, text, lit, litOn, latching, fg, bg, label, fn }
//   { k: "tee", x, y, fn }       a striped pull handle
//   { k: "label" | "box" | "slot" | "hazard" | "grille" | "screw", ... }   painted only
export function panel(ctx, node, F, spec) {
  const ppm = spec.ppm || 2000;
  const paintCtl = (spec.ctl || []).map(({ fn, spring, litOn, latching, momentary, name, cartridge, ...c }) => c);
  const r = ctx.pa.alloc(spec.w * ppm, spec.h * ppm, {
    kind: "panel", m: [spec.w, spec.h], title: spec.title, ctl: paintCtl, holes: spec.holes, seed: ctx.seed++, bg: spec.bg, fasteners: spec.fasteners, textSize: spec.textSize, titleY: spec.titleY,
  });
  quad(node.g(ctx.M.panels), F, spec.w, spec.h, { uv: r.uv });
  box(node.g(ctx.M.dark), F.move(0, 0, -0.003), [spec.w, spec.h, 0.0059], { skip: "pz" });
  const pname = spec.name || spec.title || "PANEL";
  for (const c of spec.ctl || []) {
    const P = F.move(-spec.w / 2 + c.x, spec.h / 2 - c.y, 0);
    const what = c.name || c.label || (c.text ? c.text.replace(/\n/g, " ") : "") || (c.k === "knob" ? "KNOB" : c.k === "tee" ? "HANDLE" : "SWITCH");
    const name = `${ctx.station}_${slug(pname)}_${slug(what)}`;
    const label = `${pname} · ${what}`;
    if (c.k === "toggle") toggle(ctx, node, P, c, name, label);
    else if (c.k === "knob") knob(ctx, node, P, c, name, label);
    else if (c.k === "pb") pushButton(ctx, node, P, c, name, label);
    else if (c.k === "tee") teeHandle(ctx, node, P, name, label, c.fn);
    else if (c.k === "slot" && c.cartridge) cartridge(ctx, node, P, name.replace(/_DTC$/, "_CARTRIDGE"), `${pname} · cartridge`, c.fn);
  }
  return r;
}

// Toggle: the lever pivots at the top of its bushing, about the panel's X axis. Positions are listed top first.
export function toggle(ctx, parent, P, c, name, label) {
  const M = ctx.M;
  const ax = outOf(P);
  cyl(parent.g(M.metal), ax.move(0, 0.0015, 0), 0.0045, 0.003, 6);
  cyl(parent.g(M.metal), ax.move(0, 0.0045, 0), 0.0027, 0.003, 10, { capBottom: false });
  const pos = c.pos || ["ON", "OFF"];
  const angles = (pos.length === 3 ? [-26, 0, 26] : [-26, 26]).map((d) => d * deg);
  const state = c.state ?? (pos.length === 3 ? 1 : 0);
  const rest = new Frame(P.point([0, 0, 0.0055]), P.x, P.y, P.z);
  const pose = rest.rotX(angles[state]);
  const entry = { control: "toggle", label, fn: c.fn ?? null, motion: "rotate", axis: [1, 0, 0], positions: pos, angles, state };
  if (c.spring != null) Object.assign(entry, { momentary: c.momentary ?? [0], spring: c.spring });
  const nd = operable(ctx, parent, name, rest, pose, entry);
  const tip = pose.point([0, 0, 0.0155]);
  rod(nd.g(M.metal), pose.o, tip, 0.0014, 8, { r2: 0.001, capBottom: false });
  sphere(nd.g(M.metal), Frame.at(tip), 0.0021, 8);
  if (c.guard) guard(ctx, parent, P, name + "_GUARD", label + " guard");
}

// A red switch guard, hinged along its top edge; open by default.
function guard(ctx, parent, P, name, label) {
  const M = ctx.M;
  const rest = new Frame(P.point([0, 0.011, 0.002]), P.x, P.y, P.z);
  const angles = [-100 * deg, 0];
  const pose = rest.rotX(angles[0]);
  const nd = operable(ctx, parent, name, rest, pose, { control: "guard", label, fn: null, motion: "rotate", axis: [1, 0, 0], positions: ["OPEN", "CLOSED"], angles, state: 0 });
  // modelled closed, relative to the hinge, then carried by the pose
  const at = (x, y, z) => pose.point([x, y - 0.011, z - 0.002]);
  const G = new Frame(at(0, 0.001, 0.021), pose.x, pose.y, pose.z);
  box(nd.g(M.red), G, [0.016, 0.02, 0.0016]);
  box(nd.g(M.red), new Frame(at(0.0072, 0.001, 0.011), pose.x, pose.y, pose.z), [0.0016, 0.02, 0.02]);
  box(nd.g(M.red), new Frame(at(-0.0072, 0.001, 0.011), pose.x, pose.y, pose.z), [0.0016, 0.02, 0.02]);
}

// Rotary knob: turns about the panel normal (local Z). Stops run clockwise; clockwise is negative.
export function knob(ctx, parent, P, c, name, label) {
  const M = ctx.M;
  const r = c.r || 0.007;
  cyl(parent.g(M.plastic), outOf(P).move(0, 0.001, 0), r * 1.14, 0.002, 20);
  const stops = c.stops || [];
  const span = (c.span ?? 270) * deg;
  let entry, angle;
  if (stops.length > 1) {
    const angles = stops.map((_, i) => span / 2 - (span * i) / (stops.length - 1));
    const sel = c.sel ?? Math.floor((stops.length - 1) / 2);
    angle = angles[sel];
    entry = { control: "rotary", label, fn: c.fn ?? null, motion: "rotate", axis: [0, 0, 1], positions: stops, angles, state: sel };
  } else {
    const min = span / 2, max = -span / 2, value = c.value ?? 0.7;
    angle = min + (max - min) * value;
    entry = { control: "rotary", label, fn: c.fn ?? null, motion: "rotate", axis: [0, 0, 1], min, max, value };
  }
  const rest = new Frame(P.o, P.x, P.y, P.z);
  const pose = rest.rotZ(angle);
  const nd = operable(ctx, parent, name, rest, pose, entry);
  const dk = { uvConst: mid(darkUV(ctx)) };
  const ax = outOf(pose);
  const dirW = pose.y;
  if (c.style === "bar") {
    cyl(nd.g(M.panels), ax.move(0, 0.004, 0), r * 0.55, 0.006, 12, dk);
    rbox(nd.g(M.panels), Frame.facing(pose.point([0, 0, 0.0085]), pose.z, dirW), [r * 0.62, r * 2.3, 0.0085], 0.0015, 2, dk);
    quad(nd.g(M.panels), Frame.facing(pose.point([0, r * 0.55, 0.01279]), pose.z, dirW), 0.0011, r * 0.9, { uv: whiteUV(ctx) });
  } else {
    const h = c.tall ? 0.017 : 0.012;
    lathe(nd.g(M.panels), ax, [[0, 0.002], [r * 0.84, 0.002], [r * 0.8, h], [r * 0.66, h + 0.0015], [0, h + 0.0015]], 16, dk);
    quad(nd.g(M.panels), Frame.facing(pose.point([0, r * 0.38, h + 0.0016]), pose.z, dirW), 0.0011, r * 0.62, { uv: whiteUV(ctx) });
  }
  return nd;
}

// Push button: the cap moves in along -Z. Lit caps switch between the Displays (lit) and Displays_Unlit materials.
export function pushButton(ctx, parent, P, c, name, label) {
  const M = ctx.M;
  const w = c.w || 0.012, h = c.h || 0.012;
  const lit = !!c.lit;
  const on = lit && (c.litOn ?? false);
  const uv = c.text != null ? capUV(ctx, c.text, w, h, { lit, fg: c.fg, bg: c.bg, glowColor: c.glowColor, fill: c.fill }) : lit ? darkLitUV(ctx) : darkUV(ctx);
  const side = lit ? darkLitUV(ctx) : darkUV(ctx);
  bezel(parent.g(M.plastic), P.move(0, 0, 0.0018), w + 0.0036, h + 0.0036, w + 0.0006, h + 0.0006, 0.0036, { r: 0.0012, ri: 0.0004, seg: 2 });
  const rest = P.move(0, 0, c.depth ?? 0.0045);
  const entry = { control: "button", label, fn: c.fn ?? null, motion: "translate", axis: [0, 0, -1], travel: 0.0018, latching: !!c.latching };
  if (lit) entry.lit = on;
  const nd = operable(ctx, parent, name, rest, rest, entry);
  box(nd.g(lit ? (on ? M.displays : M.displaysUnlit) : M.panels), rest, [w, h, 0.005], { uv, uvs: { nz: side, px: side, nx: side, py: side, ny: side } });
  return nd;
}

// Striped T-handle that pulls straight out (canopy jettison).
export function teeHandle(ctx, parent, P, name, label, fn) {
  const M = ctx.M;
  const nd = operable(ctx, parent, name, P, P, { control: "handle", label, fn: fn ?? null, motion: "translate", axis: [0, 0, 1], positions: ["IN", "PULLED"], travel: 0.035, state: 0 });
  rod(nd.g(M.metal), P.point([0, 0, -0.01]), P.point([0, 0, 0.022]), 0.0035, 10);
  box(nd.g(M.panels), P.move(0, 0, 0.027), [0.05, 0.013, 0.011], { uv: hazardUV(ctx), uvs: allFaces(hazardUV(ctx)) });
}

// Data transfer cartridge that ejects from its slot.
function cartridge(ctx, parent, P, name, label, fn) {
  const nd = operable(ctx, parent, name, P, P, { control: "handle", label, fn: fn ?? null, motion: "translate", axis: [0, 0, 1], positions: ["IN", "EJECTED"], travel: 0.02, state: 0 });
  box(nd.g(ctx.M.plastic), P.move(0, 0, 0.012), [0.07, 0.014, 0.028]);
}

// A block of keys. keys: [{ x, y, w, h, text, name, fn }] in the frame's plane (metres from centre, y up).
function keys(ctx, parent, F, list, o = {}) {
  const depth = o.depth ?? 0.005;
  for (const k of list) {
    const P = F.move(k.x, k.y, depth / 2);
    const uv = k.text ? capUV(ctx, k.text, k.w, k.h, { fg: o.fg, bg: o.bg, fill: o.fill }) : darkUV(ctx);
    const nd = operable(ctx, parent, k.name, P, P, { control: "key", label: k.label, fn: k.fn ?? null, motion: "translate", axis: [0, 0, -1], travel: Math.min(0.002, depth * 0.4) });
    box(nd.g(ctx.M.panels), P, [k.w, k.h, depth], { uv, uvs: { nz: darkUV(ctx), px: darkUV(ctx), nx: darkUV(ctx), py: darkUV(ctx), ny: darkUV(ctx) } });
  }
}

// A rocker: rocks about local X; UP and DOWN spring back to the middle.
function rocker(ctx, parent, R, name, label, fn, size = [0.011, 0.022, 0.006]) {
  const M = ctx.M;
  rbox(parent.g(M.plastic), R.move(0, 0, -0.0015), [size[0] + 0.003, size[1] + 0.003, 0.003], 0.0015, 1);
  const angles = [-8 * deg, 0, 8 * deg];
  const nd = operable(ctx, parent, name, R, R, { control: "rocker", label, fn, motion: "rotate", axis: [1, 0, 0], positions: ["UP", "CENTER", "DOWN"], angles, state: 1, momentary: [0, 2], spring: 1 });
  const dk = { uvConst: mid(darkUV(ctx)) };
  rbox(nd.g(M.panels), R.move(0, 0, size[2] / 2), size, 0.002, 2, dk);
  rbox(nd.g(M.panels), R.move(0, size[1] * 0.25, size[2]).rotX(-12 * deg), [size[0] * 0.8, size[1] * 0.36, 0.003], 0.001, 1, dk);
}

// ---- multipurpose display (MPD) -------------------------------------------------------------------------------------------
// F: the panel surface at the display's centre, +Z toward the crew.
// Keys: T1-T6 along the top (left to right), B1-B6 along the bottom, L1-L6 and R1-R6 down the sides (top to bottom),
// the fixed-action keys FCR WPN TSD VID COM A/C and MENU, BRT and VID rockers, and the DAY/NT/MONO knob.
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
  const k = (id, x, y, w, h, text) => ({ name: `${name}_${id}`, label: `${name.replace(/_/g, " ")} · ${text || id}`, fn: `mpd:${name}:${id}`, x, y, w, h, text });
  for (let i = 0; i < 6; i++) {
    btn.push(k(`T${i + 1}`, along(i), OFF + S / 2 + 0.0105, 0.017, 0.0105));
    btn.push(k(`B${i + 1}`, along(i), OFF - S / 2 - 0.0105, 0.017, 0.0105));
    btn.push(k(`L${i + 1}`, -S / 2 - 0.0105, OFF + along(5 - i), 0.0105, 0.017));
    btn.push(k(`R${i + 1}`, S / 2 + 0.0105, OFF + along(5 - i), 0.0105, 0.017));
  }
  ["FCR", "WPN", "TSD", "VID", "COM", "A/C"].forEach((t, i) => btn.push(k(slug(t), -0.08 + i * 0.032, -H / 2 + 0.0125, 0.025, 0.0115, t)));
  btn.push(k("MENU", W / 2 - 0.013, -H / 2 + 0.0125, 0.017, 0.0115, "M"));
  keys(ctx, node, Fk, btn, { depth: 0.0055 });
  rocker(ctx, node, Fk.move(-(W / 2 - 0.013), H / 2 - 0.018, 0.0015), `${name}_BRT`, `${name.replace(/_/g, " ")} · BRT`, `mpd:${name}:BRT`);
  rocker(ctx, node, Fk.move(W / 2 - 0.013, H / 2 - 0.018, 0.0015), `${name}_VIDEO`, `${name.replace(/_/g, " ")} · VID`, `mpd:${name}:VIDEO`);
  knob(ctx, node, Fk.move(-W / 2 + 0.013, -H / 2 + 0.0125, -0.001), { r: 0.0055, stops: ["DAY", "NT", "MONO"], sel: 0, span: 90, fn: `mpd:${name}:MODE` }, `${name}_MODE`, `${name.replace(/_/g, " ")} · DAY/NT/MONO`);
  return node;
}

// ---- up-front display (EUFD) and keyboard unit (KU) ---------------------------------------------------------------------------
export function eufd(ctx, parent, F, name) {
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
  const scr = node.child(name + "_Screen", F.move(off[0], off[1], D - 0.006), { screen: "EUFD", size_m: [WW, WH] });
  quad(scr.g(screenMaterial(ctx, name, "EUFD", 512, 212)), scr.frame, WW + 0.004, WH + 0.004, { uv: [0, 0, 1, 1] });
  const Fk = F.move(0, 0, D);
  const k = (id, x, y, w, h) => ({ name: `${name}_${id}`, label: `${name.replace(/_/g, " ")} · ${id}`, fn: `eufd:${name}:${id}`, x, y, w, h });
  const list = [];
  ["WCA", "IDM", "RTS"].forEach((id, i) => list.push(k(id, -W / 2 + 0.012, H / 2 - 0.02 - i * 0.03, 0.009, 0.02)));
  ["STBY", "PRESET", "ENTER", "SWAP"].forEach((id, i) => list.push(k(id, -0.045 + i * 0.033 + off[0], -H / 2 + 0.0065, 0.018, 0.0075)));
  ["UP", "DOWN", "SELECT"].forEach((id, i) => list.push(k(id, W / 2 - 0.012, H / 2 - 0.028 - i * 0.026, 0.009, 0.016)));
  keys(ctx, node, Fk, list, { depth: 0.005 });
  knob(ctx, node, Fk.move(W / 2 - 0.01, H / 2 - 0.013, -0.001), { r: 0.0045, value: 0.8, fn: `eufd:${name}:BRT` }, `${name}_BRT`, `${name.replace(/_/g, " ")} · BRT`);
  return node;
}

export const KU_ROWS = [
  ["A", "B", "C", "D", "E", "F", "1", "2", "3"],
  ["G", "H", "I", "J", "K", "L", "4", "5", "6"],
  ["M", "N", "O", "P", "Q", "R", "7", "8", "9"],
  ["S", "T", "U", "V", "W", "X", ".", "0", "/"],
  ["Y", "Z", "SPC", "BKS", "CLR", "ENT", "+", "-", "*"],
];
const KEY_ID = { ".": "DOT", "/": "SLASH", "+": "PLUS", "-": "MINUS", "*": "STAR" };

export function keyboard(ctx, parent, F, name) {
  const M = ctx.M;
  const node = parent.child(name, F);
  const W = 0.19, H = 0.118, D = 0.018;
  box(node.g(M.dark), F.move(0, 0, D / 2 - 0.002), [W, H, D - 0.004], { skip: "pz" });
  const face = ctx.pa.alloc(W * 1600, H * 1600, { kind: "panel", m: [W, H], ctl: [{ k: "label", x: W - 0.012, y: H - 0.0045, text: "KU", size: 0.003 }], fasteners: false, bg: "#25282a", seed: ctx.seed++ });
  const padW = 0.15, padH = 0.016, padY = H / 2 - 0.013;
  bezel(node.g(M.panels), F.move(0, 0, D - 0.004), W, H, padW, padH, 0.004, { r: 0.006, ri: 0.001, uv: face.uv, off: [0, padY] });
  const scr = node.child(name + "_Screen", F.move(0, padY, D - 0.0065), { screen: "KU", size_m: [padW, padH] });
  quad(scr.g(screenMaterial(ctx, name, "KU", 512, 56)), scr.frame, padW + 0.003, padH + 0.003, { uv: [0, 0, 1, 1] });
  const list = [];
  KU_ROWS.forEach((row, r) => {
    row.forEach((t, c) => {
      const id = KEY_ID[t] || t;
      list.push({ name: `${name}_${id}`, label: `${name.replace(/_/g, " ")} · ${t}`, fn: `ku:${name}:${t}`, x: -0.0795 + c * 0.0182 + (c >= 6 ? 0.0055 : 0), y: padY - 0.0205 - r * 0.0168, w: 0.0148, h: 0.0118, text: t });
    });
  });
  keys(ctx, node, F.move(0, 0, D - 0.004), list, { depth: 0.006 });
  return node;
}

// ---- standby instruments ---------------------------------------------------------------------------------------------------------
// F at the instrument's centre on the panel face. Needles and the ADI face are driven nodes; each gauge has a setting knob.
export function gauge(ctx, parent, F, name, type, d) {
  const M = ctx.M;
  const node = parent.child(name, F);
  const plate = d + 0.016;
  rbox(node.g(M.plastic), F.move(0, 0, 0.003), [plate, plate, 0.006], 0.003, 2);
  const ax = outOf(F);
  lathe(node.g(M.plastic), ax, [[d / 2, 0.006], [d / 2 + 0.0035, 0.006], [d / 2 + 0.0035, 0.0095], [d / 2 + 0.001, 0.0108], [d / 2, 0.0108]], 32);
  const circle = (r, n = 40) => [...Array(n)].map((_, i) => [Math.cos((i / n) * Math.PI * 2) * r, Math.sin((i / n) * Math.PI * 2) * r]);
  if (type === "ADI") {
    // The attitude ball is a live display of its own.
    const ball = node.child(name + "_Screen", F, { screen: "ADI", drive: "a picture of the attitude ball; repaint for pitch and roll" });
    poly(ball.g(screenMaterial(ctx, name, "ADI", 256, 256)), F.move(0, 0, 0.0064), circle(d / 2 + 0.0005), { uv: [0, 0, 1, 1] });
    const o = orangeUV(ctx);
    box(node.g(M.panels), F.move(-d * 0.2, -0.001, 0.0084), [d * 0.22, 0.0022, 0.0012], { uv: o, uvs: allFaces(o) });
    box(node.g(M.panels), F.move(d * 0.2, -0.001, 0.0084), [d * 0.22, 0.0022, 0.0012], { uv: o, uvs: allFaces(o) });
    box(node.g(M.panels), F.move(0, -0.001, 0.0084), [0.003, 0.003, 0.0012], { uv: o, uvs: allFaces(o) });
    poly(node.g(M.panels), F.move(0, d * 0.34, 0.0084), [[0, 0.004], [-0.003, -0.002], [0.003, -0.002]], { uv: o });
  } else {
    const faceUV = region(ctx, false, "gauge:" + type, 256, 256, { kind: "gauge", type });
    poly(node.g(M.panels), F.move(0, 0, 0.0064), circle(d / 2 + 0.0005), { uv: faceUV });
    // Airspeed and altitude needles rest at zero (12 o'clock) so they can be driven with absolute angles.
    const hands = type === "ALT" ? [[0.43, 0.0016, 0], [0.26, 0.0028, 0]] : type === "CLOCK" ? [[0.4, 0.0014, 0.2], [0.28, 0.0022, 2.1]] : [[0.4, 0.0018, 0]];
    hands.forEach(([len, w, rot], i) => {
      const rest = F.move(0, 0, 0.0074 + i * 0.0005);
      const nd = node.child(`${name}_Needle${hands.length > 1 ? i + 1 : ""}`, rest.rotZ(-rot), { drive: "rotate about local Z from rest; clockwise is negative", axis: [0, 0, 1] });
      nd.restFrame = rest;
      quad(nd.g(M.panels), nd.frame.move(0, (len * d) / 2 - 0.004, 0), w, len * d + 0.006, { uv: whiteUV(ctx) });
    });
    cyl(node.g(M.plastic), ax.move(0, 0.0086, 0), 0.0026, 0.001, 12);
  }
  // the setting knob in the lower left corner
  const kn = { ADI: ["PULL TO CAGE", "adiCage"], ASI: ["TEST", "asiTest"], ALT: ["BARO SET", "altBaro"], CLOCK: ["SET", "clockSet"] }[type];
  knob(ctx, node, F.move(-plate / 2 + 0.006, -plate / 2 + 0.006, 0.006), { r: 0.0042, value: 0.5, span: 720, fn: kn[1] }, `${name}_KNOB`, `${name.replace(/_/g, " ")} · ${kn[0]}`);
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
  box(node.g(M.darkMetal), S.move(0, 0.12, 0.2), [0.34, 0.03, 0.36]);
  for (const sx of [-1, 1]) {
    box(node.g(M.darkMetal), S.move(sx * 0.15, 0.06, 0.2), [0.03, 0.12, 0.4]);
    box(node.g(M.metal), S.move(sx * 0.15, 0.012, 0.2), [0.045, 0.024, 0.46]);
  }
  box(node.g(M.armor), S.move(0, 0.24, 0.22), [0.43, 0.14, 0.46]);
  rbox(node.g(M.cushion), S.move(0, 0.33, 0.235), [0.39, 0.075, 0.43], 0.03, 3);
  const back = S.move(0, 0.34, -0.02).rotX(-12 * deg);
  box(node.g(M.armor), back.move(0, 0.36, -0.035), [0.45, 0.8, 0.045]);
  rbox(node.g(M.cushion), back.move(0, 0.31, 0.03), [0.38, 0.58, 0.075], 0.03, 3);
  rbox(node.g(M.cushion), back.move(0, 0.71, 0.025), [0.24, 0.14, 0.06], 0.025, 3);
  const wing = [[-0.07, 0.17], [0.44, 0.17], [0.44, 0.33], [0.26, 0.44], [0.12, 0.95], [-0.09, 1.02]];
  for (const sx of [-1, 1]) extrude(node.g(M.armor), new Frame(at(sx * 0.226, 0, 0), [0, 0, 1], [0, 1, 0], [-1, 0, 0]), wing, 0.026);
  for (const sx of [-1, 1]) {
    rod(node.g(M.metal), at(sx * 0.17, 0.05, -0.12), at(sx * 0.17, 0.95, -0.2), 0.022, 12);
    rod(node.g(M.darkMetal), at(sx * 0.17, 0.35, -0.13), at(sx * 0.17, 0.75, -0.18), 0.03, 12);
  }
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
  // inertia reel lock: LOCKED forward, UNLOCKED back
  const hinge = at(0.24, 0.3, 0.3);
  const rest = Frame.at(hinge);
  const angles = [0.35, 0];
  const pose = rest.rotX(angles[1]);
  const lk = operable(ctx, node, `${ctx.station}_Seat_Inertia_Reel`, rest, pose, { control: "lever", label: "Seat · inertia reel lock", fn: `${ctx.station.toLowerCase()}.inertiaReel`, motion: "rotate", axis: [1, 0, 0], positions: ["LOCKED", "UNLOCKED"], angles, state: 1 });
  rod(lk.g(M.metal), hinge, v3.add(hinge, [0.01, 0.04, 0.08]), 0.004, 8);
  rbox(lk.g(M.plastic), Frame.at(v3.add(hinge, [0.01, 0.045, 0.09])), [0.018, 0.014, 0.03], 0.004, 2);
  return node;
}

// ---- flight controls --------------------------------------------------------------------------------------------------------------------
// Cyclic: pivots at `base`; tilt about local X for pitch (+ forward) and local Z for roll (+ right).
export function cyclic(ctx, parent, name, base, o = {}) {
  const M = ctx.M;
  const B = Frame.at(base);
  lathe(parent.g(M.rubber), B, [[0, 0], [0.075, 0], [0.074, 0.018], [0.058, 0.045], [0, 0.045]], 18, { smooth: true });
  const node = operable(ctx, parent, name, B, B, { control: "stick", label: `${name.replace(/_/g, " ")}`, fn: "cyclic", motion: "stick", axes: { pitch: [1, 0, 0], roll: [0, 0, 1] }, limits: { pitch: 0.26, roll: 0.26 }, note: "+X pushes it forward, +Z pushes it right" });
  const len = o.len ?? 0.52, lean = o.lean ?? 0.06;
  lathe(node.g(M.rubber), B.move(0, 0.045, 0), [[0.058, 0], [0.04, 0.025], [0.026, 0.055], [0.018, 0.085], [0, 0.085]], 18, { smooth: true });
  const top = v3.add(base, [0, len, lean]);
  const axis = v3.norm(v3.sub(top, base));
  const g0 = v3.add(base, v3.mul(axis, len - 0.15));
  rod(node.g(M.metal), v3.add(base, [0, 0.1, 0]), g0, 0.011, 12);
  const G = Frame.upAlong(g0, axis, [1, 0, 0]);
  lathe(node.g(M.plastic), G, [[0, -0.01], [0.017, -0.01], [0.019, 0.02], [0.022, 0.06], [0.021, 0.1], [0.02, 0.118], [0, 0.118]], 16, { smooth: true });
  const H = G.move(0, 0.13, 0.008).rotX(18 * deg);
  rbox(node.g(M.plastic), H, [0.042, 0.04, 0.05], 0.012, 3);
  const pre = name.replace(/_Cyclic$/, "");
  const btn = (id, label, fn, P, r, h, mat) => {
    const nd = operable(ctx, node, `${name}_${id}`, P, P, { control: "button", label: `${pre} cyclic · ${label}`, fn, motion: "translate", axis: [0, -1, 0], travel: 0.002 });
    cyl(nd.g(mat), P, r, h, 10);
  };
  btn("Trim", "force trim release", "trim", Frame.upAlong(H.point([0.0, 0.021, -0.008]), H.y, H.x), 0.006, 0.006, M.metal);
  btn("Weapon_Select", "weapon action switch", "was", Frame.upAlong(H.point([0.012, 0.018, -0.018]), v3.norm(v3.add(H.y, v3.mul(H.z, -0.6))), H.x), 0.005, 0.007, M.darkMetal);
  btn("Chaff", "chaff", "chaff", Frame.upAlong(H.point([-0.013, 0.019, -0.012]), H.y, H.x), 0.004, 0.005, M.red);
  // trigger, pivoting at its top
  const T = G.move(0, 0.1, 0.022);
  const tn = operable(ctx, node, `${name}_Trigger`, T, T, { control: "trigger", label: `${pre} cyclic · weapon trigger`, fn: "trigger", motion: "rotate", axis: [1, 0, 0], positions: ["RELEASED", "PULLED"], angles: [0, -0.3], state: 0, momentary: [1], spring: 0 });
  box(tn.g(M.metal), T.move(0, -0.015, 0.002).rotX(-15 * deg), [0.012, 0.03, 0.006]);
  tube(node.g(M.plastic), bezier([G.point([0, 0.05, 0.02]), G.point([0, 0.06, 0.055]), G.point([0, 0.11, 0.05]), G.point([0, 0.12, 0.024])], 8), 0.003, 6);
  return node;
}

// Collective: pivots at `pivot`, runs to `grip`. Rotate about local X from 0 (down) to -0.3 (up).
export function collective(ctx, parent, name, pivot, grip, o = {}) {
  const M = ctx.M;
  const dir = v3.norm(v3.sub(grip, pivot));
  const R = Frame.at(pivot);
  cyl(parent.g(M.darkMetal), Frame.upAlong(pivot, [1, 0, 0], [0, 1, 0]), 0.03, 0.05, 16);
  const node = operable(ctx, parent, name, R, R, { control: "collective", label: name.replace(/_/g, " "), fn: "collective", motion: "rotate", axis: [1, 0, 0], min: 0, max: -0.3, value: 0, note: "value 0 is fully down, 1 fully up" });
  const side = o.side ?? 1;
  rod(node.g(M.metal), pivot, grip, 0.016, 12);
  const g1 = v3.add(grip, v3.mul(dir, 0.14));
  rod(node.g(M.rubber), v3.sub(grip, v3.mul(dir, 0.05)), g1, 0.021, 14);
  const Hb = Frame.along(v3.add(g1, [0, 0.022, 0.0]), dir, [0, 1, 0]);
  rbox(node.g(M.plastic), Hb.move(0.03, 0.01, 0), [0.075, 0.05, 0.055], 0.01, 2);
  const pre = name.replace(/_Collective$/, "");
  const sw = [
    ["Searchlight", "SEARCHLIGHT", { pos: ["ON", "OFF"], state: 1, fn: "searchlight" }],
    ["Radio_Select", "RADIO SELECT", { pos: ["UP", "MID", "DN"], state: 1, fn: "rts", spring: 1, momentary: [0, 2] }],
    ["Missile_Advance", "MISSILE ADVANCE", { pos: ["ADV", "OFF"], state: 1, fn: "msladv", spring: 1, momentary: [0] }],
  ];
  [[0.012, 0.012], [0.036, -0.012], [0.05, 0.014]].forEach(([dx, dz], i) => {
    const P = Frame.facing(Hb.point([dx, 0.036, dz]), Hb.y, Hb.x);
    const [id, lbl, c] = sw[i];
    toggle(ctx, node, P, c, `${name}_${id}`, `${pre} collective · ${lbl}`);
  });
  const redP = Frame.upAlong(Hb.point([0.062, 0.0, side * 0.03]), v3.mul(Hb.z, side), Hb.y);
  const rn = operable(ctx, node, `${name}_Flare`, redP, redP, { control: "button", label: `${pre} collective · flare dispense`, fn: "flare", motion: "translate", axis: [0, -1, 0], travel: 0.002 });
  cyl(rn.g(M.red), redP, 0.006, 0.006, 10);
  const mP = Frame.upAlong(Hb.point([0.07, 0.028, 0]), v3.norm(v3.add(Hb.x, Hb.y)), Hb.z);
  const mn = operable(ctx, node, `${name}_Chop`, mP, mP, { control: "button", label: `${pre} collective · engine chop`, fn: "chop", motion: "translate", axis: [0, -1, 0], travel: 0.002 });
  cyl(mn.g(M.metal), mP, 0.007, 0.012, 10);
  // friction knob near the pivot
  const fP = Frame.upAlong(v3.add(pivot, v3.mul(dir, 0.12)), [0, 1, 0], [1, 0, 0]).move(0, 0.03, 0);
  const fr = operable(ctx, node, `${name}_Friction`, fP, fP, { control: "rotary", label: `${pre} collective · friction`, fn: null, motion: "rotate", axis: [0, 1, 0], min: 0, max: -3.14, value: 0.3 });
  cyl(fr.g(M.plastic), fP, 0.012, 0.02, 12);
  return node;
}

// Pedals: each hinged at the top of its arm; the two move in opposition (fn "pedals").
export function pedals(ctx, parent, name, center, o = {}) {
  const M = ctx.M;
  const spread = o.spread ?? 0.125;
  rod(parent.g(M.darkMetal), v3.add(center, [spread + 0.07, 0.24, 0.1]), v3.add(center, [-spread - 0.07, 0.24, 0.1]), 0.012, 10);
  for (const sx of [1, -1]) {
    const hinge = v3.add(center, [sx * spread, 0.24, 0.1]);
    const R = Frame.at(hinge);
    const side = sx > 0 ? "Left" : "Right";
    // value 0 = full left pedal, 1 = full right pedal. The left pedal goes forward (-X) for left yaw.
    const lim = sx > 0 ? { min: -0.2, max: 0.2 } : { min: 0.2, max: -0.2 };
    const nd = operable(ctx, parent, `${name}_${side}`, R, R, { control: "pedal", label: `${name.replace(/_/g, " ")} ${side.toLowerCase()}`, fn: "pedals", motion: "rotate", axis: [1, 0, 0], ...lim, value: 0.5, note: "value 0 is full left pedal, 1 full right; the pair move in opposition" });
    rod(nd.g(M.darkMetal), hinge, v3.add(center, [sx * spread, 0.05, 0.02]), 0.01, 10);
    const pad = Frame.facing(v3.add(center, [sx * spread, 0.04, 0.0]), [0, 0.5, -0.87], [0, 0, 1]);
    rbox(nd.g(M.darkMetal), pad, [0.09, 0.15, 0.018], 0.006, 2);
    for (let i = 0; i < 5; i++) box(nd.g(M.rubber), pad.move(0, -0.06 + i * 0.03, 0.01), [0.08, 0.008, 0.004]);
    box(nd.g(M.darkMetal), pad.move(0, -0.075, 0.02), [0.09, 0.008, 0.03]);
  }
}

// Levers in a quadrant, pivoting under the panel about the aircraft's lateral axis.
// `F`: the quadrant panel's top-left corner (+X right, +Y forward along the slots, +Z up).
// Each lever: { name, label, fn, x, positions, slotY: [panel y of each position], state, hingeY, color }.
export function levers(ctx, parent, F, list) {
  const M = ctx.M;
  for (const L of list) {
    const hinge = F.point([L.x, L.hingeY, -0.06]);
    const rest = Frame.at(hinge);
    // angle about +X that points the lever through the slot at each position (+ is forward)
    const angles = L.slotY.map((y) => Math.atan2(y - L.hingeY, 0.06));
    const pose = rest.rotX(angles[L.state]);
    const nd = operable(ctx, parent, L.name, rest, pose, { control: "lever", label: L.label, fn: L.fn, motion: "rotate", axis: [1, 0, 0], positions: L.positions, angles, state: L.state });
    const tip = pose.point([0, 0.14, 0]);
    rod(nd.g(M.metal), hinge, tip, 0.0045, 10);
    rbox(nd.g(L.color === "red" ? M.red : M.plastic), new Frame(pose.point([0, 0.152, 0]), pose.x, pose.y, pose.z), [0.036, 0.026, 0.02], 0.007, 2);
  }
}

// Air vent: an eyeball that turns to open and close.
export function vent(ctx, parent, V, name, label) {
  const M = ctx.M;
  const ax = Frame.upAlong(V.o, V.z, V.x);
  lathe(parent.g(M.plastic), ax, [[0.016, 0], [0.018, 0], [0.018, 0.006], [0.0145, 0.008], [0.0145, 0.002]], 18);
  const rest = new Frame(V.o, V.x, V.y, V.z);
  const nd = operable(ctx, parent, name, rest, rest, { control: "rotary", label, fn: null, motion: "rotate", axis: [0, 0, 1], min: 0, max: -1.57, value: 0 });
  const dk = { uvConst: mid(darkUV(ctx)) };
  sphere(nd.g(M.panels), Frame.upAlong(V.point([0, 0, 0.004]), v3.norm(v3.add(V.z, v3.mul(V.y, 0.3))), V.x), 0.0135, 14, { from: 0, to: Math.PI / 2, ...dk });
  box(nd.g(M.panels), V.move(0, 0, 0.016), [0.018, 0.003, 0.004], { uvAll: darkUV(ctx) });
}
