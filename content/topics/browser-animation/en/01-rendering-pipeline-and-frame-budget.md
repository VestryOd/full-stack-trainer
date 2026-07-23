# Rendering Pipeline and Frame Budget

## Why there's no "professional" animation without this

A developer who knows how to write `transition: all 0.3s ease` and stops there is working blind: they can't explain why one animation is smooth while another stutters on a mid-range Android phone, and they fix problems by guessing ("let me add `will-change`, maybe that helps"). A senior developer understands what happens between changing a CSS property and pixels actually appearing on screen — because that's exactly where performance is won or lost.

Every other article in this topic is about *which tool to pick* (CSS transitions, WAAPI, rAF, GSAP) and *how to use it*. This article is about what happens physically inside the browser in response to any of those tools. Without it, choosing `transform` over `top` looks like superstition ("I heard transform is faster") instead of an engineering decision.

## The path of a single frame: Style → Layout → Paint → Composite

The browser doesn't "redraw the page" as one atomic action. Every change goes through a pipeline of stages, and **which stage that pipeline starts from** determines how expensive the frame is.

```txt
┌──────────┐   ┌──────────┐   ┌─────────────┐   ┌───────────┐
│ Style    │──>│ Layout   │──>│ Paint       │──>│ Composite │──> pixels on screen
│ (recalc) │   │ (reflow) │   │ (rasterize) │   │ (layers)  │
└──────────┘   └──────────┘   └─────────────┘   └───────────┘
```

**1. Style (recalculation)** — the browser figures out which CSS rules apply to each DOM node and resolves final computed values (cascade, inheritance, specificity). The output is a computed style per element. This runs almost any time something that affects a selector match or a property changes.

**2. Layout (a.k.a. reflow)** — the browser computes geometry: the exact size and position of every element on the page. This is the expensive stage because it's **cascading** — no element exists in a vacuum. Changing one `div`'s width can shift every element after it, and in a flex or grid container it can force a geometry recompute for all children. In the worst case, layout touches the entire document.

**3. Paint (rasterization)** — the browser fills in pixels for each element: background, text, shadows, borders, images. Technically this doesn't happen on a single "canvas" but across a set of layers (more on those below). Paint is cheaper than layout but still not free — rasterizing a large-blur `box-shadow` across the full viewport is a real CPU/GPU cost.

**4. Composite** — the browser assembles the already-painted layers into the final frame, applying transforms, opacity, and stacking order. This is the only stage that can run **without touching Style, Layout, or Paint at all**, if the change affects only compositing.

Here's the fact that explains the rest of this article: **the earlier a change enters the pipeline, the more expensive it is**. A change that kicks off the whole path starting at Layout is always more expensive than one that only reaches Composite — even when the visual result looks similar.

```txt
Expensive path (changing width):
  Style → Layout → Paint → Composite   (all 4 stages)

Cheap path (changing transform):
  Composite                             (1 stage only)
```

## Main thread vs. compositor thread: who does what

The browser (Chromium is the easiest case to reason about, and the most common one) has at least two threads that matter for animation:

```txt
┌───────────────────────────────────────────────────────┐
│                      Main Thread                      │
│   JS execution · Style · Layout · Paint (produces the │
│   display list) · event handlers · rAF callbacks      │
└───────────────────────────┬───────────────────────────┘
                            │ hands off layers + display list
                            ▼
┌────────────────────────────────────────────────────────────┐
│                     Compositor Thread                      │
│   Tile rasterization (often on GPU via separate raster     │
│   threads) · layer assembly · transform/opacity            │
│   animations · scrolling · submitting the frame to the GPU │
└────────────────────────────────────────────────────────────┘
```

The main thread is the same thread that runs all your JavaScript, where React does reconciliation, where event handlers fire. There is exactly **one** of it, and it's sequential: while the main thread is busy with a long synchronous JS task, it can't compute Style/Layout/Paint for the next frame — and it can't respond to a user click either.

The compositor thread is separate and lighter (in Chromium, some of the work additionally offloads to the GPU process). On its own, **without going back to the main thread**, it can animate already-rasterized layers: shift them (`transform`), change their opacity, scale them. That's why these animations don't stutter even when the main thread is busy — say, React is rendering a large component tree while a `transform`-based CSS animation keeps running smoothly, because it physically executes on a different thread.

This is the real answer to "how can an animation possibly run *unblocked* by heavy JS?" — it gets blocked only if it requires recomputation on the main thread (Style/Layout/Paint). A purely compositor-driven animation is almost entirely independent of the main thread (with rare exceptions, like some scroll scenarios that still need synchronous main-thread hit-testing).

## Frame budget: 16.7 ms isn't a round number for aesthetics

A 60 Hz display shows 60 frames per second. That gives the browser:

```txt
1000 ms / 60 = 16.666... ms  per frame
```

Inside that budget, the browser has to run JS (if any), Style, Layout, Paint, Composite, rasterization, and physically hand the frame to the display. In practice, a realistic budget for *your own* code at a comfortable 60 fps is closer to 8-10 ms — the rest is eaten by the browser's internal stages and system overhead.

On 120 Hz displays (flagship phones, some laptops and monitors), the budget is twice as tight:

```txt
1000 ms / 120 = 8.33... ms per frame
```

This isn't a theoretical footnote: an animation that looked smooth on your 60 Hz dev monitor can visibly stutter on a QA engineer's 120 Hz phone — not because it got "heavier," but because the per-frame budget got cut in half while your JS cost stayed the same.

**Jank is, physically, a missed frame.** If the browser doesn't finish preparing a new frame by the time the display is ready to show it, the display re-shows the previous frame (or shows a torn frame, if vsync isn't synced). The eye reads this as a stutter, a hitch, "unevenness" of motion — because instead of a steady sequence of positions (one step every 16.7 ms), the object suddenly "jumps" to a position that corresponds to two steps at once.

```txt
Smooth (60 fps, every frame lands on time):
  frame 1 →  frame 2 →  frame 3 →  frame 4   (positions: 0, 4, 8, 12px)

Jank (frame 3 gets dropped because it wasn't ready in time):
  frame 1 →  frame 2 →  [dropped]  →  frame 4   (positions: 0, 4,  —,  12px)
  The eye sees a jump from 4px straight to 12px in the time that
  used to cover two even steps.
```

## Why transform and opacity are cheap, and top/left/width/height are expensive

This is THE most common animation interview question, and the answer should be grounded in the pipeline above, not recited as a memorized fact.

| Property being changed | Stages it triggers | Why |
|---|---|---|
| `width`, `height`, `top`, `left`, `margin`, `padding`, `font-size` | Style → **Layout** → Paint → Composite | Changes the element's geometry → the browser has to recompute positions and sizes (potentially cascading to siblings and children) |
| `background-color`, `box-shadow`, `border-color`, `outline` | Style → Paint → Composite | Geometry stays the same, but pixels have to be repainted |
| `transform`, `opacity` | **Composite** (often just this) | Change neither geometry nor "how the already-painted content looks" — only how the finished layer is positioned and blended on screen |

`translateX(100px)` looks visually identical to `left: 100px` in the simple case — but from the browser's point of view, these are two different worlds. `left` says "this element now physically occupies a different place in the document flow" — that requires layout, because sibling elements may depend on the new position (though for out-of-flow elements like `position: absolute`/`fixed`, siblings aren't affected — layout still gets recomputed for the element itself). `transform` says "draw this element's already-computed layer somewhere else on screen" — the geometry in the document never changed; the element is just visually offset on top of the layout that was already calculated.

Same story with `opacity` versus, say, animating a translucent `background-color`, or a class toggle that changes `display`: `opacity` only touches the alpha channel of an already-rasterized layer during compositing, with no repaint involved.

```css
/* ❌ Expensive: every frame of this animation is Layout + Paint + Composite */
.dropdown {
  transition: top 0.2s ease, left 0.2s ease;
  position: absolute;
}
.dropdown.open {
  top: 40px;
  left: 0;
}

/* ✅ Cheap: every frame of this animation is Composite only */
.dropdown {
  transition: transform 0.2s ease;
  position: absolute;
  top: 40px;
  left: 0;
  transform: translateY(-8px) scale(0.98);
  opacity: 0;
}
.dropdown.open {
  transform: translateY(0) scale(1);
  opacity: 1;
}
```

The practical rule: **if you can express an animation using `transform` and `opacity`, do it that way**. This isn't a blanket "top bad, transform good" dogma detached from context — it's a direct consequence of which pipeline stages each property triggers.

## Layout thrashing: when your own JS forces an unnecessary reflow

By default, the browser is **lazy**: if you change `style.width` several times in a row from JS, the browser isn't obligated to recompute layout after each change — it can batch the changes and compute layout once, right before the next frame. This is called *batching*.

The problem is that some JS properties **read** geometry (`offsetHeight`, `offsetWidth`, `getBoundingClientRect()`, `scrollTop`, `clientWidth`, and a dozen similar ones). To return a correct value, the browser must give you **up-to-date** geometry — so if there are pending style changes before the read, it's forced to compute layout synchronously, right now, instead of deferring it to the next frame. This is called a **forced synchronous layout** (forced reflow).

The danger isn't one such read — it's **interleaving writes and reads inside a loop**: every iteration breaks batching and forces a full layout recompute all over again.

```javascript
// ❌ Layout thrashing: read and write are interleaved in a loop —
// every iteration forces a synchronous reflow
function resizeItemsToMatch(items, referenceHeight) {
  items.forEach((item) => {
    const currentHeight = item.offsetHeight; // READ → forces layout
                                              // if a write happened before this
    item.style.height = `${currentHeight + referenceHeight}px`; // WRITE →
                                              // invalidates layout
  });
  // With 100 items, that's up to 100 full synchronous reflows in one call.
  // In DevTools Performance this shows up as repeated "Layout" entries
  // flagged "Forced reflow" right next to this code.
}
```

```javascript
// ✅ Fix: split the read phase from the write phase —
// the browser's batching works normally again
function resizeItemsToMatch(items, referenceHeight) {
  // Phase 1: read everything you need, before the single reflow
  const heights = items.map((item) => item.offsetHeight);

  // Phase 2: write everything — writes don't read geometry, so no reflow is forced
  items.forEach((item, i) => {
    item.style.height = `${heights[i] + referenceHeight}px`;
  });
  // One reflow (at most) for the whole call instead of N.
}
```

The rule is simple and easy to remember: **read everything you need first, then write everything you need** — never interleave reads and writes in a loop. Libraries like FastDOM automate this split, but understanding the mechanism matters more than remembering a specific library name.

## GPU layers: how an element gets its own layer, and what that costs

For a `transform`/`opacity` animation to be cheap (Composite only), the element needs to be **promoted to its own composited layer** — rasterized once into a separate texture that the GPU can freely move, scale, and fade without repainting it.

The browser creates a separate layer for an element based on a number of triggers:

```txt
- 3D transforms: transform: translateZ(0), translate3d(...)
- the will-change CSS property: transform / opacity / ...
- <video>, <canvas>, <iframe>
- elements with a CSS filter that's being animated
- position: fixed / sticky in some cases (engine-dependent)
- an element with an active CSS animation/transition on transform or opacity
- an element with opacity < 1 that has composited descendants (in some cases)
```

A layer isn't free. Every composited layer is a separate texture in GPU memory:

```txt
Memory per layer ≈ width_px × height_px × 4 bytes (RGBA)

Example: a full-screen 1920×1080 element →
  1920 × 1080 × 4 ≈ 8.3 MB for ONE layer

10 such layers on a page → ~83 MB just for layer textures,
not counting the rest of the app's GPU memory
```

On a desktop with a discrete GPU, 83 MB is unnoticeable. On a budget Android phone with memory shared between CPU and GPU, it's a real chunk of the budget — and as layers pile up, the browser starts spending noticeably more time uploading textures to the GPU, hitting GPU driver memory limits more often, and in bad cases forcibly "squashing" layers back together, which hurts performance even more than having no layers at all would have.

### Why "just slap `will-change` on everything" is an anti-pattern

`will-change: transform` is a hint to the browser: "get ready, this element is about to be animated, promote it to a layer ahead of time." The problem is that promotion to a layer costs memory and costs texture-creation time **immediately**, not at the moment the animation actually starts:

```css
/* ❌ Anti-pattern: will-change slapped on a static set of elements "just in case" */
.card {
  will-change: transform;
  /* each of 200 cards on the page now occupies its own GPU
     layer — even though only 2 of them are actually animated */
}
```

```css
/* ✅ Correct: will-change is added right before the animation
   starts and removed right after it finishes */
.card--about-to-animate {
  will-change: transform;
}
```

```javascript
// ✅ Practical pattern for managing will-change from JS
function animateCard(card) {
  card.style.willChange = 'transform';
  card.addEventListener(
    'transitionend',
    () => { card.style.willChange = 'auto'; }, // drop the layer once the animation is done
    { once: true },
  );
  card.style.transform = 'translateY(-8px)';
}
```

This is called **layer explosion**: an excessive number of composited layers, each quietly costing memory and composite-stage time, adding up to a net performance regression exactly where `will-change` was supposed to help. Diagnosing this is covered in [Performance Debugging and Jank Hunting], which walks through the DevTools Layers panel; the rule to take away here is: **`will-change` is a targeted, temporary tool, not a default-on optimization**.

## Connection to other articles

```txt
[CSS Transitions and Keyframes]     — declaring transform/opacity animation
                                       declaratively, now knowing WHY it's cheap
[Web Animations API]                — the same engine, programmatic access
[rAF and JS-Driven Animation]       — what to do when declarative tools
                                       aren't enough, without breaking
                                       the frame budget by hand
[Performance Debugging and
 Jank Hunting]                      — actually seeing Layout/Paint/Composite
                                       and layer explosion in DevTools
```

## Common interview traps

- **"transform is faster because it's on the GPU"** — an imprecise answer. The precise version: `transform`/`opacity` are cheaper because they skip the layout-affecting parts of Style recalc, Layout, and Paint entirely, running only through compositing — not because "GPU beats CPU" in some general sense. `box-shadow` can also be GPU-rendered and still requires Paint.

- **Confusing Layout and Paint** — calling something a "repaint" when it was actually a reflow (layout), or vice versa. These are different stages with different costs, and DevTools Performance shows them as separate bars.

- **Not knowing about forced synchronous layout** — being unable to explain why a loop interleaving `element.offsetHeight` reads with `element.style.x = ...` writes runs an order of magnitude slower than the same code with reads and writes split into separate phases.

- **Treating `will-change` as a "free optimization"** — not realizing it reserves GPU memory for a layer, and that scattering `will-change` across many elements "just in case" can WORSEN performance (layer explosion) instead of improving it.

- **Not knowing about the 120 Hz budget** — assuming 16.7 ms is a universal constant and not accounting for the fact that modern flagship devices need to land within 8.3 ms per frame.

- **Confusing the main thread with the compositor thread** — saying "JS blocks all animation" without qualifying that this is only true for animations that require Style/Layout/Paint on the main thread; purely compositor-driven `transform`/`opacity` animations keep running smoothly even while the main thread is busy with heavy synchronous JS.
