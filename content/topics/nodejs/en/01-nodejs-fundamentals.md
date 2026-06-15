# Node.js Fundamentals

## Node.js is a runtime, not a language and not a framework

```txt
JavaScript — the language (the ECMAScript spec: syntax, types,
  Promise, async/await, ...)

Node.js — a runtime: a C++ program that embeds the V8 engine
  and adds APIs to it that aren't part of the language spec
  (fs, net, process, Buffer, ...)

Express/Nest/Fastify — frameworks built ON TOP of Node.js
```

The "Node = V8" confusion is common but worth correcting: V8 executes JS code and manages memory (heap, GC — see [Memory and Garbage Collection]), but it **has no idea** what a file or a TCP socket is. Those capabilities are provided by Node itself, via C++ bindings to libuv and other libraries. When you call `fs.readFile(...)`, the JS code running in V8 calls a C++ function that delegates the operation to libuv (see [libuv and the Thread Pool]).

```txt
┌─────────────────────────────────────────┐
│              Node.js Process              │
│                                            │
│  ┌──────────┐   ┌──────────────────────┐ │
│  │    V8    │   │    Node.js APIs       │ │
│  │ (runs JS,│←──│  (fs, net, http,      │ │
│  │  heap,   │   │   crypto, Buffer...)  │ │
│  │   GC)    │   └──────────┬───────────┘ │
│  └──────────┘              │              │
│                      ┌──────▼──────┐      │
│                      │    libuv    │      │
│                      │ (Event Loop,│      │
│                      │ Thread Pool)│      │
│                      └─────────────┘      │
└─────────────────────────────────────────┘
```

This diagram is the skeleton for every other topic in this section: V8 is covered in [V8 and the Runtime] and [Memory and Garbage Collection], the Event Loop in [The Event Loop] and [Microtasks, Macrotasks, and process.nextTick], the Thread Pool in [libuv and the Thread Pool], and multi-process/multi-thread strategies in [Worker Threads and Cluster].

## Why "single-threaded" is a deliberate architectural choice, not a limitation

When Node appeared in 2009, the dominant server model was "a thread (or process) per connection" (Apache prefork/threaded). The problem with that model: a thread is an expensive resource (stack memory, context-switch cost), and most of the time a thread serving a network request is **doing nothing** — it's just waiting on a response from a database, disk, or another service.

```txt
Traditional model (1 thread = 1 request):
  10,000 concurrent connections → 10,000 threads,
  most of them sitting in "waiting on I/O"
  → memory and context-switching become the bottleneck
  LONG BEFORE the CPU is actually busy

Node model (1 thread runs JS, I/O is delegated):
  10,000 connections → 1 main thread processes events as
  I/O operations become ready
  → no memory spent on stacks, no context switches
```

A key nuance that's often missed: "single-threaded" refers **only to the execution of your JS code**. The Node process itself is multi-threaded: internally it runs libuv's Thread Pool (4 threads by default — see [libuv and the Thread Pool]) for operations that have no async system API (parts of the filesystem, DNS, some crypto functions), plus V8's background threads for garbage collection. "Single-threaded" is about the programming model (no data races between two pieces of your JS code), not about the literal number of OS threads in the process.

## I/O-bound vs CPU-bound — where the line actually falls

```txt
I/O-bound (Node is an excellent choice):
  - HTTP/REST APIs, GraphQL
  - WebSocket / realtime
  - Reverse proxy / API Gateway
  - Streaming (video, files — see [Streams and Backpressure])
  - BFF (Backend for Frontend) — lots of parallel calls to
    other services, minimal computation of its own

CPU-bound (Node is weaker out of the box):
  - Image/video processing
  - Heavy computation (e.g., encrypting large volumes of data,
    parsing huge documents synchronously)
  - Machine learning inference
```

But "Node is bad for CPU-bound work" is a simplification worth refining in an interview: the issue isn't that Node "can't" do computation — it's that **any synchronous CPU operation blocks the single thread running the event loop** — while it runs, Node can't process ANY other event, including incoming HTTP requests from other users.

```ts
// ❌ Blocks the event loop for its entire duration —
// ALL other requests to this server "hang" during that time
app.get('/hash', (req, res) => {
  const hash = crypto.pbkdf2Sync(req.query.password, 'salt', 100_000, 64, 'sha512');
  res.json({ hash: hash.toString('hex') });
});

// ✅ Offload CPU-bound work to a Worker Thread —
// the main thread's event loop stays free
// (covered in full in [Worker Threads and Cluster])
app.get('/hash', async (req, res) => {
  const hash = await runInWorker('hash', req.query.password);
  res.json({ hash: hash.toString('hex') });
});
```

This is a central idea that many topics in this section will return to: "Node is bad for CPU-bound work" isn't an absolute truth — it's a consequence of the single-JS-thread architecture, and that consequence has concrete mitigations (Worker Threads, Cluster, offloading to separate services).

## EventEmitter — the foundation Node is built on

Most of Node's built-in APIs (the HTTP server, streams, processes) are `EventEmitter`s under the hood.

```ts
import { EventEmitter } from 'node:events';

const emitter = new EventEmitter();

emitter.on('userCreated', (user) => {
  console.log('Welcome email queued for', user.email);
});

emitter.emit('userCreated', { email: 'alice@example.com' });
```

### Senior nuance #1: the `'error'` event is a special case

```ts
// ❌ If an EventEmitter (or Stream, Socket, ...) has NO
// 'error' listener and an 'error' event is emitted — Node
// throws and (by default) CRASHES THE PROCESS, even if the
// emitter is wrapped in try/catch
const socket = net.connect(...);
socket.emit('error', new Error('ECONNRESET')); // → process crash

// ✅ ALWAYS subscribe to 'error' on EventEmitters that can
// emit it (sockets, streams, child processes)
socket.on('error', (err) => {
  logger.error('Socket error', err);
});
```

This isn't an abstract "just in case" recommendation — this behavior is specific to `'error'` among all Node events, and it regularly catches even experienced developers working with network sockets or child processes.

### Senior nuance #2: memory leaks via accumulating listeners

```ts
// ❌ On every HTTP request we subscribe to a shared emitter
// but never unsubscribe — listeners accumulate, and Node
// will print "MaxListenersExceededWarning" past 10 listeners
// by default — a real signal of a memory leak (each listener
// holds a closure over req/res)
app.get('/subscribe', (req, res) => {
  eventBus.on('update', (data) => res.write(JSON.stringify(data)));
});

// ✅ Remove the listener when the connection closes
app.get('/subscribe', (req, res) => {
  const handler = (data: unknown) => res.write(JSON.stringify(data));
  eventBus.on('update', handler);
  req.on('close', () => eventBus.off('update', handler));
});
```

`MaxListenersExceededWarning` is often dismissed as "just a warning, safe to ignore" — but in practice it's almost always a sign of a leak: either a missing unsubscribe, or an emitter created in the wrong place (e.g., a new `EventEmitter` per request instead of one shared instance).

## process — the interface to the environment your app runs in

```ts
process.env.NODE_ENV     // environment variables — configuration (see 12-factor app)
process.argv             // command-line arguments
process.pid               // process PID — for logs/monitoring
process.exitCode          // exit code (0 = success, !=0 = failure for CI/orchestrator)
```

### Senior nuance: graceful shutdown via signals

```ts
// ❌ The process is killed instantly (docker stop, k8s rolling
// update) — active requests and DB connections are cut off mid-flight
process.on('SIGTERM', () => process.exit(0));

// ✅ Graceful shutdown: stop accepting new connections, let
// in-flight requests finish, close the DB connection pool
process.on('SIGTERM', async () => {
  server.close(() => {           // stop accepting new connections
    db.pool.end().then(() => {   // close DB connections
      process.exit(0);
    });
  });

  // safety net: force-exit after 10s if something hangs
  setTimeout(() => process.exit(1), 10_000);
});
```

This connects directly to how an orchestrator (Kubernetes, ECS) rolls out deploys: `SIGTERM` is sent **before** the container is killed (`SIGKILL` follows after a grace period, typically 30s). An app that doesn't handle `SIGTERM` drops users' active requests on every deploy — a common cause of "weird errors that only happen during deploys," which interviewers like to probe backend candidates on.

## The npm ecosystem: scale as both an advantage and a risk

```txt
Advantage:
  almost any task (parsing, validation, database access,
  cryptography) has already been solved and published on npm

Risk (supply chain):
  a typical Node project has HUNDREDS of transitive
  dependencies — you're trusting code you didn't write and
  probably haven't read, from dozens of different authors
```

Senior-level points worth knowing:

```txt
- package-lock.json / yarn.lock / pnpm-lock.yaml — pin the
  EXACT versions of the entire dependency tree. Without a lock
  file, "npm install" in CI vs. on a developer's machine can
  install different patch versions of transitive packages —
  a classic source of "works on my machine, broken in prod"

- Semver (^1.2.3 vs ~1.2.3 vs 1.2.3) — "^" allows automatic
  minor/patch updates; for production code, many teams prefer
  exact versions + Dependabot/Renovate with review, rather
  than "silent" auto-updates

- npm audit / Snyk and similar — scanning dependencies for
  known vulnerabilities; this isn't "optional for cautious
  teams," it's part of a standard CI pipeline for any serious
  backend project

- postinstall scripts — a package can run arbitrary code at
  install time; this is a real attack vector (there are known
  cases of popular packages being compromised to mine crypto
  or steal tokens via postinstall)
```

## What's next in this section

```txt
[V8 and the Runtime]       — how V8 executes JS, JIT compilation
[The Event Loop]            — event loop phases, execution order
[Microtasks, Macrotasks,
 and process.nextTick]      — Promise vs setTimeout vs nextTick
[libuv and the Thread Pool] — what's REALLY async vs. "async via
                               a thread pool"
[Worker Threads and Cluster]— using multiple CPU cores
[Streams and Backpressure]  — handling large amounts of data
[Memory and Garbage
 Collection]                 — heap, memory leaks, GC pauses
[CommonJS vs ESM]            — the two module systems and their differences
```

## Common interview mistakes

- **"Node = V8"** — not distinguishing the engine (JS execution, memory, GC) from the runtime (provides fs/net/process via C++ bindings and libuv).

- **"Node is single-threaded, full stop"** — without clarifying that single-threadedness applies to JS execution, while the process itself uses a Thread Pool and V8's GC threads.

- **"Node is bad for CPU work"** stated without explaining the MECHANISM (blocking the single event loop thread) and without mentioning mitigations (Worker Threads, offloading to a separate service).

- **Not subscribing to `'error'` on an EventEmitter/Stream/Socket** — and not knowing that an unhandled `'error'` crashes the process, unlike any other event.

- **Ignoring `SIGTERM`** — not understanding the connection between process signals and graceful shutdown during deploys in a containerized environment.

- **Underestimating supply chain risk** — treating npm dependencies as "free and safe" code with no mention of lock files, a semver strategy, or vulnerability auditing.
