// Synthesised sound: rotor, turbines, APU, switch clicks, gunfire and the
// warning tone. Nothing is downloaded; it all comes from oscillators and noise.
export class Sound {
  constructor() {
    this.ctx = null;
    this.on = false;
  }
  start() {
    if (this.ctx) {
      this.ctx.resume();
      this.on = true;
      return;
    }
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    const ctx = (this.ctx = new AC());
    this.on = true;
    this.master = ctx.createGain();
    this.master.gain.value = 0.6;
    this.master.connect(ctx.destination);
    const noiseBuf = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate);
    const ch = noiseBuf.getChannelData(0);
    for (let i = 0; i < ch.length; i++) ch[i] = Math.random() * 2 - 1;
    this.noiseBuf = noiseBuf;
    const noise = () => {
      const s = ctx.createBufferSource();
      s.buffer = noiseBuf;
      s.loop = true;
      s.start();
      return s;
    };
    // rotor: filtered noise, chopped at the blade passing frequency
    const rn = noise();
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 260;
    this.rotorGain = ctx.createGain();
    this.rotorGain.gain.value = 0;
    this.chop = ctx.createOscillator();
    this.chop.type = "sawtooth";
    const chopDepth = ctx.createGain();
    chopDepth.gain.value = 0.5;
    this.chop.connect(chopDepth).connect(this.rotorGain.gain);
    this.chop.start();
    rn.connect(lp).connect(this.rotorGain).connect(this.master);
    // turbines: a whine per engine, plus a hiss
    this.turbines = [0, 1].map(() => {
      const o = ctx.createOscillator();
      o.type = "sawtooth";
      const bp = ctx.createBiquadFilter();
      bp.type = "bandpass";
      bp.Q.value = 8;
      const gn = ctx.createGain();
      gn.gain.value = 0;
      o.connect(bp).connect(gn).connect(this.master);
      o.start();
      return { o, bp, gn };
    });
    const hn = noise();
    const hp = ctx.createBiquadFilter();
    hp.type = "highpass";
    hp.frequency.value = 2500;
    this.hiss = ctx.createGain();
    this.hiss.gain.value = 0;
    hn.connect(hp).connect(this.hiss).connect(this.master);
    const apu = ctx.createOscillator();
    apu.type = "triangle";
    apu.frequency.value = 3600;
    this.apuGain = ctx.createGain();
    this.apuGain.gain.value = 0;
    apu.connect(this.apuGain).connect(this.master);
    apu.start();
    this.apuOsc = apu;
    const tone = ctx.createOscillator();
    tone.frequency.value = 900;
    this.toneGain = ctx.createGain();
    this.toneGain.gain.value = 0;
    tone.connect(this.toneGain).connect(this.master);
    tone.start();
  }
  stop() {
    if (this.ctx) this.ctx.suspend();
    this.on = false;
  }
  update(sim, t) {
    if (!this.on || !this.ctx) return;
    const now = this.ctx.currentTime;
    const nr = sim.nr / 101;
    this.chop.frequency.setTargetAtTime(Math.max(0.1, 4 * 4.82 * nr), now, 0.1);
    this.rotorGain.gain.setTargetAtTime(Math.min(0.9, nr * 0.9), now, 0.2);
    sim.eng.forEach((e, i) => {
      const tb = this.turbines[i];
      const f = 180 + e.ng * 38;
      tb.o.frequency.setTargetAtTime(f, now, 0.2);
      tb.bp.frequency.setTargetAtTime(f, now, 0.2);
      tb.gn.gain.setTargetAtTime((e.ng / 100) * 0.05, now, 0.3);
    });
    this.hiss.gain.setTargetAtTime(Math.max(sim.eng[0].ng, sim.eng[1].ng) / 100 * 0.05, now, 0.3);
    this.apuOsc.frequency.setTargetAtTime(600 + sim.apu.n * 30, now, 0.3);
    this.apuGain.gain.setTargetAtTime((sim.apu.n / 100) * 0.02, now, 0.3);
    this.toneGain.gain.setTargetAtTime(sim.mwarn && Math.floor(t * 3) % 2 === 0 ? 0.05 : 0, now, 0.01);
  }
  burst(freq, dur, gain, type = "noise") {
    if (!this.on || !this.ctx) return;
    const ctx = this.ctx;
    const g = ctx.createGain();
    g.gain.setValueAtTime(gain, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + dur);
    let src;
    if (type === "noise") {
      src = ctx.createBufferSource();
      src.buffer = this.noiseBuf;
      const f = ctx.createBiquadFilter();
      f.type = "bandpass";
      f.frequency.value = freq;
      src.connect(f).connect(g);
    } else {
      src = ctx.createOscillator();
      src.frequency.value = freq;
      src.connect(g);
    }
    g.connect(this.master);
    src.start();
    src.stop(ctx.currentTime + dur + 0.02);
  }
  click() {
    this.burst(3200, 0.03, 0.25);
  }
  gun() {
    this.burst(400, 0.09, 0.5);
  }
  whoosh() {
    this.burst(900, 0.6, 0.35);
  }
  boom() {
    this.burst(120, 1.2, 0.6);
  }
}
