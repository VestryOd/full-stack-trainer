# Node.js Interview Questions (Middle → Senior)

## How to use this cheat sheet

Every answer below is a SHORT version of what's covered in depth in the rest of this section. In a senior interview, almost ANY of these questions isn't the final question — it's an OPENER for a deeper follow-up ("why?", "what if...?", "give a real-world example"). That's why each group ends with a **"Typical follow-ups"** section showing where the interviewer usually goes next. If a follow-up catches you off guard, that's a signal to revisit the corresponding article in this section.

## Group 1: Runtime, V8, npm

**1. What is Node.js?**
Not a "programming language" and not a "framework" — it's a RUNTIME: an execution environment combining the V8 engine (runs JS), libuv (event loop, thread pool, async I/O), and a set of built-in Node APIs (`fs`, `http`, `crypto`, etc.) unavailable in the browser. See [Node.js Fundamentals].

**2. How does Node differ from the browser if both use V8?**
In both cases V8 executes the same JS, but the SET OF AVAILABLE APIs differs: the browser provides DOM/`window`/`fetch` (via the engine's Web APIs), Node provides `fs`/`process`/`net` (via libuv). They're two different "hosts" around the same engine.

**3. What does V8 do besides "execute JS"?**
A pipeline: Parser → AST → Ignition (baseline bytecode interpreter, fast startup) → TurboFan (JIT optimization of hot code) → possible Deopt when object shapes change. Plus Hidden Classes/Inline Caches for fast property access, and a Generational GC. See [V8 and the Runtime].

**4. What's a Hidden Class and why does it matter?**
V8 assigns each object "shape" (a set of keys in a specific order) a hidden class — this lets the JIT generate optimized property-access code at a fixed offset, like in statically typed languages. Adding/removing properties on different objects of the same "logical type" in a different order creates different hidden classes → the Inline Cache becomes polymorphic/megamorphic → deoptimization.

## Typical follow-ups (Group 1)

```txt
"Give an example where adding a property to an object AFTER
the constructor could slow down the code" → Hidden Classes,
adding/deleting properties in inconsistent order

"npm install runs a postinstall script that fetches something
from GitHub — what's the risk?" → supply-chain attacks,
npm audit, lock files
```

## Group 2: Event Loop, Microtasks, process.nextTick

**5. What's the Event Loop in simple terms?**
Not "a task queue" — it's a MECHANISM WITH PHASES: timers → pending callbacks → poll → check → close callbacks, which on each iteration picks ready callbacks to run, and between EVERY callback fully drains the `process.nextTick` and microtask queues. See [The Event Loop].

**6. List the Event Loop phases and what happens in each.**
`timers` (ready setTimeout/setInterval) → `pending callbacks` (some system operations) → `poll` (the main phase — I/O callbacks, blocks on epoll/kqueue/IOCP if there's nothing to do) → `check` (setImmediate) → `close callbacks` (`'close'` events).

**7. How does the microtask queue differ from the macrotask queue, and WHEN does switching happen?**
The microtask queue (`Promise.then`, `queueMicrotask`, async/await) drains COMPLETELY after the end of ANY operation — including each individual callback inside the poll phase, not just once "after the script." Macrotasks (timers/setImmediate/I/O) wait for the next loop phase. See [Microtasks, Macrotasks, and process.nextTick].

**8. Why does `Promise.then` run before `setTimeout(fn, 0)`?**
Because the microtask queue has priority over EVERY Event Loop phase — the Event Loop doesn't move to the next task (including timers) until the microtask queue is completely empty.

**9. What is `process.nextTick` and how does it differ from the microtask queue?**
A separate queue with EVEN HIGHER priority than the microtask queue — it drains first, and anything added to it WHILE it's draining is also processed before moving on to microtasks.

**10. Why can `process.nextTick` be dangerous?**
Recursively calling `process.nextTick` inside itself causes starvation — the Event Loop NEVER reaches I/O/timers, the process stops responding to requests but doesn't "crash." A realistic example is recursively processing a message queue via `nextTick` instead of `setImmediate`.

**11. How does `setImmediate` differ from `setTimeout(fn, 0)`?**
At the top level, ordering is NOT guaranteed (depends on OS timer precision). But INSIDE an I/O callback, `setImmediate` ALWAYS runs before `setTimeout(fn, 0)`, because the `check` phase runs right after `poll`, while `timers` only runs on the next loop iteration.

## Typical follow-ups (Group 2)

```txt
"Given: console.log + nextTick + Promise.then + setTimeout —
work out the order and explain the MECHANISM, not just the
answer" → explain via queue draining, not memorizing "1 5 2 3 4"

"You use async/await everywhere, but one request slows down
others — why?" → a long chain of awaits means many microtask
ticks, which block moving on to the next macrotasks
(see [Microtasks, Macrotasks, and process.nextTick])
```

## Group 3: libuv, Thread Pool, Worker Threads, Cluster

**12. Is Node single-threaded or multi-threaded?**
Both — depends what you mean. JS code runs on ONE thread (V8 + Event Loop). But a Node process also has N libuv Thread Pool threads (4 by default) and M background V8 GC threads. See [libuv and the Thread Pool] and [Memory and Garbage Collection].

**13. Which operations use the Thread Pool, and which don't?**
USE it: `fs.*`, `crypto.pbkdf2/scrypt/randomBytes` (async), `zlib.*` (async), `dns.lookup` (via `getaddrinfo`). DON'T use it: `net`/`http`/`tcp` (epoll/kqueue/IOCP — native OS async), `dns.resolve*` (via c-ares, a separate mechanism).

**14. Why doesn't `fs.readFile` block the Event Loop?**
The underlying `read()` syscall IS blocking — but Node runs it on a SEPARATE Thread Pool thread, not the main JS thread. When it completes, the result is delivered back through the same notification mechanism used for network events.

**15. When are Worker Threads needed, and why not the Thread Pool?**
The Thread Pool does NOT run your JS — it only handles built-in blocking OS operations. If you have CPU-bound JS code (image processing, custom hashing, parsing large documents), the only way to avoid blocking the main thread is a Worker Thread with its own V8 instance. See [Worker Threads and Cluster].

**16. How do Worker Threads differ from Cluster?**
Worker Threads are multiple THREADS in ONE process, each with its own V8/Event Loop, able to exchange data via `SharedArrayBuffer`. Cluster is multiple FULLY independent PROCESSES sharing one port via round-robin/SO_REUSEPORT, with no shared memory.

**17. "Cluster is obsolete because of Docker" — agree?**
Not quite. If a container is allocated 4 vCPUs but runs a SINGLE Node process, the JS event loop still only uses 1 core. Either more container replicas (preferred in k8s) or Cluster inside the container both address this, with different trade-offs around observability and graceful shutdown.

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
Not just "processing in chunks" — the key property is AUTOMATIC synchronization of producer and consumer speed (backpressure). `readFile` loads the whole file into memory; a stream keeps no more than `highWaterMark` (64KB by default) buffered. See [Streams and Backpressure].

**19. The 4 stream types and where they're used?**
Readable (a source — `fs.createReadStream`), Writable (a destination — `fs.createWriteStream`), Duplex (both — a TCP socket), Transform (Duplex + data transformation — gzip, parsers).

**20. What REALLY happens during backpressure?**
`writeStream.write(chunk)` returns `false` once the internal buffer exceeds `highWaterMark` — the data is still written to the buffer, but the signal says "slow down the producer." Ignoring this signal lets the buffer grow unbounded. `.pipe()` does `pause()`/`resume()` based on this signal and the `'drain'` event automatically.

**21. Why is `pipeline()` better than `.pipe()`?**
`.pipe()` doesn't release resources on an error MID-CHAIN — the remaining streams/file descriptors stay open. `pipeline()` properly calls `destroy()` on EVERY stream in the chain if any of them errors, and supports async/await.

**22. What's a Buffer and why doesn't it "count" toward heapUsed?**
`Buffer` is a representation of binary data physically stored OUTSIDE the regular V8 heap (in "external" memory). Tracking leaks via `heapUsed` alone will miss growth from retained Buffers — you need to check `rss`/`external`.

## Typical follow-ups (Group 4)

```txt
"Implement a Transform stream that writes to a database and
explain how to preserve backpressure" → callback() in
_transform must be called AFTER awaiting the DB write,
otherwise backpressure breaks

"A client disconnects mid-download of a large CSV streamed
from a database — what happens to the DB query with pipe()
vs pipeline()?" → pipeline() aborts the ENTIRE chain,
including cancelling the DB query
```

## Group 5: Memory and Garbage Collection

**23. Stack vs Heap — what's the difference?**
Stack — call frames, primitives, and REFERENCES (not managed by the GC, freed automatically on function return). Heap — objects/arrays/functions/closures, managed by the GC. Leaks only happen in the heap. See [Memory and Garbage Collection].

**24. How does the GC decide what to delete?**
Reachability from Root Objects (globals, active stack frames, closures) — Mark (flags reachable objects) → Sweep (frees unmarked ones) → Compact (defragments Old Space).

**25. What's Generational GC and why is it efficient?**
New Space (young generation) is cleared by the Scavenge algorithm — a copying GC whose cost is proportional to the NUMBER OF LIVE objects (not garbage). Most objects die quickly → Scavenge is almost always fast. Survivors of 2 cycles get promoted to Old Space, which is cleared more expensively via Mark-Sweep-Compact.

**26. Does the GC always fully pause the application?**
No longer fully — modern V8 uses Incremental/Concurrent/Parallel Marking and Compaction (background threads), drastically reducing pauses. But final synchronization and Sweep still require a brief main-thread pause, noticeable at p99 with a large heap.

**27. Name 3 classic memory leak patterns in Node.**
(1) A global array/cache that's never cleared, growing on a `setInterval`/per request. (2) Unremoved EventEmitter listeners — especially when a listener captures a short-lived object (a socket) in a closure while the emitter is long-lived. (3) A closure retaining a large object that was only needed during initialization.

**28. Why doesn't `process.memoryUsage().heapUsed` show the WHOLE leak?**
`heapUsed` covers only the V8 heap. `external`/`arrayBuffers` (the contents of `Buffer`/`TypedArray`) are a separate category, not included in heapUsed but affecting `rss` and OOM Kill risk.

**29. The container OOMs even though V8 "thinks" there's enough memory — why?**
By default V8 sets the Old Space limit based on the ENTIRE MACHINE's memory, not the container's cgroup limit. You need to explicitly set `--max-old-space-size` with headroom for `external` memory, which this flag doesn't bound.

## Typical follow-ups (Group 5)

```txt
"heapUsed is stable but the container's RSS keeps growing —
where do you look?" → external/arrayBuffers (retained
Buffers), not the V8 heap

"When does WeakMap solve a leak problem, and when doesn't it?"
→ solves it for caches tied to an object's lifecycle; doesn't
solve it for TTL caches (no notion of lifetime without
external strong references)
```

## Group 6: Modules — CommonJS vs ESM

**30. The main difference between CommonJS and ESM isn't just syntax. What else?**
CommonJS: `require()` is a synchronous function call, and an export is a COPY of the value at call time. ESM: loading happens in 3 phases (Construction → Instantiation → Evaluation), and an import is a LIVE BINDING to a "cell" in the source module. See [CommonJS vs ES Modules].

**31. How does a circular dependency behave in CommonJS vs ESM?**
In CommonJS — the module gets a PARTIALLY filled `module.exports` (only what was exported BEFORE the `require()` line that caused the cycle). In ESM — functions work better thanks to hoisting and live bindings, but `let`/`const` with computed values can be in TDZ if accessed during the cycle.

**32. Can CommonJS import a pure ESM package directly via `require()`?**
No — `require()` is synchronous, ESM requires asynchronous loading. The only way is dynamic `import()` (asynchronous). The reverse (ESM importing CJS) works — `module.exports` becomes `default`.

**33. What's the "dual package hazard"?**
If a library ships both CJS and ESM builds, and different parts of an app import it via `require()` and `import()` respectively, Node loads TWO separate modules with TWO instances of internal state. If the library uses a Singleton, the app ends up with two unrelated singletons.

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
- network operations are handled via epoll/kqueue/IOCP — ONE thread can monitor thousands of file descriptors without dedicating a thread per connection (see [libuv and the Thread Pool]);
- for operations with no async OS API (files, some crypto), there's the Thread Pool, a bounded pool of background threads;
- the phased Event Loop guarantees that ready callbacks are processed one at a time, never blocking each other longer than the synchronous portion of each callback (run-to-completion, see [The Event Loop]);
- the model's limit — if a callback runs synchronously for a LONG time (CPU-bound), ALL other connections wait — so CPU-bound work needs Worker Threads, and utilizing multiple cores for I/O-bound traffic needs Cluster/multiple replicas.

## Common interview mistakes

- **Memorizing answers without understanding the mechanism** — any variation of the question ("what if you add another await/listener/process?") breaks a memorized answer.

- **Ignoring follow-ups** — each of the 45 questions above is an ENTRY POINT into a deeper conversation; being unprepared for "why?" is the main sign of shallow prep.

- **Confusing "what uses the Thread Pool" with "what's asynchronous"** — almost everything in Node is asynchronous, but the Thread Pool is used only for a narrow set of operations (fs/crypto/zlib/dns.lookup).

- **Not connecting topics to each other** — e.g., not seeing the link between Memory/GC and Cluster (multiple processes with smaller heaps reduce GC pause impact), or between Streams and the Event Loop (stream events flow through the same Event Loop).
