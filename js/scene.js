// The phone app's 3D scene: the Fable One orb, built to run smoothly on a
// phone GPU (the owner's is a Moto G15 Power, Mali-G52 class).
//
//   orb     a glass sphere rippled by noise, with contour lines riding the
//           ripples and normals taken from the rippled surface, so it shades
//           like real glass; a glowing heart inside
//   halo    a shell of particles breathing round it, and a tilted disk
//   rings   three thin orbits, each with a bead of light running round it
//   stars   a far starfield; the view drifts with the phone's tilt
//
// What keeps it smooth on a phone:
//   - it draws only as often as it needs to: 30 frames a second at rest, the
//     full rate only while something moves, 20 while typing, none while a
//     sheet covers it (full detail at 60 a second, always, was "very laggy"
//     on the owner's Moto G15 Power)
//   - the detail is picked on the phone itself: Graphics > Auto starts at a
//     step that suits the GPU and steps down while frames are being missed,
//     never so far that it looks blocky (see TIERS)
//   - the canvas is opaque, so it isn't one more full-screen layer to blend
//   - the sphere is an indexed mesh, so each point on it is shaded once
//   - nothing is allocated per frame, so the garbage collector never stalls it
//   - the tilt is smoothed, so sensor jitter can't shake the picture
//   - the canvas doesn't resize while the keyboard slides in and out
//
// It keeps F.orb's interface (setState, setLevel, burst, tap, flash, busy,
// ripple, send, pulse), adds typing, cover, setGraphics and graphicsInfo,
// and emits scene-hold-start / scene-hold-end / scene-tap for the page to
// turn into listening.
(() => {
  const F = window.Fable;
  const root = document.documentElement;
  const canvas = document.getElementById("orb");
  const fallback = document.getElementById("orb-fallback");
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const noop = () => {};

  function useFallback() {
    if (canvas) canvas.hidden = true;
    if (fallback) fallback.hidden = false;
    F.orb = { webgl: false, setState: (s) => fallback && (fallback.dataset.state = s), setLevel: noop, kick: noop, flash: noop, ripple: noop, burst: noop, tap: noop, busy: noop, send: noop, pulse: noop, recolor: noop, typing: noop, cover: noop, setGraphics: noop, graphicsInfo: () => null };
  }
  if (!canvas || !window.THREE) return useFallback();

  let renderer;
  try {
    // Opaque: nothing behind the scene ever shows through it, and a
    // see-through canvas is one more full-screen layer to blend every frame.
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: "high-performance" });
  } catch (e) {
    return useFallback();
  }

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
  const world = new THREE.Group();
  scene.add(world);

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

  const U = {
    uTime: { value: 0 },
    uAmp: { value: 0.08 },
    uFreq: { value: 1.4 },
    uPulse: { value: 0 },
    uLevel: { value: 0 },
    uCore: { value: new THREE.Color("#ffffff") },
    uRim: { value: new THREE.Color("#ffffff") },
    uGround: { value: new THREE.Color("#000000") },
    uHit: { value: new THREE.Vector3(0, 0, 1) },
    uHitAge: { value: 10 },
  };

  // --- the orb ----------------------------------------------------------------------------------------
  const orb = new THREE.Group();
  world.add(orb);

  const shell = new THREE.Mesh(
    // Indexed: every point is shaded once, not once per triangle it belongs to.
    new THREE.SphereGeometry(1, 120, 90),
    new THREE.ShaderMaterial({
      uniforms: U,
      vertexShader: NOISE + `
        uniform float uTime, uAmp, uFreq, uPulse, uLevel, uHitAge;
        uniform vec3 uHit;
        varying vec3 vNormal; varying vec3 vView; varying float vDisp;
        float displace(vec3 n){
          float a = snoise(n * uFreq + vec3(0.0, uTime * 0.6, uTime * 0.3));
          float b = snoise(n * uFreq * 2.3 - uTime * 0.4) * 0.35;
          float d = (a + b) * (uAmp + uLevel * 0.22) + uPulse * (0.5 + 0.5 * sin(uTime * 7.0)) * 0.05 + uLevel * 0.05;
          float k = distance(n, uHit);
          d += 0.15 * exp(-uHitAge * 2.6) * sin(k * 22.0 - uHitAge * 16.0) * exp(-k * 2.2) * step(k, uHitAge * 1.4 + 0.2);
          return d;
        }
        void main(){
          vec3 n = normalize(position);
          float d = displace(n);
          vec3 p = n * (1.2 + d);
          vec3 t = normalize(abs(n.y) > 0.99 ? cross(n, vec3(1.0, 0.0, 0.0)) : cross(n, vec3(0.0, 1.0, 0.0)));
          vec3 b = cross(n, t);
          vec3 n1 = normalize(n + t * 0.012);
          vec3 n2 = normalize(n + b * 0.012);
          vec3 bent = normalize(cross(n1 * (1.2 + displace(n1)) - p, n2 * (1.2 + displace(n2)) - p));
          if (dot(bent, n) < 0.0) bent = -bent;
          vDisp = d;
          vec4 mv = modelViewMatrix * vec4(p, 1.0);
          vNormal = normalize(normalMatrix * bent);
          vView = normalize(-mv.xyz);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        uniform vec3 uCore, uRim, uGround; uniform float uTime, uLevel;
        varying vec3 vNormal; varying vec3 vView; varying float vDisp;
        void main(){
          vec3 N = normalize(vNormal);
          vec3 V = normalize(vView);
          vec3 key = normalize(vec3(-0.5, 0.7, 0.6));
          float fres = pow(1.0 - max(dot(N, V), 0.0), 2.3);
          float diff = max(dot(N, key), 0.0) * 0.55;
          float spec = pow(max(dot(N, normalize(key + V)), 0.0), 60.0) * 1.1;
          float env = smoothstep(-0.1, 0.9, reflect(-V, N).y) * 0.3;
          vec3 body = mix(uGround, uCore, 0.04 + diff * 0.5 + vDisp * 0.9);
          float band = abs(fract(vDisp * 16.0 - uTime * 0.25) - 0.5);
          float line = (1.0 - smoothstep(0.0, 0.05, band)) * (0.22 + 0.55 * uLevel);
          vec3 col = body + uRim * (env * 0.6 + spec);
          col = mix(col, uRim, clamp(fres * 1.05 + line, 0.0, 1.0));
          gl_FragColor = vec4(col, clamp(0.55 + fres * 0.6 + spec * 0.5 + line * 0.4, 0.0, 1.0));
        }`,
      transparent: true,
      depthWrite: false,
    })
  );
  shell.renderOrder = 3;
  orb.add(shell);

  const coreU = { uTime: U.uTime, uLevel: U.uLevel, uRim: U.uRim, uCore: U.uCore, uEnergy: { value: 0.4 } };
  const core = new THREE.Mesh(
    new THREE.SphereGeometry(0.52, 32, 24),
    new THREE.ShaderMaterial({
      uniforms: coreU,
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
  orb.add(core);

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
  const sprite = (size, opacity, additive) => {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowMap, transparent: true, depthWrite: false, opacity, blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending }));
    s.scale.setScalar(size);
    return s;
  };
  const glow = sprite(4.4, 0.28, false);
  glow.position.z = -0.8;
  glow.renderOrder = 0;
  orb.add(glow);
  const heart = sprite(1.8, 0.5, true);
  heart.renderOrder = 2;
  orb.add(heart);

  // --- particles: a breathing halo and a tilted disk -------------------------------------------------------
  function particles(count, place, sizeBase) {
    const positions = new Float32Array(count * 3);
    const seeds = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) place(i, positions, seeds);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("seed", new THREE.BufferAttribute(seeds, 3));
    const u = { uTime: U.uTime, uLevel: U.uLevel, uRim: U.uRim, uSwirl: { value: 0.15 }, uSpread: { value: 1 }, uBurst: { value: 0 }, uSize: { value: sizeBase } };
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
          float r = seed.z * uSpread + sin(uTime * 1.3 * seed.y + seed.x) * 0.06 + uLevel * 0.4 * (0.4 + 0.6 * sin(seed.x * 3.0 + uTime * 5.0)) + uBurst * (0.8 + seed.y);
          vec4 mv = modelViewMatrix * vec4(p * r, 1.0);
          vAlpha = (0.3 + 0.7 * smoothstep(-3.0, 2.0, p.z * r)) * (1.0 - smoothstep(2.4, 3.6, r)) * (1.0 - uBurst * 0.4);
          gl_PointSize = uSize * (0.6 + seed.y) * (7.0 / -mv.z) * (1.0 + uBurst * 0.8);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        uniform vec3 uRim;
        varying float vAlpha;
        void main(){
          vec2 d = gl_PointCoord - 0.5;
          float r2 = dot(d, d);
          if (r2 > 0.25) discard;
          gl_FragColor = vec4(uRim, (1.0 - sqrt(r2) * 2.0) * vAlpha * 0.85);
        }`,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }));
    points.renderOrder = 4;
    return { points, u, count };
  }
  const halo = particles(800, (i, pos, seed) => {
    const z = Math.random() * 2 - 1;
    const a = Math.random() * Math.PI * 2;
    const r = Math.sqrt(1 - z * z);
    pos.set([r * Math.cos(a), z, r * Math.sin(a)], i * 3);
    seed.set([Math.random() * 6.283, 0.4 + Math.random() * 0.9, 1.55 + Math.pow(Math.random(), 1.8) * 0.9], i * 3);
  }, 2.3);
  world.add(halo.points);
  const disk = particles(560, (i, pos, seed) => {
    const a = Math.random() * Math.PI * 2;
    pos.set([Math.cos(a), (Math.random() - 0.5) * 0.05, Math.sin(a)], i * 3);
    const radius = 1.75 + Math.pow(Math.random(), 0.7) * 0.9;
    seed.set([Math.random() * 6.283, 1.6 / radius, radius], i * 3);
  }, 1.9);
  disk.points.rotation.set(1.18, 0, 0.32);
  world.add(disk.points);

  const starGeometry = new THREE.BufferGeometry();
  const starPositions = new Float32Array(320 * 3);
  for (let i = 0; i < 320; i++) starPositions.set([(Math.random() - 0.5) * 30, (Math.random() - 0.5) * 34, -10 - Math.random() * 14], i * 3);
  starGeometry.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
  const stars = new THREE.Points(starGeometry, new THREE.PointsMaterial({ size: 0.06, transparent: true, opacity: 0.6, depthWrite: false }));
  scene.add(stars);

  // --- rings, each with a bead of light ------------------------------------------------------------------------------
  const rings = [
    { radius: 1.66, tilt: [1.35, 0.0, 0.25], speed: 0.9, opacity: 0.32 },
    { radius: 1.9, tilt: [0.5, 0.9, 0.0], speed: -0.6, opacity: 0.2 },
    { radius: 2.12, tilt: [2.2, -0.6, 0.4], speed: 0.45, opacity: 0.14 },
  ].map((spec) => {
    const pivot = new THREE.Group();
    pivot.rotation.set(spec.tilt[0], spec.tilt[1], spec.tilt[2]);
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(spec.radius, 0.009, 6, 200),
      new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: spec.opacity, depthWrite: false })
    );
    pivot.add(ring);
    const bead = new THREE.Mesh(new THREE.SphereGeometry(0.04, 12, 10), new THREE.MeshBasicMaterial({ color: 0xffffff }));
    const beadGlow = sprite(0.38, 0.8, true);
    bead.add(beadGlow);
    pivot.add(bead);
    world.add(pivot);
    return { ...spec, pivot, ring, bead, beadGlow, angle: Math.random() * 6.283 };
  });

  // --- the spark that carries a message into the orb --------------------------------------------------------------------
  const spark = sprite(0.5, 0, true);
  spark.renderOrder = 5;
  world.add(spark);
  const sparkFrom = new THREE.Vector3();
  const sparkMid = new THREE.Vector3();
  let sparkT = 1;

  // --- moods --------------------------------------------------------------------------------------------------------------
  const PRESETS = {
    idle:      { amp: 0.07, speed: 0.35, spin: 0.10, pulse: 0, freq: 1.4, swirl: 0.15, spread: 1.0, energy: 0.35, ring: 1.0 },
    listening: { amp: 0.14, speed: 1.00, spin: 0.25, pulse: 0, freq: 2.0, swirl: 0.35, spread: 0.9, energy: 0.8, ring: 1.6 },
    thinking:  { amp: 0.11, speed: 0.80, spin: 1.10, pulse: 0, freq: 3.0, swirl: 1.40, spread: 0.86, energy: 1.1, ring: 3.2 },
    speaking:  { amp: 0.12, speed: 0.70, spin: 0.20, pulse: 1, freq: 1.8, swirl: 0.30, spread: 1.05, energy: 0.9, ring: 1.4 },
  };
  let state = "idle";
  const cur = { ...PRESETS.idle };
  let levelTarget = 0;
  let level = 0;
  let kick = 0;
  let burst = 0;
  let busy = 0;
  let flashUntil = 0;
  let spinVelocity = 0;

  function cssColor(name, fallbackColor) {
    const value = getComputedStyle(root).getPropertyValue(name).trim();
    try {
      return new THREE.Color(value || fallbackColor);
    } catch (e) {
      return new THREE.Color(fallbackColor);
    }
  }
  let rimColor = new THREE.Color("#ffffff");
  let danger = new THREE.Color("#ff5a52");
  function recolor() {
    U.uCore.value = cssColor("--orb-core", "#ffffff");
    rimColor = cssColor("--orb-rim", "#ffffff");
    danger = cssColor("--danger", "#ff5a52");
    U.uRim.value = rimColor.clone();
    U.uGround.value = cssColor("--ground", "#000000");
    renderer.setClearColor(U.uGround.value, 1);
    const glowColor = cssColor("--orb-glow-color", "#ffffff");
    glow.material.color = glowColor;
    heart.material.color = glowColor.clone();
    stars.material.color = rimColor.clone();
    const light = U.uGround.value.getHSL({}).l > 0.5;
    stars.visible = !light;
    const blend = light ? THREE.NormalBlending : THREE.AdditiveBlending;
    halo.points.material.blending = disk.points.material.blending = core.material.blending = blend;
  }

  // --- size: portrait-aware, and steady while the keyboard moves ------------------------------------------------------------
  let distance = 7.6;
  let lookDown = 0;
  function resize() {
    const w = Math.max(1, canvas.clientWidth);
    const h = Math.max(1, canvas.clientHeight);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    const portrait = w / h < 1;
    camera.fov = portrait ? 48 : 38;
    camera.updateProjectionMatrix();
    // Fit the outer ring to the width, and lift the orb above the card and chat box.
    const halfWidth = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.aspect;
    distance = THREE.MathUtils.clamp(2.3 / halfWidth, 6.5, 13);
    lookDown = portrait ? 1.15 : 0;
  }
  let resizeTimer = 0;
  new ResizeObserver(() => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(resize, 150);
  }).observe(canvas);
  resize();

  // --- the phone in the hand: tilt, drag, hold ---------------------------------------------------------------------------------
  const tilt = { x: 0, y: 0, tx: 0, ty: 0 };
  let tiltBase = null;
  window.addEventListener("deviceorientation", (e) => {
    if (e.beta === null || e.gamma === null) return;
    if (!tiltBase) tiltBase = { beta: e.beta, gamma: e.gamma };
    tiltBase.beta += (e.beta - tiltBase.beta) * 0.004; // re-centre slowly on how it's held
    tiltBase.gamma += (e.gamma - tiltBase.gamma) * 0.004;
    tilt.tx = THREE.MathUtils.clamp((e.gamma - tiltBase.gamma) / 35, -1, 1);
    tilt.ty = THREE.MathUtils.clamp((e.beta - tiltBase.beta) / 35, -1, 1);
  });

  const drag = { yaw: 0, pitch: 0 };
  let pointer = null;
  const raycaster = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  const hitSphere = new THREE.Sphere(new THREE.Vector3(), 1.25);
  const hitPoint = new THREE.Vector3();

  function hitOrb(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    ndc.set(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(ndc, camera);
    hitSphere.center.setFromMatrixPosition(shell.matrixWorld);
    hitSphere.radius = 1.3 * shell.scale.x;
    if (!raycaster.ray.intersectSphere(hitSphere, hitPoint)) return null;
    return shell.worldToLocal(hitPoint.clone()).normalize();
  }

  canvas.addEventListener("pointerdown", (e) => {
    try {
      canvas.setPointerCapture(e.pointerId);
    } catch (_) {}
    const onOrb = hitOrb(e.clientX, e.clientY);
    pointer = { id: e.pointerId, x: e.clientX, y: e.clientY, lastX: e.clientX, lastY: e.clientY, moved: false, held: false, onOrb };
    wake();
    if (onOrb) {
      ripple(onOrb);
      // Holding the orb means "listen"; a drag cancels it.
      pointer.timer = setTimeout(() => {
        if (!pointer || pointer.moved) return;
        pointer.held = true;
        F.bus.emit("scene-hold-start");
      }, 260);
    }
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!pointer || e.pointerId !== pointer.id) return;
    if (!pointer.moved && !pointer.held && Math.hypot(e.clientX - pointer.x, e.clientY - pointer.y) > 12) {
      pointer.moved = true;
      clearTimeout(pointer.timer);
    }
    if (pointer.moved) {
      drag.yaw += (e.clientX - pointer.lastX) * 0.006;
      drag.pitch = THREE.MathUtils.clamp(drag.pitch + (e.clientY - pointer.lastY) * 0.004, -0.45, 0.45);
      spinVelocity += (e.clientX - pointer.lastX) * 0.01;
      wake();
    }
    pointer.lastX = e.clientX;
    pointer.lastY = e.clientY;
  });
  const release = (e) => {
    if (!pointer || (e && e.pointerId !== pointer.id)) return;
    clearTimeout(pointer.timer);
    if (pointer.held) F.bus.emit("scene-hold-end");
    else if (!pointer.moved && pointer.onOrb) F.bus.emit("scene-tap");
    pointer = null;
  };
  canvas.addEventListener("pointerup", release);
  canvas.addEventListener("pointercancel", release);

  function ripple(at) {
    if (at) U.uHit.value.copy(at);
    else U.uHit.value.set((Math.random() - 0.5) * 0.6, (Math.random() - 0.5) * 0.6, 1).normalize();
    U.uHitAge.value = 0;
    kick = Math.max(kick, 0.7);
  }

  function send() {
    // From just above the thumb to the orb, on a curve.
    sparkFrom.set(0, -0.95, 0.4).unproject(camera);
    sparkFrom.sub(camera.position).normalize().multiplyScalar(distance * 0.5).add(camera.position);
    sparkMid.copy(sparkFrom).lerp(orb.position, 0.5);
    sparkMid.x += (Math.random() - 0.5) * 1.4;
    sparkMid.y += 1.1;
    sparkT = 0;
  }

  // --- pace: missed frames ---------------------------------------------------------------------------------------------------------
  // A frame that arrives a refresh or more after it was due was missed: the
  // phone couldn't keep up. Stretches around loading, a sheet or the keyboard
  // moving aren't counted - those stutter on any phone and say nothing about
  // the scene.
  let refresh = 1000 / 60; // measured from the first 40 back-to-back frames
  const firstGaps = [];
  let lastTick = 0;
  let frames = 0;
  let late = 0;
  let missed = 0;
  let windowStart = 0;
  let settleUntil = performance.now() + 2500;
  let typing = false;
  let covered = false;
  let drawn = 0;
  let drawnSince = performance.now();
  let fpsNow = 0;

  function watch(gap, interval, now) {
    if (now < settleUntil || firstGaps.length < 40) {
      frames = late = 0;
      windowStart = now;
      return;
    }
    frames++;
    if (gap > interval + refresh * 0.7) late++;
    if (now - windowStart < 2000) return;
    missed = late / frames;
    // Auto steps down, never back up: stepping up again would just oscillate.
    if (mode === "auto" && frames >= 20 && missed > 0.15 && tier < TIERS.length - 1) setTier(tier + 1);
    frames = late = 0;
    windowStart = now;
  }

  // Is anything moving that deserves the full frame rate?
  function moving(now) {
    return state !== "idle" || pointer !== null || sparkT < 1 || now < flashUntil
      || kick > 0.05 || burst > 0.05 || busy > 0.05 || level > 0.03 || Math.abs(spinVelocity) > 0.05;
  }

  // --- how much to draw: four steps, all the same look --------------------------------------------------------------------------
  //   ratio  canvas pixels per screen point (a phone screen has about 2.6)
  //   parts  share of the halo and disk particles drawn
  //   mesh   the orb's surface detail
  //   fps    frames a second while something moves; rest, while it idles
  // Nothing goes below 1 pixel per point, which is where it starts to look
  // blocky, and the mesh stays fine enough for the ripples: at 56 x 42 the
  // orb's outline went lumpy.
  const TIERS = [
    { name: "full", ratio: 1.6, parts: 1, mesh: [120, 90], fps: 60, rest: 30 },
    { name: "high", ratio: 1.4, parts: 0.7, mesh: [108, 81], fps: 60, rest: 30 },
    { name: "light", ratio: 1.25, parts: 0.55, mesh: [96, 72], fps: 30, rest: 30 },
    { name: "lightest", ratio: 1.05, parts: 0.4, mesh: [84, 63], fps: 30, rest: 20 },
  ];
  // Phone GPUs well below a flagship's (the owner's Mali-G52 MC2 among them): Auto starts on "light".
  const WEAK_GPU = /Mali-(?:4|T|G31|G51|G52|G57)|Adreno\D*(?:[1-5]\d\d|6[01]\d)\b|PowerVR|SwiftShader|llvmpipe|Software/i;
  const FIXED = { full: 0, light: TIERS.length - 1 };
  let mode = "auto";
  let tier = 0;
  let T = TIERS[0];

  const gpu = (() => {
    try {
      const gl = renderer.getContext();
      const info = gl.getExtension("WEBGL_debug_renderer_info");
      return String(gl.getParameter(info ? info.UNMASKED_RENDERER_WEBGL : gl.RENDERER) || "");
    } catch (e) {
      return "";
    }
  })();

  function autoTier() {
    if (WEAK_GPU.test(gpu)) return 2;
    const phone = window.matchMedia("(pointer: coarse)").matches && Math.min(screen.width, screen.height) < 700;
    return phone ? 1 : 0;
  }

  function setTier(n) {
    tier = Math.max(0, Math.min(TIERS.length - 1, n));
    T = TIERS[tier];
    const ratio = Math.min(window.devicePixelRatio || 1, T.ratio);
    renderer.setPixelRatio(ratio);
    halo.u.uSize.value = 2.3 * ratio;
    disk.u.uSize.value = 1.9 * ratio;
    halo.points.geometry.setDrawRange(0, Math.round(halo.count * T.parts));
    disk.points.geometry.setDrawRange(0, Math.round(disk.count * T.parts));
    if (shell.geometry.parameters.widthSegments !== T.mesh[0]) {
      shell.geometry.dispose();
      shell.geometry = new THREE.SphereGeometry(1, T.mesh[0], T.mesh[1]);
    }
    root.dataset.gfx = T.name;
    resize();
    settleUntil = performance.now() + 1500;
  }

  function setMode(m) {
    mode = m in FIXED ? m : "auto";
    setTier(mode === "auto" ? autoTier() : FIXED[mode]);
  }
  setMode("auto");

  // --- the frame -----------------------------------------------------------------------------------------------------------------
  // A frame is asked for only when one is due: an animation frame the scene
  // doesn't draw still costs the phone a round of style, layout and
  // compositing checks. Anything that starts moving wakes it at once.
  const clock = new THREE.Clock();
  let t = 0;
  let paused = false;
  let lastDraw = 0;
  let lastCap = 0;
  let asked = false;
  let sleeper = 0;

  function ask() {
    if (asked || paused || covered) return;
    asked = true;
    requestAnimationFrame(frame);
  }
  function wake() {
    clearTimeout(sleeper);
    sleeper = 0;
    ask();
  }
  // Ask a little under a refresh before the frame is due; it's drawn on the refresh after.
  function sleepUntil(due) {
    clearTimeout(sleeper);
    const wait = due - performance.now() - refresh * 0.75;
    if (wait <= 1 || firstGaps.length < 40) {
      sleeper = 0;
      ask();
    } else {
      sleeper = setTimeout(() => {
        sleeper = 0;
        ask();
      }, wait);
    }
  }
  document.addEventListener("visibilitychange", () => {
    paused = document.hidden;
    if (!paused) {
      clock.getDelta();
      settleUntil = performance.now() + 1500;
      wake();
    }
  });

  function frame(now) {
    asked = false;
    if (paused || covered) return;
    if (firstGaps.length < 40) {
      // The screen's refresh: a low-but-not-lowest gap, so one odd short one can't skew it.
      const gap = now - lastTick;
      if (lastTick && gap > 3 && gap < 100) firstGaps.push(gap);
      if (firstGaps.length === 40) refresh = firstGaps.slice().sort((a, b) => a - b)[10];
      lastTick = now;
    }
    const cap = typing ? Math.min(20, T.rest) : moving(now) ? T.fps : T.rest;
    const interval = 1000 / cap;
    const since = now - lastDraw;
    if (since < interval - 4) {
      // Woken early, or the screen refreshes faster than the cap.
      sleepUntil(lastDraw + interval);
      return;
    }
    if (cap === lastCap) watch(since, interval, now);
    lastCap = cap;
    lastDraw = now;
    sleepUntil(now + interval);
    drawn++;
    if (now - drawnSince >= 1000) {
      fpsNow = Math.round((drawn * 1000) / (now - drawnSince));
      drawn = 0;
      drawnSince = now;
    }
    const dt = Math.min(clock.getDelta(), 0.1);
    const target = PRESETS[state] || PRESETS.idle;
    const ease = Math.min(1, dt * 3);
    for (const k in cur) cur[k] += (target[k] - cur[k]) * ease;
    const motion = reduced ? 0.25 : 1;

    level += (levelTarget - level) * Math.min(1, dt * (levelTarget > level ? 16 : 4));
    levelTarget *= Math.pow(0.15, dt);
    kick *= Math.pow(0.02, dt);
    burst *= Math.pow(0.08, dt);
    busy *= Math.pow(0.3, dt);
    spinVelocity *= Math.pow(0.35, dt);

    t += dt * cur.speed * motion;
    U.uTime.value = t;
    U.uAmp.value = cur.amp + kick * 0.2;
    U.uFreq.value = cur.freq;
    U.uPulse.value = cur.pulse;
    U.uLevel.value = level * motion;
    U.uHitAge.value += dt;
    coreU.uEnergy.value = cur.energy + burst * 0.8 + busy * 0.5;
    for (const layer of [halo, disk]) {
      layer.u.uSwirl.value = cur.swirl * (layer === disk ? 1.4 : 1) + busy * 0.6;
      layer.u.uSpread.value = cur.spread + kick * 0.12;
      layer.u.uBurst.value = burst;
    }
    U.uRim.value.lerp(performance.now() < flashUntil ? danger : rimColor, Math.min(1, dt * 8));

    orb.position.y = Math.sin(t * 0.9) * 0.05;
    shell.rotation.y += dt * (cur.spin + spinVelocity) * motion;
    orb.scale.setScalar(1 + kick * 0.05 + level * 0.05);
    core.rotation.y -= dt * (0.4 + cur.energy) * motion;
    core.scale.setScalar(1 + level * 0.25 + burst * 0.2 + 0.03 * Math.sin(t * 3.0));
    heart.material.opacity = (0.28 + cur.energy * 0.25 + level * 0.4 + burst * 0.4) * (stars.visible ? 1 : 0.35);
    heart.scale.setScalar(1.7 + level * 0.8 + burst * 0.8);
    glow.material.opacity = 0.2 + level * 0.3 + cur.pulse * 0.06 + burst * 0.15;
    glow.scale.setScalar(4.4 + level + burst * 0.8);
    halo.points.rotation.x = shell.rotation.x * 0.5;
    disk.points.rotation.z = 0.32 + Math.sin(t * 0.2) * 0.05;

    for (const r of rings) {
      r.angle += dt * r.speed * (cur.ring + busy * 2) * motion;
      r.bead.position.set(Math.cos(r.angle) * r.radius, Math.sin(r.angle) * r.radius, 0);
      r.pivot.rotation.z += dt * r.speed * 0.08 * motion;
      r.ring.material.color.copy(U.uRim.value);
      r.bead.material.color.copy(U.uRim.value);
      r.beadGlow.material.color.copy(U.uRim.value);
      r.ring.material.opacity = r.opacity * (1 + busy * 1.5 + level);
    }

    if (sparkT < 1) {
      sparkT = Math.min(1, sparkT + dt * 1.6);
      const a = sparkT;
      spark.position.set(0, 0, 0)
        .addScaledVector(sparkFrom, (1 - a) * (1 - a))
        .addScaledVector(sparkMid, 2 * (1 - a) * a)
        .addScaledVector(orb.position, a * a);
      spark.material.opacity = Math.sin(a * Math.PI);
      spark.scale.setScalar(0.5 - a * 0.25);
      if (sparkT >= 1) {
        spark.material.opacity = 0;
        ripple(null);
        kick = 1;
      }
    }

    // The view: tilt shifts it (smoothed), dragging spins it and it eases back.
    tilt.x += (tilt.tx - tilt.x) * Math.min(1, dt * 4);
    tilt.y += (tilt.ty - tilt.y) * Math.min(1, dt * 4);
    drag.yaw *= Math.pow(0.4, dt);
    drag.pitch *= Math.pow(0.4, dt);
    const yaw = drag.yaw + tilt.x * 0.3 * motion;
    const pitch = 0.05 + drag.pitch + tilt.y * 0.18 * motion;
    camera.position.set(Math.sin(yaw) * Math.cos(pitch) * distance, Math.sin(pitch) * distance, Math.cos(yaw) * Math.cos(pitch) * distance);
    camera.lookAt(0, -lookDown, 0);
    stars.position.set(-tilt.x * 0.6, tilt.y * 0.4, 0);

    renderer.render(scene, camera);
  }

  recolor();
  F.bus.on("theme", () => {
    recolor();
    wake();
  });
  wake();

  // Every change of mood wakes the scene, so it answers at once rather than on its next slow frame.
  const waking = (fn) => (...args) => {
    const result = fn(...args);
    wake();
    return result;
  };
  F.orb = {
    webgl: true,
    setState: waking((s) => {
      state = PRESETS[s] ? s : s === "acting" ? "thinking" : "idle";
    }),
    setLevel: waking((v) => {
      levelTarget = Math.max(levelTarget, Math.min(1, Math.max(0, v)));
    }),
    kick: waking(() => {
      kick = 1;
    }),
    flash: waking(() => {
      flashUntil = performance.now() + 900;
      kick = 0.6;
    }),
    ripple: waking(ripple),
    burst: waking(() => {
      burst = 1;
      kick = Math.max(kick, 0.5);
      spinVelocity += 1.2;
    }),
    tap: waking(() => {
      kick = Math.max(kick, 0.3);
      spinVelocity += 0.12;
    }),
    busy: waking(() => {
      busy = 1;
    }),
    send: waking(send),
    pulse: waking(() => {
      burst = Math.max(burst, 0.6);
    }),
    recolor,
    // The keyboard is up: fewer frames, so typing stays quick.
    typing: waking((on) => {
      typing = Boolean(on);
      settleUntil = performance.now() + 1200;
    }),
    // A sheet covers the scene: stop drawing it until it's gone.
    cover: waking((on) => {
      covered = Boolean(on);
      settleUntil = performance.now() + 1200;
    }),
    // "auto", "full" or "light" (Graphics in the menu).
    setGraphics: setMode,
    graphicsInfo() {
      return { mode, tier: T.name, fps: fpsNow, missed: Math.round(missed * 100), gpu };
    },
  };
})();
