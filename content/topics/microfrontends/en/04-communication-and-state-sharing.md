# Cross-Micro-Frontend Communication and State Sharing

## Why this isn't the same as component communication in React

Inside a single SPA, communication between components is just props, context, a shared store. Every part of the application is compiled by the same bundler, built together, deployed together — importing from anywhere is safe, because TypeScript checks compatibility at build time, and any type mismatch blocks that one single deploy.

Across micro-frontends, that condition doesn't hold: each part is potentially built separately, deployed on its own schedule, possibly on a different framework, possibly executing in a different JS realm (if it's an iframe). A direct import between such parts is either technically impossible or creates hidden coupling that undermines the entire reason micro-frontends exist — deployment independence (see article 01). Hence the set of patterns below, each with its own cost.

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

**How to reduce the risk:** extract event names and payload types into a separate versioned package (e.g. `@company/mfe-events`) that each team pulls in as an ordinary dependency. This turns an event from "a string by convention" into an actual contract — the same contract-versioning discipline discussed in depth in article 07.

## 2. A shared store instance vs. an isolated store synced via pub/sub

**Option A — a shared store instance.** The literal same Redux/Zustand instance is shared between micro-frontends through Module Federation:

```js
// webpack.config.js — both host and remote declare the same shared dependency
shared: {
  '@company/shared-store': { singleton: true, requiredVersion: '^3.0.0' },
}
```

This gives you a single source of truth with no sync lag — but it recreates the exact coupling problem independent deployment was supposed to eliminate. If the store's shape changes, **every** consuming micro-frontend must update in lockstep — effectively a distributed monolith with extra steps. This pattern is justified only when the micro-frontends are already deployed in lockstep (one team, one release cycle), or when the store's contract is treated with the same rigor as a versioned public API.

**Option B — an isolated store, synced via pub/sub.** Each micro-frontend owns its own local state; changes are broadcast over the event bus (pattern 1), and each recipient decides for itself how to fold that into its own store.

```ts
// catalog-mfe: its own local store, nothing shared directly
window.dispatchEvent(new CustomEvent('catalog:item-selected', { detail: { sku: 'ABC-123' } }));

// checkout-mfe: receives the event and decides how to update ITS OWN store
window.addEventListener('catalog:item-selected', (event) => {
  const { sku } = (event as CustomEvent<{ sku: string }>).detail;
  checkoutStore.dispatch(addItemToCart(sku)); // checkoutStore's shape is checkout's private detail
});
```

This is more resilient to independent deployment: each micro-frontend's internal store shape is a private implementation detail; the only contract is the wire format of the event.

## 3. Props/callbacks passed down from the host shell

When the host directly mounts a micro-frontend (not just route-based composition, but explicit component embedding), it can pass callback functions as the communication channel:

```tsx
<CheckoutApp
  onOrderComplete={(orderId) => router.push(`/confirmation/${orderId}`)}
/>
```

**Strengths:** type-safe (if the micro-frontend exports proper TS types for its props), the contract is explicit and discoverable right in the component's signature.

**Weaknesses:** only works when the host directly controls mounting — it doesn't help two "sibling" micro-frontends communicate directly, without the host acting as an intermediary. The host also becomes coupled to every remote's prop interface — the same versioning problem as the shared-dependency issue in article 03.

## 4. URL/query params — the "dumbest but most robust" channel

```txt
/catalog/item/42?returnUrl=/checkout&promoCode=SUMMER20
```

**Strengths:** survives a full page reload, works trivially across an iframe boundary (no `postMessage` needed), is compatible with the server-side composition from article 02, is completely framework-agnostic, and requires no shared runtime dependency between the parts at all.

**Weaknesses:** limited to serializable primitives, clutters the URL, unsuited to high-frequency updates (e.g., character-by-character form input), can't pass a function.

**When to prefer it:** handing off state between micro-frontends during navigation (the host takes the user from the catalog to checkout with a selected item), any state that should survive a reload or be directly linkable anyway.

## Anti-pattern: directly importing a sibling remote's internals

This is the single most common mistake candidates make in micro-frontend interviews — and it's a direct consequence of years of habit composing ordinary React components. Inside a single SPA, importing anything from anywhere is normal and safe, because all the code is compiled and tested together. Developers instinctively carry that same mental model across the micro-frontend boundary — and it breaks the architecture itself.

```ts
// ❌ ANTI-PATTERN: reaching into a sibling remote's internal implementation
import { cartStore } from 'catalog/src/internal/cartStore';
// this is NOT a deliberately exposed public contract —
// just a path that happens to be reachable through exposes

// ✅ Correct: only consume what's explicitly exposed as the module's public contract
import { getCartSummary } from 'catalog/PublicApi'; // deliberately exposed, versioned independently
```

Why this is dangerous specifically because it's hidden: a change to `cartStore`'s internal shape in the catalog team doesn't break a single test or a single build — not catalog's, not checkout's — because their builds happen independently and never see each other's code directly. The breakage only shows up in the user's browser, at runtime, when checkout's bundle executes alongside the new version of catalog's bundle — exactly the time and place where it's hardest to catch.

**The rule:** only import what's explicitly, deliberately exposed as a public contract (the equivalent of a microservice's REST/gRPC API) — and treat that exposed surface with the same discipline as a public API: versioning, documentation, backward compatibility, a deprecation policy (see article 07).

## Summary table of channels

```txt
┌──────────────────────┬────────────────┬───────────────┬─────────────────┬───────────────────────┐
│ Channel               │ Coupling       │ Type safety     │ Survives reload │ When to use            │
├──────────────────────┼────────────────┼───────────────┼─────────────────┼───────────────────────┤
│ Event bus             │ Loose           │ Weak (needs a  │ No              │ Pub/sub notifications  │
│                       │                 │ contract       │                 │ (cart updated, user    │
│                       │                 │ package)        │                 │ logged out)             │
├──────────────────────┼────────────────┼───────────────┼─────────────────┼───────────────────────┤
│ Shared store instance │ Tight           │ Strong          │ No              │ Only when MFEs deploy  │
│                       │                 │ (shared code)   │                 │ in lockstep             │
├──────────────────────┼────────────────┼───────────────┼─────────────────┼───────────────────────┤
│ Host props/callbacks  │ Medium (via     │ Strong          │ No              │ Host-orchestrated      │
│                       │ the host)       │                 │                 │ navigation/actions      │
├──────────────────────┼────────────────┼───────────────┼─────────────────┼───────────────────────┤
│ URL/query params      │ None/loose      │ None (strings)  │ Yes             │ State handoff during   │
│                       │                 │                 │                 │ navigation, deep-linking│
└──────────────────────┴────────────────┴───────────────┴─────────────────┴───────────────────────┘
```

## Common interview traps

- **"Micro-frontends can communicate the same way React components do — just import whatever you need"** — this is the section's central anti-pattern. Directly importing a sibling remote's internal implementation creates hidden coupling that isn't caught by either team's build or test suite — only by the user's browser at runtime.

- **"A shared store instance is the best solution because it's the simplest"** — simplest to develop against, but it recreates the coupling problem independent deployment was meant to eliminate: a change to the store's shape requires every consumer to update in lockstep.

- **"An event bus doesn't need a contract — it's just a string and an object"** — without a separate versioned package for event names and payload types, an event bus becomes a hidden, undocumented API that's just as easy to break with an uncoordinated change as a direct import is.

- **"URL/query params are too primitive a channel to take seriously"** — an underestimation: this is often the most robust channel precisely because it requires no shared runtime dependency between the parts at all, and it naturally survives a page reload.

- **"Host props/callbacks work for any pair of micro-frontends"** — they only work when the host directly mounts the component. For two "sibling" micro-frontends independently mounted by route, you need either the host acting as an explicit intermediary or one of the other three channels.
