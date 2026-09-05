# WebGL and GPU Fundamentals

## Why bother, when you'll almost always use Pixi or three.js

Because Pixi and three.js are thin wrappers over the model described here. Both talk to the GPU (graphics processing unit) through WebGL (Web Graphics Library), and neither invents its own rendering model. Every performance rule they publish comes from the pipeline this article walks through.

Two questions make that concrete. Why did adding one more filter in Pixi slow the scene down this much? Why is swapping a texture between sprites more expensive than it looks? Neither has an answer at the library level. Pixi is article 05 and three.js is article 06, and both point back here.

Without this foundation, working with either library comes down to copying examples from the docs "because that's how it works". With it, the same choices become engineering decisions grounded in the real cost of each operation.

## Why GPU rendering is fast: massive parallelism

A CPU (central processing unit) has a handful of powerful cores, usually 4-16. Each one runs complex, branching logic quickly and sequentially. A GPU is built on the opposite model: thousands of simple compute cores. Every core executes the **same** small program at the same moment, over different data. That is the classic SIMD model (single instruction, multiple data).

| Property | CPU | GPU |
|---|---|---|
| Cores | a handful, usually 4-16 | thousands of simple ones |
| What a core runs | complex, branching logic | the same small program as every other core |
| How work is processed | quickly, one step after another | simultaneously, over different data |

Rendering fits that model exactly. Take "compute the on-screen position for each of a million vertices". Or "compute the color of each of two million pixels". Both are jobs of the same shape.

Those individual operations are independent of each other and computationally identical, differing only in their input data. That independence is exactly what lets the work spread across thousands of cores instead of being processed sequentially on a CPU.

**The triangle is the universal primitive** of GPU rendering, and for a specific reason. Any three points **always** lie in a single plane, unlike four or more points, which may not be coplanar. So rasterizing a triangle is a simple, predictable operation, and it has been pushed to the limit of hardware acceleration for decades.

Any shape turns into a set of triangles at the GPU level. A 2D sprite in Pixi is a rectangle, which is two triangles. A complex 3D model in three.js is thousands of triangles forming a surface.

## The programmable pipeline: vertex shader → rasterization → fragment shader

```txt
vertex shader  ->  rasterization  ->  fragment shader

1. Vertex shader (programmable)
   in  : vertex attributes (position, UV, ...) + uniform variables
   out : an on-screen position (gl_Position)
   runs: once per vertex

2. Rasterization (fixed-function, not programmable)
   in  : the triangle's screen-space vertex positions
   out : a list of "fragments" (candidate pixels) inside the
         triangle, carrying interpolated "varying" values

3. Fragment shader (programmable)
   in  : interpolated per-pixel values + textures + uniforms
   out : the final pixel color (gl_FragColor)
   runs: once per pixel
```

The **vertex shader** runs once per vertex of the geometry. It answers one question: "where does this point end up on screen."

**Rasterization** is the only stage of the pipeline you cannot program. Fixed GPU hardware logic figures out which pixels are covered by a triangle. For each covered pixel it linearly interpolates the "varying" values between the three vertices: UV (texture coordinates), per-vertex color, and so on.

That interpolation is exactly why a gradient between three differently-colored triangle vertices "just works," with no extra code needed.

The **fragment shader** runs once per covered pixel (a "fragment") and answers "what color is this specific pixel."

## GLSL: a minimal, readable example

Shaders are written in GLSL (OpenGL Shading Language) — a C-like language with built-in vector types (`vec2`, `vec3`, `vec4`) and matrix types (`mat3`, `mat4`).

```glsl
// Vertex shader — computes the on-screen position and forwards the UV
attribute vec2 position;   // attribute: a distinct value per vertex
attribute vec2 uv;
uniform mat3 transform;     // uniform: one value for the whole draw call
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
                   // current pixel inside the triangle

void main() {
  // The red channel grows left to right, the green channel top to
  // bottom — the simplest possible 2D gradient, computed on the GPU
  // for every pixel
  gl_FragColor = vec4(vUv.x, vUv.y, 0.5, 1.0); // a required built-in variable
}
```

The key interview detail is how the three differ:

- `varying` is the **bridge** between the vertex and fragment shader. Rasterization performs the linear interpolation between vertices automatically.
- `uniform` is a single value, the same for every vertex and pixel in one draw call: a shared transformation matrix, or an animation time value.
- `attribute` is data unique to each individual vertex: position, UV, per-vertex color.

## The data that reaches the GPU: buffers, attributes, uniforms, textures

| Concept | What it is |
|---|---|
| Buffer | A raw block of GPU memory holding vertex data: positions, UVs, normals. Uploaded once, then reused across many draw calls without re-sending the data. |
| Attribute | The description of **how** the vertex shader reads its slice of a buffer for the current vertex: what offset, what data format. |
| Uniform | A single value for the whole draw call, the same for every vertex and pixel: a transform matrix, a color, a time value. |
| Texture | An image the fragment shader samples for a color by UV coordinate, through a `sampler2D` plus a `texture2D()`/`texture()` call. |

This data model isn't abstraction for its own sake. It directly explains two costs. Geometry buffers are worth creating once and reusing, unlike uniforms, which are expected to change every draw call. And swapping a texture between draws is a real, costly operation rather than a free detail.

## The draw call: the real currency of GPU performance

A **draw call** is a single command: "render these vertices with this shader program, these buffers, these uniforms, and this texture."

Here is the key and not always obvious fact. A draw call's cost is mostly **driver overhead**: validating state, synchronizing CPU↔GPU, uploading whatever data changed. It is **not** the number of triangles inside the call.

Drawing 10,000 triangles in one draw call is almost always cheaper than drawing 100 triangles across 100 separate draw calls. Those 100 calls swap texture, shader or blend mode between each one, and that is what costs.

```txt
❌ 100 separate draw calls (say, 100 sprites with different textures,
   each drawn one at a time): 100× the driver overhead for state
   validation and synchronization, regardless of the total geometry
   being tiny

✅ 1 draw call with a shared texture "atlas" (article 05, sprite
   atlases) and one buffer holding the geometry of all 100 sprites:
   the same visual result, at roughly 1/100th the driver overhead
```

That's exactly why **batching** matters. Batching means combining many objects into the smallest possible number of draw calls. It is the central performance topic in both engines. In Pixi that is the batch renderer and what "breaks" it (article 05). In three.js it is instancing and merging geometries (article 06).

In most 2D and interface-heavy scenes the real performance ceiling isn't triangle count. It's draw call count.

## Why raw WebGL is so verbose

A "hello triangle" is the simplest possible example: draw one colored triangle. In raw WebGL it takes six setup steps.

1. Write the vertex and fragment shader's GLSL source as strings.
2. Compile and link them into a shader program, checking compile errors by hand.
3. Create a geometry buffer and fill it.
4. Describe the attribute layout manually: byte offsets and strides.
5. Look up uniform variable locations by name and assign their values.
6. Only then call `drawArrays` or `drawElements`.

Typically that's several dozen lines of low-level setup. None of them describes *what* to draw. All of them describe how to get that data to the GPU.

The same triangle in three.js is roughly ten lines, because all of that setup is encapsulated inside `Mesh`/`Geometry`/`Material` (article 06). This is the direct explanation for why engines on top of WebGL exist at all. Not "for convenience": without them, the sheer volume of required boilerplate for any substantial scene becomes unmanageable.

## WebGL1 vs. WebGL2 — the short version

WebGL1 is based on OpenGL ES 2.0, where ES stands for Embedded Systems. WebGL2 is based on OpenGL ES 3.0, and it adds five things on top.

| Feature | WebGL1 | WebGL2 |
|---|---|---|
| Base | OpenGL ES 2.0 | OpenGL ES 3.0 |
| Instancing | only through an extension, which might be missing | native |
| Multiple render targets | no | yes |
| 3D textures | no | yes |
| Uniform buffer objects | no | yes |
| GLSL ES version | older | 3.00, with more language features |

In practice, modern engines target WebGL2 by default and fall back to WebGL1 where necessary. Browser support for WebGL2 is essentially universal now, so there's rarely a reason to deliberately limit a new project to WebGL1's feature set.

## WebGPU: what changes, and current adoption status

WebGPU is the newer browser graphics API that supersedes the WebGL model. It isn't "WebGL 3": it's a new API, modeled on modern low-level graphics APIs such as Vulkan, Metal and Direct3D 12.

The key difference is where state validation happens. WebGL was historically designed with a lot of implicit validation, hidden from the developer and done by the driver on every call. That is convenient, but expensive in CPU overhead.

WebGPU shifts a large share of that work to an explicit, up-front setup phase. You build whole render pipeline objects ahead of time, instead of accumulating state call by call. That lowers per-frame CPU overhead, and it lets you hand the GPU noticeably more draw calls for the same CPU cost.

Separately, WebGPU provides full-fledged **compute shaders**: programs run on the GPU for general-purpose computation, not just rendering. Physics, machine learning and data processing all qualify. WebGL essentially never offered this.

| Aspect | WebGL | WebGPU |
|---|---|---|
| State validation | implicit, done by the driver on every call | explicit, done once when the pipeline object is built |
| Per-frame CPU overhead | higher | lower, so more draw calls fit the same budget |
| Compute shaders | essentially never offered | full-fledged, for general-purpose computation |

Support status as of this writing: WebGPU is already available in some major browsers, but not universally everywhere. Before committing to WebGPU as the only path for a production project, check current support across your target browsers and devices explicitly. This is a fast-moving area, and relying on memory instead of verifying is a genuine risk here.

## Context loss: the thing everyone forgets until the first real incident

A GPU context can be lost at any moment, for reasons entirely outside your code's control:

- A graphics driver reset or crash.
- The OS (operating system) reclaiming GPU resources under memory pressure.
- Another tab monopolizing the GPU.
- A mobile app being backgrounded and then foregrounded.

Production code **must** handle this explicitly:

```javascript
canvas.addEventListener('webglcontextlost', (event) => {
  event.preventDefault(); // without this, the browser won't even
                          // attempt to restore the context
  cancelAnimationFrame(animationFrameId); // stop the render loop —
                                            // the context is invalid right now
  console.warn('WebGL context lost — waiting for restoration');
});

canvas.addEventListener('webglcontextrestored', () => {
  // critical: every GPU resource (buffers, textures, shader programs)
  // was destroyed along with the context — they need to be rebuilt
  // from scratch, not just "resumed"
  initShaders();
  initBuffers();
  reloadTextures();
  startRenderLoop();
});
```

Without `event.preventDefault()` in the `webglcontextlost` handler, the browser won't even try to restore the context. The scene stays a black screen permanently.

Without fully rebuilding resources in `webglcontextrestored`, drawing with buffers and textures that hold old, now-invalid identifiers will silently fail or throw errors. This is an especially common scenario on mobile devices with constrained GPU memory, and one of the least-tested paths until the first real production incident.

## Connection to other articles

- [Pixi.js in Depth](./05-pixijs-in-depth.md) — a retained-mode scene built on top of exactly this pipeline. Its batch renderer exists specifically to minimize the draw calls described here.
- [three.js in Depth](./06-threejs-in-depth.md) — `Geometry`/`Material`/`Mesh` is a convenient wrapper over the buffer/uniform/shader model from this article. Instancing there is a direct fix for the draw-call problem.
- [Architecture and Performance for Canvas Apps](./08-architecture-and-performance-for-canvas-apps.md) — profiling GPU work and setting resource budgets both rely on understanding draw calls, as covered here.

## Common interview traps

- **Assuming "more triangles = slower"** — in most scenes the real cost is driven by the **number of draw calls**, not by raw triangle count. What you pay per call is driver overhead. Rendering a million triangles in one call is often cheaper than a hundred triangles spread across a hundred calls.

- **Confusing the vertex and fragment shader** — being unable to say which one runs when. The vertex shader runs once **per vertex** and decides "where." The fragment shader runs once **per pixel** and decides "what color."

- **Not understanding the difference between attribute, uniform and varying** — an attribute is data unique to each vertex. A uniform is a single value for the whole draw call. A varying is the rasterization-interpolated bridge between the two shaders.

- **Not understanding why triangles specifically** — the choice of the triangle as the primitive follows from one fact. Any three points are always coplanar, unlike an arbitrary polygon.

- **Not knowing about batching as the fix for the draw-call problem** — proposing to "just reduce the polygon count". The real problem is the number of separate drawing calls, caused by texture and shader swaps between objects.

- **Not knowing about WebGL context loss** — having no answer when asked what happens to your WebGL app if the user's graphics driver resets. A second gap is not knowing about `webglcontextlost`/`webglcontextrestored`, or the need to fully rebuild GPU resources.
