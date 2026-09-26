// The phone app's 3D scene: Fable One as a small machine you hold.
//
//   core        a rippling glass orb with a glowing heart
//   gyroscope   three metal rings turning on different axes, studded with
//               machined notches, reflecting a soft studio light
//   satellites  faceted crystals on tilted orbits, each with a faint path
//   floor       a grid far below that glows under the orb and sends out a
//               ring whenever an answer arrives
//   dust        motes drifting upward through the light
//   flyers      a spark that carries each message from your thumb into the orb
//
// Made for a phone: tilting it shifts the view (gyro), dragging spins it,
// holding the orb means "listening" (the page decides), and it renders at a
// lower resolution on its own if the GPU can't keep up.
//
// It keeps F.orb's interface (setState, setLevel, burst, tap, flash, busy,
// ripple) so the chat code drives it the same way, and adds send() and pulse().
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
    F.orb = { webgl: false, setState: (s) => fallback && (fallback.dataset.state = s), setLevel: noop, kick: noop, flash: noop, ripple: noop, burst: noop, tap: noop, busy: noop, send: noop, pulse: noop, recolor: noop };
  }
  if (!canvas || !window.THREE) return useFallback();

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
  } catch (e) {
    return useFallback();
  }
  let pixelRatio = Math.min(window.devicePixelRatio || 1, 1.75);
  renderer.setPixelRatio(pixelRatio);
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
  const TARGET = new THREE.Vector3(0, 0.25, 0);

  // --- a soft studio for the metal to reflect ------------------------------------------
  function studio(tint) {
    const env = new THREE.Scene();
    const geo = new THREE.SphereGeometry(10, 32, 16);
    const colors = [];
    const pos = geo.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const y = pos.getY(i) / 10;
      const v = 0.02 + Math.max(0, y) * 0.22 + Math.exp(-Math.pow((y - 0.35) * 5, 2)) * 0.5;
      colors.push(v * tint.r, v * tint.g, v * tint.b);
    }
    geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    env.add(new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide })));
    // Two softboxes: a key from above-left and a strip light to the right.
    const box = (w, h, x, y, z, s) => {
      const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color(s, s, s) }));
      m.position.set(x, y, z);
      m.lookAt(0, 0, 0);
      env.add(m);
    };
    box(6, 3, -4, 7, 3, 3.2);
    box(1.2, 7, 7, 1, -2, 2.2);
    box(8, 1, 0, -3, -8, 0.8);
    const pmrem = new THREE.PMREMGenerator(renderer);
    const texture = pmrem.fromScene(env, 0.04).texture;
    pmrem.dispose();
    return texture;
  }

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
    uFreq: { value: 1.5 },
    uLevel: { value: 0 },
    uPulse: { value: 0 },
    uRim: { value: new THREE.Color("#ffffff") },
    uCore: { value: new THREE.Color("#ffffff") },
    uGround: { value: new THREE.Color("#000000") },
    uHit: { value: new THREE.Vector3(0, 0, 1) },
    uHitAge: { value: 10 },
  };

  // --- the core -----------------------------------------------------------------------------------
  const core = new THREE.Group();
  core.position.copy(TARGET);
  scene.add(core);

  const shell = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1, 26),
    new THREE.ShaderMaterial({
      uniforms: U,
      vertexShader: NOISE + `
        uniform float uTime, uAmp, uFreq, uLevel, uPulse, uHitAge;
        uniform vec3 uHit;
        varying vec3 vN; varying vec3 vV; varying float vD;
        float disp(vec3 n){
          float d = (snoise(n * uFreq + vec3(0.0, uTime * 0.55, uTime * 0.3)) + 0.3 * snoise(n * uFreq * 2.4 - uTime * 0.4)) * (uAmp + uLevel * 0.2);
          d += uPulse * (0.5 + 0.5 * sin(uTime * 7.0)) * 0.04 + uLevel * 0.04;
          float k = distance(n, uHit);
          d += 0.14 * exp(-uHitAge * 2.6) * sin(k * 20.0 - uHitAge * 15.0) * exp(-k * 2.0) * step(k, uHitAge * 1.4 + 0.2);
          return d;
        }
        void main(){
          vec3 n = normalize(position);
          float d = disp(n);
          vec3 p = n * (0.92 + d);
          vec3 t = normalize(abs(n.y) > 0.99 ? cross(n, vec3(1.0,0.0,0.0)) : cross(n, vec3(0.0,1.0,0.0)));
          vec3 b = cross(n, t);
          vec3 n1 = normalize(n + t * 0.015); vec3 n2 = normalize(n + b * 0.015);
          vec3 bent = normalize(cross(n1 * (0.92 + disp(n1)) - p, n2 * (0.92 + disp(n2)) - p));
          if (dot(bent, n) < 0.0) bent = -bent;
          vD = d;
          vec4 mv = modelViewMatrix * vec4(p, 1.0);
          vN = normalize(normalMatrix * bent);
          vV = normalize(-mv.xyz);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        uniform vec3 uRim, uCore, uGround; uniform float uTime, uLevel;
        varying vec3 vN; varying vec3 vV; varying float vD;
        void main(){
          vec3 N = normalize(vN); vec3 V = normalize(vV);
          vec3 L = normalize(vec3(-0.5, 0.8, 0.5));
          float fres = pow(1.0 - max(dot(N, V), 0.0), 2.2);
          float spec = pow(max(dot(N, normalize(L + V)), 0.0), 70.0) * 1.2;
          float env = smoothstep(0.0, 1.0, reflect(-V, N).y) * 0.35;
          float band = abs(fract(vD * 14.0 - uTime * 0.25) - 0.5);
          float line = (1.0 - smoothstep(0.0, 0.05, band)) * (0.2 + 0.6 * uLevel);
          vec3 col = mix(uGround, uCore, 0.05 + max(dot(N, L), 0.0) * 0.35) + uRim * (env + spec);
          col = mix(col, uRim, clamp(fres + line, 0.0, 1.0));
          gl_FragColor = vec4(col, clamp(0.5 + fres * 0.6 + spec * 0.5 + line * 0.4, 0.0, 1.0));
        }`,
      transparent: true,
      depthWrite: false,
    })
  );
  shell.renderOrder = 5;
  core.add(shell);

  function glowTexture() {
    const c = document.createElement("canvas");
    c.width = c.height = 128;
    const g = c.getContext("2d");
    const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    grad.addColorStop(0, "rgba(255,255,255,1)");
    grad.addColorStop(0.25, "rgba(255,255,255,0.35)");
    grad.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = grad;
    g.fillRect(0, 0, 128, 128);
    const t = new THREE.CanvasTexture(c);
    t.encoding = THREE.sRGBEncoding;
    return t;
  }
  const glowMap = glowTexture();
  const sprite = (size, opacity, additive = true) => {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowMap, transparent: true, depthWrite: false, opacity, blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending }));
    s.scale.setScalar(size);
    return s;
  };
  const heart = sprite(1.3, 0.8);
  heart.renderOrder = 4;
  core.add(heart);
  const halo = sprite(4.6, 0.22);
  halo.renderOrder = 1;
  core.add(halo);

  // --- lights ---------------------------------------------------------------------------------------
  scene.add(new THREE.AmbientLight(0xffffff, 0.3));
  const key = new THREE.DirectionalLight(0xffffff, 1.5);
  key.position.set(-3, 5, 4);
  scene.add(key);
  const rimLight = new THREE.DirectionalLight(0xffffff, 1.1);
  rimLight.position.set(3, 1.5, -5);
  scene.add(rimLight);
  const coreLight = new THREE.PointLight(0xffffff, 1.2, 7, 2);
  core.add(coreLight);

  // --- the gyroscope: three machined rings --------------------------------------------------------
  const metal = new THREE.MeshStandardMaterial({ color: 0xdadada, metalness: 1, roughness: 0.22, envMapIntensity: 1.3 });
  const accent = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xffffff, emissiveIntensity: 0.6, metalness: 0.4, roughness: 0.3 });
  const rings = [
    { r: 1.42, tube: 0.034, axis: "x", speed: 0.35, notches: 18 },
    { r: 1.66, tube: 0.028, axis: "y", speed: -0.25, notches: 24 },
    { r: 1.9, tube: 0.022, axis: "z", speed: 0.18, notches: 30 },
  ].map((spec, i) => {
    const pivot = new THREE.Group();
    pivot.rotation.set(i === 0 ? 1.1 : 0.4, i === 1 ? 0.7 : 0, i === 2 ? 0.6 : 0.2);
    const spinner = new THREE.Group();
    pivot.add(spinner);
    spinner.add(new THREE.Mesh(new THREE.TorusGeometry(spec.r, spec.tube, 12, 140), metal));
    // Notches round the rim: small blocks, every third one lit.
    const block = new THREE.BoxGeometry(spec.tube * 2.6, spec.tube * 2.6, 0.09);
    const plain = new THREE.InstancedMesh(block, metal, spec.notches);
    const lit = new THREE.InstancedMesh(block, accent, Math.ceil(spec.notches / 3));
    const m = new THREE.Object3D();
    let p = 0;
    let l = 0;
    for (let k = 0; k < spec.notches; k++) {
      const a = (k / spec.notches) * Math.PI * 2;
      m.position.set(Math.cos(a) * spec.r, Math.sin(a) * spec.r, 0);
      m.rotation.set(0, 0, a);
      m.updateMatrix();
      if (k % 3 === 0) lit.setMatrixAt(l++, m.matrix);
      else plain.setMatrixAt(p++, m.matrix);
    }
    plain.count = p;
    lit.count = l;
    spinner.add(plain, lit);
    core.add(pivot);
    return { ...spec, spinner };
  });

  // --- satellites on orbits ---------------------------------------------------------------------------
  const crystalMaterial = new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 0.55, roughness: 0.12, flatShading: true, emissive: 0xffffff, emissiveIntensity: 0.12, envMapIntensity: 1.6 });
  const satellites = [];
  for (let i = 0; i < 7; i++) {
    const orbit = new THREE.Group();
    orbit.rotation.set(0.35 + Math.random() * 0.9, Math.random() * Math.PI * 2, (Math.random() - 0.5) * 0.6);
    const radius = 2.45 + i * 0.16 + Math.random() * 0.2;
    const pathPoints = new THREE.EllipseCurve(0, 0, radius, radius).getPoints(96).map((pt) => new THREE.Vector3(pt.x, 0, pt.y));
    const path = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pathPoints), new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.07, depthWrite: false }));
    orbit.add(path);
    const size = 0.07 + Math.random() * 0.07;
    const crystal = new THREE.Mesh(i % 2 ? new THREE.OctahedronGeometry(size) : new THREE.IcosahedronGeometry(size, 0), crystalMaterial);
    const spark = sprite(size * 5, 0.35);
    crystal.add(spark);
    orbit.add(crystal);
    core.add(orbit);
    satellites.push({ orbit, crystal, path, radius, angle: Math.random() * Math.PI * 2, speed: 0.25 + Math.random() * 0.35, spin: 0.5 + Math.random() });
  }

  // --- the floor ---------------------------------------------------------------------------------------
  const floorU = { uTime: U.uTime, uRim: U.uRim, uWaves: { value: new THREE.Vector4(99, 99, 99, 99) }, uGlow: { value: 0.5 } };
  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(60, 60, 1, 1),
    new THREE.ShaderMaterial({
      uniforms: floorU,
      vertexShader: `
        varying vec3 vW;
        void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`,
      fragmentShader: `
        uniform vec3 uRim; uniform float uTime, uGlow; uniform vec4 uWaves;
        varying vec3 vW;
        float wave(float age, float r){ return age > 6.0 ? 0.0 : exp(-pow((r - age * 3.2) * 2.2, 2.0)) * exp(-age * 0.6); }
        void main(){
          vec2 p = vW.xz;
          float r = length(p);
          vec2 g = abs(fract(p * 0.85) - 0.5) / fwidth(p * 0.85);
          float grid = 1.0 - min(min(g.x, g.y), 1.0);
          float fade = exp(-r * 0.16);
          float glow = exp(-r * r * 0.35) * uGlow;
          float rings = wave(uWaves.x, r) + wave(uWaves.y, r) + wave(uWaves.z, r) + wave(uWaves.w, r);
          float a = grid * 0.32 * fade + glow * 0.55 + rings * 0.9 * fade + grid * rings * 0.8;
          gl_FragColor = vec4(uRim, clamp(a, 0.0, 1.0));
        }`,
      transparent: true,
      depthWrite: false,
      extensions: { derivatives: true },
    })
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -2.35;
  floor.renderOrder = 0;
  scene.add(floor);

  // A beam of light from the floor up to the orb.
  const beam = new THREE.Mesh(
    new THREE.CylinderGeometry(0.05, 0.55, 2.4, 32, 1, true),
    new THREE.ShaderMaterial({
      uniforms: { uRim: U.uRim, uLevel: U.uLevel },
      vertexShader: `varying float vY; void main(){ vY = uv.y; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `uniform vec3 uRim; uniform float uLevel; varying float vY;
        void main(){ gl_FragColor = vec4(uRim, (1.0 - vY) * 0.12 * (1.0 + uLevel * 2.0)); }`,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
    })
  );
  beam.position.y = -1.15;
  scene.add(beam);

  // --- dust ------------------------------------------------------------------------------------------------
  const DUST = 380;
  const dustPos = new Float32Array(DUST * 3);
  const dustSeed = new Float32Array(DUST);
  for (let i = 0; i < DUST; i++) {
    dustPos.set([(Math.random() - 0.5) * 12, Math.random() * 9 - 3, (Math.random() - 0.5) * 10 - 1], i * 3);
    dustSeed[i] = Math.random();
  }
  const dustGeo = new THREE.BufferGeometry();
  dustGeo.setAttribute("position", new THREE.BufferAttribute(dustPos, 3));
  dustGeo.setAttribute("seed", new THREE.BufferAttribute(dustSeed, 1));
  const dustU = { uTime: U.uTime, uRim: U.uRim, uSize: { value: 2.6 * pixelRatio }, uBurst: { value: 0 } };
  const dust = new THREE.Points(dustGeo, new THREE.ShaderMaterial({
    uniforms: dustU,
    vertexShader: `
      attribute float seed; uniform float uTime, uSize, uBurst; varying float vA;
      void main(){
        vec3 p = position;
        p.y = mod(p.y + uTime * (0.08 + seed * 0.12) + 3.0, 9.0) - 3.0;
        p.x += sin(uTime * 0.3 + seed * 20.0) * 0.2;
        vec3 away = normalize(p - vec3(0.0, 0.25, 0.0));
        p += away * uBurst * (0.6 + seed);
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        vA = (0.25 + 0.75 * seed) * smoothstep(-3.0, -1.5, p.y) * (1.0 - smoothstep(4.5, 6.0, p.y));
        gl_PointSize = uSize * (0.5 + seed) * (6.0 / -mv.z);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: `uniform vec3 uRim; varying float vA;
      void main(){ float d = length(gl_PointCoord - 0.5); if (d > 0.5) discard; gl_FragColor = vec4(uRim, (1.0 - d * 2.0) * vA * 0.7); }`,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  }));
  scene.add(dust);

  // --- flyers: a spark per message, from the thumb to the orb --------------------------------------------------
  const flyers = [];
  for (let i = 0; i < 4; i++) {
    const s = sprite(0.45, 0);
    s.renderOrder = 6;
    scene.add(s);
    flyers.push({ s, t: 1, from: new THREE.Vector3(), mid: new THREE.Vector3() });
  }

  // --- moods -------------------------------------------------------------------------------------------------------
  const PRESETS = {
    idle:      { amp: 0.07, speed: 0.4, ring: 1.0, orbit: 1.0, pulse: 0, freq: 1.5, heart: 0.7, glow: 0.45 },
    listening: { amp: 0.13, speed: 1.0, ring: 1.8, orbit: 1.4, pulse: 0, freq: 2.0, heart: 1.1, glow: 0.8 },
    thinking:  { amp: 0.1, speed: 0.9, ring: 4.0, orbit: 3.4, pulse: 0, freq: 2.8, heart: 1.3, glow: 0.7 },
    speaking:  { amp: 0.12, speed: 0.75, ring: 1.6, orbit: 1.3, pulse: 1, freq: 1.8, heart: 1.2, glow: 0.9 },
  };
  let state = "idle";
  const cur = { ...PRESETS.idle };
  let levelTarget = 0;
  let level = 0;
  let kick = 0;
  let burst = 0;
  let busy = 0;
  let flashUntil = 0;
  const waves = [99, 99, 99, 99];

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
    rimColor = cssColor("--orb-rim", "#ffffff");
    danger = cssColor("--danger", "#ff5a52");
    U.uRim.value = rimColor.clone();
    U.uCore.value = cssColor("--orb-core", "#ffffff");
    U.uGround.value = cssColor("--ground", "#000000");
    const light = U.uGround.value.getHSL({}).l > 0.5;
    const tint = cssColor("--orb-glow-color", "#ffffff");
    if (metal.envMap) metal.envMap.dispose();
    const envMap = studio(light ? new THREE.Color(0.9, 0.9, 0.9) : tint.clone().lerp(new THREE.Color(1, 1, 1), 0.6));
    metal.envMap = envMap;
    metal.color = light ? new THREE.Color(0x3a3a3a) : new THREE.Color(0xdadada);
    crystalMaterial.envMap = envMap;
    crystalMaterial.color = U.uCore.value.clone();
    crystalMaterial.emissive = tint.clone();
    accent.color = tint.clone();
    accent.emissive = tint.clone();
    metal.needsUpdate = crystalMaterial.needsUpdate = accent.needsUpdate = true;
    coreLight.color = tint.clone();
    for (const s of [heart, halo]) s.material.color = tint.clone();
    for (const sat of satellites) sat.path.material.color = rimColor.clone();
    const blend = light ? THREE.NormalBlending : THREE.AdditiveBlending;
    heart.material.blending = halo.material.blending = dust.material.blending = blend;
  }

  function resize() {
    const rect = canvas.getBoundingClientRect();
    const w = Math.max(1, rect.width);
    const h = Math.max(1, rect.height);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // A tall phone: a wider lens, the rings sized to the width, and the orb
    // lifted into the upper half so the chat has the bottom.
    const portrait = w / h < 1;
    camera.fov = portrait ? 50 : 40;
    camera.updateProjectionMatrix();
    const halfWidth = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.aspect;
    distance = THREE.MathUtils.clamp(2.2 / halfWidth, 7, 14);
    lookDown = portrait ? 1.05 : 0.3;
  }
  let distance = 8.2;
  let lookDown = 0.3;
  new ResizeObserver(resize).observe(canvas);
  resize();

  // --- the phone in the hand: tilt, drag, hold -----------------------------------------------------------------
  let gyro = { yaw: 0, pitch: 0 };
  let gyroBase = null;
  window.addEventListener("deviceorientation", (e) => {
    if (e.beta === null || e.gamma === null) return;
    if (!gyroBase) gyroBase = { beta: e.beta, gamma: e.gamma };
    gyroBase.beta += (e.beta - gyroBase.beta) * 0.005; // slowly re-centre on how it's held
    gyroBase.gamma += (e.gamma - gyroBase.gamma) * 0.005;
    gyro.yaw = THREE.MathUtils.clamp((e.gamma - gyroBase.gamma) / 30, -1, 1) * 0.35;
    gyro.pitch = THREE.MathUtils.clamp((e.beta - gyroBase.beta) / 30, -1, 1) * 0.22;
  });

  let drag = { yaw: 0, pitch: 0, vYaw: 0, vPitch: 0 };
  let pointer = null; // { x, y, t, moved, held, timer }
  const raycaster = new THREE.Raycaster();
  const sphere = new THREE.Sphere(new THREE.Vector3(), 1.0);

  function hitOrb(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    const ndc = new THREE.Vector2(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(ndc, camera);
    sphere.center.copy(core.position);
    sphere.radius = 1.05 * core.scale.x;
    const hit = new THREE.Vector3();
    if (!raycaster.ray.intersectSphere(sphere, hit)) return null;
    return shell.worldToLocal(hit).normalize();
  }

  canvas.addEventListener("pointerdown", (e) => {
    canvas.setPointerCapture(e.pointerId);
    const onOrb = hitOrb(e.clientX, e.clientY);
    pointer = { id: e.pointerId, x: e.clientX, y: e.clientY, lastX: e.clientX, lastY: e.clientY, moved: false, held: false, onOrb };
    if (onOrb) ripple(onOrb);
    // Holding the orb means "listen". A drag cancels it.
    if (onOrb) {
      pointer.timer = setTimeout(() => {
        if (!pointer || pointer.moved) return;
        pointer.held = true;
        F.bus.emit("scene-hold-start");
      }, 280);
    }
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!pointer || e.pointerId !== pointer.id) return;
    const dx = e.clientX - pointer.lastX;
    const dy = e.clientY - pointer.lastY;
    if (!pointer.moved && Math.hypot(e.clientX - pointer.x, e.clientY - pointer.y) > 10 && !pointer.held) {
      pointer.moved = true;
      clearTimeout(pointer.timer);
    }
    if (pointer.moved) {
      drag.vYaw = dx * 0.006;
      drag.vPitch = dy * 0.004;
      drag.yaw += drag.vYaw;
      drag.pitch = THREE.MathUtils.clamp(drag.pitch + drag.vPitch, -0.5, 0.45);
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
    U.uHit.value.copy(at || new THREE.Vector3((Math.random() - 0.5) * 0.6, (Math.random() - 0.5) * 0.6, 1).normalize());
    U.uHitAge.value = 0;
    kick = Math.max(kick, 0.7);
  }

  function pulse() {
    const i = waves.indexOf(Math.max(...waves));
    waves[i] = 0;
  }

  function send() {
    const f = flyers.find((x) => x.t >= 1) || flyers[0];
    // From just above the thumb (bottom centre of the screen) to the orb.
    const from = new THREE.Vector3(0, -0.92, 0.5).unproject(camera);
    const dir = from.sub(camera.position).normalize();
    f.from.copy(camera.position).add(dir.multiplyScalar(distance * 0.55));
    f.mid.copy(f.from).lerp(core.position, 0.5).add(new THREE.Vector3((Math.random() - 0.5) * 1.6, 1.2, 0.6));
    f.t = 0;
  }

  // --- adaptive quality --------------------------------------------------------------------------------------------
  let slow = 0;
  let samples = 0;
  function adapt(dt) {
    samples++;
    if (dt > 0.034) slow++;
    if (samples < 90) return;
    if (slow > 45 && pixelRatio > 0.75) {
      pixelRatio = Math.max(0.75, pixelRatio - 0.4);
      renderer.setPixelRatio(pixelRatio);
      dustU.uSize.value = 2.6 * pixelRatio;
      resize();
    }
    samples = 0;
    slow = 0;
  }

  // --- the frame --------------------------------------------------------------------------------------------------------
  const clock = new THREE.Clock();
  let t = 0;
  let paused = false;
  document.addEventListener("visibilitychange", () => {
    paused = document.hidden;
    if (!paused) {
      clock.getDelta();
      requestAnimationFrame(frame);
    }
  });

  const tmp = new THREE.Vector3();
  function frame() {
    if (paused) return;
    const dt = Math.min(clock.getDelta(), 0.05);
    const target = PRESETS[state] || PRESETS.idle;
    const ease = Math.min(1, dt * 3);
    for (const k of Object.keys(cur)) cur[k] += (target[k] - cur[k]) * ease;
    const motion = reduced ? 0.3 : 1;

    level += (levelTarget - level) * Math.min(1, dt * (levelTarget > level ? 16 : 4));
    levelTarget *= Math.pow(0.15, dt);
    kick *= Math.pow(0.02, dt);
    burst *= Math.pow(0.1, dt);
    busy *= Math.pow(0.3, dt);
    for (let i = 0; i < 4; i++) waves[i] += dt;

    t += dt * cur.speed * motion;
    U.uTime.value = t;
    U.uAmp.value = cur.amp + kick * 0.18;
    U.uFreq.value = cur.freq;
    U.uLevel.value = level * motion;
    U.uPulse.value = cur.pulse;
    U.uHitAge.value += dt;
    floorU.uWaves.value.set(waves[0], waves[1], waves[2], waves[3]);
    floorU.uGlow.value = cur.glow + level * 0.6 + burst * 0.5;
    dustU.uBurst.value = burst;
    const flashing = performance.now() < flashUntil;
    U.uRim.value.lerp(flashing ? danger : rimColor, Math.min(1, dt * 8));

    // The core breathes and floats; the rings and satellites turn.
    core.position.y = TARGET.y + Math.sin(performance.now() / 1400) * 0.08;
    shell.rotation.y += dt * (0.15 + busy) * motion;
    core.scale.setScalar(1 + kick * 0.04 + level * 0.05 + burst * 0.03);
    heart.material.opacity = 0.45 + cur.heart * 0.35 + level * 0.4 + burst * 0.4;
    heart.scale.setScalar(1.1 + level * 0.7 + burst * 0.6 + 0.05 * Math.sin(t * 3));
    halo.material.opacity = 0.14 + level * 0.25 + burst * 0.2;
    coreLight.intensity = 0.8 + cur.heart + level * 2 + burst * 2;

    for (const r of rings) {
      const spin = dt * r.speed * (cur.ring + busy * 3) * motion;
      if (r.axis === "x") r.spinner.rotation.x += spin;
      else if (r.axis === "y") r.spinner.rotation.y += spin;
      else r.spinner.rotation.z += spin;
    }
    for (const s of satellites) {
      s.angle += dt * s.speed * (cur.orbit + busy * 2) * motion;
      s.crystal.position.set(Math.cos(s.angle) * s.radius, Math.sin(s.angle * 2) * 0.12, Math.sin(s.angle) * s.radius);
      s.crystal.rotation.x += dt * s.spin;
      s.crystal.rotation.y += dt * s.spin * 0.7;
      s.path.material.opacity = 0.05 + busy * 0.12 + level * 0.08;
    }

    for (const f of flyers) {
      if (f.t >= 1) {
        f.s.material.opacity = 0;
        continue;
      }
      f.t = Math.min(1, f.t + dt * 1.5);
      const a = f.t;
      // Quadratic bezier: from -> mid -> orb.
      tmp.copy(f.from).multiplyScalar((1 - a) * (1 - a)).add(f.mid.clone().multiplyScalar(2 * (1 - a) * a)).add(core.position.clone().multiplyScalar(a * a));
      f.s.position.copy(tmp);
      f.s.material.opacity = Math.sin(a * Math.PI) * 0.95;
      f.s.scale.setScalar(0.5 - a * 0.25);
      if (f.t >= 1) {
        ripple(null);
        kick = 1;
      }
    }

    // The camera: drag spins it (and eases back), tilt shifts it.
    drag.yaw *= Math.pow(0.35, dt);
    drag.pitch *= Math.pow(0.35, dt);
    const yaw = drag.yaw + gyro.yaw;
    const pitch = 0.12 + drag.pitch + gyro.pitch;
    camera.position.set(Math.sin(yaw) * Math.cos(pitch) * distance, TARGET.y + Math.sin(pitch) * distance, Math.cos(yaw) * Math.cos(pitch) * distance);
    camera.lookAt(TARGET.x, TARGET.y - lookDown, TARGET.z);

    renderer.render(scene, camera);
    adapt(dt);
    requestAnimationFrame(frame);
  }

  recolor();
  F.bus.on("theme", recolor);
  requestAnimationFrame(frame);

  F.orb = {
    webgl: true,
    setState(s) {
      state = PRESETS[s] ? s : s === "acting" ? "thinking" : "idle";
    },
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
    ripple,
    // An answer: the orb bursts and a ring runs out across the floor.
    burst() {
      burst = 1;
      kick = Math.max(kick, 0.5);
      pulse();
    },
    tap() {
      kick = Math.max(kick, 0.3);
    },
    busy() {
      busy = 1;
    },
    send,
    pulse,
    recolor,
  };
})();
