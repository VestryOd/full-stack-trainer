# Micro-Frontends Fundamentals

## What a micro-frontend architecture actually is

A **micro-frontend (MFE)** is an independently deployable, independently developed frontend unit that gets composed with other such units — at build time, request time, or runtime in the browser — into a single application the user experiences as one product.

The key phrase is **independently deployable**. This isn't about how the code looks in a repository; it's about what happens in CI/CD and in production:

```txt
Frontend modular monolith:                Micro-frontend architecture:

repo/                                      checkout-team/repo/  → own pipeline → own deploy
├── modules/                               catalog-team/repo/   → own pipeline → own deploy
│   ├── checkout/                          account-team/repo/   → own pipeline → own deploy
│   ├── catalog/
│   └── account/                           Composition happens SEPARATELY from each
└── main.tsx                               of these deploys — at shell build time,
                                            on the server (SSI), or in the browser (runtime).
One build, one deploy.
A change in checkout requires             The checkout team can ship its part
rebuilding and redeploying EVERYTHING.     at 3pm without asking catalog or account.
```

This is a direct parallel to the modular monolith on the backend (see "Monolith vs Microservices" in the Architecture section): code modularity and deployment independence are two separate, orthogonal properties. You can have beautifully modular code with a single shared deploy (a modular monolith), and you can have poorly isolated code that still ships in independent pieces (badly designed, but nonetheless real, micro-frontends).

## Why this architecture exists at all

Micro-frontends don't solve the technical problem of "too much code." They solve an **organizational** problem: how to let multiple teams build one user-facing product without blocking each other.

### 1. Scaling the organization, not the codebase

If 3 frontend engineers work on one SPA, a single repo and a shared deploy almost always win. If 150 frontend engineers across 12 teams work on one product, a single deploy pipeline becomes a bottleneck: any merge conflict, any flaky test, any broken E2E suite blocks the release for all 12 teams at once.

```txt
Conway's Law for the frontend:
if a product is owned by N independent teams, the product tends
to structure itself into N large frontend units — whether or not
there's a working API between them.
```

### 2. Independent release cadence

The checkout team may want to ship 10 times a day (conversion experiments). The account team may ship once a week (changes touch compliance and require manual review). With a single shared deploy, both teams are forced to move at the speed of the slowest, most cautious part of the system.

### 3. Tech-stack heterogeneity (a less common primary reason than it sounds)

Sometimes MFEs let one team stay on Angular while the rest of the org moves to React — for example after an M&A merging two different frontend platforms, or during a gradual replacement of a legacy app (see the Strangler Fig pattern discussed in the routing article). This is a real reason, but in practice it shows up less often than pure organizational autonomy — most companies eventually standardize on one framework anyway.

## The core trade-off — stated explicitly

```txt
┌──────────────────────────────────┬───────────────────────────────────┐
│ What you gain                    │ What you pay                      │
├──────────────────────────────────┼───────────────────────────────────┤
│ Team autonomy:                   │ Runtime complexity:               │
│ deploy without coordination      │ versions, dependencies, and       │
│                                  │ composition must be reconciled    │
│                                  │ in the browser or at request time │
├──────────────────────────────────┼───────────────────────────────────┤
│ Deploy-level fault isolation:    │ Shared-dependency overhead:       │
│ one team's broken release        │ React, the design system, the     │
│ doesn't block the others         │ router — versions must be         │
│                                  │ explicitly reconciled             │
├──────────────────────────────────┼───────────────────────────────────┤
│ Ability to be tech-heterogeneous │ Consistency cost:                 │
│ (less often needed in practice)  │ UX, styling, and behavior must    │
│                                  │ read as ONE product even though   │
│                                  │ different teams write them        │
└──────────────────────────────────┴───────────────────────────────────┘
```

This is the exact same "monolith vs microservices" trade-off, carried into the browser — with one difference: on the backend, service boundaries are invisible to the user. In the frontend, a poorly drawn boundary between micro-frontends is something the user sees directly — mismatched fonts, duplicate modals, a flash of blank screen between transitions.

## The single most common interview trap: MFE ≠ just splitting a big app into folders

This is the single most common confusion around micro-frontends, and interviewers deliberately probe for it.

**Wrong:** "We have a large app, we split it into modules `checkout/`, `catalog/`, `account/`, each with its own public API — so we have micro-frontends."

That describes a **modular monolith**, not micro-frontends. What distinguishes the two isn't folder structure — it's the answer to one specific question:

> **Can team X ship its part to production right now, without waiting on or coordinating with team Y, and without rebuilding/redeploying the parts owned by Y?**

If the answer is "no" — because everything is compiled by a single `webpack build` and shipped as a single artifact — you have a modular monolith, however well-structured. Micro-frontends only begin where composition happens **after** each part has already been built and deployed independently — at request time on the server, or at runtime in the user's browser.

```txt
Frontend modular monolith:                Actual micro-frontends:

Development: separate modules             Development: separate repositories
Build:       ONE build                    Build:       N independent builds
Deploy:      ONE artifact                 Deploy:      N independent deploys
Composition: at build time (import)       Composition: at request/runtime
                                                        (remoteEntry, SSI, iframe)
```

Keep this criterion in mind for every article that follows — especially the Module Federation deep dive: using `ModuleFederationPlugin` by itself says nothing about whether you have micro-frontends. Module Federation can be used inside a modular monolith (one team, one shared release cycle) purely for dynamic code loading — that doesn't make the architecture a micro-frontend architecture. What makes it one is the organizational decision to deploy independently; Module Federation is just one of the mechanisms (article 03) that technically implements that independence.

## When micro-frontends make sense

- Multiple **genuinely independent** teams that need to deploy without coordinating — and this is already true organizationally, not just in theory.
- The product breaks into clearly bounded business domains (checkout, catalog, account) historically or organizationally owned by different teams.
- A merger or acquisition: two existing codebases need to appear under one domain without an immediate full rewrite.
- Incremental replacement of a legacy application (Strangler Fig for the frontend): new functionality is added as a separate micro-frontend while the old app gradually shrinks.

## When micro-frontends are a bad idea (and why this is the main trap)

- **"Our app is large" is not, by itself, a reason.** A large app owned by one team is solved by a modular monolith (feature-sliced structure, clear module boundaries, public APIs between them) — without any of the costs listed above.
- **"Our build/tests are slow"** is a tooling problem (code splitting, incremental builds, test-runner caching), not a problem that independent deployment solves.
- **"It's trendy and looks good on a resume"** — a real and common motivation in practice, but not an engineering justification. Micro-frontends add operational complexity that must be paid back by genuine organizational autonomy — otherwise it's a pure net loss.
- **A single team artificially splitting itself into several "micro-frontends"** — pays the same coordination overhead as multiple teams, with none of the autonomy benefit, since there's no one to be autonomous from.

## Bottom line

Micro-frontends are an organizational pattern implemented through a build-time or runtime mechanism. The decision is made at the level of "how many independent teams do we have, and how often do they need to ship separately," not at the level of "how should we split components into files." The next article covers the concrete mechanisms this independence is technically achieved with — from iframes to Module Federation — and the axis along which they're actually worth comparing.

## Common interview traps

- **"We split the app into modules with clear boundaries — so we have micro-frontends"** — no, that's a modular monolith. Micro-frontends are defined by deployment independence, not code structure. The litmus test: can one team ship its part without rebuilding/redeploying the parts owned by other teams?

- **"Using Module Federation means we have micro-frontends"** — Module Federation is a runtime module-loading mechanism. It can be used inside a single shared release cycle by one team purely for code splitting — that's not micro-frontends. What defines the architecture is the organizational decision to deploy independently, not the specific tool.

- **"Micro-frontends always improve performance"** — usually the opposite: without careful shared-dependency management (see article 03), micro-frontends lead to duplicate loading of React, the design system, and other shared libraries, making the page heavier, not lighter.

- **"The app is large, therefore we need micro-frontends"** — code size alone is not sufficient justification. The determining factor is organizational structure and the need for independent release cycles. A large app owned by one team is almost always better served by a modular monolith.

- **"Micro-frontends are just microservices for the frontend, so all the trade-offs carry over identically"** — the general idea (independent deployment, autonomy vs. complexity) does carry over, but in the frontend the cost of consistency is visible to the user directly (visual and UX mismatches), and runtime composition happens in the user's browser rather than on a protected internal server — which creates its own specific problems (see articles 03 and 06).
