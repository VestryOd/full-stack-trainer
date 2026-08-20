# Microtasks, Macrotasks, and process.nextTick

## Why this is a favorite interview topic — and where the real depth is

The real depth of this topic is one question: **between what exactly does queue-switching happen, and how often?** Answer that, and you can explain a whole class of production bugs. The typical one sounds like this: "why does one slow request slow down **all** other requests, even though I use async/await everywhere?"

The shallow level is different. It is "memorize the order nextTick → microtasks → macrotasks" plus predicting the `console.log` output of short snippets. That is necessary, but it is not what makes a senior answer.

## Three queues — and when each of them drains

```txt
process.nextTick queue  — drains completely after any current
                           operation finishes: after the script's
                           synchronous code, after every microtask,
                           after every Event Loop phase callback

Microtask queue           — drains completely, including new
(Promise.then,              microtasks added while the current
queueMicrotask)              ones run. Happens after the current
                           operation finishes and after the
                           nextTick queue has drained

Macrotask queue            — the Event Loop moves to the next
(setTimeout, setImmediate,   macrotask only once both queues
I/O callbacks)                above are completely empty
```

The key detail most explanations skip: this doesn't happen **once**, "after the script's synchronous block". It happens **after every callback**, wherever that callback runs. It may be one of several I/O callbacks in the poll phase, or one `setTimeout` among ten scheduled.

Every single callback the Event Loop runs ends with a full drain of the nextTick and microtask queues. Only then does the Event Loop pick up the next task.

```txt
Poll phase, 3 ready I/O callbacks:

  callback1() {
    promise.then(microtaskA)  // scheduled
  }
  → run microtaskA (queue drain)
  callback2() { ... }
  → queue drain
  callback3() { ... }
  → queue drain

  Only now does the Event Loop move to the check phase
```

## async/await is .then() with syntactic sugar — and that matters for counting "ticks"

```ts
// These two snippets are equivalent in microtask-tick count
async function a() {
  await Promise.resolve();
  console.log('after await');
}

function b() {
  Promise.resolve().then(() => console.log('after then'));
}
```

```ts
// ❌ Each await inside a chain adds at least one microtask
// tick — a chain of 100 awaits, even over already-resolved
// values (no real I/O), takes 100 passes through the
// microtask queue
async function chainedAwaits() {
  let result = 0;
  for (let i = 0; i < 100; i++) {
    result = await Promise.resolve(result + 1); // a tick on each iteration
  }
  return result;
}
```

Practical implication: microtasks can make ready timers wait. Suppose 100 `setTimeout(fn, 0)` callbacks are ready to run, and `chainedAwaits` above is also running somewhere in a promise chain. All 100 timers wait until the microtask queue is completely drained.

For long enough promise chains that delay becomes noticeable, though it is usually under a millisecond. Most applications never see it. But applications with very high event rates — trading, realtime analytics — do. There the difference between "await on every iteration" and "await once every N iterations" is measurable.

## process.nextTick starvation — not a theoretical scenario, a real class of bugs

```ts
// ❌ The classic starvation example — the Event Loop will
// never reach I/O, timers, or anything else. The server
// won't "crash" — it'll just spin forever in the nextTick
// queue and stop responding to requests
function loop() {
  process.nextTick(loop);
}
loop();
```

But the realistic version of this bug looks much less obvious:

```ts
// ❌ Recursively processing a message queue via nextTick —
// looks like "efficient" immediate processing, but if messages
// arrive faster than they're processed, the nextTick queue
// never empties, and the HTTP server in the same process stops
// responding to requests
function processQueue() {
  if (messages.length > 0) {
    handleMessage(messages.shift());
    process.nextTick(processQueue);  // "continue as soon as possible"
  }
}
```

```ts
// ✅ setImmediate yields control back to the Event Loop —
// I/O and timers get processed between iterations
function processQueue() {
  if (messages.length > 0) {
    handleMessage(messages.shift());
    setImmediate(processQueue);
  }
}
```

The difference is fundamental. With `process.nextTick` the callback goes into a queue that is drained **before the Event Loop moves to the next phase**. But `setImmediate` is a macrotask: it waits for its own phase, `check`. So the `poll` phase, where incoming traffic is handled, gets to run between iterations.

## The full priority map — tied to Event Loop phases

```txt
Call Stack (synchronous code) — runs first, always
    ↓
process.nextTick queue — drains completely
    ↓
Microtask queue (Promise, queueMicrotask) — drains completely
    ↓
═══════════ end of "current operation" ═══════════
    ↓
timers (setTimeout/setInterval, ready by time)
    ↓ (nextTick + microtasks drain after each callback)
pending callbacks
    ↓ (nextTick + microtasks drain after each callback)
poll (I/O callbacks — the main phase)
    ↓ (nextTick + microtasks drain after each callback)
check (setImmediate)
    ↓ (nextTick + microtasks drain after each callback)
close callbacks
    ↓
[next loop iteration → back to timers]
```

## Walking through the classic example — the mechanism, not just the answer

```ts
console.log('1');

process.nextTick(() => console.log('2'));

Promise.resolve().then(() => console.log('3'));

setTimeout(() => console.log('4'), 0);

console.log('5');

// Output: 1, 5, 2, 3, 4
```

```txt
Step 1: the script's synchronous code runs (Call Stack)
        → prints "1", registers the nextTick callback,
          registers the microtask, registers the timer,
          prints "5"

Step 2: the script's sync code finishes → nextTick queue drains
        → prints "2"

Step 3: nextTick queue is empty → microtask queue drains
        → prints "3"

Step 4: both queues are empty → the Event Loop moves to the
        timers phase → the timer is ready → prints "4"
```

Memorizing the specific output "1 5 2 3 4" stops helping the moment the example changes. An interviewer only has to nest an extra `setTimeout` inside the first one, or put a `.then()` inside `nextTick`.

One rule covers **any** variation of this question. After any operation, nextTick drains completely first, then microtasks drain completely, and only then comes the next macrotask.

## Practical guidance: when to choose what

```txt
process.nextTick — for:
  - guaranteeing a callback runs before any I/O, but after
    the current synchronous operation finishes (e.g., emitting
    an event right after a constructor so subscribers have
    time to attach: a classic EventEmitter-based API pattern)
  - rarely needed in ordinary business code

queueMicrotask / await — for:
  - standard asynchronous code, promise chains

setImmediate — for:
  - "run as soon as possible, but after the current I/O
    phase" — e.g., splitting heavy synchronous work into
    chunks (see The Event Loop)

setTimeout(fn, 0) — for:
  - similar to setImmediate, but goes through the timers
    phase, which runs first on the next loop iteration; the
    difference between setImmediate and setTimeout(0) is
    usually negligible except inside an I/O callback
    (see The Event Loop)
```

## Common interview mistakes

- **Memorizing specific examples instead of the mechanism.** Any change to the example breaks a memorized answer: a nested `.then`, `nextTick` inside `nextTick`, several `setTimeout` calls. Explain it through "queues drain after every operation", not through a table of memorized outputs.

- **Not knowing the microtask queue drains after every callback**, not once "after the script". That explains a common surprise. A promise scheduled during one I/O callback runs before the next I/O callback, even when both are ready.

- **Not seeing starvation as a real threat.** Recursion through `process.nextTick` gets dismissed as an "exotic edge case". In real code, draining a queue recursively through nextTick is a common pattern, even if a mistaken one.

- **Not understanding that async/await is .then() with sugar.** The consequence: you cannot explain why a long chain of awaits adds microtask ticks, even when the awaited values are already available synchronously.

- **Treating setImmediate and setTimeout(fn, 0) as "the same thing".** One is a separate phase, `check`; the other is the timers phase. The difference shows up specifically when they are called inside an I/O callback (see [Event Loop](./03-event-loop.md)).
