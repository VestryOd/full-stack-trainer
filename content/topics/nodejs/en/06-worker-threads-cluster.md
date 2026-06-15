# Worker Threads and Cluster

## Three ways to use more than one core — and they solve different problems

```txt
Thread Pool (libuv)  — does NOT run your JS. Solves the
                        problem "operation X has no async
                        OS API" (see [libuv and the Thread Pool])

Worker Threads        — runs YOUR JS code in a separate
                        thread, with its own V8 instance and
                        Event Loop. Solves the problem "heavy
                        computation blocks the main thread"

Cluster / multiple
processes              — multiple FULLY independent Node
                        processes sharing one port. Solves
                        the problem "one process uses one
                        CPU core"
```

A common mistake is treating these as interchangeable "ways to do parallelism." In practice they're solutions for DIFFERENT problems, and a mature architecture usually combines them: Cluster/multiple containers — to utilize all cores for HTTP traffic, and Worker Threads — inside EACH of those processes, so specific heavy operations don't block that particular process.

## Worker Threads: not just "a new thread" — a new V8 instance

```txt
Each Worker has:
  - its own V8 instance (own heap, own GC — independent
    from the main thread, see [Memory and Garbage Collection])
  - its own Event Loop (its own microtask/macrotask queue)
  - its own global scope

NOT shared with the main thread:
  - regular variables/objects (passed via structured clone —
    this is a COPY, not a reference)

CAN be shared (explicitly):
  - SharedArrayBuffer + Atomics — the only way to get real
    shared memory between threads
```

```ts
// main.ts
import { Worker } from 'node:worker_threads';

const worker = new Worker('./hash-worker.js', {
  workerData: { password: 'user-input', cost: 100_000 },
});

worker.on('message', (hash) => console.log('Hash:', hash));
worker.on('error', (err) => console.error('Worker crashed:', err));
```

```ts
// hash-worker.js
import { parentPort, workerData } from 'node:worker_threads';
import crypto from 'node:crypto';

const hash = crypto.pbkdf2Sync(workerData.password, 'salt', workerData.cost, 64, 'sha512');
parentPort.postMessage(hash.toString('hex'));
```

### Senior nuance #1: creating a Worker is NOT free

```txt
Creating a Worker requires:
  - initializing a NEW V8 instance (tens of milliseconds)
  - allocating memory for a separate heap

❌ Creating a Worker PER REQUEST — the initialization
   overhead can exceed the parallelism gain for short tasks:

  app.post('/hash', (req, res) => {
    const worker = new Worker('./hash-worker.js', { workerData: req.body });
    worker.on('message', (h) => res.json({ hash: h }));
  });

✅ Worker Pool — a fixed set of workers reused across
   requests (the pattern implemented by libraries like
   piscina/workerpool — the typical choice in real
   projects instead of a hand-rolled implementation):

  const pool = new Piscina({ filename: './hash-worker.js' });
  app.post('/hash', async (req, res) => {
    const hash = await pool.run(req.body); // reuses a worker from the pool
    res.json({ hash });
  });
```

### Senior nuance #2: passing data — a copy unless Transferable/SharedArrayBuffer

```ts
// ❌ Passing a large Buffer/array via postMessage —
// structured clone COPIES the data (2x memory during the
// transfer, plus serialization time for large payloads)
worker.postMessage({ buffer: largeBuffer }); // largeBuffer gets COPIED

// ✅ Transferable objects — transfer "ownership" of an
// ArrayBuffer with no copy (after transfer, the original
// buffer becomes unusable in the sending thread)
worker.postMessage({ buffer: largeArrayBuffer }, [largeArrayBuffer]);

// ✅ SharedArrayBuffer + Atomics — both threads see the SAME
// memory; requires explicit synchronization (Atomics.wait/
// notify), with all the data-race risks familiar from
// "real" multithreaded programming
const shared = new SharedArrayBuffer(1024);
worker.postMessage({ shared });
```

`SharedArrayBuffer` is the rare case in Node where genuine data races, familiar from languages with shared memory (C++/Java), become possible. For most tasks (send input, get a result back), a Transferable ArrayBuffer is sufficient and easier to justify in an interview.

## Cluster: multiple processes, one shared port

```ts
import cluster from 'node:cluster';
import os from 'node:os';

if (cluster.isPrimary) {
  const numCPUs = os.availableParallelism(); // modern API, see below
  for (let i = 0; i < numCPUs; i++) cluster.fork();

  cluster.on('exit', (worker) => {
    console.log(`Worker ${worker.process.pid} died, restarting`);
    cluster.fork(); // graceful restart of the dead worker
  });
} else {
  startHttpServer(); // each worker process is its own HTTP server
}
```

### How multiple processes listen on ONE port

```txt
The primary process creates the server socket and hands the
file descriptor to each worker process (or uses SO_REUSEPORT
on modern OSes, where the kernel itself distributes incoming
connections between processes).

Default distribution strategy (Linux, "round-robin" in the
cluster module):
  Primary accepts the connection → hands it off to one of
  the worker processes round-robin

  (on Windows and with SO_REUSEPORT — the OS balances on its
  own, without the primary's involvement)
```

### Senior nuance: Cluster and stateful connections (WebSocket)

```txt
The problem: round-robin distributes NEW connections across
processes, but each WebSocket client stays "pinned" to the
process that accepted it. If that process keeps
presence/state in memory — the other processes don't know
about it.

This is the SAME "connection pinning"/"sticky session" issue
covered for load balancers in [WebSockets and Realtime
Systems] and [Scalability and Load Balancing] — Cluster just
moves the same problem from the "multiple servers" level to
the "multiple processes on one server" level. The solution is
also the same — Redis Pub/Sub for cross-process
communication, presence stored in Redis instead of in memory.
```

## Cluster vs containers — is Cluster really "obsolete"

```txt
Old model (a single bare-metal server):
  1 server, 8 cores → 1 Node process uses 1 core →
  Cluster with 8 worker processes utilizes all 8

Modern model (Kubernetes/ECS):
  The deployment is configured with N "replicas"
  (pods/containers), each a separate Node process. The
  orchestrator distributes replicas across cores/nodes of
  the cluster, and a Load Balancer/Service spreads traffic
  across replicas.
```

It's tempting to conclude "Cluster is never needed anymore" — but that's not quite right:

```txt
Nuance: if a CONTAINER is allocated, say, 4 vCPUs, and a
SINGLE Node process runs inside it — that process still uses
only 1 core for JS execution (event loop is single-threaded),
leaving the other 3 vCPUs of the container idle for the
CPU-bound part of the workload (though the Thread Pool/Worker
Threads use them partially).

Option A: 1 container = 1 Node process, more replicas
  (4 replicas at 1 vCPU each instead of 1 replica at 4 vCPU) —
  usually preferred in k8s: simpler health checks, simpler
  rolling updates, per-replica metrics

Option B: 1 container = Cluster with multiple worker
  processes (e.g., via PM2 in cluster mode) — sometimes used
  when replica-level orchestration is constrained or
  expensive (per-replica sidecar overhead)
```

The strong answer is neither "Cluster is obsolete" nor "Cluster is always needed," but an explicit trade-off: Cluster inside a container gives finer-grained CPU utilization of that one replica, but complicates observability (logs/metrics from multiple processes in one container) and graceful shutdown (you need to correctly stop ALL worker processes on `SIGTERM`, see [Node.js Fundamentals]).

## Decision summary table

```txt
Task                              → Solution
─────────────────────────────────────────────────────
fs/crypto/zlib operation with     → Thread Pool (built in,
no async OS API                      just await/.promises)

Heavy computation (image           → Worker Threads (via a
processing, custom hashing,          worker pool — piscina)
parsing large documents)

Utilizing all CPU cores of a       → multiple processes:
server/container for HTTP             Cluster OR multiple
traffic                                container replicas
                                        (preferred in k8s)

Coordinating state across          → Redis (Pub/Sub, presence) —
processes/replicas                    NOT in-memory, see
                                        [WebSockets and Realtime Systems]
```

## Common interview mistakes

- **"Worker Threads solve the same problem as the Thread Pool"** — failing to distinguish "running YOUR JS in a separate thread" from "delegating operations with no async OS API to libuv's background threads."

- **Creating a Worker per request** — not mentioning the V8 instance initialization overhead and the worker pool pattern (piscina/workerpool) as the standard solution.

- **Not knowing that data passed to a Worker is copied by default** — confusing a plain `postMessage` with Transferable objects and SharedArrayBuffer, and not understanding the cost of structured cloning for large payloads.

- **"Cluster is fully obsolete because of Docker"** — without the nuance that a single Node process inside a multi-core container still uses only one core for the event loop, and Cluster/multiple replicas solve this at different levels with different trade-offs.

- **Not connecting Cluster to the sticky session problem** — for WebSocket/stateful connections, Cluster creates the same connection-pinning problem as multiple servers behind a load balancer, solved the same way (Redis).
