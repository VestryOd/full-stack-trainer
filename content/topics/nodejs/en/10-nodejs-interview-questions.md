# Node.js Interview Questions (Middle → Senior)

## How to use this cheat sheet

Every answer below is a short version of what the rest of this section covers in depth. If a follow-up catches you off guard, that is a signal to revisit the matching article.

In a senior interview none of these questions is the last one. Each one opens a deeper follow-up: "why?", "what if...?", "give a real-world example". That is why each group ends with a **"Typical follow-ups"** section showing where the interviewer usually goes next.

```txt
The six groups:
  1. Runtime, V8, npm                     → questions 1-4
  2. Event Loop, microtasks, nextTick     → questions 5-11
  3. libuv, Thread Pool, Workers, Cluster → questions 12-17
  4. Streams, backpressure, Buffer        → questions 18-22
  5. Memory and garbage collection        → questions 23-29
  6. Modules: CommonJS vs ESM             → questions 30-33
```

## Group 1: Runtime, V8, npm

**1. What is Node.js?**
Node.js is a **runtime**: an execution environment that combines V8 (Google's JavaScript engine) with libuv and a set of built-in APIs. It is not a "programming language" and not a "framework". See [Node.js Fundamentals](./01-nodejs-fundamentals.md).

- V8 runs your JS.
- libuv provides the event loop, the thread pool and async I/O.
- The built-in Node APIs (`fs`, `http`, `crypto`, and so on) are not available in the browser.

**2. How does Node differ from the browser if both use V8?**
The **set of available APIs** differs, while V8 executes the same JS in both cases. The browser provides the DOM (document object model), `window` and `fetch` through its Web APIs. Node provides `fs`, `process` and `net` through libuv. They are two different "hosts" around the same engine.

**3. What does V8 do besides "execute JS"?**
It runs a whole compilation pipeline. On top of that it keeps Hidden Classes and Inline Caches for fast property access, plus a generational GC (garbage collector). See [V8 and Node.js Runtime](./02-v8-and-runtime.md).

```txt
Parser → AST (abstract syntax tree)
       → Ignition   a baseline bytecode interpreter —
                     fast startup
       → TurboFan   the JIT (just-in-time) compiler that
                     optimizes hot code
       → Deopt      possible when object shapes change
```

**4. What's a Hidden Class and why does it matter?**
V8 assigns a hidden class to each object "shape", that is to each set of keys in a specific order. This lets the JIT (just-in-time) compiler generate optimized property-access code at a fixed offset, as in statically typed languages.

Add or remove properties in a different order across objects of the same "logical type", and you get different hidden classes. The Inline Cache then becomes polymorphic, then megamorphic, and the code is deoptimized.

## Typical follow-ups (Group 1)

```txt
"Give an example where adding a property to an object after
the constructor could slow down the code" → Hidden Classes,
adding/deleting properties in inconsistent order

"npm install runs a postinstall script that fetches something
from GitHub — what's the risk?" → supply-chain attacks,
npm audit, lock files
```

## Group 2: Event Loop, Microtasks, process.nextTick

**5. What's the Event Loop in simple terms?**
It is a **mechanism with phases**, not "a task queue". The phases are timers → pending callbacks → idle, prepare → poll → check → close callbacks. On each iteration it picks the ready callbacks and runs them. Between **every** callback it fully drains the `process.nextTick` queue and the microtask queue. See [Event Loop](./03-event-loop.md).

**6. List the Event Loop phases and what happens in each.**
The phases below run in a fixed order. In `poll` the process can block and wait on the readiness mechanism of the operating system (OS). That mechanism is epoll on Linux, kqueue on macOS, IOCP (input/output completion ports) on Windows.

```txt
timers            → ready setTimeout/setInterval callbacks
pending callbacks → some system operations
poll              → the main phase: I/O callbacks; blocks
                     here when there is nothing else to do
check             → setImmediate
close callbacks   → 'close' events
```

**7. How does the microtask queue differ from the macrotask queue, and when does switching happen?**
The microtask queue (`Promise.then`, `queueMicrotask`, async/await) drains **completely** after **any** operation ends. That includes each individual callback inside the poll phase, not just once "after the script".

Macrotasks (timers, `setImmediate`, I/O) wait for the next loop phase. See [Microtasks, Macrotasks, and process.nextTick](./04-microtasks-macrotasks-nexttick.md).

**8. Why does `Promise.then` run before `setTimeout(fn, 0)`?**
Because the microtask queue has priority over **every** Event Loop phase. The Event Loop doesn't move to the next task, timers included, until the microtask queue is completely empty.

**9. What is `process.nextTick` and how does it differ from the microtask queue?**
It is a separate queue with **even higher** priority than the microtask queue. It drains first. Anything added to it **while** it is draining is also processed before microtasks get their turn.

```txt
Priority, highest first:
  1. process.nextTick queue — drained completely
  2. microtask queue        — drained completely
  3. the next Event Loop phase (timers, poll, check, ...)
```

**10. Why can `process.nextTick` be dangerous?**
Recursively calling `process.nextTick` inside itself causes starvation. The Event Loop **never** reaches I/O or timers, so the process stops responding to requests — but it doesn't "crash". A realistic example: processing a message queue recursively via `nextTick` instead of `setImmediate`.

**11. How does `setImmediate` differ from `setTimeout(fn, 0)`?**
At the top level the order is **not** guaranteed: it depends on the timer precision of the operating system. **Inside** an I/O callback, `setImmediate` **always** runs before `setTimeout(fn, 0)`. The `check` phase comes right after `poll`, while `timers` only comes on the next loop iteration.

## Typical follow-ups (Group 2)

```txt
"Given: console.log + nextTick + Promise.then + setTimeout —
work out the order and explain the mechanism, not just the
answer" → explain via queue draining, not memorizing "1 5 2 3 4"

"You use async/await everywhere, but one request slows down
others — why?" → a long chain of awaits means many microtask
ticks, which block moving on to the next macrotasks
(see Microtasks, Macrotasks, and process.nextTick)
```

## Group 3: libuv, Thread Pool, Worker Threads, Cluster

**12. Is Node single-threaded or multi-threaded?**
Both, depending on what you mean. Your JS code runs on **one** thread (V8 plus the Event Loop). But a Node process also has N libuv Thread Pool threads, 4 by default, and M background V8 GC threads. See [libuv and the Thread Pool] and [Memory, Heap, Stack, and Garbage Collection](./08-memory-garbage-collection.md).

**13. Which operations use the Thread Pool, and which don't?**
Only a narrow set of operations does:

```txt
Use the Thread Pool:
  fs.*
  crypto.pbkdf2 / scrypt / randomBytes  (async forms)
  zlib.*                                (async forms)
  dns.lookup                            (via getaddrinfo)

Do not use it:
  net / http / tcp  → epoll, kqueue, IOCP: the native async
                       interfaces of the operating system
  dns.resolve*      → via c-ares, a separate mechanism
```

**14. Why doesn't `fs.readFile` block the Event Loop?**
The underlying `read()` system call **is** blocking. But Node runs it on a **separate** Thread Pool thread, not on the main JS thread. When it completes, the result comes back through the same notification mechanism that network events use.

**15. When are Worker Threads needed, and why not the Thread Pool?**
The Thread Pool does **not** run your JS. It only handles built-in blocking operations of the operating system. So CPU-bound JS code needs a Worker Thread with its own V8 instance.

CPU-bound means the work keeps the central processing unit (CPU) busy instead of waiting for I/O: image processing, custom hashing, parsing large documents. A Worker Thread is the only way to keep such work off the main thread. See [Worker Threads and Cluster](./06-worker-threads-cluster.md).

**16. How do Worker Threads differ from Cluster?**
Several threads in one process, versus several fully independent processes:

```txt
                Worker Threads       Cluster
──────────────────────────────────────────────────────────
Unit            threads inside       fully independent
                 one process          processes
V8/Event Loop   one per thread       one per process
Shared memory   yes, through         none
                 SharedArrayBuffer
One shared      —                    yes, via round-robin
port                                  or SO_REUSEPORT
```

**17. "Cluster is obsolete because of Docker" — agree?**
Not quite. If a container gets 4 virtual cores (4 vCPU) but runs a **single** Node process, the JS event loop still uses only 1 core. Two answers address this: more container replicas, which is preferred in Kubernetes (k8s), or Cluster inside the container. Their trade-offs differ around observability and graceful shutdown.

## Typical follow-ups (Group 3)

```txt
"You have bcrypt.hash + fs.readFile on every request, and
under load latency grows non-linearly — why?" → both
operations share one Thread Pool (4 threads by default) —
contention

"How does a Worker Thread exchange data with the main thread —
is there copying?" → structured clone by default (copy),
Transferable ArrayBuffer (no copy), SharedArrayBuffer + Atomics
(real shared memory)
```

## Group 4: Streams, Backpressure, Buffer

**18. What's a Stream and why is it "better" than readFile?**
The key property is **automatic** synchronization of producer and consumer speed — backpressure — not just "processing in chunks". `readFile` loads the whole file into memory. A stream keeps no more than `highWaterMark` buffered — 64KB by default since Node.js 22, 16KB before. See [Streams and Backpressure](./07-streams-and-backpressure.md).

**19. The 4 stream types and where they're used?**
Four types, split by the direction of the data flow:

```txt
Readable   — a source                (fs.createReadStream)
Writable   — a destination           (fs.createWriteStream)
Duplex     — both directions at once (a TCP socket; TCP is
              the transmission control protocol)
Transform  — Duplex plus a data transformation (gzip,
              parsers)
```

**20. What really happens during backpressure?**
`writeStream.write(chunk)` returns `false` once the internal buffer exceeds `highWaterMark`. The data is still written to the buffer. The `false` is only a signal: "slow down the producer". Ignoring it lets the buffer grow without bound. `.pipe()` reacts to that signal and to the `'drain'` event automatically, with `pause()` and `resume()`.

**21. Why is `pipeline()` better than `.pipe()`?**
On an error in the middle of the chain, `.pipe()` doesn't release resources: the remaining streams and file descriptors stay open. The `pipeline()` helper calls `destroy()` on **every** stream in the chain if any of them errors. It also supports async/await.

**22. What's a Buffer and why doesn't it "count" toward heapUsed?**
`Buffer` is a representation of binary data, stored physically **outside** the regular V8 heap, in "external" memory. So tracking leaks by `heapUsed` alone misses growth from retained Buffers. You also have to look at `rss` (resident set size) and `external`.

## Typical follow-ups (Group 4)

```txt
"Implement a Transform stream that writes to a database and
explain how to preserve backpressure" → callback() in
_transform must be called after awaiting the database write,
otherwise backpressure breaks

"A client disconnects mid-download of a large CSV streamed
from a database — what happens to the query with pipe()
vs pipeline()?" → pipeline() aborts the whole chain,
including cancelling the database query
```

## Group 5: Memory and Garbage Collection

**23. Stack vs Heap — what's the difference?**
Stack holds call frames, primitives and **references**. It is not managed by the GC: memory is freed automatically when the function returns. Heap holds objects, arrays, functions and closures, and it is managed by the GC. Leaks only happen in the heap. See [Memory, Heap, Stack, and Garbage Collection](./08-memory-garbage-collection.md).

**24. How does the GC decide what to delete?**
By reachability from Root Objects: globals, active stack frames, closures. Whatever is not reachable is garbage.

```txt
Mark     → flags every object reachable from a root
Sweep    → frees the objects that were not flagged
Compact  → defragments Old Space by moving live objects
            together
```

**25. What's Generational GC and why is it efficient?**
New Space, the young generation, is cleared by the Scavenge algorithm. Scavenge is a copying collector, and its cost is proportional to the **number of live** objects, not to the amount of garbage. Most objects die quickly, so Scavenge is almost always fast.

Objects that survive 2 cycles are promoted to Old Space, which is cleared by the more expensive Mark-Sweep-Compact.

**26. Does the GC always fully pause the application?**
No longer fully. Modern V8 uses Incremental, Concurrent and Parallel Marking and Compaction on background threads, which cuts pauses drastically. But final synchronization and Sweep still need a brief pause of the main thread. With a large heap that pause is visible at p99 latency — the slowest 1% of requests.

**27. Name 3 classic memory leak patterns in Node.**
All three are bugs in the graph of references, not in the GC:

```txt
1. A global array or cache that is never cleared — it grows
   on a setInterval or on every request.
2. EventEmitter listeners that are never removed. Worst when
   the listener captures a short-lived object (a socket) in
   a closure while the emitter is long-lived.
3. A closure that retains a large object which was only
   needed during initialization.
```

**28. Why doesn't `process.memoryUsage().heapUsed` show the whole leak?**
`heapUsed` covers only the V8 heap. `external` and `arrayBuffers` — the contents of `Buffer` and `TypedArray` — are a separate category. They are not included in `heapUsed`, but they do affect `rss` and the risk of an OOM Kill (OOM — out of memory).

**29. The container OOMs even though V8 "thinks" there's enough memory — why?**
By default V8 sets the Old Space limit from the memory of the **whole machine**, not from the container's cgroup limit. A cgroup is the Linux control group that caps a container's resources. So set `--max-old-space-size` explicitly, and leave headroom for `external` memory, which this flag doesn't bound.

## Typical follow-ups (Group 5)

```txt
"heapUsed is stable but the container's RSS keeps growing —
where do you look?" → external/arrayBuffers (retained
Buffers), not the V8 heap

"When does WeakMap solve a leak problem, and when doesn't it?"
→ solves it for caches tied to an object's lifecycle; doesn't
solve it for caches with a time to live (no notion of lifetime
without external strong references)
```

## Group 6: Modules — CommonJS vs ES Modules

**30. The main difference between CommonJS and ESM isn't just syntax. What else?**
ESM (ES Modules — ES stands for ECMAScript) differs from CommonJS in how a module is loaded and in what an import gives you. In CommonJS, `require()` is a synchronous function call, and an export is a **copy** of the value at call time.

In ESM, loading happens in 3 phases: Construction → Instantiation → Evaluation. An import there is a **live binding** to a "cell" in the source module. See [CommonJS vs ES Modules](./09-commonjs-vs-esm.md).

**31. How does a circular dependency behave in CommonJS vs ESM?**
Both survive it, but the result differs:

```txt
CommonJS → the module gets a partially filled
            module.exports: only what was exported before
            the require() line that caused the cycle

ESM      → functions work better, thanks to hoisting and
            live bindings. But let/const with a computed
            value can be in the temporal dead zone (TDZ)
            when accessed during the cycle
```

**32. Can CommonJS import a pure ESM package directly via `require()`?**
No. `require()` is synchronous, and ESM needs asynchronous loading. The only way is dynamic `import()`, which is asynchronous. The reverse direction works: when ESM imports CommonJS (CJS), `module.exports` becomes `default`.

**33. What's the "dual package hazard"?**
If a library ships both CJS and ESM builds, one part of an app can import it via `require()` and another via `import()`. Node then loads **two** separate modules with **two** instances of internal state. If the library uses a Singleton, the app ends up with two unrelated singletons.

## Typical follow-ups (Group 6)

```txt
"ESM speeds up my Node API server via tree shaking — agree?"
→ no, tree shaking is a bundler optimization for client code;
Node itself doesn't tree-shake at runtime

"Library X uses a module-level Singleton and 'settings aren't
applied' under mixed require/import — what could cause this?"
→ dual package hazard
```

## The most common "wrap-up" senior question

**Why can Node handle thousands of connections concurrently with a single JS thread?**

Weak answer: "Event Loop and non-blocking I/O."

Strong answer breaks this down into specific mechanisms:

- Network operations go through epoll, kqueue or IOCP. **One** thread can watch thousands of file descriptors, with no thread per connection (see [libuv and the Thread Pool]).
- Operations with no async operating-system API — files, some crypto — go to the Thread Pool, a bounded pool of background threads.
- The phased Event Loop guarantees that ready callbacks are processed one at a time. They never block each other for longer than the synchronous portion of each callback (run-to-completion, see [Event Loop](./03-event-loop.md)).
- The limit of the model: if one callback runs synchronously for a **long** time (CPU-bound), **all** other connections wait. So CPU-bound work needs Worker Threads, and using several cores for I/O-bound traffic needs Cluster or multiple replicas.

## Common interview mistakes

- **Memorizing answers without understanding the mechanism** — any variation of the question ("what if you add another await/listener/process?") breaks a memorized answer.

- **Ignoring follow-ups** — every one of the 33 questions above is an entry point into a deeper conversation. Being unprepared for "why?" is the main sign of shallow preparation.

- **Confusing "what uses the Thread Pool" with "what's asynchronous"** — almost everything in Node is asynchronous. The Thread Pool, though, is used only for a narrow set of operations: `fs`, `crypto`, `zlib`, `dns.lookup`.

- **Not connecting topics to each other** — for example, missing the link between Memory/GC and Cluster. Several processes with smaller heaps reduce the impact of GC pauses. Another missed link is Streams and the Event Loop: stream events flow through that same loop.
