# Event Loop

## Why the Event Loop exists — reframed as a "contract"

The JS engine (V8) can execute synchronous code and manage the call stack — and that's all it can do. The Event Loop is the mechanism libuv provides on top of V8. It replaces one contract with another. Instead of "run a function and return a result" you get "schedule an operation, return control immediately, and call back when the result is ready."

```txt
Without an Event Loop (synchronous model):
  fs.readFileSync()  → the thread blocks for however long the
                         disk read takes (could be ms, could be
                         seconds under heavy disk load)

With an Event Loop (asynchronous model):
  fs.readFile(cb)    → the operation is handed to libuv, the JS
                         thread immediately continues running
                         other code; once the disk returns data,
                         cb is placed in a queue, and the Event
                         Loop runs it once it reaches the
                         corresponding phase
```

This isn't "Node is smart and figures it out" — it's an explicit contract. Every time the Event Loop hands control to your JS code, that code runs **to completion** (run-to-completion). The Event Loop cannot interrupt a running JS function. Almost every practical rule in this topic follows from that contract.

## The full phase diagram — and what actually happens in each phase

```txt
   ┌───────────────────┐
┌─>│       timers      │  setTimeout / setInterval,
│  └───────────────────┘  ready by time
│  ┌───────────────────┐
│  │ pending callbacks │  callbacks for some system
│  │   (pending I/O)   │  operations, e.g. errors on a
│  │                   │  TCP socket (Transmission
│  │                   │  Control Protocol)
│  └───────────────────┘
│  ┌───────────────────┐
│  │   idle, prepare   │  internal libuv housekeeping
│  └───────────────────┘
│  ┌───────────────────┐
│  │        poll       │  ← the central phase:
│  │                   │  I/O callbacks (fs, network),
│  │                   │  and waiting for new I/O events
│  └───────────────────┘
│  ┌───────────────────┐
│  │       check       │  setImmediate
│  └───────────────────┘
│  ┌───────────────────┐
└──┤  close callbacks  │  socket.on('close'), etc.
   └───────────────────┘
```

Between **every** pair of phases the Event Loop fully drains two queues: the **microtask queue** (Promise callbacks, `queueMicrotask`) and the `process.nextTick` queue. Often it does the same inside a phase, after each callback.

This detail is critical, and it has an article of its own: [Microtasks, Macrotasks, and process.nextTick](./04-microtasks-macrotasks-nexttick.md). It explains most "unexpected" execution orderings.

### Poll — the most important phase, and why

Poll is the phase where Node spends the **most time** in a real application (assuming the app isn't compute-bound). Two things happen here:

```txt
1. If the poll queue has ready I/O callbacks (a database
   query returned, a file was read, a response arrived)
   → run them (draining microtasks after each)

2. If the queue is empty:
   - if there's a setImmediate() queued for check → move
     to check immediately
   - if there are timers about to fire → wait for I/O, but
     no longer than until the next timer fires
   - otherwise → block on this phase and wait for I/O from
     the operating system, until an event arrives or a
     timer expires
```

That last point is key: when there is nothing to do, the Event Loop **doesn't spin in a hot loop burning CPU time**. CPU stands for central processing unit — the processor.

Instead the loop blocks on a system call of the operating system (OS): `epoll_wait`, `kqueue`, or IOCP (I/O completion ports) on Windows. The operating system then "wakes" the process when a network packet arrives, a file operation finishes, or a timer expires. This is why a Node process with thousands of idle connections consumes almost no CPU.

## setTimeout vs setImmediate — the order depends on context

This is one of the most common "trick questions," and the correct answer is "it depends on where it's called from":

```ts
// At the module (top-level) scope — the order is not guaranteed
setTimeout(() => console.log('timeout'), 0);
setImmediate(() => console.log('immediate'));
// May print "timeout, immediate" or "immediate, timeout" —
// depends on how long process initialization took before
// this point (setTimeout(0) is actually scheduled for ~1ms,
// and if the event loop started before that mark — timers
// aren't ready yet on the first pass)
```

```ts
// Inside an I/O callback — the order is always deterministic
fs.readFile(__filename, () => {
  setTimeout(() => console.log('timeout'), 0);
  setImmediate(() => console.log('immediate'));
});
// Always: "immediate, timeout"
//
// Why: we're in the poll phase (this is an I/O callback).
// The next phase after poll is check (setImmediate).
// timers comes on the next iteration of the loop, after check.
```

Memorizing "what gets printed" is useless. What matters is the **mechanism**. The phase order `timers → poll → check` is fixed, and the only variable is **which phase execution starts from**. Inside an I/O callback you are definitely in poll, so check (`setImmediate`) is guaranteed to come before the next pass through timers.

## "The Event Loop does nothing until the stack is empty" — practical consequences

```ts
// ❌ This function blocks the Event Loop for seconds —
// no other request to the server will be processed,
// regardless of how much I/O they're doing
function blockingHash(password: string) {
  return crypto.pbkdf2Sync(password, 'salt', 500_000, 64, 'sha512');
}

app.post('/login', (req, res) => {
  const hash = blockingHash(req.body.password); // all other
  res.json({ hash });                            // requests wait
});
```

```ts
// ✅ The same task, split into chunks via setImmediate —
// between chunks, the Event Loop can process other work.
// This does not speed up the operation itself (the CPU is
// still busy), but it keeps the server responsive
function processBigArrayInChunks(items: Item[], onDone: () => void) {
  let i = 0;
  function chunk() {
    const end = Math.min(i + 1000, items.length);
    for (; i < end; i++) process(items[i]);
    if (i < items.length) setImmediate(chunk);  // yield control
    else onDone();
  }
  chunk();
}
```

Senior nuance: "splitting into chunks" is a **trade-off**, not a fix. Total CPU time doesn't change. What changes is that between chunks the Event Loop can serve other requests. For genuinely heavy computation the correct solution is Worker Threads (see [Worker Threads and Cluster](./06-worker-threads-cluster.md)). They run on a separate thread, so they really do free the main one.

## Monitoring event loop lag in production — what separates theory from practice

In real systems the question isn't "does the event loop ever block". It is "how delayed is it **right now**, under the current load". That is what the **event loop lag** (or delay) metric is for:

```ts
import { monitorEventLoopDelay } from 'node:perf_hooks';

const histogram = monitorEventLoopDelay({ resolution: 20 });
histogram.enable();

setInterval(() => {
  // p99 event loop delay over the last interval.
  // p99 = the value 99% of the samples stay below.
  console.log('p99 lag (ms):', histogram.percentile(99) / 1e6);
  histogram.reset();
}, 5000);
```

```txt
Practical meaning:
  - lag close to 0 — the event loop responds almost instantly
  - lag growing under load — somewhere, synchronous code is
    running that doesn't let the event loop "breathe" between tasks

  This is a metric worth exporting to Prometheus/Datadog for
  production Node services — rising event loop lag often
  precedes rising API latency even before CPU usage looks
  critical.

  Example: a "hot" function is called in bursts rather than
  continuously. Average CPU usage looks normal, while p99
  request latency rises exactly because of the lag during
  those bursts.
```

## Connection to other topics

```txt
V8 and the Runtime        — V8 runs your JS code synchronously,
                              "to completion", between phases
Microtasks, Macrotasks,
 and process.nextTick      — what happens between phases and
                              between individual callbacks
[libuv and the Thread Pool] — how exactly an operation ends up
                               in the poll queue (via the thread
                               pool or a native OS async API)
Worker Threads and Cluster — the real solution for CPU-bound
                              work that must not block the loop
```

## Common interview mistakes

- **"The Event Loop is a while(true) with a queue"** — a simplification that explains nothing. It covers neither the order of phases nor the reason microtasks run between them. It also hides the fact that the poll phase can block on I/O without consuming CPU.

- **Memorizing the output of `setTimeout(0)` vs `setImmediate()`** without understanding that the order depends on the calling context: top-level, or inside an I/O callback. A slightly varied example in an interview will break a memorized answer.

- **Not distinguishing "split into chunks via setImmediate" from "offload to a Worker Thread"**. The first doesn't reduce total CPU load, it only spreads it over time. The second actually frees the main thread.

- **Not knowing about monitoring event loop lag.** Roles with production responsibility get asked "how would you know a Node service is degrading because the event loop is blocked". Having no answer about `monitorEventLoopDelay` or APM metrics (APM — application performance monitoring) looks like purely theoretical knowledge.

- **Confusing "asynchronous" with "parallel"** — the Event Loop gives you **concurrency**: many operations "in flight" at once. Each of them is waiting for I/O to finish. It does not give you **parallelism**, the simultaneous execution of JS code. For that you need Worker Threads or Cluster.
