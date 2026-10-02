// A simple simulation of the aircraft behind the controls: APU, engines,
// rotor and rotor brake, fire handles, fuel, cautions and warnings, lights,
// weapons, the TADS sight, and an arcade flight model that drives the
// instruments. It's tuned to feel right in a cockpit, not to be a flight
// model you'd certify.
const G = 9.81;
const FIELD_FT = 1150;
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const approach = (v, t, rate, dt) => (v < t ? Math.min(t, v + rate * dt) : Math.max(t, v - rate * dt));

export class Sim {
  constructor(controls) {
    this.ctl = controls;
    this.events = [];
    this.reset();
  }

  reset() {
    this.t = 0;
    this.apu = { on: false, n: 0, fire: false };
    this.eng = [0, 1].map(() => ({ ng: 84.6, tgt: 610, running: true, starting: false, fire: false, oil: 62 }));
    this.nr = 101;
    this.rotorAngle = 0;
    this.tailAngle = 0;
    // flight state: position (m, world), velocity, heading (deg, clockwise from north), pitch/roll (deg)
    this.p = [0, 0, 0];
    this.v = [0, 0, 0];
    this.hdg = 0;
    this.pitch = 0;
    this.roll = 0;
    this.onGround = true;
    this.airborneSince = null;
    this.fuelFwd = 1120;
    this.fuelAft = 1330;
    this.masterArm = false;
    this.weapon = "MSL";
    this.gun = 300;
    this.rkt = { LI: 19, RI: 19 };
    this.msl = { LO: 4, RO: 4 };
    this.gone = {};
    this.burstLeft = 0;
    this.burstClock = 0;
    this.tedac = { fov: "M", sensor: "FLIR", az: 0, el: -1.5, range: 3420, lasing: 0, slaved: false };
    this.rts = 0;
    this.radios = [["VHF", "127.500", "TOWER", "121.500"], ["UHF", "305.100", "GUARD", "243.000"], ["FM1", "30.000", "BN CMD", "32.250"], ["FM2", "51.500", "CO TAC", "52.100"], ["HF", "3.050", "", "5.200"]];
    this.ack = new Set();
    this.mwarn = false;
    this.mcaut = false;
    this.messages = [];
    this.canopyGone = false;
    this.input = { x: 0, y: 0, col: 0, ped: 0 };
  }

  // A control changed; `ev.pressed` for buttons, keys and triggers.
  control(c, ev) {
    const fn = c.fn;
    if (!fn) return;
    if (ev.pressed) {
      switch (fn) {
        case "apu":
          if (!this.apu.fire) this.apu.on = !this.apu.on;
          break;
        case "fire1":
        case "fire2": {
          const e = this.eng[fn === "fire1" ? 0 : 1];
          e.fire = !e.fire;
          this.say(e.fire ? `ENG ${fn.slice(-1)} FIRE HANDLE PULLED` : `ENG ${fn.slice(-1)} FIRE HANDLE RESET`);
          break;
        }
        case "fireApu":
          this.apu.fire = !this.apu.fire;
          if (this.apu.fire) this.apu.on = false;
          break;
        case "dischPri":
        case "dischRes":
          this.say(fn === "dischPri" ? "PRIMARY BOTTLE DISCHARGED" : "RESERVE BOTTLE DISCHARGED");
          break;
        case "mwarn":
          this.mwarn = false;
          this.acknowledge("W");
          break;
        case "mcaut":
          this.mcaut = false;
          this.acknowledge("C");
          break;
        case "masterArm":
          this.masterArm = !this.masterArm;
          break;
        case "was": {
          const order = ["GUN", "RKT", "MSL"];
          this.weapon = order[(order.indexOf(this.weapon) + 1) % 3];
          this.say(`WEAPON ${this.weapon}`);
          break;
        }
        case "trigger":
          this.fire();
          break;
        case "tailWheel":
          this.tailLock = !this.tailLock;
          break;
        case "tedac.fov":
          this.tedac.fov = { W: "M", M: "N", N: "W" }[this.tedac.fov];
          break;
        case "tedac.sensor":
          this.tedac.sensor = this.tedac.sensor === "FLIR" ? "DTV" : "FLIR";
          break;
        case "tedac.slave":
          this.tedac.slaved = !this.tedac.slaved;
          break;
        case "tedac.laser":
          if (this.state("laserArm") === "ARM") this.tedac.lasing = 2.5;
          else this.say("LASER SAFE");
          break;
        case "flare":
          this.events.push({ type: "flare" });
          this.say("FLARE");
          break;
        case "trim":
          this.say("FORCE TRIM RELEASE");
          break;
        default:
          if (fn.startsWith("jett.")) this.jettison(fn.slice(5));
      }
    }
    if (fn === "canopyJett" && c.state === 1 && !this.canopyGone) {
      this.canopyGone = true;
      this.events.push({ type: "canopyJett" });
      this.say("CANOPY JETTISONED");
    }
  }

  // Current position label of the first control with this fn.
  state(fn) {
    const c = this.ctl.get(fn);
    return c && c.positions ? c.positions[c.state] : undefined;
  }
  value(fn, d = 0) {
    const c = this.ctl.get(fn);
    return c ? c.value : d;
  }
  latched(fn) {
    const c = this.ctl.get(fn);
    return c ? c.on : false;
  }

  say(text) {
    this.messages.unshift({ text, until: this.t + 4 });
    this.events.push({ type: "toast", text });
  }

  acknowledge(level) {
    for (const m of this.wcaList()) if (m.level === level) this.ack.add(m.text);
  }

  jettison(which) {
    const list = which === "ALL" ? ["LO", "LI", "RI", "RO"] : [which];
    for (const s of list) {
      if (this.gone[s]) continue;
      this.gone[s] = true;
      if (s in this.rkt) this.rkt[s] = 0;
      if (s in this.msl) this.msl[s] = 0;
      this.events.push({ type: "jettison", station: s });
    }
    this.say(which === "ALL" ? "EMERGENCY JETTISON" : `JETTISON ${which}`);
  }

  fire() {
    if (!this.masterArm) return this.say("MASTER ARM SAFE");
    if (this.onGround && !this.latched("gndOride")) return this.say("GROUND OVERRIDE OFF");
    if (this.weapon === "GUN") {
      if (this.gun <= 0) return this.say("GUN EMPTY");
      const burst = { "10": 10, "20": 20, "50": 50, "100": 100, ALL: 300 }[this.state("gunBurst") || "20"];
      this.burstLeft = Math.min(this.gun, burst);
    } else if (this.weapon === "RKT") {
      let n = 0;
      for (const s of ["LI", "RI"]) if (this.rkt[s] > 0) {
        this.rkt[s]--;
        n++;
        this.events.push({ type: "rocket", station: s });
      }
      if (!n) this.say("NO ROCKETS");
    } else {
      const s = ["LO", "RO"].find((k) => this.msl[k] > 0);
      if (!s) return this.say("NO MISSILES");
      this.events.push({ type: "missile", station: s, index: this.msl[s], target: this.tedac.lasing > 0 });
      this.msl[s]--;
    }
  }

  wcaList() {
    const L = [];
    const air = !this.onGround;
    const run = this.eng.map((e) => e.running);
    ["1", "2"].forEach((n, i) => {
      if (this.eng[i].fire) L.push({ level: "W", text: `ENG ${n} FIRE HNDL` });
      if (!run[i] && (air || run[1 - i])) L.push({ level: air ? "W" : "C", text: `ENG ${n} OUT` });
    });
    if (air && this.nr < 94) L.push({ level: "W", text: "LOW ROTOR RPM" });
    const brk = this.state("rtrBrk");
    if (brk && brk !== "OFF" && this.nr > 1) L.push({ level: "C", text: "RTR BRK ON" });
    if (this.fuelFwd + this.fuelAft < 400) L.push({ level: "C", text: "FUEL LOW" });
    if (air && (this.state("doorCpg") === "OPEN" || this.state("doorPilot") === "OPEN")) L.push({ level: "C", text: "CANOPY OPEN" });
    if (this.apu.on) L.push({ level: "A", text: this.apu.n > 95 ? "APU ON" : "APU START" });
    if (this.apu.fire) L.push({ level: "W", text: "APU FIRE HNDL" });
    for (const [fn, t] of [["aiInlet", "INLET ANTI-ICE"], ["aiTads", "TADS ANTI-ICE"], ["aiWshld", "WSHLD ANTI-ICE"], ["boost", "BOOST PUMP ON"]]) if (this.state(fn) === "ON") L.push({ level: "A", text: t });
    if (this.state("xfeed") && this.state("xfeed") !== "NORM") L.push({ level: "A", text: `XFEED ${this.state("xfeed")}` });
    if (this.state("fuelTrans") && this.state("fuelTrans") !== "OFF") L.push({ level: "A", text: `FUEL XFR ${this.state("fuelTrans")}` });
    if (this.latched("parkBrake")) L.push({ level: "A", text: "PARK BRAKE ON" });
    if (!this.tailLock) L.push({ level: "A", text: "TAIL WHL UNLK" });
    if (this.latched("gndOride")) L.push({ level: "A", text: "GND ORIDE ON" });
    if (this.state("searchlight") === "ON") L.push({ level: "A", text: "SEARCH LT ON" });
    return L;
  }

  update(dt) {
    this.t += dt;
    const { input } = this;
    if (this.tailLock === undefined) this.tailLock = true;
    // --- APU ---
    this.apu.n = approach(this.apu.n, this.apu.on ? 100 : 0, this.apu.on ? 16 : 12, dt);
    // --- engines ---
    const col = input.col;
    const levers = ["pwr1", "pwr2"].map((f) => {
      const c = this.ctl.get(f);
      return c ? c.fraction() : 1;
    });
    const idleAt = (() => {
      const c = this.ctl.get("pwr1");
      if (!c) return 0.43;
      const a = c.angles;
      return (a[1] - a[0]) / (a[2] - a[0]);
    })();
    const air = this.apu.n > 90 || this.eng.some((e) => e.running && e.ng > 60);
    this.eng.forEach((e, i) => {
      const f = levers[i];
      const cut = f < 0.25 || e.fire || this.fuelFwd + this.fuelAft <= 0;
      const throttle = clamp((f - idleAt) / (1 - idleAt), 0, 1);
      const start = this.state(i ? "eng2Start" : "eng1Start") === "START";
      if (e.running) {
        if (cut) {
          e.running = false;
          this.say(`ENG ${i + 1} SHUTDOWN`);
        }
      } else if (e.starting) {
        // The start runs on by itself once begun; with the lever at OFF the starter only motors it.
        e.ng = approach(e.ng, cut ? 22 : 64, e.ng < 22 ? 6 : 8, dt);
        e.tgt = approach(e.tgt, e.ng > 20 && !cut ? 780 : 60, 60, dt);
        if (e.ng >= 60 && !cut) {
          e.running = true;
          e.starting = false;
          this.say(`ENG ${i + 1} RUNNING`);
        }
        if (cut && e.ng >= 21.9 && (e.startClock = (e.startClock || 0) + dt) > 15) {
          e.starting = false;
          e.startClock = 0;
          this.say(`ENG ${i + 1} START ABORTED - POWER LEVER OFF`);
        }
      } else if (start) {
        if (air) {
          e.starting = true;
          this.say(`ENG ${i + 1} START`);
        } else if (!this._noAir) {
          this._noAir = true;
          this.say("START: NO AIR - APU OFF");
          setTimeout(() => (this._noAir = false), 2000);
        }
      }
      if (e.running) {
        const target = 64 + (24 + col * 10) * throttle;
        e.ng = approach(e.ng, target, 12, dt);
        e.tgt = approach(e.tgt, 420 + e.ng * 2.2 + col * 180 * throttle, 90, dt);
        e.oil = approach(e.oil, 50 + e.ng * 0.14, 10, dt);
      } else if (!e.starting) {
        e.ng = approach(e.ng, 0, 6, dt);
        e.tgt = approach(e.tgt, 60, 25, dt);
        e.oil = approach(e.oil, 0, 15, dt);
      }
      e.np = e.running ? (e.ng < 64 ? e.ng : 70 + 31 * throttle) : 0;
    });
    // --- rotor ---
    const drive = Math.max(...this.eng.map((e) => (e.running ? e.np : 0)));
    const brk = this.state("rtrBrk") || "OFF";
    let target = drive;
    if (brk === "BRK") target = drive > 0 ? Math.max(0, drive - 35) : 0;
    if (brk === "LOCK" && this.nr < 5) target = 0;
    if (this.nr < target) this.nr = approach(this.nr, target, this.nr > 60 ? 12 : 6, dt);
    else this.nr = approach(this.nr, target, brk === "BRK" ? 10 : 1.4 + col * 1.5, dt);
    if (brk === "LOCK" && this.nr < 5) this.nr = 0;
    const running = this.eng.filter((e) => e.running).length;
    // each engine carries half the load with both running, all of it alone
    const load = (12 + 118 * col) * (this.nr / 101);
    this.eng.forEach((e) => (e.tq = e.running ? load * (running === 1 ? 2 : 1) : 0));
    // --- fuel ---
    const burn = (this.eng.reduce((a, e) => a + (e.running ? 0.06 + e.ng * 0.0012 : 0), 0) + (this.apu.on ? 0.02 : 0)) * dt;
    const trans = this.state("fuelTrans");
    if (this.fuelAft > 0) this.fuelAft = Math.max(0, this.fuelAft - burn * 0.55);
    if (this.fuelFwd > 0) this.fuelFwd = Math.max(0, this.fuelFwd - burn * 0.45);
    if (trans === "FWD" && this.fuelAft > 0 && this.fuelFwd < 1600) (this.fuelAft -= 8 * dt), (this.fuelFwd += 8 * dt);
    if (trans === "AFT" && this.fuelFwd > 0 && this.fuelAft < 2200) (this.fuelFwd -= 8 * dt), (this.fuelAft += 8 * dt);
    this.flight(dt);
    this.weapons(dt);
    // --- TADS ---
    const t = this.tedac;
    if (t.slaved) (t.az = approach(t.az, 0, 30, dt)), (t.el = approach(t.el, -1.5, 30, dt));
    if (t.lasing > 0) {
      t.lasing -= dt;
      const elr = (-t.el * Math.PI) / 180;
      const h = this.p[1] + 2;
      t.range = elr > 0.002 ? Math.min(9999, h / Math.tan(elr) + 3000 * (1 - Math.min(1, h / 50))) : 0;
    }
    // --- cautions and warnings ---
    const list = this.wcaList();
    for (const m of list) {
      if (this.ack.has(m.text)) continue;
      if (m.level === "W" && !this.mwarn) (this.mwarn = true), this.events.push({ type: "warn" });
      if (m.level === "C" && !this.mcaut) this.mcaut = true;
    }
    for (const a of [...this.ack]) if (!list.some((m) => m.text === a)) this.ack.delete(a);
    this.wca = list;
    this.messages = this.messages.filter((m) => m.until > this.t);
    // lit legends
    this.lit = {
      mwarn: this.mwarn,
      mcaut: this.mcaut,
      apu: this.apu.on && this.apu.n > 95,
      fire1: this.eng[0].fire,
      fire2: this.eng[1].fire,
      fireApu: this.apu.fire,
      masterArm: true,
      tailWheel: this.tailLock,
    };
  }

  flight(dt) {
    const { input } = this;
    const nrf = clamp(this.nr / 101, 0, 1.1);
    const thrust = input.col * 1.9 * G * nrf * nrf;
    const rad = Math.PI / 180;
    const wasGround = this.onGround;
    if (!this.onGround) {
      this.pitch = approach(this.pitch, -input.y * 22, 30, dt);
      this.roll = approach(this.roll, input.x * 32, 45, dt);
    } else {
      this.pitch = approach(this.pitch, 0, 20, dt);
      this.roll = approach(this.roll, 0, 20, dt);
    }
    const speed = Math.hypot(this.v[0], this.v[2]);
    let yawRate = input.ped * 55 * nrf;
    if (this.onGround && (this.tailLock || this.latched("parkBrake"))) yawRate = 0;
    if (speed > 12 && !this.onGround) yawRate += ((G * Math.tan(this.roll * rad)) / speed) * (180 / Math.PI) * 0.8;
    this.hdg = (this.hdg + yawRate * dt + 360) % 360;
    // body axes in world space (nose = +Z at heading 0, east = -X)
    const h = this.hdg * rad, p = this.pitch * rad, r = this.roll * rad;
    const fwd = [-Math.sin(h) * Math.cos(p), Math.sin(p), Math.cos(h) * Math.cos(p)];
    // the rotor's thrust axis: yaw -h about Y, then pitch -p about X, then roll r about Z (as the model is posed)
    const up = [-Math.sin(r) * Math.cos(h) + Math.cos(r) * Math.sin(p) * Math.sin(h), Math.cos(r) * Math.cos(p), -Math.sin(r) * Math.sin(h) - Math.cos(r) * Math.sin(p) * Math.cos(h)];
    const ul = 1;
    const a = [(up[0] / ul) * thrust, (up[1] / ul) * thrust - G, (up[2] / ul) * thrust];
    // drag: linear plus quadratic, stronger vertically
    for (const i of [0, 2]) a[i] -= this.v[i] * 0.12 + this.v[i] * Math.abs(this.v[i]) * 0.0035;
    a[1] -= this.v[1] * 0.5;
    if (this.onGround) {
      if (thrust < G * 0.98) {
        a[0] = a[2] = 0;
        this.v[0] *= Math.pow(0.02, dt);
        this.v[2] *= Math.pow(0.02, dt);
        if (!this.latched("parkBrake") && this.nr > 60 && input.col > 0.15 && Math.abs(input.y) > 0.1) {
          // taxi: the cyclic pushes it along
          const ta = input.y * 1.5;
          a[0] = fwd[0] * ta;
          a[2] = fwd[2] * ta;
        }
      }
    }
    for (let i = 0; i < 3; i++) this.v[i] += a[i] * dt;
    if (this.onGround && this.v[1] < 0) this.v[1] = 0;
    for (let i = 0; i < 3; i++) this.p[i] += this.v[i] * dt;
    if (this.p[1] <= 0) {
      if (!wasGround && this.v[1] < -3.5) this.say("HARD LANDING");
      this.p[1] = 0;
      if (this.v[1] < 0) this.v[1] = 0;
      this.onGround = true;
    } else if (this.p[1] > 0.05) this.onGround = false;
    if (!this.onGround && this.airborneSince === null) this.airborneSince = this.t;
    this.fwd = fwd;
    this.speedFwd = this.v[0] * -Math.sin(h) + this.v[2] * Math.cos(h);
    this.speedRight = this.v[0] * -Math.cos(h) + this.v[2] * -Math.sin(h);
    this.slip = clamp((this.speedRight * 0.05 - input.ped * 0.2) * (this.onGround ? 0 : 1), -1, 1);
  }

  weapons(dt) {
    if (this.burstLeft > 0) {
      this.burstClock -= dt;
      while (this.burstClock <= 0 && this.burstLeft > 0) {
        this.burstClock += 0.1;
        this.burstLeft--;
        this.gun--;
        this.events.push({ type: "gun" });
      }
    }
  }

  // Everything the displays show.
  data(now = new Date()) {
    const pad = (n) => String(n).padStart(2, "0");
    const e = this.eng;
    const fuel = this.fuelFwd + this.fuelAft;
    const burnH = e.reduce((a, x) => a + (x.running ? 0.06 + x.ng * 0.0012 : 0), 0) * 3600;
    const endur = burnH > 0 ? fuel / burnH : 0;
    const flt = this.airborneSince === null ? 0 : this.t - this.airborneSince;
    return {
      hdg: this.hdg, ias: Math.max(0, this.speedFwd * 1.944), alt: FIELD_FT + this.p[1] * 3.281 + (this.value("altBaro", 0.5) - 0.5) * 400, ralt: this.p[1] * 3.281,
      pitch: this.pitch, roll: this.roll, vs: this.v[1] * 196.85, slip: this.slip || 0, vx: (this.speedRight || 0) * 1.944, vz: (this.speedFwd || 0) * 1.944,
      tq: Math.max(e[0].tq || 0, e[1].tq || 0), nr: this.nr, fuel,
      time: `${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}:${pad(now.getUTCSeconds())}`,
      flt: `${pad(Math.floor(flt / 3600))}:${pad(Math.floor(flt / 60) % 60)}`,
      pos: [this.p[0], this.p[2]],
      eng: { tq: e.map((x) => x.tq || 0), tgt: e.map((x) => x.tgt), ng: e.map((x) => x.ng), np: e.map((x) => x.np || 0), nr: this.nr, oil: e.map((x) => x.oil), hyd: [this.nr > 50 ? 3000 : this.nr * 60, this.nr > 50 ? 3010 : this.nr * 60], run: e.map((x) => x.running) },
      fuelTanks: { fwd: this.fuelFwd, aft: this.fuelAft, boost: this.state("boost") === "ON", xfeed: this.state("xfeed") || "NORM", trans: this.state("fuelTrans") || "OFF", endurance: `${Math.floor(endur)}:${pad(Math.floor((endur % 1) * 60))}` },
      wpn: { arm: this.masterArm, sel: this.weapon, gun: this.gun, burst: this.state("gunBurst") || "20", rkt: this.rkt, msl: this.msl, gone: this.gone, code: "A 1688" },
      radios: this.radios, rts: this.rts,
      wca: this.wca || [],
      tedac: {
        power: this.state("tadsPower") || "ON", sensor: this.tedac.sensor, flir: this.state("flirPower") !== "OFF", dtv: this.state("dtvPower") !== "OFF",
        pol: this.state("flirPol") || "WHT", gain: this.value("tedacGain", 0.5), level: this.value("tedacLevel", 0.5), fov: this.tedac.fov,
        az: this.tedac.az, el: this.tedac.el, range: this.tedac.range, lasing: this.tedac.lasing > 0, laserArm: this.state("laserArm") === "ARM", slaved: this.tedac.slaved,
      },
      t: this.t,
    };
  }
}
