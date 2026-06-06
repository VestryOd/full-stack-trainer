# Event Loop

## The Most Important Concept in Node.js

If an interviewer asks only one Node.js question, the probability is very high that it will be:

```txt
What is the Event Loop?
```

---

# Why the Event Loop Is Needed

JavaScript runs on a single thread.

---

For example:

```js
console.log('A');
console.log('B');
console.log('C');
```

---

Result:

```txt
A
B
C
```

---

Everything executes sequentially.

---

# The Problem

Imagine:

```js
const data = fs.readFileSync('huge-file.txt');
```

---

Reading takes:

```txt
5 seconds
```

---

What happens?

---

The entire thread is blocked.

---

No other code executes.

---

# Node.js Solution

Asynchrony.

---

Instead of:

```js
readFileSync()
```

use:

```js
readFile()
```

---

Then:

```txt
Node starts the operation
↓
does not wait for it to finish
↓
continues executing code
```

---

But this raises the question:

```txt
How do you know
when the operation finishes?
```

---

That is what the Event Loop is for.

---

# What is the Event Loop

Simplified:

```txt
while (true) {
  take a task
  execute the task
}
```

---

In practice it is more complex.

---

The Event Loop constantly checks:

```txt
are there any ready callbacks?
```

---

If yes:

```txt
execute
```

---

If no:

```txt
wait
```

---

# The Core Idea

JavaScript executes code.

---

Asynchronous operations are offloaded to:

```txt
OS
libuv
Thread Pool
```

---

When the operation finishes:

```txt
the callback enters the queue
```

---

The Event Loop picks up the callback.

---

Executes it.

---

# Architecture

```txt
Call Stack
    ↓
Event Loop
    ↓
Task Queues
```

---

# Call Stack

The function execution stack.

---

For example:

```js
foo();
```

---

The function enters the stack.

---

When it finishes:

```txt
it is removed from the stack
```

---

# A Very Important Rule

While the stack is not empty:

```txt
the Event Loop executes nothing
```

---

Example:

```js
while(true){}
```

---

The Event Loop will never get control.

---

The server will hang.

---

# Main Phases of the Event Loop

Simplified:

```txt
Timers
↓
Pending Callbacks
↓
Idle / Prepare
↓
Poll
↓
Check
↓
Close Callbacks
```

---

# Timers

Executes:

```js
setTimeout()
setInterval()
```

---

# Pending Callbacks

Some system callbacks.

---

Rarely asked about in detail.

---

# Poll

The most important phase.

---

Handles:

```txt
I/O
Database
Network
Filesystem
```

---

Most of Node's work happens here.

---

# Check

Executes:

```js
setImmediate()
```

---

# Close Callbacks

For example:

```js
socket.on('close')
```

---

# Simplified Diagram

```txt
Timers
↓
Poll
↓
Check
↓
Timers
↓
Poll
↓
Check
```

---

# Example

```js
setTimeout(() => {
  console.log('timeout');
}, 0);

console.log('sync');
```

---

Result:

```txt
sync
timeout
```

---

Why?

---

Because all synchronous code executes first.

---

Only then does the Event Loop start processing queues.

---

# Why setTimeout(0) Does Not Mean Immediately

A very popular question.

---

It means:

```txt
no earlier than 0 ms from now
```

---

But not:

```txt
right now
```

---

The Event Loop still has to reach the Timers phase.

---

# Blocking the Event Loop

A very important topic.

---

Bad:

```js
for(let i=0; i<10000000000; i++) {}
```

---

What happens?

---

The main thread is busy.

---

The Event Loop stops working.

---

The API stops responding.

---

# How to Avoid Blocking

Use:

```txt
Worker Threads
Queues
Streams
Chunk Processing
```

---

# Interview Answer

The Event Loop is the mechanism that coordinates asynchronous operations in Node.js. It continuously checks the queues of ready tasks and executes them when the call stack becomes empty. Thanks to the Event Loop, Node can efficiently handle a large number of I/O operations without creating a separate thread per request.
