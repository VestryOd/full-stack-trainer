# SVG, D3, and Choosing a Visualization Technology

## Closing the decision space

Articles 01-06 covered the path from immediate-mode Canvas 2D through WebGL/Pixi/three.js. This article brings SVG back into the picture — a technology that's neither canvas nor WebGL, and a genuinely underrated third option — and clears up d3.js, probably the most misunderstood library in the entire data-visualization space (not least because its name sounds similar to three.js, even though they're two entirely unrelated tools for two different jobs). The goal is a coherent map of the whole choice: DOM/CSS → SVG → Canvas 2D → WebGL/Pixi → off-the-shelf charting libraries, and an honest rule for when to move from one level to the next.

## SVG: a retained-mode vector DOM

SVG elements (`<circle>`, `<rect>`, `<path>`) are REAL DOM nodes, literally the same kind of thing as a `<div>`, just drawing themselves as vector geometry instead of a block layout:

```html
<svg width="400" height="300">
  <circle cx="100" cy="100" r="20" fill="steelblue" />
</svg>
```

Everything else that sets SVG apart from canvas follows from that:

```txt
- Inspectable in DevTools like any other DOM element
- Styleable via CSS (fill, stroke are ordinary CSS properties),
  animatable via CSS transitions/WAAPI (the same retained-mode
  model covered in browser-animation — SVG shares it fully)
- Accessible to screen readers out of the box: ARIA attributes
  attach directly to elements, and assistive tech traverses the
  SVG tree the same way it does ordinary DOM
- Crisp at any zoom/DPI, because it's a vector, not a raster
  buffer — the devicePixelRatio problem from article 01 simply
  doesn't exist for SVG
```

**But every SVG element is a real DOM node with real DOM overhead** (style recalculation, layout, per-node memory) — the same costs covered for DOM animation in the browser-animation topic. A scatterplot with 50,000 `<circle>` elements is 50,000 live DOM nodes, and the browser pays for EVERY one of them on the initial render, on any update, and while scrolling the page. The same scatterplot on canvas is one DOM node total (the `<canvas>` itself), regardless of whether there are 50 or 50,000 points inside it.

## What d3 actually is — and what it is NOT

d3 stands for **Data-Driven Documents**. It is NOT a 3D library (despite sounding like "three.js" — a naming coincidence, not a related tool), and it's not primarily a charting library either — it's a collection of small, independent, composable modules:

```txt
d3-selection  — querying and manipulating DOM nodes (conceptually
                 like jQuery, but aware of bound data)
d3-scale       — PURE functions: a data domain → a visual range
                 (linear, time, ordinal, log scales)
d3-shape       — PURE functions: an array of data → shape geometry
                 (line, area, arc, pie)
d3-axis        — rendering ticks and labels for a given scale
d3-force       — force-directed simulation for graph node layout
d3-geo         — map projections
... plus dozens more narrowly-focused modules
```

The key insight: most of d3's real value is MATH and DATA-BINDING utilities, entirely independent of HOW you end up rendering the result. `d3-scale`/`d3-shape` return numbers and geometry strings — they don't care whether the result ends up in an SVG `<path>`'s `d` attribute or a `ctx.lineTo()` call on canvas.

## Selections and the data join: enter/update/exit, and the modern `.join()`

```javascript
d3.select('svg')
  .selectAll('circle')
  .data(dataset, (d) => d.id) // bind DOM nodes to array elements by id
  .join(
    (enter) => enter.append('circle').attr('r', 0)
      .call((e) => e.transition().attr('r', 5)), // NEW data — create a node
    (update) => update, // data with an EXISTING node — just update its attributes
    (exit) => exit.transition().attr('r', 0).remove(), // a node with NO data left — remove it
  )
  .attr('cx', (d) => xScale(d.x))
  .attr('cy', (d) => yScale(d.y));
```

The data join reconciles a data array against DOM nodes already bound to the PREVIOUS data state, splitting the result into three explicit categories: **enter** — data with no matching DOM node yet (needs to be created), **update** — data that already has a matching node (just needs its attributes refreshed), **exit** — nodes with no matching data anymore (need to be removed). Conceptually, this solves the same problem React reconciliation does (diffing a previous tree against a new one), just done EXPLICITLY and by hand rather than through a hidden virtual-DOM algorithm — and this pattern predates React by years. `.join()` is the modern, consolidated API that replaced the more verbose idiom of three separate enter/update/exit selection variables from earlier d3 versions.

## Scales and shape generators: the real, reusable core

```javascript
const xScale = d3.scaleLinear().domain([0, 100]).range([0, width]); // pure math: data → pixels
const yScale = d3.scaleLinear().domain([0, maxValue]).range([height, 0]);

const lineGenerator = d3.line()
  .x((d) => xScale(d.x))
  .y((d) => yScale(d.y)); // returns a STRING for an SVG <path>'s d="..." attribute
```

This is d3's real, durable core value — not the data join (which many projects don't even use, relying on React/Vue for the DOM instead) and not SVG rendering specifically, but renderer-agnostic scale math and shape geometry generation from data.

## The hybrid pattern: d3's math + canvas rendering

Since `d3-scale`/`d3-shape` aren't tied to SVG, you can use them for large datasets while drawing the result to canvas instead of thousands of DOM nodes:

```javascript
const path = d3.line()
  .x((d) => xScale(d.x))
  .y((d) => yScale(d.y))
  .context(ctx); // the KEY method: context() redirects the shape
                  // generator to draw via ctx.moveTo()/lineTo() instead
                  // of returning an SVG path string

ctx.beginPath();
path(dataset); // the same scale/shape math as for SVG, but the result
                // goes straight into article 01's canvas primitives
ctx.strokeStyle = 'steelblue';
ctx.stroke();
```

This is exactly the technique a senior engineer should be able to propose in answer to "how do you visualize 100,000 points if d3 usually draws to SVG": don't abandon d3 entirely — keep its excellent scale/shape math, drop SVG's per-node DOM overhead entirely, and switch rendering to canvas (articles 01-03). The question "SVG or canvas" and the question "should I use d3" are actually ORTHOGONAL to each other.

## An honest decision framework

```txt
SVG            — interactive dashboards, up to ~1-2 thousand
                  elements, when accessibility, CSS styling,
                  crispness at any zoom, and rich per-element
                  interactivity matter (ordinary DOM events/hover
                  states are easiest to wire up on individual SVG nodes)

Canvas 2D      — 10,000+ points, scatterplots, heatmaps, custom
                  visualization needing per-pixel control — where
                  DOM node count alone would become the bottleneck

WebGL/Pixi     — 100,000+ points, or high-frequency real-time
                  updates (streaming data, live dashboards with huge
                  series) — where even Canvas 2D's CPU rasterization
                  hits a ceiling (article 04: batching and GPU parallelism)

Off-the-shelf  — ECharts, Chart.js, and similar libraries cover ~90%
charting          of "standard" needs (bar/line/pie/scatter with
libraries         legends, tooltips, responsive resizing) with far
                  less code and much more polished out-of-the-box
                  behavior (accessibility, interaction) than a
                  hand-rolled d3 build
```

**The honest, senior-level build-vs-buy reasoning:** a hand-rolled d3 build earns its place for BESPOKE, non-standard visualization that doesn't fit the model of any off-the-shelf charting library (unique layouts, novel interaction patterns, original visual encodings of data). If the task is "build a bar chart with tooltips," reaching for d3 directly instead of a ready-made library almost always means reinventing legends, responsiveness, and accessibility that are already solved elsewhere, in exchange for an illusory "flexibility" that rarely turns out to be genuinely needed in practice. Reach for d3 not because it's powerful (true, but not an argument on its own), but because the specific visualization design genuinely can't be expressed by any existing charting tool.

## Connection to other articles

```txt
[Canvas 2D Fundamentals]              — the drawing primitives
                                         d3-shape switches to via
                                         .context() for large datasets
[WebGL and GPU Fundamentals] /
[Pixi.js in Depth]                    — the next tier, once even
                                         canvas rendering of a dataset
                                         hits a performance ceiling
[Architecture and Performance for
 Canvas Apps]                          — hybrid SVG/canvas
                                         architectures and profiling
                                         at data scale, covered here
                                         at the conceptual level
```

## Common interview traps

- **Confusing d3.js with a 3D/WebGL library** — not knowing "D3" stands for Data-Driven Documents and has nothing to do with 3D graphics — a common mix-up caused by the name sounding like three.js.

- **Not knowing why SVG "doesn't scale" for large datasets** — not connecting the performance degradation to the fact that every SVG element is a real DOM node with real style-recalc/layout/memory overhead, rather than a vague "SVG is slow."

- **Being unable to explain enter/update/exit** — not knowing it's an explicit, manual version of what React does through hidden virtual-DOM reconciliation, and that the modern API for it is `.join()`.

- **Assuming d3 is inseparable from SVG** — not knowing that `d3-scale`/`d3-shape` are renderer-agnostic, pure math, and that `d3.line().context(ctx)` lets you draw the same geometry to canvas instead of SVG.

- **Having no framework for choosing between SVG/Canvas/WebGL by data volume** — being unable to give even rough guidelines (thousands → SVG, tens of thousands → canvas, hundreds of thousands/real-time → WebGL).

- **Always reaching for a hand-rolled d3 build instead of an off-the-shelf charting library** — having no honest build-vs-buy reasoning: for standard charts, a ready-made library is almost always the better trade in development time and out-of-the-box accessibility/interaction quality.
