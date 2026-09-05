# SVG, d3.js, and Choosing a Visualization Technology

## Closing the decision space

This article puts SVG back on the map and clears up d3.js. SVG (scalable vector graphics) is a vector format built from DOM (document object model — the browser's tree of page objects) nodes. It is neither canvas nor WebGL (Web Graphics Library — the browser's low-level graphics API), and it is a genuinely underrated third option.

Articles 01-06 covered the path from immediate-mode Canvas 2D through WebGL/Pixi/three.js, so SVG is the piece that was missing. The most misunderstood library in the whole data-visualization space is probably d3.js. Part of the reason is the name: it sounds like three.js, and the two are entirely unrelated tools for different jobs.

The goal is a coherent map of the whole choice: DOM/CSS → SVG → Canvas 2D → WebGL/Pixi → off-the-shelf charting libraries. It comes with an honest rule for when to move from one level to the next.

## SVG: a retained-mode vector DOM

SVG is a **retained-mode** system: the browser keeps the element tree and repaints it for you. SVG elements (`<circle>`, `<rect>`, `<path>`) are **real** DOM nodes — literally the same kind of thing as a `<div>`. They just draw themselves as vector geometry instead of a block layout:

```html
<svg width="400" height="300">
  <circle cx="100" cy="100" r="20" fill="steelblue" />
</svg>
```

Everything else that sets SVG apart from canvas follows from that:

```txt
- Inspectable in DevTools like any other DOM element
- Styleable via CSS (fill, stroke are ordinary CSS properties)
- Animatable via CSS transitions and the Web Animations API
  (WAAPI). That is the same retained-mode model covered in
  browser-animation, and SVG uses all of it
- Accessible to screen readers out of the box: ARIA
  (accessible rich internet applications) attributes attach
  directly to elements, and assistive tech walks the SVG tree
  the way it walks ordinary DOM
- Crisp at any zoom level and any DPI (dots per inch), because
  it is a vector, not a raster buffer. The devicePixelRatio
  problem from article 01 does not exist for SVG
```

**But every SVG element is a real DOM node with real DOM overhead** — style recalculation, layout, per-node memory. Those are the same costs covered for DOM animation in the browser-animation topic.

A scatterplot with 50,000 `<circle>` elements is 50,000 live DOM nodes. The browser pays for **every** one of them on the initial render, on any update, and while scrolling the page. The same scatterplot on canvas is one DOM node total (the `<canvas>` itself), no matter whether there are 50 or 50,000 points inside it.

## What d3 actually is — and what it is not

d3 stands for **Data-Driven Documents**. It is **not** a 3D library, despite sounding like "three.js" — the names are a coincidence, not a sign of a related tool. It is not primarily a charting library either. It is a collection of small, independent, composable modules:

```txt
d3-selection  — querying and manipulating DOM nodes (conceptually
                 like jQuery, but aware of bound data)
d3-scale       — pure functions: a data domain → a visual range
                 (linear, time, ordinal, log scales)
d3-shape       — pure functions: an array of data → shape geometry
                 (line, area, arc, pie)
d3-axis        — rendering ticks and labels for a given scale
d3-force       — force-directed simulation for graph node layout
d3-geo         — map projections
... plus dozens more narrowly-focused modules
```

The key insight: most of d3's real value is **math** and **data-binding** utilities, entirely independent of **how** you render the result. Both `d3-scale` and `d3-shape` return numbers and geometry strings. They don't care whether the result ends up in an SVG `<path>`'s `d` attribute or in a `ctx.lineTo()` call on canvas.

## Selections and the data join: enter/update/exit, and the modern `.join()`

```javascript
d3.select('svg')
  .selectAll('circle')
  .data(dataset, (d) => d.id) // bind DOM nodes to array elements by id
  .join(
    (enter) => enter.append('circle').attr('r', 0)
      .call((e) => e.transition().attr('r', 5)), // new data — create a node
    (update) => update, // data that already has a node — just update attributes
    (exit) => exit.transition().attr('r', 0).remove(), // node with no data — drop it
  )
  .attr('cx', (d) => xScale(d.x))
  .attr('cy', (d) => yScale(d.y));
```

The data join reconciles a data array against DOM nodes already bound to the **previous** data state. It splits the result into three explicit categories:

- **enter** — data with no matching DOM node yet, so a node has to be created.
- **update** — data that already has a matching node, so the node's attributes just get refreshed.
- **exit** — nodes with no matching data anymore, so they have to be removed.

Conceptually this solves the same problem React reconciliation solves: diffing a previous tree against a new one. The difference is that d3 does it **explicitly** and by hand, not through a hidden virtual-DOM algorithm. The pattern also predates React by years.

`.join()` is the modern, consolidated API for it. It replaced the more verbose idiom of three separate enter/update/exit selection variables from earlier d3 versions.

## Scales and shape generators: the real, reusable core

```javascript
const width = 600;
const height = 400;
const maxValue = d3.max(dataset, (d) => d.y); // the largest y in the data

// pure math: data → pixels
const xScale = d3.scaleLinear().domain([0, 100]).range([0, width]);
const yScale = d3.scaleLinear().domain([0, maxValue]).range([height, 0]);

const lineGenerator = d3.line()
  .x((d) => xScale(d.x))
  .y((d) => yScale(d.y)); // returns a string for an SVG <path>'s d="..." attribute
```

This is d3's real, durable core value. It is not the data join — many projects don't even use it, relying on React or Vue for the DOM. It is not SVG rendering either. It is renderer-agnostic scale math and shape geometry generated from data.

## The hybrid pattern: d3's math + canvas rendering

`d3-scale` and `d3-shape` aren't tied to SVG. You can use them for large datasets, drawing the result to canvas instead of thousands of DOM nodes:

```javascript
// xScale/yScale come from the scales snippet above
const path = d3.line()
  .x((d) => xScale(d.x))
  .y((d) => yScale(d.y))
  .context(ctx); // the key method: context() redirects the shape
                  // generator to draw via ctx.moveTo()/lineTo() instead
                  // of returning an SVG path string

ctx.beginPath();
path(dataset); // the same scale/shape math as for SVG, but the result
                // goes straight into article 01's canvas primitives
ctx.strokeStyle = 'steelblue';
ctx.stroke();
```

A senior engineer should be able to propose exactly this when asked how to visualize 100,000 points, given that d3 usually draws to SVG. Don't abandon d3 entirely: keep its excellent scale/shape math, drop SVG's per-node DOM overhead, and switch rendering to canvas (articles 01-03).

The question "SVG or canvas" and the question "should I use d3" are **orthogonal** to each other.

## An honest decision framework

Two hardware terms show up below: the CPU (central processing unit) runs your JS, and the GPU (graphics processing unit) fills pixels.

```txt
SVG            — interactive dashboards, up to ~1-2 thousand
                  elements, when accessibility, CSS styling,
                  crispness at any zoom and rich per-element
                  interactivity matter (ordinary DOM events and
                  hover states are easiest to wire up on
                  individual SVG nodes)

Canvas 2D      — 10,000+ points, scatterplots, heatmaps, custom
                  visualization needing per-pixel control — where
                  DOM node count alone would become the bottleneck

WebGL/Pixi     — 100,000+ points, or high-frequency real-time
                  updates (streaming data, live dashboards with
                  huge series) — where even Canvas 2D's CPU
                  rasterization hits a ceiling (article 04:
                  batching and GPU parallelism)

Off-the-shelf  — ECharts, Chart.js and similar libraries cover
charting          ~90% of "standard" needs (bar/line/pie/scatter
libraries         with legends, tooltips, responsive resizing)
                  with far less code and much more polished
                  out-of-the-box behavior (accessibility,
                  interaction) than a d3 build you write yourself
```

**The honest, senior-level build-vs-buy reasoning:** write your own d3 build when the visualization is non-standard and fits the model of no off-the-shelf charting library. That means unique layouts, novel interaction patterns, original visual encodings of data.

If the task is "build a bar chart with tooltips," using d3 instead of a ready-made library almost always means reinventing legends, responsiveness and accessibility. All three are already solved elsewhere, and what you get back is a "flexibility" that rarely turns out to be needed.

Reach for d3 not because it's powerful — that's true, but it isn't an argument on its own. Reach for it because the specific visualization design genuinely can't be expressed by any existing charting tool.

## Connection to other articles

- [Canvas 2D Fundamentals](./01-canvas-2d-fundamentals.md) — the drawing primitives `d3-shape` switches to via `.context()` for large datasets.
- [WebGL and GPU Fundamentals](./04-webgl-and-gpu-fundamentals.md) and [Pixi.js in Depth](./05-pixijs-in-depth.md) — the next tier, once even canvas rendering of a dataset hits a performance ceiling.
- [Architecture and Performance for Canvas Apps](./08-architecture-and-performance-for-canvas-apps.md) — hybrid SVG/canvas architectures and profiling at data scale, covered here at the conceptual level.

## Common interview traps

- **Confusing d3.js with a 3D/WebGL library** — not knowing that `D3` is short for Data-Driven Documents and has nothing to do with 3D graphics. The mix-up is common, because the name sounds like three.js.

- **Not knowing why SVG "doesn't scale" for large datasets** — not connecting the performance degradation to a concrete cause. Every SVG element is a real DOM node with real style-recalc, layout and memory overhead. "SVG is slow" is not an explanation.

- **Being unable to explain enter/update/exit** — not knowing it's an explicit, manual version of what React does through hidden virtual-DOM reconciliation. The modern API for it is `.join()`.

- **Assuming d3 is inseparable from SVG** — not knowing that `d3-scale` and `d3-shape` are renderer-agnostic pure math. The call `d3.line().context(ctx)` draws the same geometry to canvas instead of SVG.

- **Having no framework for choosing between SVG/Canvas/WebGL by data volume** — being unable to give even rough guidelines. Thousands of elements → SVG; tens of thousands → canvas; hundreds of thousands or real-time → WebGL.

- **Always reaching for your own d3 build instead of an off-the-shelf charting library** — having no honest build-vs-buy reasoning. For standard charts a ready-made library is almost always the better trade, in development time and in out-of-the-box accessibility and interaction quality.
