# Library architecture and module boundaries

## Theory

This chapter is about **why** the libs in a real Nx project look the way they do: dozens of small libraries with odd names like `catalog-data-access` instead of a couple of "utils". Behind it stand not taste but two classification axes and a linter that defends them.

### Axis one: the lib type

Over the years the Nx community converged on four types:

```
┌──────────────────┬───────────────────────────────────┬────────────────────────────────┐
│ lib type         │ may depend on                     │ what lives inside              │
├──────────────────┼───────────────────────────────────┼────────────────────────────────┤
│ type:feature     │ feature · ui · data-access · util │ pages, smart components, flows │
├──────────────────┼───────────────────────────────────┼────────────────────────────────┤
│ type:ui          │ ui · util                         │ dumb components, no data       │
├──────────────────┼───────────────────────────────────┼────────────────────────────────┤
│ type:data-access │ data-access · util                │ API clients, state, services   │
├──────────────────┼───────────────────────────────────┼────────────────────────────────┤
│ type:util        │ util                              │ pure functions, types, helpers │
└──────────────────┴───────────────────────────────────┴────────────────────────────────┘
```

Read the matrix top to bottom as "from smart to dumb": feature knows everything, util knows no one. The key prohibitions run bottom-up: **ui doesn't fetch data** (or the component can't be reused with a different source), **data-access knows nothing about rendering** (or it can't be called from a Node script or another framework), **util stays pure** (or it isn't util). An arrow down the matrix is allowed; up is a violation.

### Axis two: the scope (domain)

Type answers "what is it", scope answers "whose is it": `catalog`, `checkout`, `shared`. In the file system a scope is a grouping folder: `libs/<scope>/<type>`; the scope folder itself is not a project — it's just grouping:

```
libs/
├── catalog/
│   ├── feature/         # catalog-feature: the catalog page
│   └── data-access/     # catalog-data-access: products, API
├── checkout/            # arrives in chapter 10
└── shared/
    ├── ui/              # shared-ui: Button and other bricks
    └── util/            # shared-util: formatting, types
```

There's a single scope rule, but it's the most important one: **domains don't reach into each other directly; whatever is common lives in shared**. `catalog` may depend on `catalog` and `shared`; on `checkout` — no. This very rule is what makes the future microfrontends (chapter 10) genuinely independent: if catalog imports nothing from checkout, they can be built and deployed separately.

### Tags: the machine-readable form of both axes

A classification is useless while it lives in heads and wikis. In Nx it's written into `tags` in project.json — plain strings with no built-in semantics (the `axis:value` convention):

```json
{ "name": "catalog-feature", "tags": ["scope:catalog", "type:feature"] }
```

We already saw tags — empty — in chapter 01: the generator creates `"tags": []` exactly for this. Best filled in at generation time (`--tags=scope:catalog,type:feature`), and in chapter 07 our custom generator will do it automatically.

### @nx/enforce-module-boundaries: a linter on top of the graph

An ESLint rule from `@nx/eslint-plugin` that turns conventions into build errors. The mechanics: the linter sees an import → resolves it to the target project via the project graph (the same one from chapter 02) → checks the source and target projects' tags against `depConstraints`. The config lives in the root eslint config:

```js
'@nx/enforce-module-boundaries': ['error', {
  depConstraints: [
    { sourceTag: 'type:feature', onlyDependOnLibsWithTags: ['type:feature', 'type:ui', 'type:data-access', 'type:util'] },
    { sourceTag: 'type:ui', onlyDependOnLibsWithTags: ['type:ui', 'type:util'] },
    // ...
  ],
}],
```

Constraints combine with AND: an import must pass **every** rule whose sourceTag the source project carries. `catalog-feature` (scope:catalog + type:feature) may import `shared-ui` because it passes both the scope axis (shared is allowed for catalog) and the type axis (ui is allowed for feature). As a bonus, the same rule forbids relative imports across project boundaries and deep imports past index.ts — the very holes from chapter 02.

Know the default state: a freshly generated config contains the placeholder `{ sourceTag: '*', onlyDependOnLibsWithTags: ['*'] }` — the rule is formally enabled but **allows everything**. A repo has boundaries only when someone replaced the placeholder with real constraints and lint runs in CI.

### Buildable and publishable: why NOT everything

By default a lib is non-buildable (`--bundler=none`, like our shared-ui): it has no build of its own; the consumer compiles its sources through the alias. A **buildable** lib has its own `build` target and an artifact in dist — needed in exactly two situations: incremental builds of a giant repo (build libs separately and reuse them from cache) and technical necessity (chapter 12: a Node app's compiler needs its neighbour's ready artifact — we'll hit it in practice). **Publishable** is buildable + npm-package packaging (`--publishable --importPath=...`): only for code actually published externally.

The reflex "I'll make every lib buildable, like npm packages" is an expensive mistake: every lib grows a build config, the pipeline grows `^build` orchestration, cold starts slow down severalfold — and at ordinary repo sizes there's no payoff: vite builds the app from lib sources just fine. The rule: **non-buildable until proven otherwise**.

## In a real-world monorepo

- `grep -h '"tags"' $(find libs apps -name project.json -not -path '*/node_modules/*') | sort | uniq -c` — the repo's entire taxonomy in one command: which axes are in use, whether any projects lack tags.
- Find `enforce-module-boundaries` in the root eslint config: if it holds the `'*' → '*'` placeholder, the repo's boundaries are decorative and its layering can't be trusted.
- `nx graph` → group by scope folders with your eyes: in a healthy repo, cross-domain edges go only through shared; a direct catalog → checkout edge is a review finding.
- Verify that lint with this rule actually runs in CI (grep the CI config): a rule that doesn't run doesn't exist.
- `for p in $(ls libs/*/*/project.json); do grep -l '"build"' $p; done` + `nx show project <lib>` — which libs are buildable; each should have a reason (incrementality? publishing? technical necessity?).

## What we're adding to the project

We refactor mini-shop from "an app + one lib" into a layered structure: `catalog-feature` (the catalog page), `catalog-data-access` (products, mocked for now — the real API arrives in chapter 12), `shared-util` (price formatting). We add tags, enable real depConstraints — and break a rule on purpose to read the error.

## Practical exercise

**Input:** the workspace after chapter 05.

**Task:**

1. Generate three libs (all non-buildable, vitest, tags set right away via `--tags`):
   - `shared-util` in `libs/shared/util` (`scope:shared`, `type:util`) — a plain TS lib (`@nx/js:lib`) with `formatPrice(cents: number): string`;
   - `catalog-data-access` in `libs/catalog/data-access` (`scope:catalog`, `type:data-access`) — a `Product` type and a mocked `getProducts(): Promise<Product[]>`;
   - `catalog-feature` in `libs/catalog/feature` (`scope:catalog`, `type:feature`) — a `CatalogPage` component: loads products, renders cards with the shared-ui `Button` and prices via `formatPrice`.
2. Tag the existing projects: `shell` (`scope:shell`, `type:app`), `shared-ui` (`scope:shared`, `type:ui`).
3. Replace the `'*' → '*'` placeholder in the root eslint config with the matrix: both axes, including `type:app → type:feature|ui|util` (the app must not reach data-access directly — features bring the data).
4. Wire `CatalogPage` into shell in place of the previous App content.
5. Break the rule twice and read both errors: import `CatalogPage` inside `shared-ui` (a type violation) and import from `catalog-data-access` inside `shell` (a violation of your app matrix). Revert.

**Requirements:** `nx run-many -t lint` is green after the refactoring; `nx graph` shows the layers: shell → catalog-feature → {catalog-data-access, shared-ui}; shared-util at the bottom.

**Edge cases to think about:**

- A team introduces boundaries into a repo with a hundred existing violations. Enable error right away?
- Where does code live that both catalog and checkout need, but that consists of React components with data?
- Why is `scope:shared → scope:shared` (shared can't see domains) the most important rule in the matrix?

## Worked solution

Step 1 — generation (note: tags are set at creation time, not "someday later"):

```bash
npx nx g @nx/js:lib shared-util --directory=libs/shared/util \
  --bundler=none --unitTestRunner=vitest --linter=eslint \
  --importPath=@mini-shop/shared-util --tags=scope:shared,type:util

npx nx g @nx/js:lib catalog-data-access --directory=libs/catalog/data-access \
  --bundler=none --unitTestRunner=vitest --linter=eslint \
  --importPath=@mini-shop/catalog-data-access --tags=scope:catalog,type:data-access

npx nx g @nx/react:lib catalog-feature --directory=libs/catalog/feature \
  --bundler=none --unitTestRunner=vitest --linter=eslint \
  --importPath=@mini-shop/catalog-feature --tags=scope:catalog,type:feature
```

The code, layer by layer (each lib re-exports its public part through its index.ts):

```ts
// libs/shared/util/src/lib/format-price.ts
export function formatPrice(cents: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(cents / 100);
}
```

```ts
// libs/catalog/data-access/src/lib/products.ts
export interface Product {
  id: string;
  title: string;
  priceCents: number;
}

const MOCK_PRODUCTS: Product[] = [
  { id: 'p1', title: 'Mechanical keyboard', priceCents: 12900 },
  { id: 'p2', title: 'USB-C dock', priceCents: 8900 },
  { id: 'p3', title: '4K monitor', priceCents: 41900 },
];

// The contract is async from day one: in chapter 12 a real HTTP client
// replaces the mocks and not a single consumer changes.
export async function getProducts(): Promise<Product[]> {
  return MOCK_PRODUCTS;
}
```

```tsx
// libs/catalog/feature/src/lib/catalog-page.tsx
import { useEffect, useState } from 'react';
import { Button } from '@mini-shop/shared-ui';
import { formatPrice } from '@mini-shop/shared-util';
import { getProducts, type Product } from '@mini-shop/catalog-data-access';

export function CatalogPage() {
  const [products, setProducts] = useState<Product[]>([]);

  useEffect(() => {
    getProducts().then(setProducts);
  }, []);

  return (
    <section>
      <h2>Catalog</h2>
      {products.map((p) => (
        <article key={p.id}>
          <h3>{p.title}</h3>
          <span>{formatPrice(p.priceCents)}</span>
          <Button onClick={() => console.log('add', p.id)}>Add to cart</Button>
        </article>
      ))}
    </section>
  );
}
```

Steps 2–3 — tags and the matrix. `tags` are added to the project.json of shell and shared-ui, and the placeholder in the root eslint config is replaced:

```js
// eslint.config.mjs (the rule fragment)
'@nx/enforce-module-boundaries': ['error', {
  enforceBuildableLibDependency: true,
  allow: [],
  depConstraints: [
    // the scope axis: domains are isolated, common code goes to shared
    { sourceTag: 'scope:catalog', onlyDependOnLibsWithTags: ['scope:catalog', 'scope:shared'] },
    { sourceTag: 'scope:shared', onlyDependOnLibsWithTags: ['scope:shared'] },
    { sourceTag: 'scope:shell', onlyDependOnLibsWithTags: ['scope:catalog', 'scope:shared'] },
    // the type axis: from smart to dumb
    { sourceTag: 'type:app', onlyDependOnLibsWithTags: ['type:feature', 'type:ui', 'type:util'] },
    { sourceTag: 'type:feature', onlyDependOnLibsWithTags: ['type:feature', 'type:ui', 'type:data-access', 'type:util'] },
    { sourceTag: 'type:ui', onlyDependOnLibsWithTags: ['type:ui', 'type:util'] },
    { sourceTag: 'type:data-access', onlyDependOnLibsWithTags: ['type:data-access', 'type:util'] },
    { sourceTag: 'type:util', onlyDependOnLibsWithTags: ['type:util'] },
  ],
}],
```

Key decisions:

- `type:app` has no right to data-access: the app is a thin wrapper (chapter 01); features bring it data. If tomorrow someone wants to "quickly hit the API from App", the linter will point to where that belongs.
- `scope:shell` sees catalog (it mounts the pages) but is visible to no one: nothing can reference an app at all (no lib lists scope:shell in its onlyDependOn).
- Both axes are checked simultaneously: an import passes through the scope rule AND the type rule.

Step 5 — breaking things. Importing `catalog-feature` inside shared-ui:

```bash
npx nx lint shared-ui
# error  A project tagged with "type:ui" can only depend on libs
#        tagged with "type:ui", "type:util"   @nx/enforce-module-boundaries
```

Importing `catalog-data-access` in shell yields the symmetric error for `type:app`. The error text names tags, not project names — the rule scales to any future libs without touching the config.

Answers to the edge cases:

- Enabling error immediately in a repo with a hundred violations blocks everyone's work. The working pattern: enable as `warn`, list the violations in a backlog, burn them down in batches, flip to `error` at zero. For targeted legacy exceptions there's the `allow` whitelist — but every entry there should carry a removal ticket.
- Data-bearing components needed by both domains — that's `shared/feature` (type feature, scope shared): the matrix allows it (shared-feature may use shared-data-access). If such code keeps piling up, the "common" domain may actually be a full-fledged third scope.
- `scope:shared → scope:shared` guarantees shared knows nothing about domains: otherwise a hidden catalog ↔ checkout bridge forms through a shared lib, and domain independence (and with it independent microfrontend deploys) quietly dies without formally breaking any other rule.

## Check yourself

1. Why is a ui lib forbidden to depend on data-access? Give a concrete scenario that breaks when it does.
2. Describe the mechanics of enforce-module-boundaries: how does the linter know which project an imported module belongs to and what its tags are?
3. depConstraints holds two groups of rules — by scope and by type. How do they combine for a specific import, and why are two axes usually enough?
4. How does a non-buildable lib differ from a buildable one in terms of what happens during `nx build shell`? Name the situations where buildable is justified.
5. A repo has tags and real depConstraints, yet violations keep leaking into main. Which link is most likely missing?

<details>
<summary>Answers</summary>

1. A ui component that fetches its own data can't be reused: a product card calling `getProducts()` from inside is hard-wired to the catalog data source — you can't drop it into checkout with a list of already-purchased items, or render it in storybook without network mocks. The ui → util-only dependency guarantees the component receives everything via props, while "where the data comes from" is decided by the feature layer. Bonus: ui lib tests need neither API mocks nor state providers.
2. The linter uses the project graph: the import specifier resolves through paths/workspaces to a file; the file lies inside some projectRoot — that's the target project; its project.json holds the tags. Then it's a mechanical check: for every rule whose sourceTag the source project carries, the target's tags must be within onlyDependOnLibsWithTags. If not — a lint error listing the tags.
3. With AND: an import is legal only if it passes every applicable rule. `catalog-feature → shared-ui`: the scope rule (catalog may use shared — OK) AND the type rule (feature may use ui — OK). Two axes usually suffice because they're orthogonal and answer two independent questions: "whose" (ownership, deploy independence) and "what" (layer, dependency direction). A third axis (e.g. platform:web/node) is added by the same mechanism once a third independent question appears.
4. Non-buildable: the lib has no build task at all; vite, building shell, compiles its sources directly through the alias — one build in the task graph. Buildable: the lib has its own build with a dist artifact, `^build` sequences the order, the consumer links against the artifact. Justified for incremental builds of a very large repo (reusing prebuilt lib artifacts from cache), for external publishing (publishable), and when a ready artifact is technically required (chapter 12).
5. The CI run. A rule exists only when it executes: if `nx affected -t lint` is not among the required PR checks (or lint is allowed to fail), boundaries remain documentation. Easy to verify: find lint in the CI config and confirm it blocks the merge.

</details>

## Common mistake

A developer from the single-app world creates one `shared/common` lib — "where else would common stuff go?" — and it starts swelling: today a formatter lands there, tomorrow a React hook with an API call, the day after constants from two unrelated domains. Six months later the whole repo depends on it, any edit inside makes affected ≈ everything (chapter 05), and untangling it becomes a quarter-long project. The type/scope classification is the vaccine against exactly this: everything has exactly one right place, and "not sure where — so into common" stops being an option. If you struggle to pick a type for a piece of code, that usually means the piece needs cutting.

The second mistake is quieter and more insidious: tags are assigned, the rule is in the config — but it's the generator's `'*' → '*'` placeholder, or lint doesn't block merges in CI. You get the **illusion of boundaries**: the team believes in the layering, recites it in interviews, while the graph quietly grows cross-cutting imports — no machine is stopping them. The first thing to do after this chapter in your work repo: open the root eslint config and answer honestly — are our boundaries a rule or a decoration?
