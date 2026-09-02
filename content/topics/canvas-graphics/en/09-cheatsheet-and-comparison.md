# Cheat Sheet and Technology Comparison

Reference material for articles 01-08 — no new concept explanations, just compact tables and snippets for quick lookup. If something here isn't clear, it's covered in depth in the article named in that section's heading.

**Abbreviations used in the tables below:**

- DOM (document object model — the browser's tree of page objects)
- CPU (central processing unit — the main processor, the one that runs your JS)
- GPU (graphics processing unit — the video chip that fills pixels)
- UI (user interface)
- SVG (scalable vector graphics — a vector format whose elements are DOM nodes)
- PBR (physically based rendering — lighting computed from real material physics)
- WebGL (Web Graphics Library — the browser API for GPU rendering)
- WebGPU (the newer browser API for GPU access, the successor to WebGL)

## Part 1: Cheat Sheet

### Canvas 2D: context methods by purpose (articles 01-03)

| Group | Methods/properties |
|---|---|
| Drawing (no path) | `fillRect`, `strokeRect`, `clearRect` |
| Paths | `beginPath`, `moveTo`, `lineTo`, `arc`, `quadraticCurveTo`, `bezierCurveTo`, `closePath`, `fill`, `stroke` |
| Styles | `fillStyle`, `strokeStyle`, `lineWidth`, `lineCap`, `lineJoin`, `setLineDash`, `createLinearGradient`, `createRadialGradient`, `createPattern` |
| Transforms | `translate`, `rotate`, `scale`, `setTransform`, `resetTransform` |
| State | `save`, `restore` |
| Text | `fillText`, `strokeText`, `font`, `textAlign`, `textBaseline`, `measureText` |
| Pixels | `getImageData`, `putImageData`, `createImageData` |
| Compositing | `globalCompositeOperation`, `globalAlpha` |
| Export | `toDataURL`, `toBlob`, `createImageBitmap` |

### The canonical retina-correct canvas setup (article 01)

```javascript
function setupCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  canvas.style.width = `${rect.width}px`;
  canvas.style.height = `${rect.height}px`;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  return ctx;
}
```

### The minimal game loop (article 02)

```javascript
let previousTimestamp;
function loop(timestamp) {
  if (previousTimestamp === undefined) previousTimestamp = timestamp;
  const dt = (timestamp - previousTimestamp) / 1000;
  previousTimestamp = timestamp;

  update(dt);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  draw(ctx);

  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
```

### `drawImage`: three call forms (article 02)

```javascript
ctx.drawImage(image, dx, dy);                  // 1. as-is, at a position
ctx.drawImage(image, dx, dy, dWidth, dHeight); // 2. + scaling
ctx.drawImage(                                 // 3. + cropping from the source (sprites)
  image,
  sx, sy, sWidth, sHeight, // where to crop from the source
  dx, dy, dWidth, dHeight, // where to paste it, and at what size
);
```

### `globalCompositeOperation` — quick reference (article 03)

| Mode | Effect |
|---|---|
| `source-over` (default) | Ordinary drawing on top |
| `destination-out` | New shapes **erase** existing content — the basis of a scratch card |
| `source-atop` | New content only shows where opaque content already exists |
| `multiply` | Channels multiplied — darker |
| `screen` | Visually the opposite of multiply — lighter |
| `lighter` | Channels added (additive) — glow/particles |

### Pixi.js — quick start (article 05)

| API | Purpose |
|---|---|
| `new Application()` + `await app.init(...)` | Create the application/renderer |
| `app.stage.addChild(container)` | The scene tree's root |
| `new Sprite(texture)` | Draw a texture at a position/rotation/scale |
| `Texture` vs. `BaseTexture` | A window into an image region vs. the actual GPU texture |
| `app.ticker.add((t) => ...)` | The built-in update loop, `t.deltaTime`/`t.deltaMS` |
| `await Assets.load(url)` | Loading with caching/deduplication |
| `sprite.destroy()` / `texture.destroy(true)` | Releasing GPU resources |

### three.js — quick start (article 06)

| API | Purpose |
|---|---|
| `new THREE.Scene()` | The scene tree |
| `new THREE.PerspectiveCamera(fov, aspect, near, far)` | A camera with perspective projection |
| `new THREE.WebGLRenderer()` | A wrapper over the WebGL context |
| `new THREE.Mesh(geometry, material)` | Geometry (shape) + Material (shading) in the scene |
| `AmbientLight` / `DirectionalLight` / `PointLight` / `SpotLight` | Light source types |
| `camera.aspect = ...; camera.updateProjectionMatrix()` | A **required** pair on resize |
| `OrbitControls` / `GLTFLoader` | Mouse camera control / model loading |
| `geometry.dispose()`, `material.dispose()`, `texture.dispose()` | Releasing GPU resources |

### d3.js — core API (article 07)

| API | Purpose |
|---|---|
| `d3.select(el).selectAll(sel)` | Selecting DOM nodes |
| `.data(array, keyFn).join(enter, update, exit)` | Data binding + DOM reconciliation |
| `d3.scaleLinear().domain([...]).range([...])` | A pure function: data → pixels |
| `d3.line().x(fn).y(fn)` | A line geometry generator from a data array |
| `d3.line().context(ctx)` | Redirects the shape generator to draw to canvas instead of SVG |

## Part 2: Technology Comparison

### What each technology is for

| Technology | Best for | What it can do |
|---|---|---|
| **DOM + CSS** *(see the Browser Animation topic)* | Ordinary UI, accessible out of the box | Layout, styling, CSS animation |
| **SVG** | Interactive dashboards, icons, diagrams | A vector retained-mode DOM, CSS styling, accessibility |
| **Canvas 2D** | Per-pixel work, custom 2D graphics | Immediate-mode drawing, pixel filters, compositing |
| **WebGL (raw)** | Full control over the GPU pipeline | Shaders, buffers, arbitrary rendering |
| **WebGPU** | Modern, low-level GPU access | Explicit pipeline objects, compute shaders, lower per-frame CPU overhead |
| **Pixi.js** | 2D scenes with hundreds to thousands of sprites | Retained-mode scene, batching, filters, sprite atlases |
| **three.js** | 3D scenes and objects | Cameras, lighting, PBR materials, glTF model loading |
| **d3.js** | Scale/shape math + data binding | Scales, shape generators, data joins, renderer-agnosticism (SVG or canvas) |
| **Charting libraries (ECharts/Chart.js)** | Standard charts with minimal code | Ready-made bar/line/pie/scatter with legends, tooltips, responsiveness |
| **Lottie** *(see the Browser Animation topic)* | Playing back complex animation from After Effects | Exact 1:1 playback of vector motion graphics |

### Where it is used, and how much it holds

| Technology | Typical real-world use | Rough comfort zone (element count) |
|---|---|---|
| **DOM + CSS** *(see the Browser Animation topic)* | Any standard interface | Hundreds to thousands of nodes |
| **SVG** | Charts with rich interactivity, illustrations, icons | Up to ~1-2 thousand elements |
| **Canvas 2D** | Charts/dashboards with 10k+ points, simple games, effects (scratch card) | 10,000+ simple objects |
| **WebGL (raw)** | The engines built on top of it (Pixi, three.js), niche custom renderers | Bounded by per-draw-call driver overhead, not raw object count |
| **WebGPU** | Heavy GPU compute, next-generation engines | Higher than WebGL, thanks to lower per-draw-call overhead |
| **Pixi.js** | Particle-heavy promo pages, 2D games, slot/casino games | Thousands to tens of thousands of sprites (with atlases/batching) |
| **three.js** | Product 3D configurators, brand 3D scenes, visualizations | Thousands of meshes (more via instancing) |
| **d3.js** | Bespoke, non-standard data visualization | Depends on the target renderer (SVG limits or canvas limits) |
| **Charting libraries (ECharts/Chart.js)** | 90% of product dashboards and reports | Typically thousands of points, library-dependent |
| **Lottie** *(see the Browser Animation topic)* | Onboarding illustrations, branded loaders | Not about element count — about a single animation's complexity |

### Performance profile and limitations

| Technology | Performance profile | Limitations |
|---|---|---|
| **DOM + CSS** *(see the Browser Animation topic)* | Compositor for transform/opacity, main thread for layout | Not suited to per-pixel/GPU-intensive graphics |
| **SVG** | DOM-based, the same per-node overhead as ordinary DOM | Degrades at large node counts |
| **Canvas 2D** | CPU rasterization, one DOM node regardless of content | No retained-mode scene out of the box, manual hit detection |
| **WebGL (raw)** | GPU parallelism, compositor-independent rendering | Extremely verbose API, high barrier to entry |
| **WebGPU** | Lower CPU overhead per call than WebGL | Browser support isn't universal yet — check before production use |
| **Pixi.js** | GPU batching via WebGL | Overkill for a handful of simple shapes |
| **three.js** | GPU rendering with a full 3D pipeline | Requires understanding 3D math/lighting for non-trivial scenes |
| **d3.js** | Depends on what it renders into (SVG DOM or canvas) | Not an out-of-the-box "charting library" — requires hand-building the viz |
| **Charting libraries (ECharts/Chart.js)** | Usually SVG/canvas under the hood, optimized by the library's authors | Less freedom for non-standard/unique visualizations |
| **Lottie** *(see the Browser Animation topic)* | Depends on the renderer (svg/canvas/html) | Requires a bodymovin export pipeline, not for interactive graphics |

**How to use these tables in practice:** start from the top rows (DOM/CSS, SVG). Move down a level only once the specific task — data volume, interactivity, per-pixel control, 3D — hits a real limitation of the current one. The rule is the same as in the browser-animation comparison table. The tool choice follows the task, not the technology's "power" taken out of context.
