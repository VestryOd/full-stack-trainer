# Node.js Fundamentals

## What is Node.js

Node.js is a JavaScript Runtime Environment.

It is very important to understand:

```txt
Node.js ≠ JavaScript
Node.js ≠ Framework
```

---

JavaScript is a language.

Node.js is a runtime environment.

---

# What "Runtime" Means

A runtime is a program that allows JavaScript code to be executed.

---

For example:

```js
console.log('Hello');
```

---

In the browser, this code is executed by:

```txt
Chrome
Firefox
Safari
```

---

On the server, it is executed by:

```txt
Node.js
```

---

# Why Node.js Was Created

Before Node, JavaScript existed almost exclusively in the browser.

---

In 2009, Ryan Dahl created Node.js.

The main idea:

```txt
An asynchronous server
without creating a thread per request
```

---

# Key Advantages of Node.js

## One Language

Frontend:

```txt
JavaScript / TypeScript
```

Backend:

```txt
JavaScript / TypeScript
```

---

## High Performance for I/O

Node is a great fit for:

```txt
REST API
GraphQL
WebSockets
Realtime applications
Proxy
Streaming
```

---

## Huge Ecosystem

npm contains millions of packages.

---

# Where Node Excels

I/O Bound tasks.

---

For example:

```txt
Database queries
HTTP requests
Redis
Files
Message queues
```

---

Node does not wait for operations to complete.

It continues serving other requests.

---

# Where Node Performs Worse

CPU-bound tasks.

---

For example:

```txt
Video encoding
Image processing
Machine Learning
Complex computations
```

---

Because the main JS thread is single.

---

# Core Parts of Node.js

Node consists of:

```txt
V8
Libuv
Event Loop
Thread Pool
Node APIs
```

---

Many developers think:

```txt
Node = V8
```

That is wrong.

V8 is only one part of Node.

---

# What Node Adds on Top of JavaScript

The browser does not have:

```js
fs.readFile()
```

---

Node does.

---

The browser does not have:

```js
process.env
```

---

Node does.

---

Node provides:

```txt
File System
Network APIs
Streams
Processes
Buffers
Crypto
Timers
```

---

# The Node.js Process

When you run:

```bash
node app.js
```

a:

```txt
Node Process
```

is created.

---

The process has:

```txt
Heap
Stack
Event Loop
Thread Pool
```

---

# Event Driven Architecture

Node is built around events.

---

Example:

```js
server.on('request', callback);
```

---

Event:

```txt
request
```

---

Handler:

```txt
callback
```

---

Most of Node works this way.

---

# EventEmitter

The foundation of the event model.

---

Example:

```js
emitter.on('userCreated', handler);
```

---

And then:

```js
emitter.emit('userCreated');
```

---

Many built-in Node APIs use EventEmitter.

---

# Key Takeaway

Node.js is a JavaScript Runtime optimized for asynchronous I/O.

Its strength is not in computations, but in efficiently handling a large number of concurrent I/O operations.
