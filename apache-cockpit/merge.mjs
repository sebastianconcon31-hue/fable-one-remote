#!/usr/bin/env node
// Joins the cockpit (generate.mjs) and the outside (exterior/build.py) into
// the whole aircraft:
//
//   apache_ah64d.glb          the game model: every control and moving part is its own node
//   apache_ah64d_static.glb   the same with the cockpit's controls merged (fewer draw calls)
//   apache_ah64d_web.glb      for the browser viewer: smaller WebP textures
//
//   node merge.mjs [--exterior exterior/apache_exterior.glb] [--out dir]
//
// The canopy doors are the cockpit's operable door nodes; the exterior's door
// glass and frames are moved onto them, so opening a door opens the real canopy.
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { mergeDocuments, unpartition, prune, textureCompress, dedup } from "@gltf-transform/functions";
import sharp from "sharp";
import { readFileSync, writeFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (k, d) => (args.includes(k) ? args[args.indexOf(k) + 1] : d);
const outDir = opt("--out", here);
const exteriorPath = opt("--exterior", join(here, "apache_exterior.glb"));
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);

// What each moving or detachable part of the outside does; the viewer drives them the same way.
const deg = Math.PI / 180;
const NOTES = {
  Exterior: { note: "the outside at 1:1, built by exterior/build.py from published AH-64D dimensions (see measurements.json)" },
  Ground_Reference: { marker: "ground level under the wheels" },
  Main_Rotor: { drive: "spin about local Y; + is counter-clockwise seen from above, as on the real aircraft", axis: [0, 1, 0], rpm100: 289 },
  Tail_Rotor: { drive: "spin about local X", axis: [1, 0, 0], rpm100: 1403 },
  TADS_Turret: { drive: "slew in azimuth about local Y (±120°)", axis: [0, 1, 0], limits: [-120 * deg, 120 * deg] },
  TADS_Sensors: { drive: "elevate about local X (+30° up to -60° down)", axis: [1, 0, 0], limits: [-60 * deg, 30 * deg] },
  PNVS_Turret: { drive: "slew in azimuth about local Y; follows the pilot's head", axis: [0, 1, 0], limits: [-90 * deg, 90 * deg] },
  M230_Turret: { drive: "train in azimuth about local Y (±86°)", axis: [0, 1, 0], limits: [-86 * deg, 86 * deg] },
  M230_Gun: { drive: "elevate about local X (+ is down; +60° down to -11° up)", axis: [1, 0, 0], muzzle: [0, -0.61, 2.02], limits: [-11 * deg, 60 * deg] },
  FCR_Radome: { note: "Longbow fire control radar on its mast; it doesn't turn with the rotor" },
  Light_Nav_Left: { light: "navigation, red" },
  Light_Nav_Right: { light: "navigation, green" },
  Light_Nav_Tail: { light: "navigation, white" },
  Light_Anticollision_Top: { light: "anti-collision strobe, red" },
  Light_Anticollision_Bottom: { light: "anti-collision strobe, red" },
};
for (const s of ["Left", "Right"]) {
  NOTES[`Store_${s}_Inboard`] = { store: "M261 19-shot 2.75 in rocket pod", note: "released by the jettison buttons" };
  NOTES[`Store_${s}_Outboard`] = { store: "M299 Hellfire launcher", note: "released by the jettison buttons" };
  for (let i = 1; i <= 4; i++) NOTES[`Hellfire_${s}_${i}`] = { store: "AGM-114 Hellfire", note: "launched by the weapon trigger with missiles selected" };
}

const byName = (doc, name) => doc.getRoot().listNodes().filter((n) => n.getName() === name);

// 4x4 column-major helpers (glTF's layout)
function mat4mul(a, b) {
  const o = new Array(16).fill(0);
  for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) for (let k = 0; k < 4; k++) o[c * 4 + r] += a[k * 4 + r] * b[c * 4 + k];
  return o;
}
function mat4inv(m) {
  // rigid transforms only: transpose the rotation, rotate back the translation
  const o = new Array(16).fill(0);
  for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) o[c * 4 + r] = m[r * 4 + c];
  for (let r = 0; r < 3; r++) o[12 + r] = -(o[r] * m[12] + o[4 + r] * m[13] + o[8 + r] * m[14]);
  o[15] = 1;
  return o;
}

async function build(cockpitPath, label) {
  const doc = await io.read(cockpitPath);
  const ext = await io.read(exteriorPath);
  mergeDocuments(doc, ext);
  const root = doc.getRoot();
  const [scene, ...others] = root.listScenes();
  const top = doc.createNode("AH64D").setExtras({
    aircraft: "AH-64D Apache Longbow",
    units: "metres",
    axes: "glTF: +Y up, +Z toward the nose, +X to the crew's left",
    origin: "front cockpit floor, centreline, under the gunner's seat back",
  });
  for (const s of [scene, ...others]) {
    for (const n of s.listChildren()) {
      s.removeChild(n);
      top.addChild(n);
    }
  }
  scene.addChild(top);
  for (const s of others) s.dispose();
  root.setDefaultScene(scene);

  // Canopy doors: the cockpit's door node (with its control extras) takes the exterior door's glass and frame.
  for (const name of ["Canopy_Door_CPG", "Canopy_Door_Pilot"]) {
    const nodes = byName(doc, name);
    const control = nodes.find((n) => n.getExtras().control);
    const shell = nodes.find((n) => !n.getExtras().control);
    if (!control || !shell) continue; // the static model has no door controls: keep the exterior's own door
    // same hinge line and pivot; re-express the door's parts in the cockpit node's frame, whatever axes the exterior used
    const a = control.getWorldMatrix(), b = shell.getWorldMatrix();
    const dp = Math.hypot(a[12] - b[12], a[13] - b[13], a[14] - b[14]);
    const dx = Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
    if (dp > 1e-3 || dx > 1e-3) throw new Error(`${name}: the cockpit's hinge and the exterior's disagree (${dp.toFixed(4)} m, ${dx.toFixed(4)})`);
    const rel = mat4mul(mat4inv(a), b);
    for (const c of shell.listChildren()) {
      const m = mat4mul(rel, c.getMatrix());
      shell.removeChild(c);
      control.addChild(c);
      c.setMatrix(m);
    }
    shell.dispose();
  }
  for (const [name, extras] of Object.entries(NOTES)) for (const n of byName(doc, name)) n.setExtras({ ...n.getExtras(), ...extras });
  await doc.transform(prune({ keepLeaves: true, keepAttributes: true }), unpartition());
  return doc;
}

const sizes = {};
async function write(doc, name) {
  const p = join(outDir, name);
  await io.write(p, doc);
  sizes[name] = statSync(p).size;
}

// the game model and the static one
const full = await build(join(here, "apache_cockpit.glb"), "full");
// normal maps come out of Blender as PNG; high-quality JPEG is a fifth of the size and looks the same
await full.transform(textureCompress({ encoder: sharp, targetFormat: "jpeg", quality: 94, slots: /^normalTexture$/, pattern: /normal/i }));
await write(full, "apache_ah64d.glb");
const stat = await build(join(here, "apache_cockpit_static.glb"), "static");
await stat.transform(textureCompress({ encoder: sharp, targetFormat: "jpeg", quality: 94, slots: /^normalTexture$/, pattern: /normal/i }));
await write(stat, "apache_ah64d_static.glb");

// the browser's copy: the exterior's textures at a quarter of the pixels, everything as WebP
const web = await build(join(here, "apache_cockpit.glb"), "web");
await web.transform(
  textureCompress({ encoder: sharp, targetFormat: "webp", quality: 86, resize: [2048, 2048], pattern: /AH64_Paint/ }),
  textureCompress({ encoder: sharp, targetFormat: "webp", quality: 86, resize: [1024, 1024], pattern: /AH64_(Mech|Stores)/ }),
  textureCompress({ encoder: sharp, targetFormat: "webp", quality: 92, pattern: /^(?!AH64_).*/ }),
  dedup({ propertyTypes: ["Texture"] }),
);
await write(web, "apache_ah64d_web.glb");

for (const [k, v] of Object.entries(sizes)) console.log(`${k}: ${(v / 1048576).toFixed(1)} MB`);
const nodes = full.getRoot().listNodes();
const controls = nodes.filter((n) => n.getExtras().control).length;
let tris = 0;
for (const m of full.getRoot().listMeshes()) for (const p of m.listPrimitives()) tris += (p.getIndices() ? p.getIndices().getCount() : p.getAttribute("POSITION").getCount()) / 3;
console.log(`apache_ah64d.glb: ${Math.round(tris).toLocaleString()} triangles, ${nodes.length} nodes, ${controls} operable controls, ${full.getRoot().listMaterials().length} materials, ${full.getRoot().listTextures().length} textures`);
