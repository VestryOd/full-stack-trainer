# Modules: ESM vs CommonJS

## CommonJS — the mechanics from the inside

CommonJS (CJS) is Node.js's module system that predates ESM standardization. Understanding its mechanics matters for working with legacy code and for explaining the key differences from ESM.

### The module wrapper

Every CJS file is **wrapped in a function** before execution:

```js
(function(exports, require, module, __filename, __dirname) {
  // Your module code here
});
```

This is where `exports`, `require`, `module`, `__filename`, and `__dirname` come from — they're not global variables, they're **wrapper parameters**. Node.js invokes this function on the first `require()` of a module.

### `module.exports` vs `exports`

The most common CJS trap:

```js
// exports is a local variable that initially points to module.exports:
console.log(exports === module.exports); // true

// ✅ Adding properties — works through either:
exports.foo = 1;        // module.exports.foo = 1 ← same thing
module.exports.bar = 2; // module.exports.bar = 2

// ❌ Reassigning exports — breaks the connection:
exports = { foo: 1 }; // exports is now a new object; module.exports is unchanged

// require() returns module.exports, not exports!
// If exports is reassigned, the changes are lost
module.exports = { foo: 1 }; // ✅ correct way to replace the entire export
```

```js
// ❌ Common mistake:
// counter.js
exports = function() { return ++count; }; // won't work

// ✅ Correct:
module.exports = function() { return ++count; };
```

### `require` caching

CJS caches each module by its **absolute file path** in `require.cache`. A subsequent `require()` returns the cached `module.exports` without re-executing the code:

```js
// Inspect the cache:
Object.keys(require.cache); // all loaded modules

// Invalidate the cache (rare, but useful in testing):
delete require.cache[require.resolve('./my-module')];

// Proof of caching:
// counter.js
let count = 0;
module.exports = { increment: () => ++count, get: () => count };

// main.js
const a = require('./counter');
const b = require('./counter'); // same object
a.increment();
console.log(b.get()); // 1 — a and b reference the same module.exports
```

### `require()` — synchronous, dynamic

```js
// Path computed at runtime — allowed:
const plugin = require(`./plugins/${pluginName}`);

// Conditional import — allowed:
if (process.env.NODE_ENV === 'test') {
  const mock = require('./mocks/db');
}

// require in the middle of a function — allowed:
function loadConfig() {
  return require('./config.json'); // JSON is parsed automatically
}
```

## ESM — the mechanics from the inside

ESM (ECMAScript Modules) is the language's standard module system. A fundamentally different model: **static analysis, live bindings, asynchronous loading**.

### Three phases of ESM execution

```txt
1. Parsing
   — the engine parses the dependency graph (all imports)
   — paths must be string literals (no runtime computation)
   — Module Records are created for all modules

2. Linking
   — Environment Records are created for each module
   — exported bindings (let/const/function) are created but not initialized
   — imported names are linked to those bindings

3. Evaluation
   — modules execute in dependency order (post-order)
   — bindings are initialized with values
```

The key point: **imports are not copies** — they are **live bindings** (live references to the exported bindings).

### Live bindings vs CJS copies

```js
// === counter.mjs ===
export let count = 0;
export function increment() { count++; }

// === main.mjs ===
import { count, increment } from './counter.mjs';

console.log(count); // 0
increment();
console.log(count); // 1 ← live binding: we see the updated value!

// With the CJS equivalent:
// === counter.cjs ===
let count = 0;
module.exports = {
  count,               // ← copy of count's value at the time of exports
  increment() { count++; }
};

// === main.cjs ===
const { count, increment } = require('./counter.cjs');
console.log(count); // 0
increment();
console.log(count); // 0 ← CJS: we copied the primitive, not the binding
                    //         count inside the module changed, but our copy didn't
```

This is the fundamental difference: ESM exports a **binding**, CJS exports a **value** (a copy for primitives, a reference for objects).

### Import hoisting

`import` declarations are **hoisted** — they are processed before the module's code runs. The engine links all imports during the Linking phase, not when the `import` line is reached.

```js
// This is legal in ESM:
foo(); // works even though import is below

import { foo } from './utils.mjs';
// foo — a function declaration in utils.mjs, also hoisted within it

// But you can't access hoisted let/const values from another module:
console.log(bar); // ReferenceError (TDZ) if bar is let/const in utils.mjs
import { bar } from './utils.mjs';
```

### ESM is always strict mode

```js
// In an ESM module — automatically strict mode, no 'use strict' needed:
function sloppy() {
  x = 1; // ReferenceError: x is not defined
          // In CJS without 'use strict' — this would create a global variable
}
```

## Circular dependencies — the senior-level trap

### CJS: the partially-built `module.exports`

In CJS, when A requires B which requires A (a cycle), B receives the **current state of A's `module.exports`** — whatever has been assigned before the circular `require`.

```js
// === a.cjs ===
const b = require('./b.cjs');
console.log('a: b.done =', b.done);

exports.done = true;
console.log('a: finished');

// === b.cjs ===
const a = require('./a.cjs'); // ← circular require
console.log('b: a.done =', a.done);

exports.done = true;
console.log('b: finished');

// Run: node a.cjs
// b: a.done = undefined  ← a hasn't executed exports.done = true yet
// a: b.done = true       ← b has already executed its exports.done
// b: finished
// a: finished
```

Execution order:
1. `a.cjs` starts loading; `require('./b.cjs')` is called
2. `b.cjs` starts loading; `require('./a.cjs')` is called
3. Node sees `a.cjs` in the cache (already loading), returns the **current** `module.exports` — an empty object `{}`
4. `b.cjs` continues with `a = {}`, assigns `b.done = true`, completes
5. `a.cjs` receives the completed `b`, assigns `a.done = true`, completes

### ESM: live bindings help... but not always

In ESM, the Linking phase creates all bindings (but doesn't initialize them). This means that in a cycle, the binding **exists**, but may be in the TDZ:

```js
// === a.mjs ===
import { b } from './b.mjs';
export const a = 'a_value';
console.log('a: b =', b);

// === b.mjs ===
import { a } from './a.mjs';
export const b = 'b_value';
console.log('b: a =', a);
```

```txt
ESM execution order (post-order: dependencies first):
  1. Parsing: a.mjs imports b.mjs, b.mjs imports a.mjs
  2. Linking: create bindings for a and b (both in TDZ)
  3. Evaluation: b.mjs executes first (it's a dependency of a.mjs):
       b is initialized to 'b_value'
       console.log('b: a =', a) → ReferenceError! a is in TDZ

  If b.mjs uses a function instead of const:
  export function getA() { return a; } // ← function captures a later
  // Then calling getA() after a is initialized works fine
```

**The golden rule for ESM cycles**: if you need data from a circular import, use functions (they capture the binding, not the value at creation time), or ensure the needed module is initialized before access.

```js
// ✅ Works with ESM cycles:
// b.mjs
import { a } from './a.mjs';
export function getA() { return a; } // function — accesses a later

// a.mjs
import { getA } from './b.mjs';
export const a = 'hello';
console.log(getA()); // 'hello' — a is initialized by this point
```

## Predict the output — load order

```js
// === lib.mjs ===
export let value = 1;
export function increment() { value++; }
export function getValue() { return value; }

// === main.mjs ===
import { value, increment, getValue } from './lib.mjs';

console.log(value);      // ?
increment();
console.log(value);      // ?
console.log(getValue()); // ?

const snapshot = value;
increment();
console.log(snapshot === value); // ?
```

<details>
<summary>Answer</summary>

```
1     // live binding, initial value
2     // live binding — we see the change inside the module
2     // getValue() reads the same binding
false // snapshot = 2 (primitive copied), then value became 3
      // snapshot (2) !== value (3)
```

Nuance: `const snapshot = value` copies the **current value** of the primitive (2) into a local variable. `value` is a live binding to the variable in lib.mjs, but the assignment `snapshot = value` copies the primitive's value, not the binding itself. So `snapshot` doesn't update with subsequent `increment()` calls.

</details>

## `import()` — dynamic import

`import()` is a function-like operator returning `Promise<namespace>`. Works in both ESM and CJS:

```js
// Lazy loading:
async function loadChart() {
  const { Chart } = await import('./chart.mjs');
  return new Chart(data);
}

// Conditional import (impossible with static import):
const module = await import(
  process.env.NODE_ENV === 'test' ? './mock-db.mjs' : './db.mjs'
);

// import() in CJS can import ESM (require() cannot):
// main.cjs
async function main() {
  const { foo } = await import('./esm-module.mjs'); // ✅
}

// Difference from require():
// require('./module') → returns module.exports
// import('./module')  → returns Promise<namespace object>
//   namespace object: { default, ...namedExports }
```

```js
// The namespace object:
// === utils.mjs ===
export const PI = 3.14;
export default function add(a, b) { return a + b; }

// === main.mjs ===
const ns = await import('./utils.mjs');
ns.PI;            // 3.14
ns.default;       // function add
ns.default(1, 2); // 3
```

## Top-level `await`

ESM modules can use `await` at the top level. Importing modules **wait** for completion:

```js
// === config.mjs ===
const response = await fetch('/api/config');
export const config = await response.json();
// This module is "ready" only when fetch completes

// === app.mjs ===
import { config } from './config.mjs';
// app.mjs won't start executing until config.mjs finishes its await
console.log(config.apiUrl); // guaranteed to be initialized
```

**Impact on parallelism**: if multiple independent modules use top-level await, the engine can load them in parallel.

```js
// ❌ Sequential (slow):
// a.mjs
export const a = await fetchA(); // 500ms

// b.mjs
export const b = await fetchB(); // 500ms

// main.mjs imports a.mjs, then b.mjs → ~1000ms

// ✅ Parallel:
// main.mjs
const [a, b] = await Promise.all([fetchA(), fetchB()]); // ~500ms
export { a, b };
```

Top-level await **does not work** in CJS modules — there's no mechanism for top-level waiting.

## CJS ↔ ESM interop

```txt
CJS → ESM: require() from CJS cannot import ESM (in Node.js)
           Why: require() is synchronous, ESM loads asynchronously
           Fix: use import() (dynamic, returns a Promise)

ESM → CJS: import 'something.cjs' works
           module.exports of CJS becomes the default export in ESM:
           import cjsModule from './module.cjs';
           cjsModule.someMethod(); // via default

Mixed projects — package.json:
  "type": "module"    → .js files = ESM, .cjs = CJS
  "type": "commonjs"  → .js files = CJS, .mjs = ESM (default)

Dual packages (CJS + ESM):
  package.json exports:
    { "import": "./dist/esm/index.mjs",
      "require": "./dist/cjs/index.cjs" }
```

## Key differences: summary table

```txt
Feature              CJS                        ESM
────────────────────────────────────────────────────────────────
Syntax               require/module.exports     import/export
Loading              Synchronous (blocking)     Asynchronous
Dependency analysis  Runtime (dynamic)          Parse time (static)
Import paths         Computed (dynamic)         String literals only
Exported values      Copy (for primitives)      Live binding
Strict mode          Optional                   Always
Top-level await      ❌                          ✅
Tree-shaking         ❌ (difficult)              ✅ (static analysis)
Circular deps        Partially-built            Live bindings (TDZ risk)
                     module.exports
```

## Connection to other topics

```txt
[Execution Contexts]    — Module Environment Record: import bindings
                           are live bindings in the LexicalEnvironment
[Event Loop]            — ESM loading is async; top-level await
                           blocks dependent modules via Promise
[Generators]            — for-await-of, async generators work
                           only in ESM (or async functions)
[Modern JS]             — dynamic import(), AbortSignal for cancelling
                           fetch inside top-level await
```

## Common interview traps

- **"`exports = {...}` is the same as `module.exports = {...}`"** — no. `exports` is a local reference variable. Reassigning `exports` breaks the link to `module.exports`. `require()` always returns `module.exports`.

- **"ESM import is just CJS require with different syntax"** — no. Three fundamental differences: static analysis (ESM) vs runtime (CJS), live bindings (ESM) vs copies (CJS), async (ESM) vs sync (CJS).

- **"Tree-shaking works with CJS"** — not properly. Tree-shaking requires static analysis of exports/imports. CJS is dynamic; exports can be computed. Bundlers (webpack, rollup) try, but with significant limitations.

- **"Circular dependencies are always an error"** — no, both systems support cycles. But you must understand what you get: CJS gives a partially-executed `module.exports`; ESM gives a live binding (potentially in TDZ). Fix: use accessor functions instead of directly exporting values.

- **"`import()` and `require()` are the same"** — no. `import()` returns `Promise<namespace object>` with `default` and named exports. `require()` returns `module.exports` synchronously. `import()` can load ESM modules from a CJS context; `require()` cannot.

- **"Top-level await is available in any JS file"** — only in ESM modules. In CJS (`require`/`module.exports`) there is no top-level waiting mechanism.

- **"ESM live bindings are like object references"** — no. An object reference lets you mutate the object through it. An ESM live binding is a reference to a **binding** (a variable in another module) that updates on every read. You cannot mutate `count` from another module through an import — only through an exported function.
