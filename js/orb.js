// The orb: Fable One's face, built as a small 3D scene.
//
//   shell     a glass sphere rippled by simplex noise. Its normals are worked
//             out from the rippled surface itself (finite differences in the
//             vertex shader), so the ripples catch the light and shade like
//             real bumps instead of looking painted on.
//   core      a glowing energy ball inside the shell, seen through the glass
//   rings     three tilted orbits, each with a bead of light running round it
//   disk      a tilted disk of particles turning at different speeds
//   halo      a shell of particles breathing round the orb
//   stars     a far starfield; the camera drifts with the pointer, so the
//             layers move at different depths
//
// It reacts to real things only: the pointer (ripples where it hovers, a
// shockwave where it's pressed, a lean towards it), typing, the microphone
// level, speech, answers arriving, and tools running.
(() => {
  const F = window.Fable;
  const root = document.documentElement;
  const canvas = document.getElementById("orb");
  const fallback = document.getElementById("orb-fallback");
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let state = "idle";
  let levelTarget = 0;
  let kick = 0;
  let flashUntil = 0;

  function useFallback() {
    if (canvas) canvas.hidden = true;
    if (fallback) fallback.hidden = false;
    const noop = () => {};
    F.orb = {
      webgl: false,
      setState(s) {
        state = s;
        if (fallback) fallback.dataset.state = s;
      },
      setLevel: noop, kick: noop, flash: noop, recolor: noop, ripple: noop, burst: noop, tap: noop, busy: noop,
    };
  }

  if (!canvas || !window.THREE) return useFallback();

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
  } catch (e) {
    return useFallback();
  }
  let pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
  renderer.setPixelRatio(pixelRatio);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
  const CAMERA_Z = 7.6;
  camera.position.z = CAMERA_Z;
  const world = new THREE.Group(); // everything but the stars
  scene.add(world);

  // Classic 3D simplex noise (Ashima Arts / Stefan Gustavson, MIT).
  const NOISE = `
    vec3 mod289(vec3 x){return x-floor(x*(1.0/289.0))*289.0;}
    vec4 mod289(vec4 x){return x-floor(x*(1.0/289.0))*289.0;}
    vec4 permute(vec4 x){return mod289(((x*34.0)+1.0)*x);}
    vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-0.85373472095314*r;}
    float snoise(vec3 v){
      const vec2 C=vec2(1.0/6.0,1.0/3.0); const vec4 D=vec4(0.0,0.5,1.0,2.0);
      vec3 i=floor(v+dot(v,C.yyy)); vec3 x0=v-i+dot(i,C.xxx);
      vec3 g=step(x0.yzx,x0.xyz); vec3 l=1.0-g; vec3 i1=min(g.xyz,l.zxy); vec3 i2=max(g.xyz,l.zxy);
      vec3 x1=x0-i1+C.xxx; vec3 x2=x0-i2+C.yyy; vec3 x3=x0-D.yyy;
      i=mod289(i);
      vec4 p=permute(permute(permute(i.z+vec4(0.0,i1.z,i2.z,1.0))+i.y+vec4(0.0,i1.y,i2.y,1.0))+i.x+vec4(0.0,i1.x,i2.x,1.0));
      float n_=0.142857142857; vec3 ns=n_*D.wyz-D.xzx;
      vec4 j=p-49.0*floor(p*ns.z*ns.z); vec4 x_=floor(j*ns.z); vec4 y_=floor(j-7.0*x_);
      vec4 x=x_*ns.x+ns.yyyy; vec4 y=y_*ns.x+ns.yyyy; vec4 h=1.0-abs(x)-abs(y);
      vec4 b0=vec4(x.xy,y.xy); vec4 b1=vec4(x.zw,y.zw);
      vec4 s0=floor(b0)*2.0+1.0; vec4 s1=floor(b1)*2.0+1.0; vec4 sh=-step(h,vec4(0.0));
      vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy; vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
      vec3 p0=vec3(a0.xy,h.x); vec3 p1=vec3(a0.zw,h.y); vec3 p2=vec3(a1.xy,h.z); vec3 p3=vec3(a1.zw,h.w);
      vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
      p0*=norm.x; p1*=norm.y; p2*=norm.z; p3*=norm.w;
      vec4 m=max(0.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.0); m=m*m;
      return 42.0*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
    }`;

  const uniforms = {
    uTime: { value: 0 },
    uAmp: { value: 0.1 },
    uFreq: { value: 1.4 },
    uPulse: { value: 0 },
    uLevel: { value: 0 },
    uCore: { value: new THREE.Color("#ffffff") },
    uRim: { value: new THREE.Color("#ffffff") },
    uGround: { value: new THREE.Color("#000000") },
    // The pointer: where it hovers on the surface, and the last press.
    uHover: { value: new THREE.Vector3(0, 0, 1) },
    uHoverAmt: { value: 0 },
    uHit: { value: new THREE.Vector3(0, 0, 1) },
    uHitAge: { value: 10 },
  };

  // --- the shell ---------------------------------------------------------------------
  const DISPLACE = NOISE + `
    uniform float uTime, uAmp, uFreq, uPulse, uLevel, uHoverAmt, uHitAge;
    uniform vec3 uHover, uHit;
    float displace(vec3 n){
      float a = snoise(n * uFreq + vec3(0.0, uTime * 0.6, uTime * 0.3));
      float b = snoise(n * uFreq * 2.3 - uTime * 0.4) * 0.35;
      float beat = uPulse * (0.5 + 0.5 * sin(uTime * 7.0)) * 0.05;
      float d = (a + b) * (uAmp + uLevel * 0.22) + beat + uLevel * 0.05;
      // A soft swell under the pointer.
      float hd = distance(n, uHover);
      d += uHoverAmt * 0.09 * exp(-hd * hd * 9.0) * (0.6 + 0.4 * sin(uTime * 9.0 - hd * 14.0));
      // The shockwave from a press: a ring that travels out and fades.
      float kd = distance(n, uHit);
      d += 0.16 * exp(-uHitAge * 2.6) * sin(kd * 22.0 - uHitAge * 16.0) * exp(-kd * 2.2) * step(kd, uHitAge * 1.4 + 0.2);
      return d;
    }`;

  const shellMaterial = new THREE.ShaderMaterial({
    uniforms,
    vertexShader: DISPLACE + `
      varying vec3 vNormal; varying vec3 vView; varying float vDisp; varying vec3 vObj;
      void main(){
        vec3 n = normalize(position);
        float d = displace(n);
        vec3 p = n * (1.2 + d);
        // Normals of the rippled surface, from two nearby points on it.
        vec3 t = normalize(abs(n.y) > 0.99 ? cross(n, vec3(1.0, 0.0, 0.0)) : cross(n, vec3(0.0, 1.0, 0.0)));
        vec3 b = cross(n, t);
        float e = 0.012;
        vec3 n1 = normalize(n + t * e);
        vec3 n2 = normalize(n + b * e);
        vec3 p1 = n1 * (1.2 + displace(n1));
        vec3 p2 = n2 * (1.2 + displace(n2));
        vec3 bent = normalize(cross(p1 - p, p2 - p));
        if (dot(bent, n) < 0.0) bent = -bent;
        vDisp = d;
        vObj = n;
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        vNormal = normalize(normalMatrix * bent);
        vView = normalize(-mv.xyz);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: `
      uniform vec3 uCore, uRim, uGround; uniform float uTime, uLevel;
      varying vec3 vNormal; varying vec3 vView; varying float vDisp; varying vec3 vObj;
      void main(){
        vec3 N = normalize(vNormal);
        vec3 V = normalize(vView);
        vec3 key = normalize(vec3(-0.5, 0.7, 0.6));
        vec3 fill = normalize(vec3(0.7, -0.3, 0.4));
        float fres = pow(1.0 - max(dot(N, V), 0.0), 2.3);
        float diff = max(dot(N, key), 0.0) * 0.55 + max(dot(N, fill), 0.0) * 0.18;
        // Glossy: a sharp key highlight and a softer one from the fill.
        vec3 H = normalize(key + V);
        float spec = pow(max(dot(N, H), 0.0), 60.0) * 1.1 + pow(max(dot(N, normalize(fill + V)), 0.0), 18.0) * 0.18;
        // A fake studio: a bright band above, dark below, reflected in the glass.
        vec3 R = reflect(-V, N);
        float env = smoothstep(-0.1, 0.9, R.y) * 0.35 + smoothstep(0.6, 1.0, R.y) * 0.35;
        vec3 body = mix(uGround, uCore, 0.04 + diff * 0.5 + vDisp * 0.9);
        float band = abs(fract(vDisp * 16.0 - uTime * 0.25) - 0.5);
        float line = (1.0 - smoothstep(0.0, 0.05, band)) * (0.22 + 0.55 * uLevel);
        vec3 col = body + uRim * (env * 0.6 + spec) ;
        col = mix(col, uRim, clamp(fres * 1.05 + line, 0.0, 1.0));
        // Glass: see-through in the middle, solid at the rim.
        float alpha = clamp(0.55 + fres * 0.6 + spec * 0.5 + line * 0.4, 0.0, 1.0);
        gl_FragColor = vec4(col, alpha);
      }`,
    transparent: true,
    depthWrite: false,
  });
  const shell = new THREE.Mesh(new THREE.IcosahedronGeometry(1, 36), shellMaterial);
  shell.renderOrder = 3;
  world.add(shell);

  // --- the core inside --------------------------------------------------------------------
  const coreUniforms = { uTime: uniforms.uTime, uLevel: uniforms.uLevel, uRim: uniforms.uRim, uCore: uniforms.uCore, uEnergy: { value: 0.4 } };
  const core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.52, 8),
    new THREE.ShaderMaterial({
      uniforms: coreUniforms,
      vertexShader: NOISE + `
        uniform float uTime, uEnergy;
        varying float vN; varying vec3 vNormal; varying vec3 vView;
        void main(){
          vec3 n = normalize(position);
          vN = snoise(n * 2.4 + uTime * (0.6 + uEnergy));
          vec3 p = n * (0.52 + vN * 0.05 * (0.6 + uEnergy));
          vec4 mv = modelViewMatrix * vec4(p, 1.0);
          vNormal = normalize(normalMatrix * n);
          vView = normalize(-mv.xyz);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        uniform vec3 uRim, uCore; uniform float uLevel, uEnergy;
        varying float vN; varying vec3 vNormal; varying vec3 vView;
        void main(){
          float facing = max(dot(normalize(vNormal), normalize(vView)), 0.0);
          float glow = (0.35 + 0.65 * facing) * (0.55 + 0.45 * vN) * (0.5 + uEnergy * 0.8 + uLevel * 0.7);
          gl_FragColor = vec4(mix(uCore, uRim, 0.5) * glow, clamp(glow, 0.0, 1.0));
        }`,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
  );
  core.renderOrder = 1;
  world.add(core);

  // --- glow sprites ------------------------------------------------------------------------------
  function glowTexture() {
    const c = document.createElement("canvas");
    c.width = c.height = 128;
    const g = c.getContext("2d");
    const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    grad.addColorStop(0, "rgba(255,255,255,0.95)");
    grad.addColorStop(0.3, "rgba(255,255,255,0.3)");
    grad.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = grad;
    g.fillRect(0, 0, 128, 128);
    return new THREE.CanvasTexture(c);
  }
  const glowMap = glowTexture();
  const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowMap, transparent: true, depthWrite: false, opacity: 0.3 }));
  glow.scale.setScalar(5.4);
  glow.position.z = -0.8;
  glow.renderOrder = 0;
  world.add(glow);
  const coreGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowMap, transparent: true, depthWrite: false, opacity: 0.5, blending: THREE.AdditiveBlending }));
  coreGlow.scale.setScalar(1.9);
  coreGlow.renderOrder = 2;
  world.add(coreGlow);

  // --- particles: halo shell and a tilted disk ---------------------------------------------------
  function particleLayer(count, place, sizeBase) {
    const positions = new Float32Array(count * 3);
    const seeds = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) place(i, positions, seeds);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("seed", new THREE.BufferAttribute(seeds, 3));
    const u = {
      uTime: uniforms.uTime, uLevel: uniforms.uLevel, uRim: uniforms.uRim,
      uSwirl: { value: 0.15 }, uSpread: { value: 1 }, uBurst: { value: 0 }, uSize: { value: sizeBase * pixelRatio },
    };
    const points = new THREE.Points(geometry, new THREE.ShaderMaterial({
      uniforms: u,
      vertexShader: `
        attribute vec3 seed;
        uniform float uTime, uLevel, uSwirl, uSpread, uSize, uBurst;
        varying float vAlpha;
        void main(){
          float ang = uTime * uSwirl * seed.y + seed.x;
          float c = cos(ang), s = sin(ang);
          vec3 p = vec3(position.x * c - position.z * s, position.y, position.x * s + position.z * c);
          float breathe = sin(uTime * 1.3 * seed.y + seed.x) * 0.06;
          float r = seed.z * uSpread + breathe + uLevel * 0.4 * (0.4 + 0.6 * sin(seed.x * 3.0 + uTime * 5.0)) + uBurst * (0.8 + seed.y);
          vec4 mv = modelViewMatrix * vec4(p * r, 1.0);
          vAlpha = (0.25 + 0.75 * smoothstep(-3.0, 2.0, mv.z + 7.6)) * (1.0 - smoothstep(2.4, 3.6, r)) * (1.0 - uBurst * 0.4);
          gl_PointSize = uSize * (0.6 + seed.y) * (7.0 / -mv.z) * (1.0 + uBurst * 0.8);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        uniform vec3 uRim;
        varying float vAlpha;
        void main(){
          float d = length(gl_PointCoord - 0.5);
          if (d > 0.5) discard;
          gl_FragColor = vec4(uRim, (1.0 - d * 2.0) * vAlpha * 0.85);
        }`,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }));
    points.renderOrder = 4;
    return { points, u };
  }

  const halo = particleLayer(1300, (i, pos, seed) => {
    const z = Math.random() * 2 - 1;
    const a = Math.random() * Math.PI * 2;
    const r = Math.sqrt(1 - z * z);
    pos.set([r * Math.cos(a), z, r * Math.sin(a)], i * 3);
    seed.set([Math.random() * 6.283, 0.4 + Math.random() * 0.9, 1.55 + Math.pow(Math.random(), 1.8) * 0.9], i * 3);
  }, 2.1);
  world.add(halo.points);

  // A disk: unit ring in the XZ plane, spread by radius; inner parts turn faster.
  const disk = particleLayer(900, (i, pos, seed) => {
    const a = Math.random() * Math.PI * 2;
    const jitter = (Math.random() - 0.5) * 0.05;
    pos.set([Math.cos(a), jitter, Math.sin(a)], i * 3);
    const radius = 1.75 + Math.pow(Math.random(), 0.7) * 0.9;
    seed.set([Math.random() * 6.283, 1.6 / radius, radius], i * 3);
  }, 1.7);
  disk.points.rotation.set(1.18, 0, 0.32);
  world.add(disk.points);

  // Far stars, outside the group: they only move with the camera.
  const starGeometry = new THREE.BufferGeometry();
  const starPositions = new Float32Array(500 * 3);
  for (let i = 0; i < 500; i++) {
    starPositions.set([(Math.random() - 0.5) * 34, (Math.random() - 0.5) * 20, -10 - Math.random() * 14], i * 3);
  }
  starGeometry.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
  const stars = new THREE.Points(starGeometry, new THREE.PointsMaterial({ size: 0.05, transparent: true, opacity: 0.55, depthWrite: false }));
  scene.add(stars);

  // --- rings, each with a bead of light running round it ---------------------------------------------
  const rings = [
    { radius: 1.66, tilt: [1.35, 0.0, 0.25], speed: 0.9, opacity: 0.28 },
    { radius: 1.9, tilt: [0.5, 0.9, 0.0], speed: -0.6, opacity: 0.16 },
    { radius: 2.12, tilt: [2.2, -0.6, 0.4], speed: 0.45, opacity: 0.12 },
  ].map((spec) => {
    const pivot = new THREE.Group();
    pivot.rotation.set(...spec.tilt);
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(spec.radius, 0.0065, 8, 220),
      new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: spec.opacity, depthWrite: false })
    );
    pivot.add(ring);
    const bead = new THREE.Mesh(new THREE.SphereGeometry(0.035, 12, 12), new THREE.MeshBasicMaterial({ color: 0xffffff }));
    const beadGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowMap, transparent: true, depthWrite: false, opacity: 0.8, blending: THREE.AdditiveBlending }));
    beadGlow.scale.setScalar(0.34);
    bead.add(beadGlow);
    pivot.add(bead);
    world.add(pivot);
    return { ...spec, pivot, ring, bead, beadGlow, angle: Math.random() * 6.283 };
  });
  // The scanner: sweeps the sphere top to bottom while it works on a page or the screen.
  const scanner = new THREE.Mesh(
    new THREE.TorusGeometry(1.3, 0.006, 8, 200),
    new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, depthWrite: false })
  );
  scanner.rotation.x = Math.PI / 2;
  world.add(scanner);

  // --- moods ---------------------------------------------------------------------------------------
  // amp = ripple height, speed = surface motion, spin = rotation, pulse =
  // speaking beat, freq = ripple density, swirl = particle orbit speed,
  // spread = halo radius, scan = scanner, energy = core brightness, ring = ring speed.
  const PRESETS = {
    idle:      { amp: 0.07, speed: 0.35, spin: 0.10, pulse: 0, freq: 1.4, swirl: 0.15, spread: 1.0, scan: 0, energy: 0.35, ring: 1.0 },
    listening: { amp: 0.14, speed: 1.00, spin: 0.25, pulse: 0, freq: 2.0, swirl: 0.35, spread: 0.9, scan: 0, energy: 0.8, ring: 1.6 },
    thinking:  { amp: 0.11, speed: 0.80, spin: 1.10, pulse: 0, freq: 3.0, swirl: 1.40, spread: 0.86, scan: 0, energy: 1.1, ring: 3.2 },
    speaking:  { amp: 0.12, speed: 0.70, spin: 0.20, pulse: 1, freq: 1.8, swirl: 0.30, spread: 1.05, scan: 0, energy: 0.9, ring: 1.4 },
    acting:    { amp: 0.09, speed: 0.90, spin: 0.55, pulse: 0, freq: 2.4, swirl: 0.80, spread: 0.95, scan: 1, energy: 1.0, ring: 2.6 },
  };
  const current = { ...PRESETS.idle };

  function cssColor(name, fallbackColor) {
    const value = getComputedStyle(root).getPropertyValue(name).trim();
    try {
      return new THREE.Color(value || fallbackColor);
    } catch (e) {
      return new THREE.Color(fallbackColor);
    }
  }
  let rimColor = new THREE.Color("#ffffff");
  let dangerColor = new THREE.Color("#ff4d4d");
  function recolor() {
    uniforms.uCore.value = cssColor("--orb-core", "#ffffff");
    rimColor = cssColor("--orb-rim", "#ffffff");
    dangerColor = cssColor("--danger", "#ff4d4d");
    uniforms.uRim.value = rimColor.clone();
    uniforms.uGround.value = cssColor("--ground", "#000000");
    const glowColor = cssColor("--orb-glow-color", "#ffffff");
    glow.material.color = glowColor;
    coreGlow.material.color = glowColor.clone();
    stars.material.color = cssColor("--orb-rim", "#ffffff");
    // Light themes: stars and additive glows would vanish into white.
    const light = uniforms.uGround.value.getHSL({}).l > 0.5;
    stars.visible = !light;
    for (const layer of [halo, disk]) layer.points.material.blending = light ? THREE.NormalBlending : THREE.AdditiveBlending;
    core.material.blending = light ? THREE.NormalBlending : THREE.AdditiveBlending;
  }

  function resize() {
    const rect = canvas.getBoundingClientRect();
    const w = Math.max(1, rect.width);
    const h = Math.max(1, rect.height);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // Keep the whole scene in frame in a wide, short side-panel strip too.
    baseZ = w / h < 1 ? CAMERA_Z / Math.max(0.55, w / h) : CAMERA_Z;
    camera.updateProjectionMatrix();
  }
  let baseZ = CAMERA_Z;
  new ResizeObserver(resize).observe(canvas);
  resize();

  // --- the pointer ---------------------------------------------------------------------------------
  const pointer = new THREE.Vector2(0, 0);
  let pointerOver = false;
  let leanX = 0;
  let leanY = 0;
  const raycaster = new THREE.Raycaster();
  const hitSphere = new THREE.Sphere(new THREE.Vector3(0, 0, 0), 1.25);
  const hitPoint = new THREE.Vector3();

  // Where the pointer meets the orb, in the shell's own (rotating) space.
  function surfacePoint(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    pointer.set(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(pointer, camera);
    hitSphere.radius = 1.25 * shell.scale.x;
    if (!raycaster.ray.intersectSphere(hitSphere, hitPoint)) return null;
    return shell.worldToLocal(hitPoint.clone()).normalize();
  }

  window.addEventListener("pointermove", (e) => {
    leanX = (e.clientX / window.innerWidth - 0.5) * 0.8;
    leanY = (e.clientY / window.innerHeight - 0.5) * 0.6;
    const p = surfacePoint(e.clientX, e.clientY);
    pointerOver = Boolean(p);
    if (p) uniforms.uHover.value.lerp(p, 0.5).normalize();
  });
  canvas.addEventListener("pointerleave", () => (pointerOver = false));
  canvas.addEventListener("pointerdown", (e) => {
    const p = surfacePoint(e.clientX, e.clientY);
    ripple(p);
  });
  canvas.addEventListener("click", () => F.bus.emit("orb-click"));

  function ripple(at) {
    uniforms.uHit.value.copy(at || new THREE.Vector3((Math.random() - 0.5) * 0.6, (Math.random() - 0.5) * 0.6, 1).normalize());
    uniforms.uHitAge.value = 0;
    kick = Math.max(kick, 0.7);
  }

  // --- adaptive quality ------------------------------------------------------------------------------
  // School Chromebooks have modest GPUs. If frames run slow for a couple of
  // seconds, render at a lower resolution rather than stutter.
  let slowFrames = 0;
  let sampled = 0;
  function adapt(dt) {
    sampled++;
    if (dt > 0.03) slowFrames++;
    if (sampled < 120) return;
    if (slowFrames > 60 && pixelRatio > 0.75) {
      pixelRatio = Math.max(0.75, pixelRatio - 0.5);
      renderer.setPixelRatio(pixelRatio);
      halo.u.uSize.value = 2.1 * pixelRatio;
      disk.u.uSize.value = 1.7 * pixelRatio;
      resize();
    }
    sampled = 0;
    slowFrames = 0;
  }

  // --- the frame ---------------------------------------------------------------------------------------
  const clock = new THREE.Clock();
  let t = 0;
  let level = 0;
  let burst = 0;
  let busyBoost = 0;
  let hoverAmt = 0;
  let spinVelocity = 0;
  function frame() {
    const dt = Math.min(clock.getDelta(), 0.05);
    const target = PRESETS[state] || PRESETS.idle;
    const ease = Math.min(1, dt * 3);
    for (const k of Object.keys(current)) current[k] += (target[k] - current[k]) * ease;
    const motion = reduced ? 0.25 : 1;

    // The level jumps up fast and falls back slowly, like a VU meter.
    level += (levelTarget - level) * Math.min(1, dt * (levelTarget > level ? 18 : 4));
    levelTarget *= Math.pow(0.15, dt);
    burst *= Math.pow(0.08, dt);
    busyBoost *= Math.pow(0.3, dt);
    kick *= Math.pow(0.02, dt);
    hoverAmt += ((pointerOver ? 1 : 0) - hoverAmt) * Math.min(1, dt * 5);

    t += dt * current.speed * motion;
    uniforms.uTime.value = t;
    uniforms.uAmp.value = current.amp + kick * 0.2;
    uniforms.uFreq.value = current.freq;
    uniforms.uPulse.value = current.pulse;
    uniforms.uLevel.value = level * motion;
    uniforms.uHoverAmt.value = hoverAmt * motion;
    uniforms.uHitAge.value += dt;
    coreUniforms.uEnergy.value = current.energy + burst * 0.8 + busyBoost * 0.5;
    for (const layer of [halo, disk]) {
      layer.u.uSwirl.value = current.swirl * (layer === disk ? 1.4 : 1) + busyBoost * 0.6;
      layer.u.uSpread.value = current.spread + kick * 0.12;
      layer.u.uBurst.value = burst;
    }

    const flashing = performance.now() < flashUntil;
    uniforms.uRim.value.lerp(flashing ? dangerColor : rimColor, Math.min(1, dt * 8));

    // The orb turns on its own, leans to the pointer, and swells with sound.
    spinVelocity *= Math.pow(0.4, dt);
    shell.rotation.y += dt * (current.spin + spinVelocity) * motion;
    shell.rotation.x += (leanY * 0.6 - shell.rotation.x) * dt * 2;
    shell.rotation.z += (-leanX * 0.3 - shell.rotation.z) * dt * 2;
    shell.scale.setScalar(1 + kick * 0.05 + level * 0.05);
    core.rotation.y -= dt * (0.4 + current.energy) * motion;
    core.scale.setScalar(1 + level * 0.25 + burst * 0.2 + 0.03 * Math.sin(t * 3.0));
    coreGlow.material.opacity = (0.28 + current.energy * 0.25 + level * 0.4 + burst * 0.4) * (stars.visible ? 1 : 0.35);
    coreGlow.scale.setScalar(1.7 + level * 0.8 + burst * 0.8);
    glow.material.opacity = 0.2 + level * 0.3 + current.pulse * 0.06 + burst * 0.15;
    glow.scale.setScalar(5.4 + level * 1.2 + burst);
    halo.points.rotation.x = shell.rotation.x * 0.5;
    disk.points.rotation.z = 0.32 + Math.sin(t * 0.2) * 0.05;

    for (const r of rings) {
      r.angle += dt * r.speed * (current.ring + busyBoost * 2) * motion;
      r.bead.position.set(Math.cos(r.angle) * r.radius, Math.sin(r.angle) * r.radius, 0);
      r.pivot.rotation.z += dt * r.speed * 0.08 * motion;
      r.ring.material.color.copy(uniforms.uRim.value);
      r.bead.material.color.copy(uniforms.uRim.value);
      r.beadGlow.material.color.copy(uniforms.uRim.value);
      r.ring.material.opacity = r.opacity * (1 + busyBoost * 1.5 + level);
    }

    const y = Math.sin(performance.now() / 700) * 1.05;
    scanner.position.y = y;
    scanner.scale.setScalar(Math.sqrt(Math.max(0.02, 1.35 * 1.35 - y * y)) / 1.3);
    scanner.material.opacity = 0.55 * current.scan;
    scanner.material.color.copy(uniforms.uRim.value);

    // Depth: the camera drifts with the pointer, so near and far move differently.
    camera.position.x += (leanX * 1.1 - camera.position.x) * dt * 1.6;
    camera.position.y += (-leanY * 0.8 - camera.position.y) * dt * 1.6;
    camera.position.z = baseZ;
    camera.lookAt(0, 0, 0);

    renderer.render(scene, camera);
    adapt(dt);
    requestAnimationFrame(frame);
  }

  recolor();
  F.bus.on("theme", recolor);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", recolor);
  requestAnimationFrame(frame);

  F.orb = {
    webgl: true,
    setState(s) {
      state = PRESETS[s] ? s : "idle";
      if (fallback) fallback.dataset.state = state;
    },
    // 0..1, from the mic or from speech. Decays on its own.
    setLevel(v) {
      levelTarget = Math.max(levelTarget, Math.min(1, Math.max(0, v)));
    },
    kick() {
      kick = 1;
    },
    flash() {
      flashUntil = performance.now() + 900;
      kick = 0.6;
    },
    // A shockwave from a point on the surface (or somewhere on the front).
    ripple,
    // Particles thrown outwards: an answer has arrived.
    burst() {
      burst = 1;
      kick = Math.max(kick, 0.5);
      spinVelocity += 1.2;
    },
    // A keystroke: a small tap.
    tap() {
      kick = Math.max(kick, 0.35);
      spinVelocity += 0.15;
      if (Math.random() < 0.3) ripple(null);
    },
    // A tool is running: rings and particles speed up for a moment.
    busy() {
      busyBoost = 1;
    },
    recolor,
  };
})();
