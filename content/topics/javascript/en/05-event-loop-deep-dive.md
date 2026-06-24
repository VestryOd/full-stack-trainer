# Event Loop: A Deep Dive

## Three components you need to understand first

Before examining the algorithm, you need a clear mental model of three things that are constantly interacting.

### Call Stack

A LIFO stack of execution frames. Each function call pushes a frame onto the top; returning from a function pops it. **Run-to-completion**: the engine cannot interrupt a running JS function — the Event Loop only gets control when the stack is **completely empty**.

```js
function a() { b(); }
function b() { c(); }
function c() { console.log('c'); }

a();
// The stack at the point of console.log:
// [c] ← top
// [b]
// [a]
// [global]
```

### Task Queue / Macrotask Queue

A FIFO queue. Sources of tasks:
- `setTimeout` / `setInterval` (when the delay expires)
- User events (click, input)
- I/O callbacks (network, file — in Node.js)
- `postMessage` / `MessageChannel`
- `setImmediate` (Node.js only)

**"Macrotask" is not an HTML spec term** (the spec just says "task"), but the word has settled in the community to distinguish tasks from microtasks.

### Microtask Queue

A separate queue with higher priority. Sources:
- `Promise.then` / `.catch` / `.finally` (always, even if the Promise is already resolved)
- `queueMicrotask(fn)`
- `MutationObserver` (browser)
- `process.nextTick` (Node.js — special case, see below)

## The full Event Loop algorithm

### Browser Event Loop (HTML spec)

```txt
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   1. Pick ONE task from the Task Queue (if any)            │
│      ↓                                                      │
│   2. Execute the task (run-to-completion)                   │
│      ↓                                                      │
│   3. Drain ALL microtasks from the Microtask Queue         │
│      (including ones added during processing)               │
│      ↓                                                      │
│   4. [Rendering opportunity] — if needed:                   │
│      requestAnimationFrame → style → layout → paint         │
│      ↓                                                      │
│   5. → go back to step 1                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**The critical point of step 3**: The Microtask Queue is drained **completely** — not just one microtask, but every last one. If a microtask adds a new microtask, that one also runs before the next task. An infinite loop of microtasks will block the Event Loop forever.

```js
// ❌ Infinite microtask loop — page will freeze
function infinite() {
  Promise.resolve().then(infinite);
}
infinite();
```

### Why `Promise.then` always queues a microtask

Even if a Promise is already in the `fulfilled` state, `.then(cb)` **does not call `cb` synchronously**. The spec requires: a Promise reaction is always placed into the Microtask Queue, never executed immediately. This guarantees predictable ordering — code after `.then()` always runs before the callback.

```js
const p = Promise.resolve(42); // already resolved

p.then(v => console.log('then:', v));
console.log('sync');

// Output:
// 'sync'      ← synchronous code
// 'then: 42'  ← microtask, executed after the stack empties
```

## Execution order: working through concrete examples

### Example 1: the baseline

```js
console.log('1');

setTimeout(() => console.log('2'), 0);

Promise.resolve()
  .then(() => console.log('3'))
  .then(() => console.log('4'));

console.log('5');
```

<details>
<summary>Step-by-step breakdown</summary>

```txt
Synchronous code (one task: "script"):
  console.log('1')  → output: 1
  setTimeout(...)   → Task Queue: [t1]
  Promise.resolve().then('3') → Microtask: [m3]
  console.log('5')  → output: 5

Stack empty → drain Microtask Queue:
  Microtask m3:
    console.log('3') → output: 3
    .then('4')        → Microtask: [m4]
  Microtask m4:
    console.log('4') → output: 4
  Microtask Queue empty

Next Event Loop iteration — pick from Task Queue:
  setTimeout callback:
    console.log('2') → output: 2

Result: 1, 5, 3, 4, 2
```

</details>

### Example 2: nested microtasks

```js
// Predict the output:
Promise.resolve()
  .then(() => {
    console.log('A');
    Promise.resolve().then(() => console.log('B'));
  })
  .then(() => console.log('C'));

Promise.resolve().then(() => console.log('D'));
```

<details>
<summary>Step-by-step breakdown</summary>

```txt
Synchronous code:
  .then('A + inner B')   → Microtask Queue: [mA]
  .then('D')             → Microtask Queue: [mA, mD]
  (the second .then('C') is registered on the first Promise,
   but waits for mA to resolve)

Drain Microtask Queue:

Iteration 1 — mA:
  console.log('A')            → output: A
  Promise.resolve().then('B') → enqueues mB
  mA completes → first Promise resolves → enqueues mC
  Microtask Queue: [mD, mB, mC]

Iteration 2 — mD:
  console.log('D')            → output: D
  Microtask Queue: [mB, mC]

Iteration 3 — mB:
  console.log('B')            → output: B
  Microtask Queue: [mC]

Iteration 4 — mC:
  console.log('C')            → output: C

Result: A, D, B, C
```

The key trap: `mC` is enqueued only **after** `mA` completes (because `mC` is a `.then` on the promise that resolves when `mA` completes). By that point, `mD` and `mB` are already in the queue.

</details>

### Example 3: mixed — setTimeout + Promise + async/await

```js
// Predict the output:
async function asyncFn() {
  console.log('async start');
  await Promise.resolve();
  console.log('after await');
}

console.log('1');
setTimeout(() => console.log('timeout'), 0);
asyncFn();
console.log('2');
```

<details>
<summary>Step-by-step breakdown</summary>

```txt
Synchronous code:
  console.log('1')          → output: 1
  setTimeout(...)            → Task Queue: [timeout]
  asyncFn():
    console.log('async start') → output: async start
    await Promise.resolve()
    → await desugars to .then()
    → everything after await is queued as a microtask
    → asyncFn suspends, control returns to the caller
  console.log('2')          → output: 2

Stack empty → Microtask Queue: ['after await']

  'after await':
    console.log('after await') → output: after await

Next Event Loop iteration:
  Task Queue: [timeout]
  console.log('timeout')   → output: timeout

Result: 1, async start, 2, after await, timeout
```

`async/await` is syntactic sugar over Promises, so the "continuation after await" always lands in the Microtask Queue, not the Task Queue.

</details>

### Example 4: composite — for a senior interview

```js
// Predict the output:
console.log('start');

setTimeout(() => {
  console.log('timeout 1');
  Promise.resolve().then(() => console.log('promise inside timeout'));
}, 0);

setTimeout(() => console.log('timeout 2'), 0);

new Promise((resolve) => {
  console.log('promise executor');
  resolve();
}).then(() => {
  console.log('then 1');
  return Promise.resolve();
}).then(() => console.log('then 2'));

Promise.resolve().then(() => console.log('then 3'));

console.log('end');
```

<details>
<summary>Step-by-step breakdown</summary>

```txt
Synchronous code:
  'start'                → output: start
  setTimeout 1           → Task Queue: [t1]
  setTimeout 2           → Task Queue: [t1, t2]
  new Promise(executor):
    'promise executor'   → output: promise executor (executor is synchronous!)
    resolve()            → Promise resolved
  .then('then 1')        → Microtask: [m1]
  .then('then 3')        → Microtask: [m1, m3]
  'end'                  → output: end

Drain Microtask Queue:
  m1 ('then 1'):
    'then 1'             → output: then 1
    return Promise.resolve() → second .then('then 2') waits on this promise
                          → adds m2 to the queue
    Microtask: [m3, m2]

  m3 ('then 3'):
    'then 3'             → output: then 3
    Microtask: [m2]

  m2 ('then 2'):
    'then 2'             → output: then 2
    Microtask: []

Task Queue: [t1, t2]
  t1 ('timeout 1'):
    'timeout 1'          → output: timeout 1
    Promise.resolve().then(...) → Microtask: [mp]
  Drain Microtask Queue:
    mp: 'promise inside timeout' → output: promise inside timeout
  t2 ('timeout 2'):
    'timeout 2'          → output: timeout 2

Result: start, promise executor, end, then 1, then 3, then 2,
        timeout 1, promise inside timeout, timeout 2
```

</details>

## Node.js: `process.nextTick` vs `queueMicrotask` vs `Promise.then`

In Node.js, the Microtask Queue has two priority levels:

```txt
Node.js order after each task (and between event loop phases):

  1. nextTick Queue    ← process.nextTick()
     (drained completely)
  2. Microtask Queue  ← Promise.then(), queueMicrotask()
     (drained completely)
  3. Next event loop phase / next task
```

```js
// Node.js only:
Promise.resolve().then(() => console.log('promise'));
process.nextTick(() => console.log('nextTick'));
queueMicrotask(() => console.log('queueMicrotask'));
console.log('sync');

// Output:
// sync
// nextTick        ← nextTick Queue first
// promise         ← Promise microtask
// queueMicrotask  ← queueMicrotask (same queue as Promise, FIFO)
```

**Why does `process.nextTick` have the highest priority?** It predates Promises and was designed with the semantics "run before the next event loop iteration." Its priority over Promises is an API legacy, not a deliberate design choice. In modern code, `process.nextTick` should only be used when you specifically need that "before all Promises" semantic.

**Recursive `process.nextTick` — a dangerous trap:**

```js
// ❌ Will block the event loop in Node.js: the nextTick Queue is drained
// to empty before Promise microtasks — if nextTick adds another nextTick,
// the loop never ends
function blockNode() {
  process.nextTick(blockNode);
}
blockNode();
```

## Rendering and the Event Loop in the browser

Rendering (layout, paint) happens **between tasks**, not between microtasks. Microtasks are part of the same "task" from the rendering pipeline's perspective.

```js
// This will NOT produce an intermediate visual effect:
button.addEventListener('click', () => {
  element.style.color = 'red';
  Promise.resolve().then(() => {
    element.style.color = 'blue';
  });
  // The user only sees 'blue' — the render happens
  // after the entire Microtask Queue is drained
});
```

`requestAnimationFrame` fires **at the end of a task, before the render** — ideal for animations, but doesn't guarantee millisecond-precise timing.

```txt
Task → Microtask Queue (fully drained) → rAF → Render → next task
```

## `queueMicrotask` vs `Promise.resolve().then`

Functionally equivalent (both add to the Microtask Queue). The differences:
- `Promise.resolve().then(fn)` — allocates a Promise object (extra allocation)
- `queueMicrotask(fn)` — directly into the queue, no Promise, no ability to pass a value or catch errors

```js
// Preferred when you only need a microtask without Promise semantics:
queueMicrotask(() => {
  // runs as a microtask, without creating an unnecessary Promise object
});
```

## Connection to other topics

```txt
[Asynchronous Patterns]  — Promise internals, async/await as sugar over
                            microtasks are covered in the next article
[Node.js Event Loop]     — libuv phases (timers, poll, check, close) in depth
                            in the Node.js topic; this article covers JS-level only
[Generators]             — async generator + for-await-of works through
                            the same Microtask Queue under the hood
[Performance]            — long synchronous tasks block the Event Loop;
                            monitor via PerformanceObserver / monitorEventLoopDelay
```

## Common interview traps

- **"Microtasks run between macrotasks"** — an oversimplification that doesn't explain the key point: the Microtask Queue is drained **completely** after each task (and at any microtask checkpoint). New microtasks added during processing also run before the next task.

- **"Promise.then runs when the Promise is resolved"** — a Promise may be resolved, but the callback only executes when the stack empties and the Event Loop reaches the Microtask Queue. Synchronous code after `.then()` always runs first.

- **"setTimeout(fn, 0) is immediate"** — no. First, the minimum delay in browsers is typically 1–4 ms (4 ms after several nested setTimeouts). Second, the task enters the queue and only executes after all current tasks and all accumulated microtasks.

- **"queueMicrotask and Promise.resolve().then are the same thing"** — functionally close, but `queueMicrotask` doesn't create a Promise object and has no `.catch` semantics. An error thrown inside `queueMicrotask` is not catchable via `.catch`.

- **Not knowing the `process.nextTick` vs Promise order in Node.js** — the nextTick Queue is processed before the Microtask Queue. This isn't an "implementation detail" — it's documented behavior that matters for understanding sequencing in Node.js applications.

- **"Rendering happens between microtasks"** — no. From the rendering pipeline's perspective, a task and all its microtasks form one atomic block. Rendering (if needed) only happens after the Microtask Queue is fully drained.
