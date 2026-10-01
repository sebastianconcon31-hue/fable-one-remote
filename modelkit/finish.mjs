#!/usr/bin/env node
// Finishes a vehicle that its build.py exported:
//
//   NAME.glb          the game model (normal maps re-encoded as high-quality JPEG)
//   NAME_web.glb      for browsers: WebP textures at half size (paint 2K, the rest 1K)
//   NAME_viewer.html  the shared viewer in one file, with the web model inside; opens from disk
//
//   node modelkit/finish.mjs exported.glb OUT_DIR NAME
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

const [src, out, name] = process.argv.slice(2);
if (!name) throw new Error("usage: node modelkit/finish.mjs exported.glb OUT_DIR NAME");
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const size = (p) => `${(statSync(p).size / 1048576).toFixed(1)} MB`;

const full = await io.read(src);
await full.transform(textureCompress({ encoder: sharp, targetFormat: "jpeg", quality: 94, pattern: /normal/i }), dedup(), prune({ keepLeaves: true }));
const fullPath = join(out, `${name}.glb`);
await io.write(fullPath, full);

const web = await io.read(src);
await web.transform(
  textureCompress({ encoder: sharp, targetFormat: "webp", quality: 86, resize: [2048, 2048], pattern: /_Paint/ }),
  textureCompress({ encoder: sharp, targetFormat: "webp", quality: 86, resize: [1024, 1024], pattern: /^(?!.*_Paint)/ }),
  dedup(),
  prune({ keepLeaves: true }),
);
const webPath = join(out, `${name}_web.glb`);
await io.write(webPath, web);

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
const root = full.getRoot().listScenes()[0].listChildren()[0];
const title = root?.getExtras()?.vehicle || name;
swap(/<title>[^<]*<\/title>/, `<title>${title.split(/[,(]/)[0].trim()}</title>`);
swap(/<script type="importmap">[\s\S]*?<\/script>\n/, "");
swap('<script type="module" src="viewer.js"></script>', `<script id="vehicle-model" type="application/octet-stream">${readFileSync(webPath).toString("base64")}</script>\n<script type="module">${inline(bundle.outputFiles[0].text)}</script>`);
const viewerPath = join(out, `${name}_viewer.html`);
writeFileSync(viewerPath, html);

let tris = 0;
const meshTris = new Map();
for (const m of full.getRoot().listMeshes()) {
  let t = 0;
  for (const p of m.listPrimitives()) t += (p.getIndices() ? p.getIndices().getCount() : p.getAttribute("POSITION").getCount()) / 3;
  meshTris.set(m, t);
}
for (const n of full.getRoot().listNodes()) if (n.getMesh()) tris += meshTris.get(n.getMesh());
console.log(`${name}.glb: ${size(fullPath)}, ${Math.round(tris).toLocaleString()} triangles drawn, ${full.getRoot().listNodes().length} nodes, ${full.getRoot().listMaterials().length} materials, ${full.getRoot().listTextures().length} textures`);
console.log(`${name}_web.glb: ${size(webPath)}`);
console.log(`${name}_viewer.html: ${size(viewerPath)}`);
