# libuv and Thread Pool

## "Node is single-threaded" — where exactly the line is

The statement "Node is single-threaded" is true for one specific thing — executing your JS code in V8. But a Node process contains:

```txt
1 thread   — runs JS (V8) + libuv's Event Loop
N threads  — libuv's Thread Pool (4 by default)
M threads  — V8's background GC threads (see [Memory and Garbage Collection])
```

Network operations (`http`, `net`, `tcp`) **don't use the Thread Pool at all** — this is the critical detail that's most often confused. They rely on the OS's native async mechanisms:

```txt
Linux:   epoll
macOS:   kqueue
Windows: IOCP (I/O Completion Ports)
```

These mechanisms let a SINGLE thread monitor thousands of file descriptors (sockets) and get notified when a specific socket is ready to read/write — without dedicating a thread per connection. That's why Node can hold 10,000+ open WebSocket connections without 10,000 threads — for networking, no thread is needed at all until data is ready.

## Why the filesystem is a different story

A natural question: "if epoll exists for networking, why does `fs.readFile` use the Thread Pool instead of the same mechanism?"

```txt
Answer: on most platforms (especially Linux), there's NO
RELIABLE non-blocking API for file operations at the OS
level — unlike sockets.

epoll works great for sockets, but if you try to use it for
regular files on Linux, it's either unsupported or behaves
unpredictably (always reports "ready").

libuv's solution: perform the blocking system call (read(),
open(), stat()) on a SEPARATE Thread Pool thread — and when
the call completes (that thread blocks, but it's not the main
thread!), the result is passed back to the Event Loop through
the same notification mechanism.
```

This explains why **file operations simulate asynchrony via threads**, while network operations are **genuinely asynchronous at the OS level**. For user code, the difference is invisible (both use callbacks/Promises), but for understanding what REALLY consumes the Thread Pool resource, this distinction is key.

## The full map: what uses the Thread Pool

```txt
USE the Thread Pool:
  fs.*           (except fs.FSWatcher — file watching uses
                  platform-specific notifications)
  crypto.pbkdf2, crypto.scrypt, crypto.randomBytes (async),
  crypto.generateKeyPair (async)
  zlib.* (gzip/gunzip/brotli — async versions)
  dns.lookup()   — uses the system's getaddrinfo()

DON'T use the Thread Pool (native OS async):
  net, http, https, tcp, udp — epoll/kqueue/IOCP
  dns.resolve*() — uses c-ares, its OWN async DNS
                   resolution implementation, NOT the
                   system's getaddrinfo() and NOT the Thread Pool
```

### Senior nuance: `dns.lookup` vs `dns.resolve` — a common "gotcha"

```ts
// dns.lookup uses the OS's getaddrinfo() → Thread Pool
// (the SAME pool as fs/crypto/zlib!)
dns.lookup('example.com', callback);

// dns.resolve4/resolve6/resolveCname uses c-ares →
// NOT the Thread Pool, a separate mechanism
dns.resolve4('example.com', callback);
```

If an application does a lot of DNS resolution via `dns.lookup` (e.g., implicitly — via `http.get` with hostnames, which by default resolve through `lookup`) AT THE SAME TIME as heavy `crypto`/`fs` operations — they **compete for the same Thread Pool**. This is a non-obvious connection rarely discussed: "slow outgoing HTTP requests to external APIs" and "slow file reads" can turn out to be RELATED symptoms of one cause — a saturated Thread Pool.

## A concrete example of an "invisible" bottleneck

```ts
// ❌ On every request — bcrypt (CPU-heavy, via Thread Pool)
// PLUS reading a file (also Thread Pool)
app.post('/register', async (req, res) => {
  const hash = await bcrypt.hash(req.body.password, 12); // Thread Pool
  const template = await fs.promises.readFile('welcome.html'); // Thread Pool
  // ...
});
```

```txt
With UV_THREADPOOL_SIZE=4 (default) and 10 concurrent
registrations:

  - 4 requests start bcrypt.hash immediately → occupy ALL
    4 pool threads
  - fs.readFile FOR THOSE SAME requests waits in line, even
    though reading the file itself takes a fraction of a
    millisecond
  - the remaining 6 requests' bcrypt.hash calls wait entirely

  Observed symptom: "the API got slow," "CPU isn't maxed"
  (bcrypt is fast, but the pool is narrow), latency grows
  non-linearly with the number of concurrent requests
```

### The fix and its limits

```bash
# Increasing the pool relieves the symptom, but doesn't fix the root cause
UV_THREADPOOL_SIZE=16 node app.js
```

```txt
Important: UV_THREADPOOL_SIZE must be set BEFORE Node queues
its first task for the pool — i.e., BEFORE any require/call
that triggers the Thread Pool (often before the first
fs/crypto call). Setting it "on the fly" via process.env in
code may no longer have an effect if the pool is already
initialized by that point.

But: more threads = more stack memory + more context
switches on a CPU with a limited number of cores. "Just bump
it to 128" isn't a solution — it shifts the problem and
potentially creates a new one (CPU contention).

The real fix for CPU-heavy operations (bcrypt, pbkdf2 with a
high cost factor) is Worker Threads (see [Worker Threads and
Cluster]), where the computation gets its OWN dedicated
thread instead of sharing a pool with the whole app's file
operations.
```

## How to diagnose Thread Pool saturation in production

```txt
Indirect signs:
  - CPU usage is NOT maxed, but p99 latency is rising
  - latency rises NON-LINEARLY with RPS — a sudden jump past
    a certain concurrency level
  - operations that "logically" are unrelated (DNS, fs,
    bcrypt) degrade AT THE SAME TIME

Direct diagnosis:
  - APM tools (Datadog, New Relic) show "thread pool queue
    time" separately from "execution time"
  - you can measure it explicitly by wrapping calls and
    timing the gap between calling fs.readFile and the
    callback actually starting, relative to when it was queued
```

## Connection to other topics

```txt
[The Event Loop]            — the Thread Pool is JUST ONE
                               source of events for the poll
                               phase; networking arrives in
                               poll directly via epoll/kqueue,
                               with no Thread Pool involved
[Worker Threads and Cluster] — the correct solution for
                               CPU-heavy work that shouldn't
                               share a resource with
                               fs/crypto/zlib/dns.lookup
[Memory and Garbage
 Collection]                  — another source of background
                               threads in the process (V8's
                               GC threads)
```

## Common interview mistakes

- **"Node is single-threaded" with no qualification** — not mentioning the Thread Pool, V8's background GC threads, or that "single-threaded" refers specifically to JS execution.

- **Assuming ALL async operations in Node use the Thread Pool** — not distinguishing network operations (epoll/kqueue/IOCP, no Thread Pool) from filesystem/crypto/zlib operations (Thread Pool).

- **Not knowing the difference between `dns.lookup` and `dns.resolve*`** — missing that DNS resolution via `lookup` competes with fs/crypto for the same pool, while `resolve*` doesn't.

- **"Just increase UV_THREADPOOL_SIZE" as a universal fix** — without understanding it's a palliative with its own cost (memory, context switching), not a substitute for Worker Threads for genuinely heavy computation.

- **Not knowing how to diagnose pool saturation** — treating "CPU is fine but latency is rising" as an unsolvable mystery rather than a classic symptom of Thread Pool contention.
