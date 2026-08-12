# Fullstack in a monorepo: a Node API and shared contracts

## Theory

### Why the backend belongs in the same repo

So far the monorepo benefits worked inside the frontend. They reach full scale when the backend moves into the same repo — because the most fragile boundary in web development is not between libs but **between the frontend and the backend**: the API contract. In polyrepo land it's guarded manually: a swagger page, a versioned types package, "did you rename that field?" threads. In a monorepo the contract is code:

```
                  the contract as code

             ┌────────────────────────────┐
             │ libs/shared/api-types      │
             │ Product · ProductsResponse │
             │ (type:util, pure types)    │
             └────────────────────────────┘
  import type: both sides compile against ONE contract
                           ▼
┌───────────────────────┐    ┌────────────────────────┐
│ apps/api (Express)    │    │ catalog-data-access    │
│ GET /api/products     │    │ fetch + typed          │
│ GET /api/products/:id │    │ requests and responses │
└───────────────────────┘    └────────────────────────┘

at runtime it is plain HTTP: the compiler checked the types, nobody checked the data
```

Then the whole machinery of this course fires at once. Rename a field in `api-types` → tsc instantly goes red in **every** consumer on both sides of HTTP — before the commit, not a week later on a staging environment. `nx affected` (chapter 05) sees the contract lib change and decides on its own: test the api, the data-access, and everything above. Boundaries (chapter 06) keep the contract from growing foreign dependencies. This is the main practical monorepo payoff for a fullstack engineer — and the thing most worth demonstrating in an interview.

An honest caveat: the shared-types payoff belongs to a TS backend. If the backend is Go/Java, the contract stays code via generation (an OpenAPI schema → generated types for both sides), and affected keeps working through implicit links; but the direct "one types lib" is gone.

### @nx/node: a third kind of application in the graph

To Nx a backend is just another node: `nx g @nx/node:app` with a framework choice (express / fastify / none; for Nest there's a separate `@nx/nest` package with its own generators). The essential differences from frontend apps:

- **The build is esbuild** (the default in recent versions): it bundles main.ts together with all workspace libs into `dist/apps/api/main.js`, the same way vite/rspack bundle the frontend. Consequence: non-buildable libs work here too.
- **serve** — a watch-mode build + a Node process restart on changes.

> **Versions.** Closing the chapter 06 promise — "the technical necessity of buildable libs, we'll see it in chapter 12" — honestly: with the esbuild bundler it **doesn't arise** — libs compile from sources through aliases, just like on the frontend. The necessity was real in older Node setups where the app compiled via `@nx/js:tsc` without bundling: there, every workspace lib needed its own compiled artifact with declarations, so they all became buildable. If you meet a forest of buildable libs around Node apps in a legacy repo — now you know where it came from.

### The contract is a platform-neutral lib

`shared/api-types` is an ordinary `@nx/js` lib tagged `scope:shared, type:util`, with one extra requirement: **no runtime code, no platform APIs**. It's imported by a browser bundle and by a Node process — so inside there are only types and, at most, isomorphic constants: no `fs`, no `window`, no side effects. Large repos formalize this as a third tag axis (`platform:web / platform:node / platform:agnostic`) with a "web doesn't import node" boundary rule — the very "third axis" mentioned in chapter 06.

### What the types do not guarantee

The compiler verified that both sides are *written* against one contract. At runtime there's a network between them, and nobody verifies that the actual JSON matches `Product`: types are erased. While the api and the frontend deploy from one commit, divergence is impossible; but our deploys are independent (chapter 11 says hello): yesterday's frontend may receive a response from today's api. The survival rules are the same as for shared libs: backward-compatible API evolution (add fields, don't rename; deprecate instead of delete) — and, on boundaries with external or unstable sources, runtime validation (zod and friends), which turns "quietly wrong data" into an explicit error.

## In a real-world monorepo

- `nx show projects | grep -v e2e` + `nx graph`: does the repo have Node apps, and through which libs are they connected to the frontend. The "bridge" nodes between front and back are almost always contract libs.
- Find the contract: `ls libs/shared | grep -iE 'types|contracts|dto|api'`. Check its purity: `grep -rn "from 'fs'\|window\." libs/shared/api-types/src` — platform imports in a contract lib mean it will someday break somebody's bundle.
- Edit the contract lib: `nx show projects --affected` should list projects **on both sides** of HTTP. If it shows only the frontend — the backend is tied to the contract by copy-paste, not by an import: the drift has already begun.
- How does the frontend learn the API address: grep for `API_URL`/`baseUrl`/proxy configs. A hardcoded production domain in data-access is a review finding.
- If the backend isn't in the repo: look for codegen (`openapi`, `orval`, `graphql-codegen` in devDeps) — a contract can be code even without a shared repo.

## What we're adding to the project

A real backend: an `api` app on Express with catalog endpoints, a contract lib `shared/api-types` — and `catalog-data-access` finally swaps the chapter 06 mocks for real HTTP. The "not a single consumer changes" promise from the comment in products.ts — we're about to test it.

## Practical exercise

**Input:** the workspace after chapter 11.

**Task:**

1. Generate the contract lib `shared-api-types` (`libs/shared/api-types`, `scope:shared,type:util`, bundler none). Move the `Product` interface from catalog-data-access into it and add a list response type `ProductsResponse`.
2. Generate the `api` app (`@nx/node`, framework express, `apps/api`, tags `scope:api,type:app`); add the scope rule to boundaries (api sees only shared).
3. Endpoints: `GET /api/products` (the list, `ProductsResponse`) and `GET /api/products/:id` (a product or 404). Data — an in-memory array from the former mocks, typed `Product[]` from the contract lib.
4. Enable CORS (the frontend dev ports are 4200–4202) and run `nx serve api`.
5. Rewrite `catalog-data-access`: `getProducts()` and a new `getProduct(id)` go over HTTP with api-types types; network/status errors become exceptions. Verify that `catalog-feature` didn't change by a single line.
6. The full stack locally: `nx serve api` + `nx serve shell --devRemotes=catalog` — the catalog renders backend data.
7. **The contract experiment** (the core of the chapter): rename the `title` field to `name` in api-types. Record: (a) the `nx show projects --affected` list; (b) where and with what messages `typecheck`/`build` failed; (c) fix all sides and reach a green `nx affected -t lint,test,typecheck,build`.

**Requirements:** tags and boundaries green; api has a `typecheck` target; the frontend imports nothing from `apps/api` (check the graph).

**Edge cases to think about:**

- Why must `Product` move into api-types rather than being re-exported from catalog-data-access "for compatibility"?
- What happens if you deploy the new api (field `name`) while the old frontend (expecting `title`) is live? How does that differ from chapter 11's first-wins?
- Where does runtime validation (zod) belong in this scheme, and where is it overhead?

## Worked solution

Steps 1–2 — generation:

```bash
npx nx g @nx/js:lib shared-api-types --directory=libs/shared/api-types \
  --bundler=none --unitTestRunner=vitest --linter=eslint \
  --importPath=@mini-shop/shared-api-types --tags=scope:shared,type:util

npx nx add @nx/node
npx nx g @nx/node:app api --directory=apps/api --framework=express \
  --e2eTestRunner=none --tags=scope:api,type:app
```

The contract:

```ts
// libs/shared/api-types/src/lib/products.ts — the ONLY place the contract is described
export interface Product {
  id: string;
  title: string;
  priceCents: number;
}

export interface ProductsResponse {
  products: Product[];
  total: number;
}
```

Steps 3–4 — the backend (thin, per chapter 01 — for the course the logic sits in main.ts; in a real api it would move into `api/feature` libs):

```ts
// apps/api/src/main.ts
import express from 'express';
import cors from 'cors';
import type { Product, ProductsResponse } from '@mini-shop/shared-api-types';

const PRODUCTS: Product[] = [
  { id: 'p1', title: 'Mechanical keyboard', priceCents: 12900 },
  { id: 'p2', title: 'USB-C dock', priceCents: 8900 },
  { id: 'p3', title: '4K monitor', priceCents: 41900 },
];

const app = express();
app.use(cors({ origin: /localhost:42\d\d$/ }));

app.get('/api/products', (_req, res) => {
  const body: ProductsResponse = { products: PRODUCTS, total: PRODUCTS.length };
  res.json(body);
});

app.get('/api/products/:id', (req, res) => {
  const product = PRODUCTS.find((p) => p.id === req.params.id);
  if (!product) return res.status(404).json({ message: 'Product not found' });
  return res.json(product);
});

const port = process.env.PORT ? Number(process.env.PORT) : 3333;
app.listen(port, () => console.log(`[api] http://localhost:${port}`));
```

Step 5 — data-access moves to HTTP; the signatures don't change, so catalog-feature is untouched (that async contract from chapter 06):

```ts
// libs/catalog/data-access/src/lib/products.ts
import type { Product, ProductsResponse } from '@mini-shop/shared-api-types';

// Address configuration is a deployment concern; a constant is enough for dev
const API_BASE = 'http://localhost:3333';

async function request<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export async function getProducts(): Promise<Product[]> {
  const { products } = await request<ProductsResponse>('/api/products');
  return products;
}

export function getProduct(id: string): Promise<Product> {
  return request<Product>(`/api/products/${id}`);
}

export type { Product } from '@mini-shop/shared-api-types';
```

The `Product` re-export in the last line is a deliberate decision (edge case 1): data-access consumers keep importing `Product` from it (the data-access layer stays their single API door, chapter 06 boundaries don't blur), but the **definition** lives only in api-types — a re-export is not a copy, there's nothing to drift.

Step 7 — the contract experiment. After `title` → `name`:

```bash
npx nx show projects --affected --base=main
# shared-api-types   ← the edit's owner
# api                ← the backend consumer
# catalog-data-access
# catalog-feature    ← the upward closure through the graph
# catalog
# shell

npx nx affected -t typecheck --base=main
# apps/api/src/main.ts:8:15 — error TS2561: Object literal may only specify known
#   properties, but 'title' does not exist in type 'Product'. Did you mean 'name'?
# libs/catalog/feature/src/lib/catalog-page.tsx:24 — error TS2339:
#   Property 'title' does not exist on type 'Product'.
```

There's the whole scene: **one contract edit — the compiler enumerated every spot on both sides of HTTP, and affected assembled the exact work list**. In polyrepo the same refactoring means publishing a types package, PRs into two repos and hoping nobody was forgotten. Fix the api and catalog-page, run `nx affected -t lint,test,typecheck,build` — green.

Answers to the remaining edge cases:

- Deploying the new api under the old frontend is classic version skew: the frontend reads `product.title` and gets `undefined` (silent UI degradation, not an exception — which is what makes it insidious). The difference from chapter 11's first-wins: there it was a race for a singleton in the browser; here it's artifact drift across the network. The cure is shared: backward-compatible evolution (add `name`, mark `title` deprecated, remove after all consumers have shipped), plus the affected-driven "deploy these together" hint.
- Zod belongs on the boundaries where TypeScript is powerless: api input (POST request bodies — user input validation), responses of external APIs, configs from env. Inside our "api ↔ frontend from one repo" pair, blanket runtime validation of every response is overhead: the contract is already compiler-checked, and skew is handled by compatibility; turn it on where the sides genuinely deploy far apart or the data source isn't yours.

## Check yourself

1. Replay the "renamed a contract field" chain in a monorepo and in a polyrepo: what are the steps, where is the error caught, and how much time passes before detection in each case?
2. Why must a contract lib be platform-neutral, and how is that expressed (and defended) in terms of tags and boundaries?
3. What does a shared `api-types` guarantee, and what doesn't it? Where does the compiler's job end and the need for runtime validation begin?
4. Why does a Node app with the esbuild bundler need no buildable libs, and in which setup were they needed?
5. An edit to `shared/api-types` — describe what happens on `nx affected -t test,build` and why it works "across" an HTTP boundary that doesn't exist in the graph.

<details>
<summary>Answers</summary>

1. Monorepo: the api-types edit → tsc fails in every consumer locally/in the PR → affected gathers their tests → everything is fixed in one atomic PR. Time to detection — seconds. Polyrepo: the types-package edit → publish a new version → every consumer repo must bump the version itself (eventually) → until then the frontend and backend compile against different contracts, and the first signal is often a runtime error on staging or in production. Time to detection — days, and it's non-deterministic.
2. Two different runtimes import it: the browser bundle (no fs, no process) and Node (no window, no DOM). Any platform import breaks the opposite side's build — and not immediately, but when someone first touches the affected module. Expressed in tags: `type:util` already forbids downward dependencies; large repos add a `platform:*` axis with rules like "platform:web doesn't import platform:node", and the contract gets `platform:agnostic`.
3. It guarantees: both sides are *written* against one data description, and any incompatible contract change breaks every consumer's compilation immediately. It doesn't guarantee: that the actual bytes in the HTTP response match the types — types are erased at runtime, and the sides may be deployed from different commits. The line: within one commit/deploy the compiler suffices; across independent deploys or external sources you need compatibility discipline and/or runtime validation at the boundary.
4. esbuild bundles the app from sources: workspace libs resolve through tsconfig aliases and land in the final main.js just as they do in a frontend bundle — no per-lib artifact needed. Buildable libs were a necessity in setups where the Node app compiled via `@nx/js:tsc` without bundling: a tsc build of the app needs each dependency's ready d.ts/JS, so every lib grew its own build.
5. api-types owns the changed files; the upward closure (chapter 05) collects everyone importing it: api, catalog-data-access, then catalog-feature, catalog, shell. Test/build tasks are created for them (cache rules apply). The HTTP boundary is irrelevant — the ordinary import graph does the work: both sides of the network *statically import one lib*, and that very edge makes the backend and the frontend neighbours in the graph.

</details>

## Common mistake

A developer from the single-app world is used to "API response types" being a `types.ts` file next to the fetch code. In the monorepo they do the same: the `Product` interface lives in a frontend lib, while the backend "knows" the contract as a similar interface written next to the route (or not written at all). A month later the fields drift apart — the frontend has `priceCents`, the backend already has `price` — and every tool in this course is helpless: **neither the compiler nor affected sees the drift of two copies, because there's no edge in the graph**. The rule is simple: the description of what travels over the network lives in exactly one place — the contract lib; the frontend and backend import it rather than retell it.

The second mistake has the opposite sign: believing that a green tsc means the data is valid. Types are a compile-time illusion: they guarantee the consistency of the *code*, but at runtime untyped JSON travels the network from whatever artifact is actually deployed. While both sides ship from one commit, the illusion is safe; with independent deploys (which this whole course is about) a gap opens where the old frontend talks to the new api. The answer isn't schema paranoia on every call, but awareness: backward-compatible contract evolution as the norm, and runtime validation exactly where the sides genuinely diverge in time or the source isn't yours.
