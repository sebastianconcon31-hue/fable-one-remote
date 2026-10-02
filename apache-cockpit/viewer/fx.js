// Things that fly off the aircraft: gun rounds, rockets, missiles, jettisoned
// stores and the canopy doors - plus flashes, smoke and impacts.
import * as THREE from "three";

const GRAV = new THREE.Vector3(0, -9.81, 0);
const tmp = new THREE.Vector3(), tmp2 = new THREE.Vector3(), q = new THREE.Quaternion();

function glowTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d");
  const r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  r.addColorStop(0, "rgba(255,255,255,1)");
  r.addColorStop(0.35, "rgba(255,255,255,0.45)");
  r.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = r;
  g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}

export class Effects {
  constructor(scene, aircraft, model, groundY) {
    this.scene = scene;
    this.aircraft = aircraft;
    this.model = model;
    this.groundY = groundY;
    this.items = [];
    this.glow = glowTexture();
    this.detached = [];
    this.saved = new Map();
  }

  sprite(color, size, additive = true, opacity = 1) {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.glow, color, transparent: true, opacity, depthWrite: false, blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending }));
    s.scale.setScalar(size);
    this.scene.add(s);
    return s;
  }

  puff(pos, color, size, life, grow = 1.5, vel = null, additive = false, opacity = 0.6) {
    const s = this.sprite(color, size, additive, opacity);
    s.position.copy(pos);
    this.items.push({ obj: s, life, age: 0, grow, size, vel: vel ? vel.clone() : null, fade: opacity, kind: "puff" });
  }

  flash(pos, size = 1.2) {
    const s = this.sprite(0xffd28a, size, true, 1);
    s.position.copy(pos);
    this.items.push({ obj: s, life: 0.06, age: 0, grow: 1, size, fade: 1, kind: "puff" });
  }

  explode(pos, big = false) {
    this.puff(pos, 0xffb050, big ? 8 : 2.2, big ? 0.6 : 0.3, 2.2, null, true, 1);
    for (let i = 0; i < (big ? 8 : 3); i++) {
      const v = new THREE.Vector3((Math.random() - 0.5) * 3, 2 + Math.random() * 3, (Math.random() - 0.5) * 3);
      this.puff(pos, 0x6b6456, big ? 4 : 1.5, big ? 3 : 1.5, 2.5, v, false, 0.7);
    }
  }

  worldOf(name) {
    const o = this.model.getObjectByName(name);
    return o ? o.getWorldPosition(new THREE.Vector3()) : null;
  }

  forward() {
    return new THREE.Vector3(0, 0, 1).applyQuaternion(this.aircraft.quaternion);
  }

  gunRound() {
    const g = this.model.getObjectByName("M230_Gun");
    if (!g) return;
    g.updateWorldMatrix(true, false);
    const muzzle = new THREE.Vector3(0, -0.61, 2.02);
    const pivot = new THREE.Vector3(0, -0.6, 0.4);
    // the muzzle in the gun node's frame, then to world
    const local = muzzle.clone().sub(pivot);
    const world = local.clone().applyMatrix4(g.matrixWorld);
    const dir = new THREE.Vector3(0, 0, 1).transformDirection(g.matrixWorld);
    this.flash(world, 0.9);
    const tracer = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 3, 4), new THREE.MeshBasicMaterial({ color: 0xffc070 }));
    tracer.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    tracer.position.copy(world);
    this.scene.add(tracer);
    this.items.push({ obj: tracer, life: 3, age: 0, vel: dir.multiplyScalar(805).add(this.velocity()), kind: "round", gravity: true });
  }

  velocity() {
    return this.aircraftVel ? this.aircraftVel.clone() : new THREE.Vector3();
  }

  rocket(station) {
    const x = station === "LI" ? 1.2 : -1.2;
    const start = new THREE.Vector3(x, 0.1, -1.72).applyMatrix4(this.aircraft.matrixWorld);
    const dir = this.forward();
    const m = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 1.4, 8), new THREE.MeshStandardMaterial({ color: 0x5a5f50 }));
    m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    m.position.copy(start);
    this.scene.add(m);
    this.flash(start, 1.5);
    this.items.push({ obj: m, life: 6, age: 0, vel: dir.multiplyScalar(250).add(this.velocity()), acc: 400, kind: "rocket", gravity: true, smoke: 0 });
  }

  missile(station, index, target) {
    const side = station === "LO" ? "Left" : "Right";
    const src = this.model.getObjectByName(`Hellfire_${side}_${index}`);
    if (!src) return;
    src.updateWorldMatrix(true, true);
    const m = src.clone(true);
    src.getWorldPosition(m.position);
    src.getWorldQuaternion(m.quaternion);
    m.scale.setScalar(1);
    // geometry in the clone is relative to the source node's frame; keep the world pose
    this.scene.add(m);
    src.visible = false;
    this.hidden = this.hidden || [];
    this.hidden.push(src);
    const dir = this.forward();
    this.flash(m.position, 2);
    this.items.push({ obj: m, life: 12, age: 0, vel: dir.clone().multiplyScalar(20).add(this.velocity()), dir, acc: 90, kind: "missile", loft: target ? 0.12 : 0.04, smoke: 0 });
  }

  // Detach a node from the aircraft and let it fall (jettisoned stores, canopy doors).
  drop(name, push = new THREE.Vector3(), spin = 0) {
    const o = this.model.getObjectByName(name);
    if (!o || !o.parent) return;
    if (!this.saved.has(o)) this.saved.set(o, { parent: o.parent, position: o.position.clone(), quaternion: o.quaternion.clone() });
    o.updateWorldMatrix(true, true);
    this.scene.attach(o);
    this.detached.push(o);
    this.items.push({ obj: o, life: 1e9, age: 0, vel: this.velocity().add(push), kind: "drop", gravity: true, spin: new THREE.Vector3((Math.random() - 0.5) * spin, (Math.random() - 0.5) * spin, (Math.random() - 0.5) * spin), rest: false });
  }

  jettison(station) {
    const side = station[0] === "L" ? "Left" : "Right";
    const where = station[1] === "O" ? "Outboard" : "Inboard";
    this.drop(`Store_${side}_${where}`, new THREE.Vector3(0, -1.5, 0), 0.6);
  }

  canopy() {
    for (const n of ["Canopy_Door_CPG", "Canopy_Door_Pilot"]) {
      const out = new THREE.Vector3(-6, 5, 0).applyQuaternion(this.aircraft.quaternion);
      this.drop(n, out, 4);
      const p = this.worldOf(n);
      if (p) this.flash(p, 1.5);
    }
  }

  update(dt) {
    for (const it of [...this.items]) {
      it.age += dt;
      const o = it.obj;
      if (it.kind === "puff") {
        const k = it.age / it.life;
        o.scale.setScalar(it.size * (1 + (it.grow - 1) * k));
        o.material.opacity = it.fade * (1 - k);
        if (it.vel) o.position.addScaledVector(it.vel, dt);
      } else if (it.kind === "missile") {
        const speed = it.vel.length();
        if (speed < 420) it.vel.addScaledVector(it.dir, it.acc * dt);
        if (it.age < 1.5) it.vel.y += it.loft * 60 * dt;
        else it.vel.y -= 6 * dt;
        o.position.addScaledVector(it.vel, dt);
        o.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), tmp.copy(it.vel).normalize());
        it.smoke -= dt;
        if (it.smoke <= 0 && it.age > 0.15) {
          it.smoke = 0.03;
          this.puff(tmp2.copy(o.position).addScaledVector(it.vel, -0.01), 0xbdb8ad, 0.8, 2.5, 3);
          this.puff(o.position, 0xffc080, 0.5, 0.05, 1, null, true, 1);
        }
      } else if (it.kind === "rocket") {
        if (it.age < 1.1) it.vel.addScaledVector(tmp.copy(it.vel).normalize(), it.acc * dt);
        it.vel.addScaledVector(GRAV, dt);
        o.position.addScaledVector(it.vel, dt);
        o.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), tmp.copy(it.vel).normalize());
        it.smoke -= dt;
        if (it.smoke <= 0 && it.age < 1.2) {
          it.smoke = 0.02;
          this.puff(o.position, 0xcfcac0, 0.6, 1.8, 3);
        }
      } else if (it.kind === "round") {
        it.vel.addScaledVector(GRAV, dt);
        o.position.addScaledVector(it.vel, dt);
      } else if (it.kind === "drop" && !it.rest) {
        it.vel.addScaledVector(GRAV, dt);
        o.position.addScaledVector(it.vel, dt);
        o.rotateX(it.spin.x * dt);
        o.rotateY(it.spin.y * dt);
        o.rotateZ(it.spin.z * dt);
        o.updateWorldMatrix(false, true);
        const box = new THREE.Box3().setFromObject(o);
        if (box.min.y <= this.groundY) {
          o.position.y += this.groundY - box.min.y;
          it.rest = true;
          this.puff(o.position, 0x8a826f, 2, 1.5, 2.2);
        }
        continue;
      }
      const hitGround = it.kind !== "puff" && o.position.y <= this.groundY;
      if (hitGround) this.explode(tmp.copy(o.position).setY(this.groundY + 0.3), it.kind === "missile");
      if (hitGround || it.age > it.life) {
        this.scene.remove(o);
        if (o.geometry && it.kind !== "missile") o.geometry.dispose();
        this.items.splice(this.items.indexOf(it), 1);
      }
    }
  }

  reset() {
    for (const it of this.items) if (it.kind !== "drop") this.scene.remove(it.obj);
    this.items = [];
    for (const o of this.detached) {
      const s = this.saved.get(o);
      if (s) {
        s.parent.add(o);
        o.position.copy(s.position);
        o.quaternion.copy(s.quaternion);
      }
    }
    this.detached = [];
    for (const h of this.hidden || []) h.visible = true;
    this.hidden = [];
  }
}
