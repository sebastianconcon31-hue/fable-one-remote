#!/usr/bin/env node
// Finishes the truck that build.py exports:
//
//   hemtt_m977a4.glb       the game model (normal maps re-encoded as high-quality JPEG)
//   hemtt_m977a4_web.glb   for browsers: half-size WebP textures
//   hemtt_viewer.html      the viewer in one file, with the web model inside; opens from disk
//
//   node hemtt-m977/finish.mjs path/to/exported.glb
//
// Uses the packages installed in ../apache-cockpit (npm install there).
import { createRequire } from "node:module";
import { readFileSync, writeFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const pkgs = join(here, "..", "apache-cockpit");
const require = createRequire(join(pkgs, "package.json"));
const load = async (name) => import(pathToFileURL(require.resolve(name)).href);
const { NodeIO } = await load("@gltf-transform/core");
const { ALL_EXTENSIONS } = await load("@gltf-transform/extensions");
const { textureCompress, prune, dedup } = await load("@gltf-transform/functions");
const sharp = (await load("sharp")).default;
const esbuild = require("esbuild");

const src = process.argv[2];
if (!src) throw new Error("usage: node hemtt-m977/finish.mjs exported.glb");
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const size = (p) => `${(statSync(p).size / 1048576).toFixed(1)} MB`;

const full = await io.read(src);
await full.transform(textureCompress({ encoder: sharp, targetFormat: "jpeg", quality: 94, pattern: /normal/i }), prune({ keepLeaves: true }));
const fullPath = join(here, "hemtt_m977a4.glb");
await io.write(fullPath, full);

const web = await io.read(src);
await web.transform(
  textureCompress({ encoder: sharp, targetFormat: "webp", quality: 86, resize: [2048, 2048], pattern: /HEMTT_Paint/ }),
  textureCompress({ encoder: sharp, targetFormat: "webp", quality: 86, resize: [1024, 1024], pattern: /HEMTT_(Chassis|Cargo)/ }),
  dedup({ propertyTypes: ["Texture"] }),
  prune({ keepLeaves: true }),
);
const webPath = join(here, "hemtt_m977a4_web.glb");
await io.write(webPath, web);

// the one-file viewer: three.js and the viewer bundled, the web model embedded
const bundle = await esbuild.build({
  entryPoints: [join(here, "viewer", "viewer.js")],
  bundle: true,
  format: "esm",
  minify: true,
  target: "es2020",
  legalComments: "none",
  nodePaths: [join(pkgs, "node_modules")],
  write: false,
});
const inline = (s) => s.replace(/<\/script/gi, "<\\/script");
let html = readFileSync(join(here, "viewer", "viewer.html"), "utf8");
const swap = (from, to) => {
  const next = html.replace(from, () => to);
  if (next === html) throw new Error("viewer.html no longer has " + from);
  html = next;
};
swap(/<script type="importmap">[\s\S]*?<\/script>\n/, "");
swap('<script type="module" src="viewer.js"></script>', `<script id="truck-model" type="application/octet-stream">${readFileSync(webPath).toString("base64")}</script>\n<script type="module">${inline(bundle.outputFiles[0].text)}</script>`);
const viewerPath = join(here, "hemtt_viewer.html");
writeFileSync(viewerPath, html);

let tris = 0;
for (const m of full.getRoot().listMeshes()) for (const p of m.listPrimitives()) tris += (p.getIndices() ? p.getIndices().getCount() : p.getAttribute("POSITION").getCount()) / 3;
console.log(`hemtt_m977a4.glb: ${size(fullPath)}, ${Math.round(tris).toLocaleString()} triangles, ${full.getRoot().listNodes().length} nodes, ${full.getRoot().listMaterials().length} materials, ${full.getRoot().listTextures().length} textures`);
console.log(`hemtt_m977a4_web.glb: ${size(webPath)}`);
console.log(`hemtt_viewer.html: ${size(viewerPath)}`);
