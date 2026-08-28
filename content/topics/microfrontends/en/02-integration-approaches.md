# Integration Approaches

## The comparison axis: who resolves what, and when

Every micro-frontend integration approach answers the same question differently. **At what point is it decided which code, at which version, ends up where? And who makes that decision?** That is the axis interviewers want you to compare approaches on. The question is not which approach is best, but when resolution happens:

```txt
Build time — on the host team's CI
  An npm package is compiled into the host's single bundle
  ahead of time, before deploy.
    │
    ▼
Request time — on the server or edge, per request
  The server assembles HTML fragments into one page on
  every incoming request.
    │
    ▼
Runtime — in the browser, as the user's JS executes
  The browser fetches remoteEntry.js, or resolves an
  import map, at the moment the user navigates.
```

The further down this list, the later the decision is made. Later means more flexibility: you can change a remote's version without rebuilding the host. Later also means more risk. Resolution can fail, or load a dependency twice, exactly while the user is looking at the screen.

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

**Strengths:**

- As simple as it gets.
- Full type safety through ordinary `.d.ts` files.
- Tree-shaking works normally.
- No network requests at runtime.
- No risk of a React version mismatch in the user's browser: every dependency is pinned at the host's build step.

**Weaknesses — and here's where a common confusion lives.** The checkout team can publish a new version of their package whenever they want, and that is independent development. But until the host bumps `package.json` and redeploys its own app, the user won't see the new version.

Build-time integration gives you **independent development and versioning**. It does not give you **independent deployment of the running application** — the host's deploy remains the bottleneck. If the organization's actual pain is waiting on the host's release window, this approach doesn't solve it.

## 2. Server-side composition (Server-Side Includes / template composition)

Composition happens **on the server or at the edge, on every incoming request**. The composition layer can be a reverse proxy, an edge function, or a dedicated "compositor" service such as Tailor.js in the Node ecosystem. It requests an HTML fragment from each micro-frontend's own server. It then stitches the fragments into a single page, before that page reaches the browser.

```txt
                    ┌──────────────────────────┐
Browser request ──► │ Compositor (edge/reverse │
                    │ proxy, e.g. Tailor.js)   │
                    └──────────────────────────┘
                            │               │               │
                            ▼               ▼               ▼
                       Header MFE     Checkout MFE     Footer MFE
                      (own server)    (own server)    (own server)
                        returns         returns         returns
                        an HTML         an HTML         an HTML
                        fragment        fragment        fragment

                            │               │               │
                            ▼               ▼               ▼
                    The compositor stitches the fragments into one
                    HTML page and returns it to the browser
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

**Who resolves, and when:** the compositor (server/edge), on every HTTP request. This means each fragment's version can be changed independently and instantly, with no rebuild of the other parts. The decision is made fresh on every request, not once at host-build time.

**Strengths:** the page arrives at the browser already assembled. That gives a fast TTFB (time to first byte), and it works even with JS disabled on the client. It is excellent for search engine optimization (SEO) and for content critical to the first paint.

**Weaknesses:**

- It requires composition infrastructure: an edge layer or a dedicated service.
- Interactivity inside a fragment (client JS, hydration) is each fragment's own concern.
- Coordinating behavior across fragments on the client is harder than with client-side composition.

## 3. Iframes — the "safe but bad" default

An iframe is the only way to get true isolation of JS, CSS and the DOM (document object model). Each iframe is a separate browsing context, with its own `window` global, its own DOM tree and its own styles. Nothing "leaks" between parent and iframe without an explicit `postMessage`.

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

**Who resolves, and when:** the browser, at the moment `<iframe src>` loads. That is a fully independent navigation context. No dependency resolution between host and iframe happens at all, and that is exactly what the isolation buys you.

**Why it's a "default, but a bad one":**

- **The isolation tax.** The very thing that makes an iframe safe is the fully separate context. That same separation makes sharing design-system CSS, fonts and global styles nearly impossible without duplication. Every iframe loads its own styles from scratch.
- **The user-experience tax.** You get nested scrollbars. Resizing the iframe to fit its content is a known hack, built on `ResizeObserver` plus `postMessage`. Focus and tab navigation don't flow "through" the boundary naturally. Printing the page often breaks.
- **Routing and deep-linking pain.** The browser's address bar doesn't reflect state inside the iframe on its own. Say the user is at step 3 of checkout inside an iframe, and then reloads the page or copies the link. That state is lost, unless you explicitly sync it via `history.pushState` and `postMessage`. The back button also doesn't behave the way the user expects by default.

**When an iframe is the right call, not a compromise.** When isolation is a requirement, not a side effect. That is the case when you embed a widget from an untrusted third-party vendor: a payment form, a chat widget, an ad. You **deliberately** don't want that code to reach the DOM and cookies of the rest of the page. In that case, an iframe's downsides are exactly the price of a real sandbox.

## 4. Client-side runtime integration

Composition happens **in the user's browser, at JS execution time** — usually when navigating to a route that needs a specific micro-frontend.

### Module Federation (Webpack 5 / Rspack)

At runtime, the host fetches the remote application's `remoteEntry.js` and requests a specific exposed module from it. [Module Federation: How It Actually Works Under the Hood](./03-module-federation-deep-dive.md) covers the full mechanics. What matters here is that **resolution happens in the browser, at the moment the module is requested**. That includes reconciling shared dependency versions, React among them, between host and remote.

```ts
// host: dynamically loading a remote module during navigation
const CheckoutApp = React.lazy(() => import('checkout/CheckoutApp'));
```

### single-spa

A framework-agnostic orchestrator. A root config registers a set of named applications. Each one gets its own activity function, which decides when that application should be mounted — usually based on the route. Each application is a separate bundle, which single-spa mounts and unmounts through its own lifecycle. Applications can use different frameworks (React, Angular, Vue) at the same time on one page.

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

No bundler-specific runtime at all. The browser natively resolves the import graph of ECMAScript modules (ESM). An **import map** lets you remap where a bare specifier (`"react"`) points — to a CDN (content delivery network) URL with a specific version.

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
  // resolved by the browser via the import map
  import { CheckoutWidget } from 'checkout-mfe';
</script>
```

**What all three share:** resolution happens on the client. That means it can be changed without rebuilding the host. Update the import map or the remote's manifest, and everyone gets the new version on the next load.

It also means resolution can break on the client, in front of a live user. There is no single point where the error can be caught before it reaches production.

## Summary table

| | Build-time (npm package) | Server-side (SSI — server-side includes) | Iframe | Client runtime (Module Federation, single-spa, ESM) |
|---|---|---|---|---|
| **When resolved** | Host's build | Every HTTP request | Iframe load | Browser runtime |
| **Isolation** | None (shared bundle) | None on the client (shared DOM) | Full (separate browsing context) | Partial (shared DOM, shared JS realm) |
| **Real deploy independence** | Development only | Yes, per request | Yes, fully | Yes, per load |
| **Shared CSS and fonts** | Trivial | Needs discipline | Practically impossible without duplication | Needs discipline, see [Styling and Isolation](./06-styling-and-isolation.md) |
| **Search ranking / no-JS** | Same as host | Excellent | Poor | Poor without SSR (server-side rendering) |
| **Typical use case** | Internal team library | Content-heavy pages: media, e-commerce landing | Untrusted third-party widget | Many teams, one single-page app, mixed frameworks |

## Common interview traps

- **"Micro-frontends always mean Module Federation"** — Module Federation is just one of four real approaches, and not always the right one. Server-side composition is often better for content-heavy pages; iframes are the only sound choice for untrusted third-party code.

- **"Iframes are always bad, modern approaches replaced them"** — an iframe remains the right choice when you need real isolation from untrusted code. Third-party widgets and embedded payment forms are the usual cases. The iframe's downsides in usability and routing are the price of a real sandbox, not a sign of an outdated tool.

- **"A versioned npm package already gives you full micro-frontends"** — build-time integration gives you development independence, but not deployment independence for the running application. The user won't see the new version until the host rebuilds and redeploys. This solves half of the organizational problem, not all of it.

- **"All approaches solve the shared-dependency problem equally"** — no. The later resolution happens, the sharper the question of reconciling React, design-system and router versions across independently deployed parts. That problem is specific to client-side runtime integration, and [Module Federation: How It Actually Works Under the Hood](./03-module-federation-deep-dive.md) covers it in depth.

- **"You pick one correct approach for the whole product"** — in practice, mature organizations combine them. Server-side composition goes to content pages, where search ranking matters. Client-side runtime goes to interactive single-page sections, and iframes are used selectively for third-party embeds. That is not a sign of an immature architecture. It is a deliberate choice, matched to the different requirements of different parts of the product.
