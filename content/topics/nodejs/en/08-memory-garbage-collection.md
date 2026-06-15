# Memory, Heap, Stack, and Garbage Collection

## Why this is the #2 cause of production incidents (after Event Loop lag)

A memory leak in Node rarely looks like an obvious error — the application keeps responding to requests, but the process's `RSS` slowly creeps up over hours or days, until the orchestrator (k8s) OOM-kills the container and restarts it. Between restarts everything "works," so the problem is often only noticed once restart frequency becomes suspicious.

## Stack vs Heap — quick, but focused on what people confuse

```txt
Stack:
  - function call frames, primitives, REFERENCES to objects
  - fixed size at startup (--stack-size); overflow
    → "Maximum call stack size exceeded" (RangeError)
  - NOT managed by the GC — memory is freed automatically
    on function return

Heap:
  - objects, arrays, functions, closures
  - managed by V8's Garbage Collector
  - this is where memory leaks happen
```

A common confusion: "a primitive declared inside a function lives in the heap because variables are objects." Actually the primitive itself (`number`, `boolean`, short `string`) lives on the stack; the heap holds objects/arrays/functions, and the stack variable holds a REFERENCE to them.

## V8 Heap structure — more detail than "Young + Old Generation"

```txt
The V8 heap consists of several spaces:

  New Space (Young Generation)
    - small (typically a few MB), for new objects
    - cleared by the Scavenge algorithm (copying GC) —
      FAST and FREQUENT (dozens/hundreds of times per
      second under load)

  Old Space (Old Generation)
    - objects that "survived" 2 Scavenge cycles in New Space
      get PROMOTED here
    - cleared by Mark-Sweep-Compact — LESS often, but MORE
      expensive

  Large Object Space
    - objects above a certain size threshold (e.g., large
      Buffers/arrays) — skip New Space entirely, go straight
      here (never moved — too expensive)

  Code Space, Map Space
    - compiled code (JIT), Hidden Classes/Shapes
      (see [V8 and the Runtime])
```

### Scavenge: why young generation cleanup is so fast

```txt
Scavenge is a copying-GC algorithm (a variant of Cheney's
algorithm):

  New Space is split into 2 halves: "from-space" and "to-space"

  1. live objects are copied from from-space to to-space
  2. the ENTIRE from-space is considered garbage and simply
     "forgotten" — no traversal of dead objects at all!
  3. the two half-spaces swap roles

So the cost of a Scavenge is proportional to the number of
LIVE objects, not the total amount of garbage — most objects
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

Old Space is usually MUCH larger than New Space — traversing
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
  - Concurrent Marking — part of Mark runs on BACKGROUND
    threads (see [libuv and the Thread Pool] — these are
    DIFFERENT threads, V8's own GC threads, not the libuv
    Thread Pool)
  - Parallel Compaction — the Compact phase uses multiple
    threads at once

Result: full pauses got much shorter (single-digit
milliseconds for most apps), but didn't disappear entirely —
final Mark synchronization and the Sweep phase itself still
require a brief pause of the main thread.
```

For an interview, the point isn't "GC stops the world and that's bad," but: modern GC REDUCES the impact on latency, but for a sufficiently large heap (gigabytes of live objects) pauses are still noticeable at p99/p999 latency — an argument for horizontal scaling (more processes with smaller heaps each) over one process with a huge heap, see [Worker Threads and Cluster].

## process.memoryUsage() — what EACH field actually means

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
  — the process's ENTIRE memory footprint in RAM: V8 heap +
    Buffers + native modules + Node's own executable code.
    This is the number the orchestrator (k8s) compares
    against the container's memory limit for OOM Kill.

heapTotal
  — how much memory V8 has ALLOCATED for the heap (grows in
    jumps, not smoothly — V8 reserves memory in blocks)

heapUsed
  — how much of heapTotal is ACTUALLY occupied by live
    objects. The primary indicator for tracking leaks on the
    JS side

external
  — memory managed by C++ but tied to JS objects — primarily
    the contents of Buffer/TypedArray. NOT included in heapUsed!

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
Buffer data is stored OUTSIDE the regular V8 heap (in
"external" memory), but the reference to the Buffer object is
a regular JS object on the heap. If you monitor ONLY heapUsed
(as many "quick" guides suggest) — RSS growth from retained
Buffers goes UNNOTICED. RSS and external are mandatory metrics
when diagnosing leaks related to files/network data.
```

## Memory leaks — three classic patterns, with a focus on WHY the GC can't help

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
    // → socket is NEVER collected by the GC, even after
    // the connection closes
  });
}
```

```ts
// ❌ Pattern 3: a closure retains a large object that was
// only needed during initialization
function createHandler() {
  const hugeConfigCache = loadHugeConfig(); // 200 MB, needed ONCE

  return (req: Request) => {
    // hugeConfigCache isn't used here, but the closure STILL
    // holds a reference to it, because JS doesn't do
    // "partial capture" — the whole variable from the
    // enclosing scope is captured
    return processRequest(req);
  };
}
```

```txt
In all three cases the GC works CORRECTLY — it doesn't delete
the object because the object is REACHABLE from a root
(global, a long-lived EventEmitter, a closure). A "leak" isn't
a GC bug, it's a bug in your code's REFERENCE GRAPH. Worth
saying explicitly in an interview: V8's GC doesn't "lose"
memory — it faithfully keeps everything you (mistakenly) are
still treating as needed.
```

### WeakMap / WeakRef — when they ACTUALLY solve the problem

```ts
// ✅ WeakMap — the key doesn't keep the object alive
const metadataCache = new WeakMap<object, Metadata>();

function attachMetadata(obj: object, meta: Metadata) {
  metadataCache.set(obj, meta);
  // once obj is no longer used ANYWHERE ELSE (even if
  // metadataCache still exists) — the GC can collect both
  // obj and the corresponding WeakMap entry
}
```

```txt
WeakMap/WeakRef are a good fit for: caches tied to an object's
lifecycle (e.g., metadata for DOM nodes in the browser, or for
request objects in Node — though this is rare in Node, since a
request is short-lived and a plain Map cleared on a 'close'
event is usually enough).

NOT a good fit for: TTL caches (a WeakMap has no TTL — the
object stays alive as long as ANY strong reference to it
exists anywhere else).
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
MONOTONICALLY after every full GC cycle — i.e., there's a
local sawtooth pattern (allocation → GC → drop), but the
"floor" of the sawtooth rises over time.

Sign of "this is just normal behavior": heapUsed grows to some
plateau and stabilizes — V8 simply grew heapTotal to fit the
working set (caches, connection pools) and stops growing.
```

```bash
# Heap snapshot — to find the SPECIFIC culprit object
node --inspect server.js
# Chrome DevTools → Memory → Heap Snapshot,
# compare two snapshots taken N minutes apart → "Comparison"
# view shows objects that appeared BETWEEN snapshots and
# weren't freed
```

```txt
Caution: taking a heap snapshot is a Stop The World operation
and causes a temporary memory SPIKE (V8 has to materialize a
full description of the object graph). Taking a snapshot on a
LIVE production instance under load risks a brief full freeze
of the process; this is usually done on a single replica
temporarily pulled out of the load balancer, or via clinic.js's
heap profiler, which has lower overhead.
```

## `--max-old-space-size` and containers — a frequent source of "unexplainable" OOMs

```txt
By default, V8 sets the Old Space limit based on the SYSTEM's
TOTAL memory (NOT the container's cgroup limit!) — on a
machine with 64GB RAM but a container limited to 512MB, V8 may
try to grow the heap beyond the container's limit, and the
orchestrator OOM-kills the process BEFORE V8 itself decides a
GC is needed.

✅ Explicitly cap V8's heap BELOW the container limit:
  node --max-old-space-size=400 server.js
  # leaving ~25% headroom for external/Buffers/native modules,
  # which are NOT counted toward --max-old-space-size
```

```txt
Modern Node versions (≥18) PARTIALLY fix this automatically
(V8 can read cgroup limits), but explicit configuration remains
best practice — especially since external memory (Buffers) is
NOT bounded by --max-old-space-size at all, and the container
can still OOM from accumulating Buffers even with a "safe" heap.
```

## Connection to other topics

```txt
[V8 and the Runtime]        — Hidden Classes/Shapes and Inline
                               Caches affect HOW MUCH memory
                               each object takes up (this
                               article is about WHEN memory
                               gets freed)
[Worker Threads and Cluster] — multiple processes with smaller
                               heaps each reduce the impact of
                               GC pauses on p99 latency compared
                               to one huge heap
[libuv and the Thread Pool]  — V8's GC threads are a SEPARATE
                               thread pool, not libuv's Thread Pool
```

## Common interview mistakes

- **"The GC fully stops the application on every cycle"** — without mentioning Incremental/Concurrent/Parallel GC in modern V8, which sharply reduce (but don't fully eliminate) the impact on latency.

- **Monitoring only `heapUsed`** — missing leaks via `external`/`arrayBuffers` (retained Buffers), which don't show up in heapUsed but directly affect RSS and OOM Kill risk.

- **"A leaked object is a Garbage Collector bug"** — not explaining that the GC works correctly by definition of reachability, and a leak is a bug in the code's reference graph (a forgotten listener, a growing global array, a closure with an unnecessary capture).

- **Not knowing about `--max-old-space-size` and container memory limits** — not understanding why the process can be OOM-killed by the orchestrator even when V8 "thinks" a GC isn't needed yet.

- **Recommending WeakMap as a universal caching solution** — not distinguishing "a cache tied to an object's lifecycle" (where WeakMap fits) from "a TTL cache" (where WeakMap doesn't work, since there's no notion of lifetime without external strong references).
