# Hooks Fundamentals

## Why hooks exist — the problem with class components

Before hooks (React < 16.8), stateful logic lived in class components. The core problem was not syntax — it was that **stateful logic was inseparable from the component that used it**. Two components needing the same subscription logic would either duplicate it or use Higher-Order Components / render props, which produced deeply nested component trees for purely organizational reasons ("wrapper hell"). Hooks let you extract stateful logic into a function and reuse it across components without changing the component hierarchy.

The secondary problems hooks solve:
- `this` binding in class methods (a constant source of bugs)
- Logic split across lifecycle methods: related code spread across `componentDidMount`, `componentDidUpdate`, `componentWillUnmount`
- Classes are harder to minify and make hot reload less reliable

---

## The linked list — why the Rules of Hooks are not arbitrary

Hooks are stored as a **singly linked list** attached to the Fiber node of the component. There is no dictionary, no names, no magic introspection. React tracks hooks by **call order** — the first hook call is node 1, the second is node 2, and so on.

```txt
FIBER NODE for <MyComponent>
│
└── memoizedState (first hook)
      │  { state: 0, queue: ..., next: ─────────────────────────┐ }
      │                                                           │
      └────────────────────── next ──────────────────────────────▼
                                      { state: 'Alice', queue: ..., next: ──┐ }
                                                                              │
                                                                              ▼
                                                          { effect: ..., next: null }
```

On the first render, React builds this list. On every subsequent render, React **walks the same list in the same order** and associates each `useState` / `useEffect` call with its existing node.

This is why:

```ts
// RULE: never call hooks conditionally

// ✅ Correct — same number of hooks on every render:
function Component({ show }: { show: boolean }) {
  const [a, setA] = useState(0);  // node 1
  const [b, setB] = useState(''); // node 2
  useEffect(() => {}, []);        // node 3
  return <div>{a}</div>;
}

// ❌ Wrong — conditional hook, different number of nodes per render:
function Component({ show }: { show: boolean }) {
  if (show) {
    const [a, setA] = useState(0); // node 1 on some renders, missing on others
  }
  const [b, setB] = useState('');  // node 1 or node 2 depending on `show`
  // React reads node 2's previous value into [b, setB] on the render where
  // show=false — but that node 2 actually held the `a` value from the previous render.
  // State is now corrupted.
}
```

The `eslint-plugin-react-hooks` linter rule enforces this statically. The error message "Rendered more hooks than during the previous render" means the list lengths don't match.

**Why not a dictionary?** React was designed this way deliberately — no dynamic hook names, no string keys, no reflection. The linked list keeps the implementation minimal and ensures hook identity is stable across re-renders as long as call order is stable.

---

## useState — mechanics under the hood

```tsx
const [count, setCount] = useState(0);
```

On the **first render** (mount), React:
1. Creates a new hook node in the linked list
2. Runs the initializer (`0` — or the function if you pass `() => expensiveCompute()`)
3. Stores the initial state in `node.memoizedState`
4. Returns `[node.memoizedState, node.queue.dispatch]`

On **subsequent renders** (update), React:
1. Finds the existing node by walking the list to the same position
2. Processes all queued updates (from `setCount` calls) in order
3. Stores the new state in `node.memoizedState`
4. Returns the updated `[state, dispatch]`

### Lazy initializer — when to use it

```tsx
// ❌ Runs expensive computation on every render:
const [state, setState] = useState(JSON.parse(localStorage.getItem('data') ?? '{}'));

// ✅ Runs only on mount (function form):
const [state, setState] = useState(() => JSON.parse(localStorage.getItem('data') ?? '{}'));
```

Pass a function when the initial value is expensive to compute. React calls the function only once — during mount — and ignores it on re-renders.

### The state setter is stable

The `setCount` function returned by `useState` is **referentially stable** — it is the same function reference across all renders of the component. This is why it is safe to omit from `useEffect` / `useCallback` dependency arrays:

```tsx
useEffect(() => {
  const timer = setInterval(() => {
    setCount(c => c + 1); // setCount is stable — no need in deps array
  }, 1000);
  return () => clearInterval(timer);
}, []); // ✅ empty deps is correct here
```

---

## useEffect — the complete mental model

`useEffect` is not "a lifecycle method with a different name." The correct mental model:

```txt
useEffect(setup, deps)

→ After every render where deps have changed (compared with Object.is):
    1. Run the cleanup of the previous effect (if any)
    2. Run setup

→ On unmount:
    3. Run the cleanup of the last effect
```

The setup function is always called **after** the browser has painted the screen (asynchronously, after the commit phase). This is intentional — it doesn't block the paint.

### The three dependency array forms

```tsx
// Form 1: no array — runs after EVERY render
useEffect(() => {
  document.title = `Count: ${count}`;
});

// Form 2: empty array — runs ONCE after mount, cleanup on unmount
useEffect(() => {
  const sub = store.subscribe(handler);
  return () => sub.unsubscribe();
}, []);

// Form 3: with deps — runs after mount AND whenever any dep changes
useEffect(() => {
  const sub = store.subscribe(userId, handler);
  return () => sub.unsubscribe();
}, [userId]); // re-subscribes when userId changes
```

**Common trap:** "I want to run this only once" → empty array. But if the effect's setup reads props or state, those are stale closures after the first render. Correct: include everything the effect reads from the component scope in the dependency array. The `exhaustive-deps` ESLint rule enforces this.

### Cleanup functions — what they are and when they run

The function returned from `useEffect` is called the *cleanup function*. React calls it in two situations:
1. Before re-running the effect (when deps changed)
2. When the component unmounts

```tsx
useEffect(() => {
  // SETUP: subscribe
  const controller = new AbortController();
  fetch('/api/data', { signal: controller.signal })
    .then(res => res.json())
    .then(setData)
    .catch(err => { if (err.name !== 'AbortError') setError(err); });

  // CLEANUP: cancel the fetch if the component unmounts or deps change
  // (prevents setting state on unmounted component)
  return () => controller.abort();
}, [userId]);
```

Without the cleanup: if `userId` changes before the fetch completes, two fetches race; the slower one might resolve last and overwrite the result from the faster newer one (a **race condition**). The cleanup cancels the previous fetch before starting a new one.

### Why effects run after paint (and why that matters)

```txt
Render → Commit → Browser paint → useEffect

If useEffect blocked paint (like useLayoutEffect does), users would
see a blank screen until the effect finishes — bad for anything async.
useEffect is intentionally deferred.
```

The consequence: if your effect reads a layout measurement (element dimensions, scroll position), by the time it runs, the browser has already painted with potentially stale dimensions. Use `useLayoutEffect` for that case.

---

## useLayoutEffect — what it solves

`useLayoutEffect` has the same signature as `useEffect` but fires **synchronously after DOM mutations and before the browser paints**:

```txt
Render → Commit (DOM mutations) → useLayoutEffect → Browser paint → useEffect
```

Use case: reading DOM layout and synchronously adjusting it before the user sees the intermediate state.

```tsx
function Tooltip({ anchor }: { anchor: HTMLElement }) {
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ top: 0, left: 0 });

  useLayoutEffect(() => {
    // This runs BEFORE the browser shows the tooltip at its initial position.
    // We measure and reposition in the same paint cycle.
    const rect = tooltipRef.current!.getBoundingClientRect();
    const anchorRect = anchor.getBoundingClientRect();
    setPosition({ top: anchorRect.bottom, left: anchorRect.left });
  }, [anchor]);

  return <div ref={tooltipRef} style={position}>...</div>;
}
```

With `useEffect`: the tooltip flashes at the wrong position for one frame (the browser painted before the effect ran). With `useLayoutEffect`: the DOM is updated before paint — no visible flicker.

**Server rendering caveat:** `useLayoutEffect` is skipped on the server (where there is no DOM) and React warns about it. If a component with `useLayoutEffect` is server-rendered, either use `useEffect` instead, or conditionally render the component only on the client.

---

## Dependency array pitfalls — the complete list

### 1. Stale closures

```tsx
function Timer() {
  const [count, setCount] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      console.log(count); // captures count from the render when this effect ran
      // count is always 0 if deps = []
    }, 1000);
    return () => clearInterval(id);
  }, []); // ← missing count in deps
}
```

Fix: either add `count` to deps (effect re-creates the timer on each count change) or use a functional update to avoid reading count altogether: `setCount(c => c + 1)`.

### 2. Object and array deps (reference equality)

```tsx
function Component({ config }: { config: { timeout: number } }) {
  useEffect(() => {
    const timer = setTimeout(fetch, config.timeout);
    return () => clearTimeout(timer);
  }, [config]); // config is a new object on every parent render → infinite loop
}
```

Fix: depend on the primitive values instead of the object:

```tsx
useEffect(() => { ... }, [config.timeout]);
```

Or memoize the object in the parent with `useMemo` (see Hooks Advanced article).

### 3. Functions as deps

```tsx
function Component({ onData }: { onData: (data: Data) => void }) {
  useEffect(() => {
    fetch('/api').then(onData); // onData may change on every parent render
  }, [onData]); // → re-fetches every time parent re-renders
}
```

Fix: wrap `onData` in `useCallback` in the parent, or use `useEffectEvent` (React 19+) to capture the latest version without making it a dep.

### 4. Exhaustive-deps false negatives

The `exhaustive-deps` linter rule catches missing deps but cannot always detect issues with mutable refs. Mutable refs (`ref.current`) are intentionally excluded from dep arrays — the ref object is stable but its content can change silently. This is correct behavior, but it means reading `ref.current` inside an effect gives you the latest value, not a captured snapshot, which can be surprising.

---

## The "each render is a snapshot" mental model

Every time a component renders, React calls your function. That function call captures the current values of props and state in a closure. `useEffect`'s setup runs with the values from the render that scheduled it — not the latest values at the time the effect fires.

```tsx
function Counter() {
  const [count, setCount] = useState(0);

  useEffect(() => {
    setTimeout(() => {
      // This `count` is captured from the render that scheduled this effect.
      // If count was 0 when this effect ran, count will be 0 in this callback
      // even if setCount(5) was called before the timeout fires.
      console.log(count);
    }, 3000);
  }, [count]);

  return <button onClick={() => setCount(c => c + 1)}>{count}</button>;
}
```

This is not a bug — it is the defined behavior. Each render has its own version of every value. If you need to always read the latest value (not the snapshot), use a `useRef` (covered in the advanced hooks article).

---

## Common interview traps

**"Can you call hooks inside a loop?"**
No — the number and order of hook calls must be the same on every render. Calling hooks inside a loop would produce a different number of hooks depending on the array length. If you need per-item state, extract each item into its own component.

**"What's the difference between `useEffect(() => {}, [])` and `componentDidMount`?"**
In StrictMode (development), `useEffect` with `[]` runs twice: mount → cleanup → mount. `componentDidMount` runs once. More importantly, the mental model differs: `componentDidMount` is "do this when the component mounts." `useEffect` is "synchronize with these values" — the empty array says "there are no values to synchronize with, so run only once."

**"Why does my `useEffect` run infinitely?"**
Almost always: an object or array created inline in the component is listed as a dependency. Objects are compared by reference, so a new `{}` or `[]` on each render is always "changed." Fix: move the object outside the component, memoize it with `useMemo`, or depend on the primitive properties instead.

**"Is it safe to do `async` setup functions in useEffect?"**
`useEffect`'s setup cannot return a Promise — it must return either nothing or a cleanup function. An `async` function always returns a Promise, so `useEffect(async () => { ... })` will cause a warning and the return value (the cleanup function, if any) is lost. Correct pattern:

```tsx
useEffect(() => {
  let cancelled = false;
  async function load() {
    const data = await fetch('/api').then(r => r.json());
    if (!cancelled) setData(data);
  }
  load();
  return () => { cancelled = true; };
}, []);
```

**"Does `useEffect` run on the server?"**
No. Neither `useEffect` nor `useLayoutEffect` runs during server-side rendering. This means any code that should only run in the browser (DOM access, localStorage, browser APIs) must be in a `useEffect`. Accessing these APIs directly in the component body causes hydration mismatches.
