// Live displays: every "Screen_*" material in the model gets a canvas that's
// repainted from the simulation, using the same painter (lib/paint.js) that
// drew the pictures baked into the file.
import * as THREE from "three";

const START = { Pilot_MPD_Left: "FLT", Pilot_MPD_Right: "TSD", CPG_MPD_Left: "WPN", CPG_MPD_Right: "ENG", CPG_TEDAC: "TEDAC", Pilot_EUFD: "EUFD", CPG_EUFD: "EUFD", Pilot_KU: "KU", CPG_KU: "KU", Pilot_Standby_ADI: "ADI", Pilot_Compass: "COMPASS" };
const RATE = { TEDAC: 15, VID: 15, ADI: 20, COMPASS: 20, EUFD: 4, KU: 4, FCR: 15 };
const FAB = { FCR: "FCR", WPN: "WPN", TSD: "TSD", VID: "VID", COM: "COM", A_C: "AC", MENU: "MENU" };

export class Displays {
  constructor(root, sim, paint) {
    this.sim = sim;
    this.paint = paint;
    this.screens = new Map();
    this.ku = {};
    this.eufdScroll = {};
    const seen = new Set();
    root.traverse((o) => {
      if (!o.isMesh || !o.material || !o.material.name.startsWith("Screen_") || seen.has(o.material)) return;
      seen.add(o.material);
      const id = o.material.name.slice(7);
      const img = o.material.map && o.material.map.image;
      const cv = document.createElement("canvas");
      cv.width = img ? img.width : 512;
      cv.height = img ? img.height : 512;
      const tex = new THREE.CanvasTexture(cv);
      tex.flipY = false;
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = 4;
      o.material.map = tex;
      o.material.emissiveMap = tex;
      o.material.needsUpdate = true;
      this.screens.set(id, { id, cv, tex, mat: o.material, page: START[id] || "FLT", boxed: {}, brt: 1, contrast: 1, mode: "DAY", next: 0 });
    });
    for (const k of ["Pilot_KU", "CPG_KU"]) this.ku[k] = "";
    this.dimmed = 1;
  }

  // The boxed labels for a screen's current page.
  boxedFor(s, d) {
    const own = s.boxed[s.page] || [];
    if (s.page === "WPN") return [...own.filter((b) => !["L2", "L3", "L4"].includes(b)), { GUN: "L2", MSL: "L3", RKT: "L4" }[d.wpn.sel]];
    if (s.page === "TEDAC") return [{ W: "L1", M: "L2", N: "L3" }[d.tedac.fov], d.tedac.sensor === "FLIR" ? "R1" : "R2"];
    if (s.page === "COM") return [`L${d.rts + 1}`];
    const home = { FLT: "B2", TSD: "B3", ENG: "T2", FUEL: "T3", FCR: "B3", VID: "B4", COM: "B5", AC: "B6" }[s.page];
    const tsd = s.page === "TSD" ? [this.tsd.ctr && "R3", this.tsd.frz && "R5", !this.tsd.map && "T2"].filter(Boolean) : [];
    return [...own, ...tsd, home].filter(Boolean);
  }

  get tsd() {
    if (!this._tsd) this._tsd = { scale: 25, ctr: false, frz: false, map: true, frozen: null };
    return this._tsd;
  }

  // A key on an MPD, the TEDAC, a keyboard unit or an EUFD. Returns a message to show, if any.
  key(fn) {
    const [kind, unit, id] = fn.split(":");
    const d = this.sim.data();
    if (kind === "mpd") {
      const s = this.screens.get(unit);
      if (!s) return;
      if (id === "BRT") return;
      if (FAB[id]) {
        s.page = FAB[id];
        return `${unit.replace(/_/g, " ")}: ${s.page === "AC" ? "A/C" : s.page}`;
      }
      const P = this.paint.PAGES[s.page];
      const nav = P.nav && P.nav[id];
      if (nav) {
        s.page = nav;
        return;
      }
      if (s.page === "WPN" && ["L2", "L3", "L4"].includes(id)) {
        this.sim.weapon = { L2: "GUN", L3: "MSL", L4: "RKT" }[id];
        return `WEAPON ${this.sim.weapon}`;
      }
      if (s.page === "COM" && /^L[1-5]$/.test(id)) {
        this.sim.rts = +id[1] - 1;
        return `RADIO ${this.sim.radios[this.sim.rts][0]}`;
      }
      if (s.page === "TSD") {
        const t = this.tsd;
        if (id === "B4") t.scale = { 10: 25, 25: 50, 50: 100, 100: 10 }[t.scale];
        else if (id === "R3") t.ctr = !t.ctr;
        else if (id === "R5") (t.frz = !t.frz), (t.frozen = t.frz ? [...d.pos] : null);
        else if (id === "T2") t.map = !t.map;
        return;
      }
      // any other labelled key selects (boxes) its option
      const label = labelOf(P.labels, id);
      if (label) {
        const list = (s.boxed[s.page] = s.boxed[s.page] || []);
        const i = list.indexOf(id);
        if (i >= 0) list.splice(i, 1);
        else list.push(id);
      }
      return;
    }
    if (kind === "tedac") {
      const t = this.sim.tedac;
      const k = id || unit;
      if (k === "L1" || k === "L2" || k === "L3") t.fov = { L1: "W", L2: "M", L3: "N" }[k];
      if (k === "R1") t.sensor = "FLIR";
      if (k === "R2") t.sensor = "DTV";
      return;
    }
    if (kind === "ku") {
      let s = this.ku[unit] || "";
      if (id === "CLR") s = "";
      else if (id === "BKS") s = s.slice(0, -1);
      else if (id === "SPC") s += " ";
      else if (id === "ENT") {
        const msg = s.trim() ? `${unit.replace(/_/g, " ")}: ENTERED ${s.trim()}` : null;
        s = "";
        this.ku[unit] = s;
        return msg;
      } else s += id;
      this.ku[unit] = s.slice(-22);
      return;
    }
    if (kind === "eufd") {
      const sim = this.sim;
      if (id === "RTS") sim.rts = (sim.rts + 1) % sim.radios.length;
      else if (id === "SWAP") {
        const r = sim.radios[sim.rts];
        [r[1], r[3]] = [r[3], r[1]];
        return `${r[0]} ${r[1]}`;
      } else if (id === "UP" || id === "DOWN") this.eufdScroll[unit] = Math.max(0, (this.eufdScroll[unit] || 0) + (id === "UP" ? -1 : 1));
      return;
    }
  }

  rocker(fn, dir) {
    const [, unit, id] = fn.split(":");
    const s = this.screens.get(unit);
    if (!s) return;
    if (id === "BRT") s.brt = Math.max(0.15, Math.min(1.8, s.brt + dir * 0.2));
    if (id === "VIDEO") s.contrast = Math.max(0.5, Math.min(1.8, s.contrast + dir * 0.15));
    return `${unit.replace(/_/g, " ")} ${id === "BRT" ? "brightness" : "contrast"} ${Math.round((id === "BRT" ? s.brt : s.contrast) * 100)}%`;
  }

  mode(fn, mode) {
    const s = this.screens.get(fn.split(":")[1]);
    if (s) s.mode = mode;
  }

  eufdBrightness(unit, v) {
    const s = this.screens.get(unit);
    if (s) s.brt = 0.15 + v * 1.2;
  }

  update(now) {
    const d = this.sim.data();
    for (const s of this.screens.values()) {
      s.mat.emissiveIntensity = s.brt * this.dimmed;
      if (now < s.next) continue;
      s.next = now + 1000 / (RATE[s.page] || 10);
      const data = s.page === "KU" ? { ...d, scratch: this.ku[s.id] } : s.page === "EUFD" ? { ...d, wca: d.wca.slice(this.eufdScroll[s.id] || 0) } : s.page === "TSD" ? { ...d, tsd: this.tsd, pos: this.tsd.frozen || d.pos } : d;
      this.paint.drawScreen(s.cv, s.page, data, { boxed: this.boxedFor(s, d) }, { mode: s.mode, contrast: s.contrast });
      s.tex.needsUpdate = true;
    }
  }

  reset() {
    for (const s of this.screens.values()) Object.assign(s, { page: START[s.id] || "FLT", boxed: {}, brt: 1, contrast: 1, mode: "DAY", next: 0 });
    for (const k of Object.keys(this.ku)) this.ku[k] = "";
    this._tsd = null;
  }
}

function labelOf(labels, id) {
  if (!labels) return "";
  const side = { T: "top", B: "bottom", L: "left", R: "right" }[id[0]];
  return (labels[side] || [])[+id.slice(1) - 1] || "";
}
