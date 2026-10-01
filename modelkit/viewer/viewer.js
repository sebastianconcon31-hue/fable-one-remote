// Shows one of the vehicles and works whatever moves on it. The controls come
// from the model itself: every driven node says how it moves in its glTF
// extras (`control`: wheel, sprocket, steer, track, hinge, slide, traverse,
// elevate or cargo, with its `axis`, `limits` and `group`).
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const $ = (id) => document.getElementById(id);
const canvas = $("view");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.toneMapping = THREE.AgXToneMapping;
renderer.toneMappingExposure = 1.15;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.6;
const SKY = 0xa9bfd6;
scene.background = new THREE.Color(SKY);
scene.fog = new THREE.Fog(SKY, 60, 220);
const hemi = new THREE.HemisphereLight(0xdfe8f2, 0x5a5448, 0.9);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff1dd, 3.2);
sun.position.set(-9, 14, 7);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -9, right: 9, top: 9, bottom: -9, near: 1, far: 40 });
sun.shadow.bias = -0.0004;
scene.add(sun);
const ground = new THREE.Mesh(new THREE.CircleGeometry(160, 64), new THREE.MeshStandardMaterial({ color: 0x8a8476, roughness: 0.95 }));
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

const camera = new THREE.PerspectiveCamera(38, 1, 0.05, 500);
const orbit = new OrbitControls(camera, canvas);
orbit.enableDamping = true;
orbit.minDistance = 1.5;
orbit.maxDistance = 45;
orbit.maxPolarAngle = Math.PI * 0.495;
let VIEWS = {};
function view(name) {
  const v = VIEWS[name];
  if (!v) return;
  camera.position.copy(v[0]);
  orbit.target.copy(v[1]);
  orbit.update();
}
for (const b of document.querySelectorAll("[data-view]")) b.addEventListener("click", () => view(b.dataset.view));

const status = (t) => ($("status").textContent = t);
const toggle = (b, on) => b.setAttribute("aria-pressed", String(on));
const parts = { wheel: [], steer: [], track: [], hinge: [], slide: [], traverse: [], elevate: [], cargo: [] };
const nodes = {};
const mats = {};
const rest = new Map();
const state = { drive: 0, speed: 0, travel: 0, steer: 0, traverse: 0, elevate: 0, night: false, groups: {}, lifting: null, unloaded: [] };
let model;
let bench = false; // a small thing on a stand (a helmet) rather than a vehicle on the ground
const BENCH = 0x2a2e31;

function group(title) {
  const g = document.createElement("div");
  g.className = "group plate";
  const c = document.createElement("span");
  c.className = "cap";
  c.textContent = title;
  g.append(c);
  $("controls").insertBefore(g, $("status"));
  return g;
}
function button(g, label, fn, pressed) {
  const b = document.createElement("button");
  b.textContent = label;
  if (pressed !== undefined) b.setAttribute("aria-pressed", String(pressed));
  b.addEventListener("click", (e) => fn(e.currentTarget));
  g.append(b);
  return b;
}
function slider(g, label, min, max, value, fn) {
  const l = document.createElement("label");
  l.className = "slider";
  l.textContent = label + " ";
  const i = document.createElement("input");
  Object.assign(i, { type: "range", min, max, step: (max - min) / 400, value });
  i.addEventListener("input", () => fn(+i.value));
  l.append(i);
  g.append(l);
  return i;
}

function buildControls(root) {
  $("title").textContent = root.userData.vehicle || root.name;
  document.title = root.userData.vehicle || root.name;
  if (root.userData.blurb) $("blurb").textContent = root.userData.blurb;
  const moving = parts.wheel.length || parts.track.length;
  if (moving || parts.steer.length) {
    const g = group("Drive");
    if (moving) {
      button(g, "Forward", (b) => { state.drive = state.drive === 1 ? 0 : 1; toggle(b, state.drive === 1); toggle(back, false); }, false);
      var back = button(g, "Reverse", (b) => { state.drive = state.drive === -1 ? 0 : -1; toggle(b, state.drive === -1); toggle(g.querySelector("button"), false); }, false);
    }
    if (parts.steer.length) slider(g, "Steer", -1, 1, 0, (v) => (state.steer = v));
  }
  if (parts.traverse.length || parts.elevate.length) {
    const g = group(root.userData.weapon || "Turret");
    if (parts.traverse.length) slider(g, "Traverse", -Math.PI, Math.PI, 0, (v) => (state.traverse = v));
    if (parts.elevate.length) {
      const [lo, hi] = parts.elevate[0].limits;
      slider(g, "Elevation", lo, hi, 0, (v) => (state.elevate = v));
    }
  }
  const groups = {};
  for (const p of [...parts.hinge, ...parts.slide]) (groups[p.group] ||= []).push(p);
  const names = Object.keys(groups);
  if (names.length) {
    const g = group("Open and close");
    for (const name of names) {
      state.groups[name] = { v: 0, target: 0 };
      button(g, name, (b) => { const s = state.groups[name]; s.target = s.target ? 0 : 1; toggle(b, !!s.target); }, false);
    }
  }
  const g = group("Scene");
  if (mats.HDU_Display) button(g, "Display", (b) => { const on = b.getAttribute("aria-pressed") !== "true"; toggle(b, on); mats.HDU_Display.emissiveIntensity = on ? 1 : 0; }, true); // a head-worn display's screen
  button(g, "Night", (b) => { state.night = !state.night; toggle(b, state.night); night(state.night); }, false);
  if (parts.cargo.length) {
    button(g, "Unload", unload);
    button(g, "Reload", reload);
  }
}

function night(n) {
  hemi.intensity = n ? 0.06 : 0.9;
  sun.intensity = n ? 0.05 : 3.2;
  scene.environmentIntensity = n ? 0.05 : 0.6;
  scene.background.set(n ? 0x0a0e16 : bench ? BENCH : SKY);
  if (scene.fog) scene.fog.color.copy(scene.background);
  for (const k of ["Light_White", "Light_Amber", "Light_Red"]) if (mats[k]) mats[k].emissiveIntensity = n ? 6 : 1;
  for (const [name, o] of Object.entries(nodes)) {
    if (!/^Light_Head/.test(name)) continue;
    if (!o.userData.lamp) {
      const l = new THREE.SpotLight(0xfff1d8, 0, 45, 0.5, 0.5, 1.2);
      l.position.set(0, 0, 0.1);
      l.target.position.set(0, -0.6, 10);
      o.add(l, l.target);
      o.userData.lamp = l;
    }
    o.userData.lamp.intensity = n ? 60 : 0;
  }
}

function unload() {
  if (state.lifting) return;
  const p = parts.cargo.find((c) => c.o.visible && !state.unloaded.includes(c));
  if (!p) return status("Nothing left to unload. Reload it.");
  state.lifting = { p, t: 0 };
  status(`Unloading ${p.o.name.replace(/_/g, " ").toLowerCase()}.`);
}
function reload() {
  for (const p of state.unloaded) {
    p.o.position.copy(rest.get(p.o).p);
    p.o.visible = true;
  }
  state.unloaded = [];
  state.lifting = null;
  status("Loaded up again.");
}

// a track's loop as cumulative lengths, for finding the point a given distance round it
function loop(path) {
  const P = [];
  for (let i = 0; i < path.length; i += 2) P.push(new THREE.Vector2(path[i], path[i + 1]));
  P.push(P[0].clone());
  const S = [0];
  for (let i = 1; i < P.length; i++) S.push(S[i - 1] + P[i].distanceTo(P[i - 1]));
  return { P, S, L: S[S.length - 1] };
}
function along(lp, s, out) {
  s = ((s % lp.L) + lp.L) % lp.L;
  let lo = 0, hi = lp.S.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (lp.S[mid] <= s) lo = mid;
    else hi = mid;
  }
  const t = (s - lp.S[lo]) / Math.max(1e-9, lp.S[lo + 1] - lp.S[lo]);
  return out.copy(lp.P[lo]).lerp(lp.P[lo + 1], t);
}

function onModel(gltf) {
  model = gltf.scene;
  let root = null;
  model.traverse((o) => {
    if (o.isMesh) {
      o.castShadow = !o.material.transparent;
      o.receiveShadow = true;
      if (o.material.transparent) o.material.depthWrite = false;
      mats[o.material.name] = o.material;
    }
    if (!o.name) return;
    nodes[o.name] = o;
    rest.set(o, { q: o.quaternion.clone(), p: o.position.clone() });
    const u = o.userData;
    if (u.vehicle && !root) root = o;
    const kind = u.control;
    if (!kind || !parts[kind]) return;
    const p = { o, axis: new THREE.Vector3().fromArray(u.axis || [1, 0, 0]).normalize(), limits: u.limits || [0, 1], group: u.group || "Hatches", radius: u.radius || 0.5, ratio: u.ratio ?? 1 };
    if (u.limits_by_traverse) Object.assign(p, { table: u.limits_by_traverse, step: u.traverse_step || 5 });
    if (u.gravity) p.gravity = true; // a hook on its cable: hangs straight down whatever its parent does
    if (kind === "track") Object.assign(p, { lp: loop(u.path), pitch: u.pitch, links: [] });
    parts[kind].push(p);
  });
  for (const t of parts.track) {
    t.links = t.o.children.filter((c) => /_Link_\d+$/.test(c.name)).sort((a, b) => (a.name < b.name ? -1 : 1));
  }
  scene.add(model);
  // views from the vehicle's size
  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3());
  const c = box.getCenter(new THREE.Vector3());
  const r = Math.max(size.x, size.z) * 0.8 + 2.5;
  const h = size.y * 0.5;
  VIEWS = {
    front: [new THREE.Vector3(c.x + r * 0.62, h + r * 0.22, c.z + r * 0.95), new THREE.Vector3(c.x, h, c.z + size.z * 0.05)],
    side: [new THREE.Vector3(c.x + r * 1.3, h + 0.4, c.z), new THREE.Vector3(c.x, h, c.z)],
    rear: [new THREE.Vector3(c.x - r * 0.6, h + r * 0.4, c.z - r * 1.0), new THREE.Vector3(c.x, h, c.z - size.z * 0.1)],
    top: [new THREE.Vector3(c.x + 0.01, size.y + r * 1.25, c.z), new THREE.Vector3(c.x, 0, c.z)],
  };
  if (root?.userData.stand === "bench") {
    bench = true;
    ground.visible = false;
    scene.fog = null;
    scene.background.set(BENCH);
    const d = Math.max(size.x, size.y, size.z) * 2.3;
    camera.near = 0.01;
    camera.updateProjectionMatrix();
    Object.assign(orbit, { minDistance: d * 0.3, maxDistance: d * 4, maxPolarAngle: Math.PI });
    VIEWS = {
      front: [new THREE.Vector3(c.x + d * 0.45, c.y + d * 0.2, c.z + d * 0.85), c.clone()],
      side: [new THREE.Vector3(c.x + d, c.y, c.z), c.clone()],
      rear: [new THREE.Vector3(c.x - d * 0.5, c.y + d * 0.25, c.z - d * 0.85), c.clone()],
      top: [new THREE.Vector3(c.x + 0.001, c.y + d, c.z), c.clone()],
    };
  }
  Object.assign(sun.shadow.camera, { left: -r, right: r, top: r, bottom: -r });
  sun.shadow.camera.updateProjectionMatrix();
  view("front");
  buildControls(root || model);
  $("loading").hidden = true;
  status(root?.userData.hint || "Drag to look round it. Everything that moves is on the buttons below.");
}
function onFail(e) {
  $("loading").textContent = "The model could not be loaded.";
  console.error(e);
}
const loader = new GLTFLoader();
const embedded = document.getElementById("vehicle-model");
if (embedded) {
  const bin = atob(embedded.textContent.trim());
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  setTimeout(() => loader.parse(bytes.buffer, "", onModel, onFail), 30);
} else loader.load(window.VEHICLE_MODEL_URL || new URLSearchParams(location.search).get("model") || "model.glb", onModel, undefined, onFail);

// ---- animation ---------------------------------------------------------------------------------------------------------------
const qa = new THREE.Quaternion();
// a hook hangs plumb under where it hangs at rest, let down by `drop` along the world's down
const qp = new THREE.Quaternion(), qr = new THREE.Quaternion(), down = new THREE.Vector3();
function hang(p) {
  const o = p.o, r = rest.get(o);
  if (!r.parentQ) r.parentQ = o.parent.getWorldQuaternion(new THREE.Quaternion()); // the parent's turn at rest (read before anything moves)
  o.parent.updateWorldMatrix(true, false);
  o.parent.getWorldQuaternion(qp);
  qr.copy(qp).invert();
  down.set(0, -(p.drop || 0), 0).applyQuaternion(qr);
  o.position.copy(r.p);
  o.parent.localToWorld(o.position); // where its rest point is now, in the world
  o.position.add(down.applyQuaternion(qp));
  o.parent.worldToLocal(o.position);
  o.quaternion.copy(qr).multiply(r.parentQ).multiply(r.q); // upright as at rest
}
// a gun's elevation limits at the turret's traverse: its extras hold [lowest, highest] every `step` degrees
function byTraverse(p, a) {
  const n = p.table.length;
  const f = ((((a * 180) / Math.PI) % 360) + 360) % 360 / p.step;
  const i = Math.floor(f) % n, j = (i + 1) % n, t = f - Math.floor(f);
  return [0, 1].map((k) => p.table[i][k] * (1 - t) + p.table[j][k] * t);
}
function turn(o, a, axis) {
  o.quaternion.copy(rest.get(o).q).multiply(qa.setFromAxisAngle(axis, a));
}
const A = new THREE.Vector2(), Bp = new THREE.Vector2(), X = new THREE.Vector3(1, 0, 0), Y = new THREE.Vector3(), Z = new THREE.Vector3(), M = new THREE.Matrix4();
const clock = new THREE.Clock();
function tick() {
  const dt = Math.min(clock.getDelta(), 0.05);
  if (model) {
    state.speed += (state.drive * 4 - state.speed) * Math.min(1, dt * 1.5);
    state.travel += state.speed * dt;
    for (const p of parts.wheel) turn(p.o, state.travel / p.radius, p.axis);
    for (const p of parts.steer) {
      const [lo, hi] = p.limits;
      turn(p.o, state.steer * p.ratio * (state.steer > 0 ? hi : -lo), p.axis);
    }
    for (const t of parts.track) {
      t.links.forEach((l, i) => {
        const s = i * t.pitch + state.travel;
        along(t.lp, s, A);
        along(t.lp, s + t.pitch, Bp);
        const tz = Bp.x - A.x, ty = Bp.y - A.y;
        const len = Math.hypot(tz, ty) || 1;
        Z.set(0, ty / len, tz / len);
        Y.set(0, tz / len, -ty / len);
        M.makeBasis(X, Y, Z);
        l.quaternion.setFromRotationMatrix(M);
        l.position.set(0, (A.y + Bp.y) / 2, (A.x + Bp.x) / 2);
      });
    }
    for (const p of parts.traverse) turn(p.o, state.traverse, p.axis);
    for (const p of parts.elevate) {
      const [lo, hi] = p.table ? byTraverse(p, state.traverse) : p.limits;
      turn(p.o, Math.min(hi, Math.max(lo, state.elevate)), p.axis);
    }
    for (const [name, s] of Object.entries(state.groups)) {
      s.v += (s.target - s.v) * Math.min(1, dt * 2.5);
      for (const p of [...parts.hinge, ...parts.slide]) {
        if (p.group !== name) continue;
        const v = p.limits[0] + (p.limits[1] - p.limits[0]) * s.v;
        if (parts.hinge.includes(p)) turn(p.o, v, p.axis);
        else if (!p.gravity) p.o.position.copy(rest.get(p.o).p).addScaledVector(p.axis, v);
        else p.drop = v;
      }
    }
    for (const p of parts.slide.filter((q) => q.gravity)) hang(p);
    if (state.night && mats.Light_Amber && nodes.Light_Beacon) mats.Light_Amber.emissiveIntensity = 3 + 4 * Math.max(0, Math.sin(performance.now() / 120));
    if (state.lifting) {
      const L = state.lifting;
      L.t += dt / 2.2;
      const r = rest.get(L.p.o);
      const up = Math.min(1, L.t * 2) * 1.6;
      const out = Math.max(0, L.t * 2 - 1) * 2.6 * Math.sign(r.p.x || 1);
      L.p.o.position.set(r.p.x + out, r.p.y + up, r.p.z);
      if (L.t >= 1) {
        L.p.o.visible = false;
        state.unloaded.push(L.p);
        state.lifting = null;
        status(`${parts.cargo.length - state.unloaded.length} loads left aboard.`);
      }
    }
  }
  orbit.update();
  renderer.render(scene, camera);
}
function resize() {
  const w = innerWidth, h = innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
addEventListener("resize", resize);
resize();
renderer.setAnimationLoop(tick);
window.vehicle = { nodes, parts, state, scene, camera };
