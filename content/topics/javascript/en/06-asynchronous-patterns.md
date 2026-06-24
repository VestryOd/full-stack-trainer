# Asynchronous Patterns

## Callback Hell — why it's a structural problem, not an aesthetic one

Callback hell is often explained as "ugly code with deep nesting." That's superficial. The real problem is **inversion of control**.

When you pass a callback to a function, you hand it control over part of your program. You no longer control:

```js
// You can't guarantee that thirdPartyApi:
thirdPartyApi.fetchData(userId, function(err, data) {
  // 1. Calls the callback exactly once (not 0 or 2+ times)
  // 2. Doesn't call it synchronously (earlier than you expect)
  // 3. Doesn't call it with both err AND data simultaneously
  // 4. Doesn't swallow exceptions thrown inside
  // 5. Doesn't call it several seconds later, or never at all
});
```

Beyond IoC, there are structural composition problems:

```js
// Task: fetch a user, then their orders, then the first product
// Each step depends on the previous result

fetchUser(userId, function(err, user) {
  if (err) return handleError(err);   // manual error handling everywhere

  fetchOrders(user.id, function(err, orders) {
    if (err) return handleError(err); // duplicated

    fetchProduct(orders[0].productId, function(err, product) {
      if (err) return handleError(err); // again

      // Finally have the data — but we're three levels deep.
      // Want to add a fourth step? Another level.
      // Want to run several requests in parallel? Good luck.
      console.log(product);
    });
  });
});
```

**Structural problems:**
- Error handling is manual at every level, easy to miss
- Returning values is impossible (callback ≠ return)
- Parallel operations require manual counters
- Code reads outside-in, not top-to-bottom

## Promise: internal mechanics

### States and internal slots

A Promise is an object with three internal slots:

```txt
Promise {
  [[PromiseState]]            → 'pending' | 'fulfilled' | 'rejected'
  [[PromiseResult]]           → undefined | value | reason
  [[PromiseFulfillReactions]] → list of reaction objects
  [[PromiseRejectReactions]]  → list of reaction objects
}
```

State transitions are **one-way and irreversible**:

```txt
pending ──→ fulfilled (with value)
       └──→ rejected  (with reason)
```

Once `[[PromiseState]]` changes, it changes exactly once — subsequent calls to `resolve`/`reject` are ignored:

```js
const p = new Promise((resolve, reject) => {
  resolve(1);
  resolve(2);   // ignored
  reject('err'); // ignored
});

p.then(v => console.log(v)); // 1
```

### The `resolve` and `reject` functions

When `new Promise(executor)` is called, the engine creates two functions that close over the promise object:

```txt
resolve(value):
  1. If [[PromiseState]] !== 'pending' → exit (already settled)
  2. If value is a thenable (has a .then method):
       → Promise Resolution Procedure: subscribe to value.then
       (the promise "follows" the thenable)
  3. Otherwise:
       [[PromiseState]] = 'fulfilled'
       [[PromiseResult]] = value
       → Enqueue all [[PromiseFulfillReactions]] into the Microtask Queue

reject(reason):
  1. If [[PromiseState]] !== 'pending' → exit
  2. [[PromiseState]] = 'rejected'
     [[PromiseResult]] = reason
     → Enqueue all [[PromiseRejectReactions]] into the Microtask Queue
```

**The Promise Resolution Procedure** is the mechanism that allows chaining to work with any thenable, not just native Promises:

```js
// This works because resolve invokes the Promise Resolution Procedure:
Promise.resolve({
  then(resolve) { resolve(42); } // an arbitrary thenable
}).then(v => console.log(v)); // 42
```

### `.then()` mechanics — each call creates a new Promise

```js
const p1 = Promise.resolve(1);

const p2 = p1.then(v => v + 1); // new Promise
const p3 = p2.then(v => v * 2); // another new Promise

// p1, p2, p3 are three separate Promise objects
// p1 fulfilled(1) → p2 fulfilled(2) → p3 fulfilled(4)
```

What determines the state of the new promise:

```txt
p2 = p1.then(onFulfilled, onRejected)

If p1 is fulfilled:
  → call onFulfilled(value)
  → if it returns a thenable → p2 follows it
  → if it returns an ordinary value → p2 fulfilled(value)
  → if it throws → p2 rejected(error)

If p1 is rejected:
  → if onRejected exists → call onRejected(reason)
     (same logic for the result)
  → if no onRejected → p2 rejected(reason) (propagates down)
```

```js
Promise.reject(new Error('oops'))
  .then(v => v * 2)          // no onRejected → error propagates
  .then(v => v + 1)          // none here either → still propagating
  .catch(err => {
    console.log(err.message); // 'oops' — caught here
    return 'recovered';
  })
  .then(v => console.log(v)); // 'recovered' — .catch restored the chain
```

## `async/await` — what it conceptually compiles to

An `async function` always returns a Promise. `await` suspends the generator-like execution of the function and resumes it as a Promise callback.

```js
// async/await version:
async function fetchUserData(id) {
  const user = await fetchUser(id);
  const orders = await fetchOrders(user.id);
  return { user, orders };
}

// Conceptual Promise equivalent (simplified):
function fetchUserData(id) {
  return fetchUser(id).then(user => {
    return fetchOrders(user.id).then(orders => {
      return { user, orders };
    });
  });
}
```

With error handling:

```js
// async/await:
async function safeFetch(url) {
  try {
    const data = await fetch(url);
    return await data.json();
  } catch (err) {
    console.error('Failed:', err);
    return null;
  }
}

// Conceptual equivalent:
function safeFetch(url) {
  return fetch(url)
    .then(data => data.json())
    .catch(err => {
      console.error('Failed:', err);
      return null;
    });
}
```

**Important detail**: each `await` adds at least **one** microtask to the queue. Multiple sequential `await`s on already-resolved promises still add microtasks — this affects execution ordering.

```js
// Predict the output:
async function a() {
  console.log('a1');
  await Promise.resolve();
  console.log('a2');
  await Promise.resolve();
  console.log('a3');
}

async function b() {
  console.log('b1');
  await Promise.resolve();
  console.log('b2');
}

a();
b();
console.log('sync');
```

<details>
<summary>Breakdown</summary>

```txt
Synchronously:
  a(): 'a1' → await → suspended
  b(): 'b1' → await → suspended
  'sync'

Microtask Queue after synchronous code: [resumeA, resumeB]

  resumeA: 'a2' → await → suspended → adds resumeA2
  Microtask Queue: [resumeB, resumeA2]

  resumeB: 'b2' → b() done
  Microtask Queue: [resumeA2]

  resumeA2: 'a3' → a() done

Result: a1, b1, sync, a2, b2, a3
```

Key point: each `await` causes a pause — other queued tasks can run between `await`s inside one async function.

</details>

## Error handling comparison

### Callbacks — the problems

```js
// The err-first convention — but it's just a convention, not a guarantee:
fs.readFile('file.txt', (err, data) => {
  if (err) { /* handle */ return; }
  // data is here

  // ❌ If code inside the callback throws an exception —
  // it is NOT caught by any outer try/catch
  JSON.parse(data); // SyntaxError → goes to the global handler (or crash)
});

try {
  fs.readFile('file.txt', callback); // try/catch here is USELESS —
} catch (e) {                        // the exception from callback happens later
  // we'll never get here from an async error
}
```

### Promises — improvements and traps

```js
fetch('/api/data')
  .then(res => res.json())
  .then(data => processData(data))
  .catch(err => console.error(err)); // catches errors from the entire chain

// ❌ Trap: returning a promise from then without return
fetch('/api/data')
  .then(res => {
    fetch('/api/other'); // ← no return! This promise is "lost"
  })
  .then(data => console.log(data)) // data = undefined
  .catch(err => console.error(err)); // will NOT catch errors from fetch('/api/other')

// ✅ Correct:
fetch('/api/data')
  .then(res => fetch('/api/other')) // implicit return in arrow function
  .then(res => res.json())
  .catch(err => console.error(err));
```

```js
// ❌ Unhandled Promise Rejection:
async function dangerous() {
  throw new Error('boom');
}
dangerous(); // Error is unhandled — UnhandledPromiseRejection

// ✅ Always await or .catch():
await dangerous().catch(err => console.error(err));
```

### async/await — cleaner, but its own pitfalls

```js
// ✅ try/catch works naturally:
async function loadData() {
  try {
    const user = await fetchUser();
    const orders = await fetchOrders(user.id);
    return orders;
  } catch (err) {
    // Catches rejection from fetchUser OR fetchOrders
    console.error(err);
    throw err; // re-throw if needed
  } finally {
    // Runs regardless (just like a regular finally)
    cleanup();
  }
}

// ❌ Classic mistake: await in a loop = sequential, not parallel
async function sequential() {
  const results = [];
  for (const id of ids) {
    results.push(await fetchItem(id)); // each request waits for the previous!
  }
  return results;
}

// ✅ Parallel via Promise.all:
async function parallel() {
  return Promise.all(ids.map(id => fetchItem(id)));
}
```

## Promise Combinators — exact semantics of each

### `Promise.all` — all or nothing

```js
// Resolves: when ALL promises are fulfilled → array of values (in input order)
// Rejects:  on the FIRST rejection → with its reason, others are ignored

const [user, orders, products] = await Promise.all([
  fetchUser(id),
  fetchOrders(id),
  fetchProducts(id),
]);

// Trap: if one rejects, the already-resolved promises are "lost"
// They did execute, but their results are inaccessible
Promise.all([
  Promise.resolve(1),
  Promise.reject('error'),
  Promise.resolve(3),
]).catch(err => console.log(err)); // 'error'
// Values 1 and 3 are inaccessible
```

### `Promise.allSettled` — all results, regardless of outcome (ES2020)

```js
// ALWAYS resolves (never rejects)
// Result: array of objects { status, value | reason }

const results = await Promise.allSettled([
  fetchUser(id),       // might fail
  fetchOrders(id),     // might fail
  fetchProducts(id),   // might fail
]);

results.forEach(result => {
  if (result.status === 'fulfilled') {
    console.log('OK:', result.value);
  } else {
    console.log('FAIL:', result.reason);
  }
});
// Use when you need all results regardless of partial failures
```

### `Promise.race` — first to finish, any outcome

```js
// Resolves OR rejects: as soon as the FIRST promise settles (fulfilled or rejected)

// Timeout pattern:
function withTimeout(promise, ms) {
  const timeout = new Promise((_, reject) =>
    setTimeout(() => reject(new Error('Timeout')), ms)
  );
  return Promise.race([promise, timeout]);
}

await withTimeout(fetchSlowData(), 3000);
// If fetchSlowData takes > 3s → rejection with 'Timeout'

// Trap: the "losers" keep running —
// Promise.race doesn't cancel them, just ignores their results
```

### `Promise.any` — first success (ES2021)

```js
// Resolves: when the FIRST promise fulfills → with its value
// Rejects:  only when ALL reject → AggregateError with a list of all reasons

// Pattern: request data from multiple sources, take the fastest
const data = await Promise.any([
  fetchFromCDN1('/data'),
  fetchFromCDN2('/data'),
  fetchFromCDN3('/data'),
]);
// Returns the result from the first successful CDN

// All failed:
Promise.any([
  Promise.reject('err1'),
  Promise.reject('err2'),
]).catch(err => {
  console.log(err instanceof AggregateError); // true
  console.log(err.errors); // ['err1', 'err2']
});
```

### Summary table

```txt
Combinator          Resolves                  Rejects
─────────────────────────────────────────────────────────────
Promise.all         All fulfilled             First rejected
Promise.allSettled  Always (never rejects)    —
Promise.race        First settled             First settled
Promise.any         First fulfilled           All rejected → AggregateError
```

## Predict the output — async/await + Promise combinators

```js
async function delay(ms, value) {
  await new Promise(resolve => setTimeout(resolve, ms));
  return value;
}

async function main() {
  console.log('start');

  const [a, b] = await Promise.all([
    delay(100, 'A'),
    delay(50, 'B'),
  ]);
  console.log(a, b); // ?

  try {
    await Promise.any([
      Promise.reject('err1'),
      Promise.reject('err2'),
    ]);
  } catch (e) {
    console.log(e instanceof AggregateError, e.errors); // ?
  }

  const result = await Promise.race([
    delay(200, 'slow'),
    delay(10, 'fast'),
  ]);
  console.log(result); // ?

  console.log('end');
}

main();
```

<details>
<summary>Answer</summary>

```
start
A B            // Promise.all waits for both (100ms), order = input order
true ['err1', 'err2']  // AggregateError, all rejection reasons in .errors
fast           // Promise.race → fastest (10ms)
end
```

`Promise.all` returns values **in input array order**, not in completion order. `delay(100, 'A')` is slower, but `a` = 'A'.

</details>

## Error handling patterns in real code

```js
// Pattern 1: wrap in [error, data] — Go style
async function tryCatch(promise) {
  try {
    return [null, await promise];
  } catch (err) {
    return [err, null];
  }
}

const [err, user] = await tryCatch(fetchUser(id));
if (err) { /* handle */ return; }
// user is guaranteed non-null

// Pattern 2: per-step .catch for different error types
await fetchUser(id)
  .catch(err => { throw new UserNotFoundError(err.message); })
  .then(user => fetchOrders(user.id))
  .catch(err => { throw new OrdersUnavailableError(err.message); });

// Pattern 3: AbortController for cancellation (covered in detail in article 12)
const controller = new AbortController();
setTimeout(() => controller.abort(), 5000);

try {
  const res = await fetch('/api/data', { signal: controller.signal });
} catch (err) {
  if (err.name === 'AbortError') console.log('Cancelled');
  else throw err;
}
```

## Connection to other topics

```txt
[Event Loop]          — Promise.then always adds a microtask;
                         execution order is governed by the Microtask Queue
[Generators]          — async/await is generators + an automatic runner;
                         covered in detail in the next article
[Modern JS]           — AbortController for cancelling promises — in article 12
[Node.js streams]     — async iteration over streams via for-await-of
```

## Common interview traps

- **"Callback hell is about nesting"** — the main problem is not visual but structural: inversion of control, inability to return values, manual error handling at every level.

- **"Promise.all fails if one Promise is slow"** — no. `Promise.all` waits for ALL of them. It rejects on the first `rejected`. A slow but non-failing Promise simply slows down `Promise.all`.

- **"async/await is not Promises"** — an `async function` always returns a Promise. `await` is `.then()`. They are fully interoperable.

- **"Errors in an async function are caught by an outer try/catch"** — no, if the function isn't `await`ed. `asyncFn()` without `await` is a promise in flight; an outer `try/catch` won't catch it.

- **Not knowing the difference between `Promise.race` and `Promise.any`** — `race` settles on the FIRST settled (including rejection); `any` settles on the FIRST fulfilled. `race` with one immediately-rejecting promise rejects immediately; `any` does not.

- **"Promise.allSettled came with Promise"** — no, ES2020. `Promise.any` is ES2021. In an interview it matters to know what may be unavailable in older environments.

- **await in a loop = sequential** — a classic performance mistake. If iterations are independent, always use `Promise.all(items.map(...))`.
