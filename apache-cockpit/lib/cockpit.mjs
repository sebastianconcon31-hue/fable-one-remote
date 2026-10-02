// The AH-64 tandem cockpit: the tub, the canopy, and the two crew stations -
// the copilot/gunner (CPG) in front and low, the pilot behind and high.
//
// Axes are glTF's: metres, +Y up, +Z toward the nose, +X to the crew's left.
// The origin is on the front cockpit floor, on the centreline, under the CPG
// seat back.
import { v3, Frame, Node, quad, face, box, beam, rod, tube, extrude, bezier, loft, lathe, cyl, sphere, rbox, bezel } from "./geo.mjs";
import { deg, panel, mpd, eufd, keyboard, gauge, seat, cyclic, collective, pedals, levers, pushButton, screenMaterial, operable, vent, darkUV } from "./parts.mjs";

export const CPG = { srp: [0, 0, -0.02], eye: [0, 1.13, 0.14] };
export const PLT = { srp: [0, 0.46, -1.52], eye: [0, 1.6, -1.36] };

// Canopy corners, left side (the right side is the mirror image).
export const CAN = {
  A: [0.38, 0.8, 0.98], // windscreen base
  B: [0.25, 1.4, 0.64], // windscreen top / front roof
  C: [0.27, 1.46, -0.14], // front roof rear / pilot windscreen base
  Q: [0.45, 0.82, -0.14], // front sill, rear
  D: [0.26, 1.98, -0.52], // pilot windscreen top
  E: [0.27, 2.02, -1.72], // rear roof end
  R1: [0.44, 1.08, -0.46], // rear sill, front
  R2: [0.47, 1.18, -1.84], // rear sill, rear
};
const mir = (p) => [-p[0], p[1], p[2]];
const Lf = (k) => CAN[k];
const Rt = (k) => mir(CAN[k]);

const SILL = [[0.98, 0.38, 0.8], [-0.14, 0.45, 0.82], [-0.46, 0.44, 1.08], [-1.84, 0.47, 1.18]];
export function sillAt(z) {
  if (z >= SILL[0][0]) return [SILL[0][1], SILL[0][2]];
  for (let i = 0; i < SILL.length - 1; i++) {
    const [z0, x0, y0] = SILL[i], [z1, x1, y1] = SILL[i + 1];
    if (z <= z0 && z >= z1) {
      const t = (z0 - z) / (z0 - z1);
      return [x0 + (x1 - x0) * t, y0 + (y1 - y0) * t];
    }
  }
  return [SILL[SILL.length - 1][1], SILL[SILL.length - 1][2]];
}

// Instrument panel frame: local X to the crew's right, Y up the (tilted) panel, Z toward the crew.
const panelFrame = (c, tilt) => Frame.facing(c, [0, Math.sin(tilt * deg), -Math.cos(tilt * deg)], [0, 1, 0]);
// Console top frame: local X to the crew's right, Y forward, Z up.
const topFrame = (c, n = [0, 1, 0]) => Frame.facing(c, n, [0, 0, 1]);

// Panel outline with the top corners cut to clear the canopy.
const chamfered = (w, h, ch) => [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2 - ch], [w / 2 - ch, h / 2], [-w / 2 + ch, h / 2], [-w / 2, h / 2 - ch]];

// Side profile (z, y) extruded across X.
function profileSolid(g, pts, halfW) {
  const F = new Frame([0, 0, 0], [0, 0, 1], [0, 1, 0], [-1, 0, 0]);
  extrude(g, F, pts, halfW * 2);
}

// opts.canopy: "full" builds the canopy's glass and frames; "doors" leaves them to the exterior model
// (exterior/), keeping just the two crew doors' pivots - the operable nodes the door glass hangs from.
export function buildCockpit(ctx, opts = {}) {
  const M = ctx.M;
  const root = new Node("AH64_Cockpit");
  root.extras = {
    units: "metres",
    axes: "glTF: +Y up, +Z toward the nose, +X to the crew's left",
    origin: "front cockpit floor, centreline, under the CPG seat back",
  };
  const shell = root.child("Cockpit_Shell");
  structure(ctx, shell);
  canopy(ctx, root, (opts.canopy || "full") === "full");
  const cpg = root.child("CPG_Station");
  cpgStation(ctx, cpg);
  const plt = root.child("Pilot_Station");
  pilotStation(ctx, plt);
  return root;
}

// ---- tub, floors, bulkheads, consoles, panel housings ------------------------------------------------------------------------
function structure(ctx, node) {
  const M = ctx.M;
  const inward = (c, n) => n[0] * Math.sign(c[0]) < 0;
  // side walls, from the floor up to the canopy sill
  const zs = [1.0, 0.98, 0.7, 0.4, 0.1, -0.14, -0.3, -0.34, -0.34, -0.46, -0.8, -1.2, -1.6, -1.84];
  for (const sx of [1, -1]) {
    let stepSeen = false;
    const rings = zs.map((z) => {
      const [xs, ys] = sillAt(z);
      let rear = z < -0.34;
      if (z === -0.34) {
        rear = stepSeen;
        stepSeen = true;
      }
      const fy = rear ? 0.46 : 0;
      const fx = rear ? 0.36 : 0.34;
      return [[sx * (xs - 0.03), ys - 0.004, z], [sx * (xs - 0.042), ys - 0.1, z], [sx * (fx + 0.02), fy + 0.12, z], [sx * fx, fy, z]];
    });
    loft(node.g(M.paint), rings, { orient: inward });
    // A ledge along the top of the wall, out to the glass.
    const ledge = zs.filter((z, i) => zs.indexOf(z) === i).map((z) => {
      const [xs, ys] = sillAt(z);
      return [[sx * (xs - 0.03), ys - 0.004, z], [sx * (xs + 0.005), ys - 0.004, z]];
    });
    loft(node.g(M.dark), ledge, { orient: (c, n) => n[1] > 0 });
  }
  // floors
  face(node.g(M.floor), [[0.34, 0, 1.0], [-0.34, 0, 1.0], [-0.34, 0, -0.34], [0.34, 0, -0.34]], [0, 1, 0]);
  face(node.g(M.floor), [[0.36, 0.46, -0.34], [-0.36, 0.46, -0.34], [-0.36, 0.46, -1.84], [0.36, 0.46, -1.84]], [0, 1, 0]);
  // floor rails and tie-downs
  for (const [y, z0, z1] of [[0, -0.3, 0.95], [0.46, -1.8, -0.38]]) {
    for (const sx of [1, -1]) box(node.g(M.darkMetal), Frame.at([sx * 0.24, y + 0.006, (z0 + z1) / 2]), [0.03, 0.012, z1 - z0]);
  }
  // footwell bulkhead under the CPG panel
  face(node.g(M.paint), [[0.34, 0, 1.0], [0.345, 0.45, 1.0], [-0.345, 0.45, 1.0], [-0.34, 0, 1.0]], [0, 0, -1]);
  // the step between the cockpits, behind the CPG seat
  box(node.g(M.paint), Frame.at([0, 0.23, -0.29]), [0.72, 0.46, 0.1]);
  // pilot's rear bulkhead and the canopy's back wall
  face(node.g(M.paint), [[0.36, 0.46, -1.84], [0.462, 1.17, -1.84], [-0.462, 1.17, -1.84], [-0.36, 0.46, -1.84]], [0, 0, 1]);
  face(node.g(M.paint), [Lf("R2"), Lf("E"), Rt("E"), Rt("R2")], v3.cross(v3.sub(Rt("E"), Lf("E")), v3.sub(Lf("R2"), Lf("E"))), { back: true });
  // equipment bay door and a first aid kit on the rear bulkhead
  box(node.g(M.dark), Frame.at([0, 1.34, -1.76]), [0.34, 0.2, 0.02]);
  box(node.g(M.cushion), Frame.at([0.28, 1.28, -1.8]), [0.12, 0.16, 0.07]);
  // consoles
  const consoles = [
    [0.58, 0.26, 0.42, -0.12, 0.66, 0],
    [1.0, 0.27, 0.44, -1.72, -0.78, 0.46],
  ];
  for (const [top, x0, x1, z0, z1, fy] of consoles) {
    for (const sx of [1, -1]) {
      box(node.g(M.paint), Frame.at([sx * (x0 + x1) / 2, (top + fy) / 2, (z0 + z1) / 2]), [x1 - x0, top - fy, z1 - z0]);
      // a rolled edge along the inboard side
      rod(node.g(M.dark), [sx * (x0 + 0.004), top - 0.012, z0 + 0.01], [sx * (x0 + 0.004), top - 0.012, z1 - 0.01], 0.012, 10);
    }
  }
  // CPG panel housing and glareshield
  profileSolid(node.g(M.dark), [[0.727, 0.41], [0.872, 0.95], [0.845, 0.954], [0.845, 0.968], [0.975, 0.8], [1.0, 0.78], [1.0, 0.44]], 0.33);
  box(node.g(M.dark), Frame.at([0, 0.57, 0.9]), [0.78, 0.26, 0.2]);
  // pilot panel housing, glareshield and the KU pedestal
  profileSolid(node.g(M.dark), [[-0.795, 0.858], [-0.708, 0.955], [-0.612, 1.405], [-0.645, 1.408], [-0.645, 1.425], [-0.28, 1.425], [-0.28, 0.8], [-0.6, 0.8]], 0.33);
  box(node.g(M.dark), Frame.at([0, 1.0, -0.48]), [0.78, 0.4, 0.36]);
  // pilot footwell front wall (the back of the step)
  face(node.g(M.paint), [[0.36, 0.46, -0.34], [0.37, 0.8, -0.34], [-0.37, 0.8, -0.34], [-0.36, 0.46, -0.34]], [0, 0, -1]);
  // blast shield between the cockpits
  const bz = -0.265;
  const bs = [[0.31, 1.426, bz], [0.265, 1.615, bz], [-0.265, 1.615, bz], [-0.31, 1.426, bz]];
  face(node.g(M.glass), bs, [0, 0, -1]);
  for (let i = 0; i < 4; i++) beam(node.g(M.frame), bs[i], bs[(i + 1) % 4], 0.022, 0.018, [0, 0, 1], { extend: 0.02 });
}

// ---- canopy: flat transparencies in a frame; both crew doors are on the right ------------------------------------------------------
function canopy(ctx, root, full = true) {
  const M = ctx.M;
  const node = root.child("Canopy");
  const ctr = [0, 1.05, -0.4];
  const out = (pts) => {
    const c = pts.reduce((a, p) => v3.add(a, p), [0, 0, 0]).map((x) => x / pts.length);
    let n = v3.norm(v3.cross(v3.sub(pts[1], pts[0]), v3.sub(pts[2], pts[0])));
    if (v3.dot(n, v3.sub(c, ctr)) < 0) n = v3.mul(n, -1);
    return n;
  };
  const panes = {
    windscreen: [Lf("A"), Rt("A"), Rt("B"), Lf("B")],
    frontRoof: [Lf("B"), Rt("B"), Rt("C"), Lf("C")],
    pilotScreen: [Lf("C"), Rt("C"), Rt("D"), Lf("D")],
    rearRoof: [Lf("D"), Rt("D"), Rt("E"), Lf("E")],
    frontLeft: [Lf("A"), Lf("B"), Lf("C"), Lf("Q")],
    rearLeft: [Lf("Q"), Lf("C"), Lf("D"), Lf("E"), Lf("R2"), Lf("R1")],
    frontRight: [Rt("A"), Rt("B"), Rt("C"), Rt("Q")],
    rearRight: [Rt("Q"), Rt("C"), Rt("D"), Rt("E"), Rt("R2"), Rt("R1")],
  };
  const N = Object.fromEntries(Object.entries(panes).map(([k, p]) => [k, out(p)]));
  if (full) {
    const glass = node.child("Canopy_Glass");
    for (const k of ["windscreen", "frontRoof", "pilotScreen", "rearRoof", "frontLeft", "rearLeft"]) face(glass.g(M.glass), panes[k], N[k]);
  }
  // frame members: [from, to, panes it borders]
  const W = 0.05, T = 0.034;
  const members = [
    [Lf("A"), Rt("A"), ["windscreen"]],
    [Lf("A"), Lf("B"), ["windscreen", "frontLeft"]],
    [Rt("A"), Rt("B"), ["windscreen", "frontRight"]],
    [Lf("B"), Rt("B"), ["windscreen", "frontRoof"]],
    [Lf("B"), Lf("C"), ["frontRoof", "frontLeft"]],
    [Rt("B"), Rt("C"), ["frontRoof", "frontRight"]],
    [Lf("C"), Rt("C"), ["frontRoof", "pilotScreen"]],
    [Lf("C"), Lf("Q"), ["frontLeft", "rearLeft"]],
    [Rt("C"), Rt("Q"), ["frontRight", "rearRight"]],
    [Lf("C"), Lf("D"), ["pilotScreen", "rearLeft"]],
    [Rt("C"), Rt("D"), ["pilotScreen", "rearRight"]],
    [Lf("D"), Rt("D"), ["pilotScreen", "rearRoof"]],
    [Lf("D"), Lf("E"), ["rearRoof", "rearLeft"]],
    [Rt("D"), Rt("E"), ["rearRoof", "rearRight"]],
    [Lf("E"), Rt("E"), ["rearRoof"]],
    [Lf("E"), Lf("R2"), ["rearLeft"]],
    [Rt("E"), Rt("R2"), ["rearRight"]],
    [Lf("A"), Lf("Q"), ["frontLeft"]],
    [Lf("Q"), Lf("R1"), ["rearLeft"]],
    [Lf("R1"), Lf("R2"), ["rearLeft"]],
  ];
  const frames = node.child(full ? "Canopy_Frame" : "Canopy_Handles");
  for (const [a, b, ps] of full ? members : []) {
    const n = v3.norm(ps.reduce((acc, p) => v3.add(acc, N[p]), [0, 0, 0]));
    beam(frames.g(M.frame), a, b, W, T, n, { extend: 0.035 });
  }
  // Doors: hinged along their top rail, so a door node turns about its local X; +1.15 is fully open.
  const door = (name, fn, pane, hingeA, hingeB, sillA, sillB) => {
    const F = Frame.along(v3.mid(hingeA, hingeB), v3.sub(hingeB, hingeA), N[pane]);
    const d = operable(ctx, node, name, F, F, { control: "door", label: name.replace(/_/g, " "), fn, motion: "rotate", axis: [1, 0, 0], positions: ["CLOSED", "OPEN"], angles: [0, 1.15], state: 0 });
    if (!full) return d;
    face(d.g(M.glass), panes[pane], N[pane]);
    for (let i = 0; i < sillA.length - 1; i++) beam(d.g(M.frame), sillA[i], sillA[i + 1], W * 0.9, T, N[pane], { extend: 0.03 });
    // latch handle inside
    const hp = v3.add(v3.lerp(sillB[0], sillB[1], 0.5), [0.05, 0.08, 0]);
    tube(d.g(M.darkMetal), bezier([v3.add(hp, [0, 0, -0.045]), v3.add(hp, [0.025, 0.006, -0.04]), v3.add(hp, [0.025, 0.006, 0.04]), v3.add(hp, [0, 0, 0.045])], 8), 0.0045, 8, { caps: true });
    return d;
  };
  door("Canopy_Door_CPG", "doorCpg", "frontRight", Rt("B"), Rt("C"), [Rt("A"), Rt("Q")], [Rt("A"), Rt("Q")]);
  door("Canopy_Door_Pilot", "doorPilot", "rearRight", Rt("C"), Rt("E"), [Rt("Q"), Rt("R1"), Rt("R2")], [Rt("R1"), Rt("R2")]);
  // grab handles on the left posts
  for (const [a, b] of [[Lf("A"), Lf("B")], [Lf("C"), Lf("D")]]) {
    const p0 = v3.add(v3.lerp(a, b, 0.4), [-0.03, 0, -0.012]);
    const p1 = v3.add(v3.lerp(a, b, 0.62), [-0.03, 0, -0.012]);
    const inn = [-0.03, 0, 0];
    tube(frames.g(M.frame), bezier([p0, v3.add(p0, inn), v3.add(p1, inn), p1], 10), 0.007, 8, { caps: true });
  }
  // wire strike cutter above the canopy
  if (full) {
    const wc = [[0, 1.5, -0.12], [0, 1.6, 0.06], [0, 1.53, 0.08], [0, 1.47, -0.08]];
    face(frames.g(M.darkMetal), wc, [1, 0, 0], { back: true });
  }
  return node;
}


// ---- stations ------------------------------------------------------------------------------------------------------------------------
// Controls carry an `fn`: the id a simulation uses for what the control does.
const CONSOLE_Y = { cpg: 0.58, plt: 1.0 };

function consolePanels(ctx, node, sx, xc, top, zFront, list) {
  let z = zFront;
  for (const spec of list) {
    const c = [sx * xc, top + 0.003, z - spec.h / 2];
    panel(ctx, node, topFrame(c), spec);
    if (spec.after) spec.after(topFrame(c));
    z -= spec.h + 0.004;
  }
}

const volumeKnobs = (w, pre) => ["VHF", "UHF", "FM1", "FM2", "HF", "IFF"].map((n, i) => ({ k: "knob", x: w * (0.2 + (i % 3) * 0.3), y: 0.028 + Math.floor(i / 3) * 0.042, r: 0.0055, label: n, ticks: 7, arc: true, labelDy: 0.0125, fn: `${pre}vol.${n}` }));
const lit = (text, color, o = {}) => ({ k: "pb", text, lit: true, fg: color, glowColor: color, ...o });

function cpgStation(ctx, st) {
  const M = ctx.M;
  ctx.station = "CPG";
  const Fp = panelFrame([0, 0.68, 0.8], 15);
  const W = 0.8, H = 0.56;
  extrude(st.g(M.dark), Fp.move(0, 0, -0.012), chamfered(W, H, 0.07), 0.024);
  tedac(ctx, st, Fp.move(0, 0.13, 0));
  mpd(ctx, st, Fp.move(-0.265, -0.06, 0), "CPG_MPD_Left", "WPN");
  mpd(ctx, st, Fp.move(0.265, -0.06, 0), "CPG_MPD_Right", "ENG");
  keyboard(ctx, st, Fp.move(0, -0.145, 0.004).rotX(-12 * deg), "CPG_KU");
  eufd(ctx, st, Fp.move(-0.245, 0.18, 0), "CPG_EUFD");
  panel(ctx, st, Fp.move(0.245, 0.18, 0.003), {
    w: 0.2, h: 0.1, title: "ARMAMENT",
    ctl: [
      { ...lit("ARM\nSAFE", "#ffd23a", { litOn: true, fn: "masterArm" }), x: 0.035, y: 0.045, w: 0.026, h: 0.022, name: "MASTER ARM" },
      { k: "pb", x: 0.08, y: 0.045, w: 0.024, h: 0.02, text: "GND\nORIDE", fn: "gndOride", latching: true },
      { k: "toggle", x: 0.125, y: 0.05, label: "SIGHT", pos: ["TADS", "FCR"], fn: "sight" },
      { k: "toggle", x: 0.165, y: 0.05, label: "LRFD", pos: ["1ST", "LST"], fn: "lrfdMode" },
      { k: "knob", x: 0.05, y: 0.083, r: 0.005, label: "", name: "SYMBOL BRT TEDAC", ticks: 5, fn: "symBrtTedac" },
      { k: "label", x: 0.1, y: 0.085, text: "SYMBOL BRT", size: 0.0034 },
      { k: "knob", x: 0.15, y: 0.083, r: 0.005, label: "", name: "SYMBOL BRT IHADSS", ticks: 5, fn: "symBrtIhadss" },
    ],
  });
  panel(ctx, st, Fp.move(-0.27, -0.237, 0.003), {
    w: 0.19, h: 0.07, title: "VIDEO",
    ctl: [
      { k: "knob", x: 0.035, y: 0.037, r: 0.0055, label: "GAIN", ticks: 7, arc: true, value: 0.5, fn: "tedacGain" },
      { k: "knob", x: 0.085, y: 0.037, r: 0.0055, label: "LEVEL", ticks: 7, arc: true, value: 0.5, fn: "tedacLevel" },
      { k: "toggle", x: 0.135, y: 0.042, label: "POL", pos: ["WHT", "BLK"], fn: "flirPol" },
      { k: "toggle", x: 0.17, y: 0.042, label: "DVO", pos: ["ON", "OFF"], fn: "dvo" },
    ],
  });
  panel(ctx, st, Fp.move(0.27, -0.237, 0.003), {
    w: 0.19, h: 0.07, title: "TADS",
    ctl: [
      { k: "knob", x: 0.04, y: 0.04, r: 0.006, label: "PWR", stops: ["OFF", "STBY", "ON"], sel: 2, fn: "tadsPower", labelDy: 0.021 },
      { k: "toggle", x: 0.1, y: 0.042, label: "FLIR", pos: ["ON", "OFF"], fn: "flirPower" },
      { k: "toggle", x: 0.14, y: 0.042, label: "DTV", pos: ["ON", "OFF"], fn: "dtvPower" },
      { k: "toggle", x: 0.175, y: 0.042, label: "LSR", pos: ["ARM", "SAFE"], state: 1, fn: "laserArm" },
    ],
  });
  const top = CONSOLE_Y.cpg;
  consolePanels(ctx, st, 1, 0.34, top, 0.64, [
    { w: 0.15, h: 0.08, title: "NVS", ctl: [{ k: "knob", x: 0.045, y: 0.045, r: 0.0065, stops: ["OFF", "NORM", "FIXED"], sel: 1, label: "MODE", labelDy: 0.022, fn: "cpgNvsMode" }, { k: "toggle", x: 0.105, y: 0.047, label: "ACM", pos: ["ON", "OFF"], fn: "acm" }] },
    { w: 0.15, h: 0.11, title: "COMM", ctl: volumeKnobs(0.15, "cpg.") },
    { w: 0.15, h: 0.075, title: "TADS/FCR", ctl: [{ k: "toggle", x: 0.03, y: 0.045, label: "TADS", pos: ["ON", "OFF"], fn: "tadsSw" }, { k: "toggle", x: 0.075, y: 0.045, label: "FCR", pos: ["ON", "OFF"], fn: "fcrPower" }, { k: "toggle", x: 0.12, y: 0.045, label: "RFI", pos: ["ON", "OFF"], state: 1, fn: "rfi" }] },
    { w: 0.15, h: 0.085, title: "INT LT", ctl: [{ k: "knob", x: 0.03, y: 0.042, r: 0.0055, label: "PRIMARY", ticks: 7, arc: true, fn: "cpgIntPrimary" }, { k: "knob", x: 0.075, y: 0.042, r: 0.0055, label: "FLOOD", ticks: 7, arc: true, value: 0.3, fn: "cpgIntFlood" }, { k: "knob", x: 0.12, y: 0.042, r: 0.0055, label: "STBY INST", ticks: 7, arc: true, fn: "cpgIntStby" }] },
    { w: 0.15, h: 0.12, title: "", ctl: [{ k: "grille", x: 0.02, y: 0.015, w: 0.11, h: 0.09 }, { k: "label", x: 0.075, y: 0.112, text: "MAP CASE", size: 0.0035 }] },
    { w: 0.15, h: 0.1, title: "", ctl: [{ k: "label", x: 0.075, y: 0.05, text: "CAUTION\nKEEP HANDS CLEAR\nOF COLLECTIVE", size: 0.0045 }] },
  ]);
  consolePanels(ctx, st, -1, 0.34, top, 0.64, [
    { w: 0.15, h: 0.085, title: "CMWS", ctl: [{ k: "toggle", x: 0.03, y: 0.048, label: "PWR", pos: ["ON", "OFF"], fn: "cmwsPower" }, { k: "toggle", x: 0.075, y: 0.048, label: "ARM", pos: ["ARM", "SAFE"], guard: true, state: 1, fn: "cmwsArm" }, { k: "pb", x: 0.12, y: 0.05, w: 0.02, h: 0.016, text: "BYPASS", fn: "cmwsBypass", latching: true }] },
    { w: 0.15, h: 0.09, title: "WPN CONTROL", ctl: [{ k: "knob", x: 0.045, y: 0.05, r: 0.006, stops: ["10", "20", "50", "100", "ALL"], sel: 1, label: "BURST", labelDy: 0.019, fn: "gunBurst" }, { k: "toggle", x: 0.11, y: 0.05, label: "RKT", pos: ["PD", "RKT"], fn: "rktMode" }] },
    { w: 0.15, h: 0.09, title: "DATA TRANSFER", ctl: [{ k: "slot", x: 0.075, y: 0.05, w: 0.075, h: 0.012, label: "DTC", cartridge: true, fn: "cpgDtc" }] },
    { w: 0.15, h: 0.075, title: "CANOPY JETT", ctl: [{ k: "hazard", x: 0.035, y: 0.02, w: 0.08, h: 0.045 }, { k: "tee", x: 0.075, y: 0.042, fn: "canopyJett" }] },
    { w: 0.15, h: 0.12, title: "", ctl: [{ k: "grille", x: 0.02, y: 0.015, w: 0.11, h: 0.09 }] },
    { w: 0.15, h: 0.1, title: "ICS", ctl: [{ k: "toggle", x: 0.035, y: 0.05, label: "MODE", pos: ["HOT", "PTT", "VOX"], fn: "cpgIcsMode" }, { k: "knob", x: 0.1, y: 0.048, r: 0.0055, label: "VOX", ticks: 7, arc: true, fn: "cpgIcsVox" }] },
  ]);
  seat(ctx, st, "CPG_Seat", CPG.srp);
  // The CPG's cyclic stands on the right, clear of the TEDAC. Both cockpits' flight controls are linked.
  cyclic(ctx, st, "CPG_Cyclic", [-0.19, 0.02, 0.5], { len: 0.56, lean: 0.03 });
  collective(ctx, st, "CPG_Collective", [0.255, 0.5, -0.06], [0.255, 0.59, 0.3]);
  pedals(ctx, st, "CPG_Pedal", [0, 0.07, 0.86]);
  st.child("CPG_Eye", Frame.at(CPG.eye), { marker: "design eye point; +Z forward" });
}

function tedac(ctx, st, T) {
  const M = ctx.M;
  const node = st.child("CPG_TEDAC", T);
  const W = 0.25, H = 0.26, D = 0.15, OFF = 0.018, S = 0.17;
  box(node.g(M.dark), T.move(0, 0, D / 2 - 0.004), [W, H, D - 0.008], { skip: "pz" });
  const faceCtl = [
    { k: "label", x: 0.02, y: 0.012, text: "GAIN", size: 0.0034 },
    { k: "label", x: W - 0.02, y: 0.012, text: "LEV", size: 0.0034 },
    { k: "label", x: W / 2, y: H - 0.008, text: "TEDAC", size: 0.0038 },
  ];
  const face = ctx.pa.alloc(W * 1600, H * 1600, { kind: "panel", m: [W, H], ctl: faceCtl, fasteners: false, bg: "#25282a", seed: ctx.seed++ });
  bezel(node.g(M.panels), T.move(0, 0, D - 0.004), W, H, S + 0.006, S + 0.006, 0.008, { r: 0.012, ri: 0.002, uv: face.uv, off: [0, OFF] });
  const scr = node.child("CPG_TEDAC_Screen", T.move(0, OFF, D - 0.009), { screen: "TEDAC", size_m: [S, S], note: "UV 0-1; swap the material's texture for a live render target" });
  quad(scr.g(screenMaterial(ctx, "CPG_TEDAC", "TEDAC")), scr.frame, S + 0.004, S + 0.004, { uv: [0, 0, 1, 1] });
  const hz = 0.075, top = OFF + S / 2 + 0.016;
  const Ff = T.move(0, 0, D);
  box(node.g(M.rubber), Ff.move(0, top, hz / 2).rotX(-6 * deg), [S + 0.05, 0.006, hz]);
  for (const sx of [-1, 1]) {
    const side = [[0, top], [hz, top - 0.004], [hz * 0.55, OFF - S / 2 + 0.01], [0, OFF - S / 2 - 0.01]];
    extrude(node.g(M.rubber), new Frame(Ff.point([sx * (S / 2 + 0.025), 0, 0]), Ff.z, Ff.y, v3.mul(Ff.x, -1)), side, 0.006);
  }
  // bezel keys: L1-L6 and R1-R6 top to bottom, B1-B6 left to right
  const along = (i) => ((i + 0.5) / 6) * S - S / 2;
  const btn = [];
  for (let i = 0; i < 6; i++) {
    btn.push([`L${i + 1}`, -S / 2 - 0.016, OFF + along(5 - i), 0.011, 0.017]);
    btn.push([`R${i + 1}`, S / 2 + 0.016, OFF + along(5 - i), 0.011, 0.017]);
    btn.push([`B${i + 1}`, along(i), OFF - S / 2 - 0.016, 0.017, 0.011]);
  }
  for (const [id, x, y, w, h] of btn) {
    const P = Ff.move(x, y, 0.004);
    const nd = operable(ctx, node, `CPG_TEDAC_${id}`, P, P, { control: "key", label: `TEDAC · ${id}`, fn: `tedac:${id}`, motion: "translate", axis: [0, 0, -1], travel: 0.002 });
    box(nd.g(M.panels), P, [w, h, 0.006], { uvAll: darkUV(ctx) });
  }
  // hand grips, one each side; their thumb buttons and triggers work
  for (const sx of [-1, 1]) {
    const side = sx < 0 ? "Left" : "Right";
    const mount = T.point([sx * (W / 2), -0.06, D * 0.62]);
    const g = node.child(`CPG_TEDAC_Grip_${side}`, Frame.at(mount), { note: "hand grip; its buttons and trigger are the operable parts" });
    const armEnd = T.point([sx * (W / 2 + 0.06), -0.055, D * 0.78]);
    rod(g.g(M.darkMetal), mount, armEnd, 0.013, 12);
    cyl(g.g(M.darkMetal), Frame.upAlong(mount, T.x, T.y), 0.02, 0.02, 14);
    const axis = v3.norm(T.dir([sx * 0.12, -1, 0.3]));
    const topP = v3.add(armEnd, T.dir([0, 0.01, 0]));
    const bottom = v3.add(topP, v3.mul(axis, 0.125));
    lathe(g.g(M.plastic), Frame.upAlong(bottom, v3.mul(axis, -1), T.x), [[0, 0], [0.017, 0], [0.019, 0.02], [0.022, 0.06], [0.02, 0.1], [0.019, 0.125], [0, 0.125]], 14, { smooth: true });
    const Hd = Frame.upAlong(topP, v3.mul(axis, -1), T.x).move(0, 0.012, -0.004);
    rbox(g.g(M.plastic), Hd, [0.05, 0.03, 0.055], 0.01, 2);
    const [thumb, red, trig] = sx < 0 ? [["FOV", "field of view", "tedac.fov"], ["Sensor", "sensor select", "tedac.sensor"], ["Laser", "laser trigger", "tedac.laser"]] : [["Slave", "slave", "tedac.slave"], ["Weapon_Select", "weapon select", "was"], ["Trigger", "weapon trigger", "trigger"]];
    const b = (id, label, fn, P, r, h, mat) => {
      const nd = operable(ctx, g, `CPG_TEDAC_Grip_${side}_${id}`, P, P, { control: "button", label: `TEDAC ${side.toLowerCase()} grip · ${label}`, fn, motion: "translate", axis: [0, -1, 0], travel: 0.002 });
      cyl(nd.g(mat), P, r, h, 10);
    };
    b(thumb[0], thumb[1], thumb[2], Frame.upAlong(Hd.point([sx * 0.01, 0.016, 0.012]), Hd.y, Hd.x), 0.0055, 0.006, M.metal);
    b(red[0], red[1], red[2], Frame.upAlong(Hd.point([-sx * 0.012, 0.016, 0.01]), Hd.y, Hd.x), 0.0045, 0.005, M.red);
    const Tf = Frame.upAlong(v3.add(topP, v3.add(v3.mul(axis, 0.02), T.dir([0, 0, -0.022]))), v3.mul(axis, -1), T.x);
    const tn = operable(ctx, g, `CPG_TEDAC_Grip_${side}_${trig[0]}`, Tf, Tf, { control: "trigger", label: `TEDAC ${side.toLowerCase()} grip · ${trig[1]}`, fn: trig[2], motion: "rotate", axis: [1, 0, 0], positions: ["RELEASED", "PULLED"], angles: [0, 0.3], state: 0, momentary: [1], spring: 0 });
    box(tn.g(M.metal), Tf.move(0, -0.015, 0).rotX(12 * deg), [0.012, 0.028, 0.006]);
  }
  return node;
}

function pilotStation(ctx, st) {
  const M = ctx.M;
  ctx.station = "Pilot";
  const Fr = panelFrame([0, 1.18, -0.66], 12);
  const W = 0.78, H = 0.46;
  extrude(st.g(M.dark), Fr.move(0, 0, -0.012), chamfered(W, H, 0.06), 0.024);
  mpd(ctx, st, Fr.move(-0.145, -0.02, 0), "Pilot_MPD_Left", "FLT");
  mpd(ctx, st, Fr.move(0.145, -0.02, 0), "Pilot_MPD_Right", "TSD");
  eufd(ctx, st, Fr.move(0, 0.165, 0), "Pilot_EUFD");
  pushButton(ctx, st, Fr.move(-0.16, 0.172, 0), { w: 0.032, h: 0.028, text: "MASTER\nWARNING", lit: true, fg: "#ff4a36", glowColor: "#ff4a36", bg: "#141414", fn: "mwarn" }, "Pilot_Master_Warning", "MASTER WARNING");
  pushButton(ctx, st, Fr.move(0.16, 0.172, 0), { w: 0.032, h: 0.028, text: "MASTER\nCAUTION", lit: true, fg: "#ffb020", glowColor: "#ffb020", bg: "#141414", fn: "mcaut" }, "Pilot_Master_Caution", "MASTER CAUTION");
  panel(ctx, st, Fr.move(-0.325, 0.135, 0.003), {
    w: 0.11, h: 0.085, title: "ARM",
    ctl: [
      { ...lit("ARM\nSAFE", "#ffd23a", { litOn: true, fn: "masterArm" }), x: 0.03, y: 0.042, w: 0.026, h: 0.022, name: "MASTER ARM" },
      { k: "pb", x: 0.08, y: 0.042, w: 0.024, h: 0.02, text: "GND\nORIDE", fn: "gndOride", latching: true },
      { k: "label", x: 0.055, y: 0.073, text: "MASTER ARM", size: 0.0034 },
    ],
  });
  panel(ctx, st, Fr.move(-0.325, 0.025, 0.003), {
    w: 0.11, h: 0.125, title: "JETTISON",
    ctl: [
      { k: "hazard", x: 0.008, y: 0.014, w: 0.094, h: 0.004 },
      { k: "pb", x: 0.03, y: 0.04, w: 0.022, h: 0.016, text: "L\nOUTBD", fn: "jett.LO" },
      { k: "pb", x: 0.08, y: 0.04, w: 0.022, h: 0.016, text: "R\nOUTBD", fn: "jett.RO" },
      { k: "pb", x: 0.03, y: 0.072, w: 0.022, h: 0.016, text: "L\nINBD", fn: "jett.LI" },
      { k: "pb", x: 0.08, y: 0.072, w: 0.022, h: 0.016, text: "R\nINBD", fn: "jett.RI" },
      { k: "pb", x: 0.055, y: 0.103, w: 0.04, h: 0.016, text: "EMERG", fg: "#ff5a4a", fn: "jett.ALL" },
    ],
  });
  panel(ctx, st, Fr.move(-0.325, -0.105, 0.003), {
    w: 0.11, h: 0.12, title: "NVS MODE",
    ctl: [
      { k: "knob", x: 0.055, y: 0.05, r: 0.0075, stops: ["OFF", "NORM", "FIXED"], sel: 1, style: "bar", label: "", name: "MODE", fn: "nvsMode" },
      { k: "toggle", x: 0.03, y: 0.1, label: "", name: "SENSOR", pos: ["PNVS", "TADS"], fn: "nvsSensor" },
      { k: "knob", x: 0.085, y: 0.098, r: 0.005, label: "BRT", labelDy: -0.009, fn: "ihadssBrt" },
    ],
  });
  gauge(ctx, st, Fr.move(0.33, 0.148, 0), "Pilot_Standby_ADI", "ADI", 0.06);
  gauge(ctx, st, Fr.move(0.33, 0.057, 0), "Pilot_Standby_ASI", "ASI", 0.056);
  gauge(ctx, st, Fr.move(0.33, -0.033, 0), "Pilot_Standby_ALT", "ALT", 0.056);
  gauge(ctx, st, Fr.move(0.33, -0.12, 0), "Pilot_Clock", "CLOCK", 0.044);
  vent(ctx, st, Fr.move(-0.33, -0.2, 0), "Pilot_Vent_Left", "Air vent, left");
  vent(ctx, st, Fr.move(0.33, -0.2, 0), "Pilot_Vent_Right", "Air vent, right");
  const Fk = Fr.move(0, -H / 2, 0).rotX(-30 * deg).move(0, -0.065, 0);
  keyboard(ctx, st, Fk.move(0, 0, 0.001), "Pilot_KU");
  // fire panel on the glareshield
  const Ff = Frame.facing([0, 1.438, -0.56], [0, 0.94, -0.34], [0, 0, 1]);
  box(st.g(M.dark), Ff.move(0, 0, -0.01), [0.31, 0.085, 0.02]);
  panel(ctx, st, Ff.move(0, 0, 0.001), {
    w: 0.3, h: 0.075, title: "FIRE", titleY: 0.0055,
    ctl: [
      { ...lit("ENG 1\nFIRE", "#ff4a36", { fn: "fire1" }), x: 0.04, y: 0.043, w: 0.036, h: 0.03 },
      { ...lit("APU\nFIRE", "#ff4a36", { fn: "fireApu" }), x: 0.15, y: 0.043, w: 0.036, h: 0.03 },
      { ...lit("ENG 2\nFIRE", "#ff4a36", { fn: "fire2" }), x: 0.26, y: 0.043, w: 0.036, h: 0.03 },
      { k: "pb", x: 0.095, y: 0.043, w: 0.024, h: 0.018, text: "DISCH\nPRI", fn: "dischPri" },
      { k: "pb", x: 0.205, y: 0.043, w: 0.024, h: 0.018, text: "DISCH\nRES", fn: "dischRes" },
      { k: "label", x: 0.095, y: 0.066, text: "TEST 1", size: 0.003 },
      { k: "label", x: 0.205, y: 0.066, text: "TEST 2", size: 0.003 },
    ],
  });
  // the standby compass hangs off the right windscreen post; its card is a live display
  const Fc = Frame.facing([-0.19, 1.6, -0.34], [0.19, 0, -1]);
  box(st.g(M.dark), Fc.move(0, 0, -0.022), [0.075, 0.05, 0.044]);
  rod(st.g(M.dark), Fc.point([-0.02, 0.025, -0.022]), [-0.245, 1.72, -0.34], 0.006, 8);
  const cs = st.child("Pilot_Compass_Screen", Fc.move(0, 0, 0.0005), { screen: "COMPASS", drive: "card showing the heading" });
  quad(cs.g(screenMaterial(ctx, "Pilot_Compass", "COMPASS", 256, 128)), cs.frame, 0.05, 0.025, { uv: [0, 0, 1, 1] });
  const top = CONSOLE_Y.plt;
  const quadrant = [
    { k: "slot", x: 0.035, y: 0.075, w: 0.008, h: 0.12, label: "ENG 1", marks: [{ t: 0.06, text: "FLY" }, { t: 0.55, text: "IDLE" }, { t: 0.95, text: "OFF" }] },
    { k: "slot", x: 0.09, y: 0.075, w: 0.008, h: 0.12, label: "ENG 2", marks: [{ t: 0.06, text: "FLY" }, { t: 0.55, text: "IDLE" }, { t: 0.95, text: "OFF" }] },
    { k: "slot", x: 0.135, y: 0.09, w: 0.008, h: 0.075, label: "RTR BRK", marks: [{ t: 0.1, text: "OFF", side: "left" }, { t: 0.5, text: "BRK", side: "left" }, { t: 0.9, text: "LOCK", side: "left" }] },
  ];
  // slot positions, measured from the panel's top edge (forward is up the panel)
  const eng = [-(0.015 + 0.95 * 0.12), -(0.015 + 0.55 * 0.12), -(0.015 + 0.06 * 0.12)];
  consolePanels(ctx, st, 1, 0.355, top, -0.8, [
    { w: 0.16, h: 0.17, title: "POWER", ctl: quadrant, titleY: 0.006, after: (F) => {
      levers(ctx, st, F.move(-0.08, 0.085, 0), [
        { name: "Pilot_Power_Lever_1", label: "POWER · ENG 1", fn: "pwr1", x: 0.035, positions: ["OFF", "IDLE", "FLY"], slotY: eng, hingeY: -0.075, state: 2 },
        { name: "Pilot_Power_Lever_2", label: "POWER · ENG 2", fn: "pwr2", x: 0.09, positions: ["OFF", "IDLE", "FLY"], slotY: eng, hingeY: -0.075, state: 2 },
        { name: "Pilot_Rotor_Brake", label: "POWER · ROTOR BRAKE", fn: "rtrBrk", x: 0.135, positions: ["OFF", "BRK", "LOCK"], slotY: [-0.06, -0.09, -0.12], hingeY: -0.09, state: 0, color: "red" },
      ]);
    } },
    { w: 0.16, h: 0.1, title: "FUEL", ctl: [{ k: "knob", x: 0.035, y: 0.052, r: 0.007, stops: ["NORM", "AFT", "FWD"], sel: 0, style: "bar", label: "", name: "XFEED", fn: "xfeed" }, { k: "toggle", x: 0.085, y: 0.052, label: "BOOST", pos: ["ON", "OFF"], state: 1, fn: "boost" }, { k: "toggle", x: 0.128, y: 0.052, label: "TRANS", pos: ["FWD", "OFF", "AFT"], fn: "fuelTrans" }] },
    { w: 0.16, h: 0.1, title: "ENG START", ctl: [{ k: "toggle", x: 0.03, y: 0.052, label: "ENG 1", pos: ["START", "OFF", "IGN OR"], state: 1, spring: 1, fn: "eng1Start" }, { k: "toggle", x: 0.075, y: 0.052, label: "ENG 2", pos: ["START", "OFF", "IGN OR"], state: 1, spring: 1, fn: "eng2Start" }, { ...lit("APU\nON", "#5dff7a", { fn: "apu" }), x: 0.128, y: 0.052, w: 0.022, h: 0.022, name: "APU" }] },
    { w: 0.16, h: 0.11, title: "COMM", ctl: volumeKnobs(0.16, "") },
    { w: 0.16, h: 0.08, title: "ANTI-ICE", ctl: [{ k: "toggle", x: 0.035, y: 0.045, label: "INLET", pos: ["ON", "OFF"], state: 1, fn: "aiInlet" }, { k: "toggle", x: 0.08, y: 0.045, label: "TADS", pos: ["ON", "OFF"], state: 1, fn: "aiTads" }, { k: "toggle", x: 0.125, y: 0.045, label: "WSHLD", pos: ["ON", "OFF"], state: 1, fn: "aiWshld" }] },
    { w: 0.16, h: 0.14, title: "", ctl: [{ k: "grille", x: 0.02, y: 0.02, w: 0.12, h: 0.1 }] },
  ]);
  consolePanels(ctx, st, -1, 0.355, top, -0.8, [
    { w: 0.16, h: 0.1, title: "EXT LT", ctl: [{ k: "knob", x: 0.03, y: 0.05, r: 0.0055, stops: ["OFF", "BRT", "DIM"], sel: 1, label: "NAV", labelDy: 0.017, fn: "navLt" }, { k: "knob", x: 0.08, y: 0.05, r: 0.0055, stops: ["OFF", "WHT", "RED"], sel: 2, label: "A-COL", labelDy: 0.017, fn: "acolLt" }, { k: "knob", x: 0.13, y: 0.05, r: 0.0055, ticks: 7, arc: true, label: "FORM", labelDy: 0.017, value: 0, fn: "formLt" }] },
    { w: 0.16, h: 0.1, title: "INT LT", ctl: [{ k: "knob", x: 0.03, y: 0.045, r: 0.0055, label: "PRIMARY", ticks: 7, arc: true, fn: "intPrimary" }, { k: "knob", x: 0.075, y: 0.045, r: 0.0055, label: "STBY", ticks: 7, arc: true, fn: "intStby" }, { k: "knob", x: 0.12, y: 0.045, r: 0.0055, label: "FLOOD", ticks: 7, arc: true, value: 0.3, fn: "intFlood" }, { k: "toggle", x: 0.145, y: 0.08, label: "MODE", pos: ["DAY", "NT"], fn: "intMode" }] },
    { w: 0.16, h: 0.09, title: "DATA TRANSFER", ctl: [{ k: "slot", x: 0.08, y: 0.05, w: 0.075, h: 0.012, label: "DTC", cartridge: true, fn: "dtc" }] },
    { w: 0.16, h: 0.08, title: "TAIL WHEEL", ctl: [{ ...lit("LOCK", "#5dff7a", { litOn: true, fn: "tailWheel" }), x: 0.045, y: 0.045, w: 0.026, h: 0.022, name: "LOCK" }, { k: "pb", x: 0.11, y: 0.045, w: 0.03, h: 0.022, text: "PARK\nBRAKE", fn: "parkBrake", latching: true }] },
    { w: 0.16, h: 0.075, title: "CANOPY JETT", ctl: [{ k: "hazard", x: 0.04, y: 0.02, w: 0.08, h: 0.045 }, { k: "tee", x: 0.08, y: 0.042, fn: "canopyJett" }] },
    { w: 0.16, h: 0.09, title: "IFF", ctl: [{ k: "knob", x: 0.045, y: 0.05, r: 0.0065, stops: ["OFF", "STBY", "NORM", "EMER"], sel: 2, style: "bar", label: "", name: "MASTER", labelDy: 0.02, fn: "iffMaster" }, { k: "toggle", x: 0.1, y: 0.05, label: "M4", pos: ["A", "B"], fn: "iffM4" }, { k: "toggle", x: 0.135, y: 0.05, label: "ANT", pos: ["TOP", "BOT"], fn: "iffAnt" }] },
    { w: 0.16, h: 0.1, title: "ICS", ctl: [{ k: "toggle", x: 0.035, y: 0.05, label: "MODE", pos: ["HOT", "PTT", "VOX"], fn: "icsMode" }, { k: "knob", x: 0.1, y: 0.048, r: 0.0055, label: "VOX", ticks: 7, arc: true, fn: "icsVox" }] },
  ]);
  seat(ctx, st, "Pilot_Seat", PLT.srp);
  cyclic(ctx, st, "Pilot_Cyclic", [0, 0.49, -0.98], { len: 0.58, lean: 0.07 });
  collective(ctx, st, "Pilot_Collective", [0.258, 0.9, -1.58], [0.258, 1.0, -1.12]);
  pedals(ctx, st, "Pilot_Pedal", [0, 0.53, -0.62]);
  st.child("Pilot_Eye", Frame.at(PLT.eye), { marker: "design eye point; +Z forward" });
}
