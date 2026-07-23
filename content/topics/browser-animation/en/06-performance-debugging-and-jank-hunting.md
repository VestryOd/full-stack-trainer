# Performance Debugging and Jank Hunting

## From theory to "why is THIS animation janky HERE, specifically"

Articles 01-05 gave you the vocabulary and the tools: the rendering pipeline, cheap versus expensive properties, WAAPI, rAF, libraries. This article is about the senior engineer's actual workflow when the tech lead sends a screen recording captioned "the landing page is choppy while scrolling on an iPhone SE," with no other detail attached. Diagnosing jank isn't "stare at the code and guess" — it's a specific sequence of DevTools tools, each answering a different question.

## The Performance panel: where time is physically being lost

Recording (Record → replay the problematic interaction → Stop) gives you a main-thread flame chart — the first and most informative tool.

```txt
How to read the flame chart:
┌───────────────────────────────────────────────────────────┐
│ Main                                                      │
│ ▓▓▓▓░░░▓▓▓▓▓▓▓▓▓▓▓▓░░░▓▓▓░░░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░       │ ← time axis
│  JS   Style Layout  Paint    JS (rAF callback)  Composite │
└───────────────────────────────────────────────────────────┘
  Block color = category of work:
  yellow  = Scripting (your JS)
  purple  = Rendering (Style/Layout)
  green   = Painting
  blue    = Loading
```

What to look for specifically:

**Long Tasks** — any continuous block of main-thread JS longer than 50 ms gets flagged with a red triangle in the corner of the block. That's an empirically derived threshold: tasks shorter than 50 ms don't register as a response delay to a user; longer ones block the main thread long enough to be noticeable (this is the same threshold that underlies the INP metric, covered below).

**Forced reflow** — a warning (a purple Layout block flagged "Forced reflow" with a yellow exclamation mark) means exactly what article 01 covered: JS read geometry (`offsetHeight` and similar) right after writing a style, and the browser was forced to compute layout synchronously, outside its normal batching. Clicking the warning in DevTools expands a **stack trace** — the exact line of code that caused it. This is the fastest way to find layout thrashing in a real application without reading through the whole codebase line by line.

**A repeating Layout → Paint → Composite pattern on every animation frame** — if an animation's flame chart shows all three blocks on every tick, a layout-triggering property is being animated (`top`, `width`, etc. — see the table in article 01), not `transform`/`opacity`. A healthy compositor-only animation ideally shows only thin Composite blocks, with nothing in between.

## The Layers panel: why there are more layers than expected

`DevTools → More tools → Layers` gives a 3D visualization of every composited layer on the page — it literally "peels apart" the page along the Z axis, showing exactly what became its own layer and why.

```txt
For each layer, the panel shows:
  - Compositing Reasons — the EXACT reason it was promoted
    ("has a will-change: transform", "is animated", etc.) —
    no need to guess what triggered the layer
  - Memory estimate — how much GPU memory the layer occupies
    (directly tied to the width × height × 4 bytes formula
    from article 01)
```

**Layer explosion** is diagnosed here directly: if the panel shows dozens to hundreds of layers where you expected 3-5 (the elements actually being animated), the cause is almost always `will-change` left on static elements "just in case" (the anti-pattern from article 01), or a CSS filter/3D transform on a component that renders in bulk (say, every card in a list of a hundred got a `filter` for its shadow, and EACH ONE became its own layer).

## Paint flashing and the paint profiler: what's repainting when it shouldn't

`DevTools → Rendering tab → Paint flashing` highlights (usually with a green rectangle) any screen area that gets repainted, in real time, while you interact with the page.

```txt
Diagnostic scenario: scrolling a news feed flashes green across
the ENTIRE visible height on every scroll frame — even though
only the list should be scrolling, while the header and sidebar
are supposed to stay static.

The cause is almost always: an element without its own layer
overlaps or sits adjacent to the animated/scrolling content, and
the browser ends up repainting more pixels than necessary,
because paint doesn't happen per-layer in isolation — it happens
"together" for the overlapping region.

Fix: isolate the animated/scrolling area into its own composited
layer (transform: translateZ(0) or CSS containment, see below) —
so paint only touches its own pixels, not the whole overlap
with its neighbors.
```

Separately, `box-shadow`/`filter: blur()` — a noticeable "hot zone" in paint flashing on an element that looks static almost always means the shadow/blur is being repainted from scratch every frame (for example, `box-shadow` is being animated directly instead of a pre-rendered shadow's transform) — rasterizing a large blur radius on CPU/GPU is noticeably more expensive than a plain fill.

## FPS meter and frame rendering stats: a quick sanity check

`DevTools → Rendering tab → Frame Rendering Stats` turns on an overlay right on top of the page showing live FPS, GPU memory usage, and a dropped-frame counter — not a recording, a live monitor for a quick gut check ("did this change I just made regress anything?") without going through a full Performance-panel recording.

## Common causes of jank — and concrete fixes

### Layout thrashing

Covered in depth in article 01. Diagnosis: "Forced reflow" in the Performance panel. Fix: separate the read phase (`offsetHeight` and similar) from the style-write phase, never interleave them in a loop.

### Animating layout properties instead of transform/opacity

Diagnosis: a repeating Layout+Paint on every animation frame in the flame chart (see above). Fix: see the table in article 01 — rewrite the animation using `transform`/`opacity`.

### Excessive or oversized layers on mobile

```txt
Symptom: a full-screen background video or gradient image is
promoted to its own full-screen layer — unnoticeable on desktop,
but on a budget Android device with memory shared between CPU
and GPU, it causes noticeable lag across the WHOLE page, not
just the area of that element.

Diagnosis: Layers panel → the Memory estimate for that layer.

Fix: don't promote decorative background elements to their own
layer without a reason (don't attach will-change/3D-transform
to them for no purpose); for genuinely large background images,
serve a downscaled resolution at mobile breakpoints instead of
scaling a desktop-sized image down with CSS.
```

### `box-shadow`/`filter` in animation

```css
/* ❌ Animating box-shadow — every frame repaints the shadow from scratch */
.card {
  transition: box-shadow 0.3s;
}
.card:hover {
  box-shadow: 0 20px 40px rgba(0,0,0,0.3);
}
```

```css
/* ✅ A static, pre-rendered shadow on a separate pseudo-element,
   whose opacity is animated (compositor-only) instead of
   repainting a blur */
.card {
  position: relative;
}
.card::after {
  content: '';
  position: absolute;
  inset: 0;
  box-shadow: 0 20px 40px rgba(0,0,0,0.3);
  opacity: 0;
  transition: opacity 0.3s;
}
.card:hover::after {
  opacity: 1;
}
```

### Scroll handlers with synchronous layout reads

```javascript
// ❌ A non-passive listener + reading geometry on every scroll event —
// the browser has to wait for the handler to run (in case it calls
// preventDefault) before the scroll itself can visually update, and
// reading offsetTop on top of that risks a forced reflow every time
window.addEventListener('scroll', () => {
  const rect = header.getBoundingClientRect(); // reads geometry —
  if (rect.top < 0) header.classList.add('is-stuck'); // a potential forced reflow
});
```

```javascript
// ✅ passive: true explicitly tells the browser "this handler will
// never call preventDefault," removing the block on the main-thread scroll
window.addEventListener('scroll', onScroll, { passive: true });

// ✅ Even better — skip the scroll listener entirely in favor of
// IntersectionObserver: it runs asynchronously, mostly off the
// main thread per frame, with no manual getBoundingClientRect reads
const observer = new IntersectionObserver(
  ([entry]) => header.classList.toggle('is-stuck', !entry.isIntersecting),
  { threshold: 0 },
);
observer.observe(sentinelElement);
```

`{ passive: true }` isn't a micro-optimization: without it, the browser MUST synchronously wait for the JS handler to finish on every scroll event before committing the visual scroll, because in principle the handler could call `preventDefault()` and cancel it. This is the only reliable way (alongside dropping the `scroll` listener entirely in favor of `IntersectionObserver`) to guarantee your JS never blocks native scrolling.

## `content-visibility` and CSS containment: don't render what isn't visible

On long pages with many sections (docs, feeds, catalogs), the browser by default computes Style/Layout/Paint for the ENTIRE document, including content far outside the current viewport. `content-visibility: auto` explicitly lets the browser skip rendering work for content that isn't currently visible:

```css
.article-section {
  content-visibility: auto;
  contain-intrinsic-size: 0 800px; /* a placeholder size used before
    the first real render — without this the scrollbar "jumps"
    around, since the browser doesn't know the height of a
    not-yet-rendered section */
}
```

```txt
Effect: sections outside the viewport (and not near it) skip
Layout/Paint entirely until they get close to being visible —
this isn't content lazy-loading (the DOM stays in place,
searchable via Ctrl+F and visible to SEO), it's specifically
skipping rendering work. On pages with hundreds of sections,
the difference in initial render time and scroll responsiveness
is genuinely noticeable.
```

`contain` (without `content-visibility`) is a finer-grained, manual tool: it explicitly tells the browser that changes INSIDE an element shouldn't require recomputing layout/paint OUTSIDE it:

```css
.independent-widget {
  contain: layout paint; /* this element is an isolated "container":
    its internal changes don't force the browser to recompute
    geometry or repaint anything beyond its own boundaries */
}
```

This scopes layout thrashing inside the widget to just the widget, not the whole document — useful for complex widgets (a data grid, a canvas wrapper, a chat with frequently updating messages) that often change their internal markup.

## `OffscreenCanvas` — when DOM animation simply stops scaling

There's a point past which DOM/CSS animation is physically the wrong tool: thousands of independently animated particles, a complex physics simulation, frame-by-frame rendering where every element is its own DOM node. Every DOM node carries overhead with it (its own composited layer when animated, its own entry in the style tree, its own hit-testing) — and at a scale of thousands of elements, that overhead starts to dominate over the useful work itself.

The signal to switch isn't "it got a bit slower" — it's qualitative: if the profiler shows Style/Layout time growing linearly with the number of animated DOM nodes, rather than with the complexity of the animation itself, that's an architectural ceiling, not a case for one more optimization pass. `OffscreenCanvas` at that point lets you do raster rendering (Canvas 2D/WebGL) in a separate Worker thread, entirely off the main thread and the DOM tree. Actually drawing on Canvas/WebGL is its own topic ([Canvas & Graphics]); what matters here is just recognizing the moment DOM/CSS animation has hit its architectural ceiling.

## Measuring in production: Long Animation Frames and INP

DevTools profiling runs on your machine, with your CPU/GPU and your network — real users are almost always on weaker hardware. Production monitoring needs APIs that report problems from actual devices in the field.

**Long Animation Frames API (LoAF)** — a more detailed successor to the Long Tasks API, built specifically for rendering-related problems:

```javascript
new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) {
    console.log({
      duration: entry.duration,               // the "heavy" frame's total duration
      renderStart: entry.renderStart,          // when rendering began within the frame
      styleAndLayoutStart: entry.styleAndLayoutStart,
      scripts: entry.scripts.map((s) => ({     // WHICH script is actually responsible
        name: s.name,
        duration: s.duration,
        invoker: s.invoker,                    // e.g. a specific event listener or rAF callback
      })),
    });
  }
}).observe({ type: 'long-animation-frame', buffered: true });
```

Unlike the plain Long Tasks API (which just reports "something took over 50 ms"), LoAF breaks a "heavy" frame down into phases (how much went to script, how much to Style/Layout) and points at the specific culprit script — on real user devices, this gives you the same information as a stack trace in the Performance panel, without needing to reproduce the issue locally.

**INP (Interaction to Next Paint)** is a Core Web Vitals metric that measures the delay between a user's action (a click, a tap, a keypress) and the moment the browser physically shows the next updated frame in response. This ties directly back to this article's subject: if an rAF callback or JS-driven animation holds the main thread longer than the frame budget (article 01) at the exact moment a user interacts with the page, the response frame — say, a button's visual "pressed" state — gets delayed, and that directly hurts INP, in exactly the same way it hurts the animation's own perceived smoothness. For teams already optimizing LCP/CLS, it's worth internalizing: heavy, poorly budgeted animation isn't just an "aesthetic" problem — it's a measurable factor in the same Web Vitals report, with real SEO and product-metric consequences.

## Connection to other articles

```txt
[Rendering Pipeline and Frame Budget]  — the foundation: what layout
                                          thrashing, GPU layers, and
                                          frame budget actually are —
                                          here those concepts become
                                          diagnostic tools
[rAF and JS-Driven Animation]          — a typical source of Long
                                          Tasks in animation — a heavy
                                          rAF callback with no regard
                                          for the frame budget
[Animation Libraries and Ecosystem]    — the diagnostics in this
                                          article apply equally to
                                          hand-written code and to
                                          animation driven by a library
[Motion Design Patterns and
 Accessibility]                         — what to actually do with a
                                          diagnosed problem at the
                                          product level (simplify,
                                          remove, replace with a
                                          reduced-motion variant)
```

## Common interview traps

- **Not knowing what a "forced reflow" looks like in DevTools** — being unable to describe that the Performance panel flags these cases explicitly, with a purple block and a warning, and provides a stack trace pointing to the exact line of code.

- **Confusing paint flashing with the FPS meter** — not distinguishing the tools by purpose: paint flashing shows WHICH AREAS are repainting, the FPS meter only shows an aggregate frame rate, with no way to localize the cause.

- **Not knowing about `{ passive: true }`** — not understanding that a non-passive scroll/touch listener forces the browser to synchronously wait for the JS handler to finish before it can visually commit the scroll itself — this isn't about "the JS running a bit faster," it's about blocking the scroll itself.

- **Not knowing about `content-visibility`** — proposing list virtualization (react-window and similar) as the only fix for long-page performance, without knowing about the simpler CSS alternative for cases where the content can't be virtualized (an ordinary long document, say, rather than a list of identical items).

- **Assuming the local DevTools Performance panel is representative of production** — not knowing about the Long Animation Frames API/`PerformanceObserver` as a way to get the same kind of data from actual user devices in the field.

- **Not connecting animation performance to INP** — treating animation jank as a purely "visual" concern, without understanding that it directly affects a measurable Core Web Vitals metric, and therefore SEO and product-level outcomes.

- **Not recognizing when DOM/CSS animation physically stops scaling** — trying to optimize thousands of animated DOM nodes with point fixes instead of recognizing the architectural ceiling and moving to Canvas/WebGL.
