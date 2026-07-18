# Architecture and Performance for Canvas Apps

## From tools to a production feature

Articles 01-07 gave you tools: primitives, the game loop, pixels, WebGL, Pixi, three.js, SVG/d3. This article is about assembling them into a real feature inside a real React/Next.js app — one that doesn't lag on weak hardware, doesn't leak memory over an hour of use, is accessible to more than just sighted mouse users, and can be meaningfully tested. This is the same level as articles 06-07 in browser-animation, just applied to the canvas world.

## Canvas as an escape hatch from React's render model

React re-renders components declaratively, based on state/props; canvas (raw, Pixi, three.js) is an imperative, **stateful** system: the scene/buffer live across renders and shouldn't be recreated on every React re-render. The canonical solution is an **imperative core inside a declarative shell**: the scene is created ONCE, inside a `useEffect` with an empty dependency array, and changing props are synced into the already-existing "engine" through separate effects that call its methods — never recreating it wholesale.

```tsx
function ParticleCanvas({ color, count }: { color: string; count: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const engineRef = useRef<ParticleEngine | null>(null);

  useEffect(() => {
    engineRef.current = new ParticleEngine(canvasRef.current!);
    engineRef.current.start();
    return () => engineRef.current?.destroy(); // REQUIRED cleanup on unmount
  }, []); // EMPTY dependency array — the engine is created EXACTLY ONCE

  useEffect(() => {
    engineRef.current?.setColor(color); // SYNC the prop into the existing
  }, [color]);                            // engine, WITHOUT recreating it

  useEffect(() => {
    engineRef.current?.setParticleCount(count);
  }, [count]);

  return <canvas ref={canvasRef} />;
}
```

This is exactly the same pattern shown for Pixi's `Application` (article 05) and a three.js scene (article 06) — here it's generalized as the canonical approach for ANY imperative canvas engine inside React: creation inside `useEffect` with empty dependencies, syncing props through separate effects with focused dependency lists, and a mandatory `destroy()`/`cancelAnimationFrame` in the cleanup function.

## Resolution and scaling strategy

**Capping `devicePixelRatio` on mobile** — the same logic as in three.js (article 06, `renderer.setPixelRatio`), but relevant to ANY canvas rendering: rendering at full retina resolution (dPR 3 on some phones) on a weak mobile GPU is often the single most expensive line in the entire app. Capping to 1.5-2x is visually almost indistinguishable from full resolution, but noticeably cheaper in terms of the actual pixel volume that needs filling (fill-rate).

**Dynamic resolution under load** is a technique from "real" real-time graphics that applies just as well on the web: monitor frame time (see profiling below) and adaptively LOWER the internal render resolution (then upscale it via the canvas's CSS size) when frame time consistently exceeds budget, restoring resolution once load drops. This is what turns "the hero particle effect grinds to a halt on a weak phone" into "the hero particle effect gracefully loses some sharpness while staying smooth" — almost always the better trade for a promo page.

## Profiling: CPU-bound vs. GPU-bound

The same Performance tooling as in browser-animation (article 06), but here it matters to DISTINGUISH two different sources of a slow frame:

```txt
CPU-bound — JS code (your update() logic, JS-side geometry
             generation, per-pixel processing loops) takes a long
             time BEFORE the GPU even receives any drawing commands.
             Directly visible in the Performance panel's flame chart.

GPU-bound  — JS finishes quickly, draw calls are issued, but the GPU
             itself takes a long time to actually execute them
             (complex shaders, resolution too high, too many
             overlapping transparent layers). Shows up as a gap
             between "JS finished its work" and "the frame actually
             appeared on screen" — needs GPU-specific profiling
             tools (the GPU tab in DevTools, dedicated WebGL
             inspectors) for precise diagnosis; an ordinary JS flame
             chart won't show it.
```

A practical heuristic: if reducing the entity count on the JS side does NOT reduce frame time, but lowering shader complexity/resolution does, the problem is GPU-bound, and the fix is simplifying shaders/lowering resolution/cutting draw calls (article 04) — not optimizing JS. The reverse holds too: if both symptoms point the other way, the problem is on the JS side, and the fix is object pooling and algorithmic optimization of your update logic (below), not "simplifying the graphics."

## Object pooling: quieting the garbage collector

The classic GC-pressure problem: creating and discarding many short-lived objects (particles being born and dying constantly) triggers frequent garbage collection pauses — these show up as periodic frame hitches with no connection to actual rendering load, which makes them especially unpleasant to diagnose by eye.

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
                          // another particle, do NOT grow the pool unbounded
    Object.assign(p, { active: true, x, y, vx, vy, life: 1 });
    return p;
  }

  release(particle) {
    particle.active = false; // "deleting" is just a flag —
                               // the object stays in the pool for reuse
  }
}
```

The rule: if entities are created and destroyed frequently (dozens to hundreds of times a second), a fixed pool that reuses fields instead of `new`/garbage collection isn't a micro-optimization — it removes an entire class of unexplained periodic lag from your performance profile.

## Dirty-rectangle rendering: only redraw what changed

Article 02 teaches a full clear (`clearRect` over the whole canvas) every frame — the right default for scenes where most of the content is dynamic. But where there's far more static content than motion (a blinking cursor in a large text canvas, a small HUD element on top of an otherwise static illustration), it's cheaper to track WHICH rectangular regions actually changed since the last frame, and only clear/redraw those:

```txt
Dirty-rectangle bookkeeping:
  1. For every moving object, remember its bounding box on the
     PREVIOUS frame and on the CURRENT one
  2. Union all of those rectangles into a list of "dirty" regions
  3. clearRect + redraw ONLY those regions, instead of the whole canvas
```

The extra bookkeeping (storing previous bounding boxes, unioning rectangles) only pays off when the ratio of static to dynamic content is high enough — for scenes where most of the screen changes every frame anyway (particles, action-heavy games), a full clear is simpler and, in practice, no slower.

## Culling off-screen objects

Don't update/draw entities far outside the visible viewport (or, in 3D/Pixi worlds larger than the screen, outside the currently visible area): a simple AABB-versus-viewport check before drawing each entity removes both the drawing cost and, when the object's physics/logic isn't important off-screen, the update cost for invisible objects. In three.js, some of this is already handled by the camera's automatic per-object frustum culling, but at large entity counts, a linear "every object against the bounds" check becomes a bottleneck itself — that's when a spatial structure (a quadtree/grid) pays off, narrowing the check down to objects genuinely near the visible area.

## Caching text and images to offscreen canvases

The same principle as caching an expensive shadow effect in article 03, applied broadly: any visual element that's EXPENSIVE to compute but STATIC (complex text layout, a pre-computed gradient background, a composite icon built from several layers) is worth rendering ONCE into an offscreen canvas/texture and reusing via `drawImage` every frame, instead of recomputing it.

## Memory discipline: texture budgets and context-loss recovery

Mobile GPUs have noticeably less video memory than desktop ones. A scene loading many high-resolution textures with no explicit budget can exceed available memory, causing either texture eviction/reload on the fly (visible lag the first time content appears) or an outright loss of the GPU context (article 04).

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

**Context-loss recovery is more than just handling the event.** Article 04 shows `webglcontextlost`/`webglcontextrestored`, but genuine production readiness requires the recovery to be a REAL, tested code path: keep the source data/URLs needed to fully rebuild the scene (not just the GPU objects themselves, which are exactly what became invalid) — otherwise the event handler exists purely on paper, while actual scene recovery doesn't work, because the data needed to rebuild it isn't on hand anymore.

## Loading UX for heavy assets

Progressive loading — show a low-resolution placeholder texture first, swap in the full resolution once it's ready; in React, a skeleton/placeholder pattern while `GLTFLoader`/`Assets` (articles 05-06) are loading a heavy model or atlas. This is the same perceived-performance principle behind skeleton screens covered in browser-animation (article 07), applied specifically to heavy 3D/canvas assets, where real load time can be seconds rather than milliseconds, and the subjective difference between "an empty screen" and "the structure is already visible, content is loading in" is significant.

## Accessibility of canvas content: a "black box" for screen readers

Canvas isn't just less accessible than DOM/SVG (article 07) — it's structurally INVISIBLE to assistive technology: it's pixels with no semantic structure whatsoever, and a screen reader simply cannot "see" what's drawn there.

```html
<!-- Fallback content inside <canvas> — works ONLY if the browser
  doesn't support canvas at all (an extremely rare case today) — a
  screen reader reading the page in a browser that DOES render
  canvas will NEVER see this fallback content -->
<canvas>
  <p>Fallback content — practically never reached today</p>
</canvas>
```

Practically workable solutions:

```txt
- For purely decorative graphics (a particle background carrying
  no information), aria-hidden="true" is correct and sufficient,
  with no further work needed

- For canvas conveying REAL information (a chart, a diagram) —
  role="img" + aria-label for the simple case, or a PARALLEL
  accessible representation of the same data (a visually hidden
  data table mirroring the chart, an aria-live region announcing
  game-state changes) — because fallback content inside the
  <canvas> tag is NOT picked up by assistive technology when
  canvas is actually supported and rendered by the browser

- For INTERACTIVE canvas (a canvas game, a canvas editor) — canvas
  has no focus/keyboard-interaction model of its own at all, so you
  need a PARALLEL layer of ordinary DOM elements (buttons responding
  to Enter/Space), wired into the SAME logic as the mouse/touch
  handlers on the canvas — a genuine duplicate implementation of the
  interaction, not a decorative add-on
```

An honest practical rule of thumb: if the canvas is purely decorative, `aria-hidden` closes the question entirely; if it carries information or functionality, a parallel accessible implementation is a real engineering requirement that needs to be scoped into the feature's estimate from the start, not tacked on at the end as "polish."

## Testing approaches for canvas code

```txt
Extract PURE logic away from drawing — a direct payoff of the
update/draw split shown in article 02: physics, game rules, d3
scale/shape computations (article 07) shouldn't know ctx exists —
they can be tested with ordinary unit tests, with NO canvas and NO
DOM involved at all.

Visual regression testing — for the DRAWING itself, where there's
no simple "assert one JS value," screenshot-diffing tools (in the
style of Playwright/Percy) render the canvas to an image and compare
it pixel-by-pixel against a baseline — catching unintended visual
regressions in drawing code that pure unit tests structurally
cannot catch.

Do NOT unit-test the drawing calls themselves directly (mocking ctx
and asserting "fillRect was called with these arguments") — that's
a brittle test of implementation, not behavior: it breaks on any
drawing refactor, even when the visual result is identical.
```

The practical split: unit tests for logic (extracted from drawing per article 02's principle), visual regression for rendering, and NO mocking of `ctx` as a substitute for either.

## Connection to other articles

```txt
[Canvas Animation and Game Loop]      — the update/draw split that
                                         both object pooling and
                                         testability are built on
[Pixi.js in Depth] / [three.js
 in Depth]                              — the useEffect + destroy()
                                         pattern for React integration,
                                         generalized here to any
                                         canvas engine
[WebGL and GPU Fundamentals]          — context loss and GPU memory
                                         budgets, taken here to a full
                                         production strategy
[Performance Debugging and Jank
 Hunting] (browser-animation)          — the same Performance tooling,
                                         applied here to the
                                         CPU-bound/GPU-bound distinction
```

## Common interview traps

- **Recreating the canvas engine on every React render** — not moving creation into a `useEffect` with an empty dependency array, causing the engine (and its entire internal scene/state) to be destroyed and rebuilt on every unrelated parent state change.

- **Not capping `devicePixelRatio` on mobile** — rendering at full retina resolution without realizing that's often the single most expensive line of code in the entire mobile render path.

- **Not distinguishing CPU-bound from GPU-bound** — trying to "optimize the JS" when the bottleneck is real GPU work (complex shaders, resolution), or the reverse.

- **Not knowing about object pooling** — creating/discarding many short-lived objects (particles) with no awareness of the connection to garbage collection pauses, showing up as unexplained periodic frame hitches.

- **Treating dirty-rectangle rendering as a universal improvement** — not understanding the extra bookkeeping only pays off at a high ratio of static to dynamic content, not that it's always better than a full clear.

- **Assuming fallback content inside the `<canvas>` tag solves accessibility** — not knowing that content isn't picked up by assistive technology when canvas is actually supported and rendered, and that meaningful canvas content needs a parallel accessible implementation, not a declaration inside the tag.

- **Trying to unit-test the drawing calls themselves by mocking `ctx`** — not splitting logic from drawing per article 02's principle, ending up with brittle implementation tests instead of testable pure logic plus visual regression for rendering.
