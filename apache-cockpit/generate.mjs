#!/usr/bin/env node
// Builds apache_cockpit.glb: an AH-64 Apache tandem cockpit for VR.
//
//   node generate.mjs                  writes apache_cockpit.glb next to this file
//   node generate.mjs --textures       also writes the painted textures to textures/
//   node generate.mjs --out path.glb
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
import { buildExterior } from "./lib/exterior.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const flag = (f) => args.includes(f);
const opt = (f, d) => (args.includes(f) ? args[args.indexOf(f) + 1] : d);
const out = opt("--out", join(here, "apache_cockpit.glb"));

function loadPlaywright() {
  const require = createRequire(import.meta.url);
  try {
    return require("playwright");
  } catch {
    const root = execSync("npm root -g").toString().trim();
    return require(join(root, "playwright"));
  }
}

function build(pa, da) {
  const ctx = makeCtx(pa, da);
  const root = buildCockpit(ctx);
  buildExterior(ctx, root);
  return { ctx, root };
}

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
    for (const s of screens) images[s.key] = png(await page.evaluate((spec) => window.paintScreen(spec), { page: s.page, size: 512 }));
    return images;
  } finally {
    await browser.close();
  }
}

const pa = new Atlas("panels");
const da = new Atlas("displays");
build(pa, da); // pass 1: learn what the atlases must hold
pa.pack();
da.pack();
const { ctx, root } = build(pa, da); // pass 2: the real thing
const images = await paint(pa, da, ctx.screens);

const glb = writeGLB(root, images);
writeFileSync(out, glb);

if (flag("--textures")) {
  const dir = join(here, "textures");
  mkdirSync(dir, { recursive: true });
  for (const [k, buf] of Object.entries(images)) writeFileSync(join(dir, k + ".png"), buf);
}

const s = root.stats();
const mats = new Set();
(function walk(n) {
  for (const { mat } of n.geos.values()) mats.add(mat.name);
  n.children.forEach(walk);
})(root);
console.log(`wrote ${out}`);
console.log(`  ${(glb.length / 1048576).toFixed(2)} MB, ${s.tris.toLocaleString()} triangles, ${s.verts.toLocaleString()} vertices`);
console.log(`  ${s.nodes} nodes, ${s.prims} primitives (draw calls), ${mats.size} materials`);
console.log(`  panel atlas ${pa.size}px (${Math.round(pa.used() * 100)}% used), display atlas ${da.size}px (${Math.round(da.used() * 100)}% used), ${ctx.screens.length} screens`);
