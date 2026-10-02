// Operating the cockpit's controls. Every node the model marks as operable
// (glTF extras: control, motion, axis, positions/angles or min/max, rest
// pose) becomes a Control here, which knows how to move and what state it's in.
import * as THREE from "three";

const q1 = new THREE.Quaternion(), q2 = new THREE.Quaternion(), v1 = new THREE.Vector3();
const DRAGGABLE = new Set(["stick", "collective", "pedal", "lever"]);

export class Control {
  constructor(obj) {
    const u = obj.userData;
    this.obj = obj;
    this.name = obj.name;
    this.kind = u.control;
    this.label = u.label || obj.name.replace(/_/g, " ");
    this.fn = u.fn || null;
    this.motion = u.motion;
    this.axis = new THREE.Vector3(...(u.axis || [0, 0, 1]));
    this.positions = u.positions || null;
    this.angles = u.angles || null;
    this.state = u.state ?? 0;
    this.min = u.min ?? 0;
    this.max = u.max ?? 1;
    this.value = u.value ?? 0;
    this.travel = u.travel ?? 0;
    this.momentary = u.momentary || [];
    this.spring = u.spring;
    this.latching = !!u.latching;
    this.hasLit = u.lit !== undefined;
    this.lit = !!u.lit;
    this.on = false; // latched state of a latching button
    this.restQ = new THREE.Quaternion(...(u.rest?.rotation || [0, 0, 0, 1]));
    this.restP = new THREE.Vector3(...(u.rest?.translation || [0, 0, 0]));
    if (this.motion === "stick") {
      this.pitchAxis = new THREE.Vector3(...u.axes.pitch);
      this.rollAxis = new THREE.Vector3(...u.axes.roll);
      this.limits = u.limits;
      this.stick = { x: 0, y: 0 };
      this.cur = { x: 0, y: 0 };
    }
    this.defaults = { state: this.state, value: this.value, lit: this.lit };
    this.cur = this.motion === "stick" ? { x: 0, y: 0 } : this.targetParam();
    this.springAt = 0;
    this.pressUntil = 0;
    this.apply();
  }
  get discrete() {
    return !!this.positions && this.motion === "rotate" && !!this.angles;
  }
  get draggable() {
    return DRAGGABLE.has(this.kind) || (this.kind === "rotary" && !this.positions);
  }
  // The pose parameter it should move to: an angle (rad) or a travel (m).
  targetParam() {
    if (this.motion === "translate") {
      if (this.positions) return this.state ? this.travel : 0;
      return this.pressUntil > performance.now() ? this.travel : 0;
    }
    if (this.angles) return this.angles[this.state];
    return this.min + (this.max - this.min) * this.value;
  }
  apply() {
    const o = this.obj;
    if (this.motion === "stick") {
      q1.setFromAxisAngle(this.pitchAxis, this.cur.y * this.limits.pitch);
      q2.setFromAxisAngle(this.rollAxis, this.cur.x * this.limits.roll);
      o.quaternion.copy(this.restQ).multiply(q1).multiply(q2);
      o.position.copy(this.restP);
    } else if (this.motion === "translate") {
      o.quaternion.copy(this.restQ);
      v1.copy(this.axis).applyQuaternion(this.restQ).multiplyScalar(this.cur);
      o.position.copy(this.restP).add(v1);
    } else {
      o.quaternion.copy(this.restQ).multiply(q1.setFromAxisAngle(this.axis, this.cur));
      o.position.copy(this.restP);
    }
  }
  // Ease toward the target; true while still moving.
  step(dt, now) {
    if (this.spring != null && this.momentary.includes(this.state) && this.springAt && now > this.springAt) {
      this.state = this.spring;
      this.springAt = 0;
    }
    const rate = this.kind === "door" ? 3 : this.kind === "handle" ? 8 : 22;
    const k = 1 - Math.exp(-rate * dt);
    if (this.motion === "stick") {
      const dx = this.stick.x - this.cur.x, dy = this.stick.y - this.cur.y;
      if (Math.abs(dx) + Math.abs(dy) < 1e-5) return false;
      this.cur.x += dx * Math.min(1, k * 1.5);
      this.cur.y += dy * Math.min(1, k * 1.5);
    } else {
      const t = this.targetParam();
      const d = t - this.cur;
      if (Math.abs(d) < 1e-6) return false;
      this.cur += Math.abs(d) < 1e-4 ? d : d * k;
    }
    this.apply();
    return true;
  }
  // 0..1 along its travel, measured from the pose (levers read this continuously).
  fraction() {
    if (this.angles) {
      const a0 = this.angles[0], a1 = this.angles[this.angles.length - 1];
      return (this.cur - a0) / (a1 - a0);
    }
    return this.value;
  }
  describe() {
    let s = this.label;
    if (this.motion === "stick") return `${s}: pitch ${Math.round(this.stick.y * 100)}%, roll ${Math.round(this.stick.x * 100)}%`;
    if (this.positions) return `${s}: ${this.positions[this.state]}`;
    if (this.kind === "rotary" || this.kind === "collective") return `${s}: ${Math.round(this.value * 100)}%`;
    if (this.kind === "pedal") return `${s}: ${Math.round((this.value - 0.5) * 200)}%`;
    if (this.latching) return `${s}: ${this.on ? "ON" : "OFF"}`;
    if (this.hasLit) return `${s}${this.lit ? " (lit)" : ""}`;
    return s;
  }
}

export class Controls {
  constructor(root, onChange) {
    this.list = [];
    this.byFn = new Map();
    this.byObj = new Map();
    this.onChange = onChange;
    this.moving = new Set();
    root.traverse((o) => {
      if (!o.userData || !o.userData.control || !o.userData.rest) return;
      const c = new Control(o);
      this.list.push(c);
      this.byObj.set(o, c);
      if (c.fn) {
        if (!this.byFn.has(c.fn)) this.byFn.set(c.fn, []);
        this.byFn.get(c.fn).push(c);
      }
    });
    this.litMat = null;
    this.unlitMat = null;
    root.traverse((o) => {
      if (!o.isMesh) return;
      if (o.material.name === "Displays") this.litMat = o.material;
      if (o.material.name === "Displays_Unlit") this.unlitMat = o.material;
    });
    this.tinted = new Map();
    for (const c of this.list) if (c.hasLit) this.setLitOne(c, c.lit);
  }
  get(fn) {
    return (this.byFn.get(fn) || [])[0];
  }
  all(fn) {
    return this.byFn.get(fn) || [];
  }
  // The control an object belongs to, climbing up from a hit mesh.
  pick(obj) {
    for (let o = obj; o; o = o.parent) {
      const c = this.byObj.get(o);
      if (c) return c;
    }
    return null;
  }
  wake(c) {
    this.moving.add(c);
  }
  update(dt) {
    const now = performance.now();
    for (const c of this.list) if (c.springAt || c.pressUntil) this.moving.add(c);
    for (const c of [...this.moving]) {
      const still = c.step(dt, now);
      if (!still && !c.springAt && !(c.pressUntil > now)) this.moving.delete(c);
    }
  }
  // Copy a control's state to its twins (the two cyclics, collectives, pedals...).
  sync(c) {
    // Only linked controls move together: the flight controls, and latching buttons that share a function.
    if (!["stick", "collective", "pedal"].includes(c.kind) && !c.latching) return;
    for (const o of this.all(c.fn)) {
      if (o === c || o.kind !== c.kind) continue;
      o.state = c.state;
      o.value = c.value;
      o.on = c.on;
      if (c.stick) o.stick = { ...c.stick };
      this.wake(o);
    }
  }
  set(c, patch, source = "user") {
    Object.assign(c, patch);
    this.wake(c);
    this.sync(c);
    this.onChange && this.onChange(c, { source, ...patch });
  }
  // A click: dir +1 moves on (clockwise, forward, down the list), -1 back. `up` says the hit was above the pivot.
  click(c, { dir = 1, up = null } = {}) {
    const now = performance.now();
    switch (c.kind) {
      case "toggle": {
        const n = c.positions.length;
        let next = up === null ? c.state + dir : up ? c.state - 1 : c.state + 1;
        if (next < 0 || next >= n) next = up === null ? c.state - dir : up ? c.state + 1 : c.state - 1;
        next = Math.max(0, Math.min(n - 1, next));
        if (next === c.state) return;
        const springAt = c.momentary.includes(next) ? now + 700 : 0;
        this.set(c, { state: next, springAt });
        return;
      }
      case "guard":
      case "door":
      case "handle":
        this.set(c, { state: c.state ? 0 : 1 });
        return;
      case "rocker": {
        const next = up === false ? 2 : 0;
        this.set(c, { state: next, springAt: now + 250, pressed: next === 0 ? "UP" : "DOWN" });
        return;
      }
      case "trigger":
        this.set(c, { state: 1, springAt: now + 180, pressed: true });
        return;
      case "rotary":
        if (c.positions) {
          const n = c.positions.length;
          let next = c.state + dir;
          if (next >= n || next < 0) next = c.state - dir;
          this.set(c, { state: Math.max(0, Math.min(n - 1, next)) });
        } else this.set(c, { value: Math.max(0, Math.min(1, c.value + dir * 0.125)) });
        return;
      case "lever": {
        const n = c.positions.length;
        let next = c.state + dir;
        if (next >= n || next < 0) next = c.state - dir;
        this.set(c, { state: Math.max(0, Math.min(n - 1, next)) });
        return;
      }
      case "button":
      case "key":
        c.pressUntil = now + 140;
        this.wake(c);
        if (c.latching) this.set(c, { on: !c.on, pressed: true });
        else this.onChange && this.onChange(c, { source: "user", pressed: true });
        return;
    }
  }
  // Continuous motion (mouse drag or a VR hand): d = [dx, dy] in the control's own units.
  drag(c, dx, dy) {
    if (c.kind === "stick") this.set(c, { stick: { x: clamp(c.stick.x + dx, -1, 1), y: clamp(c.stick.y + dy, -1, 1) } }, "drag");
    else if (c.kind === "collective") this.set(c, { value: clamp(c.value + dy, 0, 1) }, "drag");
    else if (c.kind === "pedal") this.set(c, { value: clamp(c.value + dx, 0, 1) }, "drag");
    else if (c.kind === "rotary" && !c.positions) this.set(c, { value: clamp(c.value + dy, 0, 1) }, "drag");
    else if (c.kind === "lever") {
      // slide along the slot, then settle on the nearest detent when let go
      const a0 = c.angles[0], a1 = c.angles[c.angles.length - 1];
      c.free = clamp((c.free ?? c.fraction()) + dy, 0, 1);
      let best = 0;
      c.angles.forEach((a, i) => {
        if (Math.abs((a - a0) / (a1 - a0) - c.free) < Math.abs((c.angles[best] - a0) / (a1 - a0) - c.free)) best = i;
      });
      if (best !== c.state) this.set(c, { state: best }, "drag");
    }
  }
  release(c) {
    c.free = undefined;
    if (c.kind === "stick" && c.spring !== false) this.set(c, { stick: { x: 0, y: 0 } }, "release");
  }
  setLitOne(c, on, tint) {
    c.lit = on;
    let mat = on ? this.litMat : this.unlitMat;
    if (on && tint) {
      if (!this.tinted.has(tint)) {
        const m = this.litMat.clone();
        m.emissive.set(tint);
        this.tinted.set(tint, m);
      }
      mat = this.tinted.get(tint);
    }
    if (!mat) return;
    c.obj.traverse((o) => {
      if (o.isMesh && (o.material === this.litMat || o.material === this.unlitMat || [...this.tinted.values()].includes(o.material))) o.material = mat;
    });
  }
  setLit(fn, on, tint) {
    for (const c of this.all(fn)) if (c.hasLit && (c.lit !== on || c.tint !== tint)) {
      this.setLitOne(c, on, tint);
      c.tint = tint;
    }
  }
  resetAll() {
    for (const c of this.list) {
      c.state = c.defaults.state;
      c.value = c.defaults.value;
      c.on = false;
      c.springAt = 0;
      c.free = undefined;
      if (c.stick) c.stick = { x: 0, y: 0 };
      if (c.hasLit) this.setLitOne(c, c.defaults.lit);
      this.wake(c);
    }
  }
}

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
