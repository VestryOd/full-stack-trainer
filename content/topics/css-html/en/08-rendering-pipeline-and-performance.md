# Rendering Pipeline and Performance

## The pipeline — what happens between HTML and pixels

When a browser renders a page, it executes a sequence of distinct stages. Understanding which stages a CSS change triggers is what separates "I'll add a transition" from "I'll add a transition that runs at 60fps."

```
HTML/CSS → Parse → Style → Layout → Paint → Composite → Screen
```

Each stage can invalidate subsequent ones — triggering Layout always triggers Paint and Composite. Triggering only Composite skips Layout and Paint entirely.

### Stage 1: Parse

The browser parses HTML into a DOM tree and CSS into a CSSOM tree. These are merged into the **Render Tree** — only elements that affect visual output are included (`display: none` elements are excluded; `visibility: hidden` elements are included, they just paint as transparent).

Blocking behavior:
- CSS is **render-blocking**: the browser won't paint until the CSSOM is built (a partial CSSOM could cause flash of unstyled content)
- JavaScript is **parser-blocking** by default (unless `async` or `defer`): a `<script>` tag pauses HTML parsing until the script downloads and executes
- `defer` scripts execute after parsing completes, in order
- `async` scripts execute as soon as downloaded, possibly out of order

### Stage 2: Style (Recalculate Style)

The browser computes the **computed style** for every element in the render tree — resolving inheritance, the cascade, custom properties, and relative units. This is where `em`, `%`, `var()` become absolute pixel values.

What triggers a full style recalculation:
- Adding/removing a class on any element
- Any DOM insertion or removal
- Changes to CSS custom properties
- Pseudoclass state changes (`:hover`, `:focus`)

The cost of style recalculation scales with the number of elements affected. Deep selector chains (`div > section > article > .card > p`) require the browser to walk more of the tree — one reason shallow selectors and BEM are faster in large DOMs.

### Stage 3: Layout (Reflow)

Layout computes the **geometry** of every element — position, size, and relationship to other elements. This is the most expensive stage because layout is **interdependent**: changing one element's size can cascade changes through siblings, parents, and the entire document.

```
Layout is computed in document order.
Each block element's width is determined by its container.
Each block element's height is determined by its content (unless explicitly set).
A change to an element's height can change every sibling's position below it.
A change to a flex container's size can reposition all its flex items.
```

**What triggers Layout:**

Any property that affects the geometry of an element or its surroundings:
- `width`, `height`, `min-width`, `max-width`, `min-height`, `max-height`
- `padding`, `margin`, `border-width`
- `top`, `right`, `bottom`, `left` (for positioned elements)
- `font-size`, `font-weight`, `line-height`, `letter-spacing`
- `display`, `position`, `float`, `flex`, `grid` and their sub-properties
- `overflow`, `white-space`
- `content` (on pseudo-elements)

Reading certain JavaScript properties forces the browser to perform a **synchronous layout** (called "forced reflow") before the JavaScript can get an accurate value:

```javascript
// These properties trigger synchronous layout when read:
el.offsetWidth, el.offsetHeight
el.offsetTop, el.offsetLeft
el.scrollWidth, el.scrollHeight
el.scrollTop, el.scrollLeft
el.clientWidth, el.clientHeight
window.getComputedStyle(el)
el.getBoundingClientRect()
```

### Stage 4: Paint

Paint records drawing instructions for each layer: backgrounds, borders, text, shadows, outlines. The output is a list of drawing commands, not actual pixels yet. Paint happens per **layer** — elements on the same layer are painted together.

**What triggers Paint (but not Layout):**

Properties that change appearance without affecting geometry:
- `color`, `background-color`, `background-image`
- `border-color`, `outline-color`
- `box-shadow`, `text-shadow`
- `visibility` (but not `display`)
- `border-radius` (debated — some browsers may skip layout)

### Stage 5: Composite

The browser takes all the painted layers, applies transforms and opacity, and composites them together into the final frame — using the GPU. This is the cheapest stage because it's entirely GPU-side and doesn't require the main thread.

**What triggers only Composite (skipping Layout and Paint):**

Only two CSS properties are composited without paint on all major browsers:
- `transform` (including `translate`, `rotate`, `scale`)
- `opacity`

This is the most important performance rule in CSS: **animate `transform` and `opacity`, not `left`/`top` or `color`.**

```css
/* Triggers Layout + Paint + Composite on every frame — expensive */
@keyframes move-bad {
  from { left: 0; }
  to   { left: 200px; }
}

/* Triggers only Composite — runs entirely on GPU, smooth 60fps */
@keyframes move-good {
  from { transform: translateX(0); }
  to   { transform: translateX(200px); }
}
```

## GPU compositing layers — what creates them

The GPU compositor works with discrete layers. Certain CSS properties cause the browser to **promote** an element to its own GPU layer (called a "compositing layer" or "compositor layer"):

**Guaranteed layer promotion:**
- `will-change: transform` or `will-change: opacity`
- `transform: translateZ(0)` or `transform: translate3d(0,0,0)` (old hack)
- Elements with CSS animations running on the compositor thread (transform/opacity animations)
- `position: fixed` elements
- `<video>`, `<canvas>`, `<iframe>` elements

**Conditional promotion:**
- Elements overlapping other promoted elements (squashing/compositing overlap)
- Elements with `filter` or `backdrop-filter`

### Why layer promotion helps

Once on its own GPU layer, an element's transform and opacity changes don't require the CPU to re-paint — the GPU handles the compositing directly. A layer's content is uploaded to GPU memory once and reused across frames.

```
Without layer promotion:
  Frame 1: Animate left → Layout → Paint → Composite (CPU + GPU)
  Frame 2: Animate left → Layout → Paint → Composite (CPU + GPU)
  Frame N: Animate left → Layout → Paint → Composite (CPU + GPU)
  → Expensive every frame

With layer promotion (transform):
  Upload: Paint to GPU texture once
  Frame 1: Composite (GPU only) — apply transform matrix
  Frame 2: Composite (GPU only) — apply transform matrix
  Frame N: Composite (GPU only) — apply transform matrix
  → Cheap every frame
```

### The cost of too many layers

GPU layers consume GPU memory. Promoting too many elements causes:
- High GPU memory usage (visible as jank in Chrome DevTools → Memory)
- **Layer explosion**: when a promoted element overlaps many other elements, the browser may promote all overlapping elements to prevent rendering artifacts — creating dozens of unintended layers

## `will-change` — usage and risks

`will-change` hints to the browser that an element will change a specific property, allowing the browser to prepare an optimization (usually layer promotion) in advance.

```css
/* Tell the browser: this element's transform will change soon */
.modal {
  will-change: transform;
  /* Browser promotes to GPU layer before the animation starts */
}
```

### The rules for responsible `will-change` use

**1. Apply it before the change, remove it after**

```css
/* Wrong: always on, wastes GPU memory perpetually */
.card {
  will-change: transform;
}

/* Correct: add on hover (gives browser time to prepare), remove when done */
.card:hover {
  will-change: transform;
}

/* Or via JavaScript for explicit control */
button.addEventListener('click', () => {
  element.style.willChange = 'transform';
  element.addEventListener('animationend', () => {
    element.style.willChange = 'auto';
  }, { once: true });
});
```

**2. Don't use it as a cargo-cult performance fix**

`will-change` doesn't make anything faster by itself — it only promotes to a GPU layer, which saves time during animation but costs GPU memory. If the element doesn't actually animate, `will-change` is pure overhead.

**3. Don't blanket-apply it**

```css
/* Never do this */
* { will-change: transform; }
/* Promotes every element to its own GPU layer — catastrophic memory usage */
```

**4. Use sparingly — only for elements you know will animate**

Good candidates: modals, drawers, tooltips, loading spinners, parallax elements.

### `will-change` vs the old `translateZ(0)` hack

```css
/* Old technique: force GPU layer by making the element 3D-transformed */
.element { transform: translateZ(0); }

/* Modern equivalent */
.element { will-change: transform; }
```

`will-change` is preferable: it's declarative (states intent, not implementation), the browser can choose the best optimization strategy, and it doesn't add a transform to the element that might affect stacking contexts or coordinates.

## The `contain` property — layout and paint containment

`contain` tells the browser that an element's subtree is **independent** of the rest of the document in specific ways. This allows the browser to skip entire sections of the document when recalculating layout or paint.

```css
.widget {
  contain: layout;
  /* Layout changes inside .widget don't affect elements outside it.
     The browser can reflow .widget without reflowing the rest of the page. */
}
```

### `contain` values

```css
contain: layout;
/* Internal layout is isolated.
   Changes inside don't affect external elements, and vice versa.
   Also establishes: stacking context, block formatting context,
   absolute/fixed positioning containing block. */

contain: paint;
/* Element acts as a viewport for its subtree.
   Descendants can't overflow and be visible outside.
   Also establishes: stacking context, block formatting context,
   absolute/fixed positioning containing block.
   Similar to overflow: hidden but with additional performance hints. */

contain: style;
/* CSS counters and quotes are scoped to this subtree.
   (Rarely needed, limited browser optimization benefit) */

contain: size;
/* Element's size is independent of its contents.
   Browser doesn't need to look at descendants to determine the element's size.
   Requires explicit width + height — otherwise element collapses to 0. */

contain: strict;       /* layout + paint + size + style */
contain: content;      /* layout + paint + style (most useful combo without size) */
```

### Real-world `contain` usage

```css
/* Widget in a news feed — content changes frequently, should not reflow the feed */
.news-item {
  contain: content; /* layout + paint + style */
}

/* Fixed-size card in a grid — size never changes based on content */
.thumbnail-card {
  contain: strict;
  width: 280px;
  height: 200px;
}

/* Component with complex internal animations — prevent paint invalidation spreading */
.chart-container {
  contain: paint;
  /* Internal canvas redraws don't trigger paint for sibling elements */
}
```

### `contain: layout` and absolute positioning

An important side effect: `contain: layout` (and `contain: paint`) makes the element a containing block for absolutely positioned descendants — same as `position: relative`. This is intentional: if internal layout is isolated, absolutely positioned children must be contained within it.

## `content-visibility` — skip rendering of off-screen content

`content-visibility` tells the browser to skip rendering work for off-screen content entirely:

```css
.article-section {
  content-visibility: auto;
  contain-intrinsic-size: 0 500px; /* estimated size while not rendered */
}
```

With `content-visibility: auto`:
- Off-screen sections are not laid out, painted, or composited
- The browser uses `contain-intrinsic-size` as a placeholder to maintain scroll position
- When the section scrolls into view, it's rendered normally

The performance benefit on long pages can be dramatic — a 10,000-item list only pays rendering cost for the visible items. Unlike virtualization (which requires JavaScript), `content-visibility` is pure CSS.

## Avoiding layout thrashing

**Layout thrashing** occurs when JavaScript alternates between reading and writing layout properties in a tight loop, causing the browser to perform synchronous reflows on every read:

```javascript
// Layout thrashing — forces a synchronous reflow on every iteration
const boxes = document.querySelectorAll('.box');
boxes.forEach(box => {
  const width = box.offsetWidth; // forces reflow to get accurate value
  box.style.width = width * 2 + 'px'; // invalidates layout
  // Next iteration: offsetWidth forces another reflow because layout was invalidated
});

// Fixed: batch reads, then batch writes
const widths = Array.from(boxes).map(box => box.offsetWidth); // batch reads
boxes.forEach((box, i) => {
  box.style.width = widths[i] * 2 + 'px'; // batch writes
});
// One reflow for all reads, one layout update for all writes
```

The principle: **read first, then write.** Never interleave reads and writes to layout-affecting properties.

**`requestAnimationFrame`** batches writes to happen at the start of the next frame:

```javascript
// Schedule visual updates to happen at the right time in the rendering pipeline
function animate() {
  requestAnimationFrame(() => {
    element.style.transform = `translateX(${pos}px)`;
    pos += 1;
    if (pos < 200) animate();
  });
}
```

## CSS triggers reference

The most important table to know for senior interviews:

| Property | Layout | Paint | Composite |
|---|---|---|---|
| `width`, `height`, `margin`, `padding` | ✓ | ✓ | ✓ |
| `top`, `left` (positioned) | ✓ | ✓ | ✓ |
| `font-size`, `line-height` | ✓ | ✓ | ✓ |
| `display`, `position` | ✓ | ✓ | ✓ |
| `color`, `background-color` | — | ✓ | ✓ |
| `box-shadow`, `border-radius` | — | ✓ | ✓ |
| `visibility` | — | ✓ | ✓ |
| `outline`, `outline-color` | — | ✓ | ✓ |
| **`transform`** | **—** | **—** | **✓** |
| **`opacity`** | **—** | **—** | **✓** |

`transform` and `opacity` are in a class of their own: they touch only the Composite stage.

## Common interview traps

**"What's the difference between reflow, repaint, and compositing?"**

Reflow (Layout): the browser recalculates geometry — positions and sizes of all affected elements. Triggered by any property that changes dimensions or positioning. Most expensive — cascades through the document. Repaint (Paint): the browser re-records drawing commands for a layer's visual appearance. Triggered by color/style changes that don't affect geometry. Compositing: the GPU combines layers into the final frame — only transforms and opacity can be changed without triggering reflow or repaint. Most performant — runs on GPU without main thread involvement.

---

**"Why is animating `transform: translateX()` cheaper than `left: Xpx`?"**

`left` is a layout property — changing it triggers Layout → Paint → Composite on every frame (CPU-bound work). `transform` is a compositing property — the browser promotes the element to a GPU layer, paints it once, then only applies a matrix transformation each frame (GPU-bound, extremely cheap). The element's layout position doesn't change when `transform` is used — the GPU reads the layer's texture and applies the transform to it, no CPU work required.

---

**"What does `will-change` actually do?"**

It signals to the browser that a specific property will change soon. The browser typically responds by promoting the element to a GPU compositing layer early — before the animation starts — so the layer transition doesn't cause a jank on the first frame. It's a hint, not a guarantee. Risks: GPU memory overhead (each promoted layer uses VRAM), potential layer explosion when a promoted element overlaps many others. Apply it immediately before animation, remove it immediately after.

---

**"What is layout thrashing and how do you prevent it?"**

Layout thrashing is a JavaScript pattern where reads and writes to layout-affecting DOM properties are interleaved in a loop. Each read forces the browser to flush pending style/layout changes to get an accurate value, causing a synchronous reflow. Each write then invalidates layout again. The fix: batch all reads first, then batch all writes. This way the browser performs one reflow for all reads and one layout update for all writes.

---

**"What does `contain: layout` do?"**

It declares that changes inside the element don't affect layout outside it, and vice versa. The browser can reflow the element's subtree without considering the rest of the document, and external layout changes don't propagate inside. Side effects: creates a stacking context, a block formatting context, and a containing block for absolutely/fixed positioned descendants. Most useful for frequently-updating components (news feeds, chat, data grids) where internal DOM changes should not cause a full-page reflow.

---

**"Which CSS properties trigger only Composite and why?"**

Only `transform` and `opacity` (on all major browsers). The reason: they don't affect geometry (no Layout) and don't change pixel-level appearance of the element itself (no Paint). The browser uploads the element as a texture to the GPU once, and subsequent changes are handled entirely by the GPU compositing stage — applying a matrix multiplication (`transform`) or alpha blend (`opacity`). This is intentional API design: the browser spec guarantees these properties don't trigger layout to enable performant animations.
