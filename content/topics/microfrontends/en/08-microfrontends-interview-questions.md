# Micro-Frontends — Interview Questions (Middle/Senior)

## Group 1: Organizational Pattern vs. Component Splitting

**What is the fundamental difference between micro-frontends and a frontend modular monolith?**

Both approaches can have identically clean, well-modularized code with explicit boundaries between parts. The difference isn't in code structure — it's in the deployment model. A modular monolith is one build, one deploy artifact: a change in one module requires rebuilding and redeploying the whole application. Micro-frontends are N independent builds and N independent deploys, composed after each part is already deployed — at the host's build time, on the server per request (SSI), or in the browser at runtime (Module Federation, single-spa). Code modularity and deployment independence are two orthogonal properties; you can have one without the other.

---

**What practical criterion distinguishes "real" micro-frontends from a modular monolith?**

The question: can team X ship its part to production right now, without waiting on or coordinating with team Y, and without rebuilding/redeploying the parts owned by Y? If the answer is "no" — because everything is compiled by a single `webpack build` and shipped as a single artifact — it's a modular monolith, however well-structured. If "yes" — because composition happens after each part is already built and deployed separately — it's micro-frontends. Merely using a technology like Module Federation proves nothing on its own: it can be used inside a modular monolith, by one team, purely for dynamic code loading.

---

**Why isn't "our app is large" by itself sufficient justification for adopting micro-frontends?**

Micro-frontends solve an organizational problem — letting multiple independent teams deploy without coordinating with each other — not the technical problem of "too much code." A large app owned by one team is almost always better served by a modular monolith (feature-sliced structure, clear module boundaries, public APIs between them) — without any of the costs of micro-frontends: runtime complexity from reconciling shared dependencies, the overhead of visual consistency, needing separate CI/CD infrastructure per part. Slow builds or slow tests are a tooling problem (code splitting, test-runner caching), not a reason for independent deployment.

---

**How does Conway's Law manifest specifically in frontend architecture?**

Conway's Law (Melvin Conway, 1967): organizations that design systems are constrained to produce designs that copy the communication structures of those organizations. Applied to the frontend: if a product is owned by N independent teams, the product tends to structure itself into N large frontend units — whether or not there's a working API between them. The practical implication: micro-frontends make sense when several teams are already organizationally independent and need independent deployment; for a single team, Conway's Law simply doesn't apply — there's no one to be autonomous from, while the coordination overhead of a multi-service structure remains. The law is descriptive, not prescriptive — the Inverse Conway Maneuver (deliberately structuring teams to match the desired architecture) is the deliberate, prescriptive strategy.

## Group 2: Integration Approaches

**Compare build-time integration via npm packages with client-side runtime integration — what's the correct axis to compare them on?**

The correct comparison axis is: at what point is it decided which code, at which version, ends up where, and who makes that decision. With build-time integration, resolution happens at the host's build: the remote team can publish new package versions whenever it wants, but the user won't see the changes until the host bumps the dependency and rebuilds — development independence exists, deployment independence for the running application doesn't. With client-side runtime integration (Module Federation, single-spa, import maps), resolution happens in the browser at the moment the user navigates — a remote's version can change without rebuilding the host, but resolution can now fail exactly at the moment the user is looking at the screen, rather than being caught in the host's CI.

---

**When is an iframe the right architectural choice, rather than a compromise born of necessity?**

When isolation is a requirement, not a side effect: embedding a widget from an untrusted third-party vendor (a payment form, a chat widget, an ad), where you deliberately don't want that code to have access to the DOM and cookies of the rest of the page. An iframe provides the only true isolation of JS/CSS/DOM among all the approaches — a separate browsing context with its own `window`. The price of that isolation is the impossibility of naturally sharing styles, height-fitting hacks, and the loss of native back-button behavior and deep-linking without manual synchronization via `postMessage` and `history.pushState` — and that price is justified precisely when isolation is the goal itself, not something you're forced to tolerate.

---

**What is the actual advantage of server-side composition (SSI) over client-side runtime composition, and what's its cost?**

With server-side composition, assembling the page from HTML fragments happens on the server or edge on every incoming request — before anything reaches the browser. This gives fast TTFB, works with JS disabled on the client (progressive enhancement), and performs excellently for SEO. Each fragment's version can be changed instantly and independently, because composition is recalculated fresh on every request rather than fixed once at the host's build time. The cost: it requires dedicated composition infrastructure (an edge layer or a compositor service), and coordinating client-side interactivity between independently rendered fragments (hydration, shared JS state) is noticeably harder than with pure client-side composition.

## Group 3: Module Federation Internals

**What exactly is inside remoteEntry.js, and what happens when the host loads it?**

`remoteEntry.js` isn't the application bundle — it's a small container with two functions: `init(shareScope)`, which registers this remote's shared-dependency versions into the host's common share scope, and `get(moduleRequest)`, which returns an async factory for the requested exposed module. The actual code of the exposed modules lives in separate chunks that `get()` lazily loads — which is exactly why `remoteEntry.js` itself is tiny. When the host does `import('checkout/CheckoutApp')`, it resolves to: fetch the `checkout` remote's `remoteEntry.js`, call `init()` to reconcile dependencies, call `get('./CheckoutApp')`, execute the returned factory.

---

**Describe the shared-dependency negotiation algorithm in Module Federation. What do singleton, strictVersion, and eager mean?**

Every container registers its shared-module versions into a common share scope on initialization. When code references a shared dependency (e.g. `react`), the runtime checks the share scope: if a compatible version already exists there and `singleton: true` is set, the existing instance is reused with no new network request. If no compatible version exists, the container loads its own fallback copy of the dependency, which is always bundled inside it for exactly this case. `strictVersion: true` changes the behavior on incompatibility: instead of quietly loading the fallback, the runtime throws an explicit error — useful in staging to catch version drift before production. `eager: true` bundles the module directly into the main chunk instead of lazily loading it asynchronously — necessary for the host's entry point, but outside of it can break negotiation by registering a version before other containers have had a chance to reconcile.

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

Three typical scenarios. First — an initialization race: share-scope negotiation depends on the order in which different containers call `init()`; in dev mode the order is stable (everything's local), but in production a remote loads from a different CDN with different latency and may not find a compatible version in the share scope in time for its own initialization, so it loads its own fallback. Second — a genuine version mismatch: `requiredVersion` is formally satisfied by semver, but without `strictVersion` the runtime can silently pick a version the remote team never actually tested against. Third — the symptom: an `Invalid hook call` error, because React stores its hook dispatcher as a module-level singleton, and with two `react-dom` instances in memory it stops "recognizing" its own render. To debug: check the Network tab for a duplicated `react` chunk, inspect `window.__webpack_share_scopes__.default` in the console, and temporarily enable `strictVersion: true` in staging to get an explicit error instead of silent duplication.

---

**Why is the `import('./bootstrap')` pattern needed instead of a regular static import at the entry point?**

Webpack needs to finish running the container's `init()` (shared-dependency negotiation) before code starts actually importing `react`. A top-level static `import` in a module executes synchronously as the script loads — before the runtime gets a chance to wait for `init()` from other containers. A dynamic `import()` creates an asynchronous boundary after which webpack is guaranteed to have already reconciled the share scope. Without this pattern you get a runtime error like `Shared module is not available for eager consumption`.

```ts
// index.ts
import('./bootstrap'); // an async boundary before consuming shared dependencies
```

---

**What's the difference between static and dynamic remotes, and when is each appropriate?**

A static remote has its URL baked into the host's `webpack.config.js` at the host's build time (`checkout: 'checkout@http://.../remoteEntry.js'`) — simple, but the remote's version can't change without rebuilding the host. A dynamic remote resolves its URL at runtime — usually via a manifest the host fetches before it even knows where to get `remoteEntry.js`. This lets you change the remote's version (e.g. roll back during an incident, or ship a gradual feature-flag-gated rollout) by editing the manifest, with no redeploy of the host at all — at the cost of an extra network round-trip to the manifest and a later resolution point.

## Group 4: Communication and State Sharing

**What communication channels exist between independently deployed micro-frontends, and what are their trade-offs?**

An event bus on `window`/`document` (CustomEvent) — loose coupling, framework-agnostic, but no compile-time contract checking without a separate versioned package of event types. A shared store instance (Redux/Zustand via Module Federation's shared config) — one single source of truth with no sync lag, but recreates the coupling problem — justified only when the MFEs deploy in lockstep. Props/callbacks from the host — type-safe and explicit, but only works when the host directly mounts the component, not for direct communication between "sibling" remotes. URL/query params — the most primitive but most robust channel: survives a page reload, requires no shared runtime dependency, but is limited to serializable primitives.

---

**Why is directly importing a sibling remote's internal implementation considered an anti-pattern, even if it's technically possible via Module Federation's exposes?**

Because it creates hidden coupling that isn't caught by either team's build or tests: a change to the internal shape of catalog's `cartStore` doesn't break catalog's CI or checkout's CI, because their builds happen independently and never see each other's code directly. The breakage only shows up in the user's browser at runtime, when checkout's bundle executes alongside the new version of catalog's bundle — exactly where it's hardest to catch. The rule: only import what's explicitly and deliberately exposed as a public contract (the equivalent of a microservice's REST/gRPC API), and that surface must be treated with the same version discipline as a public API.

```ts
// ❌ Anti-pattern: internal implementation, accidentally reachable via exposes
import { cartStore } from 'catalog/src/internal/cartStore';

// ✅ Correct: only a deliberately exposed public contract
import { getCartSummary } from 'catalog/PublicApi';
```

---

**When is a shared store instance between micro-frontends justified, and when isn't it?**

It's justified when the micro-frontends already deploy in lockstep (one team, a single release cycle) or when the store's contract shape is versioned and maintained with the same rigor as a versioned public API. In the general case, it's not justified: a change to the store's shape requires every consumer to update in lockstep, which recreates exactly the coupling problem independent deployment was meant to eliminate. A more deployment-resilient alternative is an isolated store per MFE plus change synchronization over an event bus, where the only contract is the wire format of the event, and each MFE's internal store shape remains a private implementation detail.

## Group 5: Routing and Navigation

**How is routing ownership typically split between the host and remotes in a production system?**

The pattern that dominates in practice is a hybrid: the host owns only top-level segmentation (e.g. `/checkout/*` mounts `CheckoutApp`), and everything happening within that prefix belongs entirely to the checkout team — including freely adding, removing, or renaming internal routes with zero changes in the host. The host only knows the prefix — that's the minimal public contract between it and the remote.

---

**What happens if the host and a remote each create their own independent router instance (say, two `<BrowserRouter>`s), and how do you avoid it?**

The browser has one `window.history` — two independent router instances will both listen to `popstate` and independently call `pushState`, causing the back button and navigation to behave unpredictably, with one router overwriting the other's decision. The rule: only one entity should call `history.pushState`/`replaceState` for a given transition; everyone else should derive their state from `window.location`. In practice: the host creates one shared `history` instance, and the remote reuses it instead of creating its own `<BrowserRouter>` (or, as in single-spa, a global patch of `history` broadcasts a single navigation event to every registered application).

## Group 6: Styling and Isolation

**What approaches exist for style isolation between micro-frontends, and what are Shadow DOM's real trade-offs?**

CSS Modules — build-time class-name hashing, zero runtime cost, but only protects against name collisions, not against high-specificity global selectors from elsewhere. Shadow DOM — the only real browser-native isolation of the DOM and CSS, but with a real cost: event retargeting (from outside, `event.target` points to the shadow host, not the actual source of the event), incompatibility with many libraries that expect a global `document.querySelector` or use portals. CSS-in-JS (styled-components/Emotion) — the same collision protection as CSS Modules, but at runtime, with the cost of an unpredictable order of independently injected `<style>` tags between different remotes. BEM prefixing — a pragmatic, zero-tooling default, but entirely dependent on team discipline.

---

**How can a visual "version skew" of the design system between micro-frontends happen, and why is it dangerous?**

If catalog-mfe is pinned to `@company/design-system@2.1.0` and checkout-mfe to `@company/design-system@3.0.0` (a major version with breaking visual changes), and the two are composed side by side on the same page, the user literally sees two visually different button styles, both claiming to be the same design system. This is the CSS equivalent of the "two React copies" bug — except no error is thrown here; it just looks inconsistent, and it's only caught when an actual human looks at the page. Mitigation: the same organizational discipline as for shared JS dependencies — treat the design system's major version as a singleton requirement with a CI check across every repo and a defined upgrade window.

## Group 7: Deployment, Versioning, Testing, Observability

**What exactly needs versioning in a micro-frontend architecture — the whole application, or something narrower?**

What needs versioning discipline isn't the whole application, but specifically the surface that crosses the host/remote boundary: the props/API shape of exposed modules, major versions of shared dependencies, the design-system version, ownership of the route prefix. Everything else — the internal implementation — can change freely with no coordination, precisely because it isn't part of the contract. On a breaking contract change: expose a new versioned module path alongside the old one (`./CheckoutAppV2`), or make new props optional for one release before making them required — the "expand and contract" pattern, similar to safe database schema migrations.

---

**Describe the testing pyramid for micro-frontends — what role do contract tests play in it?**

Unit tests — inside each MFE's own repository, testing internal logic, nothing MFE-specific. Contract tests — verify that a given MFE's public surface (the exposed component's props, event shapes, shared-dependency version) matches its documented contract; they run in that MFE's own CI on every commit, without requiring the other side to actually be deployed — this is exactly what lets teams deploy independently without waiting for a full E2E run against everyone else. E2E tests across the composed application — the only tier that actually verifies integration (a share-scope negotiation failure, a CSS collision), but expensive and slow, so run less often.

---

**How are feature flags used to safely roll out a new remote version?**

Resolution of which remote version to serve is gated behind a feature flag at the dynamic-remote-resolution level: instead of an instant cutover to 100% of users, the new version is rolled out to a small percentage, watched via observability, and rolled back with a simple flag flip — no redeploy of anything, host included. Without gradual rollout like this, "independent deployment" in practice means "100% blast radius the moment you push," which cancels out the fault isolation micro-frontends are supposed to provide.

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

In a monolith, one stack trace spans the whole request: one deploy artifact, one source map, one log stream. In an MFE architecture, a single user-facing error can span several independently deployed bundles at different versions, potentially including different copies of shared dependencies. Reconstructing what actually happened requires: correlating deploy versions across every involved MFE at the exact timestamp of the error (accounting for the feature-flag rollout percentage), having source maps for every bundle uploaded to the observability tool tagged per MFE version, and propagating a shared trace/session ID across MFE boundaries to group events from a single user session across several separately instrumented apps. Without this, "an error happened somewhere" and "which exact version of which part actually caused it" are two different questions, and the gap between them is where incident-response time gets lost.
