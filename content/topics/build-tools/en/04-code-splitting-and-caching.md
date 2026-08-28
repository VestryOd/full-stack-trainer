# Code Splitting and Long-Term Caching

## Two problems always solved together

Code splitting answers "how do I avoid shipping what the user does not need right now". Long-term caching answers "how do I avoid re-shipping what they already have". Treating them separately makes no sense: they are configured through the same options, and sloppy splitting destroys caching more reliably than having none at all.

Both belong exclusively to the production build — in dev mode neither is attempted (see the frame in [Why Bundlers Exist](./01-why-bundlers-exist.md)).

## `import()` is the only break in the graph

A static `import` creates an edge **inside** a chunk: the bundler knows the module is needed immediately and places it alongside. A dynamic `import()` is the one construct the bundler treats as a **boundary**: everything reachable only through it moves into a separate chunk.

```tsx
// src/App.tsx — splitting by route
import { lazy, Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';

const Orders    = lazy(() => import('./routes/Orders'));
const Analytics = lazy(() => import('./routes/Analytics'));   // chart-lib goes here
const Settings  = lazy(() => import('./routes/Settings'));

export function App() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <Routes>
        <Route path="/orders"    element={<Orders />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/settings"  element={<Settings />} />
      </Routes>
    </Suspense>
  );
}
```

```txt
                  ONE BUNDLE
┌───────────────────────────────────────────┐
│ what an /orders user downloads            │
│                                           │
│ main.js   620 KB — the whole application, │
│           chart-lib and date-fns included │
│                                           │
│ total     620 KB before the first render  │
└───────────────────────────────────────────┘
someone who never opens /analytics still pays for it

                  SPLIT BY ROUTE
┌───────────────────────────────────────────────┐
│ what an /orders user downloads                │
│                                               │
│ index.js       18 KB — shell and router       │
│ vendor.js      140 KB — react, react-dom      │
│ orders.js      24 KB — the /orders route      │
│ analytics.js   430 KB — not downloaded        │
│                                               │
│ total          182 KB before the first render │
└───────────────────────────────────────────────┘
analytics.js arrives only on navigation to /analytics
```

Three things worth getting exactly right here:

- **Only `import()` creates a chunk — not a module's "heaviness".** The bundler cannot decide "this library is big, let me pull it out": it cuts the graph precisely where you put a dynamic import. The `chart-lib` package moved into `analytics.js` not because it is large, but because it is reachable only through a lazy route.
- **A conditional static import creates nothing.** Writing `if (isAdmin) { import x from '...' }` is impossible in ESM (ECMAScript modules — the `import`/`export` syntax). A `require()` inside an `if` gives no boundary either: the bundler includes the module anyway. [The Module Graph and Resolution](./02-module-graph-and-resolution.md) covers why ESM is static.
- **A module reachable from two lazy chunks lands in both.** If `lib/api.ts` is needed by `Orders` and by `Analytics`, it is duplicated unless a shared group exists. That is exactly what `splitChunks` fixes.

### Naming a chunk

```tsx
// Webpack: a magic comment — otherwise the chunk is named something like 247.a1b2c3.js
const Analytics = lazy(
  () => import(/* webpackChunkName: "analytics" */ './routes/Analytics'),
);
```

```ts
// Vite: names come from a config template, no magic comments needed
export default defineConfig({
  build: {
    rolldownOptions: {
      output: {
        chunkFileNames: 'assets/[name]-[hash].js',
      },
    },
  },
});
```

### The trap waiting in production: the chunk did not load

`import()` returns a promise, which means it can reject. Here is the most common real-life scenario. A user has a tab open. You ship a release with fresh hashes, and the old files are gone from the CDN (content delivery network). Navigating to a route then fails.

```txt
Webpack:  ChunkLoadError: Loading chunk 5 failed
Vite:     TypeError: Failed to fetch dynamically imported module
```

The fix takes two parts at once:

- **In the application:** catch the error, retry once, and reload the page on a second failure.
- **At deploy time:** do not delete the previous release's assets immediately. Keep several versions around.

A candidate who brings this scenario up unprompted has usually run something in production.

## Splitting by route: where to draw the line

Routes are the most natural boundary. They coincide with the moment a user is **psychologically prepared to wait**: clicking a link already implies a pause. Hence the rule: split where there is a navigation, and do not split where the user is merely scrolling.

What else is worth moving into a lazy chunk besides routes:

- **Modals and editors** that a minority of users ever open.
- **Heavy libraries behind a specific action**: export to PDF (portable document format), a code editor, a map.
- **Admin sections** that a regular user cannot reach.

What is **not** worth splitting: anything visible on the first screen. Lazily loading a header or a page skeleton adds one more request round to the critical path. That is exactly the waterfall discussed in [Why Bundlers Exist](./01-why-bundlers-exist.md).

## splitChunks: vendor chunks and shared code

Splitting on `import()` solves only half the problem. The other half is extracting what **every** chunk needs, so it is neither duplicated nor re-downloaded.

```js
// webpack.config.js — the defaults worth knowing
module.exports = {
  optimization: {
    splitChunks: {
      chunks: 'async',          // ← IMPORTANT: only lazy chunks are touched by default
      minSize: 20000,
      minChunks: 1,
      maxAsyncRequests: 30,
      maxInitialRequests: 30,
      enforceSizeThreshold: 50000,
      cacheGroups: {
        defaultVendors: {
          test: /[\\/]node_modules[\\/]/,
          priority: -10,
          reuseExistingChunk: true,
        },
        default: { minChunks: 2, priority: -20, reuseExistingChunk: true },
      },
    },
  },
};
```

The first line is the main source of confusion: **`chunks: 'async'` means the entry chunk is not split at all**. So `react` and `react-dom`, which entered the graph from `main.tsx`, stay inside the entry chunk together with your code by default. That is why almost every real config sets `chunks: 'all'`.

A sensible setup for `shop-admin` looks like this:

```js
// webpack.config.js — grouping by change frequency, not "everything into one vendor"
module.exports = {
  optimization: {
    runtimeChunk: 'single',
    splitChunks: {
      chunks: 'all',
      cacheGroups: {
        // changes about once a year — its own long-lived chunk
        framework: {
          test: /[\\/]node_modules[\\/](react|react-dom|react-router)[\\/]/,
          name: 'framework',
          priority: 40,
        },
        // the rest of the dependencies — updated far more often
        vendor: {
          test: /[\\/]node_modules[\\/]/,
          name: 'vendor',
          priority: 20,
        },
        // application code needed by at least two chunks
        common: {
          minChunks: 2,
          name: 'common',
          priority: 10,
          reuseExistingChunk: true,
        },
      },
    },
  },
};
```

The same job in Vite. A fresh detail matters here. As of Vite 8, where Rolldown became the bundler, the object form of `output.manualChunks` is no longer supported. The function form is deprecated. Both were replaced by `codeSplitting` with groups — structurally very close to Webpack's `cacheGroups`:

```ts
// vite.config.ts
import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          minSize: 20000,
          groups: [
            {
              name: 'framework',
              test: /node_modules[\\/](react|react-dom|react-router)/,
              priority: 40,
            },
            { name: 'vendor', test: /node_modules/, priority: 20 },
            { name: 'common', minShareCount: 2, minSize: 10000, priority: 10 },
          ],
        },
      },
    },
  },
});
```

The terms map almost line for line: `cacheGroups` ↔ `groups`, `minChunks` ↔ `minShareCount`, with `priority` and `minSize` keeping their names. That is no accident: Rolldown deliberately adopted the Webpack model because it turned out to be more workable than a flat `manualChunks`. Since this is the freshest part of the ecosystem, the exact option shape is worth checking against the Rolldown docs — it is still being refined.

**The main anti-pattern of this section is one giant `vendor` chunk.** The reasoning goes like this: put all dependencies in one chunk, and it will be cached. It breaks on a simple fact. Updating any one of fifty dependencies changes the hash of the whole chunk, so the user re-downloads 400 kilobytes instead of 12. The right grouping principle is **by change frequency**, not by where the code came from.

## The runtime chunk: a tiny file with large consequences

```txt
   Why the runtime breaks caching and why you extract it
┌──────────────────────────────────────────────────────────┐
│ the build emits index.[hash].js, vendor.[hash].js,       │
│ orders.[hash].js                                         │
│                            ↓                             │
│ the runtime needs a map of chunk id → hashed file name   │
│                            ↓                             │
│ by default that map lives INSIDE the entry chunk         │
│                            ↓                             │
│ ANY chunk hash changes → the map changes → index changes │
│                            ↓                             │
│ runtimeChunk: 'single' moves the map into a ~2 KB file   │
│                            ↓                             │
│ editing orders changes orders.js and runtime.js;         │
│ index and vendor survive                                 │
└──────────────────────────────────────────────────────────┘
Vite extracts a runtime too, but people rarely think about it:
       chunk names are substituted differently there
```

The runtime is a small piece of housekeeping code. It knows how to load chunks on demand, and it holds the mapping from a chunk id to a file on disk. While that table lives inside the entry chunk, the entry chunk changes on **any** hash change — that is, on practically every release. The single line `runtimeChunk: 'single'` severs that link.

## Long-term caching: contenthash and what breaks it

The scheme is simple: the file name contains a hash of its contents, and the server serves it with the most aggressive header available.

```js
// webpack.config.js
output: {
  filename: '[name].[contenthash].js',        // entry chunks
  chunkFilename: '[name].[contenthash].js',   // lazy chunks
}
```

```txt
Cache-Control: public, max-age=31536000, immutable
```

`immutable` means "this URL will never change its contents" — the browser will not even revalidate. That is safe precisely because changed content means a changed name and therefore a changed URL. Only `index.html` must not be cached: it is the entry point from which the browser learns the new names.

Three placeholders are easy to confuse, and the difference matters:

- `[hash]` — one hash for the entire build. Change anything and every file name changes. The worst possible option for caching.
- `[chunkhash]` — a per-chunk hash, but computed before final processing.
- `[contenthash]` — a hash of a specific asset's contents. The only correct choice, and the one that lets a CSS file stay unchanged when only the JS changed.

```txt
            What a user re-downloads after a release
┌─────────────────────────────────────────────────────────────┐
│ you changed one line in Orders.tsx                          │
│   a bad setup:  index + vendor + orders                     │
│   a good setup: orders + runtime                            │
├─────────────────────────────────────────────────────────────┤
│ you added a new module                                      │
│   a bad setup:  index + vendor, because ids shifted         │
│   a good setup: index + runtime                             │
├─────────────────────────────────────────────────────────────┤
│ you bumped one dependency                                   │
│   a bad setup:  the entire vendor chunk                     │
│   a good setup: that dependency's chunk                     │
├─────────────────────────────────────────────────────────────┤
│ you reordered imports                                       │
│   a bad setup:  vendor, because the order shifted           │
│   a good setup: nothing                                     │
├─────────────────────────────────────────────────────────────┤
│ you rebuilt with no changes                                 │
│   a bad setup:  everything, because the hashes are unstable │
│   a good setup: nothing                                     │
└─────────────────────────────────────────────────────────────┘
  the gap between the two setups is moduleIds: deterministic,
     an extracted runtimeChunk and sensible vendor grouping
```

### Why "I changed one line and the whole vendor chunk was re-downloaded"

A classic interview question with three independent causes.

**1. Unstable module identifiers.** The bundler assigns every module an id, and that id ends up inside other chunks — wherever the module is imported. If ids are handed out in graph-walk order, adding a single file to your application shifts the numbering. The vendor chunk's contents then change even though no dependency was updated.

The fix is deterministic ids that depend only on the module itself:

```js
optimization: {
  moduleIds: 'deterministic',
  chunkIds: 'deterministic',
}
```

In `mode: 'production'` this is already the default (see the defaults table in [The Webpack Core Model](./03-webpack-core-model.md)). But older configs still contain `HashedModuleIdsPlugin` and `NamedModulesPlugin` — the Webpack 4-era way of solving the same problem. The first is deprecated, the second removed; today it is all expressed through `optimization.moduleIds`.

**2. The runtime inside the entry chunk** — covered above.

**3. The hash is computed from the wrong thing.** If the hash is calculated before minification, then changes the minifier would erase anyway (comments, variable names) still change the file name. That is what `optimization.realContentHash: true`, on by default in production, addresses: the hash is taken from the **final** asset contents.

Vite ships `contenthash` in names out of the box, and the placeholders are configured through `entryFileNames`, `chunkFileNames` and `assetFileNames` under `rolldownOptions.output`. The unstable-id problem surfaces less often there, but vendor grouping has exactly the same consequences.

## Browser hints: preload, prefetch, modulepreload

```txt
        Browser hints: what you ask for and what it costs
┌───────────────────────────────────────────────────────────────┐
│ nothing — the browser loads the chunk when import() is called │
│   it costs a pause on every route navigation                  │
├───────────────────────────────────────────────────────────────┤
│ prefetch — loads when idle, at low priority                   │
│   it costs bandwidth for pages that are never opened          │
├───────────────────────────────────────────────────────────────┤
│ modulepreload — loads now, at high priority                   │
│   it competes with the critical path                          │
├───────────────────────────────────────────────────────────────┤
│ preload — loads now, at the highest priority                  │
│   it evicts what is needed right now                          │
└───────────────────────────────────────────────────────────────┘
prefetch is about the next navigation, preload about this screen;
 prefetching every route at once means downloading the whole app
```

```tsx
// Webpack: hints are magic comments inside import()
const Analytics = lazy(() => import(
  /* webpackChunkName: "analytics" */
  /* webpackPrefetch: true */          // "will be needed on the next navigation"
  './routes/Analytics'
));
```

Vite works differently: `build.modulePreload` is on by default, and the bundler inserts `<link rel="modulepreload">` for the entry chunk and its direct imports itself. The point is exactly the waterfall: the browser learns about second-level dependencies from the HTML rather than after parsing the first file. Vite also injects a small polyfill, because `modulepreload` is not supported everywhere.

The main mistake with hints is treating them as free. Bandwidth and the priority queue are finite: a lazy route marked `preload` competes with the first screen's font and CSS. A practical rule: use `prefetch` for the one or two most likely next navigations. Use `preload` only for what is needed immediately and what the browser cannot discover on its own.

## The trade-off: many small chunks or few large ones

```txt
          Many small chunks or few large ones
┌──────────────────────────────────────────────────┐
│ Few large chunks                                 │
│                                                  │
│ request count    low                             │
│ waterfall depth  short                           │
│ cache hit rate   low: an edit hits a big file    │
│ compression      better: one dictionary per file │
│ overhead         minimal                         │
│ when to pick it  little code, rare releases      │
└──────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────┐
│ Many small chunks                                   │
│                                                     │
│ request count    high, but HTTP/2 multiplexes       │
│ waterfall depth  risk of a chain of dependent loads │
│ cache hit rate   high: one small file changes       │
│ compression      worse: a dictionary per file       │
│ overhead         a runtime entry per chunk          │
│ when to pick it  a big app, frequent releases       │
└─────────────────────────────────────────────────────┘
there is no universal chunk count: it is a choice between
the cost of the first load and the cost of every later release
```

There is no recipe here — there are three questions whose answers decide it.

**How often do you release?** Quarterly, and caching barely matters: users arrive with a cold cache anyway. Several times a week, and splitting pays off — most assets stay valid across releases.

**What share of the code does the first screen need?** If it is 80%, there is little to split and you are just adding rounds. If it is 15%, splitting is where the win comes from.

**What network are your users on?** On a high-latency mobile connection every extra waterfall level costs hundreds of milliseconds. Small chunks that depend on each other then end up costlier than one medium chunk.

One argument that is often forgotten: **compression**. Gzip and Brotli build their dictionary of repeats within a single file. Ten 20-kilobyte files compress noticeably worse than one 200-kilobyte file, because each starts from its own dictionary.

That is why very small chunks rarely pay for themselves. It is no accident that Webpack's `minSize` defaults to 20 kilobytes, and Rolldown's config examples use the same value.

A practical starting point, not a dogma: keep the runtime, the framework, the remaining vendors, shared application code and one chunk per major route separate. Anything smaller than a few tens of kilobytes is usually better merged into a neighbour. How to verify the result — the bundle analysis method in [Tree Shaking and Optimization](./05-tree-shaking-and-optimization.md).

## Relation to other topics

- [Why Bundlers Exist](./01-why-bundlers-exist.md) — the request waterfall: why
  the number of levels matters more than the file count.
- [The Module Graph and Resolution](./02-module-graph-and-resolution.md) — why
  only a statically visible `import()` can be a break in the graph.
- [The Webpack Core Model](./03-webpack-core-model.md) — module → chunk → asset,
  and the `mode` defaults that `moduleIds` comes from.
- [Tree Shaking and Optimization](./05-tree-shaking-and-optimization.md) — how to
  see what landed in each chunk, and why a chunk is bigger than expected.
- [The Vite Model](./06-vite-model.md) — why none of this applies in dev mode,
  and why it should not.
- [Ecosystem and Choosing a Tool](./08-ecosystem-and-choosing.md) — Module
  Federation: sharing code between separate applications.
- The Nx course — Module Federation in practice.

## Common interview traps

- **"Code splitting is when webpack divides the bundle by itself"** — it divides only along rules you gave it. Only `import()` creates a break in the graph; `splitChunks` regroups what already exists but never invents new boundaries. Someone who thinks the bundler "will pull the heavy library out on its own" has not understood the mechanics.

- **Not knowing that `splitChunks.chunks` defaults to `'async'`.** A very practical question sounds like this: I configured `cacheGroups`, so why is `react` still in the entry chunk? The answer: entry chunks are untouched by default, and you need `chunks: 'all'`.

- **One big `vendor` chunk "so it caches better"** — the reasoning is backwards. The bigger the chunk, the likelier the next release invalidates it. The right principle is grouping by change frequency: the framework separate from everything else.

- **Being unable to explain why one edited line re-downloaded the vendor chunk.** Arguably the central question of this topic. A full answer names three causes: module ids, the runtime inside the entry chunk, and when the hash is computed. "You need contenthash" is incomplete — contenthash was already there, otherwise nobody would have noticed the problem.

- **Confusing `[hash]`, `[chunkhash]` and `[contenthash]`** — the difference is exactly what the value is computed from, and that is what decides whether caching works at all.

- **"Prefetch never hurts"** — it does. Ten routes marked `prefetch` means the whole application is downloaded, just slightly later. A strong answer frames it as a priority decision rather than a free optimization.

- **"More chunks is always better"** — also no. Compression (a dictionary per file) and chains of dependent loads are the parts people forget. They are exactly what separates a memorized recipe from understanding the trade-off.

- **Ignoring that a lazy chunk can fail to load.** A good probe: what does a user see if you deploy a new release while their tab is open? The answer separates people who have configured a production build from people who have only read about one.
