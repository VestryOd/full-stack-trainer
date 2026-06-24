# Generators and Iterators

## The iteration protocol — a spec-level contract

JavaScript defines two related protocols. Any object can implement them and gain compatibility with `for...of`, spread, destructuring, and `Array.from`.

### Iterable

An object is **iterable** if it has a `[Symbol.iterator]()` method that returns an **Iterator**.

```ts
interface Iterable<T> {
  [Symbol.iterator](): Iterator<T>;
}
```

### Iterator

An object is an **iterator** if it has a `next()` method returning an `IteratorResult`.

```ts
interface Iterator<T> {
  next(value?: unknown): IteratorResult<T>;
  return?(value?: unknown): IteratorResult<T>; // optional: early exit
  throw?(error?: unknown): IteratorResult<T>;  // optional: throw inside
}

interface IteratorResult<T> {
  value: T | undefined;
  done: boolean;
}
```

**The contract**: `done: false` — a value is available; `done: true` — iteration is complete, `value` is typically `undefined` (or the final return value for generators).

### Built-in iterables

```js
// All of these implement Symbol.iterator:
[1, 2, 3][Symbol.iterator]();          // ArrayIterator
'hello'[Symbol.iterator]();            // StringIterator (by Unicode code points!)
new Map([[1,'a']])[Symbol.iterator](); // MapIterator (entries)
new Set([1,2])[Symbol.iterator]();     // SetIterator

// for...of, spread, destructuring, Array.from — all use Symbol.iterator:
const [a, b] = new Set([10, 20, 30]); // a=10, b=20
const chars = [...'hello']; // ['h', 'e', 'l', 'l', 'o']
```

### Manual iterator implementation

```js
function range(start, end, step = 1) {
  return {
    // The object is both iterable and iterator simultaneously
    [Symbol.iterator]() { return this; },
    next() {
      if (start < end) {
        const value = start;
        start += step;
        return { value, done: false };
      }
      return { value: undefined, done: true };
    },
  };
}

for (const n of range(0, 10, 2)) {
  console.log(n); // 0, 2, 4, 6, 8
}

console.log([...range(1, 4)]); // [1, 2, 3]
```

## Generator functions and `yield` mechanics

### What a generator is

`function*` returns a **generator object** that is simultaneously:
- An **Iterator** — has a `next()` method
- An **Iterable** — `gen[Symbol.iterator]()` returns `gen` (itself)

```js
function* simple() {
  yield 1;
  yield 2;
  yield 3;
}

const gen = simple();

// As an Iterator:
gen.next(); // { value: 1, done: false }
gen.next(); // { value: 2, done: false }
gen.next(); // { value: 3, done: false }
gen.next(); // { value: undefined, done: true }

// As an Iterable:
gen[Symbol.iterator]() === gen; // true

// But gen is exhausted. Get a new one from the function:
console.log([...simple()]); // [1, 2, 3]
```

### The suspension model — what actually happens

A generator maintains **four internal states**:

```txt
suspendedStart → executing → suspendedYield → completed
                               ↑___________↓  (yield loop)
```

The key point: when `yield` is hit, the engine **saves the entire execution context** (local variables, position in code, scope chain) and returns control to the caller. The next `next()` call restores the context and continues from where it left off.

This is fundamentally different from a closure: a closure saves an Environment Record but not the execution position. A generator saves both.

```js
function* stateful() {
  let x = 0;
  while (true) {
    x++;
    const reset = yield x; // yield returns the value passed to next()
    if (reset) x = 0;
  }
}

const counter = stateful();
counter.next();     // { value: 1, done: false }
counter.next();     // { value: 2, done: false }
counter.next();     // { value: 3, done: false }
counter.next(true); // { value: 1, done: false } — reset=true, x reset to 0, then x++
counter.next();     // { value: 2, done: false }
```

### Two-way communication via `yield`

`yield` is not just "send a value out." It's an **exchange point**: the generator sends a value out, and upon resumption receives a new value in.

```js
// Predict the output:
function* echo() {
  console.log('start');
  const a = yield 'first';    // will receive the value from next(...)
  console.log('got:', a);
  const b = yield 'second';
  console.log('got:', b);
  return 'done';
}

const g = echo();

const r1 = g.next('ignored'); // first next(): starts the generator
                               // 'ignored' goes nowhere —
                               // (no preceding yield to receive it)
console.log(r1);               // ?

const r2 = g.next('hello');   // resumes, 'hello' → a
console.log(r2);               // ?

const r3 = g.next('world');   // resumes, 'world' → b
console.log(r3);               // ?

const r4 = g.next();           // generator is done
console.log(r4);               // ?
```

<details>
<summary>Breakdown</summary>

```txt
g.next('ignored'):
  Starts the generator from suspendedStart
  'start' → output: start
  yield 'first' → suspend
  r1 = { value: 'first', done: false }

g.next('hello'):
  Resumes; 'hello' = value of the (yield 'first') expression
  a = 'hello'
  'got: hello' → output: got: hello
  yield 'second' → suspend
  r2 = { value: 'second', done: false }

g.next('world'):
  Resumes; 'world' = value of (yield 'second')
  b = 'world'
  'got: world' → output: got: world
  return 'done' → completion
  r3 = { value: 'done', done: true }

g.next():
  Generator is already completed
  r4 = { value: undefined, done: true }

Full output:
  start
  { value: 'first', done: false }
  got: hello
  { value: 'second', done: false }
  got: world
  { value: 'done', done: true }
  { value: undefined, done: true }
```

</details>

### `yield*` — delegation

`yield*` delegates iteration to another iterable and returns its final value (the generator's `return`):

```js
function* inner() {
  yield 'b';
  yield 'c';
  return 'inner_done'; // this becomes the value of the yield* expression in outer
}

function* outer() {
  yield 'a';
  const result = yield* inner(); // delegates; result = 'inner_done'
  console.log('inner returned:', result);
  yield 'd';
}

console.log([...outer()]); // ['a', 'b', 'c', 'd']
// + output: inner returned: inner_done
```

`yield*` works with **any iterable**, not just generators:

```js
function* flatten(arr) {
  for (const item of arr) {
    if (Array.isArray(item)) yield* flatten(item); // recursive delegation
    else yield item;
  }
}

console.log([...flatten([1, [2, [3, 4]], 5])]); // [1, 2, 3, 4, 5]
```

### `return()` and `throw()` — external generator control

```js
function* gen() {
  try {
    yield 1;
    yield 2;
  } finally {
    console.log('cleanup'); // runs on return() or throw()
  }
}

const g = gen();
g.next();         // { value: 1, done: false }
g.return('exit'); // 'cleanup' → { value: 'exit', done: true }
// Generator is done. All subsequent next() → { value: undefined, done: true }

// throw():
const g2 = gen();
g2.next();                   // { value: 1, done: false }
g2.throw(new Error('boom'));
// 'cleanup' (finally runs)
// Error is thrown at the yield 1 point — if there's no try/catch inside
// the generator, the error propagates to the caller
```

`for...of` automatically calls `return()` on the generator when exiting early (`break`, `throw`, `return`):

```js
function* infinite() {
  let i = 0;
  try {
    while (true) yield i++;
  } finally {
    console.log('generator cleanup');
  }
}

for (const n of infinite()) {
  if (n > 2) break; // calls gen.return() → finally runs
}
// 'generator cleanup'
```

## Async generators and `for-await-of`

`async function*` — an async generator. It can both `await` and `yield`. Consumed via `for await...of`.

```js
async function* paginate(url) {
  let page = 1;
  while (true) {
    const res = await fetch(`${url}?page=${page}`);
    const { data, hasMore } = await res.json();
    yield data; // emit the current page
    if (!hasMore) break;
    page++;
  }
}

// Consumption:
for await (const page of paginate('/api/items')) {
  processPage(page);
  // the next fetch only happens when we move to the next iteration
}
```

An async iterable implements `[Symbol.asyncIterator]()`:

```js
const asyncIterable = {
  [Symbol.asyncIterator]() {
    let i = 0;
    return {
      async next() {
        await delay(100); // simulate async operation
        return i < 3
          ? { value: i++, done: false }
          : { value: undefined, done: true };
      },
    };
  },
};

for await (const val of asyncIterable) {
  console.log(val); // 0, 1, 2 — with delays
}
```

## Practical patterns

### Lazy evaluation and infinite sequences

```js
// Infinite Fibonacci sequence — doesn't compute everything upfront:
function* fibonacci() {
  let [a, b] = [0, 1];
  while (true) {
    yield a;
    [a, b] = [b, a + b];
  }
}

// Take the first N elements from any infinite iterable:
function take(iterable, n) {
  const result = [];
  for (const item of iterable) {
    result.push(item);
    if (result.length >= n) break;
  }
  return result;
}

take(fibonacci(), 8); // [0, 1, 1, 2, 3, 5, 8, 13]

// Lazy transformation pipeline (no intermediate arrays):
function* map(iterable, fn) {
  for (const item of iterable) yield fn(item);
}

function* filter(iterable, predicate) {
  for (const item of iterable) {
    if (predicate(item)) yield item;
  }
}

const result = take(
  filter(
    map(fibonacci(), x => x * 2), // double each
    x => x % 3 === 0              // keep only divisible by 3
  ),
  5
);
// [0, 6, 12, 18, 24, ...] — lazy pipeline, computes only what's needed
```

### Tree traversal

```js
function* dfsTree(node) {
  yield node.value;
  for (const child of node.children ?? []) {
    yield* dfsTree(child); // recursive delegation
  }
}

const tree = {
  value: 1,
  children: [
    { value: 2, children: [{ value: 4 }, { value: 5 }] },
    { value: 3, children: [{ value: 6 }] },
  ],
};

console.log([...dfsTree(tree)]); // [1, 2, 4, 5, 3, 6]
```

### Async pagination with error handling

```js
async function* fetchAllUsers(baseUrl) {
  let cursor = null;

  do {
    const url = cursor ? `${baseUrl}?cursor=${cursor}` : baseUrl;
    const res = await fetch(url);

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const { users, nextCursor } = await res.json();
    yield users; // emit the current batch
    cursor = nextCursor;
  } while (cursor);
}

// Usage — a unified interface regardless of data volume:
try {
  for await (const batch of fetchAllUsers('/api/users')) {
    await processBatch(batch);
  }
} catch (err) {
  console.error('Failed to fetch users:', err);
}
```

### Memoized generator (caching iteration results)

```js
function memoizeGenerator(generatorFn) {
  const cache = [];
  let gen = null;
  let done = false;

  return {
    [Symbol.iterator]() {
      let index = 0;
      return {
        next() {
          if (index < cache.length) {
            return { value: cache[index++], done: false };
          }
          if (done) {
            return { value: undefined, done: true };
          }
          gen ??= generatorFn();
          const result = gen.next();
          if (result.done) {
            done = true;
            return { value: undefined, done: true };
          }
          cache.push(result.value);
          index++;
          return result;
        },
      };
    },
  };
}

const expensiveSeq = memoizeGenerator(function* () {
  for (let i = 0; i < 5; i++) {
    console.log(`computing ${i}`);
    yield i * i;
  }
});

console.log([...expensiveSeq]); // computing 0-4, then [0,1,4,9,16]
console.log([...expensiveSeq]); // no logs — all from cache, [0,1,4,9,16]
```

## Connection to other topics

```txt
[Closures]              — a generator preserves both the Environment Record
                           (closure) and the execution position (closures can't)
[Async Patterns]        — async/await under the hood is a generator + an
                           automatic Promise runner; for-await-of = async iterator protocol
[Proxy and Symbols]     — Symbol.iterator, Symbol.asyncIterator are well-known
                           symbols that make any object iterable
[Modern JS]             — Array.from(), spread, destructuring all consume
                           Symbol.iterator; Array.fromAsync — Symbol.asyncIterator
```

## Common interview traps

- **"A generator function runs when called"** — no. `gen()` creates a generator object in the `suspendedStart` state and returns it. The code inside doesn't run until the first `next()`.

- **"The first `next(value)` passes a value into the generator"** — no. The value passed to the first `next()` is ignored — there's nowhere for it to go (no preceding `yield` to receive it). The first `next()` only starts the generator up to the first `yield`.

- **"A generator can be restarted"** — no. After `done: true`, the generator is permanently finished. A new one requires calling the generator function again.

- **"`yield*` only works with other generators"** — no. `yield*` works with any iterable: arrays, strings, Sets, Maps, other generators.

- **"The return value in a generator is lost"** — with `for...of` or spread, yes, it's lost. But with manual `next()` — `{ value: returnValue, done: true }`. And with `yield*` — the return value becomes the value of the `yield*` expression in the outer generator. Three different behaviors.

- **"`for-await-of` only works with async iterables"** — `for-await-of` also works with synchronous iterables (it wraps values in `Promise.resolve`). But `for...of` does **not** work with async iterables (`Symbol.asyncIterator`).

- **Not knowing about `return()` and resource cleanup** — `for...of` with `break` calls `gen.return()`, which triggers `finally` blocks inside the generator. Critical for generators holding resources (connections, file handles).
