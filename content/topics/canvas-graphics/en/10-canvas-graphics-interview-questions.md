# Canvas & Graphics — Interview Questions (Middle → Senior)

## Group 1: Canvas 2D Fundamentals

**What's the difference between immediate mode and retained mode, and why does it matter for canvas?**

Retained mode means the browser keeps a structure of objects and repaints what changed on its own. The DOM (document object model, the tree of page objects in a browser) and SVG (scalable vector graphics) both work this way. Immediate mode, which Canvas 2D uses, is the opposite: drawn pixels remember nothing about themselves.

```txt
┌──────────────────────────┐  ┌───────────────────────────────┐
│ Retained mode (DOM, SVG) │  │ Immediate mode (Canvas 2D)    │
│ el.style.left = "110px"  │  │ ctx.clearRect(...)            │
│ → browser repaints       │  │ ctx.fillRect(110, 10, 50, 50) │
│   what is needed         │  │ → you decide what and when    │
└──────────────────────────┘  └───────────────────────────────┘
```

A call to `ctx.fillRect(...)` colors pixels right now. After that, as far as canvas is concerned, they are just colored pixels, indistinguishable from any others. The only way to change anything is to redraw everything from scratch, or at least the part that changed.

That is why every canvas animation is built around an explicit "clear → update state → redraw" cycle. CSS and WAAPI (Web Animations API) work the other way round. There the browser repaints for you when a property changes.

---

**Why does canvas look blurry on retina displays, and how do you fix it?**

A canvas has two independent sizes, and blur appears when they disagree. The pair `canvas.width`/`canvas.height` sets the backing store: the real number of pixels in the buffer you draw into. The pair `canvas.style.width`/`style.height` sets the CSS size of the element on the page.

```txt
┌──────────────────────────────────────────┐
│ canvas.width / canvas.height             │
│ backing store: real pixels in the buffer │
├──────────────────────────────────────────┤
│ canvas.style.width / .height             │
│ CSS size of the element on the page      │
└──────────────────────────────────────────┘
```

If you never set them separately, both end up equal to the same number of CSS pixels. On a display with `devicePixelRatio: 2` the browser then stretches that buffer over twice as many physical pixels. The stretching is what you see as blur.

```javascript
const canvas = document.querySelector('canvas');
const ctx = canvas.getContext('2d');
const dpr = window.devicePixelRatio || 1;
const rect = canvas.getBoundingClientRect();

canvas.width = rect.width * dpr;         // backing store, in real pixels
canvas.height = rect.height * dpr;
canvas.style.width = `${rect.width}px`;  // CSS size stays as it was
canvas.style.height = `${rect.height}px`;

ctx.scale(dpr, dpr);  // drawing code keeps its logical CSS coordinates
```

The `ctx.scale(dpr, dpr)` call is what keeps the rest of your drawing code unchanged. Coordinates stay in the familiar logical units, and the browser maps them onto the denser buffer.

---

**What's the difference between `clearRect()` and assigning `canvas.width = canvas.width`?**

`clearRect(x, y, w, h)` makes an area transparent and touches nothing else. The transform, the styles and the clip region all survive it. Assigning `canvas.width`, even the same value back, resets the whole context as a side effect.

| What happens to | `clearRect(x, y, w, h)` | `canvas.width = canvas.width` |
|---|---|---|
| Pixels | the given rectangle is cleared | the whole canvas is cleared |
| Transform | kept | reset to the identity matrix |
| Styles, line width | kept | reset to defaults |
| Clip region | kept | reset |

That reset is easy to trigger by accident, because resizing a canvas means writing to `width`. Developers expect only the image to disappear, and are then surprised to lose an accumulated transform as well.

---

**Explain the nonzero and evenodd fill rules. When can a "donut" shape (a circle with a hole) render as solid, with no hole?**

When a path holds several sub-contours, the fill rule decides which regions get painted. The outer and inner circle of a "donut" are exactly such a pair. By default the rule is `nonzero`. For every point it counts how many times the contour winds around it, direction included. The point is filled when that count is not zero.

| Both contours wound | `nonzero` | `evenodd` |
|---|---|---|
| In opposite directions | hole stays | hole stays |
| In the same direction | hole disappears | hole stays |

So the hole vanishes when both circles are wound the same way, both clockwise for instance. Their contributions no longer cancel out, and `nonzero` paints the inner circle too.

There are two fixes. Give the contours opposite directions through the `anticlockwise` parameter of `arc()`. Or call `fill('evenodd')`, which counts only the parity of ray-contour crossings and ignores direction.

## Group 2: Canvas Animation and Pixels

**Why must a hand-written game loop use delta time, and what's the difference between fixed and variable timestep?**

Moving by a fixed step per frame (`x += 2`) ties speed to the display refresh rate. The same code runs twice as fast at 120 Hz as it does at 60 Hz. Delta time turns that step into "units per second" and removes the dependency.

```javascript
const STEP = 1 / 60;  // fixed physics step, in seconds
function updatePhysics(step) { /* move bodies forward by `step` seconds */ }
function draw(alpha) { /* alpha in [0, 1): how far we are into the next step */ }

let last = performance.now();
let accumulator = 0;

function frame(now) {
  const dt = (now - last) / 1000;  // delta time, in seconds
  last = now;
  accumulator += dt;

  while (accumulator >= STEP) {    // identical chunks, whatever the frame rate
    updatePhysics(STEP);
    accumulator -= STEP;
  }
  draw(accumulator / STEP);        // the leftover interpolates the visuals
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
```

A variable timestep means delta time differs on every frame. That is fine for visual animation, but it causes real problems for physics. A spike in `dt` can cause "tunneling": a fast object skips straight through an obstacle in one large step. The simulation then behaves differently on different devices.

A fixed timestep with an accumulator fixes both problems. Physics always steps forward in identical small chunks, whatever the actual frame rate is. The leftover time between steps is used to interpolate the visual position.

---

**What are the three approaches to hit detection on canvas, and when would you use each?**

Canvas remembers no objects, so a click is only a coordinate, and you decide yourself what it hit. There are three ways to do that.

| Approach | Good for | Cost |
|---|---|---|
| Math: bounding box or circle | simple shapes | cheapest, used in most real code |
| `isPointInPath()` | shapes already drawn as a path | one context call per shape |
| Color-picking | complex, overlapping shapes | one extra render pass per change |

The math approach compares the point against an AABB (axis-aligned bounding box — a rectangle whose sides stay parallel to the axes) or against a circle. It is the cheapest of the three and covers the vast majority of real code.

The methods `isPointInPath()` and `isPointInStroke()` ask the context itself whether a point falls inside the path it has accumulated. That is convenient for irregular shapes that are already described as a canvas path.

Color-picking draws every object in its own solid, unique color onto an invisible offscreen canvas. A click reads the pixel color under the cursor and looks up which object owns that color. It is exact for complex, overlapping, arbitrarily irregular shapes, and it costs one extra render pass on every change of the scene.

---

**Why is `getImageData` an expensive operation, and how do you mitigate that cost?**

Canvas 2D can render on the GPU (graphics processing unit — the chip that draws pixels). Asking for raw pixels on the CPU (central processing unit) then forces a synchronization. The browser has to wait for the GPU's current work to finish. Only then can it copy the buffer from GPU memory into ordinary process memory.

```txt
┌────────────────────────────────────┐
│ GPU memory                         │
│ the frame the GPU is still drawing │
└────────────────────────────────────┘
                   │  browser waits for the GPU, then copies
                   ▼
┌────────────────────────────────────┐
│ CPU memory                         │
│ the ImageData array you asked for  │
└────────────────────────────────────┘
```

Such a synchronization point costs real time inside a loop that runs every frame. Calling `getImageData` on every animation frame is a common cause of an fps (frames per second) drop.

The `willReadFrequently: true` hint, passed when you get the context, tells the browser to keep the buffer in CPU-accessible memory from the start. That avoids the repeated GPU to CPU copies.

```javascript
const canvas = document.querySelector('canvas');
const ctx = canvas.getContext('2d', { willReadFrequently: true });
```

---

**Describe how you'd implement a scratch-card effect using compositing.**

The whole effect is three layers and one compositing mode, with no extra library needed.

- A base layer: the content hidden under the "foil", such as prize text or an image.
- A "foil" layer on top, drawn with the ordinary `source-over` mode.
- Brush strokes, drawn while the cursor moves with the button held down.

```javascript
const canvas = document.querySelector('canvas');
const ctx = canvas.getContext('2d');
const prizeImage = document.querySelector('img');  // already loaded

ctx.drawImage(prizeImage, 0, 0);                   // 1. the base layer
ctx.fillStyle = '#bbbbbb';
ctx.fillRect(0, 0, canvas.width, canvas.height);   // 2. the "foil" on top

canvas.addEventListener('pointermove', (e) => {
  if (e.buttons !== 1) return;                     // only while held down
  ctx.globalCompositeOperation = 'destination-out';  // 3. erase, don't paint
  ctx.beginPath();
  ctx.arc(e.offsetX, e.offsetY, 20, 0, Math.PI * 2);
  ctx.fill();
});
```

The strokes do the actual work. Before each one, `globalCompositeOperation` switches to `destination-out`. In that mode the new shape erases existing pixels instead of painting over them. Every stroke punches a hole in the foil layer, and the base layer shows through it.

---

**What's the tainted canvas security restriction, and how do you avoid it?**

A canvas becomes "tainted" as soon as you draw an image from another origin onto it without correct CORS (cross-origin resource sharing) headers. The browser then blocks every later read of its pixel data — `getImageData`, `toDataURL`, `toBlob` — with a `SecurityError`.

The restriction exists because a readable canvas would otherwise work as an oracle. A page could draw a private cross-origin image and read the user's content straight out of the pixels.

Avoiding it takes two things at the same time, and neither one is enough on its own:

- On the client: set `img.crossOrigin = 'anonymous'` before assigning `img.src`.
- On the server: the image response must carry an `Access-Control-Allow-Origin` header.

## Group 3: WebGL and GPU Fundamentals

**What is a draw call, and why does minimizing their count matter more than minimizing triangle count?**

A draw call is one command to the GPU: "draw these vertices with this shader program, these buffers, these uniforms and this texture". WebGL (Web Graphics Library, the browser API for drawing on the GPU) issues one per batch of geometry.

Its cost is mostly driver overhead: validating state, synchronizing CPU with GPU, and uploading whatever data changed. The number of triangles inside the call is not the expensive part.

```txt
┌─────────────────────────┬─────────────────┬──────────┐
│ 100 sprites drawn as    │ Driver work     │ Geometry │
├─────────────────────────┼─────────────────┼──────────┤
│ 100 separate draw calls │ 100x validation │ the same │
├─────────────────────────┼─────────────────┼──────────┤
│ 1 draw call (batched)   │ 1x validation   │ the same │
└─────────────────────────┴─────────────────┴──────────┘
```

Drawing 10,000 triangles in one draw call is almost always cheaper than 100 triangles spread over 100 separate calls. Those hundred calls also swap a texture or a shader in between, and that is what you pay for. Batching means combining many objects into the fewest possible draw calls. That is why it is the central performance topic in both Pixi and three.js.

---

**Explain the difference between the vertex shader and fragment shader stages.**

The two stages answer two different questions, and rasterization sits between them.

```txt
┌──────────────────────────────────┐
│ Vertex shader (programmable)     │
│ once per vertex                  │
│ output: gl_Position              │
└──────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────┐
│ Rasterization (fixed-function)   │
│ which pixels the triangle covers │
│ interpolates varying values      │
└──────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────┐
│ Fragment shader (programmable)   │
│ once per covered pixel           │
│ output: gl_FragColor             │
└──────────────────────────────────┘
```

The vertex shader runs once per vertex of a piece of geometry. It answers "where will this point end up on screen", and its output is `gl_Position`.

Rasterization is the only stage you cannot program. The GPU works out which pixels a triangle covers, and it linearly interpolates the varying values between vertices. The fragment shader then runs once per covered pixel. It answers "what color is this specific pixel", and its output is `gl_FragColor`.

---

**What's the difference between an attribute, a uniform, and a varying?**

The three differ in how many values exist and who reads them.

```txt
┌───────────┬─────────────────────────────┬─────────────────────┐
│ Kind      │ How many values             │ Read by             │
├───────────┼─────────────────────────────┼─────────────────────┤
│ attribute │ one per vertex              │ the vertex shader   │
├───────────┼─────────────────────────────┼─────────────────────┤
│ uniform   │ one per draw call           │ both shaders        │
├───────────┼─────────────────────────────┼─────────────────────┤
│ varying   │ one per pixel, interpolated │ the fragment shader │
└───────────┴─────────────────────────────┴─────────────────────┘
```

An `attribute` is data unique to each vertex: a position, a UV (texture coordinate, named after its axes u and v), a per-vertex color. The vertex shader reads it.

A `uniform` is a single value, the same for all vertices and pixels within one draw call. A transform matrix, an animation time value and a shared color are typical uniforms.

A `varying` is the bridge between the two shaders. The vertex shader writes it, rasterization interpolates it linearly between vertices, and the fragment shader reads one interpolated value for every pixel it processes.

---

**Why is the triangle the universal primitive for GPU rendering?**

Any three points always lie in a single plane, which is not true of four points or more. That coplanarity makes rasterizing a triangle a simple, predictable operation, and decades of GPU development have pushed it to the hardware limit of optimization.

```txt
┌────────────────────┬────────────────────────────┐
│ Shape              │ Triangles at the GPU level │
├────────────────────┼────────────────────────────┤
│ A 2D sprite        │ 2                          │
├────────────────────┼────────────────────────────┤
│ A complex 3D model │ thousands                  │
└────────────────────┴────────────────────────────┘
```

Every shape therefore turns into a set of triangles at the GPU level. A 2D sprite is made of two of them, a complex 3D model of thousands.

---

**How do you handle WebGL context loss in production?**

Listen for the `webglcontextlost` event and call `event.preventDefault()` inside the handler. Without that call the browser will not even attempt to restore the context. Stop the render loop with `cancelAnimationFrame()` as well, because the context is invalid right now.

```javascript
const canvas = document.querySelector('canvas');
let rafId = requestAnimationFrame(render);

canvas.addEventListener('webglcontextlost', (e) => {
  e.preventDefault();       // without this there will be no restore at all
  cancelAnimationFrame(rafId);
});

canvas.addEventListener('webglcontextrestored', () => {
  rebuildSceneResources();  // programs, buffers and textures are all gone
  rafId = requestAnimationFrame(render);
});

function render() { /* draw one frame, then schedule the next */ }
function rebuildSceneResources() { /* re-upload everything from source data */ }
```

On `webglcontextrestored`, rebuild every GPU resource from scratch: shader programs, buffers, textures. Simply resuming the render loop is not enough, because every previous GPU object died together with the context.

Real production readiness means keeping the source data and URLs needed to rebuild the whole scene. The GPU identifiers themselves are worthless after the loss, so holding on to them alone leaves you with nothing to rebuild from.

## Group 4: Pixi.js

**What's the difference between Texture and BaseTexture in Pixi, and why does it matter for sprite atlases?**

`BaseTexture` is the actual pixels uploaded to GPU memory. It is one GPU texture, and it is the heavier of the two units. `Texture` is a window into a region of a `BaseTexture`, that is, a rectangle inside it. Many `Texture` objects can point at one `BaseTexture` without a re-upload.

```txt
┌──────────────────────────────────────────┐
│ BaseTexture                              │
│ the pixels, uploaded to GPU memory once  │
├──────────────────────────────────────────┤
│ Texture #1 — a rectangle inside it       │
│ Texture #2 — another rectangle           │
│ Texture #3 ... dozens more, no re-upload │
└──────────────────────────────────────────┘
```

That relationship is what makes a sprite atlas a batching mechanism. One large PNG (portable network graphics) file becomes one `BaseTexture` and is sliced into dozens of `Texture` objects. The batch renderer can then draw all of those sprites in one draw call, because the GPU never has to swap texture units between them.

---

**What breaks Pixi's batch renderer, and how do you architect a scene to minimize draw calls?**

A batch breaks whenever two neighbours in draw order need a different GPU state. Three things cause that.

| What breaks a batch | Why it breaks it |
|---|---|
| A `BaseTexture` swap between neighbours | the GPU has to bind another texture |
| A filter in the middle of the draw order | it renders into a temporary render texture |
| A blend mode change between neighbours | the GPU state changes between the two |

The architectural fixes follow from that list:

- Group sprites that share a texture next to each other in draw order, wherever the z-order allows it.
- Limit the number of distinct filters in one scene.
- For very large counts of simple, uniform sprites, use `ParticleContainer`. It trades away some flexibility for maximum batching throughput.

---

**Why is `Graphics` in Pixi more expensive to update every frame than `Sprite`?**

Updating a `Sprite` only changes a matrix, while updating a `Graphics` rebuilds geometry.

| Operation | `Sprite` | `Graphics` |
|---|---|---|
| Move, rotate, scale | a transform-matrix change | a transform-matrix change |
| `clear()` and draw again | not needed at all | regenerates the vertex buffer |

Moving, rotating or scaling a `Sprite` is cheap, because the geometry and the texture already exist. Calling `clear()` on a `Graphics` and drawing again rebuilds its geometry, and that is noticeably more expensive than a plain transform change.

The rule follows directly:

- Use `Graphics` for static or rarely changing shapes.
- For shapes that genuinely redraw every frame in large numbers, use a `Sprite` with a pre-baked texture.
- Or cache the `Graphics` result into a `RenderTexture` once, and draw that afterwards.

## Group 5: three.js

**Why do you need to call `camera.updateProjectionMatrix()` after changing camera properties?**

Changing `camera.aspect`, or `fov`, `near`, `far`, does not recompute the projection matrix by itself. The matrix stays stale until you ask for an explicit recompute.

```javascript
const camera = new THREE.PerspectiveCamera(75, 1, 0.1, 1000);
const renderer = new THREE.WebGLRenderer();

function onResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();  // without this the image stays distorted
  renderer.setSize(window.innerWidth, window.innerHeight);
}
window.addEventListener('resize', onResize);
```

Forgetting `updateProjectionMatrix()` after a window resize is a classic bug, and it produces a stretched or distorted image. The aspect ratio changed in the camera's data, but the projection actually used at render time still matches the old ratio.

---

**What is the "model looks washed out" bug, and what causes it?**

The cause is a color space mismatch, not the model and not the lighting. Textures are usually stored in sRGB, which is gamma-encoded for how a display is perceived. A renderer's lighting math, however, is only correct in linear space.

| Setting | What it tells three.js |
|---|---|
| `texture.colorSpace = THREE.SRGBColorSpace` | this color texture is stored in sRGB |
| `renderer.outputColorSpace` | which space the finished image goes out in |

So three.js has to know the encoding of every texture, and it needs its output configured correctly as well. When the two disagree, sRGB decoding happens twice or does not happen at all. The visible result is a flat, washed-out or unnaturally high-contrast image.

---

**Why is `dispose()` necessary in three.js, and what's the classic memory leak scenario?**

GPU resources — geometry, materials, textures — are not released by JS garbage collection the way ordinary objects are. The wrapper JS object can be collected while the GPU memory allocated for it stays held, until `dispose()` is called explicitly.

```javascript
// scene.clear() only detaches objects; their GPU memory stays allocated
function releaseScene(scene) {
  scene.traverse((obj) => {
    obj.geometry?.dispose();
    obj.material?.map?.dispose();
    obj.material?.dispose();
  });
  scene.clear();
}
```

The classic leak is a route change in an SPA (single-page application) that loads a new 3D model without releasing the previous scene. Calling `scene.clear()` is not releasing it: that only removes objects from the scene.

GPU memory then grows with every model switch until the tab crashes. It shows up most clearly in product configurators, where users switch variants over and over.

---

**Explain the difference between `MeshBasicMaterial`, `MeshPhongMaterial`, and `MeshStandardMaterial`.**

The three differ in how they treat light, and that is also the order of their cost.

| Material | Lighting | Look | Typical use |
|---|---|---|---|
| `MeshBasicMaterial` | unlit, ignores lights | flat color or texture | cheapest; 3D interface elements |
| `MeshPhongMaterial` | lit, specular per pixel | shiny plastic | the classic highlight look |
| `MeshStandardMaterial` | lit, physically based | realistic | the modern default |

`MeshBasicMaterial` ignores light sources entirely and shows a flat color or texture. It is the cheapest option, and it suits UI (user interface) elements drawn in 3D or a deliberately stylized look.

`MeshPhongMaterial` is lit and computes specular highlights per pixel, which gives the familiar "shiny plastic" surface.

`MeshStandardMaterial` uses PBR (physically based rendering). It models a material through roughness and metalness, based on an approximation of real light physics rather than an arbitrary highlight formula. The result is more realistic and stays consistent across different lighting setups, which is why it is the modern default for realistic scenes.

## Group 6: SVG, `D3`, and Technology Selection

**What is d3.js actually, and what's the common misconception about it?**

The misconception is treating d3 as a 3D library, because the name sounds like "three.js", or as a charting library above all. The two libraries are entirely unrelated tools.

In reality `D3` stands for "Data-Driven Documents": a collection of small, independent modules.

- `d3-selection` — DOM manipulation that is aware of the data bound to nodes.
- `d3-scale` — pure functions from a data domain to a visual range.
- `d3-shape` — pure functions from data to shape geometry.
- `d3-axis` and a dozen others.

The key detail is that `d3-scale` and `d3-shape` are renderer-agnostic. They do not care whether the result ends up in an SVG `<path>` or in canvas calls made through `.context(ctx)`.

---

**How do you decide between SVG, Canvas 2D, and WebGL for a data visualization?**

Data volume decides first, and the requirements decide the rest.

| Technology | Data volume | What you get, and what it costs |
|---|---|---|
| SVG | up to ~1-2 thousand elements | accessibility, CSS styling, crispness at any zoom |
| Canvas 2D | 10,000+ points | no DOM overhead, but manual hit detection |
| WebGL, Pixi | 100,000+ points | the only option left when canvas hits its ceiling |

Choose SVG when accessibility, CSS styling, crispness at any zoom and rich per-element interactivity matter. Every SVG element is a real DOM node with real overhead, which is what limits the element count.

Choose Canvas 2D from about 10,000 points, where the DOM node count alone would become the bottleneck. You pay for it with more manual hit detection and with no retained-mode scene out of the box.

Choose WebGL or Pixi from about 100,000 points, or for high-frequency real-time updates. That is the range where even the CPU rasterization of canvas hits a ceiling.

## Group 7: Architecture, Performance, and Debugging

**Debugging scenario: a Pixi-based promo page drops to 20 fps on a mid-range Android phone but runs at 60 fps on your desktop. Walk through your diagnosis.**

Reproduce the problem first, then work through five checks in order.

1. **Reproduce it with throttling on.** Turn on CPU and network throttling in DevTools instead of judging by eye on powerful hardware.
2. **Record a Performance session and decide CPU or GPU.** The table below shows how to read the result.
3. **Check the Layers panel and the GPU metrics.** Look for layer explosion and oversized textures. On mobile, where CPU and GPU share memory, full-screen layers cost noticeably more than on desktop.
4. **Check whether `devicePixelRatio` is capped.** Rendering at full retina resolution is often the single most expensive line in mobile rendering.
5. **Check the Pixi scene itself.** Look for broken batching: texture swaps outside a shared atlas, extra filters. Then look for new textures or render textures created inside the render loop without `destroy()`.

| What you observe in step 2 | What it means |
|---|---|
| Fewer entities in JS, same frame time | the problem is not on the CPU side |
| Simpler shaders or lower resolution, faster frames | the problem is on the GPU side |

That last item in step 5 is a GPU memory leak, and it gets worse over the course of a session. What separates systematic diagnosis from guessing is exactly this sequence of specific checks, rather than general intuition.

---

**Why should you extract pure update logic away from drawing code, and how does that affect testing strategy?**

Split `update` from `draw`, and each half becomes testable by a different method. The `update` half holds pure logic: physics, game rules, scale calculations. `draw` is the only place that touches `ctx`.

| Layer | How you test it |
|---|---|
| `update`, pure logic | ordinary unit tests, with no canvas and no DOM |
| `draw`, touches `ctx` | visual regression against a baseline image |
| A mock of `ctx` | an anti-pattern, see below |

Ordinary unit tests cover `update` completely, because nothing has to be rendered to run them. Drawing has no simple "check one value", so visual regression testing takes over. Screenshots are compared against a baseline pixel by pixel, which catches unintended visual regressions that unit tests structurally cannot catch.

Mocking `ctx` and asserting which methods were called with which arguments is an anti-pattern. It is a brittle test of the implementation, and it breaks on any drawing refactor even when the visual result is identical.
