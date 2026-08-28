# Cross-Micro-Frontend Communication and State Sharing

## Why this isn't the same as component communication in React

Inside a single SPA (single-page application), communication between components is just props, context, a shared store. Every part of the application is compiled by the same bundler, built together and deployed together. Importing from anywhere is safe: TypeScript checks compatibility at build time, and any type mismatch blocks that one single deploy.

Across micro-frontends, that condition doesn't hold. Each part is potentially built separately and deployed on its own schedule. It may run on a different framework, and it may execute in a different JS realm, as an iframe does.

A direct import between such parts is either technically impossible, or it creates hidden coupling. That coupling undermines the entire reason micro-frontends exist: deployment independence, as [Micro-Frontends Fundamentals](./01-microfrontends-fundamentals.md) explains. Hence the set of patterns below, each with its own cost.

## 1. A custom event bus on window/document

The simplest channel: one micro-frontend dispatches a `CustomEvent` on `window`, others subscribe via `addEventListener`. The publisher doesn't need to know who — or whether anyone at all — is listening.

```ts
// checkout-mfe: publishing an event
window.dispatchEvent(
  new CustomEvent('cart:updated', { detail: { itemCount: 3 } }),
);

// header-mfe: subscribing — built and deployed independently
window.addEventListener('cart:updated', (event) => {
  const { itemCount } = (event as CustomEvent<{ itemCount: number }>).detail;
  updateCartBadge(itemCount);
});
```

**Strengths:** framework-agnostic, works across Module Federation boundaries and (in a `postMessage`-based variant) across iframes, requires no shared state instance.

**Weaknesses:** no compile-time contract checking — the event name and the shape of `detail` are held together by convention unless formalized separately. Debugging is harder: there's no clear call stack, and you end up grepping the codebase for the string `'cart:updated'`.

**How to reduce the risk:** extract event names and payload types into a separate versioned package, for example `@company/mfe-events`. Each team then pulls it in as an ordinary dependency. This turns an event from a string by convention into an actual contract. [Deployment, Versioning, and Testing](./07-deployment-versioning-and-testing.md) covers the same contract-versioning discipline in depth.

## 2. A shared store instance vs. an isolated store synced via pub/sub

**Option A — a shared store instance.** The literal same Redux/Zustand instance is shared between micro-frontends through Module Federation:

```js
// webpack.config.js — both host and remote declare the same shared dependency
shared: {
  '@company/shared-store': { singleton: true, requiredVersion: '^3.0.0' },
}
```

This gives you a single source of truth with no sync lag. But it recreates the exact coupling problem independent deployment was supposed to eliminate. If the store's shape changes, **every** consuming micro-frontend must update in lockstep — effectively a distributed monolith with extra steps.

This pattern is justified in two cases only. The first is when the micro-frontends already deploy in lockstep: one team, one release cycle. The second is when the store's contract is treated with the same rigor as a versioned public API.

**Option B — an isolated store, synced via pub/sub.** Each micro-frontend owns its own local state. Changes are broadcast over the event bus from pattern 1, and each recipient decides for itself how to fold that into its own store.

```ts
// catalog-mfe: its own local store, nothing shared directly
window.dispatchEvent(
  new CustomEvent('catalog:item-selected', { detail: { sku: 'ABC-123' } }),
);

// checkout-mfe: receives the event and decides how to update its own store
window.addEventListener('catalog:item-selected', (event) => {
  const { sku } = (event as CustomEvent<{ sku: string }>).detail;
  // checkoutStore's shape is checkout's private detail
  checkoutStore.dispatch(addItemToCart(sku));
});
```

This is more resilient to independent deployment. Each micro-frontend's internal store shape is a private implementation detail, and the only contract is the wire format of the event.

## 3. Props/callbacks passed down from the host shell

When the host directly mounts a micro-frontend (not just route-based composition, but explicit component embedding), it can pass callback functions as the communication channel:

```tsx
<CheckoutApp
  onOrderComplete={(orderId) => router.push(`/confirmation/${orderId}`)}
/>
```

**Strengths:** type-safe (if the micro-frontend exports proper TS types for its props), the contract is explicit and discoverable right in the component's signature.

**Weaknesses:** only works when the host directly controls mounting. It doesn't help two "sibling" micro-frontends communicate directly, without the host acting as an intermediary. The host also becomes coupled to every remote's prop interface. That is the same versioning problem [Module Federation: How It Actually Works Under the Hood](./03-module-federation-deep-dive.md) describes for shared dependencies.

## 4. URL/query params — the "dumbest but most robust" channel

```txt
/catalog/item/42?returnUrl=/checkout&promoCode=SUMMER20
```

**Strengths:**

- Survives a full page reload.
- Works trivially across an iframe boundary, with no `postMessage` needed.
- Is compatible with the server-side composition from [Integration Approaches](./02-integration-approaches.md).
- Is completely framework-agnostic.
- Requires no shared runtime dependency between the parts at all.

**Weaknesses:** limited to serializable primitives, clutters the URL, unsuited to high-frequency updates (e.g., character-by-character form input), can't pass a function.

**When to prefer it:** handing off state during navigation, as when the host takes the user from the catalog to checkout with a selected item. Prefer it also for any state that should survive a reload, or be directly linkable anyway.

## Anti-pattern: directly importing a sibling remote's internals

This is the single most common mistake candidates make in micro-frontend interviews. It is a direct consequence of years of habit composing ordinary React components.

Inside a single SPA, importing anything from anywhere is normal and safe, because all the code is compiled and tested together. Developers instinctively carry that same mental model across the micro-frontend boundary, and it breaks the architecture itself.

```ts
// ❌ ANTI-PATTERN: reaching into a sibling remote's internal implementation
import { cartStore } from 'catalog/src/internal/cartStore';
// this is not a deliberately exposed public contract —
// just a path that happens to be reachable through exposes

// ✅ Correct: only consume what's explicitly exposed as the module's public contract
// deliberately exposed, versioned independently
import { getCartSummary } from 'catalog/PublicApi';
```

Why is this dangerous specifically because it's hidden? A change to `cartStore`'s internal shape in the catalog team doesn't break a single test or a single build — neither catalog's nor checkout's. Their builds happen independently and never see each other's code directly.

The breakage only shows up in the user's browser, at runtime, when checkout's bundle executes alongside the new version of catalog's bundle. That is exactly the time and place where it's hardest to catch.

**The rule:** only import what is explicitly, deliberately exposed as a public contract. That is the frontend equivalent of a microservice's public API over REST (representational state transfer) or gRPC.

Treat that exposed surface with the same discipline as any public API: versioning, documentation, backward compatibility, and a deprecation policy. [Deployment, Versioning, and Testing](./07-deployment-versioning-and-testing.md) covers that discipline.

## Summary table of channels

| Channel | Coupling | Type safety | Survives reload | When to use |
|---|---|---|---|---|
| Event bus | Loose | Weak (needs a contract package) | No | Pub/sub notifications: cart updated, user logged out |
| Shared store instance | Tight | Strong (shared code) | No | Only when the micro-frontends deploy in lockstep |
| Host props/callbacks | Medium (through the host) | Strong | No | Navigation and actions orchestrated by the host |
| URL/query params | None or loose | None (strings) | Yes | State handoff during navigation, deep links |

## Common interview traps

- **"Micro-frontends can communicate the same way React components do — just import whatever you need"** — this is the section's central anti-pattern. Directly importing a sibling remote's internal implementation creates hidden coupling. Neither team's build nor test suite catches it — only the user's browser at runtime.

- **"A shared store instance is the best solution because it's the simplest"** — simplest to develop against, yes. But it recreates the coupling problem independent deployment was meant to eliminate. A change to the store's shape requires every consumer to update in lockstep.

- **"An event bus doesn't need a contract — it's just a string and an object"** — it needs one. Without a separate versioned package for event names and payload types, an event bus becomes a hidden, undocumented API. That API is just as easy to break with an uncoordinated change as a direct import is.

- **"URL/query params are too primitive a channel to take seriously"** — that is an underestimation. This is often the most robust channel, precisely because it requires no shared runtime dependency between the parts at all. It also survives a page reload naturally.

- **"Host props/callbacks work for any pair of micro-frontends"** — they only work when the host directly mounts the component. For two "sibling" micro-frontends independently mounted by route, you need either the host acting as an explicit intermediary or one of the other three channels.
