# Architecture and Performance for Canvas Apps

## From tools to a production feature

This article is about assembling a real canvas feature inside a real React/Next.js app. Articles 01-07 gave you the tools: primitives, the game loop, pixels, WebGL (Web Graphics Library), Pixi, three.js, SVG (scalable vector graphics) and d3. This is the same level as articles 06-07 in browser-animation, just applied to the canvas world.

A production feature has to clear four bars:

- It doesn't lag on weak hardware.
- It doesn't leak memory over an hour of use.
- It is accessible to more than just sighted mouse users.
- It can be meaningfully tested.

## Canvas as an escape hatch from React's render model

React re-renders components declaratively, based on state and props. Canvas is the opposite: raw canvas, Pixi and three.js are imperative, **stateful** systems. The scene and the buffer live across renders, and they shouldn't be recreated on every React re-render.

The canonical solution is an **imperative core inside a declarative shell**. The scene is created **once**, inside a `useEffect` with an empty dependency array. Changing props are synced into the already-existing "engine" through separate effects that call its methods, never recreating it wholesale.

```tsx
function ParticleCanvas({ color, count }: { color: string; count: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const engineRef = useRef<ParticleEngine | null>(null);

  useEffect(() => {
    engineRef.current = new ParticleEngine(canvasRef.current!);
    engineRef.current.start();
    return () => engineRef.current?.destroy(); // required cleanup on unmount
  }, []); // empty dependency array — the engine is created exactly once

  useEffect(() => {
    engineRef.current?.setColor(color); // sync the prop into the existing
  }, [color]);                            // engine, without recreating it

  useEffect(() => {
    engineRef.current?.setParticleCount(count);
  }, [count]);

  return <canvas ref={canvasRef} />;
}
```

This is exactly the same pattern shown for Pixi's `Application` (article 05) and a three.js scene (article 06). Here it is generalized as the canonical approach for **any** imperative canvas engine inside React:

- Creation inside `useEffect` with empty dependencies.
- Syncing props through separate effects with focused dependency lists.
- A mandatory `destroy()`/`cancelAnimationFrame` in the cleanup function.

## Resolution and scaling strategy

**Capping `devicePixelRatio` on mobile** — the same logic as in three.js (article 06, `renderer.setPixelRatio`), but relevant to **any** canvas rendering. The GPU (graphics processing unit) is the chip that fills pixels, and on a weak mobile one that fill is the bottleneck.

On some phones `devicePixelRatio` is 3, so rendering at full retina resolution is often the single most expensive line in the entire app. Capping to 1.5-2x is visually almost indistinguishable from full resolution, and noticeably cheaper in the actual pixel volume that needs filling (fill-rate).

| `devicePixelRatio` | Pixels to fill, relative to the CSS size |
|---|---|
| 1 | 1× |
| 1.5 | 2.25× |
| 2 | 4× |
| 3 | 9× |

**Dynamic resolution under load** is a technique from "real" real-time graphics that applies just as well on the web. Monitor frame time (see profiling below). When it consistently exceeds budget, adaptively **lower** the internal render resolution and upscale it via the canvas's CSS size. Restore the resolution once load drops.

This is what turns "the hero effect stops dead on a weak phone" into "the hero effect gracefully loses sharpness while staying smooth". For a promo page that is almost always the better trade.

## Profiling: CPU-bound vs. GPU-bound

Two different things can make a frame slow, and here it matters to **distinguish** them. The CPU (central processing unit) is the main processor that runs your JS. The same Performance tooling as in browser-animation (article 06) applies:

```txt
CPU-bound — JS code (your update() logic, JS-side geometry
             generation, per-pixel processing loops) takes a
             long time before the GPU even receives any drawing
             commands. Directly visible in the flame chart of
             the Performance panel.

GPU-bound  — JS finishes quickly, draw calls are issued, but
             the GPU itself takes a long time to execute them
             (complex shaders, resolution too high, too many
             overlapping transparent layers). Shows up as a gap
             between "JS finished its work" and "the frame
             actually appeared on screen". Needs GPU-specific
             profiling tools (the GPU tab in DevTools, dedicated
             WebGL inspectors); an ordinary JS flame chart
             won't show it.
```

A practical heuristic reads two symptoms and gives one verdict:

- Cutting the entity count on the JS side does **not** reduce frame time, but lowering shader complexity or resolution **does**. The problem is GPU-bound. Simplify shaders, lower resolution, cut draw calls (article 04). Do not optimize JS.
- Cutting the entity count **does** reduce frame time, and lowering shader complexity or resolution does **not**. The problem is on the JS side. Use object pooling and algorithmic optimization of your update logic (below). Do not "simplify the graphics."

## Object pooling: quieting the garbage collector

The classic problem here is pressure on the GC (garbage collector — the part of the JS engine that reclaims unused memory).

Creating and discarding many short-lived objects, such as particles being born and dying constantly, triggers frequent collection pauses. Those show up as periodic frame stutters with no connection to actual rendering load, which makes them especially unpleasant to diagnose by eye.

```javascript
// ✅ A fixed pool, reusing objects instead of new/discarding them
class ParticlePool {
  constructor(size) {
    this.pool = Array.from({ length: size }, () => (
      { active: false, x: 0, y: 0, vx: 0, vy: 0, life: 0 }
    ));
  }

  spawn(x, y, vx, vy) {
    const p = this.pool.find((p) => !p.active); // reuse an existing object
    if (!p) return null; // the pool is exhausted — just skip spawning
                          // another particle, do not grow the pool unbounded
    Object.assign(p, { active: true, x, y, vx, vy, life: 1 });
    return p;
  }

  release(particle) {
    particle.active = false; // "deleting" is just a flag —
                               // the object stays in the pool for reuse
  }
}
```

The rule: if entities are created and destroyed frequently — dozens to hundreds of times a second — a fixed pool is not a micro-optimization. Reusing fields instead of `new` and garbage collection removes an entire class of unexplained periodic lag from your performance profile.

## Dirty-rectangle rendering: only redraw what changed

Article 02 teaches a full clear (`clearRect` over the whole canvas) every frame. That is the right default for scenes where most of the content is dynamic.

But some scenes hold far more static content than motion. Examples: a blinking cursor in a large text canvas, or a small HUD element on top of an otherwise static illustration. HUD stands for heads-up display, the status overlay drawn on top of a scene. There it is cheaper to track **which** rectangular regions actually changed since the last frame, and clear and redraw only those:

```txt
Dirty-rectangle bookkeeping:
  1. For every moving object, remember its bounding box on the
     previous frame and on the current one
  2. Union all of those rectangles into a list of "dirty" regions
  3. clearRect + redraw only those regions, not the whole canvas
```

The extra bookkeeping — storing previous bounding boxes, unioning rectangles — only pays off when the ratio of static to dynamic content is high enough. For scenes where most of the screen changes every frame anyway (particles, action-heavy games), a full clear is simpler and no slower in practice.

## Culling off-screen objects

Culling means skipping the entities the camera cannot see this frame. The check is one rectangle test per entity. It removes the drawing cost, and — when the object's physics and logic don't matter off-screen — the update cost too.

AABB stands for axis-aligned bounding box: the smallest rectangle that fully contains the object, with its sides parallel to the screen axes. Two such rectangles are cheap to test for overlap, which is why culling uses them instead of the object's real shape.

```txt
     Culling: one check per entity, per frame
┌───────────────────────────────────────────────┐
│ Take the next entity in the scene             │
└───────────────────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│ Does its AABB overlap the viewport rectangle? │
└───────────────────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│ no  → culled: skip both update() and draw()   │
│ yes → update() and draw() it as usual         │
└───────────────────────────────────────────────┘
 at high entity counts the linear scan is itself
    the bottleneck → use a quadtree or a grid
```

In 3D and Pixi worlds larger than the screen, the same idea applies to the currently visible area rather than the browser viewport. In three.js some of this is already handled by the camera's automatic per-object frustum culling. A frustum is the pyramid-shaped volume the camera can actually see.

At large entity counts the linear "every object against the bounds" check becomes a bottleneck itself. That is when a spatial structure pays off. A quadtree recursively splits the area into four quadrants; a plain grid does the same with fixed cells. Either one narrows the check down to objects genuinely near the visible area.

## Caching text and images to offscreen canvases

The same principle as caching an expensive shadow effect in article 03, applied broadly. Any visual element that is **expensive** to compute but **static** is worth rendering **once** into an offscreen canvas or texture. Examples: complex text layout, a pre-computed gradient background, a composite icon built from several layers. After that you reuse it via `drawImage` every frame, instead of recomputing it.

## Memory discipline: texture budgets and context-loss recovery

Mobile GPUs have noticeably less video memory than desktop ones. A scene that loads many high-resolution textures with no explicit budget can exceed the available memory. Two things can happen then. Textures get evicted and reloaded on the fly, which shows up as visible lag the first time content appears. Or the GPU context is lost outright (article 04).

```txt
Practical rules:
  - Set an explicit texture memory budget for the mobile build —
    and stay within it, rather than hoping it'll be enough
  - Downscale/compress textures specifically for mobile builds,
    instead of shipping the same assets to every device
  - Explicitly release (dispose/destroy) textures for content that
    isn't currently visible (e.g., in a long scrollable gallery of
    3D previews, keep only the ones near the viewport loaded)
```

**Context-loss recovery is more than just handling the event.** Article 04 shows `webglcontextlost` and `webglcontextrestored`, but genuine production readiness requires the recovery to be a **real**, tested code path. Keep the source data and URLs needed to fully rebuild the scene — not just the GPU objects, which are exactly what became invalid.

Otherwise the event handler exists on paper only. Actual scene recovery doesn't work, because the data needed to rebuild the scene isn't on hand anymore.

## Loading UX for heavy assets

Loading UX (user experience) for a heavy asset is progressive: show a low-resolution placeholder texture first, then swap in the full resolution once it's ready. In React that is a skeleton or placeholder pattern while `GLTFLoader`/`Assets` (articles 05-06) load a heavy model or atlas.

This is the same perceived-performance principle behind the skeleton screens covered in browser-animation (article 07). Here it applies to heavy 3D and canvas assets, where real load time can be seconds rather than milliseconds. The difference between "an empty screen" and "the structure is already visible, content is loading in" is subjectively large.

## Accessibility of canvas content: a "black box" for screen readers

Canvas isn't just less accessible than DOM (document object model — the browser's tree of page objects) or SVG (article 07). It is structurally **invisible** to assistive technology. Canvas is pixels with no semantic structure whatsoever, and a screen reader simply cannot "see" what's drawn there.

```html
<!-- Fallback content inside <canvas> — works only if the browser
  doesn't support canvas at all (an extremely rare case today) — a
  screen reader reading the page in a browser that does render
  canvas will never see this fallback content -->
<canvas>
  <p>Fallback content — practically never reached today</p>
</canvas>
```

Practically workable solutions:

```txt
- For purely decorative graphics (a particle background carrying
  no information), aria-hidden="true" is correct and sufficient,
  with no further work needed

- For canvas conveying real information (a chart, a diagram) —
  role="img" + aria-label for the simple case, or a parallel
  accessible representation of the same data (a visually hidden
  data table mirroring the chart, an aria-live region announcing
  game-state changes) — because fallback content inside the
  <canvas> tag is not picked up by assistive technology when
  canvas is actually supported and rendered by the browser

- For interactive canvas (a canvas game, a canvas editor) — canvas
  has no focus/keyboard-interaction model of its own at all, so you
  need a parallel layer of ordinary DOM elements (buttons responding
  to Enter/Space), wired into the same logic as the mouse/touch
  handlers on the canvas — a genuine duplicate implementation of the
  interaction, not a decorative add-on
```

An honest practical rule of thumb: if the canvas is purely decorative, `aria-hidden` closes the question entirely. If it carries information or functionality, a parallel accessible implementation is a real engineering requirement. Scope it into the feature's estimate from the start, instead of adding it at the end as "polish."

## Testing approaches for canvas code

```txt
Extract pure logic away from drawing — a direct payoff of the
update/draw split shown in article 02: physics, game rules, d3
scale/shape computations (article 07) shouldn't know ctx exists —
they can be tested with ordinary unit tests, with no canvas and no
DOM involved at all.

Visual regression testing — for the drawing itself, where there's
no simple "assert one JS value," screenshot-diffing tools (in the
style of Playwright/Percy) render the canvas to an image and compare
it pixel-by-pixel against a baseline — catching unintended visual
regressions in drawing code that pure unit tests structurally
cannot catch.

Do not unit-test the drawing calls themselves directly (mocking ctx
and asserting "fillRect was called with these arguments") — that's
a brittle test of implementation, not behavior: it breaks on any
drawing refactor, even when the visual result is identical.
```

The practical split: unit tests for logic, visual regression for rendering. The logic is extracted from drawing per article 02's principle, and `ctx` is never mocked as a substitute for either.

## Connection to other articles

- [Canvas Animation and the Game Loop](./02-canvas-animation-and-game-loop.md) — the update/draw split that both object pooling and testability are built on.
- [Pixi.js in Depth](./05-pixijs-in-depth.md) and [three.js in Depth](./06-threejs-in-depth.md) — the `useEffect` + `destroy()` pattern for React integration, generalized here to any canvas engine.
- [WebGL and GPU Fundamentals](./04-webgl-and-gpu-fundamentals.md) — context loss and GPU memory budgets, taken here to a full production strategy.
- Performance Debugging and Jank Hunting, in the browser-animation topic — the same Performance tooling, applied here to the CPU-bound/GPU-bound distinction.

## Common interview traps

- **Recreating the canvas engine on every React render** — not moving creation into a `useEffect` with an empty dependency array. The engine, along with its entire internal scene and state, is then destroyed and rebuilt on every unrelated parent state change.

- **Not capping `devicePixelRatio` on mobile** — rendering at full retina resolution. That is often the single most expensive line of code in the entire mobile render path.

- **Not distinguishing CPU-bound from GPU-bound** — trying to "optimize the JS" when the bottleneck is real GPU work (complex shaders, resolution), or the reverse.

- **Not knowing about object pooling** — creating and discarding many short-lived objects such as particles, with no awareness of the link to garbage collection pauses. They show up as unexplained periodic frame stutters.

- **Treating dirty-rectangle rendering as a universal improvement** — not understanding that the extra bookkeeping only pays off at a high ratio of static to dynamic content. It is not always better than a full clear.

- **Assuming fallback content inside the `<canvas>` tag solves accessibility** — not knowing that assistive technology ignores that content when canvas is actually supported and rendered. Meaningful canvas content needs a parallel accessible implementation, not a declaration inside the tag.

- **Trying to unit-test the drawing calls themselves by mocking `ctx`** — not splitting logic from drawing per article 02's principle. The result is brittle implementation tests instead of testable pure logic plus visual regression for rendering.
