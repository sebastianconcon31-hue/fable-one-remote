// The outside of the aircraft, at 1:1 scale: fuselage and tail, stub wings
// with their stores, engine nacelles, rotor pylon, main and tail rotors, the
// Longbow radome, sensor turrets, gun, landing gear and lights.
//
// The key dimensions come from published AH-64D figures (SPEC below), and
// generate.mjs measures the finished model against them.
import { v3, Frame, loft, lathe, cyl, rod, box, rbox, quad, sphere, extrude } from "./geo.mjs";
import { sillAt } from "./cockpit.mjs";
import { region, operable } from "./parts.mjs";

const deg = Math.PI / 180;

// Published AH-64D dimensions, metres.
export const SPEC = {
  fuselageLength: 14.97,
  lengthRotorsTurning: 17.73,
  mainRotorDiameter: 14.63,
  tailRotorDiameter: 2.79,
  wingspan: 5.227,
  wheelTrack: 2.03,
  wheelbase: 10.59,
  heightToRotorHead: 3.87,
  heightToFcr: 4.95,
};

// Where those put things, in model coordinates (the origin is the front cockpit floor).
export const GROUND_Y = -0.95; // bottom of the wheels
export const NOSE_Z = 2.54; // front of the TADS turret
export const TAIL_Z = NOSE_Z - SPEC.fuselageLength; // trailing edge of the fin
export const MAIN_WHEEL = [SPEC.wheelTrack / 2, -0.62, -1.6];
export const TAIL_WHEEL_Z = MAIN_WHEEL[2] - SPEC.wheelbase;
const R_MAIN = SPEC.mainRotorDiameter / 2;
const R_TAIL = SPEC.tailRotorDiameter / 2;
const HUB_H = 0.22;
export const TAIL_HUB = [0.2, 2.25, -11.9];
export const HUB = [0, GROUND_Y + SPEC.heightToRotorHead - HUB_H / 2, TAIL_HUB[2] - R_TAIL + SPEC.lengthRotorsTurning - R_MAIN];
const FCR_TOP = GROUND_Y + SPEC.heightToFcr;
const WING_TIP = SPEC.wingspan / 2;

export function buildExterior(ctx, root) {
  const M = ctx.M;
  const ext = root.child("Exterior", undefined, { note: "the whole aircraft at 1:1; see SPEC in lib/exterior.mjs for the published dimensions it's built to" });
  root.child("Ground_Reference", Frame.at([0, GROUND_Y, 0]), { marker: "ground level under the wheels" });
  fuselage(ctx, ext);
  sensors(ctx, ext);
  gun(ctx, ext);
  for (const sx of [1, -1]) wing(ctx, ext, sx);
  for (const sx of [1, -1]) nacelle(ctx, ext, sx);
  pylonAndRotor(ctx, ext);
  tail(ctx, ext);
  gear(ctx, ext);
  lights(ctx, ext);
  return ext;
}

function fuselage(ctx, ext) {
  const M = ctx.M;
  const skin = ext.child("Fuselage");
  const g = skin.g(M.ext);
  const outward = (axisY) => (c, n) => v3.dot(n, [c[0], c[1] - axisY, 0]) > 0;
  // Each ring: top/sill, widest point, chine, bottom corner - left side, then mirrored.
  const ring = (z, [sx, sy], [mx, my], cy, [bx, by]) => {
    const L = [[sx, sy, z], [mx, my, z], [mx - 0.035, cy, z], [bx, by, z]];
    return [...L, ...L.slice().reverse().map((p) => [-p[0], p[1], p[2]])];
  };
  const nose = [
    ring(2.2, [0.07, 0.2], [0.15, 0.05], -0.1, [0.08, -0.16]),
    ring(1.95, [0.17, 0.4], [0.26, 0.15], -0.16, [0.13, -0.28]),
    ring(1.6, [0.27, 0.58], [0.37, 0.25], -0.22, [0.17, -0.36]),
    ring(1.25, [0.34, 0.71], [0.45, 0.3], -0.26, [0.2, -0.4]),
    ring(0.98, [0.395, 0.8], [0.5, 0.35], -0.28, [0.22, -0.42]),
  ];
  loft(g, nose, { closed: true, orient: outward(0.2), capStart: [0, 0, 1] });
  // Along the cockpit the top edge is the canopy sill; the sides bulge out over the avionics bays.
  const zs = [0.98, 0.6, 0.2, -0.14, -0.46, -0.9, -1.4, -1.84];
  const mid = zs.map((z) => {
    const [xs, ys] = sillAt(z);
    return ring(z, [xs + 0.012, ys - 0.01], [Math.min(0.56, xs + 0.09), Math.min(0.62, 0.35 + (0.98 - z) * 0.1)], -0.28, [0.23, -0.42]);
  });
  loft(g, mid, { orient: outward(0.3) });
  const aft = [
    ring(-1.84, [0.3, 1.99], [0.57, 0.95], -0.25, [0.24, -0.41]),
    ring(-2.4, [0.3, 1.99], [0.58, 0.95], -0.24, [0.24, -0.4]),
    ring(-3.2, [0.27, 1.96], [0.53, 0.9], -0.12, [0.21, -0.3]),
    ring(-4.0, [0.21, 1.8], [0.42, 0.95], 0.05, [0.16, -0.14]),
    ring(-5.5, [0.17, 1.72], [0.32, 1.25], 0.68, [0.12, 0.55]),
    ring(-8.0, [0.14, 1.62], [0.25, 1.36], 0.98, [0.1, 0.88]),
    ring(-10.6, [0.11, 1.57], [0.19, 1.39], 1.12, [0.08, 1.04]),
    ring(-11.6, [0.08, 1.54], [0.13, 1.4], 1.17, [0.06, 1.08]),
    ring(TAIL_Z + 0.08, [0.045, 1.5], [0.06, 1.42], 1.26, [0.04, 1.2]),
  ];
  const axisAt = (z) => (z > -4 ? 0.8 : z > -5.5 ? 0.8 + ((-4 - z) / 1.5) * 0.4 : Math.min(1.35, 1.2 + ((-5.5 - z) / 5.4) * 0.1));
  loft(g, aft, { closed: true, orient: (c, n) => v3.dot(n, [c[0], c[1] - axisAt(c[2]), 0]) > 0, capEnd: [0, 0, -1] });
  loft(g, [mid[mid.length - 1], aft[0]], { orient: outward(0.8) });
  // boarding steps and hand holds along the right side
  for (const [z, y] of [[-0.2, 0.3], [-0.9, 0.65]]) box(skin.g(M.darkMetal), Frame.at([-0.555, y, z]), [0.03, 0.03, 0.22]);
}

// TADS (the big turret) and PNVS (the small one on top), on the nose. Each slews in azimuth; the TADS sensors also elevate.
function sensors(ctx, ext) {
  const M = ctx.M;
  const c = [0, 0.02, 2.3];
  const t = ext.child("TADS_Turret", Frame.at(c), { drive: "slew in azimuth about local Y", axis: [0, 1, 0] });
  t.restFrame = Frame.at(c);
  cyl(t.g(M.extDark), Frame.at(c), 0.2, 0.42, 24);
  const el = t.child("TADS_Sensors", Frame.at(c), { drive: "elevate about local X", axis: [1, 0, 0] });
  el.restFrame = Frame.at(c);
  for (const sx of [1, -1]) {
    const S = Frame.at(v3.add(c, [sx * 0.22, 0, 0.02]));
    rbox(el.g(M.ext), S, [0.15, 0.36, 0.44], 0.05, 3);
    quad(el.g(M.sensor), S.move(0, 0.04, 0.2201), 0.1, 0.12);
    quad(el.g(M.sensor), S.move(0, -0.1, 0.2201), 0.08, 0.06);
  }
  const p = [0, 0.33, 2.17];
  const pn = ext.child("PNVS_Turret", Frame.at(p), { drive: "slew in azimuth about local Y (follows the pilot's head)", axis: [0, 1, 0] });
  pn.restFrame = Frame.at(p);
  cyl(pn.g(M.extDark), Frame.at(p), 0.13, 0.2, 20);
  cyl(pn.g(M.ext), Frame.at(v3.add(p, [0, 0.12, 0])), 0.1, 0.04, 20);
  quad(pn.g(M.sensor), Frame.at(v3.add(p, [0, 0.0, 0.1305])), 0.09, 0.1);
}

// M230 30 mm chain gun: the turret trains in azimuth, the gun elevates.
function gun(ctx, ext) {
  const M = ctx.M;
  const base = [0, -0.46, 0.35];
  const tr = ext.child("M230_Turret", Frame.at(base), { drive: "train in azimuth about local Y", axis: [0, 1, 0] });
  tr.restFrame = Frame.at(base);
  cyl(tr.g(M.extDark), Frame.at(base), 0.2, 0.1, 20);
  const pivot = [0, -0.6, 0.4];
  const gn = tr.child("M230_Gun", Frame.at(pivot), { drive: "elevate about local X (+ is down)", axis: [1, 0, 0], muzzle: [0, -0.61, 2.02] });
  gn.restFrame = Frame.at(pivot);
  box(gn.g(M.extDark), Frame.at([0, -0.6, 0.48]), [0.2, 0.18, 0.7]);
  rod(gn.g(M.darkMetal), [0, -0.61, 0.83], [0, -0.61, 1.9], 0.035, 12);
  rod(gn.g(M.darkMetal), [0, -0.61, 1.9], [0, -0.61, 2.02], 0.05, 12);
}

// Stub wing: the inboard store is a 19-shot rocket pod, the outboard a four-round Hellfire launcher. sx = 1 left, -1 right.
function wing(ctx, ext, sx) {
  const M = ctx.M;
  const side = sx > 0 ? "Left" : "Right";
  const w = ext.child(`Wing_${side}`);
  const tip = WING_TIP - 0.05;
  const sec = (x, zc, yc, c, t) =>
    [[c / 2, 0], [c * 0.3, t / 2], [-c * 0.2, t / 2], [-c / 2, t * 0.1], [-c / 2, -t * 0.1], [-c * 0.2, -t / 2], [c * 0.3, -t / 2]].map(([dz, dy]) => [sx * x, yc + dy, zc + dz]);
  loft(w.g(M.ext), [sec(0.5, -2.66, 0.64, 1.02, 0.15), sec(1.5, -2.68, 0.61, 0.9, 0.12), sec(tip, -2.7, 0.58, 0.78, 0.09)], {
    closed: true,
    orient: (c, n) => v3.dot(n, [0, c[1] - (0.64 - (Math.abs(c[0]) - 0.5) * 0.03), (c[2] + 2.68) * 0.2]) > 0,
    capEnd: [sx, 0, 0],
  });
  // wingtip mount (air-to-air launcher station); its outer face is the wingspan
  box(w.g(M.extDark), Frame.at([sx * (WING_TIP - 0.025), 0.57, -2.7]), [0.05, 0.1, 0.6]);
  for (const [px, kind, where] of [[1.2, "pod", "Inboard"], [2.0, "hellfire", "Outboard"]]) {
    const x = sx * px;
    box(w.g(M.ext), Frame.at([x, 0.44, -2.62]), [0.1, 0.26, 0.8]);
    const store = w.child(`Store_${side}_${where}`, Frame.at([x, 0.3, -2.6]), { store: kind, note: "released by the jettison buttons" });
    box(store.g(M.extDark), Frame.at([x, 0.3, -2.6]), [0.14, 0.04, 0.9]);
    if (kind === "pod") {
      const podC = [x, 0.07, -2.55];
      lathe(store.g(M.ext), Frame.upAlong(podC, [0, 0, 1], [1, 0, 0]), [[0, -0.86], [0.19, -0.86], [0.2, -0.8], [0.2, 0.8], [0.19, 0.86], [0, 0.86]], 24);
      const holes = region(ctx, false, "pod-face", 128, 128, { kind: "pod" });
      const circ = [...Array(24)].map((_, i) => [Math.cos((i / 24) * Math.PI * 2) * 0.185, Math.sin((i / 24) * Math.PI * 2) * 0.185]);
      fan(store.g(M.panels), Frame.facing(v3.add(podC, [0, 0, 0.862]), [0, 0, 1]), circ, holes);
      fan(store.g(M.panels), Frame.facing(v3.add(podC, [0, 0, -0.862]), [0, 0, -1]), circ, holes);
      box(store.g(M.extDark), Frame.at([x, 0.26, -2.55]), [0.08, 0.06, 0.5]);
    } else {
      box(store.g(M.extDark), Frame.at([x, 0.19, -2.5]), [0.1, 0.2, 1.3]);
      [[-0.13, 0.22], [0.13, 0.22], [-0.13, -0.03], [0.13, -0.03]].forEach(([dx, dy], i) => {
        const mc = [x + dx, dy, -2.42];
        const m = store.child(`Hellfire_${side}_${i + 1}`, Frame.at(mc), { store: "missile", note: "launched by the weapon trigger with missiles selected" });
        hellfire(ctx, m, mc);
      });
    }
  }
}

function fan(g, F, pts, uv) {
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const [x, y] of pts) {
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
  }
  const n = F.dir([0, 0, 1]);
  const vs = pts.map(([x, y]) => ({ p: F.point([x, y, 0]), n, t: [uv[0] + ((x - minX) / (maxX - minX)) * (uv[2] - uv[0]), uv[1] + ((maxY - y) / (maxY - minY)) * (uv[3] - uv[1])] }));
  const tris = [];
  for (let i = 1; i < pts.length - 1; i++) tris.push([0, i, i + 1]);
  g.push(vs, tris);
}

function hellfire(ctx, node, c) {
  const M = ctx.M;
  const F = Frame.upAlong(c, [0, 0, 1], [1, 0, 0]);
  const L = 1.63, r = 0.089;
  lathe(node.g(M.ext), F, [[0, -L / 2], [r, -L / 2], [r, L / 2 - 0.22], [r * 0.93, L / 2 - 0.12], [r * 0.7, L / 2 - 0.04], [r * 0.45, L / 2], [0, L / 2]], 12);
  lathe(node.g(M.sensor), F, [[r * 0.45, L / 2 - 0.0005], [r * 0.45, L / 2 + 0.004], [0, L / 2 + 0.012]], 12);
  for (let i = 0; i < 4; i++) {
    const a = (i + 0.5) * (Math.PI / 2);
    const d = [Math.cos(a), Math.sin(a), 0];
    box(node.g(M.extDark), Frame.along(v3.add(c, [d[0] * (r + 0.05), d[1] * (r + 0.05), -L / 2 + 0.12]), [0, 0, 1], v3.cross([0, 0, 1], d)), [0.2, 0.004, 0.1]);
    box(node.g(M.extDark), Frame.along(v3.add(c, [d[0] * (r + 0.02), d[1] * (r + 0.02), L / 2 - 0.3]), [0, 0, 1], v3.cross([0, 0, 1], d)), [0.08, 0.003, 0.05]);
  }
}

function nacelle(ctx, ext, sx) {
  const M = ctx.M;
  const n = ext.child(sx > 0 ? "Nacelle_Left" : "Nacelle_Right");
  const c = [sx * 0.8, 1.3, -3.15];
  const F = Frame.upAlong(c, [0, 0, 1], [1, 0, 0]);
  lathe(n.g(M.ext), F, [[0, -1.12], [0.16, -1.1], [0.27, -0.85], [0.31, -0.3], [0.31, 0.5], [0.29, 0.86], [0.27, 1.0], [0.19, 1.0], [0.19, 0.96]], 24, { smooth: true });
  lathe(n.g(M.extDark), F, [[0.19, 0.96], [0.0, 0.96]], 24);
  box(n.g(M.ext), Frame.at([sx * 0.55, 1.22, -3.1]), [0.36, 0.2, 1.5]);
  rbox(n.g(M.extDark), Frame.at(v3.add(c, [sx * 0.22, 0.05, -0.85])), [0.18, 0.2, 0.5], 0.05, 2);
}

function pylonAndRotor(ctx, ext) {
  const M = ctx.M;
  const py = ext.child("Rotor_Pylon");
  const hz = HUB[2];
  const tr = (z, w0, y0, w1, y1) => [[w0, y0, z], [w1, y1, z], [-w1, y1, z], [-w0, y0, z]];
  loft(py.g(M.ext), [tr(-1.78, 0.26, 1.98, 0.2, 2.05), tr(hz + 0.75, 0.28, 1.98, 0.22, 2.32), tr(hz - 0.3, 0.28, 1.98, 0.22, 2.34), tr(-3.9, 0.24, 1.9, 0.16, 2.18)], {
    orient: (c, n) => v3.dot(n, [c[0], c[1] - 1.9, 0]) > 0,
    capStart: [0, 0.2, 1],
    capEnd: [0, 0, -1],
  });
  const hubBottom = HUB[1] - HUB_H / 2;
  rod(py.g(M.darkMetal), [0, 2.3, hz], [0, hubBottom + 0.02, hz], 0.1, 16);
  cyl(py.g(M.darkMetal), Frame.at([0, 2.45, hz]), 0.24, 0.06, 20);
  // Longbow fire control radar on its mast above the hub; it doesn't turn with the rotor.
  const hubTop = HUB[1] + HUB_H / 2;
  const fcr = ext.child("FCR_Radome", Frame.at([0, FCR_TOP - 0.3, hz]));
  rod(fcr.g(M.darkMetal), [0, hubTop, hz], [0, FCR_TOP - 0.62, hz], 0.07, 12);
  const b = FCR_TOP - 0.64, k = 0.64 / 0.62;
  lathe(fcr.g(M.ext), Frame.at([0, 0, hz]), [[0, 3.46], [0.16, 3.46], [0.2, 3.56], [0.46, 3.62], [0.53, 3.72], [0.5, 3.86], [0.4, 3.98], [0.2, 4.06], [0, 4.08]].map(([r, y]) => [r, b + (y - 3.46) * k]), 28, { smooth: true });
  const rotor = ext.child("Main_Rotor", Frame.at(HUB), { drive: "spin about local Y; + is counter-clockwise seen from above, as on the real aircraft", axis: [0, 1, 0], rpm100: 289 });
  rotor.restFrame = Frame.at(HUB);
  cyl(rotor.g(M.darkMetal), Frame.at(HUB), 0.3, HUB_H, 24);
  for (let i = 0; i < 4; i++) {
    const a = (i * Math.PI) / 2 + 20 * deg;
    const dir = [Math.cos(a), 0, Math.sin(a)];
    const side = v3.cross([0, 1, 0], dir);
    box(rotor.g(M.darkMetal), Frame.along(v3.add(HUB, v3.mul(dir, 0.45)), dir, [0, 1, 0]), [0.4, 0.12, 0.16]);
    const sec = (r, chord, th, sweep, pitch) => {
      const cp = Math.cos(pitch), sp = Math.sin(pitch);
      return [[chord / 2, 0], [chord * 0.25, th / 2], [-chord * 0.3, th * 0.35], [-chord / 2, 0], [-chord * 0.3, -th * 0.3], [chord * 0.25, -th / 2]].map(([dc, dt]) => {
        const c2 = dc * cp - dt * sp, t2 = dc * sp + dt * cp;
        return v3.add(v3.add(HUB, v3.mul(dir, r)), v3.add(v3.mul(side, c2 - sweep), [0, t2 - r * 0.008, 0]));
      });
    };
    loft(rotor.g(M.rotor), [sec(0.62, 0.5, 0.07, 0, 9 * deg), sec(3.5, 0.53, 0.06, 0, 5 * deg), sec(R_MAIN - 0.45, 0.53, 0.05, 0, 1 * deg), sec(R_MAIN, 0.36, 0.035, 0.12, 0)], {
      closed: true,
      orient: (c, n) => {
        const r = v3.dot(v3.sub(c, HUB), dir);
        return v3.dot(n, v3.sub(c, v3.add(v3.add(HUB, v3.mul(dir, r)), [0, -r * 0.008, 0]))) > 0;
      },
      capStart: v3.mul(dir, -1),
      capEnd: dir,
    });
  }
}

// Vertical fin, stabilator and the four-blade "scissor" tail rotor on the fin's left.
function tail(ctx, ext) {
  const M = ctx.M;
  const t = ext.child("Tail");
  const side = new Frame([0, 0, 0], [0, 0, 1], [0, 1, 0], [-1, 0, 0]);
  const fin = [[-10.3, 1.5], [-11.45, 2.62], [-12.12, 2.66], [TAIL_Z, 2.05], [TAIL_Z + 0.07, 0.45], [-11.7, 0.33], [-11.1, 0.95]];
  extrude(t.g(M.ext), side, fin, 0.13);
  const sec = (x, zc, yc, c, th) =>
    [[c / 2, 0], [c * 0.3, th / 2], [-c * 0.2, th / 2], [-c / 2, th * 0.1], [-c / 2, -th * 0.1], [-c * 0.2, -th / 2], [c * 0.3, -th / 2]].map(([dz, dy]) => [x, yc + dy, zc + dz]);
  for (const sx of [1, -1]) {
    loft(t.g(M.ext), [sec(sx * 0.05, -11.95, 0.78, 0.8, 0.08), sec(sx * 1.7, -12.0, 0.78, 0.62, 0.06)], {
      closed: true,
      orient: (c, n) => v3.dot(n, [0, c[1] - 0.78, (c[2] + 11.97) * 0.2]) > 0,
      capEnd: [sx, 0, 0],
    });
  }
  // tail wheel, under the fin
  const tw = [0, GROUND_Y + 0.2, TAIL_WHEEL_Z];
  rod(t.g(M.darkMetal), [0, 0.38, TAIL_WHEEL_Z + 0.2], [0, tw[1] + 0.02, tw[2] + 0.02], 0.045, 10);
  wheel(t.g(M.rubber), t.g(M.darkMetal), tw, 0.2, 0.12);
  rod(t.g(M.darkMetal), [0.06, TAIL_HUB[1], TAIL_HUB[2]], TAIL_HUB, 0.07, 12);
  const trn = ext.child("Tail_Rotor", Frame.at(TAIL_HUB), { drive: "spin about local X", axis: [1, 0, 0] });
  trn.restFrame = Frame.at(TAIL_HUB);
  cyl(trn.g(M.darkMetal), Frame.upAlong(TAIL_HUB, [1, 0, 0], [0, 1, 0]), 0.1, 0.12, 14);
  const span = R_TAIL - 0.1;
  for (const a0 of [0, Math.PI]) {
    for (const off of [0, 55 * deg]) {
      const a = a0 + off;
      const dir = [0, Math.sin(a), Math.cos(a)];
      const x = TAIL_HUB[0] + (off ? 0.05 : 0.1);
      const B = Frame.along([x, TAIL_HUB[1] + dir[1] * (0.1 + span / 2), TAIL_HUB[2] + dir[2] * (0.1 + span / 2)], dir, [1, 0, 0]);
      box(trn.g(M.rotor), B, [span, 0.035, 0.25]);
    }
  }
}

function wheel(gTire, gHub, c, r, w) {
  const F = Frame.upAlong(c, [1, 0, 0], [0, 1, 0]);
  lathe(gTire, F, [[r * 0.62, -w / 2], [r * 0.9, -w / 2], [r, -w * 0.3], [r, w * 0.3], [r * 0.9, w / 2], [r * 0.62, w / 2]], 22, { smooth: true });
  lathe(gHub, F, [[0, -w * 0.42], [r * 0.64, -w * 0.42], [r * 0.64, w * 0.42], [0, w * 0.42]], 16);
}

// Main landing gear: trailing arms and shock struts, wheels outboard.
function gear(ctx, ext) {
  const M = ctx.M;
  const g = ext.child("Landing_Gear");
  const [wx, wy, wz] = MAIN_WHEEL;
  for (const sx of [1, -1]) {
    const hub = [sx * wx, wy, wz];
    rod(g.g(M.darkMetal), [sx * 0.42, -0.3, wz + 0.48], [sx * (wx - 0.1), wy + 0.02, wz + 0.06], 0.045, 10);
    rod(g.g(M.darkMetal), [sx * 0.46, -0.2, wz - 0.42], [sx * (wx - 0.1), wy + 0.02, wz - 0.06], 0.04, 10);
    rod(g.g(M.metal), [sx * 0.62, 0.35, wz - 0.17], [sx * (wx - 0.1), wy + 0.1, wz - 0.02], 0.05, 12);
    rod(g.g(M.darkMetal), [sx * 0.6, 0.45, wz - 0.19], [sx * 0.7, 0.05, wz - 0.14], 0.07, 12);
    rod(g.g(M.darkMetal), [sx * (wx - 0.1), wy, wz], [sx * (wx - 0.03), wy, wz], 0.05, 10);
    wheel(g.g(M.rubber), g.g(M.darkMetal), hub, 0.33, 0.2);
  }
}

// Navigation lights (red left, green right, white tail) and anti-collision beacons; each has its own material to switch.
function lights(ctx, ext) {
  const M = ctx.M;
  const lt = ext.child("Lights");
  const dome = (name, mat, p, dir, r = 0.03, note) => {
    const n = lt.child(name, Frame.at(p), { light: note });
    sphere(n.g(mat), Frame.upAlong(p, dir, Math.abs(dir[1]) > 0.9 ? [1, 0, 0] : [0, 1, 0]), r, 12, { from: 0, to: Math.PI / 2 });
  };
  dome("Light_Nav_Left", M.navRed, [WING_TIP, 0.57, -2.55], [1, 0, 0], 0.03, "navigation, red");
  dome("Light_Nav_Right", M.navGreen, [-WING_TIP, 0.57, -2.55], [-1, 0, 0], 0.03, "navigation, green");
  dome("Light_Nav_Tail", M.navWhite, [0, 2.1, TAIL_Z], [0, 0, -1], 0.03, "navigation, white");
  dome("Light_Anticollision_Top", M.beacon, [0, 2.2, -3.75], [0, 1, 0], 0.045, "anti-collision strobe");
  dome("Light_Anticollision_Bottom", M.beacon, [0, -0.43, -1.3], [0, -1, 0], 0.045, "anti-collision strobe");
}
