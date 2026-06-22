# JSX and the Rendering Pipeline

## JSX is syntactic sugar — but the sugar matters

JSX looks like HTML inside JavaScript. That description is accurate but incomplete, because it hides the mechanics that explain almost every performance decision in React.

```tsx
// What you write
const element = <Button variant="primary" onClick={handleClick}>Save</Button>;

// What Babel/SWC compiles it to
const element = React.createElement(
  Button,
  { variant: 'primary', onClick: handleClick },
  'Save'
);

// React 17+ (new JSX transform) — no React import needed:
import { jsx as _jsx } from 'react/jsx-runtime';
const element = _jsx(Button, { variant: 'primary', onClick: handleClick, children: 'Save' });
```

`React.createElement` (or the new JSX runtime's `_jsx`) does not create a DOM node. It creates a **plain JavaScript object** called a React element:

```ts
{
  $$typeof: Symbol(react.element),  // marks it as a React element (XSS protection)
  type: Button,                      // string for DOM tags, function/class for components
  key: null,
  ref: null,
  props: { variant: 'primary', onClick: handleClick, children: 'Save' },
}
```

This object is **immutable** and **cheap to create** — just a `{}` allocation. The actual DOM work happens much later, in a separate phase.

### Why `$$typeof` is a Symbol

`JSON.parse` cannot produce a Symbol. If user-supplied JSON is accidentally rendered (`{JSON.parse(userInput)}`), it will never have `$$typeof: Symbol(react.element)` — React rejects it. This is React's protection against a class of XSS vulnerabilities via dangerously-rendered API responses.

---

## The two phases of every render: Render and Commit

React's rendering process is split into two fundamentally different phases:

```txt
RENDER PHASE (pure, interruptible)
─────────────────────────────────
  1. React calls your component function(s) with current props/state
  2. Component returns a tree of React elements (plain objects)
  3. React runs the reconciler (Fiber diff algorithm)
  4. React computes a list of DOM changes needed
  → NO DOM mutations happen here

COMMIT PHASE (impure, synchronous, non-interruptible)
──────────────────────────────────────────────────────
  1. React applies all DOM mutations from step 4 above
  2. Runs layout effects: useLayoutEffect cleanups → useLayoutEffect callbacks
  3. Browser paints the screen
  4. Runs passive effects: useEffect cleanups → useEffect callbacks
```

This two-phase split is not an implementation detail — it has observable consequences:

- You can call `setState` during render (carefully) because the render phase has not touched the DOM yet.
- `useLayoutEffect` fires synchronously *after* DOM mutations but *before* the browser paints — it blocks painting and is suitable for measuring layout.
- `useEffect` fires *after* the browser has already painted — it is the right place for subscriptions and non-visual side effects.
- In `StrictMode` / concurrent mode, the render phase can be interrupted, discarded, and re-run. If your render has side effects (mutations, subscriptions), they run twice. The commit phase is never interrupted.

---

## What triggers a re-render — the complete list

```txt
SOURCE                        WHAT HAPPENS
─────────────────────────────────────────────────────
setState / useState setter     schedules a re-render of that component and its subtree
useReducer dispatch           same as above
Context value changes          all consumers of that Context re-render
Parent re-renders              children re-render (unless memo'd)
forceUpdate (class)           bypasses shouldComponentUpdate, re-renders
```

The critical insight: **a re-render is not a DOM update**. A re-render means "React calls your component function again." Whether the DOM is subsequently updated depends entirely on whether the reconciler finds any differences.

```tsx
function Counter() {
  const [count, setCount] = useState(0);

  // This re-render is triggered by setCount.
  // If count didn't actually change, React still calls Counter() again,
  // but after diffing the output, makes no DOM changes.
  return <div>{count}</div>;
}
```

### The "same value" optimization (Object.is bail-out)

```tsx
const [count, setCount] = useState(0);
setCount(0); // count is already 0
```

React uses `Object.is` to compare the new state value with the current one. If they are identical, React **may** bail out and not re-render — but only after the first bail-out (to ensure effects have run at least once). This is why setting state to the same object reference doesn't trigger a re-render, but setting to a new object with the same shape does:

```tsx
// No re-render (same reference):
setUser(user); 

// Re-render (new reference, even if structurally identical):
setUser({ ...user }); 
```

---

## Why state updates are batched — and what changed in React 18

Batching means React collects multiple `setState` calls from a single event and applies them in one re-render pass rather than re-rendering after each call.

**Pre-React 18** — batching only happened inside React event handlers:

```tsx
function handleClick() {
  setA(1); // no re-render yet
  setB(2); // no re-render yet
}        // → one re-render with both updates applied

// NOT batched (pre-18):
setTimeout(() => {
  setA(1); // re-render here
  setB(2); // re-render again
}, 0);
```

**React 18 — automatic batching everywhere:**

```tsx
// All of these are now batched in React 18:
setTimeout(() => { setA(1); setB(2); });
fetch('/api').then(() => { setA(1); setB(2); });
element.addEventListener('click', () => { setA(1); setB(2); });
```

If you need to force a synchronous, unbatched update (rare), `flushSync` from `react-dom` exits batching:

```tsx
import { flushSync } from 'react-dom';

flushSync(() => setA(1)); // DOM update here
flushSync(() => setB(2)); // DOM update here again
```

**Why batching matters:** two `setState` calls → one function call (your component) → one reconciliation pass → one DOM mutation. Without batching: two function calls, two reconciliation passes, two DOM mutations. For components with many state updates in a single handler, this can be a 2–10x performance difference.

---

## Functional updates — the correct pattern when new state depends on old state

```tsx
// Wrong — captures stale closure value of count:
setCount(count + 1);
setCount(count + 1); // still uses the same stale `count`

// Correct — uses the guaranteed-latest state value:
setCount(c => c + 1);
setCount(c => c + 1); // each updater receives the result of the previous one
```

Functional updates are required whenever you call `setState` multiple times in a batch and each call depends on the result of the previous one. They are also the safe pattern inside `useEffect` with an empty dependency array when the effect needs to increment a counter.

---

## StrictMode double-rendering explained

`<React.StrictMode>` in development mode calls your component function **twice** per render, calls state initializers twice, calls `useReducer` reducers twice, and calls `useEffect` setup functions twice (by intentionally running cleanup and re-running setup).

```txt
WHAT REACT DOES IN STRICT MODE (dev only):
  1. Call component function → record output
  2. Call component function AGAIN → verify output is the same
  3. If different: throw a warning

WHY: verifies your render is a pure function of props + state.
     A side-effectful render (mutating a global, writing to DOM)
     will behave inconsistently in concurrent mode where React
     can discard renders mid-flight and restart them.
```

The double-invocation does NOT happen in production. It is exclusively a development-time purity checker.

```tsx
let renderCount = 0;

function MyComponent() {
  renderCount++; // WRONG: mutates outside state
  return <div>Rendered {renderCount} times</div>;
}

// In StrictMode dev: renders "Rendered 2 times", then "Rendered 4 times", etc.
// In production:     renders "Rendered 1 time",  then "Rendered 2 times", etc.
// The difference exposes the bug — renderCount is not idempotent.
```

`useEffect` double-invocation (mount → cleanup → mount) was added in React 18 to verify that effects properly clean up after themselves. The classic scenario it catches:

```tsx
useEffect(() => {
  const sub = eventBus.subscribe(handler);
  // If you forget the cleanup:
  // return () => eventBus.unsubscribe(sub);
}, []);
// In StrictMode: subscribe is called twice, but unsubscribe never.
// You'll see double event handlers in dev — the bug is revealed.
```

---

## The render output is not HTML — it's a description

Confusing JSX with HTML is the root cause of several common mistakes:

```tsx
// These are NOT HTML attributes. React maps them to DOM properties:
<div className="box"        // className → element.className (not class)
     htmlFor="input-id"    // htmlFor → label.htmlFor (not for)
     onClick={handler}     // onClick → addEventListener('click', ...)
     style={{ color: 'red', fontSize: 16 }} // style is an OBJECT, not a string
/>

// React controls the event system (synthetic events):
// Events bubble through the React tree, not the DOM tree.
// This matters for Portals (see Patterns article).
```

Fragments (`<>...</>` or `<React.Fragment>`) exist because JSX `React.createElement` calls take one root argument — they cannot return multiple siblings as separate roots. A Fragment is a React element with `type: Symbol(react.fragment)` that the reconciler knows to unwrap without creating a DOM node.

---

## Common interview traps

**"Does calling setState immediately re-render the component?"**
No. `setState` schedules a re-render. React batches updates and processes them asynchronously (in the same tick but after the current synchronous code finishes). The component function is called again in the next render pass, not inline.

**"Is JSX slower than using `React.createElement` directly?"**
No. JSX is compiled to `React.createElement` (or the new JSX transform) at build time — there is zero runtime overhead. The compiled output is identical.

**"What does React render to in a React Native app?"**
Not the DOM. The "renderer" is swappable: `react-dom` renders to the browser DOM; `react-native` renders to native mobile UI elements; `react-three-fiber` renders to a Three.js scene graph. The React core (reconciler, Fiber) is shared.

**"Can the render phase have side effects?"**
It shouldn't. The render phase must be a pure function of props and state. In Concurrent Mode, React may invoke your render function multiple times for a single commit, or interrupt and discard a render in progress. Side effects in render (subscriptions, mutations, timers) are not safe because they may execute zero, one, or multiple times for a single "logical" render.

**"Why does React use a virtual DOM?"**
The framing is slightly off. React doesn't use a "virtual DOM" to make DOM manipulation faster — real DOM manipulation is only called once per commit, which is as fast as it can be. The reconciler's purpose is to compute the *minimal* set of DOM changes needed between renders so that unaffected DOM nodes are not touched at all. The Fiber tree is an implementation detail of the reconciler, not a "copy of the DOM."
