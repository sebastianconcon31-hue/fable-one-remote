// Builds apache_cockpit_viewer.html: the whole viewer in one file (the model,
// three.js and the viewer code), which opens straight from disk with no server.
//
//   npm install esbuild three@0.170.0
//   node standalone.mjs [out.html]
import { createRequire } from "node:module";
import { readFileSync, writeFileSync } from "node:fs";

const here = new URL(".", import.meta.url).pathname;
const out = process.argv[2] || here + "apache_cockpit_viewer.html";
const extra = (process.env.NODE_PATH || "").split(":").filter(Boolean);
const require = createRequire(import.meta.url);
const esbuild = require(require.resolve("esbuild", { paths: [here, ...extra] }));

const bundle = await esbuild.build({
  entryPoints: [here + "viewer/main.js"],
  bundle: true,
  format: "esm",
  minify: true,
  target: "es2020",
  legalComments: "none",
  nodePaths: extra,
  write: false,
});
const js = bundle.outputFiles[0].text;
const paint = readFileSync(here + "lib/paint.js", "utf8");
const model = readFileSync(here + "apache_cockpit.glb").toString("base64");
// nothing inside an inline script may close it early
const inline = (s) => s.replace(/<\/script/gi, "<\\/script");

let html = readFileSync(here + "viewer.html", "utf8");
// function replacements, so "$&" and friends in the code stay literal
const swap = (from, to) => {
  const next = html.replace(from, () => to);
  if (next === html) throw new Error("viewer.html no longer has " + from);
  html = next;
};
swap(/<script>window\.COCKPIT_MODEL_URL[^<]*<\/script>\n/, "");
swap(/<script type="importmap">[\s\S]*?<\/script>\n/, "");
swap('<script src="lib/paint.js"></script>', `<script>${inline(paint)}</script>`);
swap(
  '<script type="module" src="viewer/main.js"></script>',
  `<script id="cockpit-model" type="application/octet-stream">${model}</script>\n<script type="module">${inline(js)}</script>`,
);
writeFileSync(out, html);
console.log(`${out}: ${(html.length / 1e6).toFixed(1)} MB (model ${(model.length / 1e6).toFixed(1)} MB, code ${((js.length + paint.length) / 1e6).toFixed(1)} MB)`);
