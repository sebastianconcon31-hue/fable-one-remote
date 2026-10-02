#!/usr/bin/env node
// Builds the AH-64 Apache cockpit for VR - the inside of the aircraft. The
// outside (and the canopy) is built in Blender by exterior/build.py, and
// merge.mjs joins the two into apache_ah64d.glb.
//
//   apache_cockpit.glb          every control is its own node, pivoted, with its motion in glTF extras
//   apache_cockpit_static.glb   the same model with controls merged in (fewer draw calls, nothing moves)
//   controls.json               every operable control: node, what it does, how it moves
//
//   node generate.mjs [--textures] [--out dir]
//
// Geometry is built here; the textures (panel lettering, gauges, display pages)
// are painted by lib/paint.js in headless Chromium through Playwright, because
// a canvas draws text and Node on its own can't. Set CHROMIUM_PATH to use a
// particular Chromium.
import { createRequire } from "node:module";
import { execSync } from "node:child_process";
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { writeGLB } from "./lib/geo.mjs";
import { Atlas } from "./lib/atlas.mjs";
import { makeCtx } from "./lib/parts.mjs";
import { buildCockpit } from "./lib/cockpit.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const flag = (f) => args.includes(f);
const outDir = args.includes("--out") ? args[args.indexOf("--out") + 1] : here;

function loadPlaywright() {
  const require = createRequire(import.meta.url);
  try {
    return require("playwright");
  } catch {
    return require(join(execSync("npm root -g").toString().trim(), "playwright"));
  }
}

function build(pa, da, interactive) {
  const ctx = makeCtx(pa, da, { interactive });
  const root = buildCockpit(ctx, { canopy: "doors" });
  return { ctx, root };
}

// The pages each display shows in the file, and which of their labels are selected.
const BOXED = { FLT: ["B2"], TSD: ["B3"], WPN: ["L3"], ENG: ["T2"] };

const png = (dataUrl) => Buffer.from(dataUrl.slice(dataUrl.indexOf(",") + 1), "base64");

async function paint(pa, da, screens) {
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
  try {
    const page = await browser.newPage();
    await page.setContent("<!doctype html><html><body></body></html>");
    await page.addScriptTag({ path: join(here, "lib/paint.js") });
    const images = {};
    const p = await page.evaluate((spec) => window.paintAtlas(spec), { size: pa.size, items: pa.items, emissive: true });
    images.panels = png(p.color);
    images.panels_emissive = png(p.emissive);
    const d = await page.evaluate((spec) => window.paintAtlas(spec), { size: da.size, items: da.items, emissive: false });
    images.displays = png(d.color);
    for (const s of screens) images[s.key] = png(await page.evaluate((spec) => window.paintScreen(spec), { page: s.page, w: s.w, h: s.h, ui: { boxed: BOXED[s.page] || [] } }));
    return images;
  } finally {
    await browser.close();
  }
}

const pa = new Atlas("panels");
const da = new Atlas("displays");
build(pa, da, true); // pass 1: learn what the atlases must hold
pa.pack();
da.pack();
const { ctx, root } = build(pa, da, true); // pass 2: the interactive model
const images = await paint(pa, da, ctx.screens);
pa.rewind();
da.rewind();
const stat = build(pa, da, false); // pass 3: the same, with controls merged

mkdirSync(outDir, { recursive: true });
const glb = writeGLB(root, images);
writeFileSync(join(outDir, "apache_cockpit.glb"), glb);
const glbStatic = writeGLB(stat.root, images);
writeFileSync(join(outDir, "apache_cockpit_static.glb"), glbStatic);
const manifest = {
  about: "Every operable control in apache_cockpit.glb. Set a node's local rotation to rest.rotation x AxisAngle(axis, angle), or its local position to rest.translation + axis x travel, where the rest pose is in each node's glTF extras.",
  units: "metres and radians; axes are node-local",
  controls: ctx.controls,
};
writeFileSync(join(outDir, "controls.json"), JSON.stringify(manifest, null, 1));

if (flag("--textures")) {
  const dir = join(outDir, "textures");
  mkdirSync(dir, { recursive: true });
  for (const [k, buf] of Object.entries(images)) writeFileSync(join(dir, k + ".png"), buf);
}

const report = (name, r, bytes) => {
  const s = r.stats();
  const mats = new Set();
  (function walk(n) {
    for (const { mat } of n.geos.values()) mats.add(mat.name);
    n.children.forEach(walk);
  })(r);
  console.log(`${name}: ${(bytes / 1048576).toFixed(2)} MB, ${s.tris.toLocaleString()} triangles, ${s.nodes} nodes, ${s.prims} draw calls, ${mats.size} materials`);
};
report("apache_cockpit.glb", root, glb.length);
report("apache_cockpit_static.glb", stat.root, glbStatic.length);
const kinds = {};
for (const c of ctx.controls) kinds[c.control] = (kinds[c.control] || 0) + 1;
console.log(`controls.json: ${ctx.controls.length} operable controls`, JSON.stringify(kinds));
console.log(`atlases: panels ${pa.size}px (${Math.round(pa.used() * 100)}%), displays ${da.size}px (${Math.round(da.used() * 100)}%), ${ctx.screens.length} live screens`);
