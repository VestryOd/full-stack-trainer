# Deployment, Versioning, and Testing

## Independent CI/CD pipelines per micro-frontend

```txt
checkout-repo/  → CI: lint → unit tests → build → publish remoteEntry.js@2.4.1 to CDN → update manifest
catalog-repo/   → CI: lint → unit tests → build → publish remoteEntry.js@1.8.0 to CDN → update manifest
```

Neither of these pipelines blocks the other. This is the organizational benefit from article 01, realized mechanically: each pipeline runs on its own schedule, and the only thing that can block it is its own tests — not a flaky test belonging to a neighboring team.

## The contract needs versioning, not the whole application

A common misconception: since this is a "micro-frontend," it must be versioned as a single monolithic unit. In reality, what needs versioning discipline isn't the whole application — it's specifically the surface that crosses the boundary between host and remote:

- the props/API shape of exposed modules (article 04),
- major versions of shared dependencies (article 03),
- the design-system version (article 06),
- ownership of the route prefix (article 05).

Everything else — the internal implementation — can change freely, with no coordination at all, precisely because it isn't part of the contract.

```json
// checkout-mfe/module-federation.manifest.json — the published contract, not the implementation
{
  "name": "checkout",
  "version": "2.4.1",
  "exposedModules": {
    "./CheckoutApp": {
      "propsSchema": { "onOrderComplete": "(orderId: string) => void" }
    }
  },
  "sharedDependencies": {
    "react": "^18.2.0"
  }
}
```

## Backward-compatibility strategies for breaking changes

When a remote needs to make a breaking change to its exposed contract (say, `CheckoutApp` now requires a new mandatory prop), it can't just ship it — the host and any other consumer would break at runtime, silently, exactly like the design-system version-skew example from article 06.

1. **Expose a new versioned module path alongside the old one.** `./CheckoutApp` (v1) keeps working; `./CheckoutAppV2` is added; the host migrates on its own schedule; the old path gets deprecated later. A direct parallel to REST API versioning (`/v1/`, `/v2/`).
2. **Make new props optional with sane defaults for one release**, and only make them required in the next major bump, after consumers have had a migration window. The same "expand and contract" pattern used for safe database schema migrations (see the question about adding a `NOT NULL` column in the Prisma topic).
3. **Communicate the deprecation through the same contract package** used for docs and types — e.g. `@company/checkout-contract` with a documented deprecation timeline, not a verbal agreement in Slack.

## The testing pyramid across MFE boundaries

**Unit tests** — inside each micro-frontend's own repository, testing its own internal logic and components, exactly like any regular application. Nothing MFE-specific here.

**Contract tests** — specifically verify that this micro-frontend's public surface (the exposed component's props, the shape of published events, the shared-dependency version) matches its documented contract. They run in this micro-frontend's own CI on every commit, **without requiring the other side to actually be deployed**. This is the equivalent of consumer-driven contract testing from the microservices world (Pact-style): the host defines what it expects the remote to expose, and the check runs against the remote's actually built artifact.

```ts
// checkout-mfe: a contract test — runs in checkout's own CI, no host needed
import { CheckoutApp } from './CheckoutApp';

test('CheckoutApp exposes onOrderComplete callback prop', () => {
  const props: React.ComponentProps<typeof CheckoutApp> = {
    onOrderComplete: (orderId: string) => {},
  };
  expect(() => render(<CheckoutApp {...props} />)).not.toThrow();
});
```

**E2E tests across the fully composed application** — the only tier that actually tests real integration: the host and the real remotes, loaded together in a browser, e.g. via Playwright/Cypress against a staging environment where every remote is deployed at its current version. Expensive, slow, run less often (nightly or pre-release) — but the only tier that catches actual runtime integration bugs (a share-scope negotiation failure, a CSS collision) that contract tests fundamentally cannot catch, because they test each side in isolation.

## Feature-flag-driven gradual rollout of a new remote version

When checkout ships a new version of its remote, instead of an instant cutover to 100% of users, resolution of **which version to serve** is gated behind a feature flag (LaunchDarkly, GrowthBook, or a simple in-house percentage rollout) — typically at the level of dynamic remote resolution (see article 03):

```ts
// manifest resolution now depends on a feature flag / rollout percentage
async function resolveCheckoutRemoteUrl(userId: string): Promise<string> {
  const isInRollout = await featureFlags.isEnabled('checkout-v2-4-1', { userId });
  return isInRollout
    ? 'https://cdn.company.com/checkout@2.4.1/remoteEntry.js'
    : 'https://cdn.company.com/checkout@2.3.0/remoteEntry.js';
}
```

This lets a team roll a new remote version out to 5% of users, watch error rates in observability, and roll back with a simple flag flip — with no redeploy of anything, host included. This is the operational payoff of dynamic remotes from article 03 combined with independent CI/CD pipelines.

## Why cross-MFE observability is harder than in a monolith

In a monolith, one stack trace spans the whole request: one deploy artifact, one source map, one log stream. In an MFE architecture, a single user-facing error can span several independently deployed bundles: the error originates in a component from `checkout-mfe@2.4.1`, is caught by an error boundary in `host@8.1.0`, and the call stack runs through `react@18.2.0` loaded from one of several possibly-active copies (see article 03). Reconstructing what actually happened requires:

1. **Correlating deploy versions across every involved MFE at the exact timestamp of the error** (which version of checkout was live for this user at this second, given the feature-flag rollout percentage) — not just "whatever main branch currently holds."
2. **Source maps for each independently built bundle**, uploaded to the observability tool (Sentry, etc.) tagged per MFE version — otherwise the stack trace is useless minified garbage from an entirely different build.
3. **A shared trace/session ID propagated across MFE boundaries** (e.g. injected on the initial page load and read by each MFE's own error-tracking SDK on init), so one dashboard can group every event belonging to a single user session, even though it happened across several separately instrumented apps.

Without deliberately engineering points 1–3, "an error happened somewhere in the composed app" and "which of the 6 independently deployed pieces, at which exact version, actually caused it" are two very different questions — and the gap between them is exactly where incident-response time gets lost.

## Common interview traps

- **"Versioning a micro-frontend means versioning the whole app as one unit"** — only the exposed public contract (props, shared dependencies, design system, route ownership) needs versioning discipline; the internal implementation can change with no coordination at all.

- **"Unit tests and E2E tests are enough, contract tests are a redundant layer"** — contract tests are precisely what lets each team deploy independently **without waiting** for a full E2E run against every other team's currently deployed version. Without them, the only way to verify integration is an expensive, slow E2E suite — which in practice resynchronizes every team's release schedule.

- **"E2E tests across the whole app replace the need for independent pipelines"** — E2E is inherently slower and comes later in the pipeline; making it the sole gate before deploy effectively recreates a single synchronized release train for every team — defeating the entire point of deployment independence.

- **"Observability problems in MFE are the same as in a monolith, just distributed"** — the specific difficulty is correlating exactly **which version** of each independently deployed, feature-flag-gated remote was active for a specific user at a specific moment — something a monolith with a single deploy history never has to reconstruct.

- **"A feature flag for rolling out a new remote version is a nice-to-have, not a necessity"** — it's the actual mechanism that makes independent deployment operationally safe. Without gradual rollout, "independent deploy" in practice means "100% blast radius the moment you push" — which cancels out the fault isolation promised in article 01.
