# Fiber and Reconciliation

## The problem Fiber was built to solve

Before React 16, React used a **stack reconciler** — a single recursive function that walked the entire component tree synchronously. Once started, it could not be interrupted.

```txt
STACK RECONCILER (React < 16)

  reconcile(rootComponent)
    → reconcile(Header)
    → reconcile(Nav)
    → reconcile(Main)
        → reconcile(Sidebar)
        → reconcile(Content)
            → reconcile(ArticleList)
                → reconcile(Article) × 50  ← this loop cannot be paused
    → reconcile(Footer)

  Total wall time: however long it takes to walk the whole tree.
  During this time: the main thread is blocked.
  Browser cannot: handle user input, run animations, paint frames.
  Result: jank on trees with many components or slow renders.
```

The fundamental constraint: JavaScript is single-threaded. A recursive call stack cannot be paused — you have to let it run to completion. If reconciling a large tree took 150 ms, the UI froze for 150 ms.

Fiber rewrites the reconciler from a recursive algorithm into an **iterative one using an explicit work queue**, so React can pause, resume, and prioritize work.

---

## What a Fiber node is

A Fiber is a JavaScript object that represents a unit of work — one component instance, one DOM element, one text node. The entire component tree is mirrored as a tree of Fiber nodes.

```ts
// Simplified — the real FiberNode has ~25 fields
type Fiber = {
  // Identity
  tag: number;           // FunctionComponent=0, ClassComponent=1, HostComponent=5...
  type: Function | string; // the component function, or 'div', 'span', etc.
  key: string | null;

  // Tree structure — Fiber uses a linked structure, not an array
  return: Fiber | null;  // parent
  child: Fiber | null;   // first child
  sibling: Fiber | null; // next sibling

  // State
  memoizedState: any;    // the hook linked list (useState, useEffect, ...)
  memoizedProps: any;    // props from the last render

  // Work
  pendingProps: any;     // props for the upcoming render
  flags: number;         // bitmask: Placement | Update | Deletion | ...
  lanes: Lanes;          // priority of pending work (see below)

  // Double buffering
  alternate: Fiber | null; // the "other" version of this fiber (current ↔ work-in-progress)
};
```

### The tree is actually a linked structure

React doesn't traverse a tree array — it follows pointers: `child` to go deeper, `sibling` to go right, `return` to go up. This allows the traversal to be interrupted at any Fiber node and resumed later without needing to hold the call stack open.

```txt
App
├── child → Header
│             ├── sibling → Nav
│             │               └── sibling → Main
│                                             ├── child → Sidebar
│                                             │             └── sibling → Content
│                                             └── ...
│
(each node also has a return pointer back to its parent)
```

---

## Double buffering — current and work-in-progress trees

At any moment React maintains two trees:

```txt
CURRENT TREE                    WORK-IN-PROGRESS TREE
(what's on screen)              (being computed in the render phase)

  App ──────────────── alternate ──── App'
  │                                   │
  Header ───────────── alternate ──── Header'
  │                                   │
  Main ─────────────── alternate ──── Main'
```

During the render phase, React builds the work-in-progress tree by cloning and updating Fiber nodes. The current tree is untouched — the browser is still showing it. When the render phase completes, React **atomically switches** the work-in-progress tree to become the new current tree. The old current tree becomes the new work-in-progress pool (its nodes are reused for the next render).

This is why the render phase is safe to interrupt and restart: the current tree (what the user sees) is never mutated during reconciliation. Only the work-in-progress tree is modified.

---

## Lanes — the priority system

React 18 introduced **Lanes** — a bitmask system that assigns a priority to every unit of work. Multiple updates can be scheduled with different priorities and processed in priority order.

```ts
// Simplified lane values (actual values are bitmasks)
const SyncLane            = 0b0000000000000000000000000000001; // highest: user input
const InputContinuousLane = 0b0000000000000000000000000000100; // drag, scroll
const DefaultLane         = 0b0000000000000000000000000010000; // normal setState
const TransitionLane      = 0b0000000000000000001000000000000; // useTransition
const IdleLane            = 0b0100000000000000000000000000000; // lowest: background work
```

```txt
PRIORITY ORDER (highest → lowest):
  SyncLane          ← onClick, onKeyDown (user must see result immediately)
  InputContinuousLane ← onMouseMove, onScroll (must be responsive)
  DefaultLane       ← normal setState in event handlers
  TransitionLane    ← startTransition (can be interrupted)
  IdleLane          ← background prefetching, non-visible work
```

When two updates are pending, React processes the higher-priority one first. If a low-priority render is in progress (e.g., a transition) and a high-priority update arrives (e.g., a keypress), React **interrupts** the transition render, processes the keypress synchronously, then resumes the transition from where it left off (or restarts it if the keypress changed the inputs).

```tsx
// Without startTransition:
setQuery(input);        // DefaultLane — search results update in same batch as typing
                        // Large result list blocks the input field

// With startTransition:
startTransition(() => {
  setQuery(input);      // TransitionLane — can be interrupted by new keypresses
});
setInputValue(input);   // DefaultLane — input field updates immediately
```

---

## The reconciliation algorithm — diffing rules

When the render phase produces a new tree of React elements, React compares it against the existing Fiber tree to determine what changed. This diff has explicit heuristics (not a general-purpose tree diff, which would be O(n³)):

### Rule 1: elements of different types produce different trees

```tsx
// Before:
<div><Counter /></div>

// After:
<span><Counter /></span>

// div → span: different type → React unmounts the entire div subtree
// (including Counter and all its state), then mounts a fresh span subtree.
// Counter's state is LOST.
```

This is why changing a wrapper element type destroys child state — even if the children look identical.

### Rule 2: same type → update in place

```tsx
// Before:
<input type="text" className="old" value="hello" />

// After:
<input type="text" className="new" value="world" />

// Same type (input) → React updates only the changed attributes
// in place on the existing DOM node. The DOM node is reused.
```

For component types: same function/class → React re-renders the existing component instance, preserving its state.

### Rule 3: keys control identity across lists

Without keys, React matches list items by **position**:

```tsx
// Before: ['Alice', 'Bob', 'Charlie']
<li>Alice</li>   // position 0
<li>Bob</li>     // position 1
<li>Charlie</li> // position 2

// After: ['Dave', 'Alice', 'Bob', 'Charlie'] (Dave prepended)
<li>Dave</li>    // position 0 ← React thinks this is still the "Alice" node → updates text
<li>Alice</li>   // position 1 ← React thinks this is still "Bob" → updates text
<li>Bob</li>     // position 2 ← still "Charlie" → updates text
<li>Charlie</li> // position 3 ← new node → mounts
```

Result: 3 DOM updates + 1 mount, when 1 mount would have been sufficient. Worse: if items have state (checkboxes, inputs), that state follows the position, not the data.

With keys, React matches by **identity**:

```tsx
<li key="alice">Alice</li>
<li key="bob">Bob</li>
<li key="charlie">Charlie</li>

// After: Dave prepended
<li key="dave">Dave</li>    // new key → mount
<li key="alice">Alice</li>  // same key → reuse existing DOM node, no update needed
<li key="bob">Bob</li>      // same key → reuse
<li key="charlie">Charlie</li> // same key → reuse
```

Result: 1 mount, 0 updates — optimal.

---

## Why index-as-key breaks things

Using the array index as key (`key={index}`) is equivalent to using no key at all for the diff algorithm — the position *is* the identity. The problems emerge when the list order changes (sort, filter, prepend):

```tsx
// Items: [{ id: 1, text: 'Buy milk' }, { id: 2, text: 'Buy eggs' }]
<li key={0}><input defaultValue="Buy milk" /></li>   // index 0
<li key={1}><input defaultValue="Buy eggs" /></li>   // index 1

// After removing item 1:
// Items: [{ id: 2, text: 'Buy eggs' }]
<li key={0}><input defaultValue="Buy eggs" /></li>   // index 0

// React sees: key=0 exists before and after → SAME component → update in place.
// But the input's DOM value is "Buy milk" (the user may have typed something).
// React only updates the `defaultValue` attribute (uncontrolled input),
// so the input still shows "Buy milk" even though it should show "Buy eggs".
// The key identity was wrong — the wrong DOM node was reused.
```

**Safe uses of index as key:**
- The list is static (never reordered, filtered, or prepended)
- Items have no local state (no inputs, no checkboxes, no animations)
- The list is purely a display list and items are never removed from the middle

If any of these conditions don't hold, use a stable unique ID from the data.

---

## The key prop as an intentional reset mechanism

Understanding that keys control component identity reveals a powerful pattern: use a key to force a component to remount from scratch.

```tsx
// Problem: EditForm caches draft state. When userId changes,
// we want a fresh form — not the old draft.

// ❌ Requires manual useEffect to reset:
function EditForm({ userId }: { userId: string }) {
  const [draft, setDraft] = useState('');
  useEffect(() => {
    setDraft(''); // reset when userId changes
  }, [userId]);
  return <input value={draft} onChange={e => setDraft(e.target.value)} />;
}

// ✅ key tells React this is a different component instance:
function Page({ userId }: { userId: string }) {
  return <EditForm key={userId} userId={userId} />;
  // When userId changes, React unmounts the old EditForm and mounts a new one.
  // State is automatically fresh — no useEffect needed.
}
```

This is idiomatic React — using the reconciler's own rules to express intent clearly.

---

## Time slicing — what it means in practice

Time slicing is the ability to **split the render phase into small chunks** and yield control back to the browser between chunks, so the browser can handle input events and paint frames.

```txt
WITHOUT TIME SLICING (synchronous rendering):
  ─────────────────────────────────────────────────────────────────▶ time
  [     long render (100ms)     ][paint][input handler][paint]
        ↑ browser is blocked for 100ms during this render

WITH TIME SLICING (concurrent rendering):
  ─────────────────────────────────────────────────────────────────▶ time
  [5ms render][input][5ms render][paint][5ms render][5ms render][paint]
               ↑ browser gets to handle input every ~5ms
```

React uses a scheduler that checks how much time has elapsed after processing each Fiber node. If the frame budget (~5 ms) is exhausted, React yields to the browser and resumes the render in the next scheduler task.

Time slicing only applies to **interruptible renders** — updates scheduled via `startTransition` or with `TransitionLane`. Synchronous updates (user input, `flushSync`) are never interrupted.

The result for users: a large, slow list rendering in the background no longer freezes the input field. The search box stays responsive because React interrupts the list render whenever a new keypress arrives.

---

## Commit phase — effects ordering

After the render phase completes the work-in-progress tree, the commit phase runs in three sub-phases, always synchronously:

```txt
BEFORE MUTATION
  → getSnapshotBeforeUpdate (class components only)
  → Read from DOM before mutations (e.g., scroll position)

MUTATION
  → Apply all DOM insertions, updates, deletions
  → ref.current is set to null for deleted nodes

LAYOUT
  → useLayoutEffect cleanups (from previous render)
  → useLayoutEffect setups (from this render)
  → ref.current is set to the new DOM node
  → setState calls here are synchronous (batched into this commit)

[Browser paints here]

PASSIVE (scheduled asynchronously, after paint)
  → useEffect cleanups (from previous render)
  → useEffect setups (from this render)
```

The distinction matters: code in `useLayoutEffect` runs before the browser paints — it can read layout, and if it calls `setState`, the resulting re-render is flushed synchronously before paint (no flicker). Code in `useEffect` runs after paint — it cannot synchronously prevent visual updates but also doesn't block the user from seeing the screen.

---

## Common interview traps

**"What is the virtual DOM and how does it relate to Fiber?"**
"Virtual DOM" is an informal term for the element tree that React's reconciler maintains. Fiber is the internal data structure React uses to implement the reconciler. Each Fiber node represents one component/element. The Fiber tree IS what people loosely call the "virtual DOM." The term "virtual DOM" predates Fiber and was accurate for the stack reconciler era — today "Fiber tree" is more precise.

**"What does React do when setState is called inside useLayoutEffect?"**
`useLayoutEffect` runs synchronously in the layout sub-phase of commit. If `setState` is called inside it, React schedules an additional synchronous render and flushes it before the browser paints. This is why tooltip repositioning with `useLayoutEffect` has no visible flicker — the DOM is updated twice in a single frame.

**"Why does removing a key cause components to remount?"**
Keys control Fiber identity. If a key is present in one render and absent in the next (or vice versa), React treats them as different elements at that position. The old Fiber (with its associated DOM node and component state) is unmounted and a new one is mounted. Keys must be stable and unique within their sibling list for the entire lifetime of the list.

**"Can you have duplicate keys in a list?"**
Technically React won't crash, but behavior is undefined — React will arbitrarily pick one of the duplicates and discard the other. Duplicate keys in the same sibling list are a bug. The ESLint rule `react/jsx-key` catches missing keys but not duplicate ones — you need `react/no-duplicate-key` for that.

**"What is a Fiber lane? How is it different from priority?"**
A lane is a bit in a 32-bit integer bitmask. Multiple updates can be in different lanes simultaneously, and React can batch, split, or interleave them. Before lanes (React < 18), React used a simple integer priority and could only track one pending priority level at a time — if two updates were pending with different priorities, the higher one would supersede the lower, potentially starving low-priority work. Lanes allow React to track many concurrent updates and guarantee that low-priority work eventually completes (starvation prevention).
