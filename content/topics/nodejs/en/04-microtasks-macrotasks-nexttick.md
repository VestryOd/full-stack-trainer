# Microtasks, Macrotasks, and process.nextTick

## Why this is a favorite interview topic — and where the real depth is

The shallow level of this topic is "memorize the order: nextTick → microtasks → macrotasks" and predict the `console.log` output of short snippets. That's necessary, but it's not what makes a senior answer. The real depth is in answering: **"between WHAT exactly does queue-switching happen, and how often"**. Missing this is what leads to production bugs like "why does one slow request slow down ALL other requests, even though I use async/await everywhere?"

## Three queues — and when EACH ONE drains

```txt
process.nextTick queue  — drains COMPLETELY after ANY current
                           operation finishes: after the script's
                           synchronous code, AFTER EVERY microtask,
                           after every Event Loop phase callback

Microtask queue           — drains COMPLETELY (including new
(Promise.then,              microtasks added WHILE running the
queueMicrotask)              current ones) after the current
                           operation finishes AND after the
                           nextTick queue has drained

Macrotask queue            — the Event Loop moves to the next
(setTimeout, setImmediate,   macrotask only once BOTH queues
I/O callbacks)                above are completely empty
```

The key detail most explanations skip: this doesn't happen **once** "after the script's synchronous block" — it happens **after EVERY callback**, no matter where it runs — whether it's one of several I/O callbacks in the poll phase, or one `setTimeout` among ten scheduled. Each individual callback executed by the Event Loop finishes with a full "drain" of the nextTick + microtask queues before the Event Loop picks up the next task.

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

  Only NOW does the Event Loop move to the check phase
```

## async/await is .then() with syntactic sugar — and that matters for counting "ticks"

```ts
// These two snippets are EQUIVALENT in microtask-tick count
async function a() {
  await Promise.resolve();
  console.log('after await');
}

function b() {
  Promise.resolve().then(() => console.log('after then'));
}
```

```ts
// ❌ Each await INSIDE a chain adds at least one microtask
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

Practical implication: if you have 100 ready `setTimeout(fn, 0)` calls AND the function above somewhere in a promise chain — all 100 timers will wait until the microtask queue is completely drained, which for sufficiently long promise chains can take a noticeable (though usually sub-millisecond) amount of time. For most applications this is invisible — but for applications with very high event rates (trading, realtime analytics), the difference between "await on every iteration" and "await once every N iterations" is measurable.

## process.nextTick starvation — not a theoretical scenario, a real class of bugs

```ts
// ❌ The classic starvation example — the Event Loop will
// NEVER reach I/O, timers, or anything else. The server
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

The difference is fundamental: `process.nextTick` enqueues into a queue that drains **before moving to the next Event Loop phase**, while `setImmediate` is a macrotask that waits for its own phase (`check`), allowing the `poll` phase (where incoming traffic is handled) to run between iterations.

## The full priority map — tied to Event Loop phases

```txt
Call Stack (synchronous code) — runs first, always
    ↓
process.nextTick queue — drains COMPLETELY
    ↓
Microtask queue (Promise, queueMicrotask) — drains COMPLETELY
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

## Walking through the classic example — explaining the MECHANISM, not just the answer

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

Memorizing the specific output "1 5 2 3 4" is useless in an interview if the example changes (an extra `setTimeout` nested inside the first one, or a `.then()` inside `nextTick`) — but understanding "after ANY operation, nextTick drains completely first, then microtasks completely, and only then the next macrotask" lets you work through ANY variation of this question.

## Practical guidance: when to choose what

```txt
process.nextTick — for:
  - guaranteeing a callback runs BEFORE any I/O, but AFTER
    the current synchronous operation finishes (e.g., emitting
    an event right after a constructor so subscribers have
    time to attach: a classic EventEmitter-based API pattern)
  - rarely needed in ordinary business code

queueMicrotask / await — for:
  - standard asynchronous code, promise chains

setImmediate — for:
  - "run as soon as possible, but AFTER the current I/O
    phase" — e.g., splitting heavy synchronous work into
    chunks (see [The Event Loop])

setTimeout(fn, 0) — for:
  - similar to setImmediate, but goes through the timers
    phase, which runs FIRST on the next loop iteration; the
    difference between setImmediate and setTimeout(0) is
    usually negligible except inside an I/O callback
    (see [The Event Loop])
```

## Common interview mistakes

- **Memorizing specific examples instead of the mechanism** — any change to the example (a nested `.then`, `nextTick` inside `nextTick`, multiple `setTimeout`s) breaks a memorized answer; explain it via "queues drain after every operation," not via a table of memorized outputs.

- **Not knowing the microtask queue drains AFTER EVERY callback**, not once "after the script" — this explains why a promise scheduled during one I/O callback runs before the next I/O callback, even if both are ready.

- **Not seeing starvation as a real threat** — process.nextTick recursion is dismissed as an "exotic edge case," even though recursively draining queues via nextTick is a not-uncommon (if mistaken) pattern in real code.

- **Not understanding that async/await is .then() with sugar** — and, as a result, being unable to explain why a long chain of awaits adds microtask ticks even when the awaited values are already available synchronously.

- **Treating setImmediate and setTimeout(fn, 0) as "the same thing"** — without understanding that one is a separate phase (check) and the other is the timers phase, and the difference shows up specifically when called inside an I/O callback (see [The Event Loop]).
