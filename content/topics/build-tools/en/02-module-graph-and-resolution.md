# The Module Graph and Resolution

## A module is a node in a graph, not a file in a folder

A build starts at an entry point and unfolds from there: the bundler reads a file, finds its imports, works out a concrete disk path for each one, reads what it found — and repeats until the queue is empty. The result is a directed graph: modules are nodes, imports are edges.

```txt
    The shop-admin module graph: the walk starts at the entry point
┌─────────────────────────────────────────────────────────────────────┐
│ a depth-first walk from main.tsx                                    │
│                                                                     │
│ main.tsx                     ← entry point: the only root           │
│ ├─ react-dom/client          bare specifier → node_modules          │
│ ├─ styles/global.css         a non-JS asset is a graph node too     │
│ ╰─ App.tsx                                                          │
│    ├─ routes/Orders.tsx                                             │
│    │  ├─ lib/api.ts                                                 │
│    │  ╰─ ui/Button.tsx       → ui/Button.css                        │
│    ├─ routes/Analytics.tsx                                          │
│    │  ├─ chart-lib           ≈600 modules from node_modules         │
│    │  ├─ date-fns            bare specifier                         │
│    │  ╰─ lib/api.ts          ← already visited: one node, two edges │
│    ╰─ routes/Settings.tsx                                           │
│       ╰─ ui/Button.tsx       ← the same node, a second edge         │
└─────────────────────────────────────────────────────────────────────┘
        this is a graph, not a tree: a module is processed once,
                   no matter how many files import it
```

Three consequences follow from that picture, and they matter daily:

- **A file nobody imports never enters the build at all.** Not because optimization dropped it, but because the walk never reached it. That is a fundamentally different story from tree shaking, where the module *is* in the graph and its exports get removed — the difference is covered in [Tree Shaking and Optimization].
- **One added import can drag hundreds of modules into the bundle.** The line `import { LineChart } from 'chart-lib'` in `Analytics.tsx` is not one node, it is an entire subtree.
- **A module is processed exactly once.** `lib/api.ts` is imported from two routes, but it is transformed and included once — and at runtime its body also executes once, with the result cached. This, incidentally, is where the whole family of "module singletons" comes from: a store or API client created at module top level exists in a single instance — right up until that module ends up in the bundle twice (see duplicates below).

The bundler does the same thing with every node: read → transform → parse imports → push what it found onto the queue. What the "transform" step consists of is covered in [The Webpack Core Model].

### There can be more than one entry point

```js
// webpack.config.js — entry points are declared explicitly
module.exports = {
  entry: {
    main:  './src/main.tsx',
    admin: './src/admin.tsx',
  },
};
```

```ts
// vite.config.ts — by default the entry point comes from index.html
import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    rolldownOptions: {              // the older name rollupOptions works as an alias
      input: {
        main:  'index.html',
        admin: 'admin.html',
      },
    },
  },
});
```

The difference is not cosmetic. In Webpack the root of the graph is a JS file, and the HTML is produced on the side by a plugin. In Vite the root of the graph is **`index.html` itself**: the bundler reads it, finds `<script type="module" src="/src/main.tsx">` and continues into JS from there. That is why Vite processes and rewrites asset references written directly in HTML, while Webpack needs a separate plugin for it. More in [The Vite Model].

## The resolution algorithm: from a string to a file on disk

Resolution is a function of "specifier string plus the file doing the importing" to "a concrete path on disk". Everything else in the build depends on what it returns.

```txt
                 Kinds of specifiers and what the bundler does with them
┌───────────────────┬────────────────┬───────────────────────────────────────────────────┐
│ kind of specifier │ example        │ what the bundler does                             │
├───────────────────┼────────────────┼───────────────────────────────────────────────────┤
│ relative          │ './lib/api'    │ path from the current file + extension probing    │
├───────────────────┼────────────────┼───────────────────────────────────────────────────┤
│ absolute          │ '/src/lib/api' │ path from the project root                        │
├───────────────────┼────────────────┼───────────────────────────────────────────────────┤
│ alias             │ '@/lib/api'    │ substituted from config, then treated as relative │
├───────────────────┼────────────────┼───────────────────────────────────────────────────┤
│ bare specifier    │ 'date-fns'     │ package lookup in node_modules, walking upwards   │
├───────────────────┼────────────────┼───────────────────────────────────────────────────┤
│ external URL      │ 'https://…'    │ not resolved, kept as an external reference       │
└───────────────────┴────────────────┴───────────────────────────────────────────────────┘
              the browser only understands relative, absolute and URL forms;
              alias and bare specifiers work only because a bundler is there
```

### Relative paths and extension probing

The string `'./lib/api'` does not point at an existing file: what is on disk is `api.ts`. The bundler probes the extensions from a list and takes the first hit; if the path is a directory, it looks for `index.*` inside.

The defaults differ between tools, and that is a recurring source of confusion:

- **Webpack:** `resolve.extensions` defaults to `['.js', '.json', '.wasm']`. TypeScript and JSX have to be added by hand — without that the build dies on the first `.tsx`.
- **Vite:** `['.mjs', '.js', '.mts', '.ts', '.jsx', '.tsx', '.json']` out of the box.

Probing costs file system calls: every extension in the list is a separate "does this file exist" check. On a project with thousands of modules and a long extension list, that becomes a measurable share of build time. Hence the practical advice: keep the list short and put the most common extensions first. How to measure where build time actually goes is covered in [Ecosystem and Choosing a Tool].

### Alias

The same task — "write `@/lib/api` instead of `../../../lib/api`" — in two configs:

```js
// webpack.config.js
const path = require('path');

module.exports = {
  resolve: {
    extensions: ['.tsx', '.ts', '.js', '.json'],
    alias: {
      '@': path.resolve(__dirname, 'src'),
      // a trailing $ means exact match only:
      // 'lodash' is swapped, 'lodash/pick' is not
      lodash$: path.resolve(__dirname, 'src/shims/lodash.ts'),
    },
  },
};
```

```ts
// vite.config.ts
import path from 'node:path';
import { defineConfig } from 'vite';

export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
});
```

A trap that costs people hours: **a bundler alias and `paths` in `tsconfig.json` are different mechanisms.** TypeScript uses `paths` for type checking only and never rewrites imports in emitted code; the bundler, by default, knows nothing about `tsconfig.json`. Configure only `paths` and your editor will be happy while the build fails with `Module not found`. Keeping the two in sync by hand invites drift, so the usual answer is a plugin that reads `paths` and feeds them to the bundler (`vite-tsconfig-paths` and friends). Webpack has been able to read paths from `tsconfig.json` on its own since 5.105 — part of the wider move toward built-in TypeScript support announced in the project roadmap.

### Bare specifiers: the node_modules lookup

```txt
             How a bare specifier is resolved
┌────────────────────────────────────────────────────────┐
│ import { format } from 'date-fns'                      │
│                           ↓                            │
│ does ./node_modules/date-fns/ exist?                   │
│ no → ../node_modules/, and so on up to the FS root     │
│                           ↓                            │
│ read the package.json of the package found             │
│                           ↓                            │
│ is there an exports field?                             │
│ yes → pick a branch by condition: import / require /   │
│       browser / node / development / production        │
│ no  → fall back to mainFields: browser → module → main │
│                           ↓                            │
│ a concrete file: date-fns/format.mjs                   │
└────────────────────────────────────────────────────────┘
   failing at step two is what Module not found means;
"resolves, but to the wrong file" means bundler and Node conditions differ
```

Walking upward matters: a package may live not next to the importing file but at the root of a monorepo. A related subtlety is symlinks — `pnpm` and workspace links create exactly those, and whether the bundler expands a symlink into its real path decides whether a package counts as "the same module". That is controlled by `resolve.symlinks` in Webpack (default `true` — expand) and `resolve.preserveSymlinks` in Vite (default `false` — also expand). In a monorepo this is where duplicates are usually born; dependency organization in a monorepo is covered in the NX course.

### package.json fields and conditional exports

```txt
                     package.json fields: why one package serves different files
┌─────────────────┬──────────────────────────────┬───────────────────────────────────────────────────┐
│ field           │ who reads it                 │ what it means                                     │
├─────────────────┼──────────────────────────────┼───────────────────────────────────────────────────┤
│ main            │ everyone, as the last resort │ the historical CJS entry                          │
├─────────────────┼──────────────────────────────┼───────────────────────────────────────────────────┤
│ module          │ bundlers, but not Node       │ the ESM entry — the precondition for tree shaking │
├─────────────────┼──────────────────────────────┼───────────────────────────────────────────────────┤
│ browser         │ bundlers targeting web       │ a file swap or a stub instead of a node API       │
├─────────────────┼──────────────────────────────┼───────────────────────────────────────────────────┤
│ exports         │ Node and modern bundlers     │ the source of truth; also seals off deep paths    │
├─────────────────┼──────────────────────────────┼───────────────────────────────────────────────────┤
│   "import"      │ when imported from ESM       │ the ESM build of the package                      │
├─────────────────┼──────────────────────────────┼───────────────────────────────────────────────────┤
│   "require"     │ when required from CJS       │ the CJS build of the package                      │
├─────────────────┼──────────────────────────────┼───────────────────────────────────────────────────┤
│   "browser"     │ a bundler targeting web      │ the browser build                                 │
├─────────────────┼──────────────────────────────┼───────────────────────────────────────────────────┤
│   "development" │ the bundler in dev mode      │ the variant with checks and warnings              │
└─────────────────┴──────────────────────────────┴───────────────────────────────────────────────────┘
           the same import yields DIFFERENT files in Node, in a bundler and in a browser —
                  that is not a bug, it is exactly what conditional exports are for
```

What this looks like in a real package:

```json
{
  "name": "chart-lib",
  "main": "./dist/index.cjs",
  "module": "./dist/index.mjs",
  "exports": {
    ".": {
      "types":   "./dist/index.d.ts",
      "browser": "./dist/index.browser.mjs",
      "import":  "./dist/index.mjs",
      "require": "./dist/index.cjs",
      "default": "./dist/index.mjs"
    },
    "./styles.css": "./dist/styles.css",
    "./package.json": "./package.json"
  }
}
```

Three rules worth knowing about `exports`:

1. **Key order is significant.** The resolver goes top to bottom and takes the first matching condition, which is why `"types"` goes first and `"default"` last. A scrambled order is a classic bug in published libraries.
2. **`exports` seals off everything it does not list.** Before this field existed you could import any file inside a package: `import util from 'chart-lib/dist/internal/util.js'`. Afterwards, only declared paths work and the rest fails with `Package subpath './dist/internal/util.js' is not defined by "exports"`. This is a frequent reason a minor dependency bump suddenly breaks a build.
3. **Different consumers apply different conditions.** Webpack with `target: 'web'` and `mode: 'production'` uses a set along the lines of `['webpack', 'production', 'browser']`, plus `import` or `require` depending on which kind of code the import came from. Vite defaults to `['module', 'browser', 'development|production']`, where the last one is substituted by mode. Node knows nothing about `webpack` or `module`, but it does know `node`.

This is exactly where the "works in Node tests, breaks in the browser" family of bugs comes from: Jest resolves the `"require"` branch with the CJS build while the bundler resolves the `"browser"` branch with different code. That is not an implementation mismatch — it is the entire point of conditional exports.

## CJS and ESM from the bundler's point of view

The module systems themselves — `require` versus `import`, live bindings, execution order — are covered in the Node.js topic, in the CommonJS vs ESM chapter. What matters here is one property and its consequences for building.

**ESM is static.** `import` is a declaration parsed before any code runs: the module name must be a literal, and imports cannot be declared inside an `if`. `require` is an ordinary function call whose argument is known only at runtime.

```js
// ESM: the bundler knows the graph without executing a line
import { format } from 'date-fns';

// CJS: the only way to know what is imported here is to run the code
const name = isLegacy ? 'date-fns' : 'dayjs';
const lib = require(name);
```

Three things follow, and half of this topic rests on them:

- **The graph is built without executing code.** The bundler reads and parses; it does not run. That is what makes building possible as static analysis at all.
- **Tree shaking only works on ESM.** Proving that an export is unused requires knowing every import up front, which is undecidable with `require`. Covered in [Tree Shaking and Optimization].
- **Code splitting rests on `import()`.** Dynamic import is the one ESM construct a bundler treats as a break in the graph. See [Code Splitting and Long-Term Caching].

### What happens when a CJS package enters the graph

The bundler cannot hand such a module to the browser as-is — `module` and `exports` do not exist there. So the module gets wrapped: its body becomes a function with local `module`/`exports`, the function is called on first access, and the result is cached and served as the module's contents. The practical consequences:

- **Named imports from CJS are a heuristic, not a guarantee.** `import { pick } from 'lodash'` works as long as the bundler can statically recognize simple forms such as `exports.pick = ...` in the package's code. If exports are assembled dynamically (in a loop, via `Object.assign`), the analysis fails and the browser reports `does not provide an export named 'pick'`. Vite's answer to this problem is dependency pre-bundling, see [The Vite Model].
- **A default import needs an interop wrapper.** `import express from 'express'` gives you the package's whole `module.exports`, because the bundler adds the same shim that TypeScript's `esModuleInterop` does. Meanwhile `import * as express from 'express'` gives a namespace object that cannot be called — the classic `express is not a function`.
- **The dual package hazard.** If a package is published as both CJS and ESM and different parts of the graph resolve different branches, **two copies** with independent state land in the bundle. The symptom: "my singleton is somehow not a singleton".

The general conclusion: a CJS dependency is a node the bundler must wrap and cannot optimize. Those are exactly the nodes that break most often when moving from Webpack to Vite ([Ecosystem and Choosing a Tool]).

## Common resolution errors and how to read them

### `Module not found`

The message always carries two parts — **what** was looked for and **from where**. Read both:

```txt
Module not found: Error: Can't resolve 'crypto' in '/app/src/lib'
BREAKING CHANGE: webpack < 5 used to include polyfills for node.js core
modules by default. This is no longer the case.
```

Three causes, by frequency:

1. **A typo or a missing extension** — the most common and the most harmless. Check it against `resolve.extensions`.
2. **The package is not in `node_modules`** — not installed, or declared only in `peerDependencies`.
3. **A node module inside browser code.** Webpack 4 silently substituted browser polyfills for `crypto`, `path`, `buffer`; Webpack 5 removed that — rightly, because quietly shipping an emulation of `Buffer` is expensive. The fix is either `resolve.fallback` with an explicit polyfill or, better, getting rid of a dependency that has no business running in a browser. In Vite the same situation looks different: the build passes and then `process is not defined` appears at runtime — migration traps are covered in [Ecosystem and Choosing a Tool].

A separate member of the same family is `Failed to resolve entry for package "chart-lib". The package may have incorrect main/module/exports specified`. Here the package was found, but no condition led to an existing file — usually a broken `exports` block in the library itself.

### Duplicate copies of one library in the bundle

```txt
          ONE COPY of react                          TWO COPIES of react
┌───────────────────────────────────┐    ┌─────────────────────────────────────────┐
│ node_modules/                     │    │ node_modules/                           │
│                                   │    │                                         │
│ ├─ react@18.3.1                   │    │ ├─ react@18.3.1                         │
│ ├─ chart-lib/     peer: react ^18 │    │ ├─ chart-lib/           peer: react ^18 │
│ ╰─ ui-kit/        peer: react ^18 │    │ ╰─ ui-kit/              needs react ^17 │
│                                   │    │    ╰─ node_modules/                     │
│ in the bundle     react once      │    │       ╰─ react@17.0.2                   │
└───────────────────────────────────┘    │                                         │
     the package manager hoisted         │ in the bundle           react twice     │
    the shared version to the top        └─────────────────────────────────────────┘
                                                 plus Invalid hook call: two
                                                 modules, two separate states
```

Duplicates are the nastiest resolution error, because the build succeeds. The symptoms arrive from a different direction: the bundle suddenly grew, `Invalid hook call` appeared, a React context came out empty in a child component, a store behaves like two separate stores. The cause is always the same: two modules with the same name but different paths — to the bundler, two distinct graph nodes.

How they arise:

- a nested install caused by incompatible version ranges (the right-hand picture);
- symlinks in a monorepo, when a package resolves both through its real path and through the link;
- one library entering the graph twice in different formats — the dual package hazard again.

Diagnosis order: first `npm ls react` (or `pnpm why react`), which lists every installed copy; then bundle analysis, to see whether both copies actually reached the output ([Tree Shaking and Optimization]).

Fixes, in increasing order of bluntness:

```ts
// vite.config.ts — "always resolve these packages to a single copy"
export default defineConfig({
  resolve: {
    dedupe: ['react', 'react-dom'],
  },
});
```

```js
// webpack.config.js — the same effect through a forced alias
module.exports = {
  resolve: {
    alias: {
      react:       path.resolve(__dirname, 'node_modules/react'),
      'react-dom': path.resolve(__dirname, 'node_modules/react-dom'),
    },
  },
};
```

Both, though, treat the symptom. The right order of action is to align versions first and move the shared package into the library's `peerDependencies`, and only then, if that is impossible, force resolution to collapse.

### Circular dependencies

The graph permits them and the bundler will not fail. The runtime will: in a cycle `A → B → A` one module starts executing before the other has assigned its exports, and `undefined` shows up in their place. The characteristic symptom is "everything broke after we reordered the imports" or "it only fails in the production build", because module concatenation changes initialization order ([Tree Shaking and Optimization]). Cycles are worth catching with a linter early rather than debugging by symptom.

## Relation to other topics

```txt
[Why Bundlers Exist]                — why resolution is needed at all and why
                                       the browser cannot search node_modules
[The Webpack Core Model]            — what happens to a graph node: loaders,
                                       plugins, the module → chunk transition
[Code Splitting and Long-Term
 Caching]                            — import() as a break in the graph
[Tree Shaking and Optimization]     — why static ESM enables optimizations,
                                       and how to find duplicates in a bundle
[The Vite Model]                    — dependency pre-bundling as the answer
                                       to CJS living in node_modules
[Ecosystem and Choosing a Tool]     — what breaks in a migration: polyfills,
                                       process.env, CJS dependencies
Node.js topic, the CommonJS vs ESM chapter
                                     — the module systems themselves: require vs
                                       import, live bindings, execution order
NX course                            — dependencies and symlinks in a monorepo
```

## Common interview traps

- **"A bundler just glues files together by their imports"** — the whole of resolution is missing, and that is precisely where real problems live. A good answer separates two steps: turning a string into a disk path (resolution) and processing the file that was found (transformation).

- **Not knowing what a bare specifier is** — the key concept of this article. The question "why does `import 'date-fns'` fail in a browser without a bundler while `import './api.js'` works?" separates people who understand the mechanics from people who remember recipes.

- **Confusing bundler aliases with `paths` in `tsconfig.json`** — a very common practical mistake and a good diagnostic question. The correct answer: TypeScript knows nothing about the build, and the bundler knows nothing about `tsconfig.json` by default; keeping them in sync is a separate job.

- **"`exports` is just a new name for `main`"** — no. `exports` not only picks an entry, it also **seals off** every path it does not list and serves different files per condition. A candidate who can explain why an upgrade broke an import from a package's internal folder has clearly worked with it first-hand.

- **"Duplicate libraries are an npm problem"** — only partly. To a bundler, two paths to `react` are two distinct modules, and it will honestly include both. The expected answer covers symptoms (`Invalid hook call`, an empty context, a bloated bundle), diagnosis (`npm ls`, bundle analysis) and fixes in the right priority: versions and `peerDependencies` first, `dedupe`/`alias` second.

- **"CJS and ESM are the same to a bundler, it rewrites everything anyway"** — it can rewrite, but it cannot statically analyze `require(someVariable)`. That single fact produces the impossibility of tree-shaking a CJS dependency, the `does not provide an export named` error, and the dual package hazard. An answer that connects ESM's static nature to specific optimizations lands far better than a recap of syntax differences.
