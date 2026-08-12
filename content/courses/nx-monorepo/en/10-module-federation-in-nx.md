# Module Federation in Nx: host, remotes and serve

## Theory

### What Nx adds on top of raw Module Federation

Building a federation on raw webpack means hand-writing ModuleFederationPlugin configs for both sides, reconciling shared lists, ports, URLs and dev-server orchestration. Nx wraps all of it into three things:

- **Generators** `@nx/react:host` and `@nx/react:remote`: they create the apps with the wiring already correct — the bootstrap pattern, configs, routing and mutual references.
- **`module-federation.config.ts`** — a declarative layer over the bundler: you describe the *what* (name, remotes, exposes), and the Nx plugin expands it into a full ModuleFederationPlugin config, including a default shared setup (all package.json dependencies are shared automatically, react as a singleton; fine-tuning — chapter 11).
- **Serve orchestration**: `nx serve shell` brings up the remotes by itself — the central topic below.

> **Versions.** The generators offer `--bundler=rspack` (the Rust implementation of the webpack API, several times faster; the default in recent Nx) or `webpack` — the configs are semantically identical. Under the hood, new versions use Module Federation 2.0 (`@module-federation/enhanced`) and the `@nx/module-federation` package; older repos use `withModuleFederation` from `@nx/react/module-federation` over webpack — the files look different, the roles are the same.

### module-federation.config.ts: the two sides of the contract

```ts
// apps/shell/module-federation.config.ts — the HOST
const config = {
  name: 'shell',
  remotes: ['catalog', 'checkout'],   // whom I can load
};

// apps/catalog/module-federation.config.ts — a REMOTE
const config = {
  name: 'catalog',
  exposes: { './Module': './src/remote-entry.ts' },  // what I give away
};
```

`remotes: ['catalog']` is a **static remote** in the "name without address" form: on dev Nx knows the catalog's port itself, in production the address is supplied at build time (as a tuple `['catalog', 'https://cdn.../']` or via env). The alternative is **dynamic remotes**: addresses aren't baked into the bundle but read at runtime from `module-federation.manifest.json`; the host is generated with `--dynamic`, and then a relocated CDN or a canary remote is a manifest edit, no host rebuild. The rule: start with static (simpler, errors show up earlier); go dynamic when remote addresses genuinely change independently of host releases.

### The bootstrap pattern: why main.ts became two files

Instead of the usual main.tsx, the generator creates a pair:

```ts
// apps/shell/src/main.ts — its entire contents:
import('./bootstrap');

// apps/shell/src/bootstrap.tsx — the real entry: createRoot().render(<App/>)
```

This is not decoration but the **async boundary** from chapter 09: the dynamic `import()` gives the bundler a point where it can stop, run shared negotiation (init the containers, pick the react versions) and only then execute the code that consumes those shared deps. Glue the two files together and you get the classic "Shared module is not available for eager consumption" (we'll reproduce it in chapter 11).

### What happens on nx serve shell

The chapter's key practical question. Spinning up three full dev servers with watch and HMR is expensive: on a real federation of 10 remotes that's gigabytes of RAM and minutes of startup. So Nx defaults to something else:

```
                  nx serve shell

          ┌───────────────────────────┐
          │ shell — a full dev server │
          │ :4200 · watch · HMR       │
          └───────────────────────────┘
     expects remotes on the configured ports
                        ▼
┌─────────────────────┐    ┌─────────────────────┐
│ catalog :4201       │    │ checkout :4202      │
│ STATIC: built once, │    │ STATIC: built once, │
│ no watch            │    │ no watch            │
└─────────────────────┘    └─────────────────────┘

nx serve shell --devRemotes=catalog → catalog becomes a dev server with HMR too
```

The remotes are built **once** (with all the cache benefits of chapter 04 — unchanged means instant) and served as static files on their ports. Only the host runs in watch mode. The consequence every newcomer trips over: **you edit catalog code while `nx serve shell` is running — and nothing happens**. Not a bug: the catalog is deployed as static files. Working on the catalog? Say so: `nx serve shell --devRemotes=catalog`, and the catalog comes up as a full dev server with HMR while checkout stays static. In new versions this orchestration of long-running tasks rides on the continuous tasks from chapter 03.

### Routing: the host owns the routes

The chapter 09 decision becomes code: react-router lives in the host, remote modules attach lazily:

```tsx
const CatalogPage = React.lazy(() => import('catalog/Module'));
```

`'catalog/Module'` is neither a file path nor a tsconfig alias: it's a federated request — "from the catalog container, take exposes './Module'". TypeScript knows nothing about such a module — it's typed by the `remotes.d.ts` file (`declare module 'catalog/Module'`) that Nx generated. Remember chapter 09: that's a declaration, not a guarantee — the real contract is checked only at runtime (MF 2.0 can generate types from the remote — chapter 11).

## In a real-world monorepo

- `cat apps/*/module-federation.config.*` — the federation map in a minute: who's the host (remotes), who's a remote (exposes), what the exposure granularity is.
- `nx show project shell --web` → the serve target: which executor/command, which ports, whether `devRemotes` is preset in the default options.
- How production learns the remote addresses: grep for `manifest` (dynamic) and for tuples/env in module-federation.config (static). That answers "what needs redeploying if the catalog moved to another CDN".
- Your team owns one remote? The local routine is `nx serve shell --devRemotes=<yours>`: the host and other teams' remotes as static, yours with HMR. Ports stuck after a crashed session — `lsof -i :4200-4210` and clean up.
- `cat apps/shell/src/remotes.d.ts` + look for generated `@mf-types` — how the repo types its federated imports (a bare declare module, or MF 2.0 types).

## What we're adding to the project

The course's culmination: mini-shop becomes a federation. The vite shell goes away (the whole point of thin apps is that they're disposable), replaced by a host + two remotes on rspack; the pages stay in libs and simply get re-wired.

## Practical exercise

**Input:** the workspace after chapter 08 (+ chapter 09 read). All UI lives in libs: catalog-feature (CatalogPage), checkout-feature-cart (CartPage), shared-ui, shared-util.

**Task:**

1. Remove the shell app with the standard generator (`@nx/workspace:remove`). Before that, write down what we lose (and confirm it's almost nothing: the chapter 04 banner and the deploy target will move to the new shell).
2. Generate the federation: host `shell` with remotes `catalog` and `checkout` (one host-generator command), bundler — rspack, vitest, no e2e.
3. Wire in the lib content: the catalog's `./Module` re-exports `CatalogPage` from `@mini-shop/catalog-feature`; checkout — `CartPage` from `@mini-shop/checkout-feature-cart`. The remote apps must stay thin (import + export).
4. Routing in the host: `/` (a storefront stub), `/catalog`, `/checkout`; lazy imports + a Suspense fallback + an error boundary for an unreachable remote (the chapter 09 decision).
5. Study serve: run `nx serve shell`, note the ports and processes; edit some text in CatalogPage — confirm that WITHOUT `--devRemotes` the change is not picked up; restart with `--devRemotes=catalog` and confirm that it is.
6. Tidy up: tags for the new projects (`scope:catalog,type:app` etc.), `typecheck` targets, the chapter 08 deploy target on both remotes (`nx deploy catalog` publishes an independent artifact — which is what all of this was for).

**Edge cases to think about:**

- What happens if you delete `import('./bootstrap')` and go back to a plain main.tsx?
- `nx build shell` — do the catalog bundles end up in it? What then gets published when you "deploy shell"?
- How does shell learn the remotes' production addresses if they live on different CDN domains?

## Worked solution

Steps 1–2 — the rebuild:

```bash
npx nx g @nx/workspace:remove shell
npx nx g @nx/react:host shell --directory=apps/shell \
  --remotes=catalog,checkout --bundler=rspack \
  --style=css --unitTestRunner=vitest --e2eTestRunner=none
```

One command created three applications and all the wiring. The essentials of what was generated:

```
apps/
├── shell/
│   ├── module-federation.config.ts   # name: 'shell', remotes: ['catalog', 'checkout']
│   ├── rspack.config.ts              # wraps the MF config with the Nx plugin
│   └── src/
│       ├── main.ts                   # import('./bootstrap') — the async boundary
│       ├── bootstrap.tsx             # the real entry
│       ├── remotes.d.ts              # declare module 'catalog/Module'
│       └── app/app.tsx               # routes with React.lazy — finished in step 4
├── catalog/
│   ├── module-federation.config.ts   # name: 'catalog', exposes: { './Module': ... }
│   └── src/remote-entry.ts           # what ships out as './Module'
└── checkout/                         # same shape
```

Step 3 — the remotes stay thin (chapters 01 and 06 pay off right here):

```ts
// apps/catalog/src/remote-entry.ts
export { CatalogPage as default } from '@mini-shop/catalog-feature';

// apps/checkout/src/remote-entry.ts
export { CartPage as default } from '@mini-shop/checkout-feature-cart';
```

Step 4 — the host owns routing and degradation:

```tsx
// apps/shell/src/app/app.tsx
import { lazy, Suspense } from 'react';
import { Link, Route, Routes } from 'react-router-dom';
import { RemoteBoundary } from './remote-boundary';

const CatalogPage = lazy(() => import('catalog/Module'));
const CheckoutPage = lazy(() => import('checkout/Module'));

export function App() {
  return (
    <>
      <nav>
        <Link to="/">mini-shop</Link> · <Link to="/catalog">Catalog</Link> ·{' '}
        <Link to="/checkout">Checkout</Link>
      </nav>
      <Suspense fallback={<p>Loading…</p>}>
        <Routes>
          <Route path="/" element={<h2>Storefront</h2>} />
          <Route
            path="/catalog"
            element={
              <RemoteBoundary fallback={<p>The catalog is temporarily unavailable</p>}>
                <CatalogPage />
              </RemoteBoundary>
            }
          />
          <Route
            path="/checkout"
            element={
              <RemoteBoundary fallback={<p>Checkout is temporarily unavailable</p>}>
                <CheckoutPage />
              </RemoteBoundary>
            }
          />
        </Routes>
      </Suspense>
    </>
  );
}

export default App;
```

`RemoteBoundary` is an ordinary class ErrorBoundary with a fallback prop: a failed remote load (step 2 of the chapter 09 sequence) degrades to a message on one route instead of taking the app down.

Step 5 — serve and its logic:

```bash
npx nx serve shell
# > catalog:  built and served as static files on :4201
# > checkout: built and served as static files on :4202
# > shell:    dev server on :4200 (watch + HMR)
```

A CatalogPage edit is invisible in this mode — the catalog is "deployed" as static files (which is an honest model of production: you don't rebuild other teams' remotes either). Working on the catalog:

```bash
npx nx serve shell --devRemotes=catalog
```

Step 6 — deploying a remote: `nx deploy catalog` → the catalog build (or a cache hit) → `.deploy/catalog` with its chunks and remote entry. There it is — the independent deploy from chapter 09, in miniature: the catalog artifact is published separately from shell.

Answers to the edge cases:

- Without `import('./bootstrap')` the bundler loses the async boundary: code consuming the shared react lands in the synchronous startup chunk before negotiation has run — "Shared module is not available for eager consumption" (the detailed breakdown is chapter 11).
- `nx build shell` builds **only shell**: dist/apps/shell contains no catalog bundles — just the addresses where the host will look for them. "Deploying shell" publishes the host; the remotes deploy through their own pipelines — that was the point.
- Production addresses: for static remotes — the tuple `['catalog', 'https://cdn.mini-shop.example/catalog/']` in the production build's module-federation.config (or env substitution); for genuinely independent infrastructure — dynamic remotes with a manifest edited without rebuilding the host.

## Check yourself

1. List what the `@nx/react:host` generator creates beyond the React app itself, and why each piece exists.
2. Why do the remotes come up as static files during `nx serve shell` rather than as dev servers? What problem does that solve, and what inconvenience does it create?
3. What's the difference between static and dynamic remotes? Give a scenario where dynamic is justified.
4. `import('catalog/Module')` — how does this specifier resolve at host build time and at runtime? How does TypeScript know such a module?
5. Our remote apps are three lines each: a re-export of a page from a lib. Which architectural payoffs from earlier chapters made that possible?

<details>
<summary>Answers</summary>

1. `module-federation.config.ts` (the name/remotes declaration, expanded by the plugin into a full bundler config), the bootstrap pair `main.ts` → `bootstrap.tsx` (the async boundary for shared negotiation), `remotes.d.ts` (TS declarations of federated modules), the routing skeleton with `React.lazy` over the remotes, serve ports for each app — plus the remote apps themselves with `remote-entry.ts` and exposes.
2. N full dev servers means RAM, minutes of startup, and watch over code you're not touching. Static serving solves the scale: remotes are built once (usually from cache) and just served; only the host keeps watch. The inconvenience: edits to a remote aren't picked up until you declare it in `--devRemotes` — the source of the classic "I'm editing and nothing changes" confusion.
3. Static: the remote list and addresses are fixed at host build time (ports on dev, URLs via tuple/env in prod); changing an address means rebuilding the host. Dynamic: the host reads addresses at runtime from a manifest; the host build doesn't depend on them. Justified when remote addresses change independently of host releases: canaries and gradual rollouts of remotes, environments with different CDNs, domain migrations that shouldn't require a host release.
4. At build time the bundler sees in the config that `catalog` is a federated remote and doesn't try to resolve the module to files: a runtime request is left in its place. At runtime it's the chapter 09 sequence: fetch the catalog's remoteEntry, `init` with the common shared scope, `container.get('./Module')`, fetch the chunks. TypeScript knows the module only from `remotes.d.ts` (or generated MF 2.0 types) — a developer's promise the runtime never checks.
5. Thin apps (chapter 01): all UI lives in libs, so recreating shell cost almost nothing and the remotes reduced to re-exports. Boundaries and scopes (chapter 06): the catalog feature doesn't pull checkout code, so the catalog remote doesn't ship someone else's code. The cache (chapter 04): static remotes rebuild instantly during serve when unchanged. The deploy executor (chapter 08) attached to the remotes without a single edit — context instead of hardcode.

</details>

## Common mistake

Day one with federation almost always looks like this: the developer runs `nx serve shell`, opens the catalog, edits `catalog-page.tsx` — nothing. Saves again, reloads the page, blames the browser cache, Nx, rspack. But it's the design: under plain serve the catalog is a static artifact, just like in production. The reflex to build: **when starting dev mode, declare what you're working on** — `--devRemotes=catalog`. It's worth pinning in the README or in a target (`serve-dev` with preset devRemotes) so newcomers don't re-run this quest.

The second mistake is putting code into a remote app. It feels natural: "it's the catalog page, so I write it in apps/catalog/src". But code locked inside an app can't be reused or covered by boundary rules (chapter 06), and the remote stops being a thin adapter, accreting logic that someone will eventually want to call from elsewhere — and will have to dig out. The rule doesn't change with federation: **all meaningful code lives in libs; an application (host or remote alike) is configuration, routing and re-exports**. Our three-line remote entries aren't a textbook simplification — they're the target state.
