import * as THREE from "three";

/**
 * Voice orb: a particle sphere whose surface is displaced by a "voice level".
 * Idle: a gentle synthetic speech rhythm. With mic enabled (explicit click only):
 * real input level from an AnalyserNode. Audio is analysed locally and never sent anywhere.
 */
const VERT = /* glsl */ `
  uniform float uTime; uniform float uLevel; uniform float uSize; uniform float uPixel;
  attribute float aSeed;
  varying float vDisp; varying float vSeed;
  void main() {
    vec3 n = normalize(position);
    float w = sin(n.x*3.0 + uTime*1.1) + sin(n.y*4.0 - uTime*1.4) + sin(n.z*5.0 + uTime*0.8);
    float disp = (w * 0.5 + 0.5) * (0.05 + uLevel * 0.55) + uLevel * 0.12 * sin(aSeed * 6.2831 + uTime * 6.0);
    vec3 p = n * (1.0 + disp);
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    gl_PointSize = uSize * uPixel * (1.0 + uLevel * 0.8) * (1.0 / -mv.z);
    vDisp = disp; vSeed = aSeed;
  }`;
const FRAG = /* glsl */ `
  uniform float uLevel;
  varying float vDisp; varying float vSeed;
  void main() {
    vec2 c = gl_PointCoord - 0.5;
    float d = length(c);
    if (d > 0.5) discard;
    float a = smoothstep(0.5, 0.0, d);
    vec3 teal = vec3(0.243, 0.878, 0.773);
    vec3 violet = vec3(0.482, 0.361, 1.0);
    vec3 saffron = vec3(1.0, 0.784, 0.341);
    float t = clamp(vDisp * 2.2, 0.0, 1.0);
    vec3 col = mix(violet, teal, smoothstep(0.0, 0.5, t));
    col = mix(col, saffron, smoothstep(0.75, 1.0, t + uLevel * 0.3 * vSeed));
    gl_FragColor = vec4(col, a * (0.55 + 0.45 * t));
  }`;

export function createOrb(canvas, { onFallback } = {}) {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: true, powerPreference: "low-power" });
  } catch {
    onFallback?.();
    return null;
  }
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const small = innerWidth < 640;
  const COUNT = small ? 3500 : 7500;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 50);
  camera.position.z = 4.2;

  const pos = new Float32Array(COUNT * 3);
  const seed = new Float32Array(COUNT);
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < COUNT; i++) { // Fibonacci sphere: even point distribution
    const y = 1 - (i / (COUNT - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const th = golden * i;
    pos.set([Math.cos(th) * r, y, Math.sin(th) * r], i * 3);
    seed[i] = Math.random();
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  geo.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1));

  const uniforms = {
    uTime: { value: 0 }, uLevel: { value: 0 }, uSize: { value: small ? 2.6 : 2.2 },
    uPixel: { value: 1 },
  };
  const mat = new THREE.ShaderMaterial({
    uniforms, vertexShader: VERT, fragmentShader: FRAG,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  });
  const points = new THREE.Points(geo, mat);
  scene.add(points);

  function resize() {
    const { clientWidth: w, clientHeight: h } = canvas;
    const dpr = Math.min(devicePixelRatio || 1, 2);
    renderer.setPixelRatio(dpr);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    uniforms.uPixel.value = dpr * (h / 2) / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) / 100;
  }
  new ResizeObserver(resize).observe(canvas);
  resize();

  // Pointer parallax
  const target = { x: 0, y: 0 };
  addEventListener("pointermove", (e) => {
    target.x = (e.clientX / innerWidth - 0.5) * 0.7;
    target.y = (e.clientY / innerHeight - 0.5) * 0.5;
  }, { passive: true });

  // Audio
  let analyser = null, stream = null, buf = null;
  let level = 0;
  async function enableMic() {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true }); // only called from a click
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const src = ctx.createMediaStreamSource(stream);
    analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    src.connect(analyser);
    buf = new Uint8Array(analyser.fftSize);
    stream.getAudioTracks()[0].addEventListener("ended", disableMic);
  }
  function disableMic() {
    stream?.getTracks().forEach((t) => t.stop());
    stream = null; analyser = null;
    window.dispatchEvent(new CustomEvent("orb:mic-stopped"));
  }
  function micLevel() {
    analyser.getByteTimeDomainData(buf);
    let sum = 0;
    for (let i = 0; i < buf.length; i++) { const v = (buf[i] - 128) / 128; sum += v * v; }
    return Math.min(1, Math.sqrt(sum / buf.length) * 5);
  }
  // Synthetic idle "speech": syllable-like bursts so the orb feels alive before any mic use.
  const idle = (t) => 0.1 + 0.14 * Math.max(0, Math.sin(t * 2.3) * Math.sin(t * 0.7 + 1.0));

  let running = false, raf = 0, last = performance.now(), t = 0;
  function frame(now) {
    raf = requestAnimationFrame(frame);
    const dt = Math.min((now - last) / 1000, 0.05);
    last = now;
    t += dt * (reduced ? 0.15 : 1);
    const raw = analyser ? micLevel() : idle(t);
    level += (raw - level) * (raw > level ? 0.35 : 0.08); // fast attack, slow release
    uniforms.uTime.value = t;
    uniforms.uLevel.value = reduced && !analyser ? 0.05 : level;
    points.rotation.y += dt * (reduced ? 0.02 : 0.12);
    points.rotation.x += (target.y - points.rotation.x) * 0.04;
    points.position.x += (target.x * 0.4 - points.position.x) * 0.04;
    renderer.render(scene, camera);
  }
  function start() { if (!running) { running = true; last = performance.now(); raf = requestAnimationFrame(frame); } }
  function stop() { running = false; cancelAnimationFrame(raf); }

  // Don't burn battery when off-screen or in a background tab.
  new IntersectionObserver(([e]) => (e.isIntersecting ? start() : stop())).observe(canvas);
  document.addEventListener("visibilitychange", () => (document.hidden ? stop() : start()));

  return { enableMic, disableMic, get micOn() { return !!analyser; } };
}
