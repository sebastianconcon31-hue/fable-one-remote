// Shows the HEMTT and works its moving parts by name: doors, wheels and
// steering, the crane, the pallet loads and the lights.
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
const sky = new THREE.Color(0xa9bfd6);
scene.background = sky.clone();
scene.fog = new THREE.Fog(sky.clone(), 60, 220);
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
orbit.minDistance = 2;
orbit.maxDistance = 40;
orbit.maxPolarAngle = Math.PI * 0.495;
const VIEWS = {
  front: [[7.5, 2.6, 10.5], [0, 1.3, 0.4]],
  side: [[14.5, 2.0, -0.4], [0, 1.4, -0.4]],
  rear: [[-7.0, 4.0, -12.5], [0, 1.4, -1.5]],
  top: [[0.01, 17, -0.4], [0, 0, -0.4]],
};
function view(name) {
  const [p, t] = VIEWS[name];
  camera.position.set(...p);
  orbit.target.set(...t);
  orbit.update();
}
for (const b of document.querySelectorAll("[data-view]")) b.addEventListener("click", () => view(b.dataset.view));
view("front");

const status = (t) => ($("status").textContent = t);
const nodes = {};
const mats = {};
const rest = new Map();
let model;

function onModel(gltf) {
  model = gltf.scene;
  model.traverse((o) => {
    if (o.isMesh) {
      o.castShadow = !o.material.transparent;
      o.receiveShadow = true;
      if (o.material.transparent) o.material.depthWrite = false;
      mats[o.material.name] = o.material;
    }
    if (o.name) {
      nodes[o.name] = o;
      rest.set(o, { q: o.quaternion.clone(), p: o.position.clone() });
    }
  });
  scene.add(model);
  $("loading").hidden = true;
  status("Doors, drive and steering, the crane, and eight pallets to unload.");
}
function onFail(e) {
  $("loading").textContent = "The truck could not be loaded.";
  console.error(e);
}
const loader = new GLTFLoader();
const embedded = document.getElementById("truck-model");
if (embedded) {
  const bin = atob(embedded.textContent.trim());
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  setTimeout(() => loader.parse(bytes.buffer, "", onModel, onFail), 30);
} else loader.load(window.TRUCK_MODEL_URL || "../hemtt_m977a4_web.glb", onModel, undefined, onFail);

// ---- controls ---------------------------------------------------------------------------------------------------------------
const state = { doors: 0, doorsTarget: 0, drive: false, wheel: 0, speed: 0, steer: 0, slew: 0, luff: 0, reach: 0, night: false, lifting: null, unloaded: [] };
const toggle = (b, on) => b.setAttribute("aria-pressed", String(on));
$("doors").addEventListener("click", (e) => {
  state.doorsTarget = state.doorsTarget ? 0 : 1;
  toggle(e.currentTarget, !!state.doorsTarget);
});
$("drive").addEventListener("click", (e) => {
  state.drive = !state.drive;
  toggle(e.currentTarget, state.drive);
});
$("lights").addEventListener("click", (e) => {
  state.night = !state.night;
  toggle(e.currentTarget, state.night);
  const n = state.night;
  hemi.intensity = n ? 0.06 : 0.9;
  sun.intensity = n ? 0.05 : 3.2;
  scene.environmentIntensity = n ? 0.05 : 0.6;
  scene.background.set(n ? 0x0a0e16 : 0xa9bfd6);
  scene.fog.color.copy(scene.background);
  for (const k of ["Light_White", "Light_Amber", "Light_Red"]) if (mats[k]) mats[k].emissiveIntensity = n ? 6 : 1;
  for (const [name, color] of [["Light_Head_Left", 0xfff1d8], ["Light_Head_Right", 0xfff1d8]]) {
    const o = nodes[name];
    if (!o) continue;
    if (!o.userData.lamp) {
      const l = new THREE.SpotLight(color, 0, 40, 0.5, 0.5, 1.2);
      l.position.set(0, 0, 0.1);
      l.target.position.set(0, -0.6, 10);
      o.add(l, l.target);
      o.userData.lamp = l;
    }
    o.userData.lamp.intensity = n ? 60 : 0;
  }
});
for (const id of ["steer", "slew", "luff", "reach"]) $(id).addEventListener("input", (e) => (state[id] = +e.target.value));
$("unload").addEventListener("click", () => {
  if (state.lifting) return;
  for (let i = 1; i <= 8; i++) {
    const p = nodes[`Cargo_Pallet_${i}`];
    if (p && p.visible && !state.unloaded.includes(p)) {
      state.lifting = { p, t: 0 };
      status(`Lifting pallet ${i} off.`);
      return;
    }
  }
  status("The bed is empty. Reload it.");
});
$("reload").addEventListener("click", () => {
  for (const p of state.unloaded) {
    const r = rest.get(p);
    p.position.copy(r.p);
    p.visible = true;
  }
  state.unloaded = [];
  state.lifting = null;
  status("All eight pallets are back on the bed.");
});

// ---- animation ---------------------------------------------------------------------------------------------------------------
const qa = new THREE.Quaternion();
const axis = new THREE.Vector3();
function turn(o, a, ax) {
  const r = rest.get(o);
  axis.fromArray(ax || o.userData.axis || [0, 1, 0]).normalize();
  o.quaternion.copy(r.q).multiply(qa.setFromAxisAngle(axis, a));
}
const clock = new THREE.Clock();
function tick() {
  const dt = Math.min(clock.getDelta(), 0.05);
  if (model) {
    state.doors += (state.doorsTarget - state.doors) * Math.min(1, dt * 3);
    for (const s of ["Left", "Right"]) if (nodes[`Door_${s}`]) turn(nodes[`Door_${s}`], state.doors * 1.15);
    state.speed += ((state.drive ? 6 : 0) - state.speed) * Math.min(1, dt * 1.5);
    state.wheel += (state.speed / 0.62) * dt;
    for (let i = 1; i <= 4; i++) for (const s of ["Left", "Right"]) if (nodes[`Wheel_${i}_${s}`]) turn(nodes[`Wheel_${i}_${s}`], state.wheel, [1, 0, 0]);
    for (const s of ["Left", "Right"]) {
      if (nodes[`Steer_1_${s}`]) turn(nodes[`Steer_1_${s}`], state.steer * 0.55, [0, 1, 0]);
      if (nodes[`Steer_2_${s}`]) turn(nodes[`Steer_2_${s}`], state.steer * 0.37, [0, 1, 0]);
    }
    if (nodes.Crane) turn(nodes.Crane, state.slew, [0, 1, 0]);
    const luff = -state.luff * 1.25;
    if (nodes.Crane_Boom) turn(nodes.Crane_Boom, luff, [1, 0, 0]);
    if (nodes.Crane_Boom_Extension) {
      const e = nodes.Crane_Boom_Extension;
      e.position.copy(rest.get(e).p).add(new THREE.Vector3(0, 0, state.reach * 2.3));
    }
    if (nodes.Crane_Hook) turn(nodes.Crane_Hook, -luff, [1, 0, 0]); // the hook hangs plumb
    if (nodes.Light_Beacon) {
      const m = mats.Light_Amber;
      if (m && state.night) m.emissiveIntensity = 3 + 4 * Math.max(0, Math.sin(performance.now() / 120));
    }
    if (state.lifting) {
      const L = state.lifting;
      L.t += dt / 2.2;
      const r = rest.get(L.p);
      const up = Math.min(1, L.t * 2) * 1.6;
      const out = Math.max(0, L.t * 2 - 1) * 2.6 * Math.sign(r.p.x || 1);
      L.p.position.set(r.p.x + out, r.p.y + up, r.p.z);
      if (L.t >= 1) {
        L.p.visible = false;
        state.unloaded.push(L.p);
        state.lifting = null;
        status(`${8 - state.unloaded.length} pallets left on the bed.`);
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
window.truck = { nodes, state, scene, camera };
