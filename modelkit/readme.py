"""Writes a vehicle's README.md from what its folder holds: about.json (the
words), measurements.json (the 1:1 check build.py writes) and stats.json
(what finish.mjs measured in the delivered files).

    python3 modelkit/readme.py VEHICLE_DIR"""
import json
import os
import sys


def table(head, rows, align=None):
    out = ["| " + " | ".join(head) + " |", "| " + " | ".join(align or ["---"] * len(head)) + " |"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def tex_summary(t):
    parts = [f"{n} at {s}²" for s, n in sorted(((int(k), v) for k, v in t.items()), reverse=True)]
    return ", ".join(parts) if parts else "none"


def main(vdir):
    A = json.load(open(os.path.join(vdir, "about.json")))
    M = json.load(open(os.path.join(vdir, "measurements.json")))
    S = json.load(open(os.path.join(vdir, "stats.json")))
    name, folder = A["name"], os.path.basename(os.path.abspath(vdir))
    g, w = S["game"], S["web"]
    L = [f"# {A['title']}", "", A["lede"], "", f"![{A['hero_alt']}](docs/hero.jpg)", ""]
    grid = A["grid"]
    for i in range(0, len(grid), 2):
        pair = grid[i:i + 2]
        if i == 0:
            L.append("| " + " | ".join(c[1] for c in pair) + " |")
            L.append("| " + " | ".join("---" for _ in pair) + " |")
        else:
            L.append("| " + " | ".join(f"**{c[1]}**" for c in pair) + " |")
        L.append("| " + " | ".join(f"![{c[2]}](docs/{c[0]})" for c in pair) + " |")
    L += ["", "## Files", ""]
    L.append(table(["File", "What it is"], [
        [f"`{name}.glb`", f"**The {A['short']}.** {A['game_note']} {g['mb']:.1f} MB."],
        [f"`{name}_web.glb`", f"A lighter copy with half-size WebP textures, for browsers and phones. {w['mb']:.1f} MB."],
        [f"`{name}_viewer.html`", f"Opens the {A['short']} in your browser with a double-click: {A['viewer_note']} {S['viewerMB']:.1f} MB; not checked in, `node modelkit/finish.mjs` makes it."],
        ["`measurements.json`", "The finished model measured against the published dimensions."],
        [", ".join(f"`{f}`" for f in A["sources"]), "The Blender build (it uses the shared `../modelkit`)."],
    ]))
    L += ["", "## Scale: 1:1", "", A["scale_intro"], ""]
    rows = M["published_vs_model"]
    deg = lambda r: r.get("unit") == "deg"
    fmt = lambda r, v: f"{v:.1f}°" if deg(r) else f"{v:.3f}"
    L.append(table(["Dimension", "Published (m)", "Model (m)"], [[r["dimension"], fmt(r, r["published"]), fmt(r, r["model"])] for r in rows], ["---", "---:", "---:"]))
    worst = max(abs(r["published"] - r["model"]) for r in rows if not deg(r))
    angles = [abs(r["published"] - r["model"]) for r in rows if deg(r)]
    L += ["", f"All within {max(1, round(worst * 1000))} mm" + (f", the angles within {max(0.1, round(max(angles), 1))}°." if angles else "."), "",
          "- **Units and axes:** metres, glTF axes. +Y is up, +Z points to the front, and +X is the left.",
          f"- **Origin:** {A['origin']}.", ""]
    L += ["## Moving parts", "", "Each is its own node, pivoted where the real part turns. Its glTF extras say how it moves: `control` (wheel, steer, track, hinge, traverse, elevate, cargo), `axis`, `limits`, and `drive` in words.", ""]
    if any("elevat" in r[1] for r in A["moving"]):
        L += ["The gun also carries `limits_by_traverse`: its lowest and highest elevation every `traverse_step` (5) degrees of the turret's traverse, measured against the hull, so a game can lift it over the deck and whatever else stands in its way instead of letting it sink through. The viewer clamps to it.", ""]
    L.append(table(["Node", "Moves"], A["moving"]))
    if A.get("track_note"):
        L += ["", A["track_note"]]
    L += ["", "## Look", ""]
    L += [f"- {x}" for x in A["look"]]
    L += ["", table(["Texture set", "Size", "Covers"], A["textures"]), "",
          "Each set has a base colour, an occlusion-roughness-metallic map and a normal map (MikkTSpace tangents included). Glass, optics and light lenses use plain material values.", ""]
    L += ["## Performance", ""]
    L.append(table(["File", "Triangles", "Draw calls", "Nodes", "Textures", "Texture memory on the GPU"], [
        [f"`{g['file']}`", f"{g['triangles']:,}", g["drawCalls"], g["nodes"], tex_summary(g["textures"]), f"about {g['gpuTextureMB']} MB"],
        [f"`{w['file']}`", f"{w['triangles']:,}", w["drawCalls"], w["nodes"], tex_summary(w["textures"]), f"about {w['gpuTextureMB']} MB"],
    ], ["---", "---:", "---:", "---:", "---", "---:"]))
    L += ["", "Texture memory assumes uncompressed RGBA with mipmaps; GPU texture compression (KTX2/Basis, BCn or ASTC) cuts it by four to eight times.", ""]
    if A.get("perf_note"):
        L += [A["perf_note"], ""]
    L += ["## Rebuilding", "", "```sh",
          "pip install bpy==5.0.1 pillow                     # once, with Python 3.11",
          "(cd apache-cockpit && npm install)                # once: glTF-Transform, sharp, esbuild, three",
          f"python3.11 {folder}/build.py --glb out/{name}.glb --textures 4096   # build, paint, bake, export",
          f"node modelkit/finish.mjs out/{name}.glb {folder} {name}            # game and web files, the viewer",
          A.get("render_cmd") or f"python3.11 modelkit/beauty.py {folder} {folder}/{name}.glb out/docs     # the renders",
          f"python3.11 {folder}/build.py --preview out --lookdev    # a quick look at the paint, without baking",
          "```", ""]
    if A.get("scheme"):
        L += [A["scheme"], ""]
    L += ["## Accuracy", ""]
    L += [f"- {x}" for x in A["accuracy"]]
    L.append("")
    open(os.path.join(vdir, "README.md"), "w").write("\n".join(L))
    print("wrote", os.path.join(vdir, "README.md"))


if __name__ == "__main__":
    main(sys.argv[1])
