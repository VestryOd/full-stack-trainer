# Performance Debugging and Jank Hunting

## From theory to "why is this animation janky in this exact place"

Articles 01-05 gave you the vocabulary and the tools: the rendering pipeline, cheap versus expensive properties, WAAPI (Web Animations API), `requestAnimationFrame` (rAF), and libraries.

This article is about the senior engineer's actual workflow. The tech lead sends a screen recording with no other detail attached. The caption: "the landing page is choppy while scrolling on an iPhone SE" (SE — Special Edition). Jank is, physically, a missed frame (article 01). Diagnosing it isn't "stare at the code and guess". It is a specific sequence of DevTools tools, each answering a different question.

## The Performance panel: where time is physically being lost

Recording (Record → replay the problematic interaction → Stop) gives you a main-thread flame chart — the first and most informative tool.

```txt
How to read the flame chart:
┌───────────────────────────────────────────────────────────┐
│ Main                                                      │
│ ▓▓▓▓░░░▓▓▓▓▓▓▓▓▓▓▓▓░░░▓▓▓░░░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░       │
│  JS   Style Layout  Paint    JS (rAF callback)  Composite │
└───────────────────────────────────────────────────────────┘
  The horizontal axis is time.
  Block color = category of work:
  yellow  = Scripting (your JS)
  purple  = Rendering (Style/Layout)
  green   = Painting
  blue    = Loading
```

Three signals are worth looking for specifically:

| Signal in the flame chart | What it means |
|---|---|
| Main-thread JS block over 50 ms, red triangle | A Long Task. The user feels the delay. |
| Purple Layout block, "Forced reflow" | A geometry read right after a style write. |
| Layout → Paint → Composite every tick | A layout property is animated, not `transform`. |

- **Long Tasks.** Any continuous block of main-thread JS longer than 50 ms gets flagged with a red triangle in the corner of the block. That is an empirically derived threshold. Tasks shorter than 50 ms don't register as a response delay to a user. Longer ones block the main thread long enough to be noticeable. The same threshold underlies INP (Interaction to Next Paint), a metric covered below.

- **Forced reflow.** A purple Layout block flagged "Forced reflow", with a yellow exclamation mark. It means exactly what article 01 covered. JS read geometry (`offsetHeight` and similar) right after writing a style. So the browser had to compute layout synchronously, outside its normal batching. Clicking the warning in DevTools expands a **stack trace** — the exact line of code that caused it. That is the fastest way to find layout thrashing in a real application, without reading the whole codebase line by line.

- **A repeating Layout → Paint → Composite pattern on every animation frame.** If an animation's flame chart shows all three blocks on every tick, a layout-triggering property is being animated, not `transform`/`opacity`. Examples are `top` and `width`; the full table is in article 01. A healthy compositor-only animation ideally shows only thin Composite blocks, with nothing in between.

## The Layers panel: why there are more layers than expected

`DevTools → More tools → Layers` gives a 3D visualization of every composited layer on the page. It splits the page along the Z axis and shows exactly what became its own layer, and why.

```txt
For each layer, the panel shows:
  - Compositing Reasons — the exact reason it was promoted
    ("has a will-change: transform", "is animated", etc.) —
    no need to guess what triggered the layer
  - Memory estimate — how much GPU memory the layer occupies
    (directly tied to the width × height × 4 bytes formula
    from article 01)
```

**Layer explosion** is diagnosed here directly. If the panel shows dozens to hundreds of layers where you expected 3-5 — the elements actually being animated — something is promoting layers for you.

The cause is almost always `will-change` left on static elements "just in case", the anti-pattern from article 01. The other common cause is a CSS filter or 3D transform on a component that renders in bulk. Say every card in a list of a hundred got a `filter` for its shadow: each one became its own layer.

## Paint flashing and the paint profiler: what's repainting when it shouldn't

`DevTools → Rendering tab → Paint flashing` highlights any screen area that gets repainted, usually with a green rectangle. It does this in real time, while you interact with the page.

```txt
Diagnostic scenario: scrolling a news feed flashes green across
the entire visible height on every scroll frame — even though
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

Watch `box-shadow` and `filter: blur()` separately. A noticeable "hot zone" in paint flashing on an element that looks static almost always means one thing. The shadow or blur is being repainted from scratch every frame.

For example, `box-shadow` is animated directly, instead of the transform of a pre-rendered shadow. Rasterizing a large blur radius on the CPU (central processor) or GPU (graphics processor) is noticeably more expensive than a plain fill.

## FPS meter and frame rendering stats: a quick sanity check

`DevTools → Rendering tab → Frame Rendering Stats` turns on an overlay right on top of the page. It shows live FPS (frames per second), GPU memory usage and a dropped-frame counter. This is not a recording but a live monitor, for a quick check of the kind "did the change I just made regress anything?". You get the answer without going through a full Performance-panel recording.

## Common causes of jank — and concrete fixes

| Cause | Diagnosis | Fix |
|---|---|---|
| Layout thrashing | "Forced reflow" warning | Split reads from writes |
| Animating layout properties | Layout+Paint every frame | Use `transform`/`opacity` |
| Too many or oversized layers | Layers panel, Memory estimate | Don't promote decoration |
| `box-shadow`/`filter` animated | Hot zone in paint flashing | Animate a pseudo-element |
| Scroll handler reads geometry | Forced reflow on every scroll | `{ passive: true }` |

### Layout thrashing

Covered in depth in article 01. Diagnosis: "Forced reflow" in the Performance panel. Fix: separate the read phase (`offsetHeight` and similar) from the style-write phase, never interleave them in a loop.

### Animating layout properties instead of transform/opacity

Diagnosis: a repeating Layout+Paint on every animation frame in the flame chart (see above). Fix: see the table in article 01 — rewrite the animation using `transform`/`opacity`.

### Excessive or oversized layers on mobile

```txt
Symptom: a full-screen background video or gradient image is
promoted to its own full-screen layer — unnoticeable on desktop,
but on a budget Android device with memory shared between CPU
and GPU, it causes noticeable lag across the whole page, not
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

`{ passive: true }` isn't a micro-optimization. Without it the browser **must** synchronously wait for the JS handler to finish on every scroll event, before committing the visual scroll. The reason: in principle the handler could call `preventDefault()` and cancel that scroll.

There are two reliable ways to guarantee your JS never blocks native scrolling. One is `{ passive: true }`. The other is dropping the `scroll` listener entirely in favour of `IntersectionObserver`.

## `content-visibility` and CSS containment: don't render what isn't visible

On long pages with many sections — docs, feeds, catalogs — the browser by default computes Style/Layout/Paint for the **entire** document. That includes content far outside the current viewport. The `content-visibility: auto` declaration explicitly lets the browser skip rendering work for content that isn't currently visible:

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

The `contain` property, used without `content-visibility`, is a finer-grained and manual tool. It explicitly tells the browser that changes **inside** an element shouldn't require recomputing layout or paint **outside** it:

```css
.independent-widget {
  contain: layout paint; /* this element is an isolated "container":
    its internal changes don't force the browser to recompute
    geometry or repaint anything beyond its own boundaries */
}
```

This scopes layout thrashing inside the widget to the widget itself, not the whole document. It is useful for complex widgets that often change their internal markup: a data grid, a canvas wrapper, a chat with frequently updating messages.

## `OffscreenCanvas` — when DOM animation simply stops scaling

There is a point past which DOM (document object model — the browser's tree of page elements) animation is physically the wrong tool. Three examples: thousands of independently animated particles, a complex physics simulation, and frame-by-frame rendering where every element is its own DOM node.

Every DOM node carries overhead with it: its own composited layer when animated, its own entry in the style tree, its own hit-testing. Hit-testing is the check of which element a pointer event landed on. At a scale of thousands of elements, that overhead starts to dominate over the useful work itself.

```txt
┌────────────────────────────────────────────┐
│ Thousands of animated DOM nodes            │
└────────────────────────────────────────────┘
                       │  measure
                       ▼
┌────────────────────────────────────────────┐
│ Profiler: Style/Layout time grows with the │
│ number of nodes, not with the complexity   │
│ of the animation                           │
└────────────────────────────────────────────┘
                       │  read the shape
                       ▼
┌────────────────────────────────────────────┐
│ An architectural ceiling, not a missing    │
│ optimization pass                          │
└────────────────────────────────────────────┘
                       │  switch tool
                       ▼
┌────────────────────────────────────────────┐
│ OffscreenCanvas: raster rendering in a     │
│ Worker, off the main thread and the DOM    │
└────────────────────────────────────────────┘
```

The signal to switch isn't "it got a bit slower". It is qualitative. Watch the shape of the growth in the profiler. Style/Layout time may grow linearly with the number of animated DOM nodes, rather than with the complexity of the animation itself. That is an architectural ceiling, not a case for one more optimization pass.

At that point `OffscreenCanvas` lets you do raster rendering in a separate Worker thread, using Canvas 2D or WebGL (3D graphics in the browser). That is entirely off the main thread and off the DOM tree. Actually drawing on Canvas and WebGL is its own topic, Canvas & Graphics. What matters here is recognizing the moment DOM/CSS animation has hit its ceiling.

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
      scripts: entry.scripts.map((s) => ({     // which script is responsible
        name: s.name,
        duration: s.duration,
        // e.g. a specific event listener or rAF callback
        invoker: s.invoker,
      })),
    });
  }
}).observe({ type: 'long-animation-frame', buffered: true });
```

The plain Long Tasks API just reports "something took over 50 ms". LoAF goes further. It breaks a "heavy" frame down into phases: how much went to script, how much to Style/Layout. It also points at the specific script responsible. On real user devices this gives you the same information as a stack trace in the Performance panel, without reproducing the issue locally.

**INP (Interaction to Next Paint)** is a Core Web Vitals metric. It measures the delay between a user's action and the moment the browser physically shows the next updated frame in response. The action can be a click, a tap or a keypress.

This ties directly back to this article's subject. Suppose an rAF callback or a JS-driven animation holds the main thread longer than the frame budget (article 01). Now suppose that happens exactly when a user interacts with the page. Then the response frame is delayed: a button's visual "pressed" state, for example. That hurts INP directly, in exactly the same way it hurts the animation's own perceived smoothness.

Many teams already optimize LCP (Largest Contentful Paint) and CLS (Cumulative Layout Shift). For them the point is worth making plainly. Heavy, poorly budgeted animation isn't just an "aesthetic" problem. It is a measurable factor in the same Web Vitals report, with real consequences for SEO (search engine optimization) and product metrics.

## Connection to other articles

- [Rendering Pipeline and Frame Budget](./01-rendering-pipeline-and-frame-budget.md) — the foundation: what layout thrashing, GPU layers and the frame budget actually are. Here those concepts become diagnostic tools.
- [requestAnimationFrame and JS-Driven Animation](./04-raf-and-js-driven-animation.md) — a typical source of Long Tasks in animation: a heavy rAF callback with no regard for the frame budget.
- [Animation Libraries and the Ecosystem](./05-animation-libraries-and-ecosystem.md) — the diagnostics in this article apply equally to code you wrote yourself and to animation driven by a library.
- [Motion Design Patterns and Accessibility](./07-motion-design-patterns-and-accessibility.md) — what to actually do with a diagnosed problem at the product level. Simplify it, remove it, or replace it with a reduced-motion variant.

## Common interview traps

- **Not knowing what a "forced reflow" looks like in DevTools.** Being unable to describe that the Performance panel flags these cases explicitly, with a purple block and a warning. And that it provides a stack trace pointing to the exact line of code.

- **Confusing paint flashing with the FPS meter.** Not distinguishing the tools by purpose. Paint flashing shows **which areas** are repainting. The FPS meter only shows an aggregate frame rate, with no way to localize the cause.

- **Not knowing about `{ passive: true }`.** A non-passive scroll or touch listener forces the browser to synchronously wait for the JS handler to finish. Only then can it visually commit the scroll. This isn't about "the JS running a bit faster". It is about blocking the scroll itself.

- **Not knowing about `content-visibility`.** Proposing list virtualization, such as `react-window`, as the only fix for long-page performance. Not knowing about the simpler CSS alternative for content that can't be virtualized — an ordinary long document, say, rather than a list of identical items.

- **Assuming the local DevTools Performance panel is representative of production.** Not knowing about the Long Animation Frames API and `PerformanceObserver` as a way to get the same kind of data from actual user devices.

- **Not connecting animation performance to INP.** Treating animation jank as a purely "visual" concern. Not understanding that it directly affects a measurable Core Web Vitals metric, and therefore SEO and product-level outcomes.

- **Not recognizing when DOM/CSS animation physically stops scaling.** Trying to optimize thousands of animated DOM nodes with point fixes, instead of recognizing the architectural ceiling and moving to Canvas or WebGL.
