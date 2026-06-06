# Microtasks, Macrotasks, and process.nextTick

## The Favorite Topic of Interviewers

A very common question involves code like this:

```js
setTimeout(() => {
  console.log('timeout');
}, 0);

Promise.resolve().then(() => {
  console.log('promise');
});

console.log('sync');
```

---

What will be printed?

---

Answer:

```txt
sync
promise
timeout
```

---

Why?

---

Because different task queues exist.

---

# Task Queues

Node has several queues.

---

Simplified:

```txt
nextTick Queue
↓
Microtask Queue
↓
Macrotask Queue
```

---

# Macrotasks

These go here:

```txt
setTimeout
setInterval
setImmediate
I/O callbacks
```

---

# Microtasks

These go here:

```txt
Promise.then
Promise.catch
Promise.finally
queueMicrotask
```

---

# The Main Rule

After the current code finishes:

```txt
All Microtasks run first
Then Macrotasks
```

---

# Example

```js
setTimeout(() => {
  console.log('timeout');
});

Promise.resolve().then(() => {
  console.log('promise');
});
```

---

Result:

```txt
promise
timeout
```

---

# Why Promise Runs First

Promise is in the:

```txt
Microtask Queue
```

---

setTimeout is in the:

```txt
Macrotask Queue
```

---

Microtasks always have priority.

---

# queueMicrotask

A special API.

---

```js
queueMicrotask(() => {
  console.log('microtask');
});
```

---

Works similarly to Promise.then.

---

# process.nextTick

The trickiest topic.

---

Node has a dedicated queue:

```txt
nextTick Queue
```

---

It has an even higher priority.

---

# Example

```js
process.nextTick(() => {
  console.log('tick');
});

Promise.resolve().then(() => {
  console.log('promise');
});
```

---

Result:

```txt
tick
promise
```

---

# Why?

Because the order is:

```txt
nextTick
↓
Microtasks
↓
Macrotasks
```

---

# Full Priority Order

```txt
Call Stack
↓
process.nextTick
↓
Promise Microtasks
↓
Timers
↓
I/O
↓
setImmediate
```

---

# A Very Popular Question

What will this code print?

```js
console.log('1');

setTimeout(() => {
  console.log('2');
});

Promise.resolve().then(() => {
  console.log('3');
});

console.log('4');
```

---

Answer:

```txt
1
4
3
2
```

---

Breakdown:

```txt
1 -> sync
4 -> sync
3 -> microtask
2 -> macrotask
```

---

# A More Complex Example

```js
console.log('1');

process.nextTick(() => {
  console.log('2');
});

Promise.resolve().then(() => {
  console.log('3');
});

setTimeout(() => {
  console.log('4');
});

console.log('5');
```

---

Answer:

```txt
1
5
2
3
4
```

---

Breakdown:

```txt
1 sync
5 sync

2 nextTick

3 Promise

4 timeout
```

---

# process.nextTick Danger

You can accidentally block the Event Loop.

---

Bad:

```js
function loop() {
  process.nextTick(loop);
}

loop();
```

---

What will happen?

---

The Event Loop will never reach the other queues.

---

We get starvation.

---

# setImmediate vs setTimeout

A very popular question.

---

```js
setImmediate(...)
```

runs in the phase:

```txt
Check
```

---

```js
setTimeout(...)
```

runs in the phase:

```txt
Timers
```

---

In regular code, the order is not guaranteed.

---

After I/O, typically the first to run will be:

```txt
setImmediate
```

---

# Senior Interview Answer

Node.js uses several task queues. The highest priority belongs to process.nextTick, followed by Promise-based microtasks, after which the Event Loop moves on to macrotasks such as setTimeout, setImmediate, and I/O callbacks. That is why Promise.then runs before setTimeout(0), and process.nextTick runs before Promise.then.
