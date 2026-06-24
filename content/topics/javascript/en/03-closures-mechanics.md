# Closures: The Mechanics

## What a closure actually is — the engine-level definition

The popular explanation: "a closure is a function that remembers variables from its lexical environment." That's correct but imprecise. More precisely:

**A closure = a function + a reference to the Environment Record it was created in.**

Not a copy of variables, not a snapshot of values — a **live reference** to the Environment Record itself. This is fundamental: if a variable in that Environment Record changes after the function was created, the function sees the new value.

In the spec, every Function Object has an internal slot `[[Environment]]`:

```txt
Function Object {
  [[Call]]          — the function call algorithm
  [[Environment]]   → reference to the Environment Record where the function was created
  [[FormalParameters]], [[ECMAScriptCode]], ...
}
```

When a function is called, the engine creates a new Function Environment Record and sets its `[[OuterEnv]]` = the function's `[[Environment]]`. That's how the scope chain is formed.

**Every function in JS is a closure.** Even a top-level function closes over the Global Environment Record. The term "closure" is typically applied when a function has a non-trivial `[[Environment]]` — one that closes over something beyond the global scope.

```js
function makeCounter() {
  let count = 0; // in makeCounter's Environment Record

  return {
    increment() { count++; },   // [[Environment]] → makeCounter's ER
    decrement() { count--; },   // [[Environment]] → makeCounter's ER
    getValue()  { return count; }, // [[Environment]] → makeCounter's ER
  };
}

const counter = makeCounter();
counter.increment();
counter.increment();
counter.decrement();
console.log(counter.getValue()); // 1

// All three methods close over THE SAME ER of makeCounter.
// Changing count via increment is visible via getValue — because
// it's one variable in one ER, not three separate copies.
```

## The classic `var`-in-loop trap — mechanical explanation

```js
// Predict the output:
for (var i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 0);
}
// ?
```

<details>
<summary>Answer</summary>

**`3, 3, 3`**

Here's what happens step by step:

1. `var i` is declared in the VariableEnvironment of **the function (or global context)**. The `for` block does not create a new scope for `var`.
2. Three arrow function callbacks are created. Each has `[[Environment]]` = the same ER (containing `i`). This is one reference to one `i`, not three copies.
3. The loop finishes. `i` becomes `3`.
4. The setTimeout callbacks are placed in the task queue and execute after the synchronous code completes.
5. Each callback reads `i` from its `[[Environment]]` — and all three see the **current** value `i = 3`.

```txt
Environment Record (function/global):
  i → 3  ← all three callbacks read from here
```

</details>

**Three ways to fix it — with different mechanics:**

```js
// Way 1: IIFE — creates a new ER per iteration (ES5 style)
for (var i = 0; i < 3; i++) {
  (function(captured) {
    setTimeout(() => console.log(captured), 0);
  })(i);
  // The IIFE creates a new ER with a separate `captured`,
  // initialized to the current value of i
}
// 0, 1, 2 ✅

// Way 2: let — the spec requires a new binding to be created per iteration
for (let i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 0);
}
// 0, 1, 2 ✅
// Mechanics: on each iteration a new LexicalEnvironment is created
// with a copy of i initialized to the current value

// Way 3: capture the value via a function parameter
for (var i = 0; i < 3; i++) {
  setTimeout(console.log.bind(null, i), 0);
}
// 0, 1, 2 ✅ — bind freezes the argument at the time of the call
```

## Closures and memory — what V8 actually retains

Closures are one of the primary sources of memory leaks in JS. To understand why, you need to know what the engine keeps in memory.

### What the GC considers "alive"

V8's garbage collector (generational mark-and-sweep) keeps an object alive if there's a **reachable reference** to it — a path from GC roots (stack, global variables, live closures).

A closure keeps the entire Environment Record that its `[[Environment]]` points to alive. This means: if at least one function is alive and closes over an ER, the entire ER stays in memory, even if that live function doesn't use every variable in that ER.

```js
function createLeak() {
  const hugeData = new Array(1_000_000).fill('leak'); // 1M elements
  const smallData = 'tiny';

  // This function only uses smallData,
  // but it closes over createLeak's ER, which contains hugeData
  return function() {
    return smallData;
  };
}

const fn = createLeak();
// fn is alive → createLeak's ER is alive → hugeData is alive
// hugeData will NOT be GC'd, even though fn never accesses it
```

### V8 context optimization (and its limits)

V8 performs **closure analysis**: when compiling a function, it analyzes which variables from outer scopes are actually used. Variables not used by any live inner function may be excluded from the "captured" Environment Record.

However: if multiple functions close over the **same** ER, V8 uses a **shared Context object** for all of them. If at least one of those functions uses a "large" variable, the Context retains it for all — even for functions that don't use it.

```js
function problem() {
  const huge = new Array(1_000_000).fill(0);
  const small = 'ok';

  const useSmall = () => small;  // doesn't use huge
  const useHuge  = () => huge;   // uses huge

  return useSmall; // only returning useSmall
  // But! useHuge and useSmall were created in the same scope →
  // V8 creates one shared Context object containing BOTH huge AND small.
  // Even after returning useSmall, huge remains in memory
  // because the Context is alive due to useSmall.
}
```

This is a known issue documented by Vyacheslav Egorov (V8 developer) and verifiable via Chrome DevTools heap snapshots.

### Primary leak scenarios via closures

**1. Forgotten timers:**
```js
class Widget {
  constructor() {
    this.data = new Array(100_000).fill('data');
    // setInterval keeps the callback alive, the callback closes over this,
    // this keeps data alive — the entire graph lives as long as the timer does
    this.timer = setInterval(() => {
      console.log('tick', this.data.length);
    }, 1000);
  }

  destroy() {
    clearInterval(this.timer); // ✅ without this — a leak
  }
}
```

**2. Detached DOM nodes:**
```js
function setup() {
  const button = document.getElementById('btn');
  const cache = new Array(100_000).fill('cached'); // large data

  button.addEventListener('click', () => {
    console.log(cache.length); // closes over cache
  });

  // If button is removed from the DOM but the listener isn't removed —
  // button (detached node) and cache both live in memory
  document.body.removeChild(button);
  // ❌ need: button.removeEventListener('click', handler)
  // or AbortController
}
```

**3. Global collections accumulating closures:**
```js
const handlers = []; // global array

function register(id) {
  const data = fetchLargeData(id); // heavy data
  handlers.push(() => process(data)); // closure lives as long as handlers does
}

// If handlers is never cleared → leak proportional to the number of register calls
```

**WeakRef and FinalizationRegistry** (ES2021) — tools for GC-safe references, covered in depth in [Memory Management].

## Practical closure-based patterns

### Module Pattern

Before ESM, closures via IIFE were the only way to create "private" variables:

```js
const userStore = (() => {
  // Private state — inaccessible from outside
  const users = new Map();
  let nextId = 1;

  // Private function
  function generateId() {
    return nextId++;
  }

  // Public API
  return {
    add(name) {
      const id = generateId();
      users.set(id, { id, name });
      return id;
    },
    get(id) {
      return users.get(id);
    },
    count() {
      return users.size;
    },
  };
})();

userStore.add('Alice'); // 1
userStore.add('Bob');   // 2
userStore.count();      // 2
userStore.users;        // undefined — private
```

### Factory functions and private state

A more flexible variant of the module pattern — without being a singleton:

```js
function createStack() {
  const items = []; // private

  return {
    push(item) { items.push(item); },
    pop() {
      if (items.length === 0) throw new Error('Stack is empty');
      return items.pop();
    },
    peek() { return items[items.length - 1]; },
    get size() { return items.length; },
    [Symbol.iterator]() { return [...items].reverse().values(); },
  };
}

const stack = createStack();
stack.push(1);
stack.push(2);
stack.pop(); // 2
stack.items; // undefined — the array is not directly accessible
```

### Memoization

```js
function memoize(fn) {
  const cache = new Map(); // closed over by the returned function

  return function(...args) {
    const key = JSON.stringify(args);
    if (cache.has(key)) {
      return cache.get(key);
    }
    const result = fn.apply(this, args);
    cache.set(key, result);
    return result;
  };
}

const expensiveCalc = memoize((n) => {
  console.log(`Computing for ${n}...`);
  return n * n;
});

expensiveCalc(5); // "Computing for 5..." → 25
expensiveCalc(5); // → 25 (from cache, no log)
expensiveCalc(6); // "Computing for 6..." → 36
```

Note: `JSON.stringify` as a key doesn't work for objects with circular references or functions. For complex cases, use a `Map` with the first argument as the key or a recursive approach (see libraries like `fast-memoize`).

### Once — a function that runs only once

```js
function once(fn) {
  let called = false;
  let result;

  return function(...args) {
    if (!called) {
      called = true;
      result = fn.apply(this, args);
    }
    return result;
  };
}

const initialize = once(() => {
  console.log('Init!');
  return { ready: true };
});

initialize(); // "Init!" → { ready: true }
initialize(); // → { ready: true } (no log)
initialize(); // → { ready: true }
```

## Predict the output — closure chain

```js
function makeAdder(x) {
  return function(y) {
    return x + y;
  };
}

const add5 = makeAdder(5);
const add10 = makeAdder(10);

console.log(add5(3));        // ?
console.log(add10(3));       // ?
console.log(add5(add10(1))); // ?

// Variation: what if x is an object?
function makeObjectAdder(obj) {
  return function(val) {
    obj.value += val; // mutating the object!
    return obj.value;
  };
}

const counter = { value: 0 };
const inc = makeObjectAdder(counter);

inc(1); // ?
inc(2); // ?
console.log(counter.value); // ?
```

<details>
<summary>Answer</summary>

```
8   // add5(3) = 5 + 3
13  // add10(3) = 10 + 3
16  // add10(1) = 11, add5(11) = 5 + 11

// makeObjectAdder:
1   // inc(1): counter.value = 0 + 1 = 1
3   // inc(2): counter.value = 1 + 2 = 3
3   // counter.value: the mutation is visible outside
```

The last example shows that a closure holds a **reference** to the object, not a copy of its value. Mutating the object through the closure is visible to anyone else holding a reference to the same object.

</details>

## Closures vs Classes — when to use which

```js
// Factory function (closure)
function createUser(name) {
  let _name = name; // private

  return {
    getName() { return _name; },
    setName(n) { _name = n; },
  };
}

// Class (with # private fields or convention)
class User {
  #name; // truly private (ES2022)

  constructor(name) { this.#name = name; }
  getName() { return this.#name; }
  setName(n) { this.#name = n; }
}
```

**Factory function:** each method is a separate function object in memory, no prototype chain. Creating 10,000 objects means 10,000 copies of each method. Privacy via closure.

**Class:** methods live on `User.prototype`, all instances share one set of methods. Privacy via `#` is enforced at the engine level. More memory-efficient when creating many instances.

## Connection to other topics

```txt
[Execution Contexts]    — a closure = [[Environment]] → the ER created
                           during that execution context
[this binding]          — arrow functions capture this through the same
                           mechanism: no own ThisBinding + resolution
                           via Scope Chain (through the ER)
[Memory Management]     — closures as the primary cause of leaks;
                           WeakMap/WeakRef as GC-safe reference tools
[Generators]            — a generator stores state in its own ER,
                           suspending execution — closure + control flow
```

## Common interview traps

- **"A closure is a copy of variables"** — no. It's a live reference to an Environment Record. Changing a variable is visible to all closures referencing the same ER. The var-in-loop case works exactly this way: all callbacks see one variable because they close over one ER.

- **"A closure only retains the variables it uses"** — partially true in V8 when no other closures share the same ER. But if multiple functions close over one ER, V8 creates a shared Context object that retains everything used by any of them. This is the real cause of "unexpected" leaks.

- **"The module pattern is obsolete — we have classes now"** — they're different tools. Classes with `#` fields give true privacy, but the module pattern is still used for singletons and configuration that doesn't need `new`.

- **"The only fix for var-in-loop is let"** — `let` is the cleanest fix, but historically IIFE and `bind` work too and appear in legacy code.

- **Not spotting the leak in timer/event patterns** — the most common practical error. A closure in a timer/listener callback keeps the entire parent scope alive. `clearInterval`/`removeEventListener` are required on teardown.

- **"Closures are a complex, JS-specific concept"** — no. Closures exist in most modern languages (Python, Go, Rust, Swift). They're especially visible in JS due to the heavy use of callback patterns and asynchronous code.
