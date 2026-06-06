# Memory, Heap, Stack, and Garbage Collection

## The Most Dangerous Production Problem

Most Node applications don't crash because of the Event Loop.

---

The usual culprit:

```txt
Memory Leak
```

---

# How Memory Is Structured

Simplified:

```txt
Stack
Heap
```

---

# Stack

Stores:

```txt
Function Calls
Primitive Values
References
```

---

Example:

```js
function sum(a, b) {
  return a + b;
}
```

---

When called, a:

```txt
Stack Frame
```

is created.

---

After the function completes:

```txt
it is removed
```

---

# Heap

This is where these live:

```txt
Objects
Arrays
Functions
Closures
```

---

Example:

```js
const user = {
  name: 'Max'
};
```

---

The object will be stored in the Heap.

---

# Why the Heap Matters

Almost all memory leaks happen here.

---

# Garbage Collector

GC automatically frees memory.

---

The core idea:

```txt
Remove unreachable objects
```

---

# Reachability

An object is considered alive if it can be reached.

---

Example:

```js
const user = {
  name: 'Max'
};
```

---

The object is reachable.

---

# An Unreachable Object

```js
let user = {
  name: 'Max'
};

user = null;
```

---

The old object is no longer needed by anyone.

---

GC can remove it.

---

# Mark and Sweep

The main GC algorithm.

---

Step 1

Mark.

---

GC starts traversing from Root Objects.

---

For example:

```txt
global
closures
stack
```

---

Marks reachable objects.

---

Step 2

Sweep.

---

All unmarked objects:

```txt
are removed
```

---

# Generational GC

A very popular interview question.

---

Observation:

Most objects have a short lifetime.

---

For example:

```js
req
res
temporary arrays
```

---

So V8 divides memory into:

```txt
Young Generation
Old Generation
```

---

# Young Generation

New objects.

---

Usually collected frequently.

---

Very fast.

---

# Old Generation

Long-lived objects.

---

For example:

```txt
Cache
Singletons
Global Objects
```

---

Collection is significantly more expensive.

---

# Why GC Causes Lag

During some phases:

```txt
JavaScript is paused
```

---

This is called:

```txt
Stop The World
```

---

Modern V8 reduces these pauses but does not eliminate them entirely.

---

# Memory Leak

A very popular interview topic.

---

# Example 1

A global array.

---

```js
const cache = [];

setInterval(() => {
  cache.push(hugeObject);
}, 1000);
```

---

Memory grows indefinitely.

---

# Example 2

Unremoved listeners.

---

```js
emitter.on('event', handler);
```

---

But:

```js
removeListener()
```

is never called.

---

This creates a leak.

---

# Example 3

Closures.

---

```js
function create() {

  const hugeArray = [];

  return () => {
    console.log(hugeArray.length);
  };
}
```

---

The closure keeps hugeArray alive.

---

GC cannot remove the array.

---

# Symptoms of a Memory Leak

These gradually grow:

```txt
Heap Usage
RSS
GC Time
```

---

Eventually:

```txt
OOM
```

---

Out Of Memory.

---

# How to Find Leaks

The most popular tools.

---

```txt
Chrome DevTools
Heap Snapshot
Node Inspector
clinic.js
```

---

# Heap Snapshot

Lets you see:

```txt
what is consuming memory
```

---

Very commonly used in production investigations.

---

# Process Memory

```js
console.log(
  process.memoryUsage()
);
```

---

Shows:

```txt
rss
heapUsed
heapTotal
external
```

---

# RSS

Resident Set Size.

---

The total memory of the process.

---

# heapUsed

The most interesting metric.

---

How much of the Heap is actually in use.

---

# A Very Popular Question

Why does memory not decrease after GC?

---

Because:

```txt
V8 may retain allocated memory
for future use
```

---

And not return it to the OS immediately.

---

# A Common Question

Why can an application slow down when there are many objects?

---

Answer:

GC has to traverse more objects.

---

This increases:

```txt
GC pressure
Pause time
CPU usage
```

---

# Senior Interview Answer

V8 uses automatic garbage collection based on Mark-and-Sweep and Generational GC algorithms. Objects are allocated in the Heap and removed when they become unreachable. The most common causes of memory leaks in Node.js are global collections, uncleaned Event Listeners, and closures that hold large objects in memory.
