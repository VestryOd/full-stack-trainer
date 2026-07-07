# Integration Approaches

## The comparison axis: who resolves what, and when

Every micro-frontend integration approach answers the same underlying question differently: **at what point is it decided which code, at which version, ends up where — and who makes that decision?** This is the axis interviewers actually want you to compare approaches on — not "which is best," but "when does resolution happen":

```txt
Build time                    Request time                  Runtime (browser)
(on the host team's CI)        (on the server/edge per request) (as the user's JS executes)
       │                              │                               │
       ▼                              ▼                               ▼
An npm package is compiled     The server/edge assembles       The browser fetches remoteEntry.js
into the host's single bundle  HTML fragments into one page    or resolves an import map at the
ahead of time, before deploy   on every incoming request       moment the user navigates
```

The further right on this axis, the later the decision is made — which means more flexibility (you can change a remote's version without rebuilding the host), but also more risk that resolution fails or duplicates exactly at the moment the user is looking at the screen.

## 1. Build-time integration (npm packages)

Each micro-frontend is published as a versioned npm package. The host installs the version it wants and imports it like a regular dependency — **at the host's own build time**.

```json
// host-app/package.json
{
  "dependencies": {
    "@company/checkout-mfe": "^2.3.0",
    "@company/catalog-mfe": "^1.8.1"
  }
}
```

```tsx
// host-app/src/App.tsx
import { CheckoutWidget } from '@company/checkout-mfe';
// Resolved by the HOST's compiler at the host's own build time —
// just like any regular npm import.

export function App() {
  return <CheckoutWidget />;
}
```

**Who resolves, and when:** the host's bundler, during the host's own `build`. No runtime magic — it's a plain import of a compiled package.

**Strengths:** as simple as it gets, full type safety (ordinary `.d.ts`), tree-shaking works normally, no network requests at runtime, no risk of a React version mismatch in the user's browser — every dependency is pinned at the host's build step.

**Weaknesses — and here's where a common confusion lives:** the checkout team can publish a new version of their package whenever they want (that's independent development), but until the host bumps `package.json` and rebuilds/redeploys its own app, the user won't see the new version. Build-time integration gives you **independent development and versioning**, but not **independent deployment of the running application** — the host's deploy remains the bottleneck. If the organization's actual pain is waiting on the host's release window, this approach doesn't solve it.

## 2. Server-side composition (Server-Side Includes / template composition)

Composition happens **on the server or at the edge, on every incoming request**. A composition layer (a reverse proxy, an edge function, or a dedicated "compositor" service such as Tailor.js in the Node ecosystem) requests an HTML fragment from each micro-frontend's own server and stitches them into a single page before it reaches the browser.

```txt
                    ┌──────────────────────────────┐
Browser request ──► │  Compositor (edge/reverse      │
                    │  proxy, e.g. Tailor.js)         │
                    └──────────────────────────────┘
                            │           │           │
                            ▼           ▼           ▼
                     Header MFE   Checkout MFE   Footer MFE
                     (own server) (own server)    (own server)
                     returns       returns          returns
                     an HTML       an HTML          an HTML
                     fragment      fragment         fragment
                            │           │           │
                            ▼           ▼           ▼
                     The compositor stitches the fragments into one
                     HTML document and returns ONE page to the browser
```

```nginx
# Edge composition via Server Side Includes (SSI) in nginx
location / {
    ssi on;
}
```

```html
<!-- shell.html, served by the host server -->
<body>
  <!--# include virtual="/fragments/header" -->
  <!--# include virtual="/fragments/checkout" -->
  <!--# include virtual="/fragments/footer" -->
</body>
```

**Who resolves, and when:** the compositor (server/edge), on every HTTP request. This means each fragment's version can be changed independently and instantly — no rebuild of the other parts required — because the decision is made fresh on every request rather than once at host-build time.

**Strengths:** the page arrives at the browser already assembled — fast TTFB, works even with JS disabled on the client (progressively enhanceable), excellent for SEO and content critical to the first paint.

**Weaknesses:** requires composition infrastructure (an edge layer or a dedicated service), interactivity inside a fragment (client JS, hydration) is each fragment's own concern, and coordinating behavior across fragments on the client is harder than with client-side composition.

## 3. Iframes — the "safe but bad" default

An iframe is the only way to get true isolation of JS, CSS, and the DOM: each iframe is a separate browsing context with its own `window` global, its own DOM tree, its own styles. Nothing "leaks" between parent and iframe without an explicit `postMessage`.

```html
<!-- host shell -->
<iframe src="https://checkout.company.com/widget" title="Checkout"></iframe>
```

```ts
// The only communication channel is postMessage. No direct DOM/state access.
window.addEventListener('message', (event) => {
  if (event.origin !== 'https://checkout.company.com') return; // always check origin
  if (event.data.type === 'CHECKOUT_COMPLETE') {
    // update host state
  }
});
```

**Who resolves, and when:** the browser, at the moment `<iframe src>` loads — a fully independent navigation context, with no dependency resolution between host and iframe happening at all (that's exactly what the isolation buys you).

**Why it's a "default, but a bad one":**

- **The isolation tax.** The very thing that makes an iframe safe (a fully separate context) makes sharing common design-system CSS, fonts, and global styles nearly impossible without duplication — every iframe loads its own styles from scratch.
- **The UX tax.** Nested scrollbars, resizing the iframe to fit its content is a known hack (`ResizeObserver` + `postMessage`), focus and tab navigation don't naturally flow "through" the boundary, printing the page often breaks.
- **Routing and deep-linking pain.** The browser's address bar URL doesn't reflect state inside the iframe on its own — if the user is at step 3 of checkout inside an iframe and reloads the page or copies the link, state is lost unless you explicitly sync it via `history.pushState` and `postMessage`. The browser's back button doesn't behave the way the user expects by default.

**When an iframe is the right call, not a compromise.** When isolation is a requirement, not a side effect: embedding a widget from an untrusted third-party vendor (a payment form, a chat widget, an ad), where you **deliberately** don't want that code to have access to the DOM and cookies of the rest of the page. In that case, an iframe's downsides are exactly the price you're willing to pay for a real sandbox.

## 4. Client-side runtime integration

Composition happens **in the user's browser, at JS execution time** — usually when navigating to a route that needs a specific micro-frontend.

### Module Federation (Webpack 5 / Rspack)

At runtime, the host fetches the remote application's `remoteEntry.js` and requests a specific exposed module from it. The full mechanics are covered in article 03 — what matters here is that **resolution happens in the browser, at the moment the module is requested**, including reconciling shared dependency versions (React, etc.) between host and remote.

```ts
// host: dynamically loading a remote module during navigation
const CheckoutApp = React.lazy(() => import('checkout/CheckoutApp'));
```

### single-spa

A framework-agnostic orchestrator: a root config registers a set of "applications," each with its own activity function (when this application should be mounted, usually based on the route), and each application is a separate bundle that single-spa mounts/unmounts through its own lifecycle. Applications can be built with different frameworks (React, Angular, Vue) simultaneously on the same page.

```ts
// root-config.js
registerApplication({
  name: '@company/checkout',
  app: () => System.import('@company/checkout'),
  activeWhen: (location) => location.pathname.startsWith('/checkout'),
});
start();
```

### Native ESM + import maps

No bundler-specific runtime at all: the browser natively resolves the import graph, and an **import map** lets you remap where a bare specifier (`"react"`) points — to a CDN URL with a specific version.

```html
<script type="importmap">
{
  "imports": {
    "react": "https://cdn.company.com/react@18.2.0/index.js",
    "checkout-mfe": "https://cdn.company.com/checkout-mfe@2.3.0/index.js"
  }
}
</script>
<script type="module">
  import { CheckoutWidget } from 'checkout-mfe'; // resolved by the browser via the import map
</script>
```

**What all three share:** resolution happens on the client, which means it can be changed without rebuilding the host (update the import map or the remote's manifest and everyone gets the new version on the next load) — but it can also break on the client, in front of a live user, with no single point where the error can be caught before it reaches production.

## Summary table

```txt
┌───────────────────┬─────────────────┬──────────────────┬───────────────────┬──────────────────┐
│                    │ Build-time      │ Server-side      │ Iframe             │ Client runtime    │
│                    │ (npm package)   │ (SSI/compositor) │                    │ (MF/single-spa/ESM)│
├───────────────────┼─────────────────┼──────────────────┼───────────────────┼──────────────────┤
│ When resolved      │ Host's build    │ Every HTTP request│ Iframe load        │ Browser runtime   │
├───────────────────┼─────────────────┼──────────────────┼───────────────────┼──────────────────┤
│ Isolation          │ None (shared    │ None on the client │ Full (separate    │ Partial (shared   │
│                    │ bundle)         │ (shared DOM)      │ browsing context)  │ DOM, JS realm)     │
├───────────────────┼─────────────────┼──────────────────┼───────────────────┼──────────────────┤
│ Real deploy        │ Development     │ Yes, per-request  │ Yes, fully         │ Yes, per-load      │
│ independence       │ only            │                   │                    │                    │
├───────────────────┼─────────────────┼──────────────────┼───────────────────┼──────────────────┤
│ Shared CSS/fonts   │ Trivial         │ Needs discipline  │ Practically        │ Needs discipline   │
│                    │                 │                   │ impossible without │ (article 06)       │
│                    │                 │                   │ duplication        │                    │
├───────────────────┼─────────────────┼──────────────────┼───────────────────┼──────────────────┤
│ SEO / no-JS        │ Same as host    │ Excellent         │ Poor               │ Poor without SSR   │
├───────────────────┼─────────────────┼──────────────────┼───────────────────┼──────────────────┤
│ Typical use case   │ Internal team   │ Content-heavy     │ Untrusted          │ Many teams, SPA,   │
│                    │ library         │ pages (media,     │ third-party widget │ mixed frameworks   │
│                    │                 │ e-commerce landing)│                   │                    │
└───────────────────┴─────────────────┴──────────────────┴───────────────────┴──────────────────┘
```

## Common interview traps

- **"Micro-frontends always mean Module Federation"** — Module Federation is just one of four real approaches, and not always the right one. Server-side composition is often better for content-heavy pages; iframes are the only sound choice for untrusted third-party code.

- **"Iframes are always bad, modern approaches replaced them"** — an iframe remains the right choice precisely when you need real isolation from untrusted code (third-party widgets, embedded payment forms). The iframe's downsides (UX, routing) are the price of a real sandbox, not a sign of an outdated tool.

- **"A versioned npm package already gives you full micro-frontends"** — build-time integration gives you development independence but not deployment independence for the running application: the user won't see the new version until the host rebuilds and redeploys. This solves half of the organizational problem, not all of it.

- **"All approaches solve the shared-dependency problem equally"** — no: the later resolution happens (the closer to browser runtime), the sharper the question of reconciling React, design-system, and router versions across independently deployed parts becomes — a problem specific to client-side runtime integration, covered in depth in article 03.

- **"You pick one correct approach for the whole product"** — in practice, mature organizations combine approaches: server-side composition for content pages (SEO-critical), client-side runtime for interactive SPA sections, iframes selectively for third-party embeds. That's not a sign of an immature architecture — it's a deliberate choice matched to the different requirements of different parts of the product.
