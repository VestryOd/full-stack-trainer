# Worker Threads and Cluster

## Three ways to use more than one core — and they solve different problems

All three exist for the same reason. One Node process runs your JavaScript on a single CPU core, and CPU here is the central processing unit — the chip that executes code. The three tools are not interchangeable, because each one solves a different problem.

```txt
Thread Pool (libuv)  — does not run your JS at all. Solves
                        the problem "operation X has no
                        async operating-system API"
                        (see [libuv and the Thread Pool])

Worker Threads        — runs your own JS code in a separate
                        thread, with its own V8 instance and
                        Event Loop. Solves the problem "heavy
                        computation blocks the main thread"

Cluster / multiple
processes              — several fully independent Node
                        processes sharing one port. Solves
                        the problem "one process uses one
                        CPU core"
```

A common mistake is to treat these as interchangeable "ways to do parallelism". They are solutions for **different** problems, and a mature architecture usually combines two of them:

- Cluster, or several containers, to utilize all cores for HTTP traffic.
- Worker Threads inside **each** of those processes, so that specific heavy operations don't block that particular process.

## Worker Threads: not just "a new thread" — a new V8 instance

V8 is the JavaScript engine inside Node, and every Worker gets its own instance of it.

```txt
Each Worker has:
  - its own V8 instance (own heap, own garbage collector —
    independent from the main thread, see [Memory and
    Garbage Collection])
  - its own Event Loop (its own microtask/macrotask queue)
  - its own global scope

Not shared with the main thread:
  - regular variables and objects (passed via structured
    clone — this is a copy, not a reference)

Can be shared, but only explicitly:
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

### Senior nuance #1: creating a Worker is not free

```txt
Creating a Worker requires:
  - initializing a new V8 instance (tens of milliseconds)
  - allocating memory for a separate heap

❌ Creating a Worker per request — the initialization
   overhead can exceed the parallelism gain for short tasks:

  app.post('/hash', (req, res) => {
    const worker = new Worker('./hash-worker.js', {
      workerData: req.body,
    });
    worker.on('message', (h) => res.json({ hash: h }));
  });

✅ Worker Pool — a fixed set of workers reused across
   requests. Libraries such as piscina and workerpool
   implement this pattern, and in real projects they are
   the typical choice instead of writing your own:

  const pool = new Piscina({ filename: './hash-worker.js' });
  app.post('/hash', async (req, res) => {
    const hash = await pool.run(req.body); // reuses a pool worker
    res.json({ hash });
  });
```

### Senior nuance #2: passing data — a copy unless Transferable/SharedArrayBuffer

```ts
// ❌ Passing a large Buffer/array via postMessage —
// structured clone copies the data (2x memory during the
// transfer, plus serialization time for large payloads)
worker.postMessage({ buffer: largeBuffer }); // largeBuffer is copied

// ✅ Transferable objects — transfer "ownership" of an
// ArrayBuffer with no copy (after transfer, the original
// buffer becomes unusable in the sending thread)
worker.postMessage({ buffer: largeArrayBuffer }, [largeArrayBuffer]);

// ✅ SharedArrayBuffer + Atomics — both threads see the same
// memory; requires explicit synchronization (Atomics.wait/
// notify), with all the data-race risks familiar from
// "real" multithreaded programming
const shared = new SharedArrayBuffer(1024);
worker.postMessage({ shared });
```

`SharedArrayBuffer` is the rare case in Node where genuine data races become possible — the kind familiar from languages with shared memory (C++/Java). Most tasks only send input and get a result back. For those, a Transferable ArrayBuffer is sufficient, and it is easier to justify in an interview.

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

### How multiple processes listen on one port

```txt
The primary process creates the server socket and hands the
file descriptor to each worker process. On modern operating
systems it can use SO_REUSEPORT instead, where the kernel
itself distributes incoming connections between processes.

Default distribution strategy (Linux, "round-robin" in the
cluster module):
  Primary accepts the connection → hands it off to one of
  the worker processes round-robin

  (on Windows and with SO_REUSEPORT the operating system
  balances on its own, without the primary's involvement)
```

### Senior nuance: Cluster and stateful connections (WebSocket)

```txt
The problem: round-robin distributes new connections across
processes, but each WebSocket client stays "pinned" to the
process that accepted it. If that process keeps presence or
other state in memory, the other processes don't know
about it.

This is the same "connection pinning" / "sticky session"
issue covered for load balancers in [WebSockets and
Realtime Systems] and [Scalability and Load Balancing].
Cluster just moves the problem from the "multiple servers"
level to the "multiple processes on one server" level. The
solution is the same too: Redis Pub/Sub for cross-process
communication, and presence stored in Redis instead of in
memory.
```

## Cluster vs containers — is Cluster really "obsolete"

```txt
Old model (a single bare-metal server):
  1 server, 8 cores → 1 Node process uses 1 core →
  Cluster with 8 worker processes utilizes all 8

Modern model (Kubernetes, also written k8s, or Amazon ECS):
  The deployment is configured with N "replicas"
  (pods/containers), each a separate Node process. The
  orchestrator distributes replicas across cores/nodes of
  the cluster, and a Load Balancer/Service spreads traffic
  across replicas.
```

It's tempting to conclude "Cluster is never needed anymore" — but that's not quite right:

```txt
Nuance: suppose a container is allocated 4 virtual cores
(4 vCPU) and a single Node process runs inside it. That
process still uses only 1 core for JS execution, because the
event loop is single-threaded. The other 3 virtual cores of
the container stay idle for the CPU-bound part of the
workload (though the Thread Pool and Worker Threads use them
partially).

Option A: 1 container = 1 Node process, more replicas
  (4 replicas at 1 vCPU each instead of 1 replica at 4 vCPU) —
  usually preferred in Kubernetes: simpler health checks,
  simpler rolling updates, per-replica metrics

Option B: 1 container = Cluster with multiple worker
  processes (for example via PM2, a process manager for
  Node, in cluster mode) — sometimes used when replica-level
  orchestration is constrained or expensive (per-replica
  sidecar overhead)
```

The strong answer is neither "Cluster is obsolete" nor "Cluster is always needed". State the trade-off explicitly:

- **For Cluster:** inside a container it gives finer-grained CPU utilization of that one replica.
- **Against Cluster:** observability gets harder, because logs and metrics now come from several processes in one container.
- **Against Cluster:** graceful shutdown gets harder — on `SIGTERM` you have to stop **all** worker processes correctly (see [Node.js Fundamentals]).

## Decision summary table

```txt
Task                              → Solution
─────────────────────────────────────────────────────
fs/crypto/zlib operation with     → Thread Pool (built in,
no async operating-system API        just await/.promises)

Heavy computation (image           → Worker Threads (via a
processing, custom hashing,          worker pool — piscina)
parsing large documents)

Utilizing all CPU cores of a       → multiple processes:
server/container for HTTP             Cluster or several
traffic                                container replicas
                                         (preferred in k8s)

Coordinating state across          → Redis (Pub/Sub, presence)
processes/replicas                    — not in memory, see
                                         [WebSockets and
                                         Realtime Systems]
```

## Common interview mistakes

- **"Worker Threads solve the same problem as the Thread Pool"** — the two are different. Worker Threads run **your** JS in a separate thread. The Thread Pool delegates operations with no async operating-system API to libuv's background threads.

- **Creating a Worker per request** — not mentioning the overhead of initializing a V8 instance. The standard solution is the worker pool pattern (piscina/workerpool).

- **Not knowing that data passed to a Worker is copied by default** — confusing a plain `postMessage` with Transferable objects and `SharedArrayBuffer`. The cost of structured cloning for large payloads is missed as well.

- **"Cluster is fully obsolete because of Docker"** — a single Node process inside a multi-core container still uses only one core for the event loop. Cluster and multiple replicas both solve this, but at different levels and with different trade-offs.

- **Not connecting Cluster to the sticky session problem** — WebSocket and other stateful connections pin each client to one process. That is the same connection-pinning problem as multiple servers behind a load balancer, and it is solved the same way, with Redis.
