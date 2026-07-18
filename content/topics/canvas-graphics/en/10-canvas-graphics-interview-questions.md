# Canvas & Graphics — Interview Questions (Middle → Senior)

## Group 1: Canvas 2D Fundamentals

**What's the difference between immediate mode and retained mode, and why does it matter for canvas?**

Retained mode (DOM, SVG) means the browser keeps a structure of objects (a node tree), and when an object's property changes, the browser figures out what to repaint on its own. Immediate mode (Canvas 2D) means drawn pixels remember nothing about themselves: calling `ctx.fillRect(...)` colors pixels right now, and after that, as far as canvas is concerned, they're just colored pixels, indistinguishable from any other colored pixels. The only way to change anything is to redraw everything (or the part that changed) from scratch. This is why any canvas animation has to be built around an explicit "clear → update state → redraw" cycle — unlike CSS/WAAPI, where the browser manages repainting for you when a property changes.

---

**Why does canvas look blurry on retina displays, and how do you fix it?**

A canvas has two independent sizes: `canvas.width`/`canvas.height` (the actual backing store size, in pixels) and `canvas.style.width`/`style.height` (the CSS size on the page). If you don't set these separately, they both end up equal to the same number of CSS pixels — and on a display with `devicePixelRatio: 2`, the browser has to stretch (upscale) the buffer to twice as many physical pixels, producing visible blur. The fix: set the backing store to `rect.width * dpr`/`rect.height * dpr`, keep the CSS size unchanged via `style.width`/`style.height`, and call `ctx.scale(dpr, dpr)` so the rest of your drawing code stays in familiar "logical" coordinates.

---

**What's the difference between `clearRect()` and assigning `canvas.width = canvas.width`?**

`clearRect(x, y, w, h)` makes an area transparent without touching anything else in the context's state (transform, styles, clip region). Assigning `canvas.width` (even to the same value) fully RESETS the context as a side effect — not just clearing pixels, but also zeroing out the transform, styles, and every other bit of state. This often gets used implicitly (resizing a canvas by changing `width`) and surprises developers who expected only the image to "disappear," not, say, an accumulated transform.

---

**Explain the nonzero and evenodd fill rules. When can a "donut" shape (a circle with a hole) render as solid, with no hole?**

When a path contains multiple sub-contours (say, the outer and inner circle of a "donut"), the browser decides which regions to fill based on the fill rule. `nonzero` (the default) counts, for each point, how many times the contour "winds" around it, taking direction into account — if the count isn't zero, the point is filled. If both contours of the "donut" are wound in the SAME direction (both clockwise), their contributions don't cancel out, and `nonzero` fills the inner circle too — the hole disappears. The fix: make the directions opposite (the `anticlockwise` parameter of `arc()`), or explicitly use `fill('evenodd')`, which just counts the parity of ray-contour intersections, ignoring direction.

## Group 2: Canvas Animation and Pixels

**Why must a hand-rolled game loop use delta time, and what's the difference between fixed and variable timestep?**

Moving by a fixed step per frame (`x += 2`) gives a speed that depends on display refresh rate — twice as fast at 120 Hz as at 60 Hz, with identical code. Delta time turns that step into "units per second," removing the dependency. A variable timestep (delta time differs every frame) is fine for visual animation, but it causes real problems for physics: a spike in `dt` can cause "tunneling" (a fast object skips through an obstacle in one large step), and the simulation physically behaves differently across devices. A fixed timestep with an accumulator fixes this: physics always steps forward in identical small chunks regardless of the actual frame rate, and the "leftover" time between steps is used to interpolate the visual position.

---

**What are the three approaches to hit detection on canvas, and when would you use each?**

Math-based (AABB/circle) — the cheapest, for simple shapes, used in the vast majority of real code. `isPointInPath()`/`isPointInStroke()` — asking the context itself whether a point falls inside an accumulated path, convenient for irregular shapes already described as a canvas path. Color-picking on a hidden canvas — every object is drawn in a solid, unique color onto an invisible offscreen canvas, and a click reads the pixel color under the cursor — an exact solution for complex, overlapping, arbitrarily irregular shapes, at the cost of an extra render pass on every scene change.

---

**Why is `getImageData` an expensive operation, and how do you mitigate that cost?**

Canvas 2D can render with GPU acceleration, and requesting raw pixels on the CPU forces a synchronization: the browser has to wait for the GPU's current work to finish and copy the buffer from GPU memory into ordinary process memory — a sync point that can cost real time in a hot loop (calling it every animation frame is a common cause of an FPS drop). The `willReadFrequently: true` hint, passed when getting the context, tells the browser to keep the buffer in CPU-accessible memory from the start, avoiding repeated GPU→CPU copies.

---

**Describe how you'd implement a scratch-card effect using compositing.**

Three layers of logic: (1) a base layer — the content hidden under the "foil" (prize text, an image); (2) a "foil" layer on top, drawn with ordinary `source-over`; (3) as the cursor moves with the button held down — switching `globalCompositeOperation` to `destination-out` before drawing the brush stroke: the new shape ERASES existing pixels instead of drawing over them, creating "holes" in the foil layer through which the base layer shows. That's the complete working mechanic, with no additional libraries needed.

---

**What's the tainted canvas security restriction, and how do you avoid it?**

If an image from a different origin is drawn onto a canvas without correct CORS headers, the canvas gets marked "tainted" — the browser blocks any subsequent reading of its pixel data (`getImageData`, `toDataURL`, `toBlob`) with a `SecurityError`. This defends against using canvas as an oracle to steal private cross-origin image content. To avoid it: set `img.crossOrigin = 'anonymous'` ON THE CLIENT and make sure the image's server sends the `Access-Control-Allow-Origin` header — both conditions are required simultaneously; client-side `crossOrigin` alone isn't enough.

## Group 3: WebGL and GPU Fundamentals

**What is a draw call, and why does minimizing their count matter more than minimizing triangle count?**

A draw call is a command: "draw these vertices with this shader program, these buffers/uniforms/texture." Its cost is mostly driver overhead (validating state, synchronizing CPU↔GPU, uploading whatever data changed) — NOT the number of triangles inside it. Drawing 10,000 triangles in one draw call is almost always cheaper than 100 triangles across 100 separate draw calls with a texture/shader swap between them — which is exactly why batching (combining many objects into the smallest number of draw calls) is the central performance topic in both Pixi and three.js.

---

**Explain the difference between the vertex shader and fragment shader stages.**

The vertex shader runs once PER VERTEX of a piece of geometry and answers "where will this point end up on screen" (its output is `gl_Position`). Between the two stages is rasterization (the only non-programmable one): the GPU determines which pixels a triangle covers, and linearly interpolates varying values between vertices. The fragment shader runs once PER COVERED PIXEL and answers "what color is this specific pixel" (its output is `gl_FragColor`).

---

**What's the difference between an attribute, a uniform, and a varying?**

An `attribute` is data unique to EACH vertex (position, UV, per-vertex color), read by the vertex shader. A `uniform` is a SINGLE value, the same for ALL vertices/pixels in one draw call (a transform matrix, an animation time value, a shared color). A `varying` is the bridge between the vertex and fragment shader: a value output by the vertex shader that gets automatically, LINEARLY INTERPOLATED by rasterization between vertices, for every pixel the fragment shader processes.

---

**Why is the triangle the universal primitive for GPU rendering?**

Any three points always lie in a single plane (they're coplanar), unlike four or more points, which may not be. This makes rasterizing a triangle a simple, predictable operation that's been pushed to the hardware limit of optimization over decades of GPU development. Any shape — from a 2D sprite (two triangles) to a complex 3D model (thousands of triangles) — turns into a set of triangles at the GPU level.

---

**How do you handle WebGL context loss in production?**

Listen for the `webglcontextlost` event and be sure to call `event.preventDefault()` inside the handler — without it, the browser won't even attempt to restore the context. Stop the render loop (`cancelAnimationFrame`), since the context is invalid right now. On `webglcontextrestored`, fully REBUILD every GPU resource (shader programs, buffers, textures) rather than just "resuming" rendering, because all previous GPU objects were destroyed along with the context. For genuine production readiness, keep the source data/URLs needed to fully rebuild the scene on hand ahead of time, not just the (now-invalid) GPU identifiers themselves.

## Group 4: Pixi.js

**What's the difference between Texture and BaseTexture in Pixi, and why does it matter for sprite atlases?**

`BaseTexture` is the actual pixels uploaded to GPU memory (one GPU texture — the "heaviest" unit). `Texture` is a "window" into a region of a `BaseTexture` (a rectangle inside it); many `Texture` objects can point to ONE `BaseTexture` without a re-upload. This is exactly what makes sprite atlases a batching mechanism: one large PNG (one `BaseTexture`) gets sliced into dozens of `Texture`s, and the batch renderer can combine drawing all of those sprites into one draw call, because the GPU doesn't need to swap texture units between them.

---

**What breaks Pixi's batch renderer, and how do you architect a scene to minimize draw calls?**

What breaks it: a `BaseTexture` swap between sprites adjacent in draw order (if they aren't from the same atlas); a filter on any object in the middle of the draw order (requires rendering into a temporary render texture, interrupting the batch); a blend mode change between adjacent objects. Architectural fixes: group sprites sharing a texture next to each other in draw order wherever z-order allows; limit the number of distinct filters in a scene; for very large counts of simple, uniform sprites, use `ParticleContainer`, which trades away some flexibility for maximum batching throughput.

---

**Why is `Graphics` in Pixi more expensive to update every frame than `Sprite`?**

Moving/rotating/scaling a `Sprite` is cheap — it's just a transform-matrix change over geometry and a texture that already exist. `Graphics`, when you call `clear()` and draw again, REBUILDS its geometry (regenerates the vertex buffer) — an operation noticeably more expensive than a plain transform change. The rule: use `Graphics` for static or infrequently-changing shapes; for shapes that genuinely need to redraw every frame in large numbers, use a `Sprite` with a pre-baked texture, or cache the `Graphics` result into a `RenderTexture` once.

## Group 5: three.js

**Why do you need to call `camera.updateProjectionMatrix()` after changing camera properties?**

Changing `camera.aspect` (or `fov`, `near`, `far`) does NOT, by itself, recompute the projection matrix — it stays stale until an explicit recompute is called. Forgetting `updateProjectionMatrix()` after a window resize is a classic bug producing a stretched/distorted image: the aspect ratio changed in the camera's data, but the actual projection used at render time still corresponds to the old ratio.

---

**What is the "model looks washed out" bug, and what causes it?**

Textures are usually stored in sRGB color space (gamma-encoded for display perception), but a renderer's lighting math is only correct in linear space. three.js needs to know each texture's encoding (`texture.colorSpace = THREE.SRGBColorSpace` for color textures) and needs correctly configured output (`renderer.outputColorSpace`). A mismatch between these settings (double sRGB decoding, or none at all) produces a visually washed-out, flat, or unnaturally contrasty result — not a problem with the model or the lighting themselves, but specifically with the color spaces on the input and output sides.

---

**Why is `dispose()` necessary in three.js, and what's the classic memory leak scenario?**

GPU resources (geometry, materials, textures) aren't released automatically by JS garbage collection the same way ordinary objects are — the wrapper JS object can be collected while the GPU memory allocated for it stays held until `dispose()` is explicitly called. The classic leak scenario: loading a new 3D model on a route change in an SPA WITHOUT releasing the previous scene's geometry/materials/textures (`scene.clear()` removes objects from the scene but doesn't release their GPU resources) — GPU memory grows with every model switch until the tab crashes, especially noticeable in product configurators where users switch variants frequently.

---

**Explain the difference between `MeshBasicMaterial`, `MeshPhongMaterial`, and `MeshStandardMaterial`.**

`MeshBasicMaterial` is unlit — it entirely ignores light sources, just a flat color/texture — the cheapest option, for 3D UI elements or a deliberately stylized look. `MeshPhongMaterial` is lit, with specular highlights computed per pixel — the classic "shiny plastic" look. `MeshStandardMaterial` is PBR (Physically Based Rendering), modeling a material via roughness/metalness parameters based on an approximation of real-world light physics rather than an arbitrary highlight formula — it produces a more realistic and consistent result across different lighting setups, and is the modern default for realistic scenes.

## Group 6: SVG, D3, and Technology Selection

**What is d3.js actually, and what's the common misconception about it?**

The misconception is treating d3 as a 3D library (because it sounds like "three.js," even though they're two entirely unrelated tools) or primarily as a charting library. In reality, D3 stands for "Data-Driven Documents," a collection of small, independent modules: `d3-selection` (DOM manipulation aware of bound data), `d3-scale` (pure functions: a data domain → a visual range), `d3-shape` (pure functions: data → shape geometry), `d3-axis`, and others. The key detail: `d3-scale`/`d3-shape` are entirely renderer-agnostic — they don't care whether the result ends up in an SVG `<path>` or in canvas calls via `.context(ctx)`.

---

**How do you decide between SVG, Canvas 2D, and WebGL for a data visualization?**

The guideline is data volume and requirements: SVG for up to ~1-2 thousand elements, when accessibility, CSS styling, crispness at any zoom, and rich per-element interactivity matter (every SVG element is a real DOM node with real overhead). Canvas 2D for 10,000+ points, where DOM node count alone would become the bottleneck, at the cost of more manual hit detection and no retained-mode scene out of the box. WebGL/Pixi for 100,000+ points, or high-frequency real-time updates, where even canvas's CPU rasterization hits a ceiling.

## Group 7: Architecture, Performance, and Debugging

**Debugging scenario: a Pixi-based promo page drops to 20fps on a mid-range Android phone but runs at 60fps on your desktop. Walk through your diagnosis.**

Sequence: (1) reproduce the problem with CPU/network throttling enabled in DevTools, instead of diagnosing by eye on powerful hardware; (2) record a session in the Performance panel and determine whether the problem is CPU-bound or GPU-bound — if reducing the entity count in JS doesn't reduce frame time, but lowering shader complexity/resolution does, it's on the GPU side; (3) check Layers/GPU-specific metrics for layer explosion or oversized textures — on mobile with shared CPU/GPU memory, full-screen layers create noticeably more load than on desktop; (4) check whether `devicePixelRatio` is capped — rendering at full retina resolution is often the single most expensive line in mobile rendering; (5) in the Pixi scene itself — check whether batching is broken (texture swaps outside a shared atlas, extra filters), and whether new textures/render textures are being created in the render loop without `destroy()` (a GPU memory leak that gets worse over the course of a session). This sequence of specific checks, rather than general guesswork, is what separates systematic diagnosis from guessing.

---

**Why should you extract pure update logic away from drawing code, and how does that affect testing strategy?**

Separating `update` (pure logic: physics, game rules, scale calculations) from `draw` (the only place touching `ctx`) lets you test `update` with ordinary unit tests, with no canvas or DOM involved at all. For the drawing itself, where there's no simple "check one value," visual regression testing (screenshot diffing, comparing a render against a baseline pixel-by-pixel) catches unintended visual regressions that unit tests structurally can't catch. Mocking `ctx` itself and asserting "which methods were called with which arguments" is an anti-pattern: it's a brittle test of implementation, breaking on any drawing refactor even when the visual result is identical.
