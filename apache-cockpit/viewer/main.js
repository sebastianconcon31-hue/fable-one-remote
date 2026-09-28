// The working AH-64 cockpit: loads apache_cockpit.glb and makes it fly.
// Click or tap any switch, knob, button or key; drag sticks and levers;
// in VR, point and pull the trigger, or grab with the grip button.
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { Controls } from "./controls.js";
import { Sim } from "./sim.js";
import { Displays } from "./displays.js";
import { Effects } from "./fx.js";
import { Sound } from "./audio.js";

const MODEL_URL = window.COCKPIT_MODEL_URL || "apache_cockpit.glb";
const GROUND_Y = -0.95;
const rad = Math.PI / 180;
const $ = (id) => document.getElementById(id);

// --- renderer, scene, world -----------------------------------------------------------------------------------
const canvas = $("view");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.xr.enabled = true;
renderer.xr.setReferenceSpaceType("local");

const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

const skyU = { top: { value: new THREE.Color() }, horizon: { value: new THREE.Color() }, below: { value: new THREE.Color() } };
const sky = new THREE.Mesh(
  new THREE.SphereGeometry(3000, 32, 16),
  new THREE.ShaderMaterial({
    uniforms: skyU, side: THREE.BackSide, depthWrite: false,
    vertexShader: "varying vec3 vP; void main(){ vP = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
    fragmentShader: "uniform vec3 top, horizon, below; varying vec3 vP; void main(){ float h = vP.y; vec3 c = h > 0.0 ? mix(horizon, top, pow(clamp(h * 1.6, 0.0, 1.0), 0.6)) : mix(horizon, below, clamp(-h * 6.0, 0.0, 1.0)); gl_FragColor = vec4(c, 1.0); }",
  })
);
sky.frustumCulled = false;
scene.add(sky);

let seed = 7;
const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
function canvasTexture(size, draw, repeat) {
  const c = document.createElement("canvas");
  c.width = c.height = size;
  draw(c.getContext("2d"), size);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  if (repeat) t.repeat.set(repeat, repeat);
  t.anisotropy = 8;
  return t;
}
const grass = canvasTexture(512, (g, s) => {
  g.fillStyle = "#56603f";
  g.fillRect(0, 0, s, s);
  for (let i = 0; i < 9000; i++) {
    const v = rnd();
    g.fillStyle = v < 0.5 ? `rgba(${70 + v * 60},${86 + v * 50},46,0.35)` : `rgba(${110 + v * 30},${100 + v * 20},62,0.25)`;
    g.fillRect(rnd() * s, rnd() * s, 1 + rnd() * 5, 1 + rnd() * 5);
  }
}, 400);
const ground = new THREE.Mesh(new THREE.PlaneGeometry(8000, 8000), new THREE.MeshStandardMaterial({ map: grass, roughness: 1 }));
ground.rotation.x = -Math.PI / 2;
ground.position.y = GROUND_Y;
ground.receiveShadow = true;
scene.add(ground);
const padTex = canvasTexture(1024, (g, s) => {
  g.fillStyle = "#77746a";
  g.fillRect(0, 0, s, s);
  for (let i = 0; i < 14000; i++) {
    const v = 90 + rnd() * 70;
    g.fillStyle = `rgba(${v},${v - 4},${v - 12},0.35)`;
    g.fillRect(rnd() * s, rnd() * s, 2, 2);
  }
  g.strokeStyle = "#e3c23a";
  g.lineWidth = 14;
  g.strokeRect(40, 40, s - 80, s - 80);
  g.fillStyle = "#ecebe2";
  g.font = "bold 360px Arial";
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.fillText("H", s / 2, s / 2 + 20);
});
const pad = new THREE.Mesh(new THREE.PlaneGeometry(26, 26), new THREE.MeshStandardMaterial({ map: padTex, roughness: 0.95 }));
pad.rotation.x = -Math.PI / 2;
pad.position.set(0, GROUND_Y + 0.01, -4);
pad.receiveShadow = true;
scene.add(pad);
{
  const trunk = new THREE.CylinderGeometry(0.25, 0.35, 3, 6).translate(0, 1.5, 0);
  const crown = new THREE.ConeGeometry(2.6, 8, 7).translate(0, 6.5, 0);
  const n = 420;
  const t1 = new THREE.InstancedMesh(trunk, new THREE.MeshStandardMaterial({ color: 0x4a3a2a, roughness: 1 }), n);
  const t2 = new THREE.InstancedMesh(crown, new THREE.MeshStandardMaterial({ color: 0x2f4127, roughness: 1 }), n);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3();
  for (let i = 0; i < n; i++) {
    const a = rnd() * Math.PI * 2, r = 60 + Math.pow(rnd(), 0.7) * 900, k = 0.7 + rnd() * 0.9;
    p.set(Math.cos(a) * r, GROUND_Y, Math.sin(a) * r);
    q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), rnd() * 6);
    s.set(k, k * (0.8 + rnd() * 0.5), k);
    m.compose(p, q, s);
    t1.setMatrixAt(i, m);
    t2.setMatrixAt(i, m);
  }
  scene.add(t1, t2);
  const hill = new THREE.MeshStandardMaterial({ color: 0x4d5a45, roughness: 1, flatShading: true });
  for (let i = 0; i < 22; i++) {
    const a = (i / 22) * Math.PI * 2 + rnd() * 0.3, r = 1400 + rnd() * 700;
    const h = new THREE.Mesh(new THREE.ConeGeometry(220 + rnd() * 260, 80 + rnd() * 160, 9), hill);
    h.position.set(Math.cos(a) * r, GROUND_Y + 30, Math.sin(a) * r);
    scene.add(h);
  }
  // a few targets on the range to the north, where the TADS looks
  const tankMat = new THREE.MeshStandardMaterial({ color: 0x4c513b, roughness: 0.9 });
  for (const [x, z] of [[0, 650], [-25, 700], [20, 620]]) {
    const t = new THREE.Group();
    t.add(new THREE.Mesh(new THREE.BoxGeometry(3.4, 1.2, 7), tankMat).translateY(0.6));
    t.add(new THREE.Mesh(new THREE.BoxGeometry(2.2, 0.8, 3), tankMat).translateY(1.6));
    t.position.set(x, GROUND_Y, z);
    scene.add(t);
  }
}

const hemi = new THREE.HemisphereLight(0xdfe8f5, 0x5a5040, 1.1);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff0da, 3.2);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -9, right: 9, top: 9, bottom: -9, near: 1, far: 60 });
sun.shadow.bias = -0.0004;
sun.shadow.normalBias = 0.02;
scene.add(sun, sun.target);

// --- the aircraft ---------------------------------------------------------------------------------------------------
const aircraft = new THREE.Group();
scene.add(aircraft);
const floods = [new THREE.PointLight(0xb9ffb0, 0, 1.7, 2), new THREE.PointLight(0xb9ffb0, 0, 1.7, 2)];
floods[0].position.set(0, 1.25, 0.45);
floods[1].position.set(0, 1.62, -0.95);
aircraft.add(...floods);
const searchlight = new THREE.SpotLight(0xfff4e0, 0, 400, 0.28, 0.4, 1);
searchlight.position.set(0, -0.5, 1.2);
searchlight.target.position.set(0, -12, 40);
aircraft.add(searchlight, searchlight.target);
const navPoints = { Light_Nav_Left: new THREE.PointLight(0xff3020, 0, 6, 2), Light_Nav_Right: new THREE.PointLight(0x30ff60, 0, 6, 2), Light_Nav_Tail: new THREE.PointLight(0xffffff, 0, 6, 2) };
const strobe = new THREE.PointLight(0xffffff, 0, 30, 2);
aircraft.add(strobe);

let model, controls, sim, displays, fx, eyes = {}, nodes = {}, mats = {};
const sound = new Sound();

// --- camera: seated at an eye point, or walking around -------------------------------------------------------------
const camera = new THREE.PerspectiveCamera(70, 1, 0.02, 6000);
const rig = new THREE.Group();
rig.add(camera);
aircraft.add(rig);
const orbit = new OrbitControls(camera, canvas);
orbit.enabled = false;
orbit.enableDamping = true;
orbit.minDistance = 2;
orbit.maxDistance = 30;
orbit.maxPolarAngle = Math.PI * 0.53;
const look = { yaw: 0, pitch: -0.14, fov: 70 };
let seat = "pilot";

function place() {
  if (seat === "walk") return;
  const e = eyes[seat];
  if (e) rig.position.copy(e);
  camera.position.set(0, 0, 0);
  camera.rotation.set(look.pitch, Math.PI + look.yaw, 0, "YXZ");
  camera.fov = look.fov;
  camera.updateProjectionMatrix();
}

function setSeat(s) {
  seat = s;
  for (const b of document.querySelectorAll("[data-seat]")) b.setAttribute("aria-selected", String(b.dataset.seat === s));
  if (s === "walk") {
    scene.attach(rig);
    rig.position.set(0, 0, 0);
    rig.quaternion.identity();
    orbit.enabled = true;
    camera.fov = 45;
    camera.updateProjectionMatrix();
    const t = aircraft.position.clone().add(new THREE.Vector3(0, 0.9, -2.5));
    camera.position.copy(t).add(new THREE.Vector3(-7.5, 3.2, 7.5));
    orbit.target.copy(t);
    orbit.update();
  } else {
    orbit.enabled = false;
    aircraft.attach(rig);
    rig.quaternion.identity();
    Object.assign(look, { yaw: 0, pitch: s === "pilot" ? -0.14 : -0.2, fov: 70 });
    place();
  }
  hintDefault();
}
for (const b of document.querySelectorAll("[data-seat]")) b.addEventListener("click", () => setSeat(b.dataset.seat));

// --- status line and toasts ------------------------------------------------------------------------------------------------
const statusEl = $("status");
let toastUntil = 0;
function toast(text) {
  if (!text) return;
  statusEl.textContent = text;
  toastUntil = performance.now() + 2500;
  vrLabel.show(text, null);
}
function hintDefault() {
  if (performance.now() < toastUntil) return;
  statusEl.textContent = seat === "walk" ? "Drag to orbit. Scroll or pinch to zoom." : "Click switches, knobs and buttons. Drag sticks and levers. Drag empty space to look.";
}

// A label that floats by the control you point at, for VR (and it helps on screen too).
const vrLabel = (() => {
  const c = document.createElement("canvas");
  c.width = 1024;
  c.height = 128;
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const spr = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false }));
  spr.renderOrder = 10;
  spr.scale.set(0.24, 0.03, 1);
  spr.visible = false;
  scene.add(spr);
  let last = "", until = 0;
  return {
    show(text, at) {
      const g = c.getContext("2d");
      if (text !== last) {
        g.clearRect(0, 0, 1024, 128);
        g.font = "bold 44px 'Saira Condensed', 'Arial Narrow', sans-serif";
        const w = Math.min(1000, g.measureText(text).width + 48);
        g.fillStyle = "rgba(20,22,24,0.88)";
        g.fillRect((1024 - w) / 2, 24, w, 80);
        g.fillStyle = "#ffc23d";
        g.textAlign = "center";
        g.textBaseline = "middle";
        g.fillText(text, 512, 66);
        tex.needsUpdate = true;
        last = text;
      }
      if (at) spr.position.copy(at);
      until = performance.now() + (at ? 400 : 2500);
      spr.visible = renderer.xr.isPresenting;
    },
    update(camPos) {
      if (performance.now() > until) spr.visible = false;
      else if (!spr.userData.anchored && camPos && renderer.xr.isPresenting) {
        // toasts float in front of you
      }
    },
    sprite: spr,
  };
})();

// --- picking ------------------------------------------------------------------------------------------------------------------
const raycaster = new THREE.Raycaster();
const ndc = new THREE.Vector2();
function pickFrom(ray) {
  raycaster.ray.copy(ray);
  raycaster.near = 0.01;
  raycaster.far = seat === "walk" ? 60 : 3;
  const hits = raycaster.intersectObject(model, true);
  for (const h of hits) {
    if (!h.object.visible) continue;
    const c = controls.pick(h.object);
    if (c) return { c, hit: h };
    if (h.object.material && h.object.material.transparent) continue;
    return null;
  }
  return null;
}
function pickScreen(x, y) {
  const r = canvas.getBoundingClientRect();
  ndc.set(((x - r.left) / r.width) * 2 - 1, -((y - r.top) / r.height) * 2 + 1);
  raycaster.setFromCamera(ndc, camera);
  return pickFrom(raycaster.ray);
}
// Was the hit above the control's pivot, along the panel's "up"?
const tv = new THREE.Vector3(), tq = new THREE.Quaternion();
function hitAbove(c, point) {
  c.obj.parent.getWorldQuaternion(tq);
  tq.multiply(c.restQ);
  const up = tv.set(0, 1, 0).applyQuaternion(tq);
  const pivot = c.obj.getWorldPosition(new THREE.Vector3());
  return point.clone().sub(pivot).dot(up) > 0;
}

const box = new THREE.Box3Helper(new THREE.Box3(), 0xffc23d);
box.visible = false;
scene.add(box);
let hovered = null;
function setHover(c) {
  hovered = c;
  if (!c) {
    box.visible = false;
    hintDefault();
    return;
  }
  box.box.setFromObject(c.obj).expandByScalar(0.003);
  box.visible = true;
  if (performance.now() > toastUntil) statusEl.textContent = c.describe();
}

function operate(c, opts) {
  controls.click(c, opts);
  sound.click();
}

// --- mouse and touch ---------------------------------------------------------------------------------------------------------
const pointers = new Map();
let pinch0 = 0;
let drag = null;
canvas.addEventListener("contextmenu", (e) => e.preventDefault());
canvas.addEventListener("pointerdown", (e) => {
  if (!model) return;
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY });
  try {
    canvas.setPointerCapture(e.pointerId);
  } catch (_) {}
  const p = pickScreen(e.clientX, e.clientY);
  drag = { c: p ? p.c : null, hit: p ? p.hit : null, button: e.button, moved: false, id: e.pointerId };
});
canvas.addEventListener("pointermove", (e) => {
  const p = pointers.get(e.pointerId);
  if (!p) {
    if (model && e.pointerType === "mouse") throttleHover(e.clientX, e.clientY);
    return;
  }
  const dx = e.clientX - p.x, dy = e.clientY - p.y;
  p.x = e.clientX;
  p.y = e.clientY;
  if (drag && Math.hypot(e.clientX - p.x0, e.clientY - p.y0) > 6) drag.moved = true;
  if (pointers.size === 2 && seat !== "walk") {
    const [a, b] = [...pointers.values()];
    const d = Math.hypot(a.x - b.x, a.y - b.y);
    if (pinch0) look.fov = THREE.MathUtils.clamp(look.fov * (pinch0 / d), 25, 95);
    pinch0 = d;
    place();
    return;
  }
  if (drag && drag.c && drag.c.draggable && drag.moved) {
    const c = drag.c;
    const k = c.kind === "stick" ? 0.006 : c.kind === "lever" ? 0.006 : 0.004;
    controls.drag(c, dx * k, -dy * k);
    statusEl.textContent = c.describe();
    return;
  }
  if (seat === "walk" || !drag || !drag.moved) return;
  const k = (look.fov / 70) * 0.0042;
  look.yaw += dx * k;
  look.pitch = THREE.MathUtils.clamp(look.pitch + dy * k, -1.35, 1.2);
  place();
});
const lift = (e) => {
  pointers.delete(e.pointerId);
  pinch0 = 0;
  if (!drag || drag.id !== e.pointerId) return;
  const d = drag;
  drag = null;
  if (!d.c) return;
  if (d.moved && d.c.draggable) return controls.release(d.c);
  if (!d.moved) operate(d.c, { dir: d.button === 2 || e.shiftKey ? -1 : 1, up: hitAbove(d.c, d.hit.point) });
};
canvas.addEventListener("pointerup", lift);
canvas.addEventListener("pointercancel", lift);
let hoverAt = 0;
function throttleHover(x, y) {
  const now = performance.now();
  if (now < hoverAt) return;
  hoverAt = now + 40;
  const p = pickScreen(x, y);
  if ((p && p.c) !== hovered) setHover(p ? p.c : null);
  canvas.style.cursor = p ? "pointer" : seat === "walk" ? "grab" : "grab";
}
canvas.addEventListener(
  "wheel",
  (e) => {
    if (seat === "walk") return;
    e.preventDefault();
    if (hovered && hovered.kind === "rotary") {
      if (hovered.positions) operate(hovered, { dir: e.deltaY > 0 ? 1 : -1 });
      else controls.drag(hovered, 0, e.deltaY > 0 ? -0.05 : 0.05);
      statusEl.textContent = hovered.describe();
      return;
    }
    look.fov = THREE.MathUtils.clamp(look.fov * (1 + e.deltaY * 0.001), 25, 95);
    place();
  },
  { passive: false }
);

// --- keyboard: fly with the keys --------------------------------------------------------------------------------------------------
const keys = new Set();
window.addEventListener("keydown", (e) => {
  if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
  keys.add(e.code);
  if (!model) return;
  if (e.code === "Space") {
    e.preventDefault();
    const t = controls.get("trigger");
    if (t) operate(t, {});
  }
  if (e.code === "KeyG") {
    const w = controls.get("was");
    if (w) operate(w, {});
  }
  if (e.code === "Digit1") setSeat("pilot");
  if (e.code === "Digit2") setSeat("cpg");
  if (e.code === "Digit3") setSeat("walk");
  if (seat !== "walk" && e.code.startsWith("Arrow")) {
    const s = 0.06;
    if (e.code === "ArrowLeft") look.yaw += s;
    if (e.code === "ArrowRight") look.yaw -= s;
    if (e.code === "ArrowUp") look.pitch = Math.min(1.2, look.pitch + s);
    if (e.code === "ArrowDown") look.pitch = Math.max(-1.35, look.pitch - s);
    place();
    e.preventDefault();
  }
});
window.addEventListener("keyup", (e) => keys.delete(e.code));

let keyStick = false, keyPedal = false;
function keyboardFlight(dt) {
  const cyc = controls.get("cyclic"), col = controls.get("collective"), ped = controls.get("pedals");
  const x = (keys.has("KeyD") ? 1 : 0) - (keys.has("KeyA") ? 1 : 0);
  const y = (keys.has("KeyW") ? 1 : 0) - (keys.has("KeyS") ? 1 : 0);
  if (cyc && (x || y || keyStick)) {
    keyStick = !!(x || y);
    controls.set(cyc, { stick: { x: x * 0.8, y: y * 0.8 } }, "key");
  }
  const up = (keys.has("KeyR") || keys.has("PageUp") ? 1 : 0) - (keys.has("KeyF") || keys.has("PageDown") ? 1 : 0);
  if (col && up) controls.set(col, { value: THREE.MathUtils.clamp(col.value + up * 0.3 * dt, 0, 1) }, "key");
  const p = (keys.has("KeyE") ? 1 : 0) - (keys.has("KeyQ") ? 1 : 0);
  if (ped && (p || keyPedal)) {
    keyPedal = !!p;
    controls.set(ped, { value: 0.5 + p * 0.45 }, "key");
  }
  // slew the TADS
  const az = (keys.has("KeyL") ? 1 : 0) - (keys.has("KeyJ") ? 1 : 0);
  const el = (keys.has("KeyI") ? 1 : 0) - (keys.has("KeyK") ? 1 : 0);
  if (az || el) {
    sim.tedac.slaved = false;
    const rate = { W: 20, M: 8, N: 3 }[sim.tedac.fov];
    sim.tedac.az = THREE.MathUtils.clamp(sim.tedac.az + az * rate * dt, -120, 120);
    sim.tedac.el = THREE.MathUtils.clamp(sim.tedac.el + el * rate * dt, -60, 30);
  }
}

// --- VR -------------------------------------------------------------------------------------------------------------------------------
const hands = [0, 1].map((i) => {
  const ctrl = renderer.xr.getController(i);
  const grip = renderer.xr.getControllerGrip(i);
  const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, -1)]), new THREE.LineBasicMaterial({ color: 0xffc23d, transparent: true, opacity: 0.7 }));
  line.scale.z = 0.6;
  ctrl.add(line);
  const body = new THREE.Mesh(new THREE.BoxGeometry(0.035, 0.03, 0.11), new THREE.MeshStandardMaterial({ color: 0x2b2e30, roughness: 0.6 }));
  body.position.z = 0.03;
  grip.add(body);
  rig.add(ctrl, grip);
  const hand = { ctrl, grip, line, hover: null, grab: null, last: new THREE.Vector3(), handedness: "" };
  ctrl.addEventListener("connected", (e) => (hand.handedness = e.data.handedness));
  const begin = () => {
    if (!model) return;
    const p = pickFrom(rayOf(ctrl));
    if (!p) return;
    if (p.c.draggable) {
      hand.grab = p.c;
      hand.last.copy(localPos(ctrl));
    } else operate(p.c, { dir: 1, up: hitAbove(p.c, p.hit.point) });
    vrLabel.show(p.c.describe(), p.hit.point);
  };
  const end = () => {
    if (hand.grab) controls.release(hand.grab);
    hand.grab = null;
  };
  ctrl.addEventListener("selectstart", begin);
  ctrl.addEventListener("selectend", end);
  ctrl.addEventListener("squeezestart", begin);
  ctrl.addEventListener("squeezeend", end);
  return hand;
});
function rayOf(obj) {
  obj.updateWorldMatrix(true, false);
  const r = new THREE.Ray();
  r.origin.setFromMatrixPosition(obj.matrixWorld);
  r.direction.set(0, 0, -1).transformDirection(obj.matrixWorld);
  return r;
}
function localPos(obj) {
  return aircraft.worldToLocal(obj.getWorldPosition(new THREE.Vector3()));
}
function vrFrame(dt) {
  const session = renderer.xr.getSession();
  if (!session) return;
  for (const h of hands) {
    if (h.grab) {
      const now = localPos(h.ctrl);
      const d = now.clone().sub(h.last);
      h.last.copy(now);
      const c = h.grab;
      // aircraft-local: +X is left, +Y up, +Z forward
      if (c.kind === "stick") controls.drag(c, -d.x / 0.1, d.z / 0.1);
      else if (c.kind === "collective") controls.drag(c, 0, d.y / 0.15);
      else if (c.kind === "lever") controls.drag(c, 0, d.z / 0.1);
      else if (c.kind === "pedal") controls.drag(c, -d.x / 0.15, 0);
      else controls.drag(c, 0, d.y / 0.1);
      vrLabel.show(c.describe(), c.obj.getWorldPosition(new THREE.Vector3()));
      continue;
    }
    const p = model ? pickFrom(rayOf(h.ctrl)) : null;
    h.line.scale.z = p ? p.hit.distance : 0.6;
    if (p) vrLabel.show(p.c.describe(), p.hit.point.clone().add(new THREE.Vector3(0, 0.03, 0)));
    h.hover = p ? p.c : null;
  }
  // thumbsticks: left flies the collective and pedals, right the cyclic
  for (const src of session.inputSources) {
    const gp = src.gamepad;
    if (!gp || gp.axes.length < 4) continue;
    const ax = gp.axes[2], ay = gp.axes[3];
    const hand = hands.find((h) => h.handedness === src.handedness);
    if (hand && hand.grab) continue;
    if (src.handedness === "right") {
      const cyc = controls.get("cyclic");
      if (cyc && (Math.abs(ax) > 0.1 || Math.abs(ay) > 0.1 || cyc._thumb)) {
        cyc._thumb = Math.abs(ax) > 0.1 || Math.abs(ay) > 0.1;
        controls.set(cyc, { stick: { x: dead(ax), y: -dead(ay) } }, "vr");
      }
    } else if (src.handedness === "left") {
      const col = controls.get("collective"), ped = controls.get("pedals");
      if (col && Math.abs(ay) > 0.15) controls.set(col, { value: THREE.MathUtils.clamp(col.value - dead(ay) * 0.3 * dt, 0, 1) }, "vr");
      if (ped && (Math.abs(ax) > 0.1 || ped._thumb)) {
        ped._thumb = Math.abs(ax) > 0.1;
        controls.set(ped, { value: 0.5 + dead(ax) * 0.5 }, "vr");
      }
    }
  }
}
const dead = (v) => (Math.abs(v) < 0.1 ? 0 : v);

const vrBtn = $("vr");
if (navigator.xr && navigator.xr.isSessionSupported) {
  navigator.xr.isSessionSupported("immersive-vr").then((ok) => {
    if (!ok) return;
    vrBtn.hidden = false;
    vrBtn.addEventListener("click", async () => {
      if (renderer.xr.isPresenting) return renderer.xr.getSession().end();
      if (seat === "walk") setSeat("pilot");
      camera.position.set(0, 0, 0);
      camera.rotation.set(0, Math.PI, 0);
      rig.rotation.set(0, Math.PI, 0);
      try {
        const session = await navigator.xr.requestSession("immersive-vr", { optionalFeatures: ["local-floor"] });
        await renderer.xr.setSession(session);
        sun.castShadow = false; // headsets are better off without the shadow pass
        vrBtn.textContent = "Exit VR";
        session.addEventListener("end", () => {
          vrBtn.textContent = "Enter VR";
          sun.castShadow = true;
          rig.rotation.set(0, 0, 0);
          place();
        });
      } catch (err) {
        toast("This browser could not start VR: " + err.message);
      }
    });
  }).catch(() => {});
}

// --- scene toggles ------------------------------------------------------------------------------------------------------------------
let night = false;
function setNight(on) {
  night = on;
  if (on) {
    skyU.top.value.set(0x05070d);
    skyU.horizon.value.set(0x1a2233);
    skyU.below.value.set(0x0b0d0c);
    hemi.intensity = 0.06;
    sun.intensity = 0;
    scene.environmentIntensity = 0.03;
    renderer.toneMappingExposure = 1.15;
    ground.material.color.set(0x303a30);
  } else {
    skyU.top.value.set(0x4f7fbf);
    skyU.horizon.value.set(0xd8e2ea);
    skyU.below.value.set(0x6b705c);
    hemi.intensity = 1.1;
    sun.intensity = 3.2;
    scene.environmentIntensity = 0.55;
    renderer.toneMappingExposure = 1.0;
    ground.material.color.set(0xffffff);
  }
}
setNight(false);
const toggle = (id, fn) => {
  const b = $(id);
  b.addEventListener("click", () => {
    const on = b.getAttribute("aria-pressed") !== "true";
    b.setAttribute("aria-pressed", String(on));
    fn(on);
  });
};
toggle("night", setNight);
toggle("sound", (on) => (on ? sound.start() : sound.stop()));
$("reset").addEventListener("click", () => {
  if (!model) return;
  fx.reset();
  controls.resetAll();
  sim.reset();
  displays.reset();
  if (seat === "walk") setSeat("walk");
  toast("Reset: on the pad, engines running");
});
$("help-toggle").addEventListener("click", () => {
  const h = $("help");
  h.hidden = !h.hidden;
  $("help-toggle").setAttribute("aria-expanded", String(!h.hidden));
});

// --- control changes: into the simulation and the displays -------------------------------------------------------------------------
function onControl(c, ev) {
  if (!sim) return;
  const fn = c.fn || "";
  if (ev.pressed && fn.includes(":")) {
    const kind = fn.split(":")[0];
    if (c.kind === "rocker") toast(displays.rocker(fn, c.state === 0 ? 1 : -1));
    else toast(displays.key(fn) || "");
  } else if (fn.includes(":") && c.kind === "rotary") {
    if (fn.endsWith(":MODE")) displays.mode(fn, c.positions[c.state]);
    if (fn.startsWith("eufd:")) displays.eufdBrightness(fn.split(":")[1], c.value);
  }
  sim.control(c, ev);
  if (ev.source === "user" && !ev.pressed && c.positions && !["stick", "collective", "pedal"].includes(c.kind)) toast(c.describe());
}

// --- load ----------------------------------------------------------------------------------------------------------------------------------
const loading = $("loading");
function onModel(gltf) {
  model = gltf.scene;
  aircraft.add(model);
  model.traverse((o) => {
    if (o.isMesh) {
      const m = o.material;
      o.castShadow = !m.transparent;
      o.receiveShadow = !m.transparent;
      if (m.transparent) {
        m.depthWrite = false;
        o.renderOrder = 2;
      }
      mats[m.name] = m;
    }
    if (o.name) nodes[o.name] = o;
  });
  model.updateMatrixWorld(true);
  for (const s of ["Pilot", "CPG"]) {
    const e = nodes[`${s}_Eye`];
    if (e) eyes[s === "Pilot" ? "pilot" : "cpg"] = aircraft.worldToLocal(e.getWorldPosition(new THREE.Vector3()));
  }
  for (const [n, l] of Object.entries(navPoints)) if (nodes[n]) nodes[n].add(l);
  if (nodes.Light_Anticollision_Top) nodes.Light_Anticollision_Top.add(strobe);
  controls = new Controls(model, (c, ev) => onControl(c, ev));
  // small moving parts don't need to cast shadows
  for (const c of controls.list) c.obj.traverse((o) => o.isMesh && (o.castShadow = false));
  sim = new Sim(controls);
  displays = new Displays(model, sim, window.CockpitPaint);
  fx = new Effects(scene, aircraft, model, GROUND_Y);
  loading.hidden = true;
  $("count").textContent = `${controls.list.length} working controls`;
  const start = (location.hash || "").slice(1);
  setSeat(start === "cpg" || start === "walk" ? start : "pilot");
  // For scripted checks: advance everything by `sec` seconds in fixed steps, without drawing.
  const step = (sec, h = 1 / 30) => { for (let t = 0; t < sec; t += h) tick(h, performance.now()); };
  window.cockpit = { controls, sim, displays, fx, nodes, setSeat, look, place, operate, aircraft, camera, pickScreen, setNight, renderer, scene, step };
}
function onProgress(loaded, total) {
  if (!total) return;
  const pct = Math.round((loaded / total) * 100);
  $("pct").textContent = pct + "%";
  $("bar").style.width = pct + "%";
}
function onFail(err) {
  loading.hidden = false;
  loading.classList.add("err");
  loading.querySelector(".plate").textContent = "The cockpit model could not be loaded. Reload the page to try again.";
  console.error(err);
}
function fromBase64(text) {
  const bin = atob(text.trim());
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}
(async () => {
  const loader = new GLTFLoader();
  // the single-file viewer carries the model in the page itself
  const embedded = document.getElementById("cockpit-model");
  if (embedded) {
    onProgress(1, 1);
    await new Promise((r) => setTimeout(r, 30)); // let the loading bar paint first
    try {
      return loader.parse(fromBase64(embedded.textContent), "", onModel, onFail);
    } catch (err) {
      return onFail(err);
    }
  }
  if (!MODEL_URL.endsWith(".txt")) return loader.load(MODEL_URL, onModel, (e) => onProgress(e.loaded, e.total), onFail);
  // the model shipped base64-encoded in a text file
  try {
    const res = await fetch(MODEL_URL);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const total = +res.headers.get("content-length") || 7000000;
    const reader = res.body.getReader();
    const parts = [];
    let got = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      parts.push(value);
      got += value.length;
      onProgress(Math.min(got, total), total);
    }
    loader.parse(fromBase64(new TextDecoder().decode(await new Blob(parts).arrayBuffer())), "", onModel, onFail);
  } catch (err) {
    onFail(err);
  }
})();

function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
window.addEventListener("resize", resize);
resize();

// --- the frame ----------------------------------------------------------------------------------------------------------------------------------
const clock = new THREE.Clock();
const tmpV = new THREE.Vector3();
let lastRead = 0;
let lastPos = null;
// One step of everything but drawing: controls, systems, flight, displays, effects.
function tick(dt, now) {
  keyboardFlight(dt);
  vrFrame(dt);
  const cyc = controls.get("cyclic"), col = controls.get("collective"), ped = controls.get("pedals");
  sim.input = { x: cyc ? cyc.stick.x : 0, y: cyc ? cyc.stick.y : 0, col: col ? col.value : 0, ped: ped ? (ped.value - 0.5) * 2 : 0 };
  sim.update(dt);
  // the aircraft
  aircraft.position.set(sim.p[0], sim.p[1], sim.p[2]);
  aircraft.rotation.set(-sim.pitch * rad, -sim.hdg * rad, sim.roll * rad, "YXZ");
  fx.aircraftVel = new THREE.Vector3(...sim.v);
  sim.rotorAngle += (sim.nr / 101) * 7.5 * dt;
  sim.tailAngle += (sim.nr / 101) * 30 * dt;
  if (nodes.Main_Rotor) nodes.Main_Rotor.rotation.y = sim.rotorAngle;
  if (nodes.Tail_Rotor) nodes.Tail_Rotor.rotation.x = sim.tailAngle;
  // sight, sensors and gun
  const t = sim.tedac;
  if (nodes.TADS_Turret) nodes.TADS_Turret.rotation.y = -t.az * rad;
  if (nodes.TADS_Sensors) nodes.TADS_Sensors.rotation.x = -t.el * rad;
  if (nodes.PNVS_Turret) nodes.PNVS_Turret.rotation.y = seat === "pilot" ? look.yaw : 0;
  const gunOn = sim.weapon === "GUN";
  if (nodes.M230_Turret) nodes.M230_Turret.rotation.y += ((gunOn ? -THREE.MathUtils.clamp(t.az, -86, 86) * rad : 0) - nodes.M230_Turret.rotation.y) * Math.min(1, dt * 4);
  if (nodes.M230_Gun) nodes.M230_Gun.rotation.x += ((gunOn ? -THREE.MathUtils.clamp(t.el, -60, 11) * rad : -0.15) - nodes.M230_Gun.rotation.x) * Math.min(1, dt * 4);
  // lights
  const nav = { OFF: 0, BRT: 1.6, DIM: 0.5 }[sim.state("navLt") || "BRT"];
  for (const n of ["Light_Nav_Red", "Light_Nav_Green", "Light_Nav_White"]) if (mats[n]) mats[n].emissiveIntensity = nav;
  for (const l of Object.values(navPoints)) l.intensity = nav * (night ? 1.2 : 0);
  const acol = sim.state("acolLt") || "OFF";
  const blink = acol !== "OFF" && sim.t % 1.1 < 0.09;
  if (mats.Light_Anticollision) {
    mats.Light_Anticollision.emissive.set(acol === "RED" ? 0xff2a1a : 0xffffff);
    mats.Light_Anticollision.emissiveIntensity = blink ? 3 : 0;
  }
  strobe.color.set(acol === "RED" ? 0xff3020 : 0xffffff);
  strobe.intensity = blink ? (night ? 8 : 2) : 0;
  const primary = Math.max(sim.value("intPrimary", 0.7), sim.value("cpgIntPrimary", 0.7));
  if (mats.Panels) mats.Panels.emissiveIntensity = 0.1 + primary * 1.4;
  floods[1].intensity = sim.value("intFlood", 0.3) * 0.7;
  floods[0].intensity = sim.value("cpgIntFlood", 0.3) * 0.7;
  searchlight.intensity = sim.state("searchlight") === "ON" ? 60 : 0;
  displays.dimmed = sim.state("intMode") === "NT" ? 0.6 : 1;
  // lit buttons follow the systems
  if (sim.lit) {
    for (const [fn, on] of Object.entries(sim.lit)) controls.setLit(fn, on, fn === "masterArm" && sim.masterArm ? "#ff4a36" : undefined);
  }
  // what happened this frame
  for (const ev of sim.events.splice(0)) {
    if (ev.type === "toast") toast(ev.text);
    else if (ev.type === "gun") (fx.gunRound(), sound.gun());
    else if (ev.type === "rocket") (fx.rocket(ev.station), sound.whoosh());
    else if (ev.type === "missile") (fx.missile(ev.station, ev.index, ev.target), sound.whoosh());
    else if (ev.type === "jettison") fx.jettison(ev.station);
    else if (ev.type === "canopyJett") (fx.canopy(), sound.boom());
    else if (ev.type === "flare") {
      const p = aircraft.localToWorld(new THREE.Vector3(0, 0.6, -3.5));
      for (let i = 0; i < 4; i++) fx.puff(p, 0xffe0a0, 1.2, 1.6, 1.4, new THREE.Vector3((Math.random() - 0.5) * 20, -4 - Math.random() * 3, (Math.random() - 0.5) * 20).add(fx.aircraftVel), true, 1);
    }
  }
  controls.update(dt);
  displays.update(now);
  fx.update(dt);
  sound.update(sim, sim.t);
  // the standby instruments
  const d = sim.data();
  if (nodes.Pilot_Standby_ASI_Needle) nodes.Pilot_Standby_ASI_Needle.rotation.z = -(Math.min(200, d.ias) / 200) * 1.75 * Math.PI;
  if (nodes.Pilot_Standby_ALT_Needle1) nodes.Pilot_Standby_ALT_Needle1.rotation.z = -((d.alt % 1000) / 1000) * 2 * Math.PI;
  if (nodes.Pilot_Standby_ALT_Needle2) nodes.Pilot_Standby_ALT_Needle2.rotation.z = -((d.alt % 10000) / 10000) * 2 * Math.PI;
  const clockNow = new Date();
  if (nodes.Pilot_Clock_Needle1) nodes.Pilot_Clock_Needle1.rotation.z = -(clockNow.getMinutes() / 60) * 2 * Math.PI;
  if (nodes.Pilot_Clock_Needle2) nodes.Pilot_Clock_Needle2.rotation.z = -(((clockNow.getHours() % 12) + clockNow.getMinutes() / 60) / 12) * 2 * Math.PI;
  // the sun and its shadows follow the aircraft
  sun.position.copy(aircraft.position).add(new THREE.Vector3(-12, 20, 9));
  sun.target.position.copy(aircraft.position);
  // in the walkaround the camera travels with the aircraft
  if (!lastPos) lastPos = aircraft.position.clone();
  const moved = tmpV.copy(aircraft.position).sub(lastPos);
  lastPos.copy(aircraft.position);
  if (seat === "walk") {
    camera.position.add(moved);
    orbit.target.add(moved);
    orbit.update();
  }
  if (now > lastRead) {
    lastRead = now + 250;
    $("readout").textContent = `${Math.round(d.ias)} KT  ·  ${Math.round(d.ralt)} FT AGL  ·  HDG ${String(Math.round(d.hdg) % 360).padStart(3, "0")}  ·  NR ${Math.round(d.nr)}%  ·  ${sim.weapon} ${sim.masterArm ? "ARM" : "SAFE"}`;
  }
  vrLabel.update();
}

renderer.setAnimationLoop(() => {
  const dt = Math.min(clock.getDelta(), 0.05);
  const now = performance.now();
  if (model) tick(dt, now);
  renderer.render(scene, camera);
});
