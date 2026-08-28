# Rendering Performance

## The browser rendering pipeline — the foundation

Before optimizing, you need to understand what exactly happens when the browser draws pixels on screen:

```txt
JavaScript / CSS Animations
          ↓
      [Style]
          ↓
      [Layout] (Reflow)
          ↓
      [Paint]
          ↓
    [Composite]
```

Each stage does one job:

- **Style** — works out which CSS rules apply to each element.
- **Layout**, also called reflow — computes the size and position of every element. This is the most expensive step.
- **Paint** — fills in the pixels of each layer.
- **Composite** — combines the layers and puts the result on screen.

The core principle is that the earlier in this pipeline a change lets you exit, the cheaper that change is.

| What you change | How far it goes | Cost |
|---|---|---|
| `transform`, `opacity` | composite only, skips layout and paint | ~0.1ms, steady 60fps |
| `color`, `background` | paint only, skips layout | a few ms, can cause jank |
| `width`, `margin`, `font-size`, element position | the whole pipeline from scratch | tens of ms, visible freezes |

## Reflow (Layout) — the most expensive type of change

Reflow occurs when the browser recalculates the **geometry of the page** — the sizes and positions of elements.

### What triggers reflow

```ts
// ❌ All of these trigger reflow:

// Changing geometric properties
element.style.width = '200px';
element.style.margin = '10px';
element.style.padding = '20px';
element.style.fontSize = '16px';
element.style.display = 'flex';

// Adding/removing DOM nodes
parent.appendChild(newChild);
parent.removeChild(oldChild);

// Changing text content
element.textContent = 'New text'; // may change element size

// Toggling classes that affect geometry
element.classList.add('expanded'); // if .expanded changes width/height
```

```ts
// ❌ READING layout properties also triggers reflow!
// The browser must flush all pending style changes first
// to return an accurate value

const properties = [
  'offsetWidth', 'offsetHeight', 'offsetTop', 'offsetLeft',
  'scrollWidth', 'scrollHeight', 'scrollTop', 'scrollLeft',
  'clientWidth', 'clientHeight', 'clientTop', 'clientLeft',
  'getComputedStyle()',
  'getBoundingClientRect()',
];
// Reading any of these = forced synchronous reflow
```

### Layout thrashing — interleaving reads and writes

```ts
// ❌ Layout thrashing — each iteration triggers a reflow
// (read → write → read → write → ...)
const boxes = document.querySelectorAll('.box');

boxes.forEach(box => {
  const width = box.offsetWidth;        // READ  → forced reflow
  box.style.width = `${width * 2}px`;  // WRITE → marks layout "dirty"
  // the next read will trigger another reflow...
});
```

```ts
// ✅ Batching: read everything first, then write everything
const boxes = document.querySelectorAll('.box');

// One reflow — read all sizes upfront
const widths = Array.from(boxes).map(box => box.offsetWidth);

// Write — the browser applies changes before the next frame
boxes.forEach((box, i) => {
  box.style.width = `${widths[i] * 2}px`;
});
```

```ts
// ✅ requestAnimationFrame — guarantees we're working at the
// start of a frame, before Paint
function animateBoxes() {
  requestAnimationFrame(() => {
    // All DOM operations in one rAF callback
    // execute atomically before the next frame
    const widths = Array.from(boxes).map(b => b.offsetWidth);
    boxes.forEach((b, i) => {
      b.style.width = `${widths[i] + 1}px`;
    });
    animateBoxes(); // next frame
  });
}
```

```ts
// ✅ FastDOM — library for read/write batching
import fastdom from 'fastdom';

boxes.forEach(box => {
  fastdom.measure(() => {
    const width = box.offsetWidth; // all measures → one reflow
    fastdom.mutate(() => {
      box.style.width = `${width * 2}px`; // all mutations → after
    });
  });
});
```

## Repaint — redrawing pixels

Repaint occurs when visual properties change **without affecting geometry**. It is cheaper than reflow, but it still costs CPU (central processing unit) time.

```ts
// Repaint only (no reflow):
element.style.color = 'red';
element.style.backgroundColor = '#fff';
element.style.visibility = 'hidden'; // vs display:none → reflow!
element.style.boxShadow = '0 2px 4px rgba(0,0,0,.2)';
element.style.borderRadius = '8px';
element.style.outline = '2px solid blue';
```

```css
/* ✅ visibility vs display:
   display: none     → reflow (element removed from flow)
   visibility: hidden → repaint only (space preserved)
   opacity: 0        → composite only (GPU) */

.hidden-no-reflow {
  visibility: hidden; /* better for performance */
}

.hidden-composite {
  opacity: 0;         /* even better — composite only */
  pointer-events: none;
}
```

## Compositing — GPU only, no CPU

Composite-only changes are the gold standard of rendering performance. The browser moves an **already-painted layer**, or changes its transparency, on the GPU (graphics processing unit). The CPU is not touched at all.

Only two CSS properties are guaranteed to be composite-only:

- `transform` — including `translate`, `scale`, `rotate`, `skew` and `matrix`.
- `opacity`.

Modern browsers add `filter` and `backdrop-filter` to that set.

```css
/* ❌ Animation via left/top — triggers reflow every frame */
@keyframes slide-bad {
  from { left: 0; }
  to   { left: 100px; }
}

/* ✅ Animation via transform — composite only */
@keyframes slide-good {
  from { transform: translateX(0); }
  to   { transform: translateX(100px); }
}
```

```css
/* ❌ Showing/hiding via display/visibility — reflow/repaint */
.toast {
  transition: visibility 0.3s;
  visibility: hidden;
}
.toast.visible {
  visibility: visible;
}

/* ✅ Via opacity + pointer-events — composite only */
.toast {
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s;
}
.toast.visible {
  opacity: 1;
  pointer-events: auto;
}
```

```ts
// ❌ JS animation via style.top — reflow every frame
let pos = 0;
function animateBad() {
  pos += 1;
  element.style.top = `${pos}px`; // reflow!
  requestAnimationFrame(animateBad);
}

// ✅ JS animation via transform
let pos = 0;
function animateGood() {
  pos += 1;
  element.style.transform = `translateY(${pos}px)`; // composite
  requestAnimationFrame(animateGood);
}

// ✅ CSS animation/transition — preferred over JS
// (browser can optimize on the compositor thread,
//  independent of the main thread)
```

## will-change — a hint to the browser

`will-change` tells the browser: "this element will be animated soon — create a separate compositor layer for it now."

```css
/* ✅ Correct usage — only for elements that WILL be animated */
.modal {
  will-change: transform, opacity;
}

.animated-card:hover {
  will-change: transform;
}

/* ❌ Wrong — will-change on everything */
* {
  will-change: transform; /* creates a separate layer for EVERY element */
}

.static-div {
  will-change: transform; /* this div is never animated */
}
```

```ts
// ✅ Dynamic will-change: enable before animation,
// disable after (frees GPU memory)
element.addEventListener('mouseenter', () => {
  element.style.willChange = 'transform';
});

element.addEventListener('mouseleave', () => {
  element.style.willChange = 'auto'; // return control to the browser
});

element.addEventListener('transitionend', () => {
  element.style.willChange = 'auto';
});
```

Every compositor layer costs GPU memory, roughly width × height × 4 bytes × 2 buffers. An 800×600 element takes about 3.7MB.

Mobile devices have little GPU memory to spare. With too many layers the browser starts evicting and reloading them, so animations get **worse**, not better. Be surgical with `will-change`.

## GPU Acceleration — how it works

```txt
Main Thread (CPU)
  JavaScript → Style → Layout → Paint
              ↓ paint layers (textures)
Compositor Thread
  Composite — layers, transform, opacity
              ↓ finished frame
GPU
  Output to the screen
```

The compositor thread runs independently of the main thread. If the main thread is blocked by a Long Task, CSS animations on composite-only properties — `transform` and `opacity` — keep running smoothly.

That is why a loading spinner animated with CSS on `transform` or `opacity` keeps spinning even when the page looks frozen under heavy JS.

## CSS Containment — isolating rendering

`contain` lets the browser isolate a subtree of the DOM (Document Object Model — the tree of page elements). Changes inside that subtree do not affect the tree outside it.

```css
/* contain: layout — layout changes don't escape the element */
.card {
  contain: layout;
  /* If card contents change — reflow only affects
     the card itself, not the entire page */
}

/* contain: paint — paint is clipped to the element's bounds */
.sidebar {
  contain: paint;
  /* Browser doesn't paint beyond sidebar boundaries.
     Saves repainting during scroll */
}

/* contain: size — size doesn't depend on children */
.fixed-size-widget {
  contain: size;
  /* Browser doesn't check children to compute size */
}

/* contain: strict — all of the above (except style) */
.isolated-widget {
  contain: strict; /* layout + paint + size */
}
```

```css
/* content-visibility: auto — skip rendering off-screen
   elements entirely */
.article-section {
  content-visibility: auto;
  /* Browser skips Style, Layout, Paint for sections
     outside the viewport until they approach it.
     Can give 5–10× speedup for long pages */

  /* contain-intrinsic-size: reserves space so the
     scrollbar doesn't jump as content appears */
  contain-intrinsic-size: 0 500px;
}
```

```ts
// Measuring the gain from content-visibility
const observer = new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) {
    if (entry.name === 'layout') {
      console.log(`Layout duration: ${entry.duration}ms`);
    }
  }
});
observer.observe({ type: 'layout-shift', buffered: true });
```

## React-specific rendering

### What causes unnecessary re-renders

```ts
// ❌ New object on every parent render —
// React treats props as changed → child re-renders
function Parent() {
  const [count, setCount] = useState(0);

  // New function on every Parent render
  const handleClick = () => setCount(c => c + 1);
  // New object on every Parent render
  const config = { theme: 'dark', size: 'large' };

  return <Child onClick={handleClick} config={config} />;
}
```

```ts
// ✅ useCallback + useMemo — stable references
function Parent() {
  const [count, setCount] = useState(0);

  const handleClick = useCallback(
    () => setCount(c => c + 1),
    [] // no dependencies → stable reference
  );

  const config = useMemo(
    () => ({ theme: 'dark', size: 'large' }),
    [] // also stable
  );

  return <Child onClick={handleClick} config={config} />;
}

// ✅ React.memo — skips re-render if props haven't changed
const Child = React.memo(function Child({ onClick, config }) {
  return <button onClick={onClick}>{config.theme}</button>;
});
```

```ts
// ✅ useDeferredValue — defers a heavy render without
// blocking user input (React 18)
function SearchResults({ query }: { query: string }) {
  // deferredQuery updates when the main thread is free
  const deferredQuery = useDeferredValue(query);

  // Heavy component renders with the "old" query
  // while the user keeps typing
  return <ExpensiveList query={deferredQuery} />;
}

function SearchPage() {
  const [query, setQuery] = useState('');

  return (
    <>
      {/* Input is always responsive — doesn't wait for ExpensiveList */}
      <input value={query} onChange={e => setQuery(e.target.value)} />
      <SearchResults query={query} />
    </>
  );
}
```

```ts
// ✅ useTransition — marks an update as non-urgent
function TabSwitcher() {
  const [tab, setTab] = useState('home');
  const [isPending, startTransition] = useTransition();

  return (
    <>
      <button
        onClick={() => {
          // Tab switching — a non-urgent update
          startTransition(() => setTab('profile'));
        }}
      >
        {isPending ? 'Loading...' : 'Profile'}
      </button>
      <TabContent tab={tab} />
    </>
  );
}
```

### Virtualizing long lists

```ts
// ❌ Rendering 10,000 rows — heavy DOM, slow scroll
function BigList({ items }: { items: Item[] }) {
  return (
    <ul>
      {items.map(item => (
        <li key={item.id}>{item.name}</li>
      ))}
    </ul>
  );
}

// ✅ react-window: renders only visible rows (~10–20)
import { FixedSizeList } from 'react-window';

function VirtualizedList({ items }: { items: Item[] }) {
  return (
    <FixedSizeList
      height={600}       // container height
      itemCount={items.length}
      itemSize={50}      // fixed row height
      width="100%"
    >
      {({ index, style }) => (
        <div style={style}>
          {items[index].name}
        </div>
      )}
    </FixedSizeList>
  );
}
```

## DevTools workflow for rendering

In the Chrome DevTools **Rendering** tab (⋮ → More tools → Rendering), three switches matter:

- **Paint flashing** — green rectangles appear wherever the page repaints. If everything flashes on scroll, something is forcing an excess repaint.
- **Layout Shift Regions** — blue rectangles show where shifts happen, which makes CLS (Cumulative Layout Shift) visible.
- **FPS meter** — FPS is the number of frames per second. The counter shows it live, and during an animation it should stay near 60.

In the **Performance** panel, record an animation:

1. Press record, play the animation, then stop.
2. The `Summary` tab shows how much time went to `Rendering` and `Painting`.
3. In the frames timeline, green is good and yellow or red is a problem.
4. On the main thread track, long green `Paint` blocks mean an expensive repaint.

The **Layers** panel (⋮ → More tools → Layers) visualizes the compositor layers. It shows which elements got their own layer, how much memory each one uses, and a `Reasons` column explaining why the layer was created.

```ts
// Programmatic approach: measuring render time
performance.mark('render-start');
// ... your DOM changes
requestAnimationFrame(() => {
  requestAnimationFrame(() => {
    // Two rAFs — guarantees the update has been applied
    performance.mark('render-end');
    performance.measure('render', 'render-start', 'render-end');
    const [measure] = performance.getEntriesByName('render');
    console.log(`Render took: ${measure.duration.toFixed(2)}ms`);
  });
});
```

## Connection to other topics

- [Core Web Vitals](./01-core-web-vitals.md) — reflow is the mechanism behind CLS, and long paint tasks make INP (Interaction to Next Paint) worse.
- [JavaScript Performance](./04-javascript-performance.md) — Long Tasks on the main thread get in the way of the compositor thread, and layout thrashing creates Long Tasks.
- [Performance Metrics](./02-performance-metrics.md) — rendering and painting count towards TBT (Total Blocking Time) once they pass 50ms.
- **CSS Containment**, the section above — `content-visibility: auto` sharply reduces the initial layout cost of long pages.

## Common interview traps

- **"GPU acceleration — add transform: translateZ(0) everywhere"** — this is a hack to force compositor layer creation that worked in older browsers. Today `will-change: transform` is sufficient. Applying `translateZ(0)` to everything has the same effect as `will-change: all`: excess layers, excess GPU memory consumption.

- **"opacity: 0 and display: none are the same thing"** — no. Setting `display: none` removes the element from document flow, which means reflow. Setting `opacity: 0` keeps the space and only changes transparency, which means composite. The difference is large, and an element at `opacity: 0` still receives events — add `pointer-events: none`.

- **"will-change improves performance"** — not by itself. It signals the browser to create a layer upfront, which removes the delay at the start of an animation. But too many layers overflow GPU memory and performance drops. It's an optimization with potential negative consequences.

- **"CSS animations are always faster than JS animations"** — only if they animate composite-only properties (transform, opacity). A CSS animation on `width` or `margin` triggers reflow just like JS does. The correct framing: "composite-only animations (CSS or JS) are faster than animations that trigger reflow/repaint."

- **"React.memo will fix my rendering performance"** — React.memo compares props by reference. If every parent render creates new objects/functions in props, React.memo is useless. You need the full combination: useCallback + useMemo in the parent + React.memo in the child.

- **"Layout thrashing is when you have lots of DOM operations"** — imprecise. Layout thrashing is specifically about interleaving **reads** of layout properties with **writes** to styles. A thousand writes in a row = one batched reflow. Read → write → read → write in a loop = a thousand reflows.

- **"content-visibility: auto is a magic pill for long pages"** — almost, but it comes with conditions. It only works for block elements whose height is known. You need `contain-intrinsic-size`, or the scrollbar jumps as content appears. Find-in-page (Ctrl+F) works, but the search may not reach hidden content immediately, because the browser renders it on demand.
