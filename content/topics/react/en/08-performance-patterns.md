# Performance Patterns

## The right starting point: measure first

Performance optimization in React has exactly one correct starting point: **measure with the React DevTools Profiler** before touching any code. Unmeasured optimization is guesswork — you will add `useMemo` and `React.memo` everywhere, slow down the app, and still not fix the actual bottleneck.

```txt
WORKFLOW:
  1. Identify a real, user-visible performance problem
     (jank on interaction, slow initial load, laggy input)
  2. Open React DevTools → Profiler → record while reproducing the problem
  3. Find the slowest components (longest bars in the flame chart)
  4. Understand WHY they are slow (unnecessary re-renders? expensive computation?)
  5. Apply the targeted fix
  6. Measure again to confirm improvement
```

Without step 2–4, every fix is a guess.

---

## React.memo — correctly explained

`React.memo` wraps a component and skips re-rendering it when its props haven't changed (compared with shallow equality using `Object.is`).

```tsx
const ExpensiveList = React.memo(function ExpensiveList({
  items,
  onSelect,
}: {
  items: Item[];
  onSelect: (id: string) => void;
}) {
  // Only re-renders when items or onSelect change (by reference)
  return (
    <ul>
      {items.map(item => (
        <li key={item.id} onClick={() => onSelect(item.id)}>{item.name}</li>
      ))}
    </ul>
  );
});
```

### The three conditions that must ALL be true for React.memo to help

```txt
1. The component renders often (its parent re-renders frequently)
2. The re-render is expensive (many children, slow computation in render)
3. The props are referentially stable between renders
   (primitives don't change, objects/arrays/functions are memoized)
```

If condition 3 is not met, `React.memo` provides zero benefit — the props comparison always returns false (changed) because new object/function references are created on every parent render.

### The most common React.memo mistake

```tsx
function Parent() {
  const [count, setCount] = useState(0);

  return (
    <>
      <button onClick={() => setCount(c => c + 1)}>+</button>
      {/* ❌ New object reference on every render — React.memo does nothing: */}
      <MemoChild config={{ theme: 'dark' }} onSelect={() => doSomething()} />
    </>
  );
}

// Fix: stabilize the props
function Parent() {
  const [count, setCount] = useState(0);

  const config = useMemo(() => ({ theme: 'dark' }), []);   // stable reference
  const handleSelect = useCallback(() => doSomething(), []); // stable reference

  return (
    <>
      <button onClick={() => setCount(c => c + 1)}>+</button>
      <MemoChild config={config} onSelect={handleSelect} />
    </>
  );
}
```

`React.memo`, `useMemo`, and `useCallback` form a triad — `React.memo` on the child only works when the parent stabilizes its outputs with `useMemo`/`useCallback`.

### Custom comparison function

```tsx
const MemoizedChart = React.memo(
  function Chart({ data, title }: { data: number[]; title: string }) {
    return <canvas>...</canvas>;
  },
  (prevProps, nextProps) => {
    // Return true = props are equal = skip re-render
    // Return false = props changed = re-render
    return (
      prevProps.title === nextProps.title &&
      prevProps.data.length === nextProps.data.length &&
      prevProps.data.every((v, i) => v === nextProps.data[i])
    );
  }
);
```

Use a custom comparator when the default shallow equality is too strict (a new array reference with identical contents would always trigger a re-render). But be careful: a wrong comparator that returns `true` when props have actually changed will cause stale UI bugs.

### When React.memo actively hurts

```tsx
// ❌ React.memo on a component that always receives new props:
const Row = React.memo(({ item, index }: { item: Item; index: number }) => (
  <tr>...</tr>
));

function Table({ items }: { items: Item[] }) {
  return (
    <tbody>
      {items.map((item, index) => (
        // If items array is rebuilt on every render (common with filters/sorts),
        // item references change → React.memo always re-renders anyway
        // + adds the props comparison overhead on top.
        <Row key={item.id} item={item} index={index} />
      ))}
    </tbody>
  );
}
```

In this case `React.memo` runs the comparison on every render and always decides to re-render anyway — you pay the comparison cost for zero gain.

---

## Avoiding unnecessary re-renders — the systematic approach

### 1. State colocation

Move state down to where it is actually used. A common source of unnecessary re-renders is state that lives too high in the tree:

```tsx
// ❌ Parent owns state that only Modal needs → every state change re-renders Parent:
function Page() {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <div>
      <HeavyDataGrid />    {/* re-renders every time modal opens/closes */}
      <button onClick={() => setModalOpen(true)}>Open</button>
      {modalOpen && <Modal onClose={() => setModalOpen(false)} />}
    </div>
  );
}

// ✅ Colocate state in a dedicated component:
function ModalTrigger() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>Open</button>
      {open && <Modal onClose={() => setOpen(false)} />}
    </>
  );
}

function Page() {
  return (
    <div>
      <HeavyDataGrid />    {/* never re-renders due to modal state */}
      <ModalTrigger />
    </div>
  );
}
```

### 2. Lift content up (children pattern)

When a component must own fast-changing state, pass slow content as `children` instead of importing it:

```tsx
// ❌ MouseTracker imports HeavyChart → HeavyChart re-renders on every mouse move:
function MouseTracker() {
  const [pos, setPos] = useState({ x: 0, y: 0 });
  return (
    <div onMouseMove={e => setPos({ x: e.clientX, y: e.clientY })}>
      <p>Mouse: {pos.x}, {pos.y}</p>
      <HeavyChart />  {/* re-renders constantly */}
    </div>
  );
}

// ✅ Pass HeavyChart as children — its parent (Page) doesn't re-render on mouse move:
function MouseTracker({ children }: { children: React.ReactNode }) {
  const [pos, setPos] = useState({ x: 0, y: 0 });
  return (
    <div onMouseMove={e => setPos({ x: e.clientX, y: e.clientY })}>
      <p>Mouse: {pos.x}, {pos.y}</p>
      {children}  {/* already-rendered subtree — not re-rendered by MouseTracker */}
    </div>
  );
}

function Page() {
  return (
    <MouseTracker>
      <HeavyChart />  {/* Page's render phase owns HeavyChart — only re-renders when Page does */}
    </MouseTracker>
  );
}
```

### 3. Context splitting (revisited in performance context)

See Context article for full details. Summary: split a monolithic context into multiple contexts grouped by update frequency. Components consuming `NotificationsContext` don't re-render when `CartContext` changes.

### 4. Deriving state instead of storing it

```tsx
// ❌ Derived state in useState → needs to be kept in sync:
const [items, setItems] = useState<Item[]>([]);
const [filteredItems, setFilteredItems] = useState<Item[]>([]);

// setItems + setFilteredItems must always be called together → bug-prone

// ✅ Derive on every render (or useMemo if expensive):
const [items, setItems] = useState<Item[]>([]);
const [filter, setFilter] = useState('');

const filteredItems = useMemo(
  () => items.filter(i => i.name.includes(filter)),
  [items, filter]
);
```

---

## Virtualization — rendering only what's visible

Rendering 10,000 list rows creates 10,000 DOM nodes — even if only 20 are visible. Virtualization renders only the visible rows (plus a small overscan buffer), dramatically reducing DOM size and render time.

```tsx
// @tanstack/react-virtual — the modern low-level solution:
import { useVirtualizer } from '@tanstack/react-virtual';

function VirtualList({ items }: { items: Item[] }) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 48,  // estimated row height in px
    overscan: 5,             // render 5 extra rows above and below viewport
  });

  return (
    <div ref={parentRef} style={{ height: '600px', overflow: 'auto' }}>
      {/* Total scrollable height — makes the scrollbar accurate */}
      <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
        {virtualizer.getVirtualItems().map(virtualRow => (
          <div
            key={virtualRow.index}
            style={{
              position: 'absolute',
              top: virtualRow.start,    // exact pixel position
              width: '100%',
              height: virtualRow.size,
            }}
          >
            {items[virtualRow.index].name}
          </div>
        ))}
      </div>
    </div>
  );
}
```

For simpler cases: `react-window` (lightweight) or `react-virtualized` (feature-rich but heavier). For tables: `@tanstack/react-table` with `@tanstack/react-virtual`.

**When virtualization is not needed:**
- Lists under ~100 items with simple row content
- Lists that are rarely re-rendered
- When the bottleneck is re-render frequency, not DOM node count (virtualization doesn't help re-render performance)

---

## Code splitting with React.lazy and Suspense

Every component you import is included in the main JavaScript bundle — even if it's only needed on one page, or behind a click. Code splitting splits the bundle into chunks that are loaded on demand.

```tsx
// Without code splitting — HeavyEditor is in the main bundle:
import { HeavyEditor } from './HeavyEditor'; // 300 kB

// With code splitting — HeavyEditor is loaded lazily when needed:
const HeavyEditor = React.lazy(() => import('./HeavyEditor'));

function Page() {
  const [editMode, setEditMode] = useState(false);

  return (
    <div>
      <button onClick={() => setEditMode(true)}>Edit</button>
      {editMode && (
        <Suspense fallback={<EditorSkeleton />}>
          <HeavyEditor />  {/* JS chunk loads when editMode becomes true */}
        </Suspense>
      )}
    </div>
  );
}
```

### Route-based code splitting (Next.js)

In Next.js App Router, every `page.tsx` and `layout.tsx` is automatically a separate chunk. Dynamic imports further split large components within a page:

```tsx
// next/dynamic — Next.js's wrapper around React.lazy + Suspense:
import dynamic from 'next/dynamic';

const Map = dynamic(() => import('./Map'), {
  loading: () => <MapSkeleton />,
  ssr: false,           // don't server-render this component (for browser-only libs)
});

// With a named export:
const Chart = dynamic(
  () => import('./Charts').then(mod => ({ default: mod.RevenueChart })),
  { loading: () => <Skeleton /> }
);
```

### Preloading chunks

If you know a user is about to navigate somewhere, you can preload the chunk before they click:

```tsx
const HeavyEditor = React.lazy(() => import('./HeavyEditor'));

function preloadEditor() {
  // Triggers the dynamic import (starts loading the chunk)
  // without rendering the component
  void import('./HeavyEditor');
}

function Page() {
  return (
    <button
      onMouseEnter={preloadEditor}  // starts loading on hover, before click
      onClick={() => setEditMode(true)}
    >
      Edit
    </button>
  );
}
```

---

## Profiling with React DevTools Profiler

The Profiler is the only reliable way to find actual performance problems.

### Reading the flame chart

```txt
FLAME CHART (one bar per component render):
  ┌──────────────────── App (3.2ms) ─────────────────────────┐
  │ ┌─── Header (0.1ms) ───┐  ┌──────── Main (3.0ms) ──────┐ │
  │ └──────────────────────┘  │ ┌── Sidebar ──┐ ┌─ Content ─┐ │ │
  │                            │ │  (0.2ms)    │ │ (2.7ms)   │ │ │
  │                            │ └────────────┘ └───────────┘ │ │
  │                            └──────────────────────────────┘ │
  └───────────────────────────────────────────────────────────┘

  Bar width = how long this render took (render phase only, not commit)
  Bar color:
    grey  = did not render this commit (skipped by memo)
    green = rendered, fast (< 1ms)
    yellow = rendered, slow
    red    = rendered, very slow (> 16ms = misses 60fps frame)
```

**Workflow for finding unnecessary re-renders:**

1. Record a profiler session while reproducing the slow interaction
2. Look for grey bars (memoized components that did re-render in a previous commit but were skipped this time — these are working correctly) and yellow/red bars
3. Click a yellow/red bar → "Why did this render?" panel shows the reason
4. "Why did this render?" tells you which prop or state changed

### The "Why did this render?" panel

```txt
Why did <ProductList> render?
  Props changed:
    onSelect: [function] → [function]
```

This tells you `onSelect` is a new function reference on every render — the exact problem `useCallback` solves.

### Commit vs render timing

The Profiler measures the **render phase** (calling component functions). It does NOT include:
- Commit phase (applying DOM mutations)
- `useEffect` execution time
- Browser paint time

A component can be fast in the Profiler but still cause slow paint (if it generates many DOM mutations in the commit phase) or slow perceived performance (if its `useEffect` does heavy work). Use Chrome DevTools Performance tab to measure total frame time including commit and paint.

### The Profiler API for production measurements

```tsx
// <Profiler> component — works in production, unlike DevTools:
import { Profiler } from 'react';

function onRenderCallback(
  id: string,              // component name passed to id prop
  phase: 'mount' | 'update' | 'nested-update',
  actualDuration: number,  // time spent in render phase (ms)
  baseDuration: number,    // estimated time without memo optimizations
  startTime: number,
  commitTime: number,
) {
  analytics.track('react_render', { id, phase, actualDuration });
}

function Page() {
  return (
    <Profiler id="ProductList" onRender={onRenderCallback}>
      <ProductList />
    </Profiler>
  );
}
```

`baseDuration` is particularly useful: it estimates how long the render would take without any `React.memo` or `useMemo` optimizations. If `baseDuration` is large but `actualDuration` is small, your memoization is working. If both are large, the component is genuinely expensive to render regardless of memoization.

---

## Expensive render body — the computation problem

If a component's render function itself is slow (not re-render frequency), `useMemo` is the right tool:

```tsx
function ReportPage({ data }: { data: RawDataPoint[] }) {
  // ❌ Runs on every render, even if data hasn't changed:
  const processed = data
    .filter(d => d.value > 0)
    .map(d => ({ ...d, normalized: d.value / data.length }))
    .sort((a, b) => b.normalized - a.normalized);

  // ✅ Only recomputes when data changes:
  const processed = useMemo(
    () =>
      data
        .filter(d => d.value > 0)
        .map(d => ({ ...d, normalized: d.value / data.length }))
        .sort((a, b) => b.normalized - a.normalized),
    [data]
  );

  return <Chart data={processed} />;
}
```

Before adding `useMemo`, verify with `console.time` that the computation is actually slow. For arrays under ~1000 items with simple transformations, it usually isn't.

---

## Common interview traps

**"Does React.memo prevent all re-renders?"**
No. `React.memo` only prevents re-renders caused by **prop changes**. It does not prevent re-renders caused by: the component's own `useState`/`useReducer` changes, Context changes (the component consumes a context that updated), or `forceUpdate`. Memo only guards the prop-to-render path.

**"What is the difference between React.memo and useMemo?"**
`React.memo` wraps a **component** and skips re-rendering it when props are the same. `useMemo` wraps a **computation inside a component** and caches its result between renders. They solve different problems: `React.memo` reduces how often a component function is called; `useMemo` reduces how expensive one render is.

**"Is virtualization always faster than rendering all items?"**
Not always. Virtualization adds overhead: absolute positioning, scroll event listeners, dynamic height calculations. For lists under ~100 items, regular rendering with a stable key prop is usually faster. Virtualization becomes beneficial when: the list is very long (500+ items), each item is non-trivial to render, and the user scrolls frequently.

**"Can you profile performance in production?"**
The React DevTools Profiler only works in development (production builds strip profiling code for performance). To profile in production: use the `<Profiler>` component API with custom `onRender` callbacks that send data to your analytics service, or use the `react-dom/profiling` build (an opt-in production build that includes profiling support but has slightly higher runtime cost).

**"What causes the most re-renders in a typical React app?"**
In order of frequency in real codebases: (1) Context value objects created inline in JSX (`value={{ user, setUser }}`) — causes all consumers to re-render on every Provider render; (2) inline callbacks passed to memoized children; (3) parent components re-rendering due to unrelated state changes; (4) missing `key` props causing React to remount instead of update. The Profiler's "Why did this render?" panel identifies all of these.
