# Build Tools: Interview Questions (Middle → Senior)

## How to use this cheat sheet

Every answer below is the **short** version of what the articles in this section cover in depth. Build tooling works in such a way that almost any question is a lead-in to a follow-up: "why?", "what if?", "how did you diagnose that?".

So after each group there is a **"Typical follow-ups"** section showing where an interviewer usually goes next. If a follow-up catches you off guard, that is a signal to return to the matching article.

One trait specific to this topic: **the ecosystem changes faster than articles age.** On versions and how to talk about them honestly, see the very end of this file.

## Group 1: why a bundler, and the dev/prod frame

**1. Do we even need a bundler now that browsers speak ESM?**

Yes, but not for the reason people usually give. ESM is the ECMAScript module system that browsers understand with no build step. It removes the need to concatenate code for syntax reasons, but three things stay:

- **The request waterfall.** The browser learns a file's imports only after downloading and parsing that file, so the cost is graph depth multiplied by network latency.
- **The packages in `node_modules`.** Some are published as CommonJS only, some as hundreds of tiny files.
- **Production optimizations.** Tree shaking, minification, hashed names — all of them require seeing the whole graph.

That said, the "no-build" niche is real: a landing page, a demo, an internal tool with two screens. See [Why Bundlers Exist](./01-why-bundlers-exist.md).

**2. What problems does a bundler solve?**

Five, and it helps to name them separately:

- **Module resolution** — the browser cannot search `node_modules`.
- **Reducing the request count.**
- **Transformation** — TypeScript, JSX (HTML-like markup written inside JavaScript), new syntax.
- **Non-JS assets** — `import './Button.css'` is a bundler convention, not part of the ESM spec.
- **Production optimization.**

The first four matter in both dev and prod. The fifth belongs to the production build, and it is what makes builds slow.

**3. Why are dev mode and the production build different problems?**

Because they optimize different things. Dev optimizes feedback speed on every file save, where tens of milliseconds is acceptable. Production optimizes size, caching and load time, where minutes are acceptable.

Hence two different approaches: Webpack describes both modes with one build model, Vite with two different ones. With the first, dev and prod behave alike, but startup grows with the project. With the second, startup barely depends on size, but a "works in dev, broken in prod" class of bugs appears.

See [Why Bundlers Exist](./01-why-bundlers-exist.md) and [The Vite Model](./06-vite-model.md).

## Typical follow-ups (group 1)

```txt
"How many request rounds does a graph six levels deep cost,
and why doesn't HTTP/2 save you?" → HTTP/2 solved parallelism
WITHIN one level, not the sequence of levels

"Fine, but doesn't modulepreload solve the waterfall?" → it
does, but producing that list requires walking the graph
first — i.e. doing the bundler's job

"On what project would you skip the build?" → they want
criteria (graph depth, whether production optimizations are
needed, whether node_modules ships to the browser), not
"you always need a bundler"
```

## Group 2: the module graph and resolution

**4. How does a bundler build the graph, and what is a bare specifier?**

From the entry point: read a file, find its imports, resolve each import to a path on disk. Then read what was found and repeat, until the queue empties. The result is a graph, not a tree: a module is processed once no matter how many files import it.

A bare specifier is an import by package name (`'date-fns'`) rather than by path. The browser only understands relative paths, absolute paths and URLs. So a bare specifier exists purely because something performs resolution: walking `node_modules` up the tree, reading `package.json`, applying aliases.

See [The Module Graph and Resolution](./02-module-graph-and-resolution.md).

**5. Why does one package serve different files to Node, to a bundler and to a browser?**

Conditional exports. The `exports` field in `package.json` lists branches by condition: `import`, `require`, `browser`, `node`, `development`/`production`. Each consumer applies its own set of conditions:

- Webpack with `target: 'web'` uses something like `['webpack', 'production', 'browser']`.
- Vite defaults to `['module', 'browser', 'development|production']`.
- Node knows neither `webpack` nor `module`.

Plus the historical fields `main` (the CommonJS entry), `module` (the ESM entry, the precondition for tree shaking) and `browser`.

This is where the "works in Node tests, breaks in the browser" family of bugs comes from. It is not an implementation mismatch but the mechanism's whole purpose. An important detail: `exports` also **seals off** every path it does not list. A minor dependency bump can therefore break an import from a package's internal folder.

**6. Two copies of React ended up in the bundle. How, and what do you do?**

To the bundler, two paths to `react` are two distinct graph nodes, and it honestly includes both. The causes:

- Incompatible version ranges, so the package manager installed a nested copy.
- Symlinks in a monorepo.
- The dual package hazard: the package resolves as CommonJS in one place and as ESM in another.

The build succeeds, so the symptoms show up at runtime. You see `Invalid hook call`, an empty context in a child component, a store behaving like two stores.

Diagnosis: `npm ls react` (or `pnpm why react`), then bundle analysis to see whether both copies reached the output. Fix from the gentlest step upward. Align versions and move the package into `peerDependencies` first, and only then reach for `resolve.dedupe` in Vite or a forced alias in Webpack.

See [The Module Graph and Resolution](./02-module-graph-and-resolution.md).

**7. What happens when a CJS package enters the graph?**

The bundler wraps it. CJS is CommonJS, the module format Node used long before browsers had one of their own. The package body becomes a function with local `module`/`exports`, called on first access, with the result cached.

Three consequences follow:

- **Named imports from a CJS package are a heuristic, not a guarantee.** They work while the bundler can statically recognize `exports.pick = ...`. If exports are assembled dynamically, you get `does not provide an export named`.
- **A default import works thanks to an interop shim.** But `import * as x` gives a namespace object that cannot be called.
- **Tree shaking and module merging are impossible** for such a node in principle.

The module systems themselves are in the Node.js topic, in the CommonJS vs ESM chapter.

## Typical follow-ups (group 2)

```txt
"I configured an alias, the editor is happy, the build fails
with Module not found — why?" → a bundler alias and paths in
tsconfig.json are different mechanisms; TypeScript does not
rewrite imports, and the bundler does not read tsconfig by
default

"Module not found: Can't resolve 'crypto' — what does that
mean?" → a node module inside browser code; Webpack 4
polyfilled it automatically, Webpack 5 stopped. The right
question is why the browser wants crypto, not which polyfill
to substitute

"The app fails with 'the store is not a singleton' — where do
you look?" → either two copies of the package or the dual
package hazard: one module reached the bundle twice in
different formats
```

## Group 3: the Webpack model

**8. What is the difference between module, chunk and asset?**

Three distinct levels, and confusing them makes it impossible even to state a problem.

- **A module** is one file after the loaders ran. Not only JS: a CSS or SVG (scalable vector graphics) file counts too, because a loader made it importable.
- **A chunk** is a unit of the bundler's decision "these modules ship together". It arises from entry points, from every `import()` and from `splitChunks` rules.
- **An asset** is a file actually written into `dist/`.

One chunk usually produces several assets (JS, extracted CSS, a source map), and one module can land in several chunks.

The practical value shows in how you phrase a problem. "My bundle is big" is a question with no answer. "Why did `chart-lib` end up in the `main` chunk rather than `analytics`" has one.

See [The Webpack Core Model](./03-webpack-core-model.md).

**9. How does a loader fundamentally differ from a plugin?**

By its unit of work.

- **A loader** is a function "file contents → file contents", applied to every file matching `test`. It knows nothing about other modules or the resulting chunks.
- **A plugin** attaches to lifecycle hooks and reaches the whole build through `compiler` and `compilation`. It can add and modify assets, interfere with chunking, fail the build.

The test is short. **If the job can be done by looking at one file, it is a loader. If it needs to know something about the build as a whole, it is a plugin.**

Transpiling TypeScript is a loader. Generating an `index.html` that links to hashed files is a plugin, because asset names are only known at the end of the build. Vite has no separate "loader" concept: both are hooks of one plugin (`transform` versus the rest).

**10. Why are loaders applied right to left?**

Because a chain is function composition: `use: [a, b, c]` means `a(b(c(file)))`, so the innermost call runs first. The same principle as `compose()`.

That is why in the CSS chain `['style-loader', 'css-loader', 'sass-loader']` the first to run is `sass-loader` (`.scss` → `.css`) and the last is `style-loader`. "Historical reasons" is a weak answer. An additional requirement: the last loader applied must return valid JavaScript, because the graph is made of JS nodes.

**11. What does `mode: 'production'` actually do?**

It does not "turn on minification" — it switches about a dozen defaults. The key ones:

- `optimization.minimize: true`.
- `moduleIds`/`chunkIds` from `'named'` to `'deterministic'`, which directly affects long-term cache stability.
- `usedExports` and `concatenateModules`: tree-shaking marks and module merging.
- `realContentHash: true` and `devtool: false`.
- The `process.env.NODE_ENV` substitution through `DefinePlugin`.

Worth knowing separately: `cache` is **off** by default in production. The filesystem cache is opted into via `cache: { type: 'filesystem' }`.

## Typical follow-ups (group 3)

```txt
"How do you speed up rebuilds in Webpack?" → the built-in
cache: { type: 'filesystem' } with buildDependencies.
Suggesting cache-loader or hard-source-webpack-plugin is a
marker of Webpack 4-era knowledge

"Your config has file-loader and url-loader — why?" → since
Webpack 5 those are Asset Modules: asset/resource,
asset/inline, asset/source

"The Vite config is shorter — so Vite is better?" → comparing
the wrong things: a short config means typical transforms are
built in, not that there is less work. The price is less
control in atypical cases
```

## Group 4: code splitting and long-term caching

**12. What creates a separate chunk?**

Only a dynamic `import()`. A static `import` is an edge inside a chunk; `import()` is the one construct the bundler treats as a graph boundary.

An important consequence: the bundler does **not** extract a library into its own chunk "because it is big". It cuts the graph exactly where you put a dynamic import.

Two more details. A conditional static import creates no boundary: it is impossible in ESM, and a `require()` inside an `if` is not analysable. And a module reachable from two lazy chunks lands in both — which is what `splitChunks` fixes.

See [Code Splitting and Long-Term Caching](./04-code-splitting-and-caching.md).

**13. I configured `cacheGroups` and `react` is still in the entry chunk. Why?**

Because `splitChunks.chunks` defaults to `'async'` — entry chunks are not split at all, only lazy ones are. You need `chunks: 'all'`. One of the most practical questions in this topic: it separates people who read the docs from people who copied a config.

**14. We changed one line and the user re-downloaded the whole vendor chunk. Why?**

Three independent causes, and a full answer names all three:

| the cause | what actually happens | the cure |
|---|---|---|
| unstable module ids | ids handed out in graph-walk order shift when you add a file, changing the vendor chunk's contents | `moduleIds: 'deterministic'` |
| the runtime inside the entry chunk | it holds the "chunk id → hashed file name" map, so it changes on any hash change | `runtimeChunk: 'single'` |
| the hash computed before minification | changes the minifier would erase anyway still change the file name | `realContentHash` |

Two notes on the first row. Module ids end up inside *other* chunks, which is why a shifted id invalidates a chunk that did not change. And `moduleIds: 'deterministic'` is already the default in production: older configs used `HashedModuleIdsPlugin` and `NamedModulesPlugin` for the same purpose, and both are now obsolete.

"You need contenthash" is an incomplete answer. It was already there, or nobody would have noticed the problem.

**15. When is splitting the bundle more harmful than helpful?**

When the cost of splitting outweighs the caching gain. Three things decide it:

| what to look at | when splitting pays | when it does not |
|---|---|---|
| release frequency | several releases a week, so most assets survive | quarterly, so users arrive cold anyway |
| the first screen's share | a small share, the rest stays lazy | 80% of the code, so there is nothing to split |
| your users' network | fast and stable | mobile, where each waterfall level costs hundreds of milliseconds |

On a mobile network small dependent chunks also cost more than one medium chunk, because you pay for the extra request rounds.

Plus the argument people forget most often: **compression**. Gzip and brotli build their dictionary within a single file. So ten files of 20 kilobytes (KB) each compress noticeably worse than one 200 KB file. It is no accident that Webpack's `minSize` defaults to 20 KB.

**16. What does a user see if you deploy a new release while their tab is open?**

A lazy route that refuses to open. `import()` returns a promise, so it can reject. The old files with the previous hashes are gone from the CDN (content delivery network), and navigating to a lazy route fails. The message is `ChunkLoadError: Loading chunk 5 failed` in Webpack, or `Failed to fetch dynamically imported module` in Vite.

The fix takes both sides:

- **In the application** — catch the error, retry once, and reload the page on a second failure.
- **At deploy time** — do not delete the previous release's assets immediately, keep several versions.

This question cleanly separates people who configured a production build from people who read about one.

## Typical follow-ups (group 4)

```txt
"Why not put all dependencies into one big vendor chunk — it
would be cached, right?" → the reasoning is backwards: the
bigger the chunk, the likelier the next release invalidates
it. Group by change frequency: the framework separate from
everything else

"Difference between [hash], [chunkhash] and [contenthash]?" →
a hash of the whole build / a per-chunk hash before final
processing / a hash of a specific asset's contents

"Let's prefetch every route — bad?" → that means downloading
the whole application, just slightly later. Bandwidth and the
priority queue are finite

"Where do you draw the splitting boundary?" → where the user
is prepared to wait (a route navigation), and not where they
are merely scrolling
```

## Group 5: tree shaking and optimization

**17. Tree shaking did not work — the whole library is in the bundle. Where do you look?**

First, fix the framing: tree shaking is not a cleanup but a **proof**. The bundler marks unused exports (`usedExports`) and the minifier removes them. Without minification there is no tree shaking.

The reasons a proof failed fall into two groups.

**What entered the graph:**

- The dependency is published as CommonJS only, and `require(x)[y]` is computed at runtime, so it is unprovable.
- A transpiler rewrote your code into CommonJS before the bundler saw it: `"module": "commonjs"` in `tsconfig.json`, or Babel without `modules: false`.

**What the bundler could not prove:**

- No `sideEffects` flag.
- The whole package imported instead of named exports.
- A top-level side effect in the module.
- An import going through a barrel file.

See [Tree Shaking and Optimization](./05-tree-shaking-and-optimization.md).

**18. What is `sideEffects` and how does it differ from `usedExports`?**

By scope. The `usedExports` flag works inside a module: it drops individual unused exports. The `sideEffects: false` field in `package.json` is a promise: "importing any of my files does nothing". That promise lets a **module and its whole subtree** be skipped entirely. The second is more effective, and the Webpack docs say so in plain language.

Two things worth extra credit:

- It is a promise verified by reality rather than by the bundler. Set it on a package that does have effects, and the build gets smaller and breaks.
- CSS imports must be listed in the array (`"sideEffects": ["*.css"]`). Otherwise styles can vanish from the production build while dev works fine — the classic "styles in dev, no styles in prod" bug.

**19. What does a minifier do beyond stripping whitespace?**

The main win is not compressing text but removing unreachable branches. The chain is worth tracing end to end:

1. In your source: `if (process.env.NODE_ENV !== 'production')`.
2. After the bundler substitutes: `if ('production' !== 'production')`.
3. After constant folding: `if (false)`.
4. After dead code removal: nothing at all.

That is how React loses whole warning subsystems in production. Beyond that: shortening local and export names, inlining single-use calls, constant folding.

Adjacent to this question is **scope hoisting** (`concatenateModules`) — merging modules into one scope. It gives the minifier more to work with, because former "public exports" become ordinary local variables. ESM only.

**20. Which `devtool` (or `build.sourcemap`) do you use in production?**

Not `'source-map'` without caveats. It appends a comment pointing at the `.map` file. If that file sits next to the bundle on a CDN, the whole application source is available to anyone.

The right options:

- **`hidden-source-map`** — the map is produced and uploaded to an error tracker such as Sentry, with no reference in the bundle.
- **`nosources-source-map`** — the map is public but carries no source text, so stack traces read fine while the code stays hidden.
- **`false`** — when you do not need error reports at all.

In dev the priority differs: rebuild speed, hence the `eval` variants. The name `eval-cheap-module-source-map` decodes as "via eval, line-only mappings, loader maps honoured".

## Typical follow-ups (group 5)

```txt
"There is 300 KB of moment in your bundle — what do you do?"
→ not "configure tree shaking": moment is written in CJS and
loads locales dynamically, so you swap the dependency for a
modular one (date-fns, dayjs)

"How will you find WHAT takes up the space?" → a bundle map
plus the mandatory third step: who exactly imports that
module (reasons in stats.json, the visualizer report).
Without it, optimization becomes guesswork

"Which number do you decide by?" → the compressed size:
200 KB in the report may be 55 KB after brotli

"Why is an unused import still in the bundle?" → three
distinct cases: top-level side effects, an import for its
effect (polyfills, CSS), and import type, which always
disappears
```

## Group 6: Vite, HMR (hot module replacement), ecosystem, migration

**21. Why is Vite fast in dev, and what does it pay for that?**

Not "because it is written in Rust" — the most common wrong answer. The reason is a **change of problem**. In dev Vite builds no graph and no bundle. It acts as a server with a transformer. It serves native ESM to the browser with imports rewritten on the fly, and transforms each file on request.

The work is proportional to the files needed for the open screen, not to project size. A five-thousand-module project starts about as fast as a five-hundred-module one.

It pays with two things:

- A large number of dev requests.
- More importantly, the fact that **dev and prod run different code**, because production is built fully: tree shaking, chunking, minification.

See [The Vite Model](./06-vite-model.md).

**22. Why does Vite pre-bundle dependencies if it is all about native ESM?**

Two reasons, both practical:

- **CommonJS interop.** A large share of `node_modules` is still published as CommonJS, and the browser cannot execute `module.exports`. Pre-bundling turns such a dependency into ESM with proper named exports.
- **Request count.** A package like `lodash-es` is hundreds of tiny files, and serving them one by one reproduces the very waterfall bundlers exist to avoid.

The result is cached in `node_modules/.vite` and invalidated by the lockfile, patches, config and `NODE_ENV`; force it with `--force`. The `new dependency optimized, reloading` message signals a dependency discovered late, worth listing in `optimizeDeps.include`.

**23. "Works in dev, broken in prod" — name the causes.**

They share one root: dev and prod run different code, and dev verifies less than it appears to.

| symptom | cause | how to catch it early |
|---|---|---|
| a blank screen in prod | a CommonJS dependency survived on pre-bundling | a prod build on every pull request |
| the styles disappeared | `sideEffects: false` plus tree shaking | open `vite preview` locally |
| `process is not defined` | `process` is a Node API, absent in a browser | move to `import.meta.env` |
| a different init order | module merging reorders modules, so a cycle harmless in dev breaks | remove cycles from the graph |
| type errors reached prod | Vite does not type-check at all, it strips types | `tsc --noEmit` as a separate build step |
| an asset was not found | the path was assembled as a string | `new URL(..., import.meta.url)` |

One practical conclusion. The production build must run in CI (continuous integration) on every pull request, and its output is worth opening locally before a release.

**24. A full page reload happens instead of HMR. And separately: why is component state lost?**

Two different symptoms with different causes, and telling them apart is half the answer.

*A full reload* means the update **bubbled up to the entry point** without finding a boundary.

The mechanism: a module can declare `accept`, meaning "I know how to take my new version". If the changed module has none, the update is handed to its importer, then to that importer's importer, and so on. Reaching the root without a boundary, the runtime reloads the page. So "HMR does not work" almost always means "no boundary was found".

*State lost without a reload* is the Fast Refresh rules. It identifies a component by name, and the rules are mechanical:

| what is in the file | what happens | why |
|---|---|---|
| `function Button() { … }` | state is preserved | the component is found by name |
| `export default () => …` | state is lost | an anonymous function is unrecognizable |
| `function example() { … }` | state is lost | the name is not PascalCase |
| `class Button extends …` | state is reset | classes are not supported |
| a hook added or removed | state is reset | the hook order changed |
| a non-component export | the update bubbles up | the file is no longer a boundary |

That last row is the most common and least obvious cause.

See [Dev Server and HMR](./07-dev-server-and-hmr.md).

**25. What breaks when migrating from Webpack to Vite, and when should you stay on Webpack?**

What breaks is almost everything relying on Node inside browser code:

- `require` in your own code, and CommonJS dependencies.
- Node polyfills: Webpack 4 substituted them automatically, Vite does not at all.
- `process.env.*`, which becomes `import.meta.env` with the `VITE_` prefix.
- `require.context`, which becomes `import.meta.glob`.
- Custom loaders, which become a plugin with a `transform` hook.
- Asset paths assembled as strings, and Module Federation configuration.

The order of work. Install Vite alongside without removing Webpack, then move the entry into `index.html`. Next: environment variables, `require` and polyfills, the dev server with proxying. Then comes the step people skip most often — **build for production and compare chunk sizes**, or you get "ten times faster but 300 KB heavier". Run end-to-end tests against the production build, and only then remove Webpack.

Stay on Webpack if:

- You have home-grown plugins working with `compilation`. The Webpack and Rollup models do not map onto one another, and the rewrite may be impossible.
- Module Federation is the architecture's foundation rather than a detail.
- Dev and prod must be identical.
- The config is generated by a framework.

And separately — **Rspack** as the forgotten middle option: native speed without rewriting the config, the loaders or most plugins. If the only complaint about Webpack is speed, that is usually more rational than changing build models.

See [Ecosystem and Choosing a Tool](./08-ecosystem-and-choosing.md).

## Typical follow-ups (group 6)

```txt
"Is Vite faster than Webpack in production too?" → that is a
comparison of bundlers rather than models: there the win
comes from native code and parallelism, not from skipping the
build. And parallelism is bounded by graph structure

"esbuild or Vite — which do you pick?" → the question is
not well formed: SWC is a transformer only, esbuild is a
transformer and bundler usually applied as a component, Vite
is a tool on top of a bundler. Different layers

"Is Turbopack just Vercel's Vite?" → architecturally they
disagree: Turbopack bundles in dev too, holding that native
ESM scales poorly to large applications. And it supports
webpack loaders but not webpack plugins

"Why does Module Federation live at bundler level?" → only
the bundler controls resolution, chunking and the
chunk-loading runtime at once — and "this module arrives from
outside" needs all three. Plus shared as protection against
several copies of React on one page

"The build takes eight minutes — where do you start?" → in
order: the cache (cold versus rebuild), graph size (did tests
and locales get in), stages (minification, source maps),
transformation (Babel instead of SWC), resolution, and only
then parallelism. Swapping the bundler is the last step

"After ten edits the request fires ten times — why?" → a
missing dispose: previous versions of the module left timers
and subscriptions behind
```

## A note on versions

This is one of the few topics where a confidently stated detail can count against you. Over the last couple of years everything moved:

- what Vite builds production with, and what it pre-bundles dependencies with;
- which minifier it defaults to;
- what the chunking options are called;
- which bundler is the default in Next.js;
- what shape `devServer.proxy` takes;
- what is migrating from plugins into Webpack's core.

So the strong interview phrasing is this: **"in the version I worked with, tool X did that. The current state is worth checking against the docs"**. Name where to check: `webpack.js.org`, `vite.dev`, `rolldown.rs`, `rspack.rs`. That reads as experience, not ignorance.

A confidently delivered stale detail does the opposite. Say "Vite uses esbuild for dev and Rollup for production", and you reveal exactly when you last opened the documentation.

What does **not** go stale and is worth knowing solidly:

- the request waterfall;
- how the graph and resolution work;
- conditional exports;
- the module/chunk/asset distinction, and the loader/plugin distinction;
- the mechanics of tree shaking and the minifier's role;
- the causes of cache invalidation;
- the `accept` boundary and update bubbling;
- the dev/prod asymmetry.

That is the level at which questions actually separate candidates. Specific option names take a minute to look up.

## Relation to other topics

- [Why Bundlers Exist](./01-why-bundlers-exist.md) — group 1.
- [The Module Graph and Resolution](./02-module-graph-and-resolution.md) — group 2.
- [The Webpack Core Model](./03-webpack-core-model.md) — group 3.
- [Code Splitting and Long-Term Caching](./04-code-splitting-and-caching.md) — group 4.
- [Tree Shaking and Optimization](./05-tree-shaking-and-optimization.md) — group 5.
- [The Vite Model](./06-vite-model.md) — questions 21–23.
- [Dev Server and HMR](./07-dev-server-and-hmr.md) — question 24.
- [Ecosystem and Choosing a Tool](./08-ecosystem-and-choosing.md) — question 25 and the group 6 follow-ups.
- **Node.js topic**, the CommonJS vs ESM chapter — the module systems themselves.
- **Web Performance topic** — what to do about size next.
- **Nx course** — Module Federation in depth.
- **Angular course** — building through the Angular command-line tool.
