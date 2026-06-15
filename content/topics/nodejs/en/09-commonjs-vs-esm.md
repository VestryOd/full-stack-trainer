# CommonJS vs ES Modules

## Why this isn't just "a syntax difference"

The shallow level is "CommonJS uses `require`/`module.exports`, ESM uses `import`/`export`, ESM is better for tree shaking." That's true, but at a senior level the question almost always moves to: **what happens to variables in a circular dependency**, **how module resolution actually works**, and **what REALLY happens when CJS and ESM are mixed in one project** — which is where real migrations lose hours in practice.

## CommonJS: `require` isn't "just an import" — it's a synchronous function call

```ts
// What you write:
const { readFile } = require('fs');
module.exports = { processFile };
```

```ts
// What Node WRAPS every file in before executing it:
(function (exports, require, module, __filename, __dirname) {
  const { readFile } = require('fs');
  module.exports = { processFile };
});
```

```txt
This explains:
  - where __dirname/__filename/require/module/exports come
    from "out of thin air" — they're PARAMETERS of the
    wrapper function
  - why a module's top-level code has its own scope (module
    variables don't leak into global)
  - why require() is a SYNCHRONOUS operation: it's a regular
    function call that must return a value before execution
    continues
```

### Module resolution algorithm — where hours get lost debugging

```txt
require('./utils')          → ./utils.js, ./utils.json, ./utils.node,
                               ./utils/index.js (in this order)

require('lodash')            → looks for node_modules/lodash in the
                               CURRENT directory, then the parent,
                               and so on up to the filesystem root
                               (so one version of lodash can end up
                               duplicated across node_modules at
                               different levels on a version conflict)

require('lodash')            → reads lodash's package.json, looks at
                               the "main" field (or "exports" for
                               modern packages) — the entry point is
                               NOT necessarily index.js
```

### Module Cache — keyed by ABSOLUTE path, not the import string

```ts
// a.js and b.js both do:
require('./utils');      // from directory /src
require('../src/utils');  // from directory /src/sub — RESOLVES to the same file

// Node caches by the RESOLVED ABSOLUTE FILE PATH —
// so both calls return the SAME exports object, even
// though the import strings differ
```

## ESM: modules load in THREE phases — why this matters

```txt
CommonJS: loading and execution are ONE operation (require
executes the file synchronously, top to bottom).

ESM (per the ECMAScript spec) has three distinct phases:
  1. Construction (Parsing) — parse ALL modules in the
     dependency graph, build a "module record" for each,
     WITHOUT executing any code
  2. Instantiation — allocate storage for all export/import
     bindings (link modules together), still WITHOUT
     executing code
  3. Evaluation — execute module code, in dependency order
     (from the leaves of the graph toward the root)
```

This three-phase loading is exactly what makes **top-level await** possible — Node can suspend one module's Evaluation on an await while continuing Instantiation/Evaluation of other independent modules in the graph, and it knows the full dependency graph BEFORE evaluation begins (because Construction completes for all modules ahead of time). CommonJS has nothing like this — `require()` must return a finished result immediately, synchronously.

## Live bindings vs value copy — the classic circular-dependency "gotcha"

### CommonJS: an export is a COPY of the value at the time of `require()`

```ts
// counter.js (CommonJS)
let count = 0;
function increment() { count++; }
module.exports = { count, increment }; // count = 0 — a SNAPSHOT at export time
```

```ts
// main.js
const { count, increment } = require('./counter');
increment();
console.log(count); // 0 — unchanged! count was copied as a primitive
```

### ESM: an import is a LIVE BINDING (a reference to the module's "cell," not its value)

```ts
// counter.mjs
export let count = 0;
export function increment() { count++; }
```

```ts
// main.mjs
import { count, increment } from './counter.mjs';
increment();
console.log(count); // 1 — ESM imports ALWAYS read the CURRENT value
```

```txt
This isn't "ESM being weird" — it's a direct consequence of
the three-phase loading: during Instantiation, a binding is
created to the SOURCE module's variable SLOT, not a copy of
its current value. Every reference to an imported name reads
the ACTUAL current state of that slot.
```

### Circular dependencies — where the difference shows up most dramatically

```ts
// a.js (CommonJS)
console.log('a starting');
exports.done = false;
const b = require('./b'); // b.js calls require('./a') INSIDE itself —
                            // it gets a PARTIAL exports object for a
                            // (only what was exported BEFORE the
                            // require('./b') line)
console.log('in a, b.done =', b.done);
exports.done = true;
```

```txt
In CommonJS, a circular dependency yields a "partially filled"
module.exports — the order of declarations BEFORE the
require() line is critical. This is the classic cause of
"why is this export undefined during initialization" bugs.

In ESM, circular dependencies work BETTER for functions
(thanks to function declaration hoisting and live bindings),
but variables initialized via let/const with a computed value
(not just = 0) can still be in a "declared but not yet
initialized" state (TDZ — Temporal Dead Zone) if accessed
during the cycle.
```

## Tree Shaking — where Node ISN'T involved

```txt
Common misconception: "ESM makes my Node server faster
thanks to tree shaking."

Reality: tree shaking is a BUNDLER optimization
(webpack/esbuild/rollup) for CLIENT-side code. Node.js itself
does NOT tree-shake at runtime — it just loads and executes
EVERY module in the dependency graph; ESM's static analysis
only gives a MARGINAL benefit here (Node can know the
dependency graph ahead of time to load files from disk in
parallel).

ESM's static analysis matters for tree shaking in the context
of BUILDING frontend code or serverless functions (where
bundle size affects cold start), not for a typical Node API
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
import logger from './legacy-logger.js'; // the WHOLE module.exports → default
logger.log('hello'); // ✅ works

// ❌ this does NOT work directly for arbitrary CJS packages:
import { log } from './legacy-logger.js';
// named imports from CJS only work if Node (via
// cjs-module-lexer) can STATICALLY analyze
// module.exports = {...} as an object literal. For dynamic
// module.exports (computed at runtime) — named imports are
// often left undefined
```

### CommonJS importing ESM — `require()` CANNOT load ESM synchronously

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
This is a ONE-WAY restriction — ESM can import CJS (with the
caveats above), but CJS CANNOT synchronously import ESM. In
practice this means: if your CommonJS project depends on a
package that's moved to "pure ESM" (e.g., recent versions of
chalk, node-fetch, inquirer) — you either migrate to ESM
entirely, or use dynamic import() (which breaks synchronous
top-level calls).
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
The problem: if ONE PART of your app imports the library via
require() (gets the CJS build), and ANOTHER PART via import
(gets the ESM build) — Node loads TWO SEPARATE modules with
TWO SEPARATE instances of internal state.

Classic symptom: a library uses a Singleton (e.g., a "global"
config registry) — but due to the dual package hazard the app
ends up with TWO Singletons that don't see each other's
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
"type": "module"  → .js files are TREATED AS ESM
"type": "commonjs" (or absent) → .js files are CommonJS

Extensions OVERRIDE "type" for a specific file:
  .mjs — ALWAYS ESM, regardless of "type"
  .cjs — ALWAYS CommonJS, regardless of "type"

Practical use: a library with "type": "module" in
package.json can ship a SEPARATE .cjs file for backward
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
Dynamic import        require() (sync)      import() (async, everywhere)
Top-level await       ❌                     ✅
```

## Connection to other topics

```txt
[Node.js Fundamentals]  — the broader npm ecosystem context
                           and package.json structure
```

## Common interview mistakes

- **"The main difference is import/export vs require syntax"** — without mentioning live bindings vs value copy, which is the SOURCE of real bugs in circular dependencies.

- **"ESM makes Node faster thanks to tree shaking"** — confusing a BUNDLER optimization for client-side code with Node.js's runtime behavior, which doesn't tree-shake.

- **Not knowing about the one-way restriction on `require()`-ing ESM** — not understanding why migrating a legacy CJS project to newer "pure ESM" dependency versions requires either a full ESM migration or dynamic `import()`.

- **Not knowing about the dual package hazard** — not being able to explain why a library using a Singleton pattern can "break" when require/import are mixed in one app.

- **Assuming `__dirname` is available in ESM "just like in CJS"** — not knowing about `import.meta.url` + `fileURLToPath` as the standard replacement.
