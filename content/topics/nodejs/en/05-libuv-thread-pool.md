# libuv and Thread Pool

## "Node is single-threaded" — where exactly the line is

The statement "Node is single-threaded" is true for one specific thing — executing your JS code in V8. But a Node process contains:

```txt
1 thread   — runs JS (V8) + libuv's Event Loop
N threads  — libuv's Thread Pool (4 by default)
M threads  — V8's background threads for garbage collection
             (GC), see Memory and Garbage Collection
```

Network operations (`http`, `net`, `tcp`) **don't use the Thread Pool at all** — this is the critical detail that's most often confused. They rely on the native async mechanisms of the operating system (OS):

```txt
Linux:   epoll
macOS:   kqueue
Windows: IOCP (I/O Completion Ports)
```

These mechanisms let a **single** thread monitor thousands of file descriptors (sockets). The thread is notified when a specific socket is ready to read or write, and no thread is dedicated to a connection.

That's why Node can hold 10,000+ open WebSocket connections without 10,000 threads. For networking, no thread is needed at all until the data is ready.

## Why the filesystem is a different story

A natural question: "if epoll exists for networking, why does `fs.readFile` use the Thread Pool instead of the same mechanism?"

```txt
Answer: on most platforms (especially Linux) there is no
reliable non-blocking API for file operations at the
operating system level — unlike sockets.

epoll works great for sockets, but if you try to use it for
regular files on Linux, it's either unsupported or behaves
unpredictably (always reports "ready").

libuv's solution: perform the blocking system call (read(),
open(), stat()) on a separate Thread Pool thread — and when
the call completes (that thread blocks, but it's not the main
thread!), the result is passed back to the Event Loop through
the same notification mechanism.
```

This explains why **file operations simulate asynchrony via threads**, while network operations are **genuinely asynchronous at the operating system level**. For user code the difference is invisible: both use callbacks or Promises. But if you want to know what really consumes the Thread Pool, this is the distinction that matters.

## The full map: what uses the Thread Pool

```txt
Use the Thread Pool:
  fs.*           (except fs.FSWatcher — file watching uses
                  platform-specific notifications)
  crypto.pbkdf2, crypto.scrypt, crypto.randomBytes (async),
  crypto.generateKeyPair (async)
  zlib.* (gzip/gunzip/brotli — async versions)
  dns.lookup()   — uses the system's getaddrinfo()

Do not use the Thread Pool (native async of the OS):
  net, http, https, tcp, udp — epoll/kqueue/IOCP
  dns.resolve*() — uses c-ares, its own async implementation
                   of DNS name resolution (DNS = Domain Name
                   System, which turns a hostname into an
                   address). Not the system's getaddrinfo(),
                   and not the Thread Pool
```

### Senior nuance: `dns.lookup` vs `dns.resolve` — a common trap

```ts
// dns.lookup uses the OS's getaddrinfo() → Thread Pool
// (the same pool as fs/crypto/zlib!)
dns.lookup('example.com', callback);

// dns.resolve4/resolve6/resolveCname uses c-ares →
// not the Thread Pool, a separate mechanism
dns.resolve4('example.com', callback);
```

Some applications resolve a lot of names through `dns.lookup`. Often that happens implicitly: `http.get` with a hostname resolves through `lookup` by default. If this runs at the same time as heavy `crypto` or `fs` operations, they **compete for the same Thread Pool**.

The connection is rarely discussed. "Slow outgoing HTTP requests to external APIs" and "slow file reads" can turn out to be two symptoms of one cause: a saturated Thread Pool.

## A concrete example of an "invisible" bottleneck

```ts
// ❌ On every request — bcrypt (CPU-heavy, via Thread Pool).
// CPU = central processing unit, the processor.
// Plus reading a file (also Thread Pool)
app.post('/register', async (req, res) => {
  const hash = await bcrypt.hash(req.body.password, 12); // Thread Pool
  const template = await fs.promises.readFile('welcome.html'); // Thread Pool
  // ...
});
```

```txt
With UV_THREADPOOL_SIZE=4 (default) and 10 concurrent
registrations:

  - 4 requests start bcrypt.hash immediately → they occupy
    all 4 pool threads
  - fs.readFile for those same requests waits in line, even
    though reading the file itself takes a fraction of a
    millisecond
  - the remaining 6 requests' bcrypt.hash calls wait entirely

  Observed symptom: "the API got slow", "the CPU isn't
  maxed out" — bcrypt is fast, but the pool
  is narrow. Latency grows non-linearly with the number of
  concurrent requests.
```

### The fix and its limits

```bash
# Increasing the pool relieves the symptom, but doesn't fix the root cause
UV_THREADPOOL_SIZE=16 node app.js
```

```txt
Important: UV_THREADPOOL_SIZE must be set before Node queues
its first task for the pool — that is, before any require or
call that triggers the Thread Pool (often before the first
fs/crypto call). Setting it "on the fly" via process.env in
code may no longer have an effect if the pool is already
initialized by that point.

But: more threads = more stack memory + more context
switches on a CPU with a limited number of cores. "Just bump
it to 128" isn't a solution — it shifts the problem and
potentially creates a new one (CPU contention).

The real fix for CPU-heavy operations (bcrypt, pbkdf2 with a
high cost factor) is Worker Threads (see Worker Threads and
Cluster), where the computation gets its own dedicated
thread instead of sharing a pool with the whole app's file
operations.
```

## How to diagnose Thread Pool saturation in production

```txt
Indirect signs:
  - CPU usage is not maxed out, but p99 latency is rising.
    p99 is the value 99% of requests stay under
  - latency rises non-linearly with RPS (requests per
    second) — a sudden jump past a certain concurrency level
  - operations that "logically" are unrelated (DNS, fs,
    bcrypt) degrade at the same time

Direct diagnosis:
  - tools for APM (application performance monitoring), such
    as Datadog or New Relic, show "thread pool queue time"
    separately from "execution time"
  - you can measure it explicitly by wrapping calls and
    timing the gap between calling fs.readFile and the
    callback actually starting, relative to when it was queued
```

## Connection to other topics

```txt
The Event Loop            — the Thread Pool is just one
                               source of events for the poll
                               phase; networking arrives in
                               poll directly via epoll/kqueue,
                               with no Thread Pool involved
Worker Threads and Cluster — the correct solution for
                               CPU-heavy work that shouldn't
                               share a resource with
                               fs/crypto/zlib/dns.lookup
Memory and Garbage
 Collection                  — another source of background
                               threads in the process (V8's
                               GC threads)
```

## Common interview mistakes

- **"Node is single-threaded" with no qualification**. No mention of the Thread Pool, and none of V8's background threads for garbage collection (GC). No mention either that "single-threaded" refers specifically to JS execution.

- **Assuming every async operation in Node uses the Thread Pool**. Network operations go through epoll, kqueue or IOCP (I/O completion ports) — the async mechanisms of the operating system, with no Thread Pool. Filesystem, crypto and zlib operations do use the pool.

- **Not knowing the difference between `dns.lookup` and `dns.resolve*`**. Name resolution through `lookup` competes with fs and crypto for the same pool. Resolution through `resolve*` does not.

- **"Just increase UV_THREADPOOL_SIZE" as a universal fix**. It only relieves the symptom, and it has its own cost: more memory for thread stacks, more context switching. It is not a substitute for Worker Threads when the computation is genuinely heavy.

- **Not knowing how to diagnose pool saturation.** "CPU is fine but latency is rising" gets treated as an unsolvable mystery. It is a classic symptom of Thread Pool contention.
