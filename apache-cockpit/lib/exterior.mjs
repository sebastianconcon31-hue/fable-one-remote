// What the crew can see of the outside: the nose with its sensor turrets and
// gun, the fuselage sides, the stub wings with their stores, the engine
// nacelles, and the rotor. It stops short of the tail, which can't be seen
// from either seat.
import { v3, Frame, loft, lathe, cyl, rod, box, rbox, quad, extrude as extrudeAt } from "./geo.mjs";
import { sillAt } from "./cockpit.mjs";
import { region } from "./parts.mjs";

const deg = Math.PI / 180;

export function buildExterior(ctx, root) {
  const M = ctx.M;
  const ext = root.child("Exterior", undefined, { note: "shell visible from the cockpit; the tail boom is not modelled" });
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
    ring(-10.9, [0.11, 1.56], [0.19, 1.38], 1.12, [0.08, 1.04]),
  ];
  const boomAxis = (z) => (z > -4 ? 0.8 : z > -5.5 ? 0.8 + ((-4 - z) / 1.5) * 0.4 : 1.2 + ((-5.5 - z) / 5.4) * 0.1);
  loft(g, aft, { closed: true, orient: (c, n) => v3.dot(n, [c[0], c[1] - boomAxis(c[2]), 0]) > 0, capEnd: [0, 0, -1] });
  // the step up behind the canopy
  const r0 = mid[mid.length - 1], r1 = aft[0];
  loft(g, [r0, r1], { orient: outward(0.8) });

  sensors(ctx, ext);
  gun(ctx, ext);
  for (const sx of [1, -1]) wing(ctx, ext, sx);
  for (const sx of [1, -1]) nacelle(ctx, ext, sx);
  pylonAndRotor(ctx, ext);
  tail(ctx, ext);
  gear(ctx, ext);
  return ext;
}

// Vertical fin, stabilator and the four-blade "scissor" tail rotor on the fin's left.
function tail(ctx, ext) {
  const M = ctx.M;
  const t = ext.child("Tail");
  const side = new Frame([0, 0, 0], [0, 0, 1], [0, 1, 0], [-1, 0, 0]);
  const fin = [[-10.25, 1.5], [-11.55, 3.05], [-12.25, 3.08], [-12.45, 2.4], [-12.35, 0.45], [-11.65, 0.33], [-11.05, 0.95]];
  extrudeProfile(t.g(M.ext), side, fin, 0.13);
  const sec = (x, zc, yc, c, th) =>
    [[c / 2, 0], [c * 0.3, th / 2], [-c * 0.2, th / 2], [-c / 2, th * 0.1], [-c / 2, -th * 0.1], [-c * 0.2, -th / 2], [c * 0.3, -th / 2]].map(([dz, dy]) => [x, yc + dy, zc + dz]);
  for (const sx of [1, -1]) {
    loft(t.g(M.ext), [sec(sx * 0.05, -12.0, 0.8, 0.8, 0.08), sec(sx * 1.7, -12.05, 0.8, 0.62, 0.06)], {
      closed: true,
      orient: (c, n) => v3.dot(n, [0, c[1] - 0.8, (c[2] + 12.02) * 0.2]) > 0,
      capEnd: [sx, 0, 0],
    });
  }
  // tail wheel
  rod(t.g(M.darkMetal), [0, 0.4, -11.95], [0, -0.72, -12.15], 0.045, 10);
  wheel(t.g(M.rubber), t.g(M.darkMetal), [0, -0.74, -12.2], 0.2, 0.12);
  const hub = [0.2, 2.72, -11.95];
  rod(t.g(M.darkMetal), [0.06, 2.72, -11.95], hub, 0.07, 12);
  const tr = ext.child("Tail_Rotor", Frame.at(hub), { control: "rotor", pivot: "spin about local X" });
  cyl(tr.g(M.darkMetal), Frame.upAlong(hub, [1, 0, 0], [0, 1, 0]), 0.1, 0.12, 14);
  for (const a0 of [0, Math.PI]) {
    for (const off of [0, 55 * deg]) {
      const a = a0 + off;
      const dir = [0, Math.sin(a), Math.cos(a)];
      const x = hub[0] + (off ? 0.05 : 0.1);
      const B = Frame.along([x, hub[1] + dir[1] * 0.75, hub[2] + dir[2] * 0.75], dir, [1, 0, 0]);
      box(tr.g(M.rotor), B, [1.3, 0.035, 0.25]);
    }
  }
}

function extrudeProfile(g, F, pts, thick) {
  const L = pts.map(([z, y]) => [z, y]);
  extrudeAt(g, F, L, thick);
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
  for (const sx of [1, -1]) {
    const hub = [sx * 1.0, -0.62, -1.78];
    rod(g.g(M.darkMetal), [sx * 0.42, -0.3, -1.3], [sx * 0.9, -0.6, -1.72], 0.045, 10);
    rod(g.g(M.darkMetal), [sx * 0.46, -0.2, -2.2], [sx * 0.9, -0.6, -1.84], 0.04, 10);
    rod(g.g(M.metal), [sx * 0.62, 0.35, -1.95], [sx * 0.9, -0.52, -1.8], 0.05, 12);
    rod(g.g(M.darkMetal), [sx * 0.6, 0.45, -1.97], [sx * 0.7, 0.05, -1.92], 0.07, 12);
    rod(g.g(M.darkMetal), [sx * 0.9, -0.62, -1.78], [sx * 0.97, -0.62, -1.78], 0.05, 10);
    wheel(g.g(M.rubber), g.g(M.darkMetal), hub, 0.33, 0.2);
  }
}

// TADS (the big turret) and PNVS (the small one on top), on the nose.
function sensors(ctx, ext) {
  const M = ctx.M;
  const t = ext.child("TADS_PNVS", Frame.at([0, 0.02, 2.3]), { note: "turret; rotate about local Y to slew" });
  const c = [0, 0.02, 2.3];
  cyl(t.g(M.extDark), Frame.at(c), 0.2, 0.42, 24);
  for (const sx of [1, -1]) {
    const S = Frame.at(v3.add(c, [sx * 0.22, 0, 0.02]));
    rbox(t.g(M.ext), S, [0.15, 0.36, 0.44], 0.05, 3);
    quad(t.g(M.sensor), S.move(0, 0.04, 0.2201), 0.1, 0.12);
    quad(t.g(M.sensor), S.move(0, -0.1, 0.2201), 0.08, 0.06);
  }
  const p = [0, 0.33, 2.17];
  const pn = ext.child("PNVS", Frame.at(p), { note: "turret; rotate about local Y to slew" });
  cyl(pn.g(M.extDark), Frame.at(p), 0.13, 0.2, 20);
  cyl(pn.g(M.ext), Frame.at(v3.add(p, [0, 0.12, 0])), 0.1, 0.04, 20);
  quad(pn.g(M.sensor), Frame.at(v3.add(p, [0, 0.0, 0.1305])), 0.09, 0.1);
}

function gun(ctx, ext) {
  const M = ctx.M;
  const base = [0, -0.46, 0.35];
  const gn = ext.child("M230_Gun", Frame.at(base), { note: "rotate about local Y to train, X to elevate" });
  cyl(gn.g(M.extDark), Frame.at(base), 0.2, 0.1, 20);
  box(gn.g(M.extDark), Frame.at([0, -0.6, 0.48]), [0.2, 0.18, 0.7]);
  rod(gn.g(M.darkMetal), [0, -0.61, 0.83], [0, -0.61, 1.9], 0.035, 12);
  rod(gn.g(M.darkMetal), [0, -0.61, 1.9], [0, -0.61, 2.02], 0.05, 12);
}

// Stub wing with a rocket pod inboard and a Hellfire launcher outboard. sx = 1 left, -1 right.
function wing(ctx, ext, sx) {
  const M = ctx.M;
  const w = ext.child(sx > 0 ? "Wing_Left" : "Wing_Right");
  const sec = (x, zc, yc, c, t) =>
    [[c / 2, 0], [c * 0.3, t / 2], [-c * 0.2, t / 2], [-c / 2, t * 0.1], [-c / 2, -t * 0.1], [-c * 0.2, -t / 2], [c * 0.3, -t / 2]].map(([dz, dy]) => [sx * x, yc + dy, zc + dz]);
  loft(w.g(M.ext), [sec(0.5, -2.66, 0.64, 1.02, 0.15), sec(1.5, -2.68, 0.61, 0.9, 0.12), sec(2.45, -2.7, 0.58, 0.78, 0.09)], {
    closed: true,
    orient: (c, n) => {
      const y0 = 0.64 - (Math.abs(c[0]) - 0.5) * 0.03;
      const z0 = -2.68;
      return v3.dot(n, [0, c[1] - y0, (c[2] - z0) * 0.2]) > 0;
    },
    capEnd: [sx, 0, 0],
  });
  // wingtip mount
  box(w.g(M.extDark), Frame.at([sx * 2.47, 0.57, -2.7]), [0.05, 0.1, 0.6]);
  for (const [px, kind] of [[1.2, "pod"], [2.0, "hellfire"]]) {
    const x = sx * px;
    box(w.g(M.ext), Frame.at([x, 0.44, -2.62]), [0.1, 0.26, 0.8]);
    box(w.g(M.extDark), Frame.at([x, 0.3, -2.6]), [0.14, 0.04, 0.9]);
    if (kind === "pod") {
      const podC = [x, 0.07, -2.55];
      const P = Frame.upAlong(podC, [0, 0, 1], [1, 0, 0]);
      lathe(w.g(M.ext), P, [[0, -0.86], [0.19, -0.86], [0.2, -0.8], [0.2, 0.8], [0.19, 0.86], [0, 0.86]], 24);
      const holes = region(ctx, false, "pod-face", 128, 128, { kind: "pod" });
      const circ = [...Array(24)].map((_, i) => [Math.cos((i / 24) * Math.PI * 2) * 0.185, Math.sin((i / 24) * Math.PI * 2) * 0.185]);
      polyAt(w.g(M.panels), Frame.facing(v3.add(podC, [0, 0, 0.862]), [0, 0, 1]), circ, holes);
      polyAt(w.g(M.panels), Frame.facing(v3.add(podC, [0, 0, -0.862]), [0, 0, -1]), circ, holes);
      box(w.g(M.extDark), Frame.at([x, 0.26, -2.55]), [0.08, 0.06, 0.5]);
    } else {
      box(w.g(M.extDark), Frame.at([x, 0.19, -2.5]), [0.1, 0.2, 1.3]);
      for (const [dx, dy] of [[-0.13, 0.22], [0.13, 0.22], [-0.13, -0.03], [0.13, -0.03]]) hellfire(ctx, w, [x + dx, dy, -2.42]);
    }
  }
}

function polyAt(g, F, pts, uv) {
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

function hellfire(ctx, parent, c) {
  const M = ctx.M;
  const F = Frame.upAlong(c, [0, 0, 1], [1, 0, 0]);
  const L = 1.63, r = 0.089;
  lathe(parent.g(M.ext), F, [[0, -L / 2], [r, -L / 2], [r, L / 2 - 0.22], [r * 0.93, L / 2 - 0.12], [r * 0.7, L / 2 - 0.04], [r * 0.45, L / 2], [0, L / 2]], 12);
  lathe(parent.g(M.sensor), F, [[r * 0.45, L / 2 - 0.0005], [r * 0.45, L / 2 + 0.004], [0, L / 2 + 0.012]], 12);
  // tail fins and mid canards, in an X
  for (let i = 0; i < 4; i++) {
    const a = (i + 0.5) * (Math.PI / 2);
    const d = [Math.cos(a), Math.sin(a), 0];
    box(parent.g(M.extDark), Frame.along(v3.add(c, [d[0] * (r + 0.05), d[1] * (r + 0.05), -L / 2 + 0.12]), [0, 0, 1], v3.cross([0, 0, 1], d)), [0.2, 0.004, 0.1]);
    box(parent.g(M.extDark), Frame.along(v3.add(c, [d[0] * (r + 0.02), d[1] * (r + 0.02), L / 2 - 0.3]), [0, 0, 1], v3.cross([0, 0, 1], d)), [0.08, 0.003, 0.05]);
  }
}

function nacelle(ctx, ext, sx) {
  const M = ctx.M;
  const n = ext.child(sx > 0 ? "Nacelle_Left" : "Nacelle_Right");
  const c = [sx * 0.8, 1.3, -3.15];
  const F = Frame.upAlong(c, [0, 0, 1], [1, 0, 0]);
  lathe(n.g(M.ext), F, [[0, -1.12], [0.16, -1.1], [0.27, -0.85], [0.31, -0.3], [0.31, 0.5], [0.29, 0.86], [0.27, 1.0], [0.19, 1.0], [0.19, 0.96]], 24, { smooth: true });
  lathe(n.g(M.extDark), F, [[0.19, 0.96], [0.0, 0.96]], 24);
  // the strut to the fuselage
  box(n.g(M.ext), Frame.at([sx * 0.55, 1.22, -3.1]), [0.36, 0.2, 1.5]);
  // exhaust suppressor
  rbox(n.g(M.extDark), Frame.at(v3.add(c, [sx * 0.22, 0.05, -0.85])), [0.18, 0.2, 0.5], 0.05, 2);
}

function pylonAndRotor(ctx, ext) {
  const M = ctx.M;
  const py = ext.child("Rotor_Pylon");
  const tr = (z, w0, y0, w1, y1) => [[w0, y0, z], [w1, y1, z], [-w1, y1, z], [-w0, y0, z]];
  loft(py.g(M.ext), [tr(-1.78, 0.26, 1.98, 0.2, 2.05), tr(-2.1, 0.28, 1.98, 0.22, 2.32), tr(-3.0, 0.28, 1.98, 0.22, 2.34), tr(-3.7, 0.24, 1.9, 0.16, 2.18)], {
    orient: (c, n) => v3.dot(n, [c[0], c[1] - 1.9, 0]) > 0,
    capStart: [0, 0.2, 1],
    capEnd: [0, 0, -1],
  });
  const hub = [0, 3.3, -2.55];
  rod(py.g(M.darkMetal), [0, 2.3, -2.55], [0, 3.2, -2.55], 0.1, 16);
  cyl(py.g(M.darkMetal), Frame.at([0, 2.55, -2.55]), 0.24, 0.06, 20);
  // Longbow fire control radar on its own mast above the hub; it doesn't turn with the rotor.
  const fcr = ext.child("FCR_Radome", Frame.at([0, 3.72, -2.55]));
  lathe(fcr.g(M.ext), Frame.at([0, 0, -2.55]), [[0, 3.46], [0.16, 3.46], [0.2, 3.56], [0.46, 3.62], [0.53, 3.72], [0.5, 3.86], [0.4, 3.98], [0.2, 4.06], [0, 4.08]], 28, { smooth: true });
  rod(fcr.g(M.darkMetal), [0, 3.3, -2.55], [0, 3.47, -2.55], 0.07, 12);
  const rotor = ext.child("Main_Rotor", Frame.at(hub), { control: "rotor", pivot: "spin about local Y (counter-clockwise seen from above)" });
  cyl(rotor.g(M.darkMetal), Frame.at(hub), 0.3, 0.22, 24);
  for (let i = 0; i < 4; i++) {
    const a = (i * Math.PI) / 2 + 20 * deg;
    const dir = [Math.cos(a), 0, Math.sin(a)];
    const side = v3.cross([0, 1, 0], dir);
    box(rotor.g(M.darkMetal), Frame.along(v3.add(hub, v3.mul(dir, 0.45)), dir, [0, 1, 0]), [0.4, 0.12, 0.16]);
    const sec = (r, chord, th, sweep, pitch) => {
      const cp = Math.cos(pitch), sp = Math.sin(pitch);
      return [[chord / 2, 0], [chord * 0.25, th / 2], [-chord * 0.3, th * 0.35], [-chord / 2, 0], [-chord * 0.3, -th * 0.3], [chord * 0.25, -th / 2]].map(([dc, dt]) => {
        const c2 = dc * cp - dt * sp, t2 = dc * sp + dt * cp;
        return v3.add(v3.add(hub, v3.mul(dir, r)), v3.add(v3.mul(side, c2 - sweep), [0, t2 - r * 0.012, 0]));
      });
    };
    loft(rotor.g(M.rotor), [sec(0.62, 0.5, 0.07, 0, 9 * deg), sec(3.5, 0.53, 0.06, 0, 5 * deg), sec(6.85, 0.53, 0.05, 0, 1 * deg), sec(7.3, 0.36, 0.035, 0.12, 0)], {
      closed: true,
      orient: (c, n) => {
        const r = v3.dot(v3.sub(c, hub), dir);
        const axisPt = v3.add(v3.add(hub, v3.mul(dir, r)), [0, -r * 0.012, 0]);
        return v3.dot(n, v3.sub(c, axisPt)) > 0;
      },
      capStart: v3.mul(dir, -1),
      capEnd: dir,
    });
  }
}
