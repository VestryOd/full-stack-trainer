# Tree Shaking and Optimization

## Tree shaking is a proof, not a cleanup

The name is misleading: it suggests the bundler shakes the graph and everything loose falls out. The work runs the other way round — the bundler must **prove** that code is removable, and at the slightest doubt it keeps it. Hence every practical problem in this area: the question is almost never "why was this removed" but "why was this **not** removed".

The mechanism has two steps:

1. **Marking (`usedExports`).** The bundler walks the graph and, for every module, records which of its exports somebody actually imports. The rest are marked unused.
2. **Removal.** The marked code is dropped by the minifier, which sees that a declaration is never referenced and deletes it.

An important consequence: **tree shaking does not work without minification.** Marking alone removes nothing. That is why Webpack turns `usedExports` on together with `minimize` in `mode: 'production'` (see the defaults table in [The Webpack Core Model](./03-webpack-core-model.md)).

### Why static ESM is the precondition

ESM (ECMAScript modules) is the `import`/`export` syntax. It is parsed before any code runs: the module name is a literal, and the list of imported names is known from the syntax. So the question "does anybody import `formatCurrency`?" has an answer computable without running the program.

```js
// ESM: the bundler knows only format is taken
import { format } from 'date-fns';

// CJS: nothing can be proven
const dateFns = require('date-fns');
const fn = dateFns[userChoice];       // which export is needed is decided at runtime
```

With `require`, proof is unreachable in principle: reading an export is an ordinary property access that may be computed dynamically. So a CJS (CommonJS — the `require`/`module.exports` format) dependency is wrapped whole, and its contents are left untouched.

The module systems themselves are covered in the Node.js topic, in the CommonJS vs ESM chapter. The bundler's view of them is in [The Module Graph and Resolution](./02-module-graph-and-resolution.md).

## Why tree shaking did not work

```txt
     Why tree shaking did not work: causes one by one
┌────────────────────────────────────────────────────────┐
│ a CJS-only dependency                                  │
│   in the bundle: a wrapper around module.exports       │
│   fix: find an ESM build or another package            │
├────────────────────────────────────────────────────────┤
│ TS or Babel rewrote it to CJS                          │
│   in the bundle: module: "commonjs" in tsconfig        │
│   fix: module: "esnext", leave the rest to the bundler │
├────────────────────────────────────────────────────────┤
│ no sideEffects flag                                    │
│   in the bundle: the whole module for one export       │
│   fix: sideEffects: false or a file list               │
├────────────────────────────────────────────────────────┤
│ importing a whole package                              │
│   in the bundle: import _ from 'lodash'                │
│   fix: named imports from the ESM build                │
├────────────────────────────────────────────────────────┤
│ a top-level side effect                                │
│   in the bundle: a window write, a registry call       │
│   fix: remove the effect or mark it PURE               │
├────────────────────────────────────────────────────────┤
│ a barrel file                                          │
│   in the bundle: index.ts dragged in its neighbours    │
│   fix: import the module directly                      │
└────────────────────────────────────────────────────────┘
the first two are about WHAT entered the graph; the rest are
 about the bundler failing to PROVE the code is unneeded
```

The second cause deserves a note of its own, because it is the most frustrating one. **A transpiler can kill tree shaking before the bundler ever sees the code.** If `tsconfig.json` says `"module": "commonjs"`, TypeScript turns every `import` into `require` — and the bundler receives CJS, from which nothing can be proven.

```json
// tsconfig.json — the right setup for a browser build
{
  "compilerOptions": {
    "module": "esnext",           // NOT commonjs: keep import/export intact
    "moduleResolution": "bundler",
    "target": "es2022"
  }
}
```

The same principle applies to Babel: `@babel/preset-env` with `modules: false`, so it does not rewrite module syntax. The general rule — **transpile syntax separately, and leave modules entirely to the bundler.**

### Why an "unused import" still ends up in the bundle

The most common source of confusion. There are three distinct cases, and mixing them up is expensive.

**Case 1: the module has side effects.** If importing a module does something, the module cannot be removed even when none of its exports are used.

```ts
// lib/analytics.ts
export function track(event: string) { /* ... */ }

// top-level side effects: they run simply because the module was imported
window.__analyticsReady = true;
globalRegistry.register('analytics');
```

```ts
// Orders.tsx — importing and using nothing
import { track } from '@/lib/analytics';   // the module lands in the bundle whole
```

The bundler does not know whether `window.__analyticsReady` and `globalRegistry.register` matter to the application. Not knowing, it keeps them.

**Case 2: an import for its effect.** Such imports should not be removed — the effect is the entire point:

```ts
import './styles/global.css';    // the effect is what we want
import 'core-js/stable';         // polyfills register themselves
```

**Case 3: `import type`.** A type-only import disappears during transpilation and never reaches the bundle — but only when written explicitly:

```ts
import type { Order } from '@/types';        // guaranteed to vanish
import { type Order, fetchOrders } from '@/lib/api';  // the type goes, the function stays
```

## The `sideEffects` flag: permission to drop whole modules

`usedExports` works inside a module — it removes individual exports. `sideEffects` works at module level — it allows the module **not to be included at all**. The second is more effective: what disappears is not a function but an entire subtree of the graph.

```json
// a library's package.json: "importing any of my files does nothing"
{
  "name": "ui-kit",
  "sideEffects": false
}
```

```json
// and if there are effects after all — list them
{
  "name": "ui-kit",
  "sideEffects": ["./src/polyfills.ts", "*.css"]
}
```

That `"*.css"` entry is critical, and people miss it regularly. An imported CSS file is a module subject to tree shaking too. With `sideEffects: false` and aggressive optimization, styles can vanish from the production build while dev worked fine. The classic "styles in dev, no styles in prod" bug. The patterns in the array are simple globs, and a pattern without a `/` is treated as `**/*.css`.

The flip side: `sideEffects: false` is a **promise** verified by reality, not by the bundler. Put the flag on a package that does have effects and the build gets smaller and breaks.

### The `/*#__PURE__*/` annotation

Sometimes there are no effects but the bundler cannot prove it — for instance with a function call at module top level:

```ts
// the bundler does not know createIcon has no outside effects
export const CloseIcon = /*#__PURE__*/ createIcon('close');
```

The annotation is a direct assertion: "this call is side-effect-free, its result can be dropped if unused". In Webpack it is honoured with `optimization.innerGraph: true` (on in production). Such annotations are usually placed by library authors rather than application authors.

### Barrel files: convenience versus size

```ts
// ui/index.ts — a barrel
export * from './Button';
export * from './DataTable';   // pulls in virtualized-list
export * from './Chart';       // pulls in chart-lib
```

```ts
// Orders.tsx
import { Button } from '@/ui';   // we asked for one button
```

In theory tree shaking should remove the rest. In practice that works only if **every** module in the chain is effect-free and flagged as such. A single `import './Chart.css'` inside `Chart.tsx` is enough to keep all of `chart-lib` in the bundle. So large projects import directly (`@/ui/Button`) and keep barrels for a library's public API, where they belong.

## Minification: what actually reduces size

```txt
         What a minifier does beyond stripping whitespace
┌───────────────────────────┬───────────────────────────┬────────┐
│ operation                 │ what happens              │ impact │
├───────────────────────────┼───────────────────────────┼────────┤
│ whitespace and comments   │ formatting is removed     │ small  │
├───────────────────────────┼───────────────────────────┼────────┤
│ shortening local names    │ const userName → const a  │ medium │
├───────────────────────────┼───────────────────────────┼────────┤
│ constant folding          │ 'a'+'b' → 'ab', 2*3 → 6   │ small  │
├───────────────────────────┼───────────────────────────┼────────┤
│ dead code removal         │ if (false) { … } vanishes │ LARGE  │
├───────────────────────────┼───────────────────────────┼────────┤
│ inlining single-use calls │ the body goes inline      │ medium │
├───────────────────────────┼───────────────────────────┼────────┤
│ mangling export names     │ formatCurrency → f        │ medium │
└───────────────────────────┴───────────────────────────┴────────┘
   the real win is not "compressing text" but removing branches
      that became unreachable once NODE_ENV was substituted
```

The mechanism producing most of the effect is worth tracing end to end:

```ts
// in the library's source
if (process.env.NODE_ENV !== 'production') {
  validatePropTypes(props);
  console.warn('Component X is deprecated');
}
```

```ts
// after the bundler substitutes NODE_ENV
if ('production' !== 'production') { /* ... */ }

// after the minifier folds constants
if (false) { /* ... */ }

// after dead code removal
// nothing
```

That is how React ends up noticeably smaller in production than in dev: what disappears is not whitespace but entire warning and validation subsystems. The `NODE_ENV` substitution is part of the `mode` defaults covered in [The Webpack Core Model](./03-webpack-core-model.md).

### Modern minifiers

Terser was the standard for a long time. It is written in JavaScript, and on large projects it accounts for most of the production build time. Today there are more options, and the landscape shifted within the tools' most recent versions:

- **Vite** at the time of writing uses a minifier from the Oxc family — that is the default value of `build.minify`. The docs state the trade-off plainly: it is tens of times faster than Terser while losing on the order of a percent in compression. The `'esbuild'` value is marked deprecated, and `'terser'` remains available for those who need that last percent of size.
- **Webpack** minifies with Terser by default; it is replaceable through `optimization.minimizer`. The project roadmap meanwhile proposes consolidating the separate minimizers (JS, CSS, HTML, JSON) into a single plugin.

```js
// webpack.config.js — the minifier declared explicitly
const TerserPlugin = require('terser-webpack-plugin');

module.exports = {
  optimization: {
    minimizer: [new TerserPlugin({ terserOptions: { format: { comments: false } } })],
  },
};
```

```ts
// vite.config.ts — the default can be overridden
export default defineConfig({
  build: {
    minify: 'terser',   // instead of the fast default — when maximum compression matters
  },
});
```

The practical conclusion: choosing a minifier is a trade-off between build time and a few percent of size. The fast option is almost always the right one. Measure the compressed size while doing so, because gzip and brotli partly absorb the difference.

### Scope hoisting: merging modules

By default every module in a bundle is a separate wrapper function with its own scope. Scope hoisting (in Webpack, `optimization.concatenateModules`, also known as `ModuleConcatenationPlugin`) merges modules imported in a single place into one scope.

```js
// without merging: every module keeps its own wrapper, and the export
// is reached through an intermediate object
var chartModule = { render: function () { /* ... */ } };
chartModule.render();       // a property lookup on every call

// with merging: one scope, and the call is a direct reference
function render() { /* ... */ }
render();                   // no lookup, and the minifier can rename it
```

The win is twofold: less housekeeping code and — more importantly — more surface for the minifier. Names that used to be "a module's public exports" become ordinary local variables, and can therefore be shortened to a single letter.

The precondition is the same: **ESM only**. A CJS module cannot be merged because its exports are assembled at runtime. One more reason a single CJS dependency in the graph costs more than it looks.

## Source maps: three trade-offs in one option

```txt
           Source maps: three trade-offs in one option
Dev values — the .map never reaches production
┌──────────────────────────────┬────────┬───────────────────────┐
│ value                        │ build  │ stack trace shows     │
├──────────────────────────────┼────────┼───────────────────────┤
│ eval                         │ fast   │ generated code        │
├──────────────────────────────┼────────┼───────────────────────┤
│ eval-cheap-module-source-map │ medium │ original line numbers │
├──────────────────────────────┼────────┼───────────────────────┤
│ eval-source-map              │ slow   │ the original in full  │
└──────────────────────────────┴────────┴───────────────────────┘

Production values — who may read your source
┌──────────────────────────────────────────────────────┐
│ source-map                                           │
│   stack trace: the original in full                  │
│   in production: the .map file is public             │
├──────────────────────────────────────────────────────┤
│ hidden-source-map                                    │
│   stack trace: the original, in the error tracker    │
│   in production: the map is uploaded, not referenced │
├──────────────────────────────────────────────────────┤
│ nosources-source-map                                 │
│   stack trace: names and lines, no code              │
│   in production: the map is public, the code is not  │
├──────────────────────────────────────────────────────┤
│ false                                                │
│   stack trace: minified code                         │
│   in production: no map is emitted at all            │
└──────────────────────────────────────────────────────┘
   every production value except false makes the build slower;
        the choice is "error reports are readable" against
                   "do not hand out our source"
```

The three axes are worth keeping apart:

- **Accuracy.** "Cheap" means no column mappings — line numbers only. That is often enough for debugging JS, but not for minified code squeezed onto one line. The word `module` in a value's name means loader-produced maps are honoured too. You then see your original TypeScript rather than the result of transpiling it.
- **Speed.** In dev what matters is not the first build but the rebuild after a save. The `eval` variants win exactly there.
- **Source leakage.** Not paranoia but a frequent real mistake. The value `devtool: 'source-map'` appends a comment pointing at the `.map` file. If that file sits next to the bundle on a CDN (content delivery network), the whole application source is available to anyone. There are two right production choices. The option `hidden-source-map` produces the map and uploads it to an error tracker such as Sentry, leaving no reference in the bundle. The option `nosources-source-map` makes the map public but strips the source text: stack traces read fine, the code stays hidden.

```ts
// vite.config.ts — the same choice, a shorter vocabulary
export default defineConfig({
  build: {
    sourcemap: 'hidden',   // false | true | 'inline' | 'hidden'
  },
});
```

Source maps as a format are covered in the Web Performance topic. Their role in browser debugging is covered in the dev-mode chapter [Dev Server and HMR](./07-dev-server-and-hmr.md), where HMR stands for hot module replacement.

## A method for analysing a bundle

```txt
         Bundle analysis order: from a number to a cause
┌────────────────────────────────────────────────────────────────┐
│ measure: build for production and look at chunk sizes          │
│                               ↓                                │
│ open the bundle map: what takes space in EVERY chunk           │
│                               ↓                                │
│ for a suspicious module ask: WHO imports it                    │
│                               ↓                                │
│ check: ESM or CJS, is there a sideEffects flag, is it a barrel │
│                               ↓                                │
│ fix the import, add the flag, or replace the dependency        │
│                               ↓                                │
│ rebuild and compare numbers — otherwise it is faith,           │
│ not optimization                                               │
└────────────────────────────────────────────────────────────────┘
       look at compressed size: 200 KB in the report may be
      55 KB after brotli — and sometimes the other way round
```

Tools for the "open the map" step:

```bash
# Webpack: a stats report plus an interactive map
npx webpack --profile --json=stats.json
npx webpack-bundle-analyzer stats.json

# Vite: a visualizer over the build statistics
npx vite-bundle-visualizer

# any bundler: a map derived from the emitted source maps
npx source-map-explorer dist/assets/*.js
```

The key step is the third one, and it is the one most often skipped. Seeing that `date-fns` occupies 90 kilobytes is not enough: you need to know **who brought it there**.

Webpack answers that in its statistics: `stats.json` contains `reasons`, the list of modules importing a given one. Vite and Rollup answer it in the visualizer report, and in warnings about a module landing in an unexpected chunk. Without an answer to the question "who imports it", optimization degenerates into guesswork.

The second easily forgotten thing: **compare compressed sizes**. Reports usually show three numbers — raw, gzip, brotli. Decisions come from the last two, because that is what users download. A library full of repetitive code compresses several times over; already-minified, dense code barely compresses at all.

### Typical findings

```txt
           Typical findings when analysing a bundle
┌───────────────────────────────────────────────────────────┐
│ a whole date library                                      │
│   in the report: moment plus dozens of locales            │
│   fix: move to date-fns/dayjs, cut the locales            │
├───────────────────────────────────────────────────────────┤
│ two versions of one package                               │
│   in the report: react under two different paths          │
│   fix: align the versions, dedupe                         │
├───────────────────────────────────────────────────────────┤
│ polyfills just in case                                    │
│   in the report: core-js taking a quarter of a chunk      │
│   fix: narrow browserslist to real browsers               │
├───────────────────────────────────────────────────────────┤
│ a barrel import                                           │
│   in the report: the entire ui-kit in a route chunk       │
│   fix: import the component directly                      │
├───────────────────────────────────────────────────────────┤
│ an icon set                                               │
│   in the report: the whole library instead of three icons │
│   fix: direct imports or an SVG sprite                    │
├───────────────────────────────────────────────────────────┤
│ translation catalogues                                    │
│   in the report: every language in the entry chunk        │
│   fix: load the catalogue on demand                       │
└───────────────────────────────────────────────────────────┘
   the pattern: almost nothing here is a "heavy library" —
            it is the way the library was imported
```

Two of the most instructive findings, on the `shop-admin` example.

**A whole date library.** The classic case is `moment`. It is written in CJS and pulls in every locale at once, so roughly 300 kilobytes arrive where formatting one date was needed. Tree shaking cannot help for two reasons at once: CJS is not analysable, and the locales are loaded dynamically. The fix is not "configure the bundler" but swap the dependency for a modular one:

```ts
// before: all of moment with all its locales
import moment from 'moment';
const label = moment(order.createdAt).format('DD.MM');

// after: one function reaches the bundle
import { format } from 'date-fns';
const label = format(order.createdAt, 'dd.MM');
```

**Polyfills just in case.** `@babel/preset-env` with a broad `browserslist` pulls in all of `core-js` — so modern browsers download emulations of features they support natively. The cure is an honest list of supported browsers:

```json
// package.json
{
  "browserslist": ["defaults and fully supports es6-module", "not dead"]
}
```

Vite handles this differently. By default it builds for modern browsers: `build.target` is tied to the Baseline Widely Available set. Support for old browsers comes from a separate plugin. So by default you pay nothing for polyfills at all.

## Relation to other topics

- [The Module Graph and Resolution](./02-module-graph-and-resolution.md) — why
  static ESM makes the proof possible and CJS does not.
- [The Webpack Core Model](./03-webpack-core-model.md) — `usedExports`,
  `sideEffects` and `concatenateModules` among the `mode` defaults.
- [Code Splitting and Long-Term Caching](./04-code-splitting-and-caching.md) —
  what to do with a finding: move it into a lazy chunk, or regroup it.
- [The Vite Model](./06-vite-model.md) — why there is no tree shaking in dev
  mode, and why that is correct.
- [Dev Server and HMR](./07-dev-server-and-hmr.md) — source maps in dev mode.
- [Ecosystem and Choosing a Tool](./08-ecosystem-and-choosing.md) — fast
  minifiers and transformers: where the speed advantage actually comes from.
- The Node.js topic, the CommonJS vs ESM chapter — the module systems themselves.
- The Web Performance topic — what to do with size next: metrics, the critical
  path, budgets.

## Common interview traps

- **"Tree shaking removes unused code"** — too broad a statement, and usually there is no mechanism behind it. A strong answer: the bundler marks unused exports and the minifier removes them; without minification there is no tree shaking.

- **Not knowing why CJS blocks tree shaking.** The expected answer is about static analysis. A static `import` is parsed before execution, while `require(x)[y]` is computed at runtime. An export's uselessness therefore cannot be proven. "CJS is an old format" explains nothing.

- **Not suspecting that `tsconfig.json` can kill tree shaking.** A very practical question: `"module": "commonjs"` turns every import into `require` before the code reaches the bundler. A candidate who knows this has usually debugged a real bundle-size problem.

- **"`sideEffects: false` is just an optimization, always safe to set"** — it is a promise. Breaking it makes the application fail in production while it still works in dev. Extra credit for mentioning that CSS imports must be listed in the array, or styles may disappear.

- **Confusing `usedExports` and `sideEffects`.** The first works inside a module (dropping exports), the second at module level (allowing a file and its whole subtree to be skipped). The second is more effective, and the Webpack docs say so explicitly.

- **"A minifier strips whitespace and renames variables"** — true, but a small share of the win. The main part is removing unreachable branches after the `NODE_ENV` substitution. Being able to trace `process.env.NODE_ENV !== 'production'` → `'production' !== 'production'` → `if (false)` → nothing is what separates understanding from recitation.

- **`devtool: 'source-map'` in production with no caveats** — that publishes your application's source code. The expected answer distinguishes `hidden-source-map` (the map goes to the error tracker only) from `nosources-source-map` (stack traces read fine, the code stays hidden).

- **Optimizing without measuring.** "I would look at what is actually in there and find out who imports it" sounds far stronger than a list of recipes. And it almost always turns out the problem is not a "heavy library" but the way it was imported.
