# Memory, Heap, Stack, and Garbage Collection

## Why this is the #2 cause of production incidents (after Event Loop lag)

A memory leak in Node rarely looks like an obvious error. The application keeps responding to requests, but the process's resident set size (RSS) slowly creeps up over hours or days.

In the end the orchestrator — Kubernetes (k8s), for example — kills the container for running out of memory (OOM — out of memory) and restarts it. Between restarts everything "works", so the problem is often only noticed once restart frequency becomes suspicious.

## Stack vs Heap — quick, but focused on what people confuse

```txt
Stack:
  - function call frames, primitives, references to objects
  - fixed size at startup (--stack-size); overflow
    → "Maximum call stack size exceeded" (RangeError)
  - not managed by the garbage collector — memory is freed
    automatically on function return

Heap:
  - objects, arrays, functions, closures
  - managed by V8's garbage collector
  - this is where memory leaks happen
```

A common confusion: "a primitive declared inside a function lives in the heap because variables are objects." Not so. The primitive itself (`number`, `boolean`, short `string`) lives on the stack. The heap holds objects, arrays and functions, and the stack variable holds a **reference** to them.

## V8 Heap structure — more detail than "Young + Old Generation"

```txt
The V8 heap consists of several spaces:

  New Space (Young Generation)
    - small (typically a few MB), for new objects
    - cleared by the Scavenge algorithm (a copying
      collector) — fast and frequent (dozens or hundreds
      of times per second under load)

  Old Space (Old Generation)
    - objects that "survived" 2 Scavenge cycles in New Space
      get promoted here
    - cleared by Mark-Sweep-Compact — less often, but more
      expensive

  Large Object Space
    - objects above a certain size threshold (e.g., large
      Buffers/arrays) — skip New Space entirely, go straight
      here (never moved — too expensive)

  Code Space, Map Space
    - compiled code (JIT — just-in-time compilation),
      Hidden Classes/Shapes (see V8 and the Runtime)
```

### Scavenge: why young generation cleanup is so fast

```txt
Scavenge is a copying-collector algorithm (a variant of
Cheney's algorithm):

  New Space is split into 2 halves: "from-space" and "to-space"

  1. live objects are copied from from-space to to-space
  2. the whole from-space is considered garbage and simply
     "forgotten" — no traversal of dead objects at all!
  3. the two half-spaces swap roles

So the cost of a Scavenge is proportional to the number of
live objects, not the total amount of garbage — most objects
in New Space die quickly (req/res, temporary arrays), so the
"live" set is small → Scavenge is almost always sub-millisecond.
```

### Mark-Sweep-Compact: why old generation cleanup is slower

```txt
1. Mark: traverse from Root Objects (globals, active stack
   frames, closures) — mark reachable objects
2. Sweep: free unmarked objects
3. Compact: defragment live objects (move them together) to
   avoid "holey" memory

Old Space is usually much larger than New Space — traversing
the object graph takes significantly longer.
```

### Modern V8: why "Stop The World" is no longer the whole story

```txt
Old V8 (pre-~2018): a Major GC meant a full pause of JS
execution lasting tens to hundreds of milliseconds for a
large heap.

Modern V8:
  - Incremental Marking — the Mark phase is split into small
    steps interleaved with JS execution (the Orinoco project)
  - Concurrent Marking — part of Mark runs on background
    threads (see [libuv and the Thread Pool] — these are
    different threads, V8's own GC threads, not the libuv
    Thread Pool)
  - Parallel Compaction — the Compact phase uses multiple
    threads at once

Result: full pauses got much shorter (single-digit
milliseconds for most apps), but didn't disappear entirely —
final Mark synchronization and the Sweep phase itself still
require a brief pause of the main thread.
```

For an interview, the point isn't "the garbage collector (GC) stops the world and that's bad". Say it in three steps:

- A modern GC **reduces** the impact on latency. It does not remove it.
- For a large enough heap — gigabytes of live objects — pauses are still noticeable at p99 and p999 latency. That is the slowest 1% and 0.1% of requests.
- So several processes with a smaller heap each beat one process with a huge heap. That is an argument for horizontal scaling, see [Worker Threads and Cluster](./06-worker-threads-cluster.md).

## process.memoryUsage() — what each field actually means

```ts
console.log(process.memoryUsage());
// {
//   rss: 85000000,
//   heapTotal: 50000000,
//   heapUsed: 35000000,
//   external: 12000000,
//   arrayBuffers: 8000000
// }
```

```txt
rss (Resident Set Size)
  — the process's entire memory footprint in physical
    memory: V8 heap + Buffers + native modules + Node's own
    executable code. This is the number the orchestrator
    (k8s) compares against the container's memory limit for
    an OOM Kill.

heapTotal
  — how much memory V8 has allocated for the heap (grows in
    jumps, not smoothly — V8 reserves memory in blocks)

heapUsed
  — how much of heapTotal is actually occupied by live
    objects. The primary indicator for tracking leaks on the
    JS side

external
  — memory managed by C++ but tied to JS objects — primarily
    the contents of Buffer/TypedArray. Not included in
    heapUsed!

arrayBuffers
  — a subset of external, specifically ArrayBuffer/Buffer
```

### Senior nuance: a leak via `external`, not `heapUsed`

```ts
// ❌ heapUsed can stay stable while external keeps growing
const buffers: Buffer[] = [];

app.post('/upload', (req, res) => {
  buffers.push(req.body); // hold onto the Buffer forever
  res.send('ok');
});
```

```txt
Buffer data is stored outside the regular V8 heap (in
"external" memory), but the reference to the Buffer object is
a regular JS object on the heap. If you monitor only heapUsed
(as many "quick" guides suggest) — RSS growth from retained
Buffers goes unnoticed. RSS and external are mandatory
metrics when diagnosing leaks related to files or network
data.
```

## Memory leaks: three classic patterns — and why the garbage collector can't help

```ts
// ❌ Pattern 1: an unboundedly growing collection, reachable
// from the global scope (a Root Object)
const requestLog: RequestInfo[] = [];
app.use((req, res, next) => {
  requestLog.push({ url: req.url, timestamp: Date.now() }); // never cleared
  next();
});
```

```ts
// ❌ Pattern 2: EventEmitter listeners added per
// request/connection but never removed
function handleConnection(socket: Socket) {
  const onBroadcast = (msg: string) => socket.send(msg);
  broadcaster.on('message', onBroadcast); // subscribe...

  socket.on('close', () => {
    // ❌ forgot: broadcaster.off('message', onBroadcast)
    // broadcaster (long-lived) now holds a reference to
    // onBroadcast → onBroadcast holds socket (via closure)
    // → socket is never collected by the GC, even after
    // the connection closes
  });
}
```

```ts
// ❌ Pattern 3: a closure retains a large object that was
// only needed during initialization
function createHandler() {
  const hugeConfigCache = loadHugeConfig(); // 200 MB, needed once

  return (req: Request) => {
    // hugeConfigCache isn't used here, but the closure still
    // holds a reference to it, because JS doesn't do
    // "partial capture" — the whole variable from the
    // enclosing scope is captured
    return processRequest(req);
  };
}
```

```txt
In all three cases the GC works correctly. It doesn't delete
the object because the object is reachable from a root: a
global, a long-lived EventEmitter, a closure. A "leak" isn't
a GC bug, it's a bug in your code's graph of references.

Worth saying explicitly in an interview: V8's GC doesn't
"lose" memory. It faithfully keeps everything you are still
treating as needed, even by mistake.
```

### WeakMap / WeakRef — when they actually solve the problem

```ts
// ✅ WeakMap — the key doesn't keep the object alive
const metadataCache = new WeakMap<object, Metadata>();

function attachMetadata(obj: object, meta: Metadata) {
  metadataCache.set(obj, meta);
  // once obj is no longer used anywhere else (even if
  // metadataCache still exists) — the GC can collect both
  // obj and the corresponding WeakMap entry
}
```

```txt
WeakMap/WeakRef are a good fit for caches tied to an object's
lifecycle. Examples: metadata for DOM nodes in the browser
(DOM — the document object model), or for request objects in
Node. In Node this is rare, since a request is short-lived
and a plain Map cleared on a 'close' event is usually enough.

They are not a good fit for caches with a time to live (TTL).
A WeakMap has no TTL: the object stays alive as long as any
strong reference to it exists anywhere else.
```

## Diagnosing in production

```ts
// Basic monitoring — export as a metric
setInterval(() => {
  const mem = process.memoryUsage();
  metrics.gauge('nodejs.heap_used', mem.heapUsed);
  metrics.gauge('nodejs.rss', mem.rss);
  metrics.gauge('nodejs.external', mem.external);
}, 10_000);
```

```txt
Sign of a leak: heapUsed (or external/rss) grows
monotonically after every full GC cycle. The graph still
rises and falls locally (allocation → GC → drop), but the
low point after each drop is higher than the previous one.

Sign of "this is just normal behavior": heapUsed grows to some
plateau and stabilizes — V8 simply grew heapTotal to fit the
working set (caches, connection pools) and stops growing.
```

```bash
# Heap snapshot — to find the specific object responsible
node --inspect server.js
# Chrome DevTools → Memory → Heap Snapshot,
# compare two snapshots taken N minutes apart → "Comparison"
# view shows objects that appeared between snapshots and
# weren't freed
```

```txt
Caution: taking a heap snapshot is a Stop The World operation
and causes a temporary memory spike (V8 has to materialize a
full description of the object graph). Taking a snapshot on a
live production instance under load risks a brief full freeze
of the process. It is usually done on a single replica
temporarily pulled out of the load balancer, or via
clinic.js's heap profiler, which has lower overhead.
```

## `--max-old-space-size` and containers — a frequent source of "unexplainable" OOMs

```txt
By default, V8 sets the Old Space limit based on the system's
total memory, not on the limit set for the container by the
Linux control group (cgroup). On a machine with 64 GB of
memory but a container limited to 512 MB, V8 may try to grow
the heap beyond the container's limit. The orchestrator then
OOM-kills the process before V8 itself decides a GC is
needed.

✅ Explicitly cap V8's heap below the container limit:
  node --max-old-space-size=400 server.js
  # leaving ~25% headroom for external/Buffers/native modules,
  # which are not counted toward --max-old-space-size
```

```txt
Modern Node versions (≥18) partially fix this automatically
(V8 can read cgroup limits), but explicit configuration
remains best practice. External memory (Buffers) is not
bounded by --max-old-space-size at all, so the container can
still hit an OOM from accumulating Buffers even with a "safe"
heap.
```

## Connection to other topics

```txt
V8 and the Runtime        — Hidden Classes/Shapes and Inline
                               Caches affect how much memory
                               each object takes up (this
                               article is about when memory
                               gets freed)
Worker Threads and Cluster — multiple processes with smaller
                               heaps each reduce the impact of
                               GC pauses on p99 latency compared
                               to one huge heap
[libuv and the Thread Pool]  — V8's GC threads are a separate
                               thread pool, not libuv's Thread Pool
```

## Common interview mistakes

- **"The GC fully stops the application on every cycle"** — without mentioning Incremental/Concurrent/Parallel GC in modern V8. Those sharply reduce the impact on latency, though they don't eliminate it.

- **Monitoring only `heapUsed`** — this misses leaks via `external`/`arrayBuffers` (retained Buffers). They don't show up in heapUsed, but they directly affect RSS and the risk of an OOM Kill.

- **"A leaked object is a Garbage Collector bug"** — the GC works correctly by the definition of reachability. A leak is a bug in the code's graph of references: a forgotten listener, a growing global array, a closure with an unnecessary capture.

- **Not knowing about `--max-old-space-size` and container memory limits** — the orchestrator can OOM-kill the process while V8 still "thinks" no GC is needed. Without this flag you cannot explain why.

- **Recommending WeakMap as a universal caching solution** — a cache tied to an object's lifecycle is where WeakMap fits. A cache with a time to live (TTL) is where it doesn't: without external strong references there is no notion of lifetime.
