# Node.js Interview Questions (Middle → Senior)

---

# 1. What is Node.js?

Node.js is a JavaScript Runtime Environment built on the V8 engine and the libuv library.

---

# 2. How does Node.js differ from the browser?

Node provides:

- File System
- Process API
- Network API
- Streams
- Crypto

which are not available in the browser.

---

# 3. What is V8?

A JavaScript Engine that executes JS code.

Responsible for:

- Parsing
- Compilation
- Optimization
- Garbage Collection

---

# 4. What is the Event Loop?

A mechanism for processing asynchronous operations.

The Event Loop executes callbacks when the Call Stack becomes empty.

---

# 5. What are the main Event Loop phases?

```txt
Timers
Pending Callbacks
Poll
Check
Close Callbacks
```

---

# 6. What is the Microtask Queue?

A queue for:

```txt
Promise.then
catch
finally
queueMicrotask
```

---

# 7. What is the Macrotask Queue?

A queue for:

```txt
setTimeout
setInterval
setImmediate
I/O callbacks
```

---

# 8. Why does Promise.then run before setTimeout?

Because Microtasks have higher priority than Macrotasks.

---

# 9. What is process.nextTick?

A special Node.js queue that runs before Microtasks.

---

# 10. Why is process.nextTick dangerous?

You can create starvation and block the Event Loop.

---

# 11. What is libuv?

A library that implements the Event Loop, Thread Pool, and asynchronous I/O.

---

# 12. Is Node.js single-threaded or multi-threaded?

JavaScript code runs on a single thread.

But Node uses:

- Thread Pool
- Worker Threads
- Cluster

---

# 13. What is the Thread Pool?

A pool of libuv worker threads.

By default:

```txt
4 threads
```

---

# 14. Which operations use the Thread Pool?

- fs
- crypto
- zlib
- dns.lookup

---

# 15. Why doesn't fs.readFile block the application?

Because the operation runs in the libuv Thread Pool.

---

# 16. What are Worker Threads?

Separate JavaScript threads for CPU-bound tasks.

---

# 17. When should you use Worker Threads?

- Image Processing
- PDF Generation
- Encryption
- Machine Learning

---

# 18. What is Cluster?

A mechanism for launching multiple Node processes to use multiple CPU cores.

---

# 19. How does Worker differ from Cluster?

Worker:

```txt
Threads
```

---

Cluster:

```txt
Processes
```

---

# 20. What are Streams?

A mechanism for processing data in chunks without loading the entire content into memory.

---

# 21. What types of Streams exist?

- Readable
- Writable
- Duplex
- Transform

---

# 22. What is Backpressure?

A mechanism for regulating data transfer speed to prevent memory overflow.

---

# 23. Why is Stream better than readFile for large files?

Because data is processed chunk-by-chunk.

---

# 24. What is a Buffer?

A special Node object for working with binary data.

---

# 25. What is the Heap?

The memory region where objects and arrays are stored.

---

# 26. What is the Stack?

The function call stack.

---

# 27. What is the Garbage Collector?

A mechanism for automatic memory deallocation.

---

# 28. How does Mark-and-Sweep work?

GC marks reachable objects, then removes the rest.

---

# 29. What is Generational GC?

Splitting objects into:

```txt
Young Generation
Old Generation
```

---

# 30. What is a Memory Leak?

A situation where objects are no longer needed but are still reachable by GC.

---

# 31. What are the most common causes of Memory Leaks?

- Global arrays
- Closures
- Event Listeners
- Cache without cleanup

---

# 32. What does process.memoryUsage() show?

Process memory statistics:

- rss
- heapUsed
- heapTotal

---

# 33. What is CommonJS?

Node.js module system:

```js
require()
module.exports
```

---

# 34. What are ES Modules?

The modern standard:

```js
import
export
```

---

# 35. What is the advantage of ESM?

- Tree Shaking
- Static Analysis
- Dynamic Import
- Top-Level Await

---

# 36. What is EventEmitter?

The basic event mechanism of Node.js.

---

# 37. What is a CPU-bound task?

A task that loads the processor.

---

# 38. What is an I/O-bound task?

A task that waits for external resources.

---

# 39. Why is Node good for I/O-bound tasks?

Because the Event Loop is not blocked by waiting.

---

# 40. Why is Node poorly suited for CPU-heavy tasks?

Because the main JS thread is single.

---

# 41. What is an Unhandled Promise Rejection?

A Promise error that was not handled with catch.

---

# 42. What is Dynamic Import?

```js
await import('./module.js');
```

Allows loading a module lazily.

---

# 43. What is Top-Level Await?

Using await outside a function in ES Modules.

---

# 44. How do you diagnose Node application performance?

- Profiling
- Heap Snapshot
- EXPLAIN ANALYZE (if the problem is in the DB)
- Clinic.js
- Chrome DevTools

---

# 45. The Most Popular Senior Question

Why is Node.js able to handle thousands of connections simultaneously?

Answer:

Because Node uses the Event Loop and non-blocking I/O. Instead of creating a thread per request, it offloads asynchronous operations to the operating system or libuv and continues serving other connections.
