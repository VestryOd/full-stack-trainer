# Ecosystem and Choosing a Tool

## The first distinction: bundler, transformer, or toolchain

Discussions about the ecosystem are usually spoiled by one mistake — every name is lined up together and the question becomes "which is best". Yet half the list does not compete with the other half at all: these are different layers.

- A **transformer** turns one file into another: TypeScript into JS, JSX into function calls, new syntax into old. It knows nothing about the module graph.
- A **bundler** builds the graph, cuts it into chunks and writes assets. Internally it almost always uses some transformer.
- A **toolchain** is a set of tools on a shared foundation: parser, linter, minifier, formatter, all working over one representation of the code.

```txt
                  The ecosystem map: what each tool is and whose niche it fills
┌───────────┬──────────────────────────┬───────────────────────────────────┬─────────────────────┐
│ tool      │ what it is               │ niche                             │ source of speed     │
├───────────┼──────────────────────────┼───────────────────────────────────┼─────────────────────┤
│ esbuild   │ bundler and transformer  │ scripts, tooling, tests           │ Go, parallelism     │
├───────────┼──────────────────────────┼───────────────────────────────────┼─────────────────────┤
│ SWC       │ transformer only         │ a Babel replacement inside others │ Rust, parallelism   │
├───────────┼──────────────────────────┼───────────────────────────────────┼─────────────────────┤
│ Oxc       │ parser, linter, minifier │ the foundation of Rolldown        │ Rust, one AST       │
├───────────┼──────────────────────────┼───────────────────────────────────┼─────────────────────┤
│ Rollup    │ bundler                  │ libraries, flat output            │ none: written in JS │
├───────────┼──────────────────────────┼───────────────────────────────────┼─────────────────────┤
│ Rolldown  │ bundler                  │ Vite's production build           │ Rust plus Oxc       │
├───────────┼──────────────────────────┼───────────────────────────────────┼─────────────────────┤
│ Rspack    │ bundler                  │ a Webpack swap by config          │ Rust, parallelism   │
├───────────┼──────────────────────────┼───────────────────────────────────┼─────────────────────┤
│ Turbopack │ bundler                  │ the internals of Next.js          │ Rust, on-disk cache │
├───────────┼──────────────────────────┼───────────────────────────────────┼─────────────────────┤
│ Parcel    │ bundler                  │ config-free building              │ Rust core and SWC   │
└───────────┴──────────────────────────┴───────────────────────────────────┴─────────────────────┘
                half this list are not competitors but parts inside another tool;
               "which one to choose" only makes sense for the rows saying "bundler"
```

Briefly on each — what it is and where you will actually meet it.

**esbuild.** Written in Go, capable of both transforming and bundling. Formally still on `0.x` versions, yet actively maintained and used everywhere — but specifically as a *component*: building a config file, running tests, producing a quick CLI build. It is rarely chosen as an application's main bundler: it deliberately omits some capabilities large applications need, in exchange for simplicity and speed.

**SWC.** Rust, a **transformer only** — it has no practically usable bundler of its own. Its reason for existing is replacing Babel where only transformation is needed: inside Next.js, Parcel, test runners. If you "use SWC", you almost certainly use a tool that uses SWC.

**Oxc.** A Rust toolchain: parser, resolver, linter (`oxlint`), transformer, minifier. The key idea is a shared foundation, so a file is not reparsed for every step. You probably do not install it directly; you receive it as Vite's minifier and as the foundation of Rolldown.

**Rollup.** The bundler that became the standard for **libraries**: flat readable output, excellent tree shaking, a simple plugin interface. Written in JS, so it loses on speed to native tools. Its main legacy is the plugin interface that both Vite and Rolldown adopted.

**Rolldown.** A Rust port of Rollup that kept compatibility with its plugins. At the time of writing it is the bundler behind Vite's production build (and the tool that pre-bundles dependencies) — see [The Vite Model].

**Rspack.** A Rust bundler that deliberately mirrors Webpack's API and configs. The positioning is direct: replace Webpack without rewriting your build. By the project's own account, compatibility covers nearly all common loaders and most popular plugins. On top of it sits a higher-level tool, Rsbuild, playing roughly the role Vite does: sensible defaults instead of a hand-written config.

**Turbopack.** A Rust bundler inside Next.js. As of Next.js 16 it is the default bundler for both dev and builds (webpack remains available behind a flag). Notably, it argues architecturally *against* Vite: Turbopack **bundles in dev too**, on the grounds that native ESM works well for small applications and starts losing on large ones because of the request count. Its bet is incremental computation with results cached to disk, plus lazily building only what was requested. A separate practical detail: it supports webpack **loaders** but not webpack **plugins**. Outside Next.js it is not yet used as a standalone tool.

**Parcel.** A bundler built on "works with no config": it detects file types itself and picks transformations. Inside are a Rust core and SWC. A good fit for a quick start and smaller projects, less so where precise control is needed.

## Where the speed comes from

```txt
                          Where the speed comes from: six mechanisms, not magic
┌───────────────────────────┬───────────────────────────────────────┬────────────────────────────────────┐
│ mechanism                 │ what it actually gives                │ the limit                          │
├───────────────────────────┼───────────────────────────────────────┼────────────────────────────────────┤
│ native code instead of JS │ parsing and codegen many times faster │ the same amount of work            │
├───────────────────────────┼───────────────────────────────────────┼────────────────────────────────────┤
│ parallelism across cores  │ files processed simultaneously        │ cores and graph dependencies       │
├───────────────────────────┼───────────────────────────────────────┼────────────────────────────────────┤
│ one AST for every step    │ a file is not reparsed per step       │ requires a unified toolchain       │
├───────────────────────────┼───────────────────────────────────────┼────────────────────────────────────┤
│ a cache between runs      │ a rebuild does strictly less          │ does not speed up the first run    │
├───────────────────────────┼───────────────────────────────────────┼────────────────────────────────────┤
│ lazy building             │ only what was requested is built      │ applies to dev only                │
├───────────────────────────┼───────────────────────────────────────┼────────────────────────────────────┤
│ doing less work at all    │ no dev bundle, no polyfills           │ paid for with dev/prod differences │
└───────────────────────────┴───────────────────────────────────────┴────────────────────────────────────┘
                          the first three are about doing the same work faster;
                  the last three are about doing less of it. Those are different answers
```

Splitting the top and bottom halves of that table is the most useful idea in this section. "Fast because Rust" describes the top half only, and in an interview that reveals surface-level understanding.

Parallelism deserves a note, because it is easy to overestimate. JavaScript on the main thread is single-threaded, and Webpack historically processed modules sequentially (working around it with loaders like `thread-loader` that spread work across processes). A native bundler distributes files across cores with no such scaffolding. But parallelism is bounded by the graph's structure: a module cannot be processed before its dependencies are known, so the speedup is never linear in core count.

The cache deserves a caveat too. A cache between runs speeds up a **rebuild** and does nothing for the first build. So in CI, where the cache is usually empty, the gain from incrementality often evaporates — unless you deliberately persist the cache directory across runs. That is one reason benchmark numbers do not match how a real project feels.

## Module Federation in bundler terms

```txt
                   Module Federation in bundler terms
┌──────────────────────────────────────────────────────────────────────┐
│ host and remote are two applications built SEPARATELY                │
│                                  ↓                                   │
│ the host declares remotes; the remote declares exposes and shared    │
│                                  ↓                                   │
│ the host's build contains no remote code — only a manifest reference │
│                                  ↓                                   │
│ at runtime the host fetches the manifest and the remote's chunk      │
│                                  ↓                                   │
│ common dependencies come from shared instead of being duplicated     │
└──────────────────────────────────────────────────────────────────────┘
 the mechanism lives at bundler level because the decision "this module
arrives from outside" is made where the graph and chunk runtime are built
```

Module Federation is a mechanism that lets one application load another application's modules **at runtime**, even though the two were built independently and deploy independently.

The key question for this article is not "how to configure it" but **why it lives in the bundler**. The answer follows from everything above: the bundler is the only place where the module graph, the resolution rules and the chunk-loading runtime are all known at once. To say "the `Analytics` module will arrive from another domain" you must intervene in resolution (do not look in `node_modules`), in chunking (do not include its code) and in the runtime (be able to fetch someone else's chunk). No tool outside the bundler controls all three simultaneously.

The second essential piece is `shared`. Without it each application would bring its own React, and the page would end up with several copies holding independent state — exactly the duplicate problem from [The Module Graph and Resolution], but at application scale.

```js
// webpack.config.js — a minimal illustration, not a guide
const { ModuleFederationPlugin } = require('webpack').container;

module.exports = {
  plugins: [
    new ModuleFederationPlugin({
      name: 'shopAdmin',
      remotes: { analytics: 'analytics@https://cdn.example.com/remoteEntry.js' },
      shared: { react: { singleton: true }, 'react-dom': { singleton: true } },
    }),
  ],
};
```

The treatment here is deliberately at overview level: Module Federation in depth — versioning of shared dependencies, failure strategies when a remote is unreachable, contracts between teams, organization in a monorepo — is covered in the **NX course**. A practical note on tooling: in Webpack it is a built-in plugin, plugins exist for Vite, and the Vite 8 announcement explicitly names the unified bundler as what "unlocks" Module Federation support. Turbopack supports no webpack plugins at all, so on Next.js 16+ the Module Federation question is answered separately.

## Migrating Webpack → Vite

```txt
                                  What breaks when moving from Webpack to Vite
┌──────────────────────────────┬──────────────────────────────────┬────────────────────────────────────────────┐
│ what breaks                  │ how it shows up                  │ what to do                                 │
├──────────────────────────────┼──────────────────────────────────┼────────────────────────────────────────────┤
│ require in your own code     │ require is not defined           │ rewrite it as import                       │
├──────────────────────────────┼──────────────────────────────────┼────────────────────────────────────────────┤
│ a CJS dependency             │ does not provide an export named │ the ESM build, optimizeDeps                │
├──────────────────────────────┼──────────────────────────────────┼────────────────────────────────────────────┤
│ node polyfills               │ process/Buffer is not defined    │ drop the dependency or polyfill explicitly │
├──────────────────────────────┼──────────────────────────────────┼────────────────────────────────────────────┤
│ process.env.*                │ undefined at runtime             │ import.meta.env and the VITE_ prefix       │
├──────────────────────────────┼──────────────────────────────────┼────────────────────────────────────────────┤
│ require.context              │ no such function exists          │ import.meta.glob                           │
├──────────────────────────────┼──────────────────────────────────┼────────────────────────────────────────────┤
│ custom loaders               │ no direct equivalent             │ a plugin with a transform hook             │
├──────────────────────────────┼──────────────────────────────────┼────────────────────────────────────────────┤
│ asset paths built as strings │ the file is missing in prod      │ ?url, ?inline, new URL                     │
├──────────────────────────────┼──────────────────────────────────┼────────────────────────────────────────────┤
│ Module Federation            │ the config is incompatible       │ a plugin; weigh its maturity               │
└──────────────────────────────┴──────────────────────────────────┴────────────────────────────────────────────┘
                       the pattern: almost everything relying on Node inside browser code
                              breaks, and almost nothing that was honest ESM does
```

Three items deserve detail, because they eat the most time.

**`require.context` → `import.meta.glob`.** The most underrated replacement. `require.context('./locales', false, /\.json$/)` is Webpack-specific; in Vite a native capability gives the same result:

```ts
// before (Webpack)
const ctx = require.context('./locales', false, /\.json$/);
const locales = ctx.keys().map((k) => ctx(k));

// after (Vite): lazy imports by glob
const loaders = import.meta.glob('./locales/*.json');            // () => Promise<module>
const eager = import.meta.glob('./locales/*.json', { eager: true }); // modules directly
```

A notable sign of ecosystem convergence: `import.meta.glob` and `import.meta.env` were invented in Vite, but Turbopack implemented compatible versions of both. Vite set not only a tool but part of the vocabulary.

**Node polyfills.** Webpack 4 substituted them automatically, Webpack 5 removed that, and Vite neither has nor plans them. The right order of action is to find out **why** browser code wanted `Buffer` or `crypto` at all. Usually the answer is "the library is server-side by design", and the fix is replacing the library rather than polyfilling. A polyfill is the last resort, and its cost in bundle size is real ([Tree Shaking and Optimization]).

**Custom loaders.** A loader that merely transforms a file's text rewrites into a plugin with a `transform` hook almost mechanically. A loader that knows about the build (generating a manifest, reading statistics) does not rewrite — because it was never really a loader but a plugin; the difference is covered in [The Webpack Core Model].

### The order of steps

1. **Install Vite alongside, without removing Webpack.** Two scripts in `package.json`, two builds. Being able to fall back to a working state at any moment is worth more than a tidy repository.
2. **Move the entry point into `index.html`.** In Vite the root of the graph is an HTML file, not JS ([The Module Graph and Resolution]). The script is attached as `<script type="module" src="/src/main.tsx">`.
3. **Replace environment variables.** `process.env.API_URL` → `import.meta.env.VITE_API_URL`. Take the opportunity to audit whether anything reached the client bundle that had no business being there.
4. **Deal with `require`, `require.context` and node polyfills.** Mechanical but the bulkiest part.
5. **Bring up the dev server.** Proxy, aliases, static assets, `historyApiFallback` ([Dev Server and HMR]).
6. **Build for production and compare chunk sizes with the old ones.** This is the most frequently skipped step — and the reason for "builds ten times faster, but the user downloads 300 KB more", because vendor grouping is configured differently ([Code Splitting and Long-Term Caching]).
7. **Run e2e tests against the production build.** Against the production build, not the dev server, for the reasons in [The Vite Model]. Only then remove Webpack.

### Criteria for staying on Webpack

An honest list of situations where migrating does not pay off:

- **You have home-grown plugins working with `compilation`.** The Webpack and Rollup models are not isomorphic, and the rewrite may be not laborious but impossible.
- **Module Federation is the architecture's foundation, not a detail.**
- **Dev and prod must be identical.** For example, when you cannot afford the "works in dev" class of bugs — in a medical or payments product where incidents are expensive.
- **The config is generated by a framework.** Angular CLI, Next.js and NX decide the bundler themselves; changing that behind the tool's back is a bad idea.
- **The problem was never the bundler.** If the build is slow because of a bloated graph, changing tools speeds up building junk.

And the middle option people often forget: **Rspack**. It gives native speed without rewriting the config, the loaders or most plugins. If the only reason to migrate is "Webpack is slow", that is usually a more rational path than moving to a different build model.

## Diagnosing a slow build

```txt
                     A slow build: what to measure and in what order
┌──────┬────────────────────────────────────┬────────────────────────────────────────────┐
│ step │ what to measure                    │ the typical finding                        │
├──────┼────────────────────────────────────┼────────────────────────────────────────────┤
│ 1    │ a cold build versus a rebuild      │ the cache is off or invalidated            │
├──────┼────────────────────────────────────┼────────────────────────────────────────────┤
│ 2    │ how many modules entered the graph │ tests, mocks, locales, a stray barrel      │
├──────┼────────────────────────────────────┼────────────────────────────────────────────┤
│ 3    │ time per build stage               │ minification and source maps               │
├──────┼────────────────────────────────────┼────────────────────────────────────────────┤
│ 4    │ transform time per file            │ Babel where SWC would do                   │
├──────┼────────────────────────────────────┼────────────────────────────────────────────┤
│ 5    │ the cost of resolution             │ a long extensions list, duplicate packages │
├──────┼────────────────────────────────────┼────────────────────────────────────────────┤
│ 6    │ core utilization during the build  │ one core out of eight                      │
└──────┴────────────────────────────────────┴────────────────────────────────────────────┘
          the rule: measure first, swap tools second. Changing the bundler on a
            project with a bloated graph speeds up building junk, not building
```

The order is chosen by the ratio of "likelihood of a finding" to "cost of checking".

**Step 1 — the cache.** Compare a cold build with a rebuild that changes nothing. If they are close, the cache is not working. Webpack's filesystem cache is **off by default in production** — enabled with `cache: { type: 'filesystem' }` ([The Webpack Core Model]). The second common case is a cache that exists but is invalidated every time: for instance, `buildDependencies` includes a file that changes on every run. In CI, separately verify that the cache directory survives between runs at all.

**Step 2 — graph size.** The most common finding of all: things reached the application build that had no business being there. Test files, mocks, every locale of a date library, an entire icon set via a barrel file. It is checked by bundle analysis ([Tree Shaking and Optimization]), and it usually yields the biggest win — because it reduces build time and output size at once.

**Step 3 — stages.** Where the time actually goes: the graph walk, transformation, minification, source map generation. Minification and full source maps are the two most expensive stages of a production build, and both are configurable.

```bash
# Webpack: statistics on time and modules
npx webpack --profile --json=stats.json

# Vite: a CPU profile of the build
npx vite build --profile

# Vite: a detailed per-stage log
DEBUG=vite:* npx vite build
```

**Step 4 — transformation.** If Babel is still in the project where SWC or a built-in transformer would suffice, that is a noticeable share of the time. The typical tell is `babel-loader` in the config when all Babel does is transpile TypeScript and JSX.

**Step 5 — resolution.** A long `resolve.extensions` list, dozens of aliases, duplicate packages — every "does this file exist" check costs a disk call, and there are millions of them ([The Module Graph and Resolution]).

**Step 6 — parallelism.** Watch core utilization during the build. One busy core out of eight on Webpack is the normal picture, and that is exactly what moving to a native bundler changes. But this is the **last** step, not the first: swapping tools while problems from steps 1–5 remain simply hides them.

Two additional settings give a quick win without structural changes:

```js
// Webpack: in dev, compile only what is actually requested
module.exports = { experiments: { lazyCompilation: true } };
```

```ts
// Vite: skip computing compressed sizes during the build — noticeable on large projects
export default defineConfig({ build: { reportCompressedSize: false } });
```

## Relation to other topics

```txt
[Why Bundlers Exist]                — the dev-versus-prod frame, which makes the
                                       Vite/Turbopack disagreement intelligible
[The Module Graph and Resolution]   — resolution, duplicate packages and the cost
                                       of extension probing
[The Webpack Core Model]            — the model Rspack copies, and the difference
                                       between a loader and a plugin
[Code Splitting and Long-Term
 Caching]                            — why a migration must compare chunk sizes,
                                       not just build times
[Tree Shaking and Optimization]     — bundle analysis as the main tool for
                                       diagnosing graph size
[The Vite Model]                    — when Vite is not the answer, and why e2e
                                       must run against the production build
[Dev Server and HMR]                — proxying, static assets and HMR after the move
NX course                            — Module Federation in depth: contracts,
                                       shared dependency versions, monorepos
Angular course                        — building through the CLI, which is best not
                                       worked around by hand
Next.js topic                         — Turbopack in practice
```

## Common interview traps

- **Lining up esbuild, SWC, Vite and Webpack as peers.** These are different layers: SWC is a transformer only, esbuild is a transformer and bundler but usually applied as a component, Vite is a tool on top of a bundler. "esbuild or Vite" is as ill-posed as "engine or car".

- **"Rust is faster, that is the whole secret."** Half the truth. Native code, parallelism and a shared AST make the same work faster; caching, lazy building and skipping the dev bundle **reduce the amount** of work. A strong answer separates the two groups and adds that parallelism is bounded by graph structure and that caching does nothing for a first build — including in CI.

- **Not knowing Rspack exists.** A very practical gap. When the only complaint about Webpack is speed, migrating to Vite means changing the build model, whereas Rspack gives the speed while keeping the config. A candidate who offers only Vite is showing a narrow option set.

- **"Turbopack is Vercel's Vite."** Architecturally they disagree: Turbopack bundles in dev too, because it holds that native ESM scales poorly to large applications. Plus an important practical detail: it supports webpack loaders but not webpack plugins.

- **Being unable to explain why Module Federation lives in the bundler.** The expected answer: only the bundler controls resolution, chunking and the chunk-loading runtime at the same time — and "this module arrives from outside" needs all three. Plus a mention of `shared` as the protection against several copies of React on one page.

- **Judging a migration by build time alone.** After the move, always compare chunk sizes: vendor grouping settings differ, and "ten times faster" combines easily with "300 KB heavier for the user".

- **Having no criterion for staying on Webpack.** An answer where migration is always justified reads as inexperience. Concrete stop factors are expected: home-grown plugins on `compilation`, Module Federation as a foundation, a requirement that dev equal prod, a framework-generated config.

- **Starting slow-build diagnosis by changing tools.** The right order is cache, graph size, stages, transformation, resolution, and only then parallelism. The most common real cause is that things sit in the graph which should not be there, and no bundler cures that.
