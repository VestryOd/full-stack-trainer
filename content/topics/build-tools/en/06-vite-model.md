# The Vite Model

## The core idea: dev and prod are two different tools in one wrapper

Everything else in this article follows from one architectural decision. Webpack describes both modes with a single model: build the whole graph, then run the dev server on top of that build. Vite asks a different question: **is a bundle needed in dev at all?** Since the browser speaks ESM, a development server only needs to answer a request for one file.

```txt
            DEV: a native-ESM server                                    PROD: a full build
┌───────────────────────────────────────────────────┐    ┌───────────────────────────────────────────────────┐
│ step by step                                      │    │ step by step                                      │
│                                                   │    │                                                   │
│ 1. startup     dependency pre-bundling            │    │ 1. walk           the whole graph from index.html │
│ 2. request     the browser asks for /src/App.tsx  │    │ 2. transform      every module at once            │
│ 3. transform   one file, on demand                │    │ 3. tree shaking   unreachable code removed        │
│ 4. response    a valid ES module                  │    │ 4. chunking       splitting and hashed names      │
│ 5. imports     the browser asks for the next ones │    │ 5. minification   the default minifier            │
│                                                   │    │                                                   │
│ no bundle      the full graph is never built      │    │ a bundle exists   DIFFERENT code runs             │
└───────────────────────────────────────────────────┘    └───────────────────────────────────────────────────┘
             cold start barely depends on                       essentially the same build Webpack does,
               the size of the project                                just on a different bundler
```

Vite's main strength and its main hazard both grow from this asymmetry, and it is worth holding them together: cold start barely depends on project size — but dev and prod run **different code**.

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

The key detail is **import rewriting**. The browser would not understand `'react/jsx-runtime'`, so Vite performs resolution on the fly (the very algorithm from [The Module Graph and Resolution]) and substitutes a path the browser can request. Resolution has not disappeared — it moved from build time into request handling.

**Why this is fast.** The amount of work is proportional to the files needed for the current screen, not to the number of files in the project. Open `/orders` and that route's modules get transformed. The `/analytics` modules are never touched until you navigate there. Hence the claim that cold start barely depends on project size: a five-thousand-module project boots about as fast as a five-hundred-module one.

**What it costs.** The request count in dev is enormous: the Network panel shows hundreds of rows instead of a dozen. Locally that is cheap (the request goes to a process on the same machine) but not free — and on very large projects it becomes noticeable. Vite 8's answer is an experimental full-bundle dev mode, which claims a several-times faster server start and an order of magnitude fewer requests. At the time of writing that is an experiment, and its status is worth checking in the `vite.dev` docs rather than treating as settled.

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

This is the least obvious part of the model, and "why does Vite pre-bundle dependencies if it is all about native ESM?" works well as an interview filter. There are exactly two reasons, both practical:

**1. CommonJS interop.** A significant share of `node_modules` is still published as CJS. The browser cannot do `module.exports`, and no amount of native ESM helps. Pre-bundling turns such a dependency into an ESM module with proper named exports — including the heuristic that lets you write `import { pick } from 'lodash'` (see the CJS wrapper discussion in [The Module Graph and Resolution]).

**2. Request count.** A package like `lodash-es` is hundreds of tiny files. Serving them one by one reproduces exactly the waterfall that bundlers exist to avoid ([Why Bundlers Exist]). One pre-bundled dependency is one request.

The cache lives in `node_modules/.vite` and is served with aggressive caching headers, with invalidation handled by a version query in the URL (`?v=8f4c1e` in the example above). The cache is rebuilt when the lockfile, patches, relevant config fields or `NODE_ENV` change; force it with `--force`.

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

The `new dependency optimized, reloading` message in the console is not an error but a signal that Vite discovered a dependency late: it was not present during the initial scan and turned up in a lazy route. Once or twice is normal; regularly is a reason to list those packages in `optimizeDeps.include`.

**A note on versions.** The pre-bundling mechanism stayed, but the tool underneath it changed: this work used to be done by esbuild, and in the current version it is done by Rolldown — the same bundler that builds production. So the popular phrasing "Vite is fast in dev because it uses esbuild" is doubly out of date: it was imprecise to begin with (esbuild handled pre-bundling and transformation, not the dev server's speed as such) and now it names the wrong tool as well.

## Prod: an ordinary full build

There is no magic in production mode — everything covered in [Code Splitting and Long-Term Caching] and [Tree Shaking and Optimization] happens: a full graph walk, tree shaking, chunk splitting, hashed names, minification.

What is worth knowing about the current state — and simultaneously the place where checking the docs beats reading someone's article:

- At the time of writing the production build is performed by **Rolldown** — a Rust port of Rollup that kept compatibility with its plugin interface. The pairing used to be different: Rollup was the bundler and esbuild handled transformation and minification. Check the current state on `vite.dev` and `rolldown.rs`.
- Hence the config renames: `build.rollupOptions` → `build.rolldownOptions` (the old name works as an alias), and the object form of `output.manualChunks` is no longer supported — replaced by `codeSplitting.groups`, covered in [Code Splitting and Long-Term Caching].
- The default minifier is from the Oxc family; `'terser'` remains available if you need the last few percent of compression. The trade-off is discussed in [Tree Shaking and Optimization].
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

The function form of the config is not decoration: `command` (`'serve'` or `'build'`) and `mode` are the only honest way to separate settings for the two modes — and a reminder that there really are two.

**Plugins.** Vite has one extension concept instead of two — a plugin with hooks, rather than separate loaders and plugins (the comparison is in [The Webpack Core Model]). The interface is inherited from Rollup: `resolveId`, `load`, `transform`, `generateBundle`. Vite-specific hooks are layered on top:

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

Compatibility with the Rollup ecosystem is not a side effect but a deliberate bet: it gave Vite a ready-made plugin catalogue from day one. Rolldown kept the same interface for exactly that reason, and the Vite 8 announcement phrases the compatibility as "most existing plugins work out of the box". But "most" is not "all": plugins reaching deep into Rollup internals may need updating.

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
- **A path assembled as a string will not be rewritten.** The classic mistake: `<img src={'/assets/' + name + '.png'} />` works in dev (the file is where you expect it) and breaks in prod (the file's name got a hash). `new URL(..., import.meta.url)` is the only form the bundler can analyse, and only when the static part of the path is visible.

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

The `.env` loading order is `.env` → `.env.local` → `.env.[mode]` → `.env.[mode].local`, where the more specific overrides the less specific, and variables already present in the environment take highest priority and are never overwritten. The prefix is configurable through `envPrefix`.

What matters about the prefix is not the mechanism but the intent: **it exists so you do not ship secrets into a bundle by accident.** Anything under `VITE_*` ends up in client-side source code — the docs warn about that in plain language. A payment API token in a variable with that prefix is not a configuration choice, it is an incident.

## The price: the "works in dev, broken in prod" class of bugs

```txt
                            The "works in dev, broken in prod" class of bugs
┌──────────────────────────┬────────────────────────────────────────┬─────────────────────────────────┐
│ symptom                  │ cause                                  │ how to catch it early           │
├──────────────────────────┼────────────────────────────────────────┼─────────────────────────────────┤
│ a blank screen in prod   │ a CJS package survived on pre-bundling │ a prod build in CI on every PR  │
├──────────────────────────┼────────────────────────────────────────┼─────────────────────────────────┤
│ the styles disappeared   │ sideEffects: false plus tree shaking   │ open vite preview locally       │
├──────────────────────────┼────────────────────────────────────────┼─────────────────────────────────┤
│ process is not defined   │ process does not exist in a browser    │ move to import.meta.env         │
├──────────────────────────┼────────────────────────────────────────┼─────────────────────────────────┤
│ a different init order   │ module merging changes the order       │ remove cycles from the graph    │
├──────────────────────────┼────────────────────────────────────────┼─────────────────────────────────┤
│ type errors reached prod │ Vite does not type-check at all        │ tsc --noEmit as a separate step │
├──────────────────────────┼────────────────────────────────────────┼─────────────────────────────────┤
│ an asset was not found   │ the file path was built as a string    │ new URL(..., import.meta.url)   │
└──────────────────────────┴────────────────────────────────────────┴─────────────────────────────────┘
                      every row shares one root cause: dev and prod run DIFFERENT
                             code, and dev verifies less than it appears to
```

Two rows deserve special attention, because they surprise even experienced developers.

**Vite does not type-check.** TypeScript is handled as transpilation: types are simply stripped. No checking happens, so a file with type errors turns cleanly into working JS and ships to production. This is a deliberate decision (type checking is slow and unnecessary on every save), but it means `tsc --noEmit` must be a separate CI step. Developers used to `ts-loader`, which failed on a type error, walk into this regularly.

**A CJS package that survived on pre-bundling.** In dev the dependency went through pre-bundling and got tidy ESM exports. In prod there is no pre-bundling — the build takes the general path, and the same dependency may produce `does not provide an export named` or an empty object instead of a module. This is exactly the case where dev mode turned out to be *kinder* than production.

The practical conclusion is single and simple: **the production build must run in CI on every pull request**, and before a release its output is worth opening locally with `vite preview`. The dev/prod asymmetry is not a reason to avoid Vite, but it is a reason not to treat a green dev server as proof that anything works.

## When Vite is not the answer

```txt
                                          When Vite is not the answer
┌─────────────────────────────┬──────────────────────────────────────┬────────────────────────────────────────┐
│ the situation               │ what exactly is the problem          │ what to consider instead               │
├─────────────────────────────┼──────────────────────────────────────┼────────────────────────────────────────┤
│ home-grown webpack plugins  │ the compiler/compilation API differs │ Rspack: the config mostly carries over │
├─────────────────────────────┼──────────────────────────────────────┼────────────────────────────────────────┤
│ Module Federation as a base │ the mature ecosystem is webpack-side │ weigh the Vite plugin's maturity       │
├─────────────────────────────┼──────────────────────────────────────┼────────────────────────────────────────┤
│ support for old browsers    │ the default target is modern         │ the legacy plugin and its size cost    │
├─────────────────────────────┼──────────────────────────────────────┼────────────────────────────────────────┤
│ a monolithic legacy config  │ inline loaders, bespoke rules        │ migrate in parts, or use Rspack        │
├─────────────────────────────┼──────────────────────────────────────┼────────────────────────────────────────┤
│ dev must equal prod         │ two models is a design decision      │ Webpack or Rspack: one model           │
└─────────────────────────────┴──────────────────────────────────────┴────────────────────────────────────────┘
                             no row here says "Vite is worse" — each says the speed
                                      advantage comes at a specific price
```

More detail on the two points people most often misjudge.

**Home-grown webpack plugins.** If a project has a plugin that works with `compilation` — editing the graph, generating assets from the whole build, interfering with chunking — rewriting it against the Rollup interface is not always merely laborious but sometimes impossible: there are two models and they are not isomorphic. The honest answer here is to look at Rspack, which is compatible with webpack configs and plugins and delivers the speed win without changing the model ([Ecosystem and Choosing a Tool]).

**Module Federation.** The mechanism was invented in the Webpack ecosystem, and most of the accumulated experience and tooling lives there. Plugins exist for Vite, and the Vite 8 announcement explicitly names the unified bundler as what "unlocks" Module Federation support. But the situation here changes fast: some solutions are mature, others are still arriving. If Module Federation is the foundation of your architecture rather than a detail, evaluate a specific implementation on a specific version rather than the general trend. The mechanism itself is covered at overview level in [Ecosystem and Choosing a Tool] and in depth in the NX course.

## Relation to other topics

```txt
[Why Bundlers Exist]                — the dev-versus-prod frame and the request
                                       waterfall that makes pre-bundling necessary
[The Module Graph and Resolution]   — the resolution Vite performs on the fly,
                                       and CJS wrappers
[The Webpack Core Model]            — the other model: one build for both modes,
                                       loaders and plugins as separate concepts
[Code Splitting and Long-Term
 Caching]                            — what Vite's production build actually does:
                                       codeSplitting.groups, hashes, chunks
[Tree Shaking and Optimization]     — the default minifier, source maps,
                                       bundle analysis
[Dev Server and HMR]                — the other half of dev mode: how an update
                                       reaches the browser
[Ecosystem and Choosing a Tool]     — Rolldown, Rspack, Turbopack and the
                                       Webpack → Vite migration step by step
NX course                            — Module Federation in practice
Angular course                       — building an Angular application
```

## Common interview traps

- **"Vite is fast because it is written in Rust"** (or "because of esbuild") — the most common mistake in this topic and a good filter. A fast language speeds up individual steps by a multiple, but the main win comes from **changing the problem**: in dev the full graph is never built, and the work is proportional to the open screen rather than the project size. An answer that opens with the implementation language shows someone read headlines rather than the mechanics.

- **"There is no build in Vite"** — not in dev, but there is in production, and it is a full one: tree shaking, chunking, minification, hashes. Someone who does not separate the two has usually not met the "broken in prod" bugs either.

- **Being unable to say why pre-bundling exists.** Two reasons are expected: CJS packages the browser cannot execute, and the request count when a package is served file by file. "For speed" without the mechanism is half credit.

- **"Vite type-checks, since it understands TypeScript"** — it does not. Types are stripped, errors are not diagnosed, and `tsc --noEmit` is needed separately. This is a practical trap that catches real projects, not an abstract fact.

- **`process.env` in browser code** — a marker of Webpack habits carried over. In Vite it is `import.meta.env` with the `VITE_` prefix, and it is worth adding that prefixed variables end up in the bundle, so no secrets belong there.

- **Confident claims about "what Vite builds production with".** This specific point changed twice in a short span. The strong phrasing is "in the version I worked with it was bundler X; the current state is worth checking in the docs" — more honest than a confidently stated stale detail.

- **"Vite is always better than Webpack"** — senior interviews value the opposite: naming the cases where Vite does not fit (home-grown plugins on `compilation`, Module Federation as a foundation, a requirement that dev equal prod, old browsers) and naming an alternative such as Rspack. An answer without a single "does not fit" reads as no migration experience.
