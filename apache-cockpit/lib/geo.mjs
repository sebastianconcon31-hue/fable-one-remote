// A small mesh kit and a glTF 2.0 binary (GLB) writer, with no dependencies.
//
// Everything is authored in world space, in glTF's own axes: +Y up, +Z toward
// the nose, +X to the crew's left (so -X is right). A Node carries a world
// frame - its pivot - and the writer turns world geometry into node-local
// geometry, so a stick or a pedal can be given a pivot anywhere without
// moving what it looks like.

export const v3 = {
  add: (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]],
  sub: (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]],
  mul: (a, s) => [a[0] * s, a[1] * s, a[2] * s],
  dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
  cross: (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]],
  len: (a) => Math.hypot(a[0], a[1], a[2]),
  norm: (a) => {
    const l = Math.hypot(a[0], a[1], a[2]) || 1;
    return [a[0] / l, a[1] / l, a[2] / l];
  },
  lerp: (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t],
  mid: (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2],
};

// An origin and three orthonormal axes.
export class Frame {
  constructor(o = [0, 0, 0], x = [1, 0, 0], y = [0, 1, 0], z = [0, 0, 1]) {
    this.o = o;
    this.x = x;
    this.y = y;
    this.z = z;
  }
  static at(o) {
    return new Frame(o);
  }
  // Local +Z along `normal` (a panel's face, toward whoever looks at it), local +Y as near `up` as it can be.
  static facing(o, normal, up = [0, 1, 0]) {
    const z = v3.norm(normal);
    let x = v3.cross(up, z);
    if (v3.len(x) < 1e-6) x = v3.cross([0, 0, 1], z);
    x = v3.norm(x);
    return new Frame(o, x, v3.cross(z, x), z);
  }
  // Local +Y exactly along `yAxis` (a stick, a lever), local +X as near `xHint` as it can be.
  static upAlong(o, yAxis, xHint = [1, 0, 0]) {
    const y = v3.norm(yAxis);
    let z = v3.cross(xHint, y);
    if (v3.len(z) < 1e-6) z = v3.cross([0, 0, 1], y);
    z = v3.norm(z);
    return new Frame(o, v3.cross(y, z), y, z);
  }
  // Local +X exactly along `xAxis`, local +Y as near `yHint` as it can be.
  static along(o, xAxis, yHint = [0, 1, 0]) {
    const x = v3.norm(xAxis);
    let z = v3.cross(x, yHint);
    if (v3.len(z) < 1e-6) z = v3.cross(x, [0, 0, 1]);
    z = v3.norm(z);
    return new Frame(o, x, v3.cross(z, x), z);
  }
  point(p) {
    const { o, x, y, z } = this;
    return [o[0] + x[0] * p[0] + y[0] * p[1] + z[0] * p[2], o[1] + x[1] * p[0] + y[1] * p[1] + z[1] * p[2], o[2] + x[2] * p[0] + y[2] * p[1] + z[2] * p[2]];
  }
  dir(d) {
    const { x, y, z } = this;
    return [x[0] * d[0] + y[0] * d[1] + z[0] * d[2], x[1] * d[0] + y[1] * d[1] + z[1] * d[2], x[2] * d[0] + y[2] * d[1] + z[2] * d[2]];
  }
  local(p) {
    const d = v3.sub(p, this.o);
    return [v3.dot(d, this.x), v3.dot(d, this.y), v3.dot(d, this.z)];
  }
  localDir(d) {
    return [v3.dot(d, this.x), v3.dot(d, this.y), v3.dot(d, this.z)];
  }
  // `f` given in this frame's coordinates, returned in world coordinates.
  mul(f) {
    return new Frame(this.point(f.o), this.dir(f.x), this.dir(f.y), this.dir(f.z));
  }
  // This frame expressed in `parent`'s coordinates.
  relativeTo(parent) {
    return new Frame(parent.local(this.o), parent.localDir(this.x), parent.localDir(this.y), parent.localDir(this.z));
  }
  move(dx, dy, dz) {
    return new Frame(this.point([dx, dy, dz]), this.x, this.y, this.z);
  }
  // Turn about the frame's own axes (radians, right-handed).
  rotX(a) {
    const c = Math.cos(a), s = Math.sin(a);
    return new Frame(this.o, this.x, v3.add(v3.mul(this.y, c), v3.mul(this.z, s)), v3.add(v3.mul(this.z, c), v3.mul(this.y, -s)));
  }
  rotY(a) {
    const c = Math.cos(a), s = Math.sin(a);
    return new Frame(this.o, v3.add(v3.mul(this.x, c), v3.mul(this.z, -s)), this.y, v3.add(v3.mul(this.z, c), v3.mul(this.x, s)));
  }
  rotZ(a) {
    const c = Math.cos(a), s = Math.sin(a);
    return new Frame(this.o, v3.add(v3.mul(this.x, c), v3.mul(this.y, s)), v3.add(v3.mul(this.y, c), v3.mul(this.x, -s)), this.z);
  }
  quat() {
    const [m00, m10, m20] = this.x, [m01, m11, m21] = this.y, [m02, m12, m22] = this.z;
    const tr = m00 + m11 + m22;
    let q;
    if (tr > 0) {
      const s = 0.5 / Math.sqrt(tr + 1);
      q = [(m21 - m12) * s, (m02 - m20) * s, (m10 - m01) * s, 0.25 / s];
    } else if (m00 > m11 && m00 > m22) {
      const s = 2 * Math.sqrt(1 + m00 - m11 - m22);
      q = [0.25 * s, (m01 + m10) / s, (m02 + m20) / s, (m21 - m12) / s];
    } else if (m11 > m22) {
      const s = 2 * Math.sqrt(1 + m11 - m00 - m22);
      q = [(m01 + m10) / s, 0.25 * s, (m12 + m21) / s, (m02 - m20) / s];
    } else {
      const s = 2 * Math.sqrt(1 + m22 - m00 - m11);
      q = [(m02 + m20) / s, (m12 + m21) / s, 0.25 * s, (m10 - m01) / s];
    }
    const l = Math.hypot(...q);
    return q.map((c) => c / l);
  }
}
export const WORLD = new Frame();

// Vertices and triangles for one material. Triangles are wound to face the
// way their vertex normals point, so the generators below only have to get
// normals right.
export class Geo {
  constructor() {
    this.p = [];
    this.n = [];
    this.t = [];
    this.i = [];
  }
  get count() {
    return this.p.length / 3;
  }
  push(verts, tris) {
    const base = this.count;
    for (const v of verts) {
      this.p.push(v.p[0], v.p[1], v.p[2]);
      const n = v3.norm(v.n);
      this.n.push(n[0], n[1], n[2]);
      this.t.push(v.t ? v.t[0] : 0, v.t ? v.t[1] : 0);
    }
    for (const tri of tris) {
      let [a, b, c] = tri;
      const pa = verts[a].p, pb = verts[b].p, pc = verts[c].p;
      const fn = v3.cross(v3.sub(pb, pa), v3.sub(pc, pa));
      if (v3.len(fn) < 1e-14) continue;
      const want = v3.add(v3.add(verts[a].n, verts[b].n), verts[c].n);
      if (v3.dot(fn, want) < 0) [b, c] = [c, b];
      this.i.push(base + a, base + b, base + c);
    }
  }
}

export class Material {
  constructor(name, o = {}) {
    this.name = name;
    this.color = o.color ?? "#808080";
    this.alpha = o.alpha ?? 1;
    this.metal = o.metal ?? 0;
    this.rough = o.rough ?? 0.7;
    this.emissive = o.emissive ?? null; // "#rrggbb"
    this.map = o.map ?? null; // image key
    this.emissiveMap = o.emissiveMap ?? null;
    this.blend = o.blend ?? false;
    this.doubleSided = o.doubleSided ?? false;
  }
}

export class Node {
  constructor(name, frame = WORLD) {
    this.name = name;
    this.frame = frame;
    this.children = [];
    this.geos = new Map();
    this.extras = undefined;
    this.restFrame = null; // for moving parts: the pose at zero, exported in extras.rest
  }
  child(name, frame = this.frame, extras) {
    const n = new Node(name, frame);
    n.extras = extras;
    this.children.push(n);
    return n;
  }
  g(mat) {
    let e = this.geos.get(mat.name);
    if (!e) {
      e = { mat, geo: new Geo() };
      this.geos.set(mat.name, e);
    }
    return e.geo;
  }
  stats() {
    let tris = 0, verts = 0, nodes = 1, prims = 0;
    for (const { geo } of this.geos.values()) {
      tris += geo.i.length / 3;
      verts += geo.count;
      if (geo.i.length) prims++;
    }
    for (const c of this.children) {
      const s = c.stats();
      tris += s.tris;
      verts += s.verts;
      nodes += s.nodes;
      prims += s.prims;
    }
    return { tris, verts, nodes, prims };
  }
}

// ---- 2D helpers ----------------------------------------------------------------------------------------

function area2(pts) {
  let a = 0;
  for (let i = 0; i < pts.length; i++) {
    const [x0, y0] = pts[i], [x1, y1] = pts[(i + 1) % pts.length];
    a += x0 * y1 - x1 * y0;
  }
  return a / 2;
}

// Ear clipping for a simple polygon; returns index triples.
export function triangulate(pts) {
  const n = pts.length;
  if (n < 3) return [];
  const idx = [...Array(n).keys()];
  if (area2(pts) < 0) idx.reverse();
  const tris = [];
  const inside = (p, a, b, c) => {
    const s = (u, v, w) => (v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0]);
    return s(a, b, p) >= -1e-12 && s(b, c, p) >= -1e-12 && s(c, a, p) >= -1e-12;
  };
  let guard = 0;
  while (idx.length > 3 && guard++ < 10000) {
    let clipped = false;
    for (let i = 0; i < idx.length; i++) {
      const i0 = idx[(i + idx.length - 1) % idx.length], i1 = idx[i], i2 = idx[(i + 1) % idx.length];
      const a = pts[i0], b = pts[i1], c = pts[i2];
      const cr = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
      if (cr <= 1e-12) continue;
      let ok = true;
      for (const j of idx) {
        if (j === i0 || j === i1 || j === i2) continue;
        if (inside(pts[j], a, b, c)) {
          ok = false;
          break;
        }
      }
      if (!ok) continue;
      tris.push([i0, i1, i2]);
      idx.splice(i, 1);
      clipped = true;
      break;
    }
    if (!clipped) break;
  }
  if (idx.length === 3) tris.push([idx[0], idx[1], idx[2]]);
  return tris;
}

// Rounded rectangle outline (w x h, corner radius r), counter-clockwise.
export function roundRect(w, h, r, seg = 4) {
  const pts = [];
  const cs = [[w / 2 - r, h / 2 - r, 0], [-w / 2 + r, h / 2 - r, 1], [-w / 2 + r, -h / 2 + r, 2], [w / 2 - r, -h / 2 + r, 3]];
  for (const [cx, cy, q] of cs) {
    for (let i = 0; i <= seg; i++) {
      const a = (q + i / seg) * (Math.PI / 2);
      pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
    }
  }
  return pts;
}

// ---- primitives ------------------------------------------------------------------------------------------
// uv rects are [u0, v0, u1, v1]: (u0, v0) lands on the face's top-left.

const uvIn = (rect, lx, ly, w, h) => (rect ? [rect[0] + ((lx + w / 2) / w) * (rect[2] - rect[0]), rect[1] + ((h / 2 - ly) / h) * (rect[3] - rect[1])] : [lx, -ly]);

export function quad(g, F, w, h, o = {}) {
  const n = F.dir([0, 0, 1]);
  const vs = [[-w / 2, h / 2], [w / 2, h / 2], [w / 2, -h / 2], [-w / 2, -h / 2]].map(([x, y]) => ({ p: F.point([x, y, 0]), n, t: uvIn(o.uv, x, y, w, h) }));
  g.push(vs, [[0, 3, 2], [0, 2, 1]]);
  if (o.back) {
    const nb = v3.mul(n, -1);
    g.push(vs.map((v) => ({ ...v, n: nb })), [[0, 2, 3], [0, 1, 2]]);
  }
}

// A flat polygon in the frame's XY plane, facing +Z.
export function poly(g, F, pts, o = {}) {
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const [x, y] of pts) {
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
  }
  const w = maxX - minX, h = maxY - minY, cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
  const n = F.dir([0, 0, o.flip ? -1 : 1]);
  const vs = pts.map(([x, y]) => ({ p: F.point([x, y, o.z ?? 0]), n, t: uvIn(o.uv, x - cx, y - cy, w, h) }));
  g.push(vs, triangulate(pts));
}

// A flat polygon given by world points (roughly planar); faces `normal`.
export function face(g, pts, normal, o = {}) {
  const n = v3.norm(normal);
  const F = Frame.facing(pts[0], n, Math.abs(n[1]) > 0.9 ? [0, 0, 1] : [0, 1, 0]);
  const loc = pts.map((p) => F.local(p));
  const s = o.uvScale ?? 1;
  const vs = pts.map((p, i) => ({ p, n, t: o.uvs ? o.uvs[i] : [loc[i][0] * s, -loc[i][1] * s] }));
  g.push(vs, triangulate(loc.map((l) => [l[0], l[1]])));
  if (o.back) {
    const nb = v3.mul(n, -1);
    g.push(vs.map((v) => ({ ...v, n: nb })), triangulate(loc.map((l) => [l[0], l[1]])));
  }
}

// Box centred on the frame. o.uv maps a rect onto the +Z face; o.faces skips faces ("pz", "nz", "px", "nx", "py", "ny").
export function box(g, F, [w, h, d], o = {}) {
  const skip = o.skip || "";
  const faces = [
    ["pz", [0, 0, 1], [1, 0, 0], [0, 1, 0], w, h, d],
    ["nz", [0, 0, -1], [-1, 0, 0], [0, 1, 0], w, h, d],
    ["px", [1, 0, 0], [0, 0, -1], [0, 1, 0], d, h, w],
    ["nx", [-1, 0, 0], [0, 0, 1], [0, 1, 0], d, h, w],
    ["py", [0, 1, 0], [1, 0, 0], [0, 0, -1], w, d, h],
    ["ny", [0, -1, 0], [1, 0, 0], [0, 0, 1], w, d, h],
  ];
  for (const [name, nn, uu, vv, fw, fh, depth] of faces) {
    if (skip.includes(name)) continue;
    const n = F.dir(nn);
    const c = v3.mul(nn, depth / 2);
    const vs = [[-1, 1], [1, 1], [1, -1], [-1, -1]].map(([a, b]) => {
      const lp = v3.add(c, v3.add(v3.mul(uu, (a * fw) / 2), v3.mul(vv, (b * fh) / 2)));
      const rect = name === "pz" ? o.uv || o.uvAll : o.uvs?.[name] || o.uvAll;
      return { p: F.point(lp), n, t: rect ? uvIn(rect, (a * fw) / 2, (b * fh) / 2, fw, fh) : [((a * fw) / 2) * (o.uvScale ?? 1), (-(b * fh) / 2) * (o.uvScale ?? 1)] };
    });
    g.push(vs, [[0, 3, 2], [0, 2, 1]]);
  }
}

// A beam from p0 to p1: `w` across (along the side), `d` along `up`.
export function beam(g, p0, p1, w, d, up = [0, 1, 0], o = {}) {
  const len = v3.len(v3.sub(p1, p0));
  if (len < 1e-5) return;
  const F = Frame.along(v3.mid(p0, p1), v3.sub(p1, p0), up);
  box(g, F, [len + (o.extend ?? 0), d, w], o);
}

// Surface of revolution about local +Y. profile: [[r, y], ...] from bottom to top.
// Each profile segment is its own band (hard edges between them) unless smooth.
export function lathe(g, F, profile, seg = 24, o = {}) {
  const phi0 = o.phi0 ?? 0, phiLen = o.phiLen ?? Math.PI * 2;
  const full = Math.abs(phiLen - Math.PI * 2) < 1e-6;
  const segN = [];
  for (let i = 0; i < profile.length - 1; i++) {
    const [r0, y0] = profile[i], [r1, y1] = profile[i + 1];
    const dr = r1 - r0, dy = y1 - y0;
    const l = Math.hypot(dr, dy) || 1;
    segN.push([dy / l, -dr / l]);
  }
  // A profile point may carry its own normal: [r, y, nr, ny].
  const given = (i) => (profile[i].length === 4 ? [profile[i][2], profile[i][3]] : null);
  const ring = (r, y, nr, ny, j) => {
    const a = phi0 + (phiLen * j) / seg;
    const c = Math.cos(a), s = Math.sin(a);
    return { p: F.point([r * c, y, -r * s]), n: F.dir([nr * c, ny, -nr * s]), t: o.uvConst || [j / seg, y] };
  };
  const vertN = (i) => {
    const a = segN[Math.max(0, i - 1)], b = segN[Math.min(segN.length - 1, i)];
    const x = a[0] + b[0], y = a[1] + b[1];
    const l = Math.hypot(x, y) || 1;
    return [x / l, y / l];
  };
  for (let i = 0; i < profile.length - 1; i++) {
    const [r0, y0] = profile[i], [r1, y1] = profile[i + 1];
    if (Math.abs(r0) < 1e-9 && Math.abs(r1) < 1e-9) continue;
    const n0 = given(i) || (o.smooth ? vertN(i) : segN[i]), n1 = given(i + 1) || (o.smooth ? vertN(i + 1) : segN[i]);
    const vs = [];
    for (let j = 0; j <= seg; j++) {
      vs.push(ring(r0, y0, n0[0], n0[1], j));
      vs.push(ring(r1, y1, n1[0], n1[1], j));
    }
    const tris = [];
    for (let j = 0; j < seg; j++) {
      const a = j * 2, b = j * 2 + 1, c = j * 2 + 2, d = j * 2 + 3;
      tris.push([a, c, d], [a, d, b]);
    }
    g.push(vs, tris);
  }
  if (!full && o.caps) {
    // close the cut faces of a partial lathe
    for (const j of [0, seg]) {
      const a = phi0 + (phiLen * j) / seg;
      const nrm = F.dir(j === 0 ? [Math.sin(a), 0, Math.cos(a)] : [-Math.sin(a), 0, -Math.cos(a)]);
      const pts = profile.map(([r, y]) => F.point([r * Math.cos(a), y, -r * Math.sin(a)]));
      face(g, pts, nrm);
    }
  }
}

export function cyl(g, F, r, h, seg = 16, o = {}) {
  const r2 = o.r2 ?? r;
  const prof = [];
  if (o.capBottom !== false) prof.push([0, -h / 2]);
  prof.push([r, -h / 2], [r2, h / 2]);
  if (o.capTop !== false) prof.push([0, h / 2]);
  lathe(g, F, prof, seg, o);
}

// A cylinder between two points.
export function rod(g, p0, p1, r, seg = 12, o = {}) {
  const axis = v3.sub(p1, p0);
  cyl(g, Frame.upAlong(v3.mid(p0, p1), axis, Math.abs(v3.norm(axis)[0]) > 0.9 ? [0, 1, 0] : [1, 0, 0]), r, v3.len(axis), seg, o);
}

export function sphere(g, F, r, seg = 16, o = {}) {
  const rings = o.rings ?? Math.max(4, seg / 2);
  const prof = [];
  const a0 = o.from ?? -Math.PI / 2, a1 = o.to ?? Math.PI / 2;
  for (let i = 0; i <= rings; i++) {
    const a = a0 + ((a1 - a0) * i) / rings;
    prof.push([Math.cos(a) * r, Math.sin(a) * r, Math.cos(a), Math.sin(a)]);
  }
  if (Math.abs(prof[0][0]) > 1e-6) prof.unshift([0, prof[0][1], 0, -1]);
  if (Math.abs(prof[prof.length - 1][0]) > 1e-6) prof.push([0, prof[prof.length - 1][1], 0, 1]);
  lathe(g, F, prof, seg, o);
}

// Box with rounded edges: w x h x d, edge radius r.
export function rbox(g, F, [w, h, d], r, seg = 3, o = {}) {
  r = Math.min(r, w / 2 - 1e-4, h / 2 - 1e-4, d / 2 - 1e-4);
  const hx = w / 2 - r, hy = h / 2 - r, hz = d / 2 - r;
  const thetas = [];
  for (let i = 0; i <= seg; i++) thetas.push([(i / seg) * (Math.PI / 2), 1]);
  for (let i = 0; i <= seg; i++) thetas.push([Math.PI / 2 + (i / seg) * (Math.PI / 2), -1]);
  const phis = [];
  const sx = [1, -1, -1, 1], sz = [1, 1, -1, -1];
  for (let q = 0; q < 4; q++) for (let j = 0; j <= seg; j++) phis.push([(q + j / seg) * (Math.PI / 2), sx[q], sz[q]]);
  const vs = [];
  for (const [t, syy] of thetas) {
    for (const [p, sxx, szz] of phis) {
      const n = [Math.sin(t) * Math.cos(p), Math.cos(t), Math.sin(t) * Math.sin(p)];
      const lp = [n[0] * r + sxx * hx, n[1] * r + syy * hy, n[2] * r + szz * hz];
      vs.push({ p: F.point(lp), n: F.dir(n), t: o.uvConst || [lp[0] * (o.uvScale ?? 1), -lp[1] * (o.uvScale ?? 1)] });
    }
  }
  const cols = phis.length;
  const tris = [];
  for (let i = 0; i < thetas.length - 1; i++) {
    for (let j = 0; j < cols; j++) {
      const j2 = (j + 1) % cols;
      const a = i * cols + j, b = i * cols + j2, c = (i + 1) * cols + j2, dd = (i + 1) * cols + j;
      tris.push([a, b, c], [a, c, dd]);
    }
  }
  g.push(vs, tris);
  // The flat top and bottom.
  for (const sy of [1, -1]) {
    const n = F.dir([0, sy, 0]);
    const c = [[hx, hz], [-hx, hz], [-hx, -hz], [hx, -hz]].map(([x, z]) => ({ p: F.point([x, sy * (h / 2), z]), n, t: o.uvConst || [x, z] }));
    g.push(c, [[0, 1, 2], [0, 2, 3]]);
  }
}

// Extrude a 2D outline (frame XY) to depth d along frame Z, centred.
export function extrude(g, F, pts, d, o = {}) {
  const ccw = area2(pts) > 0 ? pts : pts.slice().reverse();
  const tris = triangulate(ccw);
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const [x, y] of ccw) {
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
  }
  const w = maxX - minX, h = maxY - minY, cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
  if (!o.noFront) {
    const n = F.dir([0, 0, 1]);
    g.push(ccw.map(([x, y]) => ({ p: F.point([x, y, d / 2]), n, t: o.uv ? uvIn(o.uv, x - cx, y - cy, w, h) : [x, -y] })), tris);
  }
  if (!o.noBack) {
    const n = F.dir([0, 0, -1]);
    g.push(ccw.map(([x, y]) => ({ p: F.point([x, y, -d / 2]), n, t: [x, -y] })), tris);
  }
  let run = 0;
  for (let i = 0; i < ccw.length; i++) {
    const [x0, y0] = ccw[i], [x1, y1] = ccw[(i + 1) % ccw.length];
    const l = Math.hypot(x1 - x0, y1 - y0);
    if (l < 1e-9) continue;
    const n = F.dir([(y1 - y0) / l, -(x1 - x0) / l, 0]);
    const vs = [
      { p: F.point([x0, y0, d / 2]), n, t: [run, 0] },
      { p: F.point([x1, y1, d / 2]), n, t: [run + l, 0] },
      { p: F.point([x1, y1, -d / 2]), n, t: [run + l, d] },
      { p: F.point([x0, y0, -d / 2]), n, t: [run, d] },
    ];
    run += l;
    g.push(vs, [[0, 1, 2], [0, 2, 3]]);
  }
}

// A frame (ring) between an outer and an inner rounded rectangle, extruded.
// The two outlines are built corner by corner with the same point count, so
// the front and back rings are plain quads between matching points.
// o: { r, ri, seg, uv (front face, mapped over the outer size), off: [x, y] of the opening }
export function bezel(g, F, ow, oh, iw, ih, d, o = {}) {
  const r = o.r ?? 0.006, ri = o.ri ?? 0.002, seg = o.seg ?? 3;
  const [ox, oy] = o.off || [0, 0];
  const outer = roundRect(ow, oh, r, seg);
  const inner = roundRect(iw, ih, Math.max(1e-4, ri), seg).map(([x, y]) => [x + ox, y + oy]);
  const m = outer.length;
  for (const [z, nz] of [[d / 2, 1], [-d / 2, -1]]) {
    const n = F.dir([0, 0, nz]);
    const vs = [];
    const tris = [];
    const uv = (x, y) => (nz > 0 && o.uv ? uvIn(o.uv, x, y, ow, oh) : [x, -y]);
    for (let i = 0; i < m; i++) {
      vs.push({ p: F.point([outer[i][0], outer[i][1], z]), n, t: uv(outer[i][0], outer[i][1]) });
      vs.push({ p: F.point([inner[i][0], inner[i][1], z]), n, t: uv(inner[i][0], inner[i][1]) });
    }
    for (let i = 0; i < m; i++) {
      const a = i * 2, b = i * 2 + 1, c = ((i + 1) % m) * 2 + 1, e = ((i + 1) % m) * 2;
      tris.push([a, e, c], [a, c, b]);
    }
    g.push(vs, tris);
  }
  extrude(g, F, outer, d, { noFront: true, noBack: true });
  for (let i = 0; i < m; i++) {
    const [x0, y0] = inner[i], [x1, y1] = inner[(i + 1) % m];
    const l = Math.hypot(x1 - x0, y1 - y0);
    if (l < 1e-9) continue;
    const nn = F.dir([-(y1 - y0) / l, (x1 - x0) / l, 0]);
    g.push([
      { p: F.point([x0, y0, d / 2]), n: nn },
      { p: F.point([x1, y1, d / 2]), n: nn },
      { p: F.point([x1, y1, -d / 2]), n: nn },
      { p: F.point([x0, y0, -d / 2]), n: nn },
    ], [[0, 1, 2], [0, 2, 3]]);
  }
}

// Surface through a list of rings (each a list of world points, same length).
// orient(center, normal) says whether a face's normal points the right way.
export function loft(g, rings, o = {}) {
  const closed = o.closed ?? false;
  const m = rings[0].length;
  const cols = closed ? m : m - 1;
  const quads = [];
  for (let i = 0; i < rings.length - 1; i++) {
    for (let j = 0; j < cols; j++) {
      const j2 = (j + 1) % m;
      const a = rings[i][j], b = rings[i][j2], c = rings[i + 1][j2], d = rings[i + 1][j];
      let n = v3.cross(v3.sub(c, a), v3.sub(d, b));
      if (v3.len(n) < 1e-12) n = v3.cross(v3.sub(b, a), v3.sub(d, a));
      if (v3.len(n) < 1e-12) continue;
      n = v3.norm(n);
      const ctr = v3.mul(v3.add(v3.add(a, b), v3.add(c, d)), 0.25);
      if (o.orient && !o.orient(ctr, n)) n = v3.mul(n, -1);
      quads.push({ i, j, j2, pts: [a, b, c, d], n });
    }
  }
  const s = o.uvScale ?? 1;
  if (!o.smooth) {
    for (const q of quads) {
      g.push(q.pts.map((p) => ({ p, n: q.n, t: [(q.j / cols) * s, q.i * s] })), [[0, 1, 2], [0, 2, 3]]);
    }
  } else {
    const acc = new Map();
    const key = (i, j) => i * 100000 + j;
    const addN = (i, j, n) => {
      const k = key(i, j);
      acc.set(k, v3.add(acc.get(k) || [0, 0, 0], n));
    };
    for (const q of quads) {
      addN(q.i, q.j, q.n);
      addN(q.i, q.j2, q.n);
      addN(q.i + 1, q.j2, q.n);
      addN(q.i + 1, q.j, q.n);
    }
    for (const q of quads) {
      const ids = [[q.i, q.j], [q.i, q.j2], [q.i + 1, q.j2], [q.i + 1, q.j]];
      const vs = ids.map(([i, j], k) => {
        const sum = acc.get(key(i, j));
        const n = v3.dot(sum, q.n) > 0 ? sum : q.n;
        return { p: q.pts[k], n, t: [(j / cols) * s, i * s] };
      });
      g.push(vs, [[0, 1, 2], [0, 2, 3]]);
    }
  }
  const cap = (ring, outward) => {
    const c = ring.reduce((a, p) => v3.add(a, p), [0, 0, 0]).map((x) => x / ring.length);
    face(g, ring, outward);
    return c;
  };
  if (o.capStart) cap(rings[0], o.capStart);
  if (o.capEnd) cap(rings[rings.length - 1], o.capEnd);
}

// Parallel-transport frames along a path.
function pathFrames(pts, upHint = [0, 1, 0]) {
  const T = pts.map((p, i) => v3.norm(v3.sub(pts[Math.min(i + 1, pts.length - 1)], pts[Math.max(i - 1, 0)])));
  let N = v3.cross(T[0], upHint);
  if (v3.len(N) < 1e-6) N = v3.cross(T[0], [1, 0, 0]);
  N = v3.norm(N);
  const out = [];
  for (let i = 0; i < pts.length; i++) {
    if (i > 0) {
      N = v3.sub(N, v3.mul(T[i], v3.dot(N, T[i])));
      N = v3.norm(N);
    }
    const B = v3.cross(T[i], N);
    out.push({ T: T[i], N, B });
  }
  return out;
}

// Round tube along a path.
export function tube(g, pts, r, seg = 10, o = {}) {
  const fr = pathFrames(pts, o.up);
  const rings = pts.map((p, i) => {
    const ring = [];
    for (let j = 0; j < seg; j++) {
      const a = (j / seg) * Math.PI * 2;
      ring.push(v3.add(p, v3.add(v3.mul(fr[i].N, Math.cos(a) * r), v3.mul(fr[i].B, Math.sin(a) * r))));
    }
    return ring;
  });
  loft(g, rings, {
    closed: true,
    smooth: true,
    orient: (c, n) => {
      // outward from the nearest path point
      let best = pts[0], bd = Infinity;
      for (const p of pts) {
        const d = v3.len(v3.sub(p, c));
        if (d < bd) {
          bd = d;
          best = p;
        }
      }
      return v3.dot(v3.sub(c, best), n) > 0;
    },
    capStart: o.caps ? v3.mul(fr[0].T, -1) : null,
    capEnd: o.caps ? fr[fr.length - 1].T : null,
  });
}

// A flat strap (webbing) along a path; `up` says which way its broad face looks.
export function ribbon(g, pts, width, thick, up) {
  const rings = pts.map((p, i) => {
    const t = v3.norm(v3.sub(pts[Math.min(i + 1, pts.length - 1)], pts[Math.max(i - 1, 0)]));
    const u = typeof up === "function" ? up(p, i) : up;
    const side = v3.norm(v3.cross(t, u));
    const nrm = v3.norm(v3.cross(side, t));
    const hw = v3.mul(side, width / 2), ht = v3.mul(nrm, thick / 2);
    return [v3.add(v3.add(p, hw), ht), v3.add(v3.sub(p, hw), ht), v3.sub(v3.sub(p, hw), ht), v3.sub(v3.add(p, hw), ht)];
  });
  const center = (c) => {
    let best = pts[0], bd = Infinity;
    for (const p of pts) {
      const d = v3.len(v3.sub(p, c));
      if (d < bd) {
        bd = d;
        best = p;
      }
    }
    return best;
  };
  loft(g, rings, { closed: true, orient: (c, n) => v3.dot(v3.sub(c, center(c)), n) > 0 });
}

// Quadratic/cubic Bezier sampling.
export function bezier(pts, n) {
  const out = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    let ps = pts.slice();
    while (ps.length > 1) {
      const nx = [];
      for (let k = 0; k < ps.length - 1; k++) nx.push(v3.lerp(ps[k], ps[k + 1], t));
      ps = nx;
    }
    out.push(ps[0]);
  }
  return out;
}

// ---- GLB writer -------------------------------------------------------------------------------------------

function srgbToLinear(c) {
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}
export function hexLinear(hex) {
  const h = hex.replace("#", "");
  const v = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
  return v.map(srgbToLinear);
}

export function writeGLB(root, images = {}, meta = {}) {
  const json = {
    asset: { version: "2.0", generator: meta.generator || "apache-cockpit/generate.mjs", copyright: meta.copyright },
    scene: 0,
    scenes: [{ name: root.name, nodes: [0] }],
    nodes: [],
    meshes: [],
    materials: [],
    accessors: [],
    bufferViews: [],
    buffers: [],
  };
  const chunks = [];
  let offset = 0;
  const addView = (buf, target) => {
    const pad = (4 - (offset % 4)) % 4;
    if (pad) {
      chunks.push(Buffer.alloc(pad));
      offset += pad;
    }
    const view = { buffer: 0, byteOffset: offset, byteLength: buf.length };
    if (target) view.target = target;
    json.bufferViews.push(view);
    chunks.push(buf);
    offset += buf.length;
    return json.bufferViews.length - 1;
  };

  // images, textures
  const imageIndex = new Map();
  const textureOf = (key) => {
    if (!key) return undefined;
    if (!images[key]) throw new Error(`missing image ${key}`);
    if (!imageIndex.has(key)) {
      json.images = json.images || [];
      json.textures = json.textures || [];
      json.samplers = json.samplers || [{ magFilter: 9729, minFilter: 9987, wrapS: 33071, wrapT: 33071 }];
      const bv = addView(images[key]);
      json.images.push({ name: key, mimeType: "image/png", bufferView: bv });
      json.textures.push({ name: key, source: json.images.length - 1, sampler: 0 });
      imageIndex.set(key, json.textures.length - 1);
    }
    return imageIndex.get(key);
  };

  const matIndex = new Map();
  const materialOf = (m) => {
    if (matIndex.has(m.name)) return matIndex.get(m.name);
    const lin = hexLinear(m.color);
    const mat = {
      name: m.name,
      pbrMetallicRoughness: { baseColorFactor: [...lin, m.alpha], metallicFactor: m.metal, roughnessFactor: m.rough },
    };
    const bt = textureOf(m.map);
    if (bt !== undefined) mat.pbrMetallicRoughness.baseColorTexture = { index: bt };
    if (m.emissive) mat.emissiveFactor = hexLinear(m.emissive);
    const et = textureOf(m.emissiveMap);
    if (et !== undefined) mat.emissiveTexture = { index: et };
    if (m.blend) mat.alphaMode = "BLEND";
    if (m.doubleSided) mat.doubleSided = true;
    json.materials.push(mat);
    matIndex.set(m.name, json.materials.length - 1);
    return json.materials.length - 1;
  };

  const accessor = (arr, type, compType, target, withMinMax) => {
    const Typed = compType === 5126 ? Float32Array : compType === 5125 ? Uint32Array : Uint16Array;
    const ta = new Typed(arr);
    const bv = addView(Buffer.from(ta.buffer, ta.byteOffset, ta.byteLength), target);
    const comps = { SCALAR: 1, VEC2: 2, VEC3: 3 }[type];
    const acc = { bufferView: bv, componentType: compType, count: arr.length / comps, type };
    if (withMinMax) {
      const min = Array(comps).fill(Infinity), max = Array(comps).fill(-Infinity);
      for (let i = 0; i < arr.length; i++) {
        const c = i % comps;
        min[c] = Math.min(min[c], ta[i]);
        max[c] = Math.max(max[c], ta[i]);
      }
      acc.min = min;
      acc.max = max;
    }
    json.accessors.push(acc);
    return json.accessors.length - 1;
  };

  const visit = (node, parentFrame) => {
    const idx = json.nodes.length;
    const out = { name: node.name };
    json.nodes.push(out);
    const rel = node.frame.relativeTo(parentFrame);
    const t = rel.o.map((v) => Math.round(v * 1e6) / 1e6);
    if (t.some((v) => v !== 0)) out.translation = t;
    const q = rel.quat();
    if (Math.abs(q[3]) < 0.999999) out.rotation = q;
    if (node.extras) out.extras = { ...node.extras };
    if (node.restFrame) {
      const r = node.restFrame.relativeTo(parentFrame);
      out.extras = out.extras || {};
      out.extras.rest = { translation: r.o.map((v) => Math.round(v * 1e6) / 1e6), rotation: r.quat().map((v) => Math.round(v * 1e7) / 1e7) };
    }
    const prims = [];
    for (const { mat, geo } of node.geos.values()) {
      if (!geo.i.length) continue;
      const P = [], N = [];
      for (let i = 0; i < geo.count; i++) {
        const lp = node.frame.local([geo.p[i * 3], geo.p[i * 3 + 1], geo.p[i * 3 + 2]]);
        const ln = node.frame.localDir([geo.n[i * 3], geo.n[i * 3 + 1], geo.n[i * 3 + 2]]);
        P.push(...lp);
        N.push(...ln);
      }
      const attributes = {
        POSITION: accessor(P, "VEC3", 5126, 34962, true),
        NORMAL: accessor(N, "VEC3", 5126, 34962),
        TEXCOORD_0: accessor(geo.t, "VEC2", 5126, 34962),
      };
      const indices = accessor(geo.i, "SCALAR", geo.count > 65535 ? 5125 : 5123, 34963);
      prims.push({ attributes, indices, material: materialOf(mat) });
    }
    if (prims.length) {
      json.meshes.push({ name: node.name, primitives: prims });
      out.mesh = json.meshes.length - 1;
    }
    const kids = node.children.map((c) => visit(c, node.frame));
    if (kids.length) out.children = kids;
    return idx;
  };
  visit(root, WORLD);

  const bin = Buffer.concat(chunks);
  const binPadded = Buffer.concat([bin, Buffer.alloc((4 - (bin.length % 4)) % 4)]);
  json.buffers.push({ byteLength: binPadded.length });
  for (const k of ["images", "textures", "samplers"]) if (json[k] && !json[k].length) delete json[k];
  let js = Buffer.from(JSON.stringify(json), "utf8");
  js = Buffer.concat([js, Buffer.alloc((4 - (js.length % 4)) % 4, 0x20)]);
  const header = Buffer.alloc(12);
  header.writeUInt32LE(0x46546c67, 0);
  header.writeUInt32LE(2, 4);
  header.writeUInt32LE(12 + 8 + js.length + 8 + binPadded.length, 8);
  const jh = Buffer.alloc(8);
  jh.writeUInt32LE(js.length, 0);
  jh.writeUInt32LE(0x4e4f534a, 4);
  const bh = Buffer.alloc(8);
  bh.writeUInt32LE(binPadded.length, 0);
  bh.writeUInt32LE(0x004e4942, 4);
  return Buffer.concat([header, jh, js, bh, binPadded]);
}
