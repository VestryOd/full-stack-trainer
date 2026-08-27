# The Vite Model

## The core idea: dev and prod are two different tools in one wrapper

Everything else in this article follows from one architectural decision. Webpack describes both modes with a single model: build the whole graph, then run the dev server on top of that build.

Vite asks a different question: **is a bundle needed in dev at all?** The browser already speaks ESM (ECMAScript modules — the built-in `import` and `export` syntax). A development server then only needs to answer a request for one file.

```txt
              DEV: a native-ESM server
┌───────────────────────────────────────────────────┐
│ step by step                                      │
│                                                   │
│ 1. startup     dependency pre-bundling            │
│ 2. request     the browser asks for /src/App.tsx  │
│ 3. transform   one file, on demand                │
│ 4. response    a valid ES module                  │
│ 5. imports     the browser asks for the next ones │
│                                                   │
│ no bundle      the full graph is never built      │
└───────────────────────────────────────────────────┘
  cold start barely depends on the size of the project

                 PROD: a full build
┌───────────────────────────────────────────────────┐
│ step by step                                      │
│                                                   │
│ 1. walk           the whole graph from index.html │
│ 2. transform      every module at once            │
│ 3. tree shaking   unreachable code removed        │
│ 4. chunking       splitting and hashed names      │
│ 5. minification   the default minifier            │
│                                                   │
│ a bundle exists   DIFFERENT code runs             │
└───────────────────────────────────────────────────┘
  essentially the same build Webpack does, just on
  a different bundler
```

Vite's main strength and its main hazard grow from the same asymmetry. Hold both in mind at once: cold start barely depends on project size, but dev and prod run **different code**.

## Dev: the browser as the module loader

In dev mode Vite is an HTTP server with a transformer. It does not build a graph; it answers requests.

```txt
GET /src/routes/Orders.tsx
```

```js
// roughly what Vite responds with
import { jsx as _jsx } from "/node_modules/.vite/deps/react_jsx-runtime.js?v=8f4c1e";
import { fetchOrders } from "/src/lib/api.ts";
import "/src/ui/Button.css";

export function Orders() { /* the JSX is already compiled into calls */ }
```

The key detail is **import rewriting**. The browser would not understand `'react/jsx-runtime'`, so Vite resolves it on the fly and substitutes a path the browser can request. That is the very algorithm from [The Module Graph and Resolution](./02-module-graph-and-resolution.md). Resolution has not disappeared — it moved from build time into request handling.

**Why this is fast.** The amount of work is proportional to the files needed for the current screen, not to the number of files in the project. Open `/orders` and that route's modules get transformed. The `/analytics` modules are never touched until you navigate there. Hence the claim that cold start barely depends on project size: a five-thousand-module project boots about as fast as a five-hundred-module one.

**What it costs.** The request count in dev is enormous: the Network panel shows hundreds of rows instead of a dozen. Locally that is cheap, because the request goes to a process on the same machine. It is not free, though, and on very large projects it becomes noticeable.

Vite 8 answers this with an experimental full-bundle dev mode. It claims a several-times faster server start and an order of magnitude fewer requests. At the time of writing this is an experiment. Its status is worth checking in the `vite.dev` docs rather than treating it as settled.

## Dependency pre-bundling

```txt
                Why Vite pre-bundles dependencies
┌───────────────────────────────────────────────────────────────┐
│ in your code: import { debounce } from 'lodash-es'            │
│                               ↓                               │
│ without pre-bundling the browser would walk the package graph │
│                               ↓                               │
│ ≈600 separate requests for one function                       │
│                               ↓                               │
│ and a CJS package the browser cannot execute at all           │
│                               ↓                               │
│ pre-bundling: the dependency becomes a single ESM file        │
│                               ↓                               │
│ the result is cached in node_modules/.vite                    │
│                               ↓                               │
│ the browser makes ONE request, CJS is already ESM             │
└───────────────────────────────────────────────────────────────┘
    the cache is rebuilt when the lockfile, patches, config or
         NODE_ENV change; force it with the --force flag
```

This is the least obvious part of the model. The question "why does Vite pre-bundle dependencies if it is all about native ESM?" works well as an interview filter. There are exactly two reasons, both practical:

**1. CommonJS interop.** A significant share of `node_modules` is still published as CJS (CommonJS — the `module.exports` format Node has always used). The browser cannot run `module.exports`, and no amount of native ESM helps.

Pre-bundling turns such a dependency into an ESM module with proper named exports. That includes the heuristic that lets you write `import { pick } from 'lodash'`. The CJS wrappers behind it are covered in [The Module Graph and Resolution](./02-module-graph-and-resolution.md).

**2. Request count.** A package like `lodash-es` is hundreds of tiny files. Serving them one by one reproduces exactly the waterfall that bundlers exist to avoid ([Why Bundlers Exist](./01-why-bundlers-exist.md)). One pre-bundled dependency is one request.

The cache lives in `node_modules/.vite` and is served with aggressive caching headers. Invalidation is handled by a version query in the URL — `?v=8f4c1e` in the example above. The cache is rebuilt when the lockfile, patches, relevant config fields or `NODE_ENV` change; force it with `--force`.

When manual intervention is needed:

```ts
// vite.config.ts
export default defineConfig({
  optimizeDeps: {
    // a dependency Vite does not discover at startup
    // (for instance, one imported only from inside another package)
    include: ['chart-lib > date-fns'],
    // a local monorepo package: pre-bundling it would mean
    // edits inside it stop being picked up
    exclude: ['@my-org/ui-kit'],
  },
});
```

The `new dependency optimized, reloading` message in the console is not an error. It is a signal that Vite discovered a dependency late: the initial scan missed it, and it turned up in a lazy route. Once or twice is normal. Seeing it regularly is a reason to list those packages in `optimizeDeps.include`.

**A note on versions.** The pre-bundling mechanism stayed, but the tool underneath it changed. This work used to be done by esbuild. In the current version it is done by Rolldown — the same bundler that builds production.

So the popular phrasing "Vite is fast in dev because it uses esbuild" is doubly out of date. It was imprecise to begin with: esbuild handled pre-bundling and transformation, not the dev server's speed as such. And now it names the wrong tool as well.

## Prod: an ordinary full build

There is no magic in production mode. Everything the earlier articles covered happens here: a full graph walk, tree shaking, chunk splitting, hashed names, minification. The details are in [Code Splitting and Long-Term Caching](./04-code-splitting-and-caching.md) and [Tree Shaking and Optimization](./05-tree-shaking-and-optimization.md).

What is worth knowing about the current state — and simultaneously the place where checking the docs beats reading someone's article:

- At the time of writing the production build is performed by **Rolldown** — a Rust port of Rollup that kept compatibility with its plugin interface. The pairing used to be different: Rollup was the bundler and esbuild handled transformation and minification. Check the current state on `vite.dev` and `rolldown.rs`.
- Hence the config renames. `build.rollupOptions` became `build.rolldownOptions`, and the old name still works as an alias. The object form of `output.manualChunks` is gone, replaced by `codeSplitting.groups` — covered in [Code Splitting and Long-Term Caching](./04-code-splitting-and-caching.md).
- The default minifier is from the Oxc family; `'terser'` remains available if you need the last few percent of compression. The trade-off is discussed in [Tree Shaking and Optimization](./05-tree-shaking-and-optimization.md).
- `build.target` defaults to a set of widely available browser features rather than specific versions in your config. The practical consequence: no polyfills by default, and support for old browsers is a separate plugin's job.

## Config and plugins

```ts
// vite.config.ts — a typical config for shop-admin
import path from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ command, mode }) => ({
  plugins: [react()],

  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
    dedupe: ['react', 'react-dom'],
  },

  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:3000', changeOrigin: true },
    },
  },

  build: {
    sourcemap: mode === 'staging' ? 'hidden' : false,
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            { name: 'framework', test: /node_modules[\\/](react|react-dom)/, priority: 40 },
            { name: 'vendor', test: /node_modules/, priority: 20 },
          ],
        },
      },
    },
  },
}));
```

The function form of the config is not decoration. The two arguments `command` (either `'serve'` or `'build'`) and `mode` are the only honest way to separate the settings of the two modes. They are also a reminder that there really are two.

**Plugins.** Vite has one extension concept instead of two: a plugin with hooks, rather than separate loaders and plugins. The comparison is in [The Webpack Core Model](./03-webpack-core-model.md). The interface is inherited from Rollup: `resolveId`, `load`, `transform`, `generateBundle`. Vite-specific hooks are layered on top:

```ts
import type { Plugin } from 'vite';

export function envBanner(): Plugin {
  return {
    name: 'env-banner',
    enforce: 'pre',              // before Vite's built-in plugins
    apply: 'serve',              // dev server only
    config(userConfig, { mode }) { /* adjust the config before it is resolved */ },
    configureServer(server) { /* add middleware to the dev server */ },
    transformIndexHtml(html) { return html.replace('<!--banner-->', '<div>dev</div>'); },
  };
}
```

Compatibility with the Rollup ecosystem is not a side effect but a deliberate bet: it gave Vite a ready-made plugin catalogue from day one. Rolldown kept the same interface for exactly that reason. The Vite 8 announcement phrases the compatibility as "most existing plugins work out of the box". But "most" is not "all": plugins reaching deep into Rollup internals may need updating.

## Static assets and environment variables

```ts
// four different ways to get an asset — and you need all of them
import logoUrl from '@/assets/logo.svg';          // a hashed URL after the build
import logoRaw from '@/assets/logo.svg?raw';      // the contents as a string
import iconUrl from '@/assets/icon.png?url';      // always a URL, never inlined
import styles from '@/ui/Button.css?inline';      // CSS as a string, not injected

// a dynamic path — only through a URL relative to import.meta.url
const flag = new URL(`./flags/${code}.svg`, import.meta.url).href;
```

Rules worth memorizing:

- **`public/`** is served from the root in dev and copied to the root of `dist` as-is. Files there do not pass through the build: no hash in the name, no existence check. Fine for `robots.txt` and a favicon, not fine for anything meant to be cached forever.
- **Small assets are inlined** as base64 when below the threshold (`build.assetsInlineLimit`). That saves a request but grows the JS chunk — and therefore breaks separate caching of the image and the code.
- **A path assembled as a string will not be rewritten.** The classic mistake is `<img src={'/assets/' + name + '.png'} />`. It works in dev, where the file is exactly where you expect it. It breaks in prod, because the file's name got a hash. The only form the bundler can analyse is `new URL(..., import.meta.url)`, and only when the static part of the path is visible.

Environment variables work differently from Webpack, and this is the main source of migration pain:

```ts
// in browser code, ONLY this is available
import.meta.env.VITE_API_URL      // your variables — the VITE_ prefix is mandatory
import.meta.env.MODE              // the current mode
import.meta.env.PROD              // boolean
import.meta.env.DEV               // boolean
import.meta.env.BASE_URL          // the app's base path

// process.env does not exist in the browser — it is a Node API
```

The `.env` loading order is `.env` → `.env.local` → `.env.[mode]` → `.env.[mode].local`. The more specific file overrides the less specific one. Variables already present in the environment take highest priority and are never overwritten. The prefix is configurable through `envPrefix`.

What matters about the prefix is not the mechanism but the intent: **it exists so you do not ship secrets into a bundle by accident.** Anything under `VITE_*` ends up in client-side source code — the docs warn about that in plain language. A payment API token in a variable with that prefix is not a configuration choice, it is an incident.

## The price: the "works in dev, broken in prod" class of bugs

Every row below shares one root cause: dev and prod run **different code**, and dev verifies less than it appears to.

| symptom | cause | how to catch it early |
|---|---|---|
| a blank screen in prod | a CJS package survived on pre-bundling | a prod build in CI (continuous integration) on every pull request |
| the styles disappeared | `sideEffects: false` plus tree shaking | open `vite preview` locally |
| `process is not defined` | `process` does not exist in a browser | move to `import.meta.env` |
| a different init order | module merging changes the order | remove cycles from the graph |
| type errors reached prod | Vite does not type-check at all | `tsc --noEmit` as a separate step |
| an asset was not found | the file path was built as a string | `new URL(..., import.meta.url)` |

Two rows deserve special attention, because they surprise even experienced developers.

**Vite does not type-check.** TypeScript is handled as transpilation: types are simply stripped. No checking happens, so a file with type errors turns cleanly into working JS and ships to production.

This is a deliberate decision — type checking is slow and unnecessary on every save. But it means `tsc --noEmit` must be a separate CI step. Developers used to `ts-loader`, which failed on a type error, walk into this regularly.

**A CJS package that survived on pre-bundling.** In dev the dependency went through pre-bundling and got tidy ESM exports. In prod there is no pre-bundling, so the build takes the general path. The same dependency may then produce `does not provide an export named` or an empty object instead of a module. This is exactly the case where dev mode turned out to be *kinder* than production.

The practical conclusion is single and simple: **the production build must run in CI on every pull request**. Before a release, its output is worth opening locally with `vite preview`. The dev/prod asymmetry is not a reason to avoid Vite. It is a reason not to treat a green dev server as proof that anything works.

## When Vite is not the answer

No row below says "Vite is worse". Each says that the speed advantage comes at a specific price.

| the situation | what exactly is the problem | what to consider instead |
|---|---|---|
| home-grown webpack plugins | the `compiler`/`compilation` API differs | Rspack: the config mostly carries over |
| Module Federation as a base | the mature ecosystem is webpack-side | weigh the Vite plugin's maturity |
| support for old browsers | the default target is modern | the `legacy` plugin and its size cost |
| a monolithic legacy config | inline loaders, hand-written rules | migrate in parts, or use Rspack |
| dev must equal prod | two models is a design decision | Webpack or Rspack: one model |

More detail on the two points people most often misjudge.

**Home-grown webpack plugins.** Some plugins work with `compilation`: they edit the graph, generate assets from the whole build, or interfere with chunking. Rewriting one against the Rollup interface is not always merely laborious. Sometimes it is impossible, because the two models do not map onto each other.

The honest answer here is to look at Rspack. It is compatible with webpack configs and plugins, and it delivers the speed win without changing the model ([Ecosystem and Choosing a Tool](./08-ecosystem-and-choosing.md)).

**Module Federation.** The mechanism was invented in the Webpack ecosystem, and most of the accumulated experience and tooling lives there. Plugins exist for Vite, and the Vite 8 announcement explicitly names the unified bundler as what "unlocks" Module Federation support.

But the situation here changes fast: some solutions are mature, others are still arriving. If Module Federation is the foundation of your architecture rather than a detail, evaluate a specific implementation on a specific version. The general trend is not enough. The mechanism itself is covered at overview level in [Ecosystem and Choosing a Tool](./08-ecosystem-and-choosing.md), and in depth in the Nx course.

## Relation to other topics

- [Why Bundlers Exist](./01-why-bundlers-exist.md) — the dev-versus-prod frame, and the request waterfall that makes pre-bundling necessary.
- [The Module Graph and Resolution](./02-module-graph-and-resolution.md) — the resolution Vite performs on the fly, and CJS wrappers.
- [The Webpack Core Model](./03-webpack-core-model.md) — the other model: one build for both modes, loaders and plugins as separate concepts.
- [Code Splitting and Long-Term Caching](./04-code-splitting-and-caching.md) — what Vite's production build actually does: `codeSplitting.groups`, hashes, chunks.
- [Tree Shaking and Optimization](./05-tree-shaking-and-optimization.md) — the default minifier, source maps, bundle analysis.
- [Dev Server and HMR](./07-dev-server-and-hmr.md) — hot module replacement and the other half of dev mode: how an update reaches the browser.
- [Ecosystem and Choosing a Tool](./08-ecosystem-and-choosing.md) — Rolldown, Rspack, Turbopack and the Webpack → Vite migration step by step.
- Nx course — Module Federation in practice.
- Angular course — building an Angular application.

## Common interview traps

- **"Vite is fast because it is written in Rust"** (or "because of esbuild") — the most common mistake in this topic and a good filter. A fast language speeds up individual steps by a multiple. The main win comes from **changing the problem**. In dev the full graph is never built, and the work is proportional to the open screen rather than to the project size. An answer that opens with the implementation language shows someone read headlines rather than the mechanics.

- **"There is no build in Vite"** — not in dev, but there is in production, and it is a full one: tree shaking, chunking, minification, hashes. Someone who does not separate the two has usually not met the "broken in prod" bugs either.

- **Being unable to say why pre-bundling exists.** Two reasons are expected: CJS packages the browser cannot execute, and the request count when a package is served file by file. "For speed" without the mechanism is half credit.

- **"Vite type-checks, since it understands TypeScript"** — it does not. Types are stripped, errors are not diagnosed, and `tsc --noEmit` is needed separately. This is a practical trap that catches real projects, not an abstract fact.

- **`process.env` in browser code** — a marker of Webpack habits carried over. In Vite it is `import.meta.env` with the `VITE_` prefix. It is worth adding that prefixed variables end up in the bundle, so no secrets belong there.

- **Confident claims about "what Vite builds production with".** This specific point changed twice in a short span. The strong phrasing is "in the version I worked with it was bundler X; the current state is worth checking in the docs". That is more honest than a confidently stated stale detail.

- **"Vite is always better than Webpack"** — senior interviews value the opposite. The expected answer names cases where Vite does not fit, and then names an alternative such as Rspack. Home-grown plugins on `compilation`, Module Federation as a foundation, a requirement that dev equal prod, old browsers — any of them counts. An answer without a single "does not fit" reads as no migration experience.
