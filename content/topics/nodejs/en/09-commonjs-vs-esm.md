# CommonJS vs ES Modules

## Why this isn't just "a syntax difference"

The two systems differ in **when and how a module is loaded**, not only in the keywords you type. CommonJS (CJS) runs `require()` synchronously and gives you a copy of the exported values. ES Modules (ESM — ES stands for ECMAScript, the standard behind JavaScript) parse the whole dependency graph first, then link live bindings between modules.

The shallow answer is "CommonJS uses `require`/`module.exports`, ESM uses `import`/`export`, ESM is better for tree shaking". That's true, but it stops early. At a senior level the question almost always moves on to three things:

- What happens to variables in a circular dependency.
- How module resolution actually works.
- What really happens when CJS and ESM are mixed in one project.

The last one is where real migrations lose hours in practice.

## CommonJS: `require` isn't "just an import" — it's a synchronous function call

```ts
// What you write:
const { readFile } = require('fs');
module.exports = { processFile };
```

```ts
// What Node wraps every file in before executing it:
(function (exports, require, module, __filename, __dirname) {
  const { readFile } = require('fs');
  module.exports = { processFile };
});
```

```txt
This explains:
  - where __dirname/__filename/require/module/exports come
    from "out of thin air" — they're parameters of the
    wrapper function
  - why a module's top-level code has its own scope (module
    variables don't leak into global)
  - why require() is a synchronous operation: it's a regular
    function call that must return a value before execution
    continues
```

### Module resolution algorithm — where hours get lost debugging

```txt
require('./utils')     → ./utils.js, ./utils.json,
                          ./utils.node, ./utils/index.js
                          (in this order)

require('lodash')       → looks for node_modules/lodash in the
                           current directory, then the parent,
                           and so on up to the filesystem root
                           (so one version of lodash can end up
                           duplicated across node_modules at
                           different levels on a version
                           conflict)

require('lodash')       → reads lodash's package.json, looks at
                           the "main" field (or "exports" for
                           modern packages) — the entry point is
                           not necessarily index.js
```

### Module Cache — keyed by the absolute path, not the import string

```ts
// a.js and b.js both do:
require('./utils');      // from directory /src
require('../src/utils');  // from directory /src/sub — the same file

// Node caches by the resolved absolute file path —
// so both calls return the same exports object, even
// though the import strings differ
```

## ESM: modules load in three phases — why this matters

```txt
CommonJS: loading and execution are one operation (require
executes the file synchronously, top to bottom).

ESM (per the ECMAScript spec) has three distinct phases:
  1. Construction (Parsing) — parse all modules in the
     dependency graph, build a "module record" for each,
     without executing any code
  2. Instantiation — allocate storage for all export/import
     bindings (link modules together), still without
     executing code
  3. Evaluation — execute module code, in dependency order
     (from the leaves of the graph toward the root)
```

This three-phase loading is exactly what makes **top-level await** possible. Node can suspend one module's Evaluation on an `await` and keep going with Instantiation and Evaluation of other independent modules in the graph. It also knows the full dependency graph **before** evaluation begins, because Construction completes for all modules ahead of time.

CommonJS has nothing like this. `require()` must return a finished result immediately, synchronously.

## Live bindings vs value copy — the classic circular-dependency "gotcha"

### CommonJS: an export is a copy of the value at the time of `require()`

```ts
// counter.js (CommonJS)
let count = 0;
function increment() { count++; }
module.exports = { count, increment }; // count = 0 — a snapshot at export time
```

```ts
// main.js
const { count, increment } = require('./counter');
increment();
console.log(count); // 0 — unchanged! count was copied as a primitive
```

### ESM: an import is a live binding (a reference to the module's "cell," not its value)

```ts
// counter.mjs
export let count = 0;
export function increment() { count++; }
```

```ts
// main.mjs
import { count, increment } from './counter.mjs';
increment();
console.log(count); // 1 — ESM imports always read the current value
```

```txt
This isn't "ESM being weird" — it's a direct consequence of
the three-phase loading: during Instantiation, a binding is
created to the variable slot in the source module, not a copy
of its current value. Every reference to an imported name
reads the actual current state of that slot.
```

### Circular dependencies — where the difference shows up most dramatically

```ts
// a.js (CommonJS)
console.log('a starting');
exports.done = false;
const b = require('./b'); // b.js calls require('./a') inside itself —
                            // it gets a partial exports object for a
                            // (only what was exported before the
                            // require('./b') line)
console.log('in a, b.done =', b.done);
exports.done = true;
```

```txt
In CommonJS, a circular dependency yields a "partially filled"
module.exports — the order of declarations before the
require() line is critical. This is the classic cause of
"why is this export undefined during initialization" bugs.

In ESM, circular dependencies work better for functions
(thanks to function declaration hoisting and live bindings).
But variables initialized via let/const with a computed value
(not just = 0) can still be in a "declared but not yet
initialized" state (TDZ — Temporal Dead Zone) if accessed
during the cycle.
```

## Tree Shaking — where Node isn't involved

```txt
Common misconception: "ESM makes my Node server faster
thanks to tree shaking."

Reality: tree shaking is a bundler optimization
(webpack/esbuild/rollup) for client-side code. Node.js itself
does not tree-shake at runtime — it just loads and executes
every module in the dependency graph. ESM's static analysis
only gives a marginal benefit here: Node can know the
dependency graph ahead of time and load files from disk in
parallel.

ESM's static analysis matters for tree shaking when you build
frontend code or serverless functions, where bundle size
affects cold start. It does not matter for a typical Node API
server.
```

## Interop: mixing CommonJS and ESM — where time actually gets lost

### ESM importing CommonJS — `module.exports` becomes `default`

```ts
// legacy-logger.js (CommonJS)
module.exports = { log: (msg) => console.log(msg) };
```

```ts
// app.mjs (ESM)
import logger from './legacy-logger.js'; // the whole module.exports → default
logger.log('hello'); // ✅ works

// ❌ this does not work directly for arbitrary CJS packages:
import { log } from './legacy-logger.js';
// named imports from CJS only work if Node (via
// cjs-module-lexer) can statically analyze
// module.exports = {...} as an object literal. For dynamic
// module.exports (computed at runtime) — named imports are
// often left undefined
```

### CommonJS importing ESM — `require()` cannot load ESM synchronously

```ts
// ❌ impossible — require() is synchronous, an ESM module
// requires asynchronous loading (at minimum, for top-level
// await anywhere in its graph)
const esmModule = require('./esm-only-package');
// Error: require() of ES Module not supported

// ✅ the only way is dynamic import() (asynchronous)
const esmModule = await import('./esm-only-package.mjs');
```

```txt
This is a one-way restriction. ESM can import CJS, with the
caveats above, but CJS cannot synchronously import ESM.

In practice: if your CommonJS project depends on a package
that has moved to "pure ESM" (e.g., recent versions of chalk,
node-fetch, inquirer), you have two options. Either migrate
to ESM entirely, or use dynamic import() — which breaks
synchronous top-level calls.
```

### "Dual package hazard" — two versions of the same module at once

```json
// package.json of a library supporting both formats
{
  "exports": {
    "require": "./dist/index.cjs",
    "import": "./dist/index.mjs"
  }
}
```

```txt
The problem: one part of your app imports the library via
require() and gets the CJS build, another part imports it via
import and gets the ESM build. Node then loads two separate
modules with two separate instances of internal state.

Classic symptom: a library uses a Singleton (e.g., a "global"
config registry). Because of the dual package hazard the app
ends up with two Singletons that don't see each other's
changes. The bug shows up as "settings aren't applied" with no
explicit error.
```

## `__dirname`/`__filename` in ESM and `createRequire`

```ts
// CommonJS — available automatically (wrapper function params)
console.log(__dirname, __filename);

// ESM — there's no wrapper, so no __dirname/__filename.
// Equivalent via import.meta.url:
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
```

```ts
// If you need require() inside an ESM module (e.g., to load
// JSON or a CJS dependency without top-level await):
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const pkg = require('./package.json');
```

## `package.json "type"` and file extensions

```txt
"type": "module"  → .js files are treated as ESM
"type": "commonjs" (or absent) → .js files are CommonJS

Extensions override "type" for a specific file:
  .mjs — always ESM, regardless of "type"
  .cjs — always CommonJS, regardless of "type"

Practical use: a library with "type": "module" in
package.json can ship a separate .cjs file for backward
compatibility without switching the whole package.
```

## Summary comparison table

```txt
                       CommonJS              ESM
─────────────────────────────────────────────────────────────
Loading               synchronous           3 phases (async for
                                             top-level await)
Import                value copy            live binding
Circular deps         partial exports       better for functions,
                                             but TDZ for let/const
__dirname             built in              via import.meta.url
require() of ESM      ❌ doesn't work        —
import of CJS         —                     module.exports → default
Dynamic import        require() (sync)      import() (async,
                                             available everywhere)
Top-level await       ❌                     ✅
```

## Connection to other topics

```txt
[Node.js Fundamentals]  — the broader npm ecosystem context
                           and package.json structure
```

## Common interview mistakes

- **"The main difference is import/export vs require syntax"** — this leaves out live bindings vs value copy. That difference is the source of real bugs in circular dependencies.

- **"ESM makes Node faster thanks to tree shaking"** — confusing a bundler optimization for client-side code with Node.js's runtime behavior, which doesn't tree-shake.

- **Not knowing about the one-way restriction on `require()`-ing ESM** — a legacy CJS project cannot just upgrade to newer "pure ESM" dependency versions. It needs either a full ESM migration or dynamic `import()`.

- **Not knowing about the dual package hazard** — mixing require and import in one app can "break" a library that uses a Singleton pattern. Without the hazard you cannot explain why.

- **Assuming `__dirname` is available in ESM "just like in CJS"** — not knowing about `import.meta.url` + `fileURLToPath` as the standard replacement.
