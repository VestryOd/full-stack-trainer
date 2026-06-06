# libuv and Thread Pool

## The Most Common Misconception

People often say:

```txt
Node.js is single-threaded
```

---

That is not entirely true.

---

More accurately:

```txt
The JavaScript execution thread is single
```

---

But Node has additional threads internally.

---

# What is libuv

libuv is a C library that forms the foundation of Node.js.

---

It is responsible for:

```txt
Event Loop
Thread Pool
Timers
Networking
Async I/O
```

---

In practice:

```txt
Node.js
 ├── V8
 └── libuv
```

---

# Why libuv Is Needed

V8 can:

```txt
execute JavaScript
```

---

But V8 cannot:

```txt
read files
work with the network
communicate with the OS
```

---

libuv handles that.

---

# What Happens with fs.readFile()

Code:

```js
fs.readFile('file.txt', callback);
```

---

Simplified flow:

```txt
JavaScript
     ↓
Node API
     ↓
libuv
     ↓
Thread Pool
     ↓
OS
```

---

# Step by Step

Step 1

JS calls:

```js
fs.readFile(...)
```

---

Step 2

Node passes the task to libuv.

---

Step 3

libuv sends the task to the Thread Pool.

---

Step 4

The JavaScript thread continues working.

---

Step 5

When reading is complete:

```txt
the callback enters the Event Loop queue
```

---

Step 6

The Event Loop executes the callback.

---

# The Key Point

While the file is being read:

```txt
the JavaScript thread is free
```

---

So the application is not blocked.

---

# Thread Pool

libuv contains a pool of threads.

---

By default:

```txt
4 worker threads
```

---

Can be changed:

```bash
UV_THREADPOOL_SIZE=8
```

---

For example:

```bash
UV_THREADPOOL_SIZE=16
```

---

# Which Operations Use the Thread Pool

A very important question.

---

Uses Thread Pool:

```txt
fs
crypto
zlib
dns.lookup
```

---

For example:

```js
fs.readFile()
```

---

```js
crypto.pbkdf2()
```

---

```js
zlib.gzip()
```

---

# What Does NOT Use the Thread Pool

A very popular interview question.

---

Network operations typically use:

```txt
OS Event Notification APIs
```

---

For example:

```js
http.get(...)
```

---

does not occupy a worker thread.

---

# Why This Matters

Imagine:

```js
Promise.all([
  fs.readFile(...),
  fs.readFile(...),
  fs.readFile(...),
  fs.readFile(...),
  fs.readFile(...),
]);
```

---

Thread Pool:

```txt
4 threads
```

---

The first 4 tasks start immediately.

---

The fifth will wait.

---

# CPU Heavy Problem

Imagine:

```js
crypto.pbkdf2(...)
```

---

A very heavy operation.

---

If you run:

```txt
100 crypto tasks simultaneously
```

---

The Thread Pool fills up.

---

New fs operations will have to wait.

---

# How to Spot the Problem

Very often:

```txt
CPU is normal
```

---

But:

```txt
Latency is growing
```

---

Because tasks are waiting for a free worker thread.

---

# Can You Increase the Thread Pool Indefinitely?

No.

---

Why?

---

Each thread:

```txt
uses memory
creates context switches
loads the CPU
```

---

Typically:

```txt
4-16
```

is sufficient.

---

# A Common Question

Is Node.js multi-threaded or single-threaded?

---

The correct answer:

JavaScript code runs on a single thread.

But Node uses libuv, which has a Thread Pool and can execute some operations in parallel.

---

# Interview Answer

libuv is the library at the core of Node.js. It handles the Event Loop, asynchronous I/O, and the Thread Pool. Operations such as fs, crypto, and zlib run on worker threads, which prevents blocking the main JavaScript thread.
