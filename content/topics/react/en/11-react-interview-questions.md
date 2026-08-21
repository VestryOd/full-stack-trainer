# React — Interview Questions (Senior)

## Group 1: JSX, Rendering & Elements

**What does JSX actually compile to, and why does React need to be in scope in older versions?**

JSX compiles to plain function calls. JSX is JavaScript XML, the HTML-like syntax React components are written in, and a build step turns every tag into a call.

```tsx
// You write:
<Button color="blue">Click</Button>

// Classic transform ("jsx": "react" in tsconfig):
React.createElement(Button, { color: 'blue' }, 'Click');

// New JSX transform, React 17+ ("jsx": "react-jsx"):
import { jsx as _jsx } from 'react/jsx-runtime';  // injected for you
_jsx(Button, { color: 'blue', children: 'Click' });
```

With the classic transform, `React.createElement` was called directly. So `React` had to be in scope, even if you never wrote `React.` anywhere in the file. The new transform injects the runtime import automatically, so you no longer need to import React just for JSX.

---

**What is a React element and how is it different from a component?**

An element is a plain JavaScript object that describes what to render — it is not a DOM node. DOM is the Document Object Model, the tree of objects the browser builds from the page. A component is the function or class that produces elements.

```tsx
// The element — just data:
{
  $$typeof: Symbol(react.element),
  type: 'button',
  props: { color: 'blue' },
  key: null,
  ref: null,
}
```

The element is the description; the component is the factory. `$$typeof` is a Symbol, which cannot be JSON-serialized. That blocks cross-site scripting (XSS) attacks, where an attacker injects data that the page then executes. Injected JSON cannot pretend to be a React element, because it can never carry that Symbol.

---

**What triggers a re-render in React?**

Four things, and nothing else:

1. `setState` or `dispatch` is called.
2. A Context the component consumes changes.
3. The parent component re-renders and passes new props.
4. `forceUpdate` is called, in class components.

```tsx
const [n, setN] = useState(0);

setN(0);   // same value → Object.is bail-out, no re-render
setN(1);   // different value → re-render
```

Note the third trigger. Receiving the *same* props does not prevent a re-render: if the parent re-renders, React still calls the component function. The `Object.is` bail-out applies only when state is set to the value it already has.

---

**What is batching and how did React 18 change it?**

Batching means React groups several `setState` calls into a single re-render. React 18 extended it to every source of updates.

```tsx
function handleClick() {
  setCount(c => c + 1);
  setFlag(f => !f);
  // React 17 and 18: one re-render — both calls are in a React event handler
}

setTimeout(() => {
  setCount(c => c + 1);
  setFlag(f => !f);
  // React 17: two re-renders. React 18: one — batching is automatic
}, 0);

flushSync(() => setCount(c => c + 1));  // opts out: renders synchronously
```

In React 17 and earlier, batching only happened inside React event handlers. A `setState` inside a `setTimeout`, a `Promise.then` or a native DOM event triggered a separate re-render per call. React 18 introduced **automatic batching**: every state update is batched, wherever it comes from. The escape hatch is `flushSync`, which forces that one render to happen synchronously.

---

**What does StrictMode do and why does it double-render components in development?**

It calls your component functions twice in development, on purpose, so that impure renders become visible.

```txt
<React.StrictMode> in development
  render()  ← call 1
  render()  ← call 2, same props and state
  commit    ← only once

In production: one call, no doubling.
```

The double call is render phase only, never the commit. If render is truly pure, calling it twice produces the same result. If it mutates external state, logs, or is otherwise not idempotent, the second call makes that visible. StrictMode also detects deprecated APIs and warns about missing cleanup in effects.

---

## Group 2: Hooks Fundamentals

**Why are the Rules of Hooks not arbitrary — what would break if you called a hook conditionally?**

The state of every hook would shift by one position, silently. Hooks are stored as a singly linked list on the Fiber node, and React finds each hook by its position in that list.

```txt
Hook list on the Fiber — found by position, not by name

  render 1:  [1] useState   [2] useEffect   [3] useMemo
  render 2:  [1] useState   [2] useMemo     ← useEffect skipped
                             ↑ useMemo now reads useEffect's node
```

First call reads the first node, second call the second node, and so on. Skip a hook call on a conditional branch, and every hook after it shifts one position. React then reads the wrong node for each of them. The result is silent state corruption: the state that belonged to hook N is now read as the state for hook N-1. The rule exists because the linked list has no names, only positions.

---

**What is the difference between the initial render and an update for useState?**

On mount React creates the hook node; on update it walks the list to find the existing one.

```tsx
// Called ONLY on mount — the lazy initializer:
const [rows, setRows] = useState(() => expensiveCalc());

// Called on EVERY render — the result is thrown away after mount:
const [rows2, setRows2] = useState(expensiveCalc());
```

On mount, React creates a new hook node on the Fiber, runs the initializer, and stores the initial value. On update, React walks the existing linked list to the right node and reads its current value. The setter returned by `useState` is stable across renders: created once, never changed. That is why it is safe to leave out of a dependency array.

---

**What is a stale closure and when does it appear with useEffect?**

A function captured a variable from an outer scope. The variable then changed in a later render, but the function still holds the value it saw when it was created.

```tsx
function Counter() {
  const [count, setCount] = useState(0);

  useEffect(() => {
    const id = setInterval(() => console.log(count), 1000);  // always logs 0
    return () => clearInterval(id);
  }, []);  // ❌ count captured at mount, never updated
}
```

There are two fixes. Include `count` in the dependency array, so the effect re-runs whenever `count` changes. Or keep the latest value in a ref, so you can read it without re-running the effect at all.

---

**What is the difference between useEffect and useLayoutEffect?**

Both run after render, but at different moments — one before the browser paints, one after.

```txt
render → commit (React mutates the DOM) → useLayoutEffect
       → browser paints → useEffect
```

- `useEffect` runs after the browser has painted. It is asynchronous relative to paint, so it does not hold the picture back.
- `useLayoutEffect` runs right after React has applied its DOM mutations, but **before** the browser paints. It does block paint.

That block is exactly what you need when you must measure layout — the size and position of elements — and set state from that measurement. Without it the user sees one frame of the wrong layout.

```tsx
function Tooltip({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [top, setTop] = useState(0);

  useLayoutEffect(() => {
    const box = ref.current!.getBoundingClientRect();  // measure
    setTop(-box.height - 8);                           // place above
  }, []);                                              // before paint

  return <div ref={ref} style={{ top }}>{children}</div>;
}
```

Rule of thumb: default to `useEffect`. Reach for `useLayoutEffect` only when you see a flicker that can only be fixed by reading DOM measurements synchronously after commit. On the server `useLayoutEffect` does nothing, because there is no DOM, and it logs a warning. Use `useEffect` there, or guard with `typeof window !== 'undefined'`.

---

**When does useEffect cleanup run, and in what order?**

In two situations: before the effect re-runs because a dependency changed, and when the component unmounts.

```txt
Dependency changed:
  cleanup of the previous effect  →  new effect

StrictMode, on mount, in development:
  effect  →  cleanup  →  effect     ← deliberately doubled
```

The order for a dependency change is always cleanup first, new effect second. In StrictMode the cleanup-and-effect cycle is deliberately run twice on mount, which surfaces missing cleanup. The cleanup is whatever function the effect callback returns. If the callback returns nothing, there is no cleanup.

---

## Group 3: Hooks Advanced

**When does useMemo actually help performance, and when does it hurt?**

It helps when the computation is genuinely expensive and its inputs rarely change. It hurts when either half of that is false.

| Situation | `useMemo` verdict |
|---|---|
| Computation over 1 ms, runs every render, inputs rarely change | helps |
| Cheap computation, such as `filter` over under 100 items | pure overhead |
| Dependency array changes every render anyway | never hits the cache |
| Object or function created inline inside the deps | never hits the cache |

Measure with `console.time` before adding `useMemo`. The comparison cost plus the closure allocation of `useMemo` itself is not free.

---

**What are the two valid use cases for useCallback?**

Passing a callback into a memoized child, and putting a function into another hook's dependency array.

```tsx
// 1. Prop for a React.memo child — a new reference would defeat the memo:
const handleSelect = useCallback((id: string) => select(id), [select]);
<MemoList onSelect={handleSelect} />

// 2. A function used inside another hook's dependency array:
const load = useCallback(() => fetch(`/api/items?q=${query}`), [query]);
useEffect(() => { void load(); }, [load]);  // re-runs only when query changes
```

Without `useCallback` in the first case, a new function reference is created on every parent render, which defeats the memo optimization. Without it in the second case, the hook would re-run on every render. Note that `useCallback` is just `useMemo` for functions: `useCallback(fn, deps)` is exactly `useMemo(() => fn, deps)`.

---

**What are the four uses of useRef beyond storing DOM references?**

Four, and only the last one is the original use case:

1. **Latest-value pattern** — keep the most recent value of a prop or state in a ref. You can then read it inside a stale closure without re-running the effect.
2. **Previous value** — capture the value from the previous render by updating the ref in `useEffect`, after render.
3. **Instance variables** — hold mutable values that must survive across renders but must not trigger a re-render when they change: timers, subscriptions, WebSocket instances.
4. **DOM refs** — attach to an element to call imperative DOM APIs.

```tsx
// 1 and 2 in one component:
const latest = useRef(value);
const previous = useRef<string | undefined>(undefined);

useEffect(() => {
  previous.current = latest.current;  // yesterday's value
  latest.current = value;             // today's value
}, [value]);
```

---

**What does useImperativeHandle do and when should you use it?**

It replaces the ref value a parent receives with a narrow API you choose.

```tsx
function FancyInput({ ref }: { ref?: React.Ref<{ focus(): void; clear(): void }> }) {
  const input = useRef<HTMLInputElement>(null);

  useImperativeHandle(ref, () => ({
    focus: () => input.current?.focus(),
    clear: () => { if (input.current) input.current.value = ''; },
  }), []);

  return <input ref={input} />;
}
// The parent can call focus() and clear() — nothing else.
```

Without it, attaching a ref to a custom component exposes the whole DOM element, or nothing at all. With it you expose only what you meant to. Use it for component library primitives: custom inputs, video players, modal focus management. The parent legitimately needs imperative access there, but you still want to limit the surface area. In React 19 `ref` is a regular prop, so `forwardRef` is no longer needed for this.

---

**Why does useId produce IDs that are stable across server and client?**

Because it derives the value from the component's position in the Fiber tree, not from a counter.

```tsx
function Field({ label }: { label: string }) {
  const id = useId();  // e.g. "_r_1_" — same on server and client
  return (
    <>
      <label htmlFor={id}>{label}</label>
      <input id={id} aria-describedby={`${id}-hint`} />
      <span id={`${id}-hint`}>Required</span>
    </>
  );
}
```

The tree path is the same on server and client, so the derived ID is the same too, and there is no hydration mismatch. `Math.random()` and incrementing counters diverge, because server and client run the same code independently and produce different values.

- Use it for `htmlFor` and `id` pairs.
- Use it for ARIA attributes. ARIA is Accessible Rich Internet Applications — the attributes that describe a widget to a screen reader.
- Use it anywhere you need a stable, unique ID that survives SSR, that is server-side rendering, where the HTML is produced on the server.
- Never use it as a React `key`.

---

## Group 4: Context & State Management

**What causes all Context consumers to re-render and how do you prevent it?**

A new object identity for the context value. React compares context values with `Object.is`.

```tsx
// ❌ New object on every Provider render → every consumer re-renders:
<UserContext.Provider value={{ user, setUser }}>

// ✅ Same reference until user or setUser actually changes:
const value = useMemo(() => ({ user, setUser }), [user, setUser]);
<UserContext.Provider value={value}>
```

When the Provider re-renders, the inline `{{ user, setUser }}` creates a new object. The reference changes even if `user` and `setUser` did not, so `Object.is(prev, next)` is false and every consumer re-renders. The fix is to memoize the value. `React.memo` on the consumer does **not** help here: it only guards against prop changes, never against context changes.

---

**Why should you put state and dispatch in separate contexts?**

Because `dispatch` never changes and state changes constantly, so sharing one context makes dispatch-only components re-render for nothing.

```tsx
const StateContext = createContext<State | null>(null);
const DispatchContext = createContext<React.Dispatch<Action> | null>(null);

function Provider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  return (
    <DispatchContext.Provider value={dispatch}>
      <StateContext.Provider value={state}>{children}</StateContext.Provider>
    </DispatchContext.Provider>
  );
}
```

`dispatch` from `useReducer` has a stable reference: it never changes between renders. State changes on every update. Put both in one context object, and every consumer re-renders on every state change — including components that only call `dispatch`. Split them, and the dispatch-only components (submit buttons, action creators) never re-render because of a state change.

---

**When should you reach for Zustand/Redux instead of Context + useReducer?**

When updates are frequent, or many unrelated components need one slice of the state.

| Signal | Context + `useReducer` | External store |
|---|---|---|
| Update frequency | low: auth, theme, language | high: every keystroke, every frame |
| Who reads the data | a few components near each other | many disconnected components |
| State shape | simple | large, with independent slices |
| Time-travel debugging | no | yes |
| Persistence and sync with external systems | hand-rolled | built in |

The key mechanical difference: a store update does not cause a React re-render unless a component subscribes to the specific slice that changed. Context re-renders every consumer, no matter which part of the value changed.

---

## Group 5: Fiber, Reconciliation & Performance

**What problem did the Fiber architecture solved that the old stack reconciler couldn't?**

Fiber made the render phase interruptible. The old stack reconciler was a recursive, synchronous algorithm: once started, it ran to completion and blocked the main thread. For large trees that meant 50–100 ms of blocking, which drops frames and makes input unresponsive.

```txt
Stack reconciler — recursion, all or nothing
  reconcile(App) → reconcile(Main) → reconcile(Article) × 50
  Cannot stop in the middle. 50–100 ms of blocked main thread.

Fiber — a linked list walked by a loop
  child → sibling → return, one node per step
  React can stop after any node and hand control back.
```

Fiber replaced the recursion with a linked list: `child`, `sibling` and `return` pointers. Traversal became an iterative loop that can pause after any node. That is what enables time slicing. React works in chunks of about 5 ms and yields to the browser between them, so the frame rate holds while a large tree renders.

---

**What is the double buffering technique in React's Fiber architecture?**

React keeps two Fiber trees at once and swaps them in a single commit.

```txt
current tree              work-in-progress tree
(on screen, never          (being built, may be
 touched during render)     thrown away)
        │                          │
        └──────── alternate ───────┘
                    │
              one atomic swap on commit
```

The **current** tree is what is displayed. The **work-in-progress** tree is what is being built. All reconciliation work happens on the work-in-progress tree, so the current tree stays intact and always renderable.

When the work-in-progress tree is complete, React swaps the two trees atomically, in a single commit. The browser therefore always sees a complete, consistent UI — user interface, what the person on the other side of the screen sees. The `alternate` pointer on each Fiber node links the current and work-in-progress versions of the same component.

---

**Explain the three reconciliation rules React uses when diffing trees.**

1. **Different type → unmount and remount.** Say the element at a position changes from `<div>` to `<span>`, or from `<ComponentA>` to `<ComponentB>`. React unmounts the old subtree entirely and mounts the new one, with no attempt to update in place.
2. **Same type → update in place.** React updates the props of the existing Fiber, keeping the DOM nodes and the component state.
3. **Keys → identity.** Among a list of children, React matches children by `key` rather than by position.

```tsx
// Rule 1 in action — this remounts Panel and wipes its state:
{isWide ? <div><Panel /></div> : <section><Panel /></section>}

// Rule 3 in action — the row keeps its state wherever it moves:
{rows.map(r => <Row key={r.id} row={r} />)}
```

A child with key `"a"` stays the same child wherever it moves in the list. React updates it instead of unmounting and remounting it.

---

**What is wrong with using array index as a key?**

Index keys tie identity to position, so any reorder, filter or non-trailing insert makes React match the wrong elements.

```txt
before:  [A, B, C]   keys [0, 1, 2]
delete A
after:   [B, C]      keys [0, 1]

React sees key 0 and thinks "this is still A".
It updates A's Fiber with B's data, instead of unmounting A
and reusing B's existing Fiber.
```

For uncontrolled inputs that shows up as the wrong text sitting in the wrong field. Use stable, unique identifiers from the data as keys. One exception: index keys are safe when the list is static and never reordered.

---

**What is the difference between the render phase and the commit phase?**

The render phase is pure and interruptible; the commit phase is synchronous and cannot be interrupted.

| | Render phase (reconciliation) | Commit phase |
|---|---|---|
| What happens | component functions are called, output is diffed, the work-in-progress tree is built | accumulated DOM mutations are applied |
| Sub-steps | one pass over the tree | before mutation → mutation → layout |
| DOM touched | no | yes |
| Interruptible | yes: can be paused, restarted or abandoned | no |
| Effects fired | none | `useLayoutEffect` cleanups and callbacks |

After the commit the browser paints. Only then does React fire `useEffect` cleanups and callbacks — the passive effects phase.

---

**What do React's lane priorities mean and how does startTransition use them?**

Lanes are a bitmask system in which each lane is one priority level. `startTransition` marks its update with the transition lane, the lowest interactive priority.

```txt
SyncLane             highest — discrete user input
InputContinuousLane  dragging, hovering
DefaultLane          ordinary setState
TransitionLane       low-priority background work  ← startTransition
IdleLane             lowest
```

React schedules work by lane and processes higher-priority lanes first. Say a higher-priority update arrives while a transition is rendering — the user types in an input. React interrupts the transition, processes the urgent update, then resumes or restarts the transition.

---

## Group 6: Performance Patterns

**What are the three conditions that must all be true for React.memo to provide benefit?**

1. The component renders often — its parent re-renders frequently because of unrelated state changes.
2. The re-render is expensive — the component has many children, or does heavy work during render.
3. The props are referentially stable between renders — primitives do not change, and object, array and function props are memoized with `useMemo` or `useCallback`.

```tsx
// ❌ Condition 3 broken — a new object and a new function every render:
<MemoChild config={{ theme: 'dark' }} onSelect={() => pick()} />

// ✅ Stable references, so the comparison can actually succeed:
const config = useMemo(() => ({ theme: 'dark' }), []);
const onSelect = useCallback(() => pick(), []);
<MemoChild config={config} onSelect={onSelect} />
```

If condition 3 is not met, the props comparison always reports "changed", because new references are created on every parent render. `React.memo` then adds comparison overhead for zero benefit.

---

**What is the children pattern (lifting content up) and what performance problem does it solve?**

Instead of importing the heavy component, accept it as `children`. The component that owns the fast-changing state then cannot re-render it.

```tsx
// ✅ MouseTracker owns the fast state but not the heavy child:
function MouseTracker({ children }: { children: React.ReactNode }) {
  const [pos, setPos] = useState({ x: 0, y: 0 });
  return (
    <div onMouseMove={e => setPos({ x: e.clientX, y: e.clientY })}>
      <p>Mouse: {pos.x}, {pos.y}</p>
      {children}
    </div>
  );
}

function Page() {
  return <MouseTracker><HeavyChart /></MouseTracker>;
}
```

When a component owns fast-changing state — mouse position, scroll, timers — anything it imports and renders re-renders every time that state changes. With the children pattern the heavy component belongs to `Page`, which does not track the mouse. Its Fiber is already created by the grandparent, and `MouseTracker` just receives it as a pre-built value and places it in the output.

---

**When should you use virtualization and when does it not help?**

It solves the DOM node count problem. It does nothing for re-render frequency.

| | Virtualization helps | Virtualization does not help |
|---|---|---|
| The problem | 10,000 rows create 10,000 DOM nodes, expensive to attach, measure and paint | the visible rows re-render on every keystroke |
| List length | 500+ items | under about 100 items |
| Row content | non-trivial to render | trivial |
| User behaviour | scrolls a lot | barely scrolls |

Libraries: `react-window`, `@tanstack/react-virtual`. They render only the visible rows plus a small overscan buffer. Do not reach for virtualization when the list is short — the overhead is not justified — or when the real bottleneck is something else entirely.

---

**What does the React DevTools Profiler measure and what does it not measure?**

It measures the render phase only: the time spent calling component functions and diffing their output. Three things are outside that measurement:

- commit phase duration, meaning the DOM mutations being applied;
- `useEffect` execution time;
- browser paint time.

```tsx
// The <Profiler> component is not the DevTools panel — it works in production:
<Profiler
  id="ProductList"
  onRender={(id, phase, actualDuration, baseDuration) => {
    analytics.track('react_render', { id, phase, actualDuration, baseDuration });
  }}
>
  <ProductList />
</Profiler>
```

So a component can look fast in the Profiler and still feel slow. Its commit may generate many expensive DOM mutations, or its `useEffect` may do heavy work. For the whole frame, including commit and paint, use the Chrome DevTools Performance tab.

---

## Group 7: Concurrent Features

**What is the difference between startTransition and useDeferredValue?**

Both mark work as low-priority. They differ in where you apply the control.

| | `startTransition` | `useDeferredValue` |
|---|---|---|
| Use it when | you own the state setter | the value arrives from outside |
| Where you wrap | the `setState` call | the value itself |
| Typical source | your own component's state | a prop, parent state, a library |

```tsx
// You own the setter:
startTransition(() => setResults(filter(data, query)));

// You only receive the value:
const deferredQuery = useDeferredValue(query);
```

Pick the one that matches where the value originates. If you control the update, use `startTransition`. If you merely receive it, use `useDeferredValue`.

---

**How does Suspense work mechanically — what does "suspend" actually mean?**

To suspend is to throw a Promise during the render phase. React catches it and shows a fallback until the Promise resolves.

```txt
1. Component throws a Promise while rendering.
2. React catches it at the nearest <Suspense> boundary.
3. React shows that boundary's fallback.
4. React registers a callback on the thrown Promise.
5. The Promise resolves → React retries the component.
6. This time it renders normally → React commits the real UI.
```

On the retry the component must not throw again: the data has to be ready. Data libraries implement exactly this protocol — they cache requests and throw the still-running Promise on the first call. React Query and SWR both do it. SWR is stale-while-revalidate, a caching strategy that serves the cached value first and refreshes it in the background.

---

**Why does wrapping a navigation in startTransition prevent the Suspense fallback from flashing?**

Because a transition keeps the old page on screen instead of replacing it with a fallback.

```txt
Without startTransition — urgent update
  old page → fallback (flash!) → new page

With startTransition — low-priority update
  old page (isPending = true) ──────────▶ new page
  the new page renders in the background
```

- **Without `startTransition`** the navigation is urgent. React switches to the new page's Suspense boundary at once and shows the fallback immediately. Even if the data arrives in 50 ms, there is a visible flash.
- **With `startTransition`** React marks the update as a transition. It keeps the current page visible and sets `isPending` to `true` while the new page renders in the background.

When the new page's Suspense resolves and its content is ready, React commits the whole transition in one step. The old page disappears and the new one appears, with no blank screen in between.

---

**Is useDeferredValue the same as debouncing?**

No. Debouncing delays the state update; `useDeferredValue` delays nothing.

| | Debounce | `useDeferredValue` |
|---|---|---|
| What is delayed | the state update itself | only the priority of the render |
| Timer involved | yes | no |
| Intermediate values | dropped | all eventually rendered |
| Setter called | after the timer fires | immediately |

`useDeferredValue` receives an already-updated value and tells React to render it at a lower priority. The current render keeps showing the previous deferred value while the new render proceeds in the background. React will always render the latest value eventually. The lag you perceive comes from React deprioritizing the deferred render while higher-priority work exists, not from an artificial delay.

---

## Group 8: Server Components & React 19

**What is the serialization boundary and why can't functions cross it?**

It is the line where a Server Component hands data to a Client Component, and only serializable values may cross it.

```tsx
// ✅ Crosses the boundary:
<ClientComp str="hi" num={42} arr={[1, 2]} obj={{ a: 1 }}
            node={<AnotherServerComponent />} />

// ❌ Cannot cross:
<ClientComp fn={() => save()} inst={new MyClass()} map={new Map()} />
```

When a Server Component renders a Client Component, the output is serialized into the RSC payload — React Server Components payload, a JSON-like wire format. Primitives, arrays, plain objects and React elements can cross. Functions cannot: serializing code would mean shipping code to run on the client, and that is a security risk.

```txt
RSC payload — what may cross, in one line each

  ✓ primitives, arrays, plain objects
  ✓ React elements (output of another Server Component)
  ✗ functions, class instances, Symbols, Map, Set, undefined
```

That is why event handlers must live in Client Components. They cannot be defined on the server and passed down as props.

---

**Does 'use client' mean the component only runs on the client?**

No. It marks the **boundary** between the server component tree and the client component tree.

```txt
Where a Client Component actually runs

  on the server, for SSR and SSG  →  produces the initial HTML
      SSG = static site generation: pages become HTML
            at build time
  in the browser                  →  hydration, then every
                                     later update
```

So `'use client'` means something narrower. This component and its subtree use client-side React features — state, effects, browser APIs — and must be included in the JavaScript bundle sent to the browser. It does not mean "never execute on the server".

---

**What is the difference between Server Actions and API routes?**

An API route is an HTTP endpoint you write by hand. A Server Action is a function the framework exposes as an endpoint for you.

| | API route | Server Action |
|---|---|---|
| How you define it | a route file with a request handler | a function marked `'use server'` |
| How you call it | `fetch` to a URL you built | like a normal function |
| Serialization and transport | you write it | the framework does it |
| Works without JavaScript | no | yes, through `<form action={...}>` |
| Cache invalidation | your own code | `revalidatePath` / `revalidateTag` |
| Best for | public APIs consumed by third parties | internal form submits and mutations |

With an API route you define the URL, parse the request body, handle authentication and return a response. A Server Action integrates with the React form model instead, and can invalidate Next.js caches directly.

---

**What are the four main causes of hydration mismatches?**

1. **Browser APIs in render** — reading `window`, `localStorage` or `document` inside the render function. These are undefined on the server.
2. **Time and date rendering** — `new Date().toLocaleTimeString()` produces one value when the server renders and another when the client hydrates milliseconds later.
3. **Random values** — `Math.random()` gives different numbers on server and client.
4. **Conditional rendering on browser-only info** — `typeof window !== 'undefined'` is false on the server and true on the client, so the output differs.

```tsx
// ❌ Server renders '', client renders 'dark':
const theme = window.localStorage.getItem('theme') ?? 'light';

// ✅ Same on both, then updated after hydration:
const [theme, setTheme] = useState('light');
useEffect(() => setTheme(localStorage.getItem('theme') ?? 'light'), []);
```

Three fix patterns cover almost everything:

- Read browser-only values in `useEffect`, after hydration.
- Use deterministic values — hash a user ID into a colour, for instance.
- Use `suppressHydrationWarning` for mismatches you know about and intend.

---

**What is the difference between useActionState and useFormStatus in React 19?**

`useActionState` owns the action. `useFormStatus` only reads the form it sits inside.

| | `useActionState` | `useFormStatus` |
|---|---|---|
| Lives in | the component that owns the form | any component *inside* the form |
| Gives you | the action's result, plus `isPending` | `pending`, `data`, `method`, `action` |
| Reads from | the action it wraps | the nearest parent `<form>` |

`useActionState` wraps the action function, holds its result — success data or error — and provides `isPending`. It is the hook that supplies the `action` prop to the form. `useFormStatus` suits components nested inside a form — a submit button, a loading indicator. They do not own the action but need the form's status. The two compose.

---

**What does the React Compiler (React Forget) actually do and what can't it fix?**

It inserts memoization for you at build time. It cannot fix where your state lives.

```tsx
// You write this:
const filtered = todos.filter(t => t.title.includes(filter));

// The compiler emits something equivalent to this:
const filtered = useMemo(
  () => todos.filter(t => t.title.includes(filter)),
  [todos, filter]
);
```

The Compiler is a build-time Babel plugin, and it also runs through SWC — the Speedy Web Compiler, the Rust-based build tool Next.js uses. It works out which values are "reactive", meaning they depend on props, state or other reactive values, and inserts memoization where that is safe.

```txt
React Compiler
  fixes      the useMemo / useCallback / React.memo
             you would otherwise write by hand
  can't fix  state that lives too high in the tree
             inline Context value objects
             re-renders that come from the architecture
```

It optimizes individual components. It cannot fix a design where the wrong component owns the state.

---

## Group 9: Patterns & Architecture

**What is the Compound Components pattern and how does it differ from a prop-based API?**

It splits one component into a parent that owns the state and children that read it from context, so the consumer controls the layout.

```tsx
// Prop-based API — the author must anticipate every need:
<Select options={opts} renderOption={fn} maxHeight={300} showBorder />

// Compound Components — the consumer assembles it:
<Select defaultValue="react">
  <div className="header">Choose a framework</div>
  <Select.Option value="react">React</Select.Option>
  <Select.Option value="vue">Vue</Select.Option>
</Select>
```

The parent owns state and coordination logic and exposes it through context. The child components consume that context without prop drilling. A prop-based API forces the component author to anticipate every customization need in advance. Compound Components delegate layout and composition to the consumer, so the author only has to define the coordination logic.

---

**What does an Error Boundary catch and what does it not catch?**

It catches errors thrown while rendering, and nothing that happens outside the render cycle.

```txt
✓ Caught
    errors thrown during render (the component function body)
    errors in class component lifecycle methods
    errors in the constructors of child components

✗ Not caught
    errors in event handlers
    errors in async code: setTimeout, Promise rejection, async/await
    errors thrown by the Error Boundary itself
```

For an event handler, use `try/catch` inside the handler and store the error in state. Async code runs outside the React render cycle, which is why a boundary never sees it. To surface an async error through a boundary, catch it manually and set it into state. React then throws that state value during the next render, and the boundary catches it there.

---

**When would you use a Portal and what makes it different from just rendering inline?**

A Portal renders a child into a DOM node outside the React root, while keeping the child inside the React tree. Context and event bubbling keep working normally. Reach for one when a CSS ancestor creates a containment problem, which takes three shapes:

- `overflow: hidden` clips the content.
- A low `z-index` buries it under its siblings.
- A CSS transform creates a new stacking context.

```txt
React tree                DOM tree
<Dashboard>               <body>
  <Modal>                   <div id="root"> ... </div>
    <ConfirmDialog />       <div class="modal-overlay">
  </Modal>                    <ConfirmDialog />
</Dashboard>                </div>
                          </body>
```

The classic example is a modal dialog inside a scrollable card with `overflow: hidden`. Rendered inline it gets clipped. Rendered through a Portal it lands in `document.body`, where no ancestor's CSS constraints apply.

---

**Why did Higher-Order Components fall out of favor compared to custom hooks?**

An HOC is a function that takes a component and returns a wrapped one. Four costs compound, and a custom hook has none of them.

| HOC cost | With a custom hook |
|---|---|
| each HOC adds a wrapper component visible in DevTools, which makes traces confusing | no wrapper component at all |
| two HOCs injecting the same prop name silently overwrite each other | outputs are variables named by the caller |
| TypeScript needs mechanical `Omit<P, 'injectedProp'>` boilerplate | the return type is inferred |
| refs need explicit `forwardRef` forwarding | nothing to forward |

A custom hook achieves the same logic reuse as a plain function whose return values the caller names. The one remaining valid use case for an HOC is wrapping Error Boundaries, which must be class components.

---

**What is the difference between a controlled and uncontrolled component, and why does React Hook Form use uncontrolled inputs by default?**

A controlled input keeps its value in React state. An uncontrolled input keeps it in the DOM.

```tsx
// Controlled — every keystroke re-renders:
<input value={value} onChange={e => setValue(e.target.value)} />

// Uncontrolled — read on demand, no re-render per keystroke:
<input ref={inputRef} defaultValue="" />
```

With a controlled input, `defaultValue` plays no part: `value` plus `onChange` is the whole contract. With an uncontrolled input, `defaultValue` sets the initial value and you read the current one through a ref, or through `FormData` on submit.

React Hook Form uses uncontrolled inputs to avoid re-rendering on every keystroke. In a form with 20 fields, a controlled approach could trigger 20 re-renders per keystroke chain. React Hook Form registers inputs with a ref and only triggers re-renders for validation state changes and explicit form-level updates, never for individual characters.
