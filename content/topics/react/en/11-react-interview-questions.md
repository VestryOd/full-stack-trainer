# React — Interview Questions (Senior)

## Group 1: JSX, Rendering & Elements

**What does JSX actually compile to, and why does React need to be in scope in older versions?**

JSX `<Button color="blue">Click</Button>` compiles to `React.createElement(Button, { color: 'blue' }, 'Click')` with the classic transform, or to `_jsx(Button, { color: 'blue', children: 'Click' })` with the new JSX transform (React 17+). In older code, `React.createElement` was called directly, so `React` had to be in scope — even if you never wrote `React.` anywhere. With the new transform (`"jsx": "react-jsx"` in tsconfig), the runtime import is injected automatically and you no longer need to import React for JSX.

---

**What is a React element and how is it different from a component?**

A React element is a plain JavaScript object: `{ $$typeof: Symbol(react.element), type: 'button', props: { color: 'blue' }, key: null, ref: null }`. It describes what to render. A component is a function (or class) that accepts props and returns elements. The element is the description; the component is the factory. `$$typeof` is a Symbol — it cannot be JSON-serialized, which prevents XSS attacks via injected JSON rendered as JSX.

---

**What triggers a re-render in React?**

Four things: (1) `setState` / `dispatch` is called; (2) a Context the component consumes changes; (3) the parent component re-renders and passes new props; (4) `forceUpdate` (class components). Notably, receiving the *same* props does not prevent a re-render if the parent re-renders — React still calls the component function. The `Object.is` bail-out only applies when state is set to the same value as the current state — in that case React bails out without a re-render.

---

**What is batching and how did React 18 change it?**

Batching means React groups multiple `setState` calls from the same event handler into a single re-render. In React 17 and earlier, batching only happened inside React event handlers — `setState` inside a `setTimeout`, `Promise.then`, or native DOM event triggered a separate re-render per call. React 18 introduced **automatic batching**: all state updates are batched regardless of where they originate. To opt out of batching for a specific update, wrap it in `flushSync(() => setState(...))`, which forces the render to happen synchronously before returning.

---

**What does StrictMode do and why does it double-render components in development?**

`<React.StrictMode>` intentionally calls component functions twice in development (render phase only, not commit). The purpose is to expose side effects in render bodies — if render is truly pure, calling it twice produces the same result. If it mutates external state, logs, or has non-idempotent behavior, the double call makes that visible. In production, there is no double call. StrictMode also detects deprecated APIs and warns about missing cleanup in effects.

---

## Group 2: Hooks Fundamentals

**Why are the Rules of Hooks not arbitrary — what would break if you called a hook conditionally?**

Hooks are stored as a singly linked list on the Fiber node. React identifies each hook by its position in the list (first call → first node, second call → second node). If a hook call is skipped on a conditional branch, every hook after it shifts one position — React reads the wrong node for every subsequent hook. The result is silent state corruption: the state that belonged to hook N is now read as the state for hook N-1. The rule exists because the linked list has no names, only positions.

---

**What is the difference between the initial render and an update for useState?**

On mount, React creates a new hook node on the Fiber, calls the initializer (or runs the lazy initializer function), and stores the initial value. On update, React walks the existing linked list to find the correct hook node and reads its current value. The setter function returned by `useState` is stable across renders — it is created once and never changes. The lazy initializer (`useState(() => expensiveCalc())`) is only called on mount; passing an expression directly (`useState(expensiveCalc())`) calls it on every render even though the result is discarded after mount.

---

**What is a stale closure and when does it appear with useEffect?**

A stale closure occurs when a function captures a variable from an outer scope, but that variable was updated in a later render — the function still holds the old value from when it was created. Classic example: `useEffect(() => { const id = setInterval(() => console.log(count), 1000); return () => clearInterval(id); }, [])` — `count` is captured at mount and never updates. Fix: include `count` in the dependency array (effect re-runs when count changes), or use a ref to always access the latest value without re-running the effect.

---

**What is the difference between useEffect and useLayoutEffect?**

Both run after render. `useEffect` runs after the browser has painted — it is asynchronous relative to paint, so it does not block the visual update. `useLayoutEffect` runs after React has applied DOM mutations but **before** the browser paints — it blocks paint, which is necessary when you need to measure DOM layout and update state based on that measurement (to avoid a visible flash of the wrong layout). Rule of thumb: default to `useEffect`; use `useLayoutEffect` only when you see a visual flicker that can only be fixed by reading DOM measurements synchronously after commit. On the server, `useLayoutEffect` does nothing (no DOM) and logs a warning — use `useEffect` or guard with `typeof window !== 'undefined'`.

---

**When does useEffect cleanup run, and in what order?**

Cleanup runs in two situations: (1) before the effect re-runs due to a dependency change — the previous effect's cleanup runs first, then the new effect fires; (2) when the component unmounts. In StrictMode (development), the cleanup and effect cycle is deliberately run twice on mount to surface missing cleanup. The order for a dependency change: `[cleanup of previous effect] → [new effect]`. The cleanup is the function returned from the effect callback — if the callback doesn't return a function, there is no cleanup.

---

## Group 3: Hooks Advanced

**When does useMemo actually help performance, and when does it hurt?**

`useMemo` helps when: the computation is genuinely expensive (> 1ms), it runs on every render, and the inputs change infrequently. `useMemo` hurts (or is neutral but adds noise) when: the computation is cheap (array.filter on < 100 items), or the dependency array changes on every render anyway (object/function created inline), which makes `useMemo` run every time and the cache is never used. Measure with `console.time` before adding `useMemo`. The comparison cost plus the closure allocation of `useMemo` itself is not free.

---

**What are the two valid use cases for useCallback?**

(1) Passing a callback as a prop to a `React.memo`-wrapped child — without `useCallback`, a new function reference is created on every parent render, defeating the memo optimization. (2) Including a function in the dependency array of another hook (`useEffect`, `useCallback`, `useMemo`) — without stabilizing the function reference, the hook would re-run on every render. `useCallback` is `useMemo` for functions: `useCallback(fn, deps)` is exactly `useMemo(() => fn, deps)`.

---

**What are the four uses of useRef beyond storing DOM references?**

(1) **Latest-value pattern**: store the most recent value of a prop or state in a ref to access it inside a stale closure without re-running the effect. (2) **Previous value**: capture the value from the previous render by updating the ref in `useEffect` after render. (3) **Instance variables**: store mutable values that must persist across renders but should not trigger re-renders when changed (timers, subscriptions, WebSocket instances). (4) **DOM refs**: the original use case — attaching to an element to call imperative DOM APIs.

---

**What does useImperativeHandle do and when should you use it?**

`useImperativeHandle` customizes the ref value exposed to a parent when the parent attaches a ref to the component. Without it, attaching a ref to a custom component exposes the entire DOM element or nothing. With it, you expose only a controlled API: `useImperativeHandle(ref, () => ({ focus, clear }), [])` — the parent can only call `focus` and `clear`, not arbitrary DOM methods. Use it for component library primitives (custom inputs, video players, modal focus management) where the parent legitimately needs imperative access but you want to limit surface area. In React 19, `ref` is a regular prop — `forwardRef` is no longer needed.

---

**Why does useId produce IDs that are stable across server and client?**

`useId` derives its value from the component's position in the Fiber tree (the tree path), not from a counter that increments independently on client and server. Because the component tree structure is the same on server and client, the derived ID is also the same — no hydration mismatch. `Math.random()` and incrementing counters diverge because the server and client run the same code independently and produce different values. Use `useId` for `htmlFor`/`id` pairs, ARIA attributes, and any other case where a stable, unique, SSR-safe ID is needed. Never use it as a React `key`.

---

## Group 4: Context & State Management

**What causes all Context consumers to re-render and how do you prevent it?**

React compares Context values with `Object.is`. When the Provider re-renders, it creates a new object for `value={{ user, setUser }}` — the reference changes even if `user` and `setUser` haven't changed. All consumers re-render because `Object.is(prev, next)` is false. Fix: memoize the context value with `useMemo(() => ({ user, setUser }), [user, setUser])`. `React.memo` on the consumer does **not** help — it only prevents re-renders from prop changes, not context changes.

---

**Why should you put state and dispatch in separate contexts?**

`dispatch` (from `useReducer`) has a stable reference — it never changes between renders. State changes on every update. If you put both in one context object, every component consuming the context re-renders on every state change — even components that only call dispatch and don't care about the current state values. Splitting into `StateContext` and `DispatchContext` means components that only need to dispatch (submit buttons, action creators) never re-render due to state changes.

---

**When should you reach for Zustand/Redux instead of Context + useReducer?**

Context + useReducer is sufficient for: low-frequency updates (user auth, theme, language), data shared across a few components, simple state shape. Reach for an external store when: state updates are frequent (every keystroke, every animation frame), many disconnected components need the same slice, you need time-travel debugging, or you need state persistence/sync with external systems. The key difference: Zustand/Redux store updates do not cause React re-renders unless a component subscribes to the specific slice that changed. Context re-renders all consumers regardless of which part of the value changed.

---

## Group 5: Fiber, Reconciliation & Performance

**What problem did the Fiber architecture solve that the old stack reconciler couldn't?**

The old stack reconciler was a recursive, synchronous algorithm — once started, it ran to completion, blocking the main thread. For large trees this could take 50–100ms, causing dropped frames and unresponsive input. Fiber replaced recursion with a linked list (child → sibling → return pointers), turning the tree traversal into an iterative loop that can be paused after any node. This enables time slicing: React works in ~5ms chunks and yields to the browser between chunks, keeping the frame rate smooth while rendering large trees.

---

**What is the double buffering technique in React's Fiber architecture?**

React maintains two Fiber trees simultaneously: the **current** tree (what is displayed) and the **work-in-progress** tree (what is being built). All reconciliation work happens on the work-in-progress tree, leaving the current tree intact and always renderable. When the work-in-progress tree is complete, React atomically swaps the two trees in a single commit — the browser always sees a complete, consistent UI. The alternate pointer on each Fiber node links the current and work-in-progress versions of the same component.

---

**Explain the three reconciliation rules React uses when diffing trees.**

(1) **Different type → unmount and remount**: if the element at a position changes from `<div>` to `<span>`, or from `<ComponentA>` to `<ComponentB>`, React unmounts the old subtree entirely and mounts the new one — no attempt to update in place. (2) **Same type → update in place**: React updates the props of the existing Fiber, preserving DOM nodes and component state. (3) **Keys → identity**: among a list of children, React matches children by `key` rather than position. A child with key "a" is the same regardless of where it moves in the list — React updates it rather than unmounting and remounting.

---

**What is wrong with using array index as a key?**

When items are reordered, filtered, or inserted at positions other than the end, index-based keys cause React to match the wrong element identities. Example: a list `[A, B, C]` with keys `[0, 1, 2]` — deleting A produces `[B, C]` with keys `[0, 1]`. React thinks key 0 is still A (it was A before), so it updates A's Fiber with B's data instead of unmounting A and reusing B's existing Fiber. For uncontrolled inputs this causes the wrong content to appear in the field. Use stable, unique identifiers from the data as keys. Exception: index keys are safe when the list is static and never reordered.

---

**What is the difference between the render phase and the commit phase?**

The **render phase** (also called reconciliation) is pure and interruptible: React calls component functions, diffs the output against the previous tree, and builds the work-in-progress Fiber tree. No DOM mutations happen here. It can be paused, restarted, or abandoned. The **commit phase** is synchronous and non-interruptible: React applies the accumulated DOM mutations (before mutation → mutation → layout sub-phases), fires `useLayoutEffect` cleanups and callbacks, then hands off to the browser to paint. After paint, React fires `useEffect` cleanup and callbacks (the passive effects phase).

---

**What do React's lane priorities mean and how does startTransition use them?**

Lanes are a bitmask system where each lane represents a priority level: `SyncLane` (highest, used for discrete user input), `InputContinuousLane` (dragging, hovering), `DefaultLane` (normal setState), `TransitionLane` (low-priority background work), `IdleLane` (lowest). React schedules work by lane and processes higher-priority lanes first. `startTransition` marks its state update with `TransitionLane` — the lowest interactive priority. If a higher-priority update (typing in an input) arrives while a transition is rendering, React interrupts the transition, processes the high-priority update, then resumes or restarts the transition.

---

## Group 6: Performance Patterns

**What are the three conditions that must all be true for React.memo to provide benefit?**

(1) The component renders often — its parent re-renders frequently due to unrelated state changes. (2) The re-render is expensive — the component has many children or performs heavy work during render. (3) The props are referentially stable between renders — primitives don't change, and object/array/function props are memoized with `useMemo`/`useCallback`. If condition 3 is not met, the props comparison always returns "changed" because new references are created on every parent render, and `React.memo` adds comparison overhead with zero benefit.

---

**What is the children pattern (lifting content up) and what performance problem does it solve?**

When a component owns fast-changing state (mouse position, scroll, timers), any component it imports and renders will re-render every time the state changes. The fix: instead of importing the heavy component, accept it as `children`. The parent component that renders the heavy component now only re-renders when its own state changes — it is not the one tracking mouse position. The heavy component's Fiber is already created by the grandparent; `MouseTracker` just receives it as a pre-built value and places it in the output without triggering a fresh render of it.

---

**When should you use virtualization and when does it not help?**

Virtualization (react-window, @tanstack/react-virtual) solves the **DOM node count** problem: 10,000 list rows create 10,000 DOM nodes, which is expensive to attach, measure, and paint. Virtualization renders only the visible rows plus a small overscan buffer. It does not solve the **re-render frequency** problem — if the visible rows re-render on every keystroke, virtualization does not help with that. Use virtualization when: the list is 500+ items, each row is non-trivial, and the user scrolls. Don't use it when: the list is under ~100 items (overhead is not justified), or when the performance bottleneck is something else entirely.

---

**What does the React DevTools Profiler measure and what does it not measure?**

The Profiler measures the **render phase**: time spent calling component functions and diffing output. It does not measure: commit phase duration (applying DOM mutations), `useEffect` execution time, or browser paint time. A component can appear fast in the Profiler but still cause slow perceived performance if its commit generates many expensive DOM mutations or its `useEffect` does heavy work. For full frame time including commit and paint, use the Chrome DevTools Performance tab. The `<Profiler>` component API (not DevTools) works in production builds and can send `actualDuration` and `baseDuration` to analytics.

---

## Group 7: Concurrent Features

**What is the difference between startTransition and useDeferredValue?**

Both mark work as low-priority, but they differ in where you apply the control. `startTransition` is used when you **own the state setter** — you wrap the `setState` call: `startTransition(() => setResults(filter(data, query)))`. `useDeferredValue` is used when you **receive the value from outside** (prop, parent state, library) and want to defer it locally: `const deferredQuery = useDeferredValue(query)`. Use the one that matches where the value originates — if you control the update, use `startTransition`; if you receive it, use `useDeferredValue`.

---

**How does Suspense work mechanically — what does "suspend" actually mean?**

When a component "suspends," it throws a special value (a Promise) during the render phase. React catches the thrown value at the nearest `<Suspense>` boundary. React shows the boundary's `fallback` UI. React registers a callback on the thrown Promise — when it resolves, React retries rendering the suspended component. On the retry, the component must not throw again (the data must be ready) — it renders normally and React commits the result, replacing the fallback with the real UI. Data libraries (React Query, SWR) implement this protocol by caching requests and throwing the in-flight Promise on the first call.

---

**Why does wrapping a navigation in startTransition prevent the Suspense fallback from flashing?**

Without `startTransition`: the navigation is treated as urgent. React immediately switches to the new page's Suspense boundary, which shows the fallback at once — even if the data arrives in 50ms, there is a visible flash. With `startTransition`: React marks the update as a transition. Instead of replacing the current page with a fallback, React keeps the current page visible (marking `isPending = true`) while the new page renders in the background. When the new page's Suspense resolves and its content is ready, React commits the full transition in one step — the old page disappears and the new one appears without an intermediate blank screen.

---

**Is useDeferredValue the same as debouncing?**

No. Debouncing delays the **state update itself** — the setter is not called until a timer fires, so intermediate values are dropped. `useDeferredValue` receives an already-updated value and tells React to render it at a lower priority — the current render uses the previous deferred value while the new render processes in the background. There is no timer, no delay, and no dropped updates: React will always render with the latest value eventually. The perceived lag comes from React deprioritizing the deferred render when higher-priority work is present, not from an artificial delay.

---

## Group 8: Server Components & React 19

**What is the serialization boundary and why can't functions cross it?**

When a Server Component renders a Client Component, the output is serialized into the RSC payload — a JSON-like wire format. Only serializable values can cross: primitives, arrays, plain objects, React elements. Functions cannot be serialized because serializing code is a security risk (arbitrary code execution on the client). This is why event handlers must live in Client Components — they cannot be defined on the server and passed as props to a client. React elements (the output of rendering another Server Component) can cross the boundary because they are plain objects, not code.

---

**Does 'use client' mean the component only runs on the client?**

No. `'use client'` marks the **boundary** between the server component tree and the client component tree. Client Components still run on the server during SSR/SSG to produce the initial HTML — they just also run on the client for hydration and subsequent updates. `'use client'` means: this component and its subtree use client-side React features (state, effects, browser APIs) and must be included in the JavaScript bundle sent to the browser. It does not mean "never execute on the server."

---

**What is the difference between Server Actions and API routes?**

API routes are explicit HTTP endpoints — you define the URL, parse the request body, handle authentication, and return a response. Server Actions are functions marked with `'use server'` that the framework automatically exposes as POST endpoints. You call them like regular functions from Client Components; the framework handles serialization, transport, and deserialization. Server Actions integrate with the React form model (`<form action={serverAction}>`) and work without JavaScript (progressive enhancement). They can call `revalidatePath`/`revalidateTag` to invalidate Next.js caches directly. Use API routes for public APIs consumed by third parties; use Server Actions for internal form submissions and mutations from UI.

---

**What are the four main causes of hydration mismatches?**

(1) **Browser APIs in render**: accessing `window`, `localStorage`, or `document` during the render function — these are undefined on the server. (2) **Time/date rendering**: `new Date().toLocaleTimeString()` produces different values when the server renders vs when the client hydrates milliseconds later. (3) **Random values**: `Math.random()` generates different values on server and client. (4) **Conditional rendering on browser-only info**: `typeof window !== 'undefined'` is false on the server and true on the client, causing different output. Fix patterns: use `useEffect` to read browser-only values after hydration, use stable/deterministic values (hash user ID → color), or use `suppressHydrationWarning` for known intentional mismatches.

---

**What is the difference between useActionState and useFormStatus in React 19?**

`useActionState` manages the **state returned by a form action** — it wraps the action function, holds the result (success data / error), and provides `isPending` for the running action. It is used in the component that owns the form and provides the `action` prop. `useFormStatus` reads the **submission status of the nearest parent form** — it provides `pending`, `data`, `method`, and `action` fields. It is designed for components nested inside a form (a submit button, a loading indicator) that don't own the action but need to know the form's status. They compose: `useActionState` provides the `action` to the form; `useFormStatus` reads that form's status from inside child components.

---

**What does the React Compiler (React Forget) actually do and what can't it fix?**

The React Compiler is a build-time Babel/SWC plugin that statically analyzes your components, identifies which values are "reactive" (depend on props, state, or other reactive values), and automatically inserts `useMemo`, `useCallback`, and component-level memoization where safe. It eliminates the need to manually write most memoization. What it cannot fix: structural problems in the component tree — state that lives too high (causing large subtrees to re-render), inline Context value objects, or re-renders caused by architecture decisions. The Compiler optimizes individual components; it cannot fix a design where the wrong component owns the state.

---

## Group 9: Patterns & Architecture

**What is the Compound Components pattern and how does it differ from a prop-based API?**

Compound Components split a complex component into a parent (owns state and coordination logic, exposes it via context) and multiple child components (consume the context without prop drilling). The consumer assembles the UI from sub-components and controls the layout entirely. A prop-based API (`<Select options={...} renderOption={...} maxHeight={...}`) forces the component author to anticipate every customization need. Compound Components (`<Select><Select.Option value="a">A</Select.Option></Select>`) delegate layout and composition to the consumer — the component author only needs to define the coordination logic.

---

**What does an Error Boundary catch and what does it not catch?**

Error Boundaries catch errors thrown during the **render phase** (component function body), **lifecycle methods** (class component lifecycles), and **constructors** of child components. They do **not** catch: errors in event handlers (use try/catch inside the handler and store the error in state), errors in async code (setTimeout, Promise rejections, async/await — these run outside the React render cycle), or errors thrown by the Error Boundary itself. For async errors to surface through a boundary, catch them manually and set them into state — React will throw the state value during the next render, which the boundary will catch.

---

**When would you use a Portal and what makes it different from just rendering inline?**

A Portal renders a child into a DOM node outside the React root element, while keeping the child inside the React tree (context and event bubbling work normally). Use a Portal when a CSS ancestor creates a containment problem: `overflow: hidden` clips the content, a low `z-index` buries it under siblings, or a CSS transform creates a new stacking context. The classic example: a modal dialog inside a scrollable card with `overflow: hidden`. Without a Portal it gets clipped; with a Portal it renders in `document.body` and is not subject to any ancestor's CSS constraints.

---

**Why did Higher-Order Components fall out of favor compared to custom hooks?**

HOCs work, but they have compounding problems: (1) each HOC adds a wrapper component visible in DevTools, making traces confusing; (2) multiple HOCs that inject the same prop name silently overwrite each other; (3) TypeScript types require mechanical `Omit<P, 'injectedProp'>` boilerplate; (4) refs require explicit `forwardRef` forwarding. Custom hooks achieve the same logic reuse as simple functions whose return values are named by the caller — no wrapper component, no prop collision, no ref forwarding needed, clean TypeScript types. The only remaining valid use case for HOCs is wrapping Error Boundaries, which must be class components.

---

**What is the difference between a controlled and uncontrolled component, and why does React Hook Form use uncontrolled inputs by default?**

A controlled input has its value in React state — `value={value} onChange={setValue}`. Every keystroke triggers a re-render. An uncontrolled input manages its own value in the DOM — `defaultValue` sets the initial value, and you read the current value via a ref or `FormData` on submit. React Hook Form uses uncontrolled inputs to avoid re-rendering on every keystroke — for a form with 20 fields, a controlled approach could trigger 20 re-renders per keystroke chain. React Hook Form registers inputs with a ref and only triggers re-renders for validation state changes and explicit form-level updates, not for individual character inputs.
