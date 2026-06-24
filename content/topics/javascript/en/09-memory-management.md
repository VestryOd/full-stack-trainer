# Memory Management

## The JS memory lifecycle

Regardless of language, memory goes through three stages:

```txt
1. Allocation  — the engine allocates memory when a value is created
2. Use         — reading and writing data
3. Release     — GC reclaims memory when the object is unreachable
```

In JS, allocation and use happen explicitly (you write `{}`, `[]`, `new`), while release is **automatic via the garbage collector**. A memory leak occurs when an object the program no longer needs remains **reachable** from the GC's perspective — the program is accidentally holding a reference to it.

## How V8's GC works — the conceptual level

### The generational hypothesis

V8 uses a **generational garbage collector** based on the observation: **most objects die young**. Temporary objects (intermediate computations, short-lived values) live very briefly. Long-lived objects (DOM, caches, singletons) are rare.

This allows splitting the heap into two generations and applying different strategies:

```txt
V8 Heap
├── Young Generation (~1–8 MB)
│   ├── Nursery — new allocations land here
│   └── Intermediate — survived one Minor GC
└── Old Generation (hundreds of MB)
    ├── Old Space — survived multiple Minor GCs
    ├── Code Space — compiled code
    └── Large Object Space — objects above a threshold (never moved)
```

### Minor GC (Scavenge) — fast, frequent

Operates only on the Young Generation. Uses **Cheney's copying algorithm**:

```txt
1. Split Young Generation into two semi-spaces (From, To)
2. Allocate new objects in the From space
3. When From is full — run Minor GC:
   a. From GC roots, traverse the object graph in From space
   b. Copy live objects into To space (compactly)
   c. Objects that survived 2 Minor GCs → promote to Old Generation
   d. The From space is treated as entirely free (no "cleaning" needed —
      just swap the roles)
4. Swap From and To
```

**Why this is fast**: there's no need to walk the entire Old Generation. Objects that die young are simply not copied — their memory is reclaimed automatically when the roles swap.

### Major GC (Mark-Sweep-Compact) — slow, infrequent

Triggered when Old Generation approaches its threshold. Three phases:

```txt
Phase 1: Marking
  Starting from GC Roots, traverse the object graph and mark all reachable objects.
  GC Roots:
    - Global variables (window, globalThis)
    - The call stack (local variables of active functions)
    - Live closures (Environment Records referenced by live functions)
    - V8 internal references

Phase 2: Sweeping
  Walk the heap. Unmarked objects are unreachable → their memory is returned to the pool.

Phase 3: Compaction — optional
  Move live objects together → eliminate fragmentation.
  Expensive: all references to moved objects must be updated.
```

### Incremental and concurrent marking (Orinoco)

Marking the entire Old Generation causes a stop-the-world pause on the main thread. V8 uses several techniques to reduce pauses:

```txt
Incremental marking  — marking done in small slices between JS tasks
Concurrent marking   — marking runs on background threads in parallel with JS
Lazy sweeping        — dead objects are reclaimed gradually
```

In production Node.js applications, GC pause spikes show up as latency spikes. The `--trace-gc` flag logs pause information.

## What causes memory leaks in JS

A leak = an object is **logically** unreachable (the program no longer uses it) but **reachable for the GC** (a live reference exists). The GC can't read developer intent — only the reference graph.

### 1. Detached DOM nodes

```js
// ❌ Classic leak:
let detachedTree;

function createTree() {
  const root = document.createElement('div');
  for (let i = 0; i < 100; i++) {
    root.appendChild(document.createElement('span'));
  }
  detachedTree = root; // global reference keeps the entire tree alive
}

createTree();
document.body.appendChild(detachedTree);
document.body.removeChild(detachedTree);
// Nodes are removed from the DOM, but detachedTree is still alive → 101 elements in memory
detachedTree = null; // ✅ explicitly break the reference
```

A typical pattern: event listeners created on DOM elements and stored in closures keep elements in memory after removal:

```js
function setupButton() {
  const button = document.getElementById('btn');
  const cache = new Array(100_000).fill('data');

  button.addEventListener('click', () => {
    console.log(cache.length); // closes over cache
  });

  // Somewhere later:
  button.remove(); // removed from DOM
  // But the listener with cache is still alive if button is referenced elsewhere
  // or the listener wasn't removed via removeEventListener
}
```

**Fix**: `removeEventListener` when removing elements, or use `AbortController`:

```js
const controller = new AbortController();
button.addEventListener('click', handler, { signal: controller.signal });

// On teardown:
controller.abort(); // automatically removes all listeners with this signal
```

### 2. Forgotten timers and intervals

```js
class DataPoller {
  constructor() {
    this.data = new Array(50_000).fill('payload');
    // ❌ setInterval keeps the callback alive, the callback closes over this,
    //    this keeps data alive — the entire graph lives as long as the timer does
    this.interval = setInterval(() => {
      this.refresh();
    }, 1000);
  }

  refresh() { /* ... */ }

  destroy() {
    clearInterval(this.interval); // ✅ required on teardown
    this.data = null;
  }
}

// Especially dangerous in React components:
useEffect(() => {
  const interval = setInterval(tick, 1000);
  return () => clearInterval(interval); // cleanup function — required
}, []);
```

### 3. Unbounded Map/Set accumulation

```js
// ❌ Unlimited cache — leak proportional to unique arguments
const cache = new Map();

function memoize(key, fn) {
  if (!cache.has(key)) {
    cache.set(key, fn(key));
  }
  return cache.get(key);
}

// If keys are objects (e.g., request objects) and always new —
// Map holds all of them indefinitely
```

### 4. Closures holding large scopes

Covered in detail in [Closures: The Mechanics]. Key point: multiple closures over the same ER in V8 create a shared Context object that retains all variables used by at least one of them.

```js
function problem() {
  const huge = new Array(1_000_000).fill(0); // ~8 MB
  const small = 'ok';

  const a = () => huge;  // uses huge
  const b = () => small; // uses only small, but...
  // a and b are created in the same scope → shared Context → huge retained while b is alive
  return b; // only returning b — but huge won't be collected
}
```

## WeakMap, WeakSet, WeakRef — what problem each solves

### The problem with regular Map/Set

`Map` holds **strong references** to both keys and values. Caching data associated with DOM nodes or request objects prevents their GC:

```js
const nodeData = new Map();

function process(domNode) {
  nodeData.set(domNode, computeExpensiveMetadata(domNode));
}

// After removing domNode from the DOM:
document.body.removeChild(domNode);
// domNode is still alive! Map holds a strong reference to it as a key
// nodeData.delete(domNode) — requires explicit cleanup, easy to forget
```

### WeakMap — weak keys

`WeakMap` holds keys **weakly** — if there are no other references to the key object, the GC can collect it and automatically removes the entry from the WeakMap.

```txt
WeakMap:
  ✅ Keys must be objects (not primitives)
  ✅ Keys are held weakly (don't prevent GC)
  ✅ Automatic cleanup when a key is collected by GC
  ❌ Not iterable (.forEach, .keys(), .values() don't exist)
  ❌ No .size property
  ❌ Values are held strongly (while the key is alive)
```

```js
// ✅ Metadata cache for DOM nodes — doesn't prevent GC
const metadata = new WeakMap();

function attachMetadata(node, data) {
  metadata.set(node, data);
}

function getMetadata(node) {
  return metadata.get(node);
}

// When node is removed from the DOM and no other references exist —
// GC collects the node + WeakMap automatically removes the entry
// No manual cleanup required
```

**Private class data via WeakMap** (the pattern before `#` private fields):

```js
const _private = new WeakMap();

class SecureAccount {
  constructor(balance) {
    _private.set(this, { balance, transactions: [] });
  }

  deposit(amount) {
    const data = _private.get(this);
    data.balance += amount;
    data.transactions.push({ type: 'deposit', amount });
  }

  get balance() {
    return _private.get(this).balance;
  }
}

const acc = new SecureAccount(100);
acc.deposit(50);
acc.balance; // 150
// _private.get(acc) — inaccessible from outside the module (WeakMap is closure-private)
// When acc is GC'd — the WeakMap entry is GC'd along with it
```

### WeakSet — weak values

`WeakSet` holds objects weakly. Used to track "visited" objects without preventing their GC:

```js
// Track "processed" requests without keeping them in memory:
const processedRequests = new WeakSet();

function handleRequest(request) {
  if (processedRequests.has(request)) {
    return; // already processed
  }
  processedRequests.add(request);
  // ... process
}

// When request goes out of scope — WeakSet doesn't keep it alive
```

```js
// Guard against cycles in recursive object traversal:
function deepClone(obj, seen = new WeakSet()) {
  if (seen.has(obj)) return '[Circular]';
  if (typeof obj !== 'object' || obj === null) return obj;

  seen.add(obj);
  const clone = Array.isArray(obj) ? [] : {};
  for (const key of Object.keys(obj)) {
    clone[key] = deepClone(obj[key], seen);
  }
  return clone;
}
```

### WeakRef (ES2021) — a weak reference to an object

`WeakRef` lets you store a reference to an object **without preventing its GC**. `.deref()` returns the object or `undefined` (if collected):

```js
// ✅ A cache that "clears itself" when memory is needed:
class Cache {
  #store = new Map();

  set(key, value) {
    this.#store.set(key, new WeakRef(value));
  }

  get(key) {
    const ref = this.#store.get(key);
    if (!ref) return undefined;

    const value = ref.deref();
    if (value === undefined) {
      this.#store.delete(key); // clean up the dead entry
      return undefined;
    }
    return value;
  }
}
```

**Critically important**: the spec does NOT guarantee when or whether an object with a WeakRef will be collected. GC is an implementation detail. You cannot rely on WeakRef for business logic or guarantees. Only use it where losing a value is acceptable behavior (caches, optimizations).

```js
// ❌ Incorrect usage:
const ref = new WeakRef(importantData);
// ... many operations ...
const data = ref.deref();
if (data === undefined) {
  throw new Error('Critical data was GC\'d'); // this is a broken architecture
}
```

### FinalizationRegistry (ES2021) — callback on GC collection

Lets you register a callback that will be called (possibly) when an object is collected:

```js
const registry = new FinalizationRegistry((heldValue) => {
  // heldValue — what you passed at registration (NOT the object itself!)
  console.log(`Object with id ${heldValue} was GC'd`);
  cleanupExternalResource(heldValue);
});

function createTracked(id) {
  const obj = { id, data: new Array(10_000).fill(0) };

  registry.register(
    obj,   // the tracked object (held weakly)
    id,    // heldValue — passed to the callback (must NOT reference obj!)
    obj    // unregister token (optional)
  );

  return obj;
}

// Cancelling the registration:
const obj = createTracked('user-42');
registry.unregister(obj); // cancel the callback for this object
```

**Limitations of `FinalizationRegistry`**:
- The callback is **not guaranteed** — the spec permits GC to never call it
- The callback is invoked **asynchronously**, not at the moment of collection
- You cannot resurrect the object in the callback — no access to the object itself
- Don't use it for critical cleanup logic

## Diagnostic tools

```js
// Node.js: monitoring memory usage
const { heapUsed, heapTotal, external, rss } = process.memoryUsage();

// Check for heap growth under load:
function checkMemoryLeak(fn, iterations = 1000) {
  const before = process.memoryUsage().heapUsed;
  for (let i = 0; i < iterations; i++) fn();

  // Force GC (only with the --expose-gc flag):
  if (global.gc) global.gc();

  const after = process.memoryUsage().heapUsed;
  const delta = after - before;
  console.log(`Memory delta: ${(delta / 1024 / 1024).toFixed(2)} MB`);
  return delta;
}
```

In the browser: Chrome DevTools → Memory → Heap Snapshot. Compare two snapshots (before/after load). Objects remaining in the diff are leak candidates. Searching for "Detached HTMLElement" is a reliable sign of a detached-DOM leak.

## Predict the output — WeakRef + FinalizationRegistry

```js
let obj = { name: 'tracked' };
const ref = new WeakRef(obj);
const registry = new FinalizationRegistry(name => {
  console.log(`Cleaned up: ${name}`);
});

registry.register(obj, obj.name);

console.log(ref.deref()?.name); // ?

obj = null; // remove the strong reference

// Immediately after:
console.log(ref.deref()?.name); // ?

// After GC (indeterminate time later):
// Cleaned up: tracked  ← may or may not be called
```

<details>
<summary>Answer</summary>

```
'tracked'    // deref() returns the object while it's still alive
'tracked'    // the object has NOT been collected yet — GC doesn't guarantee
             // immediate collection after obj = null
             // (GC hasn't necessarily run yet)

// At the time of actual GC collection (indeterminate time later):
// 'Cleaned up: tracked'  — but this is not guaranteed by the spec
```

Key takeaway: `obj = null` makes the object *eligible* for GC but doesn't guarantee immediate collection. `ref.deref()` immediately after `obj = null` can still return the object — the GC hasn't run yet.

</details>

## Connection to other topics

```txt
[Closures]              — closures over a shared ER retain all variables
                           in the scope; the V8 shared Context mechanism
                           is covered in detail in article 03
[Proxy]                 — Proxy strongly retains target; revocable proxy
                           provides a way to explicitly break the reference
                           graph when done
[Generators]            — an unfinished generator retains its entire ER
                           (all local variables) as long as the generator
                           object is alive
[Modern JS]             — AbortController for listeners without manual
                           removeEventListener
```

## Common interview traps

- **"GC runs immediately when an object is no longer needed"** — no. GC runs on a schedule / threshold basis, not deterministically. Assigning `null` makes an object eligible for collection, but collection happens later.

- **"WeakMap/WeakSet are just like Map/Set, but weaker"** — key differences: not iterable, no `.size`, only objects as keys/values. They solve a fundamentally different problem: associating data with an object without keeping the object alive.

- **"WeakRef guarantees the object stays in memory until explicitly removed"** — no. `WeakRef` is a weak reference; GC can collect the object at any time. `deref()` may return `undefined`. It's an "opportunistic" cache.

- **"`FinalizationRegistry` is reliable for resource cleanup"** — no. The callback is not guaranteed. For reliable resource release — use explicit `dispose` / `close` / `destroy` patterns, or `using` (Explicit Resource Management, ES2025).

- **Not knowing that Minor GC (Scavenge) doesn't touch Old Generation** — understanding generational GC matters for explaining why short-lived objects are cheap (fast Minor GC), while long-lived ones are more expensive (Major GC marking the entire graph).

- **"A leak = undefined behavior"** — no. A leak in JS is strictly defined: an object remains reachable through the reference graph even though the program logic no longer accesses it. Understanding GC roots (stack, globals, closures) lets you pinpoint exactly what's keeping an object alive.
