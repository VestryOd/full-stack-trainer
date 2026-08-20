# JavaScript Advanced — Interview Questions

## Group 1: Execution Contexts & Scope

**What is an Execution Context and what does it consist of?**

An Execution Context is an abstract specification container. The engine creates one when a function is called or a script starts. It has four fields:

```txt
LexicalEnvironment    — where let/const bindings are stored
VariableEnvironment   — where var and function declarations live
ThisBinding           — the value of this
code evaluation state — execution position (vital for generators)
```

The stack of contexts is the Call Stack. The Running Execution Context is always the one on top.

---

**What is hoisting and why does it happen?**

Hoisting is a consequence of the two-phase execution model. In the creation phase, the engine scans the code and creates bindings before any line executes. It initializes `var` to `undefined` and a `function` declaration to the full function object. Bindings for `let`/`const` are created but not initialized — that is the Temporal Dead Zone (TDZ). Code is not physically "moved"; only the order of operations changes.

---

**What is the difference between `LexicalEnvironment` and `VariableEnvironment`?**

These are two fields of a single Execution Context, each pointing to a different Environment Record:

```txt
VariableEnvironment — var and function declarations; never
                      changes while the function lives
LexicalEnvironment  — let/const of the current block; a new
                      Declarative ER per {} block
```

This is what makes `let` block-scoped and `var` function-scoped at the same time inside one function.

---

**What is the TDZ and why are `let`/`const` in it?**

The Temporal Dead Zone is the state of a binding "created but not initialized" in an Environment Record. During a block's creation phase, the engine scans the entire block and puts `let`/`const` bindings into the TDZ from the very start. Any access before the declaration line throws `ReferenceError`. Consequence: inside a block, `let x` shadows an outer `x` from the beginning of the block, not from its declaration line.

---

**How does the scope chain work and why is JavaScript lexically (not dynamically) scoped?**

The scope chain is the linked list of `[[OuterEnv]]` references between Environment Records. Each ER stores an `[[OuterEnv]]` field pointing to the ER of the lexically enclosing scope. When a function is created, its `[[Environment]]` slot is fixed to the current ER — this happens at definition time, not call time. This is why a function "sees" the variables of its definition site, not its call site — lexical scoping.

---

## Group 2: `this` Binding

**Name the four rules for determining `this` and their priority.**

There are four rules, priority from top to bottom:

```txt
new Fn()           → this = the new object
fn.call/apply/bind → this = the first argument
obj.fn()           → this = the object left of the dot
fn()               → this = globalThis (sloppy) / undefined (strict)
```

When two rules match the same call, the one higher in the list wins.

---

**Why do arrow functions not have their own `this`?**

An arrow function does not create a `ThisBinding` in its Function Environment Record. When `this` is accessed inside an arrow, it resolves through the Scope Chain — like a regular identifier — finding the `this` of the lexically enclosing context. This is why `call`/`apply`/`bind` have no effect on an arrow's `this`: there is simply nothing to override.

---

**What does `bind` return and can its binding be overridden?**

`bind` returns a **bound function exotic object** with three internal slots: `[[BoundTargetFunction]]`, `[[BoundThis]]`, and `[[BoundArguments]]`. `[[BoundThis]]` cannot be overridden via `call`/`apply` or another `bind` — it is permanently fixed. The only exception: `new BoundFn()` — the `[[Construct]]` algorithm ignores `[[BoundThis]]` and creates a fresh object.

---

**Why does `obj.method` lose `this` when passed as a callback?**

`const fn = obj.method` extracts only the function — the implicit binding `this = obj` existed only in the `obj.method()` syntax. A function does not carry "memory" of its connection to an object. On a subsequent call `fn()`, default binding applies: `this = undefined` (strict) or `globalThis` (sloppy). Fix: `fn.bind(obj)`, a wrapper `() => obj.method()`, or a class field with an arrow function.

---

**Describe the `[[Construct]]` algorithm for `new Fn()`.**

When `new Fn()` is called, the engine runs three steps:

```txt
1. obj = Object.create(Fn.prototype)
2. call Fn with this = obj
3. if Fn returned an object → return it, otherwise return obj
```

So `new Fn()` with `return { x: 1 }` returns `{ x: 1 }`, not `obj`. For `new BoundFn()`, `[[BoundThis]]` is ignored and `obj` is created as normal.

---

## Group 3: Closures

**What is a closure at the engine level?**

A closure = a function + a reference to the Environment Record in which it was created (the `[[Environment]]` internal slot). This is not a copy of the variables, it is a live reference. A change to a variable in the ER is visible to every function closed over it. Every function in JS is a closure — even a top-level function closes over the Global ER.

---

**Why does `var` in a loop with `setTimeout` print the same value?**

All callbacks close over the same ER (the function's or the global one), in which `var i` is a single variable. By the time the callbacks run — after the synchronous code — the loop has finished and `i` holds its final value. Using `let i` fixes this. The spec requires a fresh LexicalEnvironment per iteration, with its own copy of `i`, so each callback closes over a unique `i`.

---

**What does V8 actually retain in memory through a closure?**

V8 creates a **Context object** for each ER that at least one live function references. If multiple functions close over the same ER, V8 creates a single shared Context — holding all variables used by any one of them. This means a function that only uses `small` may accidentally retain `large`. That happens when both were created in the same scope as another function that does use `large`.

---

**What is the main advantage of factory functions over classes for encapsulation?**

A factory function achieves true privacy through a closure: internal variables are physically inaccessible from outside the module. A class with `#`-fields (ES2022) also provides true privacy at the engine level.

The difference is elsewhere: every method of a factory function is a separate function object, with no prototype chain. For one or two instances that costs nothing. For thousands, a class is more memory-efficient, because its methods live in the prototype.

---

## Group 4: Prototypes & Inheritance

**Explain the difference between `[[Prototype]]`, `__proto__`, and `prototype`.**

Three different things with confusingly similar names:

```txt
[[Prototype]] — internal slot of every object → its prototype
__proto__     — deprecated accessor on Object.prototype that
                reads/writes [[Prototype]] (Annex B, browsers only)
prototype     — plain property of Function objects; becomes the
                [[Prototype]] of objects created via new Fn()
```

The correct way to read `[[Prototype]]` is `Object.getPrototypeOf(obj)`.

---

**What does `class` compile to under the hood? How does it differ from a manual constructor?**

`class` is syntactic sugar over the prototype mechanism. Three things still differ from a manual constructor:

```txt
1. class methods are non-enumerable, as if defined with
   Object.defineProperty and enumerable: false; a manual
   prototype.method = fn is enumerable
2. a call without new throws TypeError; a constructor function
   just runs as a normal call
3. extends sets up two chains, not one:
     Derived.prototype[[Prototype]] = Base.prototype  (instances)
     Derived[[Prototype]] = Base                      (statics)
```

---

**How does `instanceof` work and when does it produce a wrong result?**

`instanceof` checks whether `Fn.prototype` is anywhere in the object's `[[Prototype]]` chain (or calls `Symbol.hasInstance`). It fails when `Fn.prototype` is replaced after the object is created — `obj instanceof Fn` returns `false` because `obj[[Prototype]]` points to the old object. It also breaks for objects from different realms (different `Array` across iframes).

---

**What happens when you assign a property that has a setter in the prototype?**

If the `[[Prototype]]` chain contains a setter for property `x`, then `obj.x = val` invokes that setter with `this = obj`. No own property appears on `obj`. This is surprising: many expect assignment to always create an own property. `Object.defineProperty(obj, 'x', { value: val })` bypasses the setter and creates an own property.

---

**Why should you restore `constructor` when manually setting up a prototype chain?**

`Derived.prototype = Object.create(Base.prototype)` replaces the entire `prototype` object, wiping the original `Derived.prototype.constructor = Derived`. After that, `new Derived().constructor === Base`. That breaks reflection and any pattern relying on `.constructor`, such as `obj.constructor()` to create another instance of the same type. Fix: `Derived.prototype.constructor = Derived`.

---

## Group 5: Event Loop

**Describe the full browser Event Loop algorithm.**

One iteration of the Event Loop:

```txt
1. take one task from the Task Queue
2. run it to completion (run-to-completion)
3. drain the Microtask Queue fully, including microtasks
   added while draining
4. rendering opportunity (rAF → style → layout → paint)
5. go back to step 1
```

Critical: the Microtask Queue is drained completely — not one microtask, but all of them until empty.

---

**Why is `Promise.then` always asynchronous, even for an already-resolved Promise?**

The spec requires: a Promise reaction (`.then` callback) is always added to the Microtask Queue — never called synchronously. This guarantees predictable ordering: synchronous code after `.then()` always runs before the callback, regardless of the Promise's state. Without this guarantee, ordering would be unpredictable depending on when the Promise was resolved.

---

**What is the difference between `process.nextTick`, `queueMicrotask`, and `Promise.then` in Node.js?**

In Node.js the Microtask Queue is two-tiered. The `nextTick Queue` (`process.nextTick`) is drained completely first, then the Microtask Queue (`Promise.then`, `queueMicrotask`). Among microtasks, `process.nextTick` has the highest priority — it predates Promises in Node.js history. The other two share one queue, in FIFO order (first in, first out). Recursive `process.nextTick` starves the Event Loop.

---

**How does rendering relate to the Event Loop in a browser?**

Rendering (layout, paint) happens between tasks, **after** the Microtask Queue is fully drained. From rendering's perspective, a task + all its microtasks form an atomic block. Intermediate visual states created via Promise.then are invisible to the user — rendering only occurs after the entire queue is empty. The `requestAnimationFrame` callback fires immediately before rendering, after all microtasks.

---

**What happens if you create an infinite Promise chain inside `.then`?**

An infinite chain of microtasks starves the Event Loop permanently: the Microtask Queue drains to empty, but each microtask adds another — the cycle never ends. The Task Queue never gets control. In a browser, the page freezes (no rendering, no event handling); in Node.js, the process blocks. `Promise.resolve().then(function loop() { return Promise.resolve().then(loop); })` demonstrates this.

---

**How does `setTimeout(fn, 0)` differ from `queueMicrotask(fn)`?**

`setTimeout(fn, 0)` places `fn` in the Task Queue as a macrotask. It will run in the next Event Loop iteration, after all current microtasks. A call to `queueMicrotask(fn)` places `fn` in the Microtask Queue instead. That runs at the end of the current task, before the next macrotask and before rendering. The difference is critical: a microtask runs sooner and "sees" state before rendering.

---

## Group 6: Async Patterns

**What is the structural (not syntactic) problem with callbacks?**

The core problem is **inversion of control** (IoC): passing a callback hands control to the callee. Nothing guarantees that the callback runs exactly once, that it never runs synchronously, or that it never arrives with both `err` and `data`. It may also swallow an exception.

The ergonomics suffer too. You cannot `return` a value from a callback, parallel operations need manual counters, error handling is duplicated at every level, and the code reads inside-out.

---

**What happens to a Promise when you call `resolve(anotherPromise)`?**

When a thenable (object with `.then`) is passed to `resolve(value)`, the Promise Resolution Procedure kicks in. The new Promise "follows" that thenable by subscribing to its `.then`. This allows chaining to work with any thenable, not just native Promises. If you pass an already-resolved Promise — the new Promise adopts its value asynchronously (via a microtask).

---

**What does `async/await` conceptually compile to?**

An `async function` always returns a Promise. Each `await expr` conceptually becomes `expr.then(continuation)` — everything after `await` becomes a callback. `try/catch` around `await` becomes `.catch()`. Each `await` adds at minimum one microtask, so multiple sequential `await`s in one async function interleave with microtasks from other functions.

---

**How does `Promise.race` differ from `Promise.any`?**

`Promise.race` settles as soon as the **first** Promise settles (fulfilled OR rejected). `Promise.any` settles as soon as the **first** Promise fulfills; it only rejects when all have rejected — with `AggregateError` containing all reasons. A `race` with an immediately-rejecting Promise rejects at once, while `any` keeps waiting for the rest.

---

**What is `Promise.allSettled` and when should it be used instead of `Promise.all`?**

`Promise.allSettled` always resolves (never rejects) — returning an array of `{ status: 'fulfilled', value } | { status: 'rejected', reason }` for each input Promise. Use it when you need all results regardless of partial failures (e.g., loading multiple dashboard sections — show whatever loaded). `Promise.all` — when you need everything or nothing.

---

**Classic `await` in a loop mistake — what happens and how to fix it?**

`for (const id of ids) { await fetchItem(id); }` — each request waits for the previous one; operations run sequentially: total time = sum of all times. Fix: `Promise.all(ids.map(id => fetchItem(id)))` — all requests fire simultaneously, total time ≈ the maximum. When sequential order is intentional (e.g., rate limiting) — keep the `await` in the loop on purpose.

---

## Group 7: Generators & Iterators

**What is the Iterator Protocol? Implement it manually.**

An Iterable is an object with a `[Symbol.iterator]()` method returning an Iterator. An Iterator is an object with a `next()` method returning `{ value, done }`. `done: false` means a value is available; `done: true` means iteration is complete. Example: `{ [Symbol.iterator]() { return this; }, next() { return done ? { value: undefined, done: true } : { value: current++, done: false }; } }`.

---

**How does a generator function differ from a regular function when called?**

Calling `gen()` does not execute the code — it creates a generator object in state `suspendedStart` and returns it. Code runs only on the first `gen.next()`. This is the key distinction: `function* g() { console.log('hi'); }; g();` — prints nothing. A generator is simultaneously an Iterator and an Iterable: `gen[Symbol.iterator]() === gen` is true.

---

**What is passed to the first `next(value)` of a generator?**

The value of the first `next(value)` is **ignored**. There is nowhere for it to go: no preceding `yield` expression exists to receive it. The first `next()` only starts the generator up to the first `yield`. From the second `next(value)` onward, `value` becomes the result of the previous `yield` expression. In `const x = yield 'prompt';` the variable `x` holds whatever the next call passed in.

---

**What does `yield*` do and what does it return?**

`yield*` delegates iteration to another iterable: it yields all of its values in order. The value of the expression `yield* inner()` = the `return` value of the inner generator (the final `IteratorResult.value` when `done: true`). Note that `yield*` works with any iterable (array, string, Set), not just generators.

---

**What are async generators and how are they consumed?**

`async function*` is an async generator that can both `await` and `yield`. Consumed via `for await...of`. Ideal for paginated APIs — fetch the next page only when the consumer is ready — plus data streaming and lazy async pipelines. Note that `for await...of` also works with synchronous iterables, wrapping each value in Promise.resolve, but not the other way round.

---

## Group 8: Proxy, Reflect & Symbols

**What is the difference between `Reflect.get(target, prop, receiver)` and `target[prop]`?**

`target[prop]` with a getter in the prototype invokes the getter with `this = target` (the object where the property was found). `Reflect.get(target, prop, receiver)` passes `receiver` as `this` to the getter. Inside a Proxy `get(target, prop, receiver)` trap, `receiver` = the proxy itself — which is correct for inherited getters. Using `target[prop]` instead of `Reflect.get` breaks inherited getter behavior.

---

**What are Proxy invariants and why do they exist?**

Invariants are restrictions that Proxy traps cannot violate. Example: a `get` trap for a non-configurable, non-writable property must return its real value (TypeError otherwise). The purpose: to guarantee that a Proxy cannot "lie" about immutable properties and break the language's fundamental assumptions about data integrity.

---

**How does Vue 3 use Proxy for reactivity?**

`reactive(obj)` wraps an object in a Proxy with two traps:

```txt
get trap → calls track(target, prop) on every read
set trap → calls trigger(target, prop) on every write
```

The `track` call records that the current `activeEffect` depends on this property. The `trigger` call re-runs all dependent effects when the property changes. This lets the UI (user interface) update automatically on a state mutation, with no explicit subscription.

---

**How does `Symbol.for('key')` differ from `Symbol('key')`?**

`Symbol('key')` creates a new unique symbol each time — `Symbol('key') !== Symbol('key')`. `Symbol.for('key')` searches the global registry: if a symbol with that key exists, it returns it; otherwise it creates and registers one. `Symbol.for('key') === Symbol.for('key')` is true. The global registry works across modules and realms (iframes, Workers).

---

**What are well-known symbols? Give three examples with practical meaning.**

Well-known symbols are predefined symbols that override an object's behavior in standard operations. `Symbol.iterator` — makes an object iterable (for...of, spread). `Symbol.toPrimitive` — controls type coercion (hint: 'number'/'string'/'default'). `Symbol.hasInstance` — custom `instanceof` logic. `Symbol.toStringTag` — custom `Object.prototype.toString.call()` tag.

---

## Group 9: Memory Management

**Explain V8's generational GC (enough for an interview).**

V8 divides the heap into two generations:

```txt
Young Generation — new objects, ~1-8 MB
Old Generation   — long-lived objects
```

Minor GC (Scavenge) works only on Young. It copies live objects into a new semi-space (Cheney's algorithm); dead ones are lost automatically. Objects surviving 2 Minor GCs are promoted to Old Generation. Major GC (Mark-Sweep-Compact) traverses the full graph from GC Roots and removes unreachable objects. Orinoco adds incremental and concurrent marking, which reduces stop-the-world pauses.

---

**What are GC Roots in JavaScript?**

GC Roots are the starting points for marking, always considered live:

```txt
1. global variables (window, globalThis)
2. the call stack — locals of all active functions
3. live closures — Environment Records referenced by
   live functions
4. V8 internal references
```

An object is reachable if a path exists from any GC Root to it.

---

**Why use `WeakMap` and when is it preferable to `Map`?**

`WeakMap` holds keys weakly: if an object-key has no other references, the GC can collect it and will automatically delete the entry from the WeakMap. This prevents leaks when caching data attached to objects such as nodes of the DOM (document object model) or request objects. A `Map` would retain those keys forever. `WeakMap` is not iterable and has no `.size`: the spec cannot guarantee a consistent snapshot of weak keys.

---

**What does `WeakRef` guarantee and what does it not?**

`WeakRef` holds a weak reference that does not prevent GC. A call to `.deref()` returns the object, or `undefined` if it was collected. Three things are **not** guaranteed:

```txt
- when the object will be collected
- whether it will ever be collected (the spec allows an
  immortal object behind a WeakRef)
- that deref() returns undefined right after obj = null
  (GC is not deterministic)
```

Use it only for opportunistic caches, where losing a value is acceptable.

---

## Group 10: Coercion & Equality

**Describe the Abstract Equality Comparison (`==`) algorithm step by step.**

Algorithm for `x == y`:

```txt
1. same types        → Strict Equality
2. null == undefined → true, and vice versa;
                       either one with anything else → false
3. Number vs String  → ToNumber(String)
4. Boolean           → ToNumber, repeat
5. Object vs String/Number/Symbol
                     → ToPrimitive(Object), repeat
6. otherwise         → false
```

Key point: `null` equals only `null` and `undefined` — step 2 intercepts before everything else.

---

**Why is `typeof null === 'object'` a recognized bug?**

In the original JS implementation (1995), values were stored as 32-bit words, with the lower 3 bits as the type tag. The value `null` was represented as a null pointer (0x000), whose tag `000` means object. This is a bug that was proposed for fixing in ECMAScript 2015 but was rejected for backwards compatibility. The correct null check: only `x === null`.

---

**What is the difference between `Object.is`, `===`, and `==`?**

`==` is Abstract Equality with type coercion. `===` is Strict Equality without coercion, but with two exceptions: `NaN !== NaN` and `+0 === -0`. `Object.is` is the SameValue algorithm: `NaN === NaN` (true), `+0 !== -0` (false). `Object.is` is used in React for dependency comparison and in Map/Set as SameValueZero (a variant where `+0 === -0`).

---

**Why is `isNaN('hello') === true` but `Number.isNaN('hello') === false`?**

The global `isNaN(x)` first applies `ToNumber(x)`: `ToNumber('hello') = NaN`, then checks for NaN (not a number) → true. `Number.isNaN(x)` is a strict check: returns `true` only if `typeof x === 'number' && x !== x`. A string will never pass the first check → false. Rule: always use `Number.isNaN` for checking actual NaN.

---

**Why does `[] == false` equal `true` but `if ([])` executes?**

These are different algorithms. `if ([])` uses `ToBoolean([])`, and an object is always truthy. The `[] == false` comparison uses Abstract Equality:

```txt
step 4: false → 0        → [] == 0
step 5: [] → ToPrimitive → '' == 0
step 3: '' → 0           → 0 == 0 → true
```

With a Boolean, `==` first converts that Boolean to Number. It does not use ToBoolean.

---

## Group 11: Modules

**What happens with `exports = { ... }` in a CommonJS module?**

`exports` is a local variable that initially points to `module.exports`. Reassigning `exports = { ... }` creates a new object, but `module.exports` remains the original empty object. `require()` returns `module.exports`, not `exports`. The changes are lost. Correct: `module.exports = { ... }` or adding properties via `exports.key = value`.

---

**What are live bindings in ESM and how do they differ from CJS?**

ESM (ECMAScript Modules) exports a **binding**, while CJS (CommonJS) exports a value. A binding is a live reference to a variable in the exporting module. When that variable changes inside the module, the importing side sees the new value. A CJS export is taken at the moment of `module.exports`, and for primitives that is a copy.

Take `export let count = 0; export function inc() { count++; }`. In ESM, `import { count }; inc(); count;` gives 1. With CJS, a destructured `count` would still be 0.

---

**How do circular dependencies behave in CJS and ESM — what is the key difference?**

CJS: with a cycle, B receives A's **current** `module.exports` at the time of the circular `require`. That is a partially filled object — only what was assigned so far. ESM: the Linking phase creates all bindings before evaluation (live bindings exist), but they may be in the TDZ until initialized. ESM cycle fix: use function accessors instead of direct values — functions access the binding later, after initialization.

---

**Can `require()` load an ESM module?**

Since Node.js 22.12 (and 20.19) it can, under one condition: the module graph must contain no top-level `await`. Otherwise Node.js throws `ERR_REQUIRE_ASYNC_MODULE`. The reason is that `require()` is synchronous and cannot wait for an asynchronous module.

On older versions, any `require()` of ESM throws `ERR_REQUIRE_ESM`. The universal fix works everywhere: dynamic `await import('./esm-module.mjs')` from a CJS context returns a Promise with the namespace object.

---

**What is top-level await and how does it affect dependent modules?**

Top-level await is available only in ESM. A module with `export const data = await fetch(...)` is considered "ready" only after the `await` completes. All modules importing this module wait for it — they won't start executing until the top-level await resolves. This makes the entire dependency graph asynchronous. Independent modules with top-level await can be loaded in parallel.

---

## Group 12: Modern JavaScript

**How does `??` fundamentally differ from `||` — show a case where the choice matters.**

`||` triggers on any falsy value (0, `''`, `false`, `null`, `undefined`, `NaN`). `??` — only on `null`/`undefined`. Critical case: `config.retries ?? 3` — if `retries = 0`, returns 0 (correct). `config.retries || 3` — returns 3 (bug: replaces a valid 0 with the default). Same applies to an empty string as a valid value.

---

**What can `structuredClone` do that `JSON.parse(JSON.stringify())` cannot?**

`structuredClone` correctly clones: `Date` (stays a Date, not a string), `RegExp`, `Map`, `Set`, `ArrayBuffer`, `undefined` (not removed), and circular references (doesn't throw). JSON loses functions and `undefined`, turns `Date` into a string, throws on cycles, and replaces `NaN`/`Infinity` with `null`. Limitation of `structuredClone`: cannot clone functions, DOM nodes, and loses the prototype of class instances.

---

**How does AbortController cancel a `fetch` and what happens on the server side?**

`controller.abort()` sets `signal.aborted = true` and dispatches an `abort` event. The `fetch` call subscribes to that `signal` and cancels the HTTP request on abort: the browser closes the connection. The promise from `fetch` rejects with `AbortError`.

On the **server side** the story differs. The server may be unaware of the cancellation and keeps processing the request. Server-side cancellation needs an explicit mechanism, for example a cancellation token in the request body.

---

**What is a tagged template literal and what does the tag function receive?**

A tag is a function called with the `` tag`template ${expr}` `` syntax. It receives two things:

```txt
strings   — frozen array of string parts, plus strings.raw
            with the raw escape sequences
...values — the evaluated expressions
```

The function can return anything, not necessarily a string. Use cases: a query builder for SQL (structured query language) with parameters instead of string concatenation, an HTML sanitizer, `styled-components`, `gql`.

---

## Group 13: Predict the Output

**Question 1 — Event Loop + async/await**

```js
async function a() {
  console.log(1);
  await Promise.resolve();
  console.log(2);
}

console.log(3);
a();
console.log(4);
```

What does the code print and in what order?

<details>
<summary>Answer</summary>

`3, 1, 4, 2`. Synchronously: `3` → `a()` starts → `1` → `await` suspends `a()`, control returns → `4`. Stack is empty → drain Microtask Queue: `2`.

</details>

---

**Question 2 — Microtask Queue + nested Promises**

```js
Promise.resolve()
  .then(() => {
    console.log('A');
    Promise.resolve().then(() => console.log('B'));
  })
  .then(() => console.log('C'));

Promise.resolve().then(() => console.log('D'));
```

<details>
<summary>Answer</summary>

`A, D, B, C`. After sync code, queue is `[mA, mD]`. Run `mA`: 'A', enqueue `mB`, `mA` done → enqueue `mC`. Queue: `[mD, mB, mC]`. D → B → C.

</details>

---

**Question 3 — Closure + var in a loop**

```js
const fns = [];
for (var i = 0; i < 3; i++) {
  fns.push(() => i);
}
console.log(fns[0](), fns[1](), fns[2]());
```

<details>
<summary>Answer</summary>

`3 3 3`. All three arrows close over the same ER (global or function scope), where `var i` is one single variable. By the time the functions are called, the loop has finished and `i` is 3.

</details>

---

**Question 4 — Prototypes + this**

```js
function Animal(name) { this.name = name; }
Animal.prototype.speak = function() { return this.name; };

const dog = new Animal('Rex');
const speak = dog.speak;

console.log(dog.speak());  // ?
console.log(speak());      // ?
```

<details>
<summary>Answer</summary>

`'Rex'`, then `undefined` (strict) or `''` (sloppy / `globalThis.name`). `dog.speak()` — implicit binding, `this = dog`. `speak()` — default binding, `this = globalThis` or `undefined` in strict mode.

</details>

---

**Question 5 — Coercion**

```js
console.log([] + []);      // ?
console.log([] + {});      // ?
console.log(+[]);          // ?
console.log(+{});          // ?
console.log('' == false);  // ?
console.log(null == false); // ?
```

<details>
<summary>Answer</summary>

`''`, `'[object Object]'`, `0`, `NaN`, `true`, `false`.

```txt
[] → '' and {} → '[object Object]'   via ToPrimitive
+[]  = ToNumber('') = 0
+{}  = ToNumber('[object Object]') = NaN
'' == false    → false→0, ''→0, 0==0 → true
null == false  → null equals only null/undefined → false
```

</details>

---

**Question 6 — ESM live bindings**

```js
// counter.mjs
export let x = 1;
export const inc = () => x++;

// main.mjs
import { x, inc } from './counter.mjs';
console.log(x); // ?
inc();
inc();
console.log(x); // ?
const snap = x;
inc();
console.log(snap === x); // ?
```

<details>
<summary>Answer</summary>

`1`, `3`, `false`. Here `x` is a live binding, updated on each `inc()`. The assignment `snap = x` copies the current primitive value (3) into a local variable, not the binding itself. After one more `inc()`, `x` is 4 and `snap` is 3, so `3 !== 4` → false.

</details>

---

**Question 7 — Proxy + Symbol.toPrimitive**

```js
const p = new Proxy({ val: 10 }, {
  get(t, prop, r) {
    if (prop === Symbol.toPrimitive)
      return hint => t.val * (hint === 'string' ? -1 : 2);
    return Reflect.get(t, prop, r);
  }
});

console.log(+p);     // ?
console.log(`${p}`); // ?
console.log(p + 1);  // ?
```

<details>
<summary>Answer</summary>

`20`, `'-10'`, `21`.

```txt
+p       → hint 'number'  → 10*2 = 20
`${p}`   → hint 'string'  → 10*-1 = -10 → template gives '-10'
p + 1    → hint 'default' → 10*2 = 20 → 20+1 = 21
```

</details>

---

**Question 8 — Generator two-way communication**

```js
function* gen() {
  const a = yield 1;
  const b = yield 2;
  return a + b;
}
const g = gen();
console.log(g.next('x').value); // ?
console.log(g.next(10).value);  // ?
console.log(g.next(20).value);  // ?
```

<details>
<summary>Answer</summary>

`1`, `2`, `30`. The first `next('x')` — 'x' is ignored, runs to `yield 1` → `{ value: 1 }`. The second `next(10)` — 10 becomes the result of `yield 1`, `a = 10`, runs to `yield 2` → `{ value: 2 }`. The third `next(20)` — 20 becomes the result of `yield 2`, `b = 20`, `return a + b = 30` → `{ value: 30, done: true }`.

</details>
