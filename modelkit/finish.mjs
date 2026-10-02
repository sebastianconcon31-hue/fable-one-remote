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
const { textureCompress, prune, dedup, tangents, weld, unweld } = await load("@gltf-transform/functions");
const { generateTangents } = await load("mikktspace");
const sharp = (await load("sharp")).default;
const esbuild = require("esbuild");

const [src, out, name] = process.argv.slice(2);
if (!name) throw new Error("usage: node modelkit/finish.mjs exported.glb OUT_DIR NAME");
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
// MikkTSpace leaves a zero tangent where a triangle's UVs are degenerate; give those a unit one
const fixTangents = () => (doc) => {
  for (const mesh of doc.getRoot().listMeshes()) {
    for (const prim of mesh.listPrimitives()) {
      const t = prim.getAttribute("TANGENT");
      if (!t) continue;
      const a = t.getArray().slice();
      for (let i = 0; i < a.length; i += 4) {
        const l = Math.hypot(a[i], a[i + 1], a[i + 2]);
        if (l < 1e-6) a.set([1, 0, 0, 1], i);
        else if (Math.abs(l - 1) > 1e-4) a.set([a[i] / l, a[i + 1] / l, a[i + 2] / l, a[i + 3] < 0 ? -1 : 1], i);
      }
      t.setArray(a);
    }
  }
};
const size = (p) => `${(statSync(p).size / 1048576).toFixed(1)} MB`;

const full = await io.read(src);
// MikkTSpace tangents, the space Blender baked the normal maps in
await full.transform(unweld(), tangents({ generateTangents, overwrite: false }), fixTangents(), weld(), textureCompress({ encoder: sharp, targetFormat: "jpeg", quality: 94, pattern: /normal/i }), dedup(), prune({ keepLeaves: true }));
const fullPath = join(out, `${name}.glb`);
await io.write(fullPath, full);

const web = await io.read(src);
await web.transform(
  unweld(),
  tangents({ generateTangents, overwrite: false }),
  fixTangents(),
  weld(),
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

// what each file costs to draw, for the README
async function stats(doc, path) {
  const root = doc.getRoot();
  let tris = 0, draws = 0, mem = 0;
  for (const n of root.listNodes()) {
    const m = n.getMesh();
    if (!m) continue;
    for (const p of m.listPrimitives()) {
      draws++;
      tris += (p.getIndices() ? p.getIndices().getCount() : p.getAttribute("POSITION").getCount()) / 3;
    }
  }
  const sizes = {};
  for (const t of root.listTextures()) {
    const meta = await sharp(Buffer.from(t.getImage())).metadata();
    mem += (meta.width * meta.height * 4 * 4) / 3;
    sizes[meta.width] = (sizes[meta.width] || 0) + 1;
  }
  return { file: path.split("/").pop(), mb: +(statSync(path).size / 1048576).toFixed(1), triangles: Math.round(tris), drawCalls: draws, nodes: root.listNodes().length,
    materials: root.listMaterials().length, textures: sizes, gpuTextureMB: Math.round(mem / 1048576) };
}
const report = { game: await stats(full, fullPath), web: await stats(web, webPath), viewerMB: +(statSync(viewerPath).size / 1048576).toFixed(1) };
writeFileSync(join(out, "stats.json"), JSON.stringify(report, null, 1));
for (const r of [report.game, report.web]) console.log(`${r.file}: ${r.mb} MB, ${r.triangles.toLocaleString()} triangles, ${r.drawCalls} draw calls, ${r.nodes} nodes, textures ${JSON.stringify(r.textures)}`);
console.log(`${name}_viewer.html: ${report.viewerMB} MB`);
