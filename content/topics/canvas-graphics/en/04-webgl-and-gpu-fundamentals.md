# WebGL and GPU Fundamentals

## Why bother, when you'll almost always use Pixi or three.js

Answering "why did adding one more filter in Pixi slow the scene down this much" or "why is swapping a texture between sprites more expensive than it looks" requires understanding WHAT actually happens under the hood of any GPU engine — Pixi (article 05) and three.js (article 06) don't invent their own rendering model, they just wrap exactly what this article describes in a convenient shell. Without this foundation, working with either library comes down to copying examples from the docs "because that's how it works"; with it, it becomes engineering decisions grounded in the real cost of each operation.

## Why GPU rendering is fast: massive parallelism

A CPU has a handful (usually 4-16) of powerful cores, each able to run complex, branching logic quickly and sequentially. A GPU is built on a fundamentally different model: thousands of simple compute cores, each executing the EXACT SAME small program simultaneously over different data — the classic SIMD model (single instruction, multiple data). This maps perfectly onto rendering: "compute the on-screen position for EVERY one of a million vertices," or "compute the color of EVERY one of two million pixels" — these operations are independent of each other and computationally identical, differing only in their input data. That independence is exactly what lets the work spread across thousands of cores instead of being processed sequentially on a CPU.

**The triangle is the universal primitive** of GPU rendering for a specific reason: any three points ALWAYS lie in a single plane (unlike four or more points, which may not be coplanar), so rasterizing a triangle is a simple, predictable operation that's been pushed to the limit of hardware acceleration for decades. Any shape — from a 2D sprite in Pixi (a rectangle is two triangles) to a complex 3D model in three.js (thousands of triangles forming a surface) — turns into a set of triangles at the GPU level.

## The programmable pipeline: vertex shader → rasterization → fragment shader

```txt
Vertex Shader                 Rasterization              Fragment Shader
(programmable)                (fixed-function,           (programmable)
                                NOT programmable)

Input: vertex attributes      Input: the triangle's        Input: interpolated
  (position, UV, ...)           screen-space vertex           per-pixel values +
  + uniform variables            positions                    textures + uniforms
Output: an on-screen position  Output: a list of            Output: the final pixel
  (gl_Position)                  "fragments" (candidate         color (gl_FragColor)
  ONCE PER VERTEX                 pixels) inside the             ONCE PER PIXEL
                                  triangle, carrying
                                  interpolated "varying" values
```

The **vertex shader** runs once per piece of geometry's vertex and answers "where does this point end up on screen." **Rasterization** is the only NON-programmable stage of the pipeline: fixed GPU hardware logic figures out which pixels are covered by a triangle and linearly interpolates any "varying" values (UV coordinates, per-vertex color, etc.) between the three vertices for each covered pixel — this is exactly why a gradient between three differently-colored triangle vertices "just works," with no extra code needed. The **fragment shader** runs once per covered pixel ("fragment") and answers "what color is this specific pixel."

## GLSL: a minimal, readable example

Shaders are written in GLSL (OpenGL Shading Language) — a C-like language with built-in vector types (`vec2`, `vec3`, `vec4`) and matrix types (`mat3`, `mat4`).

```glsl
// Vertex shader — computes the on-screen position and forwards the UV
attribute vec2 position;   // attribute: a distinct value per VERTEX
attribute vec2 uv;
uniform mat3 transform;     // uniform: ONE value for the whole draw call
varying vec2 vUv;           // varying: passed to the fragment shader,
                             // interpolated between vertices during rasterization

void main() {
  vUv = uv;
  vec3 transformed = transform * vec3(position, 1.0);
  gl_Position = vec4(transformed.xy, 0.0, 1.0); // a required built-in variable
}
```

```glsl
// Fragment shader — turns the interpolated UV into a color gradient
precision mediump float; // a required precision directive —
                          // mediump is plenty for most cases and
                          // noticeably cheaper on mobile GPUs than highp

varying vec2 vUv; // the same coordinates that left the vertex shader,
                   // now interpolated by rasterization for the
                   // CURRENT pixel inside the triangle

void main() {
  // The red channel grows left to right, the green channel top to
  // bottom — the simplest possible 2D gradient, computed on the GPU
  // for every pixel
  gl_FragColor = vec4(vUv.x, vUv.y, 0.5, 1.0); // a required built-in variable
}
```

The key interview detail: `varying` is the BRIDGE between the vertex and fragment shader, where rasterization performs the linear interpolation between vertices automatically; `uniform` is a single value that's the same for ALL vertices/pixels in one draw call (say, a shared transformation matrix, or an animation time value); `attribute` is data unique to each individual vertex (position, UV, per-vertex color).

## The data that reaches the GPU: buffers, attributes, uniforms, textures

```txt
Buffer     — a raw block of GPU memory holding vertex data (positions,
              UVs, normals...), uploaded once, reusable across many
              draw calls without re-sending the data
Attribute  — HOW the vertex shader reads its slice of a buffer for
              the current vertex (what offset, what data format)
Uniform    — a single value for the whole draw call, the same for
              every vertex/pixel (a transform matrix, a color, time)
Texture    — an image the fragment shader samples for a color by UV
              coordinate, via a sampler2D + texture2D()/texture() call
```

This data model isn't abstraction for its own sake — it directly explains why geometry buffers are worth creating once and reusing (unlike uniforms, which are expected to change every draw call), and why swapping a texture between draws is a real, costly operation rather than a free detail.

## The draw call: the real currency of GPU performance

A **draw call** is a single command: "render these vertices with this shader program, these buffers, these uniforms, and this texture." A key, not always obvious fact: a draw call's cost is mostly **driver overhead** (validating state, synchronizing CPU↔GPU, uploading whatever data changed) — NOT the number of triangles inside it. Drawing 10,000 triangles in ONE draw call is almost always cheaper than drawing 100 triangles across 100 separate draw calls that swap texture/shader/blend mode between each one.

```txt
❌ 100 separate draw calls (say, 100 sprites with different textures,
   each drawn one at a time): 100× the driver overhead for state
   validation and synchronization, regardless of the total geometry
   being tiny

✅ 1 draw call with a shared texture "atlas" (article 05, sprite
   atlases) and one buffer holding the geometry of all 100 sprites:
   the same visual result, at roughly 1/100th the driver overhead
```

That's exactly why **batching** (combining many objects into the smallest possible number of draw calls) is the central performance topic in both Pixi (article 05, the batch renderer and what "breaks" it) and three.js (article 06, instancing/merging geometries): the real performance ceiling in most 2D/UI-heavy scenes isn't triangle count — it's draw call count.

## Why raw WebGL is so verbose

A "hello triangle" — the simplest possible example, drawing one colored triangle — in raw WebGL requires: writing the vertex and fragment shader's GLSL source as strings, compiling and linking them into a shader program with manual compile-error checking, creating and filling a geometry buffer, manually describing the attribute layout (byte offsets and strides), looking up uniform variable locations by name and assigning their values, and only then calling `drawArrays`/`drawElements`. Typically that's several dozen lines of low-level setup — none of which describes "what to draw," only HOW to get that data to the GPU. The same triangle in three.js is roughly ten lines, because all of that setup is encapsulated inside `Mesh`/`Geometry`/`Material` (article 06). This is the direct explanation for why engines on top of WebGL exist at all — not "for convenience," but because the sheer volume of required boilerplate for any substantial scene otherwise becomes unmanageable.

## WebGL1 vs. WebGL2 — in one paragraph

WebGL1 is based on OpenGL ES 2.0; WebGL2 is based on OpenGL ES 3.0, adding: native instancing support (no extensions that might be missing, as in WebGL1), multiple render targets, 3D textures, uniform buffer objects, and a newer GLSL ES version (3.00) with more language features. In practice: modern engines target WebGL2 by default, falling back to WebGL1 where necessary; browser support for WebGL2 is essentially universal now, so there's rarely a reason to deliberately limit a new project to WebGL1's feature set.

## WebGPU: what changes, and current adoption status

WebGPU isn't "WebGL 3" — it's a new API, modeled on modern low-level graphics APIs (Vulkan, Metal, Direct3D 12). The key difference: WebGL was historically designed with a lot of IMPLICIT, hidden-from-the-developer state validation happening on every call by the driver — convenient, but expensive in CPU overhead. WebGPU shifts a large share of that work to an EXPLICIT, up-front setup phase (building whole render pipeline objects ahead of time, instead of accumulating state call by call), which lowers per-frame CPU overhead and lets you hand the GPU noticeably more draw calls for the same CPU cost. Separately, WebGPU provides full-fledged **compute shaders** — programs run on the GPU for GENERAL-purpose computation (not just rendering: physics, machine learning, data processing), something WebGL essentially never offered.

Support status as of this writing: WebGPU is already available in some major browsers, but not universally everywhere; before committing to WebGPU as the only path for a production project, it's worth explicitly checking current support across your target browsers/devices — this is a fast-moving area, and relying on memory instead of verifying is a genuine risk here.

## Context loss: the thing everyone forgets until the first real incident

A GPU context can be lost at any moment for reasons entirely outside your code's control: a graphics driver reset or crash, the OS reclaiming GPU resources under memory pressure, another tab monopolizing the GPU, a mobile app being backgrounded and foregrounded. Production code MUST handle this explicitly:

```javascript
canvas.addEventListener('webglcontextlost', (event) => {
  event.preventDefault(); // WITHOUT this, the browser won't even attempt to restore the context
  cancelAnimationFrame(animationFrameId); // stop the render loop —
                                            // the context is invalid right now
  console.warn('WebGL context lost — waiting for restoration');
});

canvas.addEventListener('webglcontextrestored', () => {
  // CRITICAL: every GPU resource (buffers, textures, shader programs)
  // was destroyed along with the context — they need to be rebuilt
  // FROM SCRATCH, not just "resumed"
  initShaders();
  initBuffers();
  reloadTextures();
  startRenderLoop();
});
```

Without `event.preventDefault()` in the `webglcontextlost` handler, the browser won't even try to restore the context — the scene stays a black screen permanently. Without fully rebuilding resources in `webglcontextrestored`, attempts to draw with buffers/textures using old (now-invalid) identifiers will silently fail or throw errors. This is an especially common scenario on mobile devices with constrained GPU memory — and one of the least-tested paths until the first real production incident.

## Connection to other articles

```txt
[Pixi.js in Depth]                    — a retained-mode scene built on
                                         top of exactly this pipeline; the
                                         batch renderer exists specifically
                                         to minimize the draw calls
                                         described here
[three.js in Depth]                    — Geometry/Material/Mesh is a
                                         convenient wrapper over the
                                         buffer/uniform/shader model from
                                         this article; instancing is a
                                         direct fix for the draw-call problem
[Architecture and Performance for
 Canvas Apps]                          — profiling GPU work and setting
                                         resource budgets both rely on
                                         understanding draw calls, as
                                         covered here
```

## Common interview traps

- **Assuming "more triangles = slower"** — not knowing that real-world cost in most scenes is driven by the NUMBER OF DRAW CALLS (per-call driver overhead), not raw triangle count — rendering a million triangles in one call is often cheaper than a hundred triangles spread across a hundred calls.

- **Confusing the vertex and fragment shader** — being unable to explain that the vertex shader runs once PER VERTEX and decides "where," while the fragment shader runs once PER PIXEL and decides "what color."

- **Not understanding the difference between attribute/uniform/varying** — not knowing that an attribute is data unique to each vertex, a uniform is a single value for the whole draw call, and a varying is the rasterization-interpolated bridge between the vertex and fragment shader.

- **Not understanding why triangles specifically** — not connecting the choice of triangle as the primitive to the fact that any three points are always coplanar, unlike an arbitrary polygon.

- **Not knowing about batching as the fix for the draw-call problem** — proposing to "just reduce the polygon count" when the real problem is the number of separate drawing calls caused by texture/shader swaps between objects.

- **Not knowing about WebGL context loss** — having no answer to "what happens to your WebGL app if the user's graphics driver resets," and not knowing about `webglcontextlost`/`webglcontextrestored` or the need to fully rebuild GPU resources.
