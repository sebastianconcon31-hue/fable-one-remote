// Merges extras into a glTF's nodes, by node name, from a JSON file: { "Gun": { "limits_by_traverse": [...] }, ... }
//   node modelkit/set_extras.mjs MODEL.glb EXTRAS.json [OUT.glb]
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import { readFileSync } from "node:fs";
const require = createRequire(new URL("../apache-cockpit/package.json", import.meta.url));
const load = async (n) => import(pathToFileURL(require.resolve(n)).href);
const { NodeIO } = await load("@gltf-transform/core");
const { ALL_EXTENSIONS } = await load("@gltf-transform/extensions");
const [src, json, out] = process.argv.slice(2);
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const doc = await io.read(src);
const extras = JSON.parse(readFileSync(json, "utf8"));
for (const n of doc.getRoot().listNodes()) {
  if (extras[n.getName()]) {
    n.setExtras({ ...n.getExtras(), ...extras[n.getName()] });
    console.log("extras set on", n.getName());
  }
}
await io.write(out || src, doc);
