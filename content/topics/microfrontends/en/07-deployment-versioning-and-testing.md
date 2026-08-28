# Deployment, Versioning, and Testing

## Independent CI/CD pipelines per micro-frontend

```txt
checkout-repo/  CI: lint → unit tests → build
                → publish remoteEntry.js@2.4.1 to CDN
                → update manifest

catalog-repo/   CI: lint → unit tests → build
                → publish remoteEntry.js@1.8.0 to CDN
                → update manifest
```

Continuous integration and continuous delivery (CI/CD) run per repository, and neither blocks the other. This is the organizational benefit from [Micro-Frontends Fundamentals](./01-microfrontends-fundamentals.md), made mechanical. Each pipeline runs on its own schedule. Only its own tests can block it, never a neighbor's flaky test.

## The contract needs versioning, not the whole application

A common misconception: since this is a "micro-frontend," it must be versioned as a single monolithic unit. In reality, what needs versioning discipline isn't the whole application — it's specifically the surface that crosses the boundary between host and remote:

- the props/API shape of exposed modules ([Cross-Micro-Frontend Communication and State Sharing](./04-communication-and-state-sharing.md)),
- major versions of shared dependencies ([Module Federation: How It Actually Works Under the Hood](./03-module-federation-deep-dive.md)),
- the design-system version ([Styling and Isolation](./06-styling-and-isolation.md)),
- ownership of the route prefix ([Routing and Navigation Across Micro-Frontends](./05-routing-and-navigation.md)).

Everything else — the internal implementation — can change freely, with no coordination at all, precisely because it isn't part of the contract.

```json
// checkout-mfe/module-federation.manifest.json
// the published contract, not the implementation
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

Suppose a remote needs a breaking change in its contract: `CheckoutApp` now requires a new mandatory prop. Shipping that directly breaks the host and every other consumer at runtime, silently — exactly like the design-system version skew in [Styling and Isolation](./06-styling-and-isolation.md).

1. **Expose a new versioned module path alongside the old one.** `./CheckoutApp` (v1) keeps working, and `./CheckoutAppV2` is added next to it. The host migrates on its own schedule; the old path is deprecated later. A direct parallel to versioning a REST (representational state transfer) API: `/v1/`, `/v2/`.
2. **Make new props optional with sane defaults for one release.** They become required only in the next major bump, after consumers have had a migration window. The same expand-and-contract pattern keeps database schema migrations safe. See the `NOT NULL` column question in the Prisma topic.
3. **Communicate the deprecation through the same contract package** used for docs and types. For example, `@company/checkout-contract` with a documented deprecation timeline, not a verbal agreement in Slack.

## The testing pyramid across micro-frontend boundaries

**Unit tests** — inside each micro-frontend's own repository, testing its own internal logic and components, exactly like any regular application. Nothing is micro-frontend (MFE) specific here.

**Contract tests** — verify that this micro-frontend's public surface matches its documented contract. That surface: the exposed component's props, the shape of published events, the shared-dependency version. They run in its own CI on every commit, **without requiring the other side to be deployed**.

This is consumer-driven contract testing from microservices, Pact-style. The host defines what it expects the remote to expose; the check runs against the remote's actual built artifact.

```tsx
// checkout-mfe: a contract test — runs in checkout's own CI, no host needed
import React from 'react';
import { render } from '@testing-library/react';
import { CheckoutApp } from './CheckoutApp';

test('CheckoutApp exposes onOrderComplete callback prop', () => {
  // The contract check is the type annotation, not the assertion: drop
  // onOrderComplete from CheckoutApp and this file stops compiling.
  const props: React.ComponentProps<typeof CheckoutApp> = {
    onOrderComplete: (orderId: string) => {},
  };
  // The assertion only adds "and it still mounts".
  expect(() => render(<CheckoutApp {...props} />)).not.toThrow();
});
```

**E2E (end-to-end) tests across the fully composed application** — the only tier that tests real integration. The host and the real remotes load together in a browser, through Playwright or Cypress. Staging holds every remote at its current version.

They are expensive and slow, so they run nightly or before a release. They are also the only tier that catches real integration bugs: a failed share-scope negotiation, a CSS collision. Contract tests cannot catch those: they test each side in isolation.

## Feature-flag-driven gradual rollout of a new remote version

When checkout ships a new version of its remote, it does not cut every user over at once. A feature flag decides **which version to serve**. It can be LaunchDarkly, GrowthBook, or a simple in-house percentage rollout. It sits at the level of dynamic remote resolution, described in [Module Federation: How It Actually Works Under the Hood](./03-module-federation-deep-dive.md):

```ts
// manifest resolution now depends on a feature flag / rollout percentage
async function resolveCheckoutRemoteUrl(userId: string): Promise<string> {
  const isInRollout = await featureFlags.isEnabled('checkout-v2-4-1', { userId });
  return isInRollout
    ? 'https://cdn.company.com/checkout@2.4.1/remoteEntry.js'
    : 'https://cdn.company.com/checkout@2.3.0/remoteEntry.js';
}
```

A team can roll a new remote version out to 5% of users, watching error rates in observability. A single flag flip rolls it back, and nothing is redeployed, host included. This is the operational payoff of dynamic remotes from [Module Federation: How It Actually Works Under the Hood](./03-module-federation-deep-dive.md), combined with independent CI/CD pipelines.

## Why cross-MFE observability is harder than in a monolith

In a monolith, one stack trace spans the whole request: one deploy artifact, one source map, one log stream. In an MFE architecture, a single error the user sees can span several independently deployed bundles.

Such an error starts in a component from `checkout-mfe@2.4.1`. An error boundary in `host@8.1.0` catches it. The call stack then runs through `react@18.2.0`, loaded from whichever copy is live at that moment. More than one copy can be live, as [Module Federation: How It Actually Works Under the Hood](./03-module-federation-deep-dive.md) explains.

Reconstructing what actually happened requires:

1. **Correlating deploy versions across every involved MFE at the exact timestamp of the error.** Which version of checkout was live for this user in that second, given the feature-flag rollout percentage? Not whatever the main branch holds now.
2. **Source maps for each independently built bundle**, uploaded to the observability tool (Sentry) and tagged with the MFE version. Without it the stack trace is minified garbage from a different build.
3. **A shared trace or session id propagated across MFE boundaries.** It is injected on the initial page load, and each MFE's error tracker reads it on start-up. One dashboard then groups every event of a user session, even though they come from several separately instrumented apps.

Engineer points 1–3 deliberately, or you end up with two different questions. One is soft: an error happened somewhere in the app. The other is the one you need: which of the six independently deployed pieces, at which version, caused it. The gap between them is where incident-response time goes.

## Common interview traps

- **"Versioning a micro-frontend means versioning the whole app as one unit"** — only the exposed public contract needs versioning discipline. That is props, shared dependencies, the design system, route ownership. The internal implementation can change with no coordination at all.

- **"Unit tests and E2E tests are enough, contract tests are a redundant layer"** — contract tests are what lets each team deploy independently. They remove the **wait** for a full E2E run against every other team's deployed version. Without them, verifying integration means an expensive, slow E2E suite, which in practice resynchronizes every team's releases.

- **"E2E tests across the whole app replace the need for independent pipelines"** — E2E is slower by nature and lands later in the pipeline. Make it the sole gate before deploy and you recreate a single synchronized release train for every team. That defeats the entire point of deployment independence.

- **"Observability problems in MFE are the same as in a monolith, just distributed"** — the specific difficulty is version correlation. Which version of each independently deployed remote, behind its feature flag, was active for this user at this moment? A monolith with one deploy history never has to reconstruct that.

- **"A feature flag for rolling out a new remote version is a nice-to-have, not a necessity"** — it is what makes independent deployment operationally safe. Without a gradual rollout, an independent deploy reaches 100% of users the moment you push. That cancels out the fault isolation promised in [Micro-Frontends Fundamentals](./01-microfrontends-fundamentals.md).
