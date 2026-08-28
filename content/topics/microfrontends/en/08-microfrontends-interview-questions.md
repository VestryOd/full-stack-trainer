# Micro-Frontends — Interview Questions (Middle/Senior)

## Group 1: Organizational Pattern vs. Component Splitting

**What is the fundamental difference between micro-frontends and a frontend modular monolith?**

Both approaches can have identically clean, well-modularized code with explicit boundaries between parts. The difference isn't in code structure — it's in the deployment model.

| | Modular monolith | Micro-frontends |
|---|---|---|
| Builds and deploy artifacts | one | N independent |
| One module changes | rebuild and redeploy everything | deploy that part alone |
| Composition | inside the single build | after each part is deployed |

Composition itself runs at the host's build time, on the server for each request, or in the browser at runtime. Server-side includes (SSI) do the server variant, Module Federation and single-spa the runtime one.

Code modularity and deployment independence are orthogonal properties: you can have one without the other.

---

**What practical criterion distinguishes "real" micro-frontends from a modular monolith?**

One question decides it. Can team X ship its part to production right now, without waiting on team Y, and without rebuilding or redeploying the parts Y owns?

- **No** — everything is compiled by a single `webpack build` and shipped as one artifact. That is a modular monolith, however well structured.
- **Yes** — composition happens after each part is already built and deployed separately. Those are micro-frontends.

Using a technology like Module Federation proves nothing on its own. One team can use it inside a modular monolith, purely for dynamic code loading.

---

**Why isn't "our app is large" by itself sufficient justification for adopting micro-frontends?**

Micro-frontends solve an organizational problem: letting several independent teams deploy without coordinating with each other. They do not solve the technical problem of too much code.

A large app owned by one team is almost always better served by a modular monolith — feature-sliced structure, clear module boundaries, public APIs between them. That avoids the three standing costs of micro-frontends:

- runtime complexity from reconciling shared dependencies;
- the overhead of keeping the parts visually consistent;
- separate continuous integration and continuous delivery (CI/CD) infrastructure per part.

Slow builds or slow tests are a tooling problem — code splitting, test-runner caching — not a reason for independent deployment.

---

**How does Conway's Law manifest specifically in frontend architecture?**

Conway's Law (Melvin Conway, 1967): organizations that design systems are constrained to produce designs that copy their own communication structures.

Applied to the frontend: if a product is owned by N independent teams, it tends to structure itself into N large frontend units. That happens whether or not there is a working API between them.

The practical implication:

- Micro-frontends make sense when several teams are already organizationally independent and need independent deployment.
- For a single team the law simply does not apply. There is no one to be autonomous from, and the coordination overhead of a multi-service structure stays.

The law is descriptive, not prescriptive. The Inverse Conway Maneuver — structuring teams to match the desired architecture — is the prescriptive counterpart.

## Group 2: Integration Approaches

**Compare build-time integration via npm packages with client-side runtime integration — what's the correct axis to compare them on?**

Two terms run through this section. The **host** loads someone else's code at runtime; a **remote** publishes its code for others to load.

The correct axis is *when* it is decided which code, at which version, ends up where — and who makes that decision.

**Build-time integration.** Resolution happens at the host's build. The remote team can publish new package versions whenever it wants, but the user sees nothing until the host bumps the dependency and rebuilds. Development independence exists; deployment independence for the running application does not.

**Client-side runtime integration** (Module Federation, single-spa, import maps). Resolution happens in the browser at the moment the user navigates. A remote's version can change without rebuilding the host. The trade-off: resolution can now fail while the user is looking at the screen, instead of being caught in the host's CI.

---

**When is an iframe the right architectural choice, rather than a compromise born of necessity?**

When isolation is a requirement, not a side effect. The case is a widget from an untrusted third-party vendor: a payment form, a chat widget, an ad. You deliberately do not want that code touching the DOM (document object model) or the cookies of the surrounding page.

An iframe gives the only true isolation of JS, CSS and DOM among all the approaches: a separate browsing context with its own `window`. The price:

- styles cannot be shared naturally;
- fitting the frame's height needs hacks;
- native back-button behavior and deep linking are lost until you synchronize them by hand, through `postMessage` and `history.pushState`.

That price is justified when isolation is the goal itself, not something you are forced to tolerate.

---

**What is the actual advantage of server-side composition (SSI) over client-side runtime composition, and what's its cost?**

With server-side composition the page is assembled from HTML fragments on the server or edge, on every incoming request, before anything reaches the browser. The advantages follow:

- fast TTFB (time to first byte): the browser gets finished HTML;
- it works with JS disabled on the client (progressive enhancement);
- it performs excellently for SEO (search engine optimization);
- each fragment's version can change instantly, because composition is recalculated on every request instead of being fixed at the host's build.

The cost is infrastructure: a dedicated composition layer at the edge, or a compositor service. Coordinating client-side interactivity between independently rendered fragments — hydration, shared JS state — is also noticeably harder than with pure client-side composition.

## Group 3: Module Federation Internals

**What exactly is inside remoteEntry.js, and what happens when the host loads it?**

`remoteEntry.js` isn't the application bundle. It is a small container with two functions:

- `init(shareScope)` — registers this remote's shared-dependency versions into the host's common share scope.
- `get(moduleRequest)` — returns an async factory for the requested exposed module.

The actual code of the exposed modules lives in separate chunks that `get()` loads lazily, which is exactly why `remoteEntry.js` itself is tiny.

So `import('checkout/CheckoutApp')` in the host resolves into four steps:

1. Fetch the `checkout` remote's `remoteEntry.js`.
2. Call `init()` to reconcile dependencies.
3. Call `get('./CheckoutApp')`.
4. Execute the returned factory.

---

**Describe the shared-dependency negotiation algorithm in Module Federation. What do singleton, strictVersion, and eager mean?**

Negotiation runs in five steps.

1. On initialization, every container registers its shared-module versions into a common share scope.
2. Code references a shared dependency, say `react`.
3. The runtime looks in the share scope for a compatible version.
4. If one is there and `singleton: true` is set, that instance is reused, with no new network request.
5. If none is there, the container loads its own fallback copy — always bundled inside it for exactly this case.

**The three flags**

- `singleton: true` — reuse one instance instead of loading a second copy.
- `strictVersion: true` — on incompatibility, throw an explicit error instead of quietly loading the fallback. Useful in staging, to catch version drift before production.
- `eager: true` — bundle the module into the main chunk instead of loading it asynchronously. Necessary for the host's entry point. Outside it, this can break negotiation by registering a version before other containers have reconciled.

```js
shared: {
  react: {
    singleton: true,
    requiredVersion: '^18.2.0',
    strictVersion: true,
    eager: false,
  },
}
```

---

**Why do two copies of React sometimes load in production even though everything worked in dev? How do you actually debug it?**

Three typical scenarios.

1. **An initialization race.** Share-scope negotiation depends on the order in which containers call `init()`. In dev that order is stable, because everything is local. In production a remote loads from a different CDN (content delivery network), with different latency. It may not find a compatible version in the share scope in time, and loads its own fallback.
2. **A genuine version mismatch.** Semver formally satisfies `requiredVersion`. But without `strictVersion` the runtime can silently pick a version the remote team never tested against.
3. **The symptom you see.** An `Invalid hook call` error. React stores its hook dispatcher as a module-level singleton, and with two `react-dom` instances in memory it stops recognizing its own render.

To debug it:

- check the Network tab for a duplicated `react` chunk;
- inspect `window.__webpack_share_scopes__.default` in the console;
- turn `strictVersion: true` on temporarily in staging, to get an explicit error instead of silent duplication.

---

**Why is the `import('./bootstrap')` pattern needed instead of a regular static import at the entry point?**

Webpack has to finish the container's `init()` — shared-dependency negotiation — before any code imports `react`.

A top-level static `import` executes synchronously as the script loads, before the runtime gets a chance to wait for `init()` from other containers. A dynamic `import()` creates an asynchronous boundary, and after it webpack is guaranteed to have reconciled the share scope. Without this pattern you get a runtime error: `Shared module is not available for eager consumption`.

```ts
// index.ts
import('./bootstrap'); // an async boundary before consuming shared dependencies
```

---

**What's the difference between static and dynamic remotes, and when is each appropriate?**

A **static remote** has its URL baked into the host's `webpack.config.js` at build time — the `checkout: 'checkout@http://.../remoteEntry.js'` entry.

A **dynamic remote** resolves its URL at runtime, through a manifest the host fetches before it even knows where to get `remoteEntry.js`.

| | Static remote | Dynamic remote |
|---|---|---|
| URL known at | host build time | runtime |
| Change remote version | rebuild the host | edit the manifest |
| Extra network cost | none | one round-trip to the manifest |
| Resolution can fail | in the host's build | in the user's browser |

That is what lets you roll a version back during an incident, or ship a gradual flag-gated rollout, without redeploying the host.

## Group 4: Communication and State Sharing

**What communication channels exist between independently deployed micro-frontends, and what are their trade-offs?**

Four channels, each with a different trade-off.

| Channel | Strength | Weakness |
|---|---|---|
| Event bus on `window`/`document` | loose coupling, framework-agnostic | no compile-time contract check without a versioned package of event types |
| Shared store (Redux/Zustand via `shared`) | one source of truth, no sync lag | recreates coupling; justified only when the parts deploy in lockstep |
| Props and callbacks from the host | type-safe and explicit | only where the host mounts the component directly, not between sibling remotes |
| URL and query params | survives a reload, needs no shared runtime dependency | limited to serializable primitives |

The URL channel is the most primitive and, for that reason, the most robust.

---

**Why is directly importing a sibling remote's internal implementation considered an anti-pattern, even if it's technically possible via Module Federation's exposes?**

Because it creates hidden coupling that neither team's build or tests can catch. A change to the internal shape of catalog's `cartStore` breaks neither catalog's CI nor checkout's CI. The two builds happen independently and never see each other's code.

The breakage shows up in the user's browser at runtime, when checkout's bundle executes alongside the new version of catalog's bundle. That is exactly where it is hardest to catch.

The rule: import only what is explicitly and deliberately exposed as a public contract. That is the equivalent of a microservice's public REST (representational state transfer) or gRPC API. It deserves the same version discipline as any public API.

```ts
// ❌ Anti-pattern: internal implementation, accidentally reachable via exposes
import { cartStore } from 'catalog/src/internal/cartStore';

// ✅ Correct: only a deliberately exposed public contract
import { getCartSummary } from 'catalog/PublicApi';
```

---

**When is a shared store instance between micro-frontends justified, and when isn't it?**

It is justified in two cases:

- the micro-frontends already deploy in lockstep, meaning one team and a single release cycle;
- the store's contract shape is versioned and maintained as rigorously as a public API.

In the general case it is not justified. A change to the store's shape forces every consumer to update in lockstep, which recreates the coupling that independent deployment was meant to eliminate.

The deployment-resilient alternative is an isolated store per micro-frontend (MFE), plus change synchronization over an event bus. Then the only contract is the wire format of the event, and each MFE's internal store shape stays a private implementation detail.

## Group 5: Routing and Navigation

**How is routing ownership typically split between the host and remotes in a production system?**

The pattern that dominates in practice is a hybrid.

- The host owns only top-level segmentation: `/checkout/*` mounts `CheckoutApp`.
- Everything inside that prefix belongs entirely to the checkout team, including freely adding, removing or renaming internal routes with zero changes in the host.

The host only knows the prefix, and that prefix is the minimal public contract between it and the remote.

---

**What happens if the host and a remote each create their own independent router instance (say, two `<BrowserRouter>`s), and how do you avoid it?**

The browser has one `window.history`. Two independent router instances both listen to `popstate` and both call `pushState` on their own. The back button and navigation then behave unpredictably, with one router overwriting the other's decision.

The rule: only one entity calls `history.pushState` or `replaceState` for a given transition, and everyone else derives their state from `window.location`.

In practice the host creates one shared `history` instance and the remote reuses it, instead of creating its own `<BrowserRouter>`. In single-spa the same end is reached differently: a global patch of `history` broadcasts one navigation event to every registered application.

## Group 6: Styling and Isolation

**What approaches exist for style isolation between micro-frontends, and what are Shadow DOM's real trade-offs?**

Four approaches, none of them free.

| Approach | Isolation | Cost |
|---|---|---|
| CSS Modules | build-time class-name hashing | name collisions only, not high-specificity global selectors |
| Shadow DOM | the only real browser-native isolation of DOM and CSS | event retargeting; libraries expecting a global `document` break |
| CSS-in-JS (styled-components, Emotion) | same collision protection, at runtime | order of independently injected `<style>` tags across remotes is unpredictable |
| BEM (block, element, modifier) prefixing | naming convention, zero tooling | rests entirely on team discipline |

Shadow DOM's cost deserves detail. From outside the boundary, `event.target` points at the shadow host, not at the real source of the event. Libraries that reach for a global `document.querySelector`, or that use portals, often stop working inside it.

---

**How can a visual "version skew" of the design system between micro-frontends happen, and why is it dangerous?**

Suppose `catalog-mfe` is pinned to `@company/design-system@2.1.0` and `checkout-mfe` to `@company/design-system@3.0.0`, a major version with breaking visual changes. Compose the two side by side on one page. The user then literally sees two different button styles, both claiming to be the same design system.

This is the CSS equivalent of the two-React-copies bug, with one difference: no error is thrown. The page just looks inconsistent, and it is only caught when an actual human looks at it.

Mitigation is the same organizational discipline used for shared JS dependencies. Treat the design system's major version as a singleton requirement, with a CI check across every repository and a defined upgrade window.

## Group 7: Deployment, Versioning, Testing, Observability

**What exactly needs versioning in a micro-frontend architecture — the whole application, or something narrower?**

Not the whole application, but specifically the surface that crosses the host/remote boundary:

- the props/API shape of exposed modules;
- major versions of shared dependencies;
- the design-system version;
- ownership of the route prefix.

Everything else — the internal implementation — can change freely with no coordination, because it is not part of the contract.

On a breaking contract change there are two moves. Expose a new versioned module path alongside the old one, such as `./CheckoutAppV2`. Or make new props optional for one release before making them required — the expand-and-contract pattern, as in safe database schema migrations.

---

**Describe the testing pyramid for micro-frontends — what role do contract tests play in it?**

Three tiers; only the middle one is specific to this architecture.

**Unit tests** — inside each MFE's own repository, testing internal logic. Nothing specific to micro-frontends here.

**Contract tests** — verify that a given MFE's public surface matches its documented contract: the exposed component's props, event shapes, the shared-dependency version. They run in that MFE's own CI on every commit, without requiring the other side to be deployed.

That last property is the point: it lets teams deploy independently, without waiting for a full E2E (end-to-end) run against everyone else.

**E2E tests across the composed application** — the only tier that actually verifies integration, catching a share-scope negotiation failure or a CSS collision. Expensive and slow, so they run less often.

---

**How are feature flags used to safely roll out a new remote version?**

Resolution of which remote version to serve is gated behind a feature flag, at the dynamic-remote-resolution level. Instead of an instant cutover to 100% of users, the new version goes out to a small percentage. It is watched through observability and rolled back with a single flag flip. Nothing is redeployed, host included.

Without a gradual rollout like this, independent deployment in practice means that 100% of users get the new version the moment you push. That cancels out the fault isolation micro-frontends are supposed to provide.

```ts
async function resolveCheckoutRemoteUrl(userId: string): Promise<string> {
  const isInRollout = await featureFlags.isEnabled('checkout-v2-4-1', { userId });
  return isInRollout
    ? 'https://cdn.company.com/checkout@2.4.1/remoteEntry.js'
    : 'https://cdn.company.com/checkout@2.3.0/remoteEntry.js';
}
```

---

**Why is debugging errors (observability) harder in a micro-frontend architecture than in a monolith?**

In a monolith, one stack trace spans the whole request: one deploy artifact, one source map, one log stream. In an MFE architecture, a single error the user sees can span several independently deployed bundles at different versions. Those bundles may even include different copies of shared dependencies.

Reconstructing what happened requires three things:

1. Correlating deploy versions across every involved MFE at the exact timestamp of the error, accounting for the feature-flag rollout percentage.
2. Source maps for every bundle, uploaded to the observability tool and tagged per MFE version.
3. A shared trace or session id propagated across MFE boundaries, so events from one user session can be grouped across separately instrumented apps.

Without this, an error happened somewhere and which exact version of which part caused it are two different questions. The gap between them is where incident-response time goes.
