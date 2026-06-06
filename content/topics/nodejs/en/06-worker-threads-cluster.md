# Worker Threads and Cluster

## The Main Question

If Node has a Thread Pool:

```txt
Why do we need Worker Threads?
```

---

Because:

```txt
The Thread Pool does not execute JavaScript code
```

---

It executes:

```txt
fs
crypto
zlib
dns
```

---

But if we have:

```js
while(true){}
```

---

The Thread Pool won't help.

---

# CPU-bound Tasks

For example:

```txt
image processing
video encoding
pdf generation
machine learning
hashing
```

---

These run on the main JS thread.

---

And block the Event Loop.

---

# The Solution

Worker Threads.

---

# What is a Worker Thread

A separate JavaScript thread.

---

Architecture:

```txt
Main Thread
      │
      ├── Worker 1
      ├── Worker 2
      └── Worker 3
```

---

Each Worker has:

```txt
its own Event Loop
its own V8 Instance
its own Call Stack
```

---

# Creating a Worker

```js
const { Worker } = require('worker_threads');

new Worker('./worker.js');
```

---

# Messaging

A Worker does not share memory directly.

---

Uses:

```txt
postMessage()
```

---

Example:

Main:

```js
worker.postMessage(100);
```

---

Worker:

```js
parentPort.on('message', value => {
  ...
});
```

---

# Why This Matters

Now a heavy task runs:

```txt
not on the Main Thread
```

---

The Event Loop stays free.

---

# When to Use Worker Threads

Use for:

```txt
CPU-bound tasks
```

---

For example:

```txt
image resize
PDF rendering
video processing
AI
encryption
```

---

# When NOT to Use

Regular:

```txt
REST API
DB Queries
HTTP Requests
```

---

Workers are not needed for these.

---

# Cluster

A very popular interview topic.

---

# Why Cluster Is Needed

A Node process uses:

```txt
1 CPU Core
```

---

Imagine a server with:

```txt
8 CPU cores
```

---

Result:

```txt
only 1 out of 8 is used
```

---

# The Solution

Cluster.

---

# What Cluster Does

Creates multiple processes.

---

Architecture:

```txt
Master
  │
  ├── Process 1
  ├── Process 2
  ├── Process 3
  └── Process 4
```

---

Each process:

```txt
has its own Event Loop
has its own Heap
has its own V8
```

---

# Important

These are NOT threads.

---

These are full processes.

---

# Shared Memory

Worker Threads:

```txt
can use SharedArrayBuffer
```

---

Cluster:

```txt
memory is not shared
```

---

# Worker vs Cluster

Worker Threads:

```txt
multi-threading
single process
```

---

Cluster:

```txt
multiple processes
multiple CPU cores
```

---

# What Is Used More Today

An interesting question.

---

In the past:

```txt
Cluster
```

was used constantly.

---

Today it is more common to use:

```txt
Docker
Kubernetes
PM2
multiple containers
```

---

So Cluster has become less popular.

---

# Practical Example

Imagine:

```txt
4 CPU cores
```

---

Option 1

```txt
1 Node Process
```

Uses:

```txt
1 core
```

---

Option 2

```txt
4 Cluster Processes
```

Uses:

```txt
4 cores
```

---

# A Common Question

Worker Threads or Cluster for image processing?

---

Usually:

```txt
Worker Threads
```

---

Because it is a CPU-heavy task.

---

# A Common Question

Worker Threads or Cluster for an API?

---

Usually:

```txt
Cluster
```

or multiple containers.

---

# Interview Answer

Worker Threads allow CPU-intensive JavaScript code to run in separate threads and are used for computationally heavy tasks. Cluster creates multiple Node.js processes and enables the use of multiple CPU cores for scaling server applications. Worker Threads solve the CPU-bound computation problem, while Cluster solves the problem of utilizing only a single CPU core.
