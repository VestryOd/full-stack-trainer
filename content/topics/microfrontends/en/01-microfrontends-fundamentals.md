# Micro-Frontends Fundamentals

## What a micro-frontend architecture actually is

A **micro-frontend (MFE)** is a frontend unit that one team develops and deploys on its own. Composition with the other units happens separately: at build time, at request time, or at runtime in the browser. The user sees the result as one product.

The key phrase is **independently deployable**. This isn't about how the code looks in a repository. It is about what happens in the CI/CD pipeline — continuous integration and continuous delivery — and in production:

```txt
Frontend modular monolith — one build, one deploy:

repo/
├── modules/
│   ├── checkout/
│   ├── catalog/
│   └── account/
└── main.tsx

Micro-frontend architecture — one pipeline per team:

checkout-team/repo/  → own pipeline → own deploy
catalog-team/repo/   → own pipeline → own deploy
account-team/repo/   → own pipeline → own deploy
```

In the modular monolith, a change in checkout means rebuilding and
redeploying everything. With micro-frontends, composition happens separately
from each deploy: at shell build time, on the server through SSI (server-side
includes), or in the browser at runtime. The checkout team ships at 3pm
without asking catalog or account.

This is a direct parallel to the modular monolith on the backend, described in "Monolith vs Microservices" in the Architecture section. Code modularity and deployment independence are two separate, orthogonal properties.

You can have beautifully modular code behind a single shared deploy — that is a modular monolith. You can also have poorly isolated code that still ships in independent pieces: badly designed micro-frontends, but micro-frontends nonetheless.

## Why this architecture exists at all

Micro-frontends don't solve the technical problem of having too much code. They solve an **organizational** problem: how to let multiple teams build one user-facing product without blocking each other.

### 1. Scaling the organization, not the codebase

If 3 frontend engineers work on one SPA (single-page application), a single repo and a shared deploy almost always win. Put 150 frontend engineers across 12 teams on one product, and that single pipeline becomes the bottleneck. Any merge conflict, any flaky test, any broken end-to-end (E2E) suite blocks the release for all 12 teams at once.

```txt
Conway's Law for the frontend:
if a product is owned by N independent teams, the product tends
to structure itself into N large frontend units — whether or not
there's a working API between them.
```

### 2. Independent release cadence

The checkout team may want to ship 10 times a day (conversion experiments). The account team may ship once a week (changes touch compliance and require manual review). With a single shared deploy, both teams are forced to move at the speed of the slowest, most cautious part of the system.

### 3. Tech-stack heterogeneity (a less common primary reason than it sounds)

Sometimes micro-frontends let one team stay on Angular while the rest of the org moves to React. That happens after a merger of two different frontend platforms. It also happens during a gradual replacement of a legacy app: [Routing and Navigation Across Micro-Frontends](./05-routing-and-navigation.md) covers the Strangler Fig pattern.

This is a real reason, but it shows up less often than pure organizational autonomy. Most companies eventually standardize on one framework anyway.

## The core trade-off — stated explicitly

```txt
┌────────────────────────────────┬─────────────────────────────────┐
│ What you gain                  │ What you pay                    │
├────────────────────────────────┼─────────────────────────────────┤
│ Team autonomy:                 │ Runtime complexity:             │
│ deploy without coordination    │ versions, dependencies and      │
│                                │ composition must be reconciled  │
│                                │ in the browser or on request    │
├────────────────────────────────┼─────────────────────────────────┤
│ Deploy-level fault isolation:  │ Shared-dependency overhead:     │
│ one team's broken release      │ React, the design system, the   │
│ doesn't block the others       │ router — versions must be       │
│                                │ explicitly reconciled           │
├────────────────────────────────┼─────────────────────────────────┤
│ Tech-stack heterogeneity:      │ Consistency cost:               │
│ rarely the main reason         │ UX, styling and behavior must   │
│                                │ read as one product even though │
│                                │ different teams write them      │
└────────────────────────────────┴─────────────────────────────────┘
```

This is the same "monolith vs microservices" trade-off, carried into the browser, with one difference. On the backend, service boundaries are invisible to the user. In the frontend, the user sees a poorly drawn boundary directly: mismatched fonts, duplicate modals, a flash of blank screen between transitions.

## The single most common interview trap: MFE ≠ just splitting a big app into folders

This is the single most common confusion around micro-frontends, and interviewers deliberately probe for it.

**Wrong:** "We have a large app, we split it into modules `checkout/`, `catalog/`, `account/`, each with its own public API — so we have micro-frontends."

That describes a **modular monolith**, not micro-frontends. What distinguishes the two isn't folder structure — it's the answer to one specific question:

> **Can team X ship its part to production right now, without waiting on team Y and without coordinating with it? And without rebuilding or redeploying the parts that Y owns?**

If the answer is "no", you have a modular monolith, however well-structured. That is the case whenever a single `webpack build` compiles everything into one artifact.

Micro-frontends only begin where composition happens **after** each part has been built and deployed on its own. That is composition at request time on the server, or at runtime in the user's browser.

| Stage | Frontend modular monolith | Actual micro-frontends |
|---|---|---|
| Development | separate modules | separate repositories |
| Build | one build | N independent builds |
| Deploy | one artifact | N independent deploys |
| Composition | at build time, via `import` | at request time or at runtime, via `remoteEntry`, SSI or an iframe |

Keep this criterion in mind for every article that follows, and especially for the Module Federation deep dive. Using `ModuleFederationPlugin` by itself says nothing about whether you have micro-frontends.

Module Federation can live inside a modular monolith — one team, one shared release cycle — purely for dynamic code loading. That still isn't a micro-frontend architecture.

What makes an architecture micro-frontend is the organizational decision to deploy independently. Module Federation is only one mechanism that implements it. The article [Module Federation: How It Actually Works Under the Hood](./03-module-federation-deep-dive.md) shows how that mechanism is built.

## When micro-frontends make sense

- Multiple **genuinely independent** teams that need to deploy without coordinating — and this is already true organizationally, not just in theory.
- The product breaks into clearly bounded business domains (checkout, catalog, account) historically or organizationally owned by different teams.
- A merger or acquisition: two existing codebases need to appear under one domain without an immediate full rewrite.
- Incremental replacement of a legacy application (Strangler Fig for the frontend): new functionality is added as a separate micro-frontend while the old app gradually shrinks.

## When micro-frontends are a bad idea (and why this is the main trap)

- **"Our app is large" is not, by itself, a reason.** A large app owned by one team is solved by a modular monolith: feature-sliced structure, clear module boundaries, public APIs between them. None of the costs listed above apply.
- **"Our build/tests are slow"** is a tooling problem (code splitting, incremental builds, test-runner caching), not a problem that independent deployment solves.
- **"It's trendy and looks good on a resume"** — a real and common motivation in practice, but not an engineering justification. Micro-frontends add operational complexity that must be paid back by genuine organizational autonomy — otherwise it's a pure net loss.
- **A single team artificially splitting itself into several "micro-frontends".** It pays the same coordination overhead as multiple teams and gets none of the autonomy benefit. There is nobody to be autonomous from.

## Bottom line

Micro-frontends are an organizational pattern implemented through a build-time or runtime mechanism. The decision comes down to two questions. How many independent teams do we have? How often do they need to ship separately? It is not a question of how to split components into files.

The next article, [Integration Approaches](./02-integration-approaches.md), covers the concrete mechanisms that achieve this independence. They range from iframes to Module Federation, and the article gives the axis worth comparing them on.

## Common interview traps

- **"We split the app into modules with clear boundaries — so we have micro-frontends"** — no, that's a modular monolith. Micro-frontends are defined by deployment independence, not code structure. The litmus test: can one team ship its part without rebuilding/redeploying the parts owned by other teams?

- **"Using Module Federation means we have micro-frontends"** — Module Federation is a runtime module-loading mechanism. It can be used inside a single shared release cycle by one team purely for code splitting — that's not micro-frontends. What defines the architecture is the organizational decision to deploy independently, not the specific tool.

- **"Micro-frontends always improve performance"** — usually the opposite. Without careful management of shared dependencies, the page loads React, the design system and other shared libraries more than once. [Module Federation: How It Actually Works Under the Hood](./03-module-federation-deep-dive.md) explains how sharing is negotiated.

- **"The app is large, therefore we need micro-frontends"** — code size alone is not sufficient justification. The determining factor is organizational structure and the need for independent release cycles. A large app owned by one team is almost always better served by a modular monolith.

- **"Micro-frontends are just microservices for the frontend, so all the trade-offs carry over identically".** The general idea does carry over: independent deployment, and autonomy against complexity. Two things differ. In the frontend the cost of consistency is visible to the user directly, as visual and user-experience mismatches. Runtime composition happens in the user's browser rather than on a protected internal server, and that creates its own specific problems. The articles [Module Federation: How It Actually Works Under the Hood](./03-module-federation-deep-dive.md) and [Styling and Isolation](./06-styling-and-isolation.md) cover them.
