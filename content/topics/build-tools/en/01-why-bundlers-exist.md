# Why Bundlers Exist

## One sentence the whole topic grows out of

A bundler takes an entry point, walks the import graph from it, transforms every file it finds, and emits a set of assets the browser can download and run. Everything else — loaders, plugins, chunks, hashed filenames — is detail about how exactly four verbs get done: *walk*, *transform*, *combine*, *optimize*.

The productive way into this subject is not the config file but the question "which problem does this config line solve". Otherwise you get the familiar picture: someone can copy a working `webpack.config.js` but cannot explain why changing one line of source code made every user re-download two megabytes of vendor code.

## Three eras — as an explanation, not a timeline

History matters here for one reason only: each era solved the previous era's problem, and traces of all three are still sitting in your `node_modules`.

### Global scripts: tag order instead of a module system

```html
<script src="/js/jquery.js"></script>
<script src="/js/utils.js"></script>
<script src="/js/app.js"></script>
```

There are no modules — there is a shared `window` object and a loading order. That produces three chronic problems:

- **Collisions.** Two libraries declare `formatDate` — whichever loads last wins. The bug shows up not at load time but a month later, in somebody else's code.
- **Implicit dependencies.** The fact that `app.js` does not work without `utils.js` is written down nowhere. That knowledge lives in your head and in the order of the tags.
- **Manual ordering.** Swap two lines in the HTML and the application breaks.

The partial cure was the IIFE wrapper: hide the internals, expose one object.

```js
var Utils = (function () {
  function formatDate(d) { /* ... */ }
  return { formatDate: formatDate };   // internals hidden, one name on window
})();
```

It works, but it does not solve the main problem: dependencies are still not expressed in the code.

### CommonJS and AMD: modules arrived, but the browser knew nothing about them

Node.js brought `require`/`module.exports` — a synchronous lookup on disk. That is an excellent model on a server and an impossible one in a browser: there is no file system, and a synchronous network request would freeze the page. In parallel the browser got AMD (`define([...], factory)`), asynchronous by construction but verbose, and UMD, a wrapper trying to detect its environment and please everyone at once.

Here is the point that explains bundlers. `require('lodash')` cannot work in a browser **in principle** — there is no file system and no package lookup algorithm. And that is where the idea behind every modern bundler comes from:

> Let a tool walk the module graph ahead of time, on the developer's machine, and emit a single file the browser can simply run.

That is how browserify worked, and how the first versions of Webpack worked. "Collapse the graph into a file" is the original definition of a bundler.

### Native ESM: the browser finally got modules

```html
<script type="module" src="/src/main.js"></script>
```

`import`/`export` work in the browser with no tooling at all, and bare specifiers (`import { format } from 'date-fns'`) can be declared through an import map. Which raises the central question of this topic: if the browser handles modules on its own, what is the bundler still for? The answer comes below — but first, what a bundler actually does.

## The five jobs a bundler covers

```txt
                                   The five jobs a bundler exists for
┌──────────────────────────┬────────────────────────────────┬──────────────────────────────────────────┐
│ the job                  │ what the browser does alone    │ what the bundler adds                    │
├──────────────────────────┼────────────────────────────────┼──────────────────────────────────────────┤
│ find a module by name    │ URLs and relative paths only   │ node_modules, alias, exports fields      │
├──────────────────────────┼────────────────────────────────┼──────────────────────────────────────────┤
│ number of requests       │ one request per module         │ the graph collapsed into a few files     │
├──────────────────────────┼────────────────────────────────┼──────────────────────────────────────────┤
│ TS, JSX, new syntax      │ does not understand it at all  │ transformed into supported JS            │
├──────────────────────────┼────────────────────────────────┼──────────────────────────────────────────┤
│ CSS, images, fonts       │ separate tags and manual paths │ an asset becomes a node of the graph     │
├──────────────────────────┼────────────────────────────────┼──────────────────────────────────────────┤
│ size and caching in prod │ nothing                        │ minification, tree shaking, hashed names │
└──────────────────────────┴────────────────────────────────┴──────────────────────────────────────────┘
                          the first four jobs matter both in dev and in prod;
                the fifth belongs to the prod build, and it is what makes the build slow
```

**1. Module resolution.** The browser understands URLs only: `./utils.js`, `/src/app.js`, `https://…`. The string `'date-fns'` is not a path to it — it is a `Failed to resolve module specifier` error. A bundler knows the lookup algorithm: walk `node_modules` up the tree, read `package.json`, pick the right file out of the `exports` field, apply configured aliases. Import maps cover part of this in the browser, but nobody is going to list hundreds of transitive dependencies by hand — and generating an import map automatically requires a tool that already walked the graph. The mechanics are in [The Module Graph and Resolution].

**2. Cutting the number of requests.** One module, one HTTP request. A typical application has thousands of modules, and that is not an abstraction: `lodash-es` alone is roughly 600 separate files.

**3. Transformation.** TypeScript, JSX and syntax that older browsers do not support simply do not exist as far as the browser is concerned. Something has to turn them into runnable JS, and the cheapest place to do it is along the way — during the same graph walk.

**4. Non-JS assets.** The line `import './Button.css'` has no meaning in the ESM specification: the language's module system knows nothing about styles. Bundlers invented that convention, and with it the ability to treat a stylesheet, an image or an SVG as a node of the same graph as your code. A practical consequence: an unused component drops its styles from the bundle too.

**5. Optimizing for production.** Minification, dead code removal, splitting into chunks, hashed filenames for long-term caching. All of it requires seeing the **whole** graph — optimizing one file in isolation from the rest is meaningless.

## The running example: the `shop-admin` panel

One application runs through the entire topic — a React SPA with three routes, only one of which is heavy:

```txt
shop-admin/
├─ index.html
├─ package.json
└─ src/
   ├─ main.tsx              — entry point
   ├─ App.tsx               — layout and router
   ├─ routes/
   │  ├─ Orders.tsx         — orders table, light
   │  ├─ Analytics.tsx      — charts: chart-lib + date-fns  ← the heavy route
   │  └─ Settings.tsx       — a form, light
   ├─ lib/api.ts            — a fetch wrapper
   └─ ui/
      ├─ Button.tsx
      └─ Button.css
```

```tsx
// src/main.tsx — the graph walk starts here
import { createRoot } from 'react-dom/client';
import { App } from './App';
import './styles/global.css';

createRoot(document.getElementById('root')!).render(<App />);
```

```tsx
// src/routes/Analytics.tsx — the one "heavy" route
import { LineChart } from 'chart-lib';
import { format } from 'date-fns';
import { fetchMetrics } from '../lib/api';

export function Analytics() {
  const points = fetchMetrics();
  return <LineChart data={points} formatX={(d: Date) => format(d, 'dd.MM')} />;
}
```

This example carries code splitting ([Code Splitting and Long-Term Caching]), tree shaking and bundle analysis ([Tree Shaking and Optimization]) and the dev/prod differences ([The Vite Model]). The question worth holding in mind from the start: **why should a user who opened `/orders` download `chart-lib` at all?**

## If browsers speak ESM and HTTP/2 exists, why haven't bundlers disappeared?

This is the central question of the topic and a very common interview question. The answer has three independent parts.

### The request waterfall

```txt
        NO BUNDLING: native ESM                           BUNDLED
┌─────────────────────────────────────┐    ┌────────────────────────────────────┐
│ round    what the browser requests  │    │ round    what the browser requests │
│                                     │    │                                    │
│ round 1   index.html                │    │ round 1   index.html               │
│ round 2   main.tsx                  │    │ round 2   index-a1b2c3.js          │
│ round 3   App.tsx, router.ts        │    │           vendor-d4e5f6.js         │
│ round 4   Analytics.tsx, api.ts     │    │           index-9f8e7d.css         │
│ round 5   chart-lib/index.js        │    └────────────────────────────────────┘
│ round 6   ≈600 files of chart-lib/* │    graph depth does not change the round count:
└─────────────────────────────────────┘    the bundler walked the graph ahead of time
   the browser learns about level N+1
    only once it has parsed level N
```

HTTP/2 did remove the old limit of six parallel connections per host: a hundred files on the same level are multiplexed and arrive almost together. What HTTP/2 does not remove is **sequence**: the browser cannot know that `Analytics.tsx` imports `chart-lib` until it has downloaded and parsed `Analytics.tsx` itself. The cost is not "how many files" but "how many levels deep", multiplied by network latency. On a fast local connection the difference is invisible; on a mobile network with 150 ms of latency, six rounds turn into nearly a second before the first render.

The partial cure is `<link rel="modulepreload">`: tell the browser up front which modules it will need. But producing that list means walking the graph beforehand — which is exactly what a bundler does. Preload hints and their cost are covered in [Code Splitting and Long-Term Caching].

### Packages are not built to be served as-is

Even setting the waterfall aside: some packages in `node_modules` are still published as CommonJS only, and the browser cannot execute that at all. Some ship as hundreds of tiny files. Some use bare specifiers internally, each of which needs resolving too. This is exactly why Vite — a tool built ideologically around native ESM in dev — still pre-bundles dependencies before the dev server starts; details in [The Vite Model].

### Production optimizations need the whole graph

Minification, removing unused code, merging modules, stable hashes for long-lived caching — none of these work on a single file. "Can this function be deleted?" is a question about the entire graph at once.

### When going build-less genuinely works

The "no-build" niche is real and not heresy: a landing page, a demo, an internal tool with two screens, a docs page with a hundred lines of script. If you have dozens of modules rather than thousands, and nothing from `node_modules` ships to the browser, a bundler adds more complexity than value. The strong interview answer is "it depends on graph depth and on whether you need production optimizations", not "you always need a bundler".

## The frame for the whole topic: dev mode and the prod build are different jobs

```txt
             The frame for the whole topic: dev and prod are different jobs
┌────────────────────┬───────────────────────────┬─────────────────────────────────────┐
│                    │ dev mode                  │ prod build                          │
├────────────────────┼───────────────────────────┼─────────────────────────────────────┤
│ what matters       │ feedback speed            │ size, caching, load time            │
├────────────────────┼───────────────────────────┼─────────────────────────────────────┤
│ how often          │ on every file save        │ once before a deploy                │
├────────────────────┼───────────────────────────┼─────────────────────────────────────┤
│ acceptable time    │ tens of milliseconds      │ minutes                             │
├────────────────────┼───────────────────────────┼─────────────────────────────────────┤
│ minification       │ off                       │ on                                  │
├────────────────────┼───────────────────────────┼─────────────────────────────────────┤
│ tree shaking       │ not needed                │ mandatory                           │
├────────────────────┼───────────────────────────┼─────────────────────────────────────┤
│ source maps        │ detailed and cheap        │ a trade-off on accuracy             │
├────────────────────┼───────────────────────────┼─────────────────────────────────────┤
│ what actually runs │ code close to your source │ code transformed beyond recognition │
└────────────────────┴───────────────────────────┴─────────────────────────────────────┘
                Webpack describes both modes with a single build model;
           Vite uses two different ones — hence both its speed and its traps
```

This table is the frame the topic keeps returning to. The two main tools answer it differently:

- **Webpack** uses one model for both modes: build the whole graph, then run the dev server on top of that same build (with optimizations off and hot reloading added). The upside is that dev and prod behave alike. The downside is that cold-start time grows with the project. The model is covered in [The Webpack Core Model].
- **Vite** uses two different models: in dev the browser gets native ESM and files are transformed on request, in prod a full build runs. The upside is that startup barely depends on project size. The downside is a whole class of "works in dev, broken in prod" bugs. Covered in [The Vite Model] and [Dev Server and HMR].

**On versions.** At the time of writing, Webpack 5.x is the current line — actively developed, with a published roadmap toward a sixth major version bringing built-in CSS, HTML and TypeScript support in place of the familiar plugins and loaders. Vite has reached version 8, where both the production build and dependency pre-bundling run on a single bundler, Rolldown (a Rust port of Rollup), which replaced the earlier esbuild + Rollup pairing. This corner of the ecosystem moves faster than articles age, so the status of any specific tool is worth checking against the primary sources — `webpack.js.org`, `vite.dev`, `rolldown.rs` — rather than against someone's year-old comparison. The full ecosystem map is in [Ecosystem and Choosing a Tool].

## Relation to other topics

```txt
[The Module Graph and Resolution]   — how the graph is built and by which
                                       algorithm a module name is resolved
[The Webpack Core Model]            — module → chunk → asset, loaders, plugins
[Code Splitting and Long-Term
 Caching]                            — why a /orders user should not download
                                       chart-lib, and how to arrange that
[Tree Shaking and Optimization]     — what gets dropped from the bundle and why
[The Vite Model]                    — the dev/prod asymmetry and its price
[Dev Server and HMR]                — what the feedback loop looks like
[Ecosystem and Choosing a Tool]     — esbuild, SWC, Rollup, Rolldown, Rspack,
                                       Turbopack, Parcel: whose niche is whose
Node.js topic, the CommonJS vs ESM chapter
                                     — the module systems themselves, require vs
                                       import, interop: only referenced here
```

## Common interview traps

- **"A bundler exists to glue files into one"** — that describes browserify circa 2013. Gluing is one of five jobs, and in a modern application split by routes "one file" is the opposite of the goal. A middle+ answer lists resolution, transformation, non-JS assets and production optimizations separately from concatenation.

- **"Browsers speak ESM, so bundlers are obsolete"** — a half-truth interviewers happily pull on. The follow-up is always the same: *"how many request rounds does a graph six levels deep cost you?"* Native ESM removes the need to concatenate for syntax reasons; it does not remove the waterfall, the CommonJS packages in `node_modules`, or production optimizations.

- **"HTTP/2 solved the many-requests problem"** — HTTP/2 solved *parallelism* within one level, not the *sequence* of levels. Confusing the two is a very common sign of surface-level knowledge.

- **Not separating dev from prod** — the most valuable dividing line in this topic. A candidate who says "Vite is fast because it is written in Rust" has not understood the mechanics; a candidate who says "in dev it does not build the whole graph, it serves modules on request, and pays for that with dev/prod behaviour differences" has. See [The Vite Model].

- **"A bundler means webpack"** — Webpack set the vocabulary everyone uses (module, chunk, loader, plugin), but it is one tool among a dozen. An answer that reduces every build question to a Webpack config reads as "I can copy someone else's config".

- **Confident claims about "what Vite runs on right now"** — this part of the ecosystem changes every few months. A time-bound formulation lands far better: "in the version I worked with, production was built by X; the current state is worth checking in the docs". A confidently stated stale detail costs more than an honest "I would need to check".
