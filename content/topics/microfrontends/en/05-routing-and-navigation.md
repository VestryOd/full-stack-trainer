# Routing and Navigation Across Micro-Frontends

## Who owns the router

There are two poles, and almost every real system is a hybrid of the two.

**The host owns the router entirely.** A single router instance (e.g., React Router in the shell app) knows every top-level route and decides which micro-frontend to mount for which path. The micro-frontend takes over control only once it's already inside its own segment.

**Each micro-frontend owns its own router.** The host knows nothing about the internal route structure of a given micro-frontend — only which path prefix it should activate that micro-frontend for (in single-spa terms, `activeWhen`).

In practice, the hybrid dominates: **the host owns top-level segmentation; each remote owns its own subtree.**

```txt
Host:
  /catalog/*   → mounts CatalogApp     (everything past this is the catalog team's concern)
  /checkout/*  → mounts CheckoutApp    (everything past this is the checkout team's concern)
  /account/*   → mounts AccountApp     (everything past this is the account team's concern)

Inside CheckoutApp (a separate remote, its own repository):
  /checkout/cart
  /checkout/payment
  /checkout/confirmation
  ← fully owned by the checkout team; the host knows nothing about these paths
```

This gives real independence: the checkout team can add, remove, or rename any of its internal routes without a single change in the host. The host only knows the `/checkout/*` prefix — that's the minimal public contract.

## Keeping browser history in sync across the MFE boundary

The browser has exactly **one** `window.history` — it's physically impossible to have two independent history stacks at once. If both the host and a remote create their own independent router instance (say, each its own `<BrowserRouter>`), both will listen to `popstate` and try to call `pushState` independently — the result: the back button behaves unpredictably, one router overwrites the other's decision.

**The rule:** only one entity should call `history.pushState`/`replaceState` for any given transition; everyone else must derive their internal state from `window.location`, not the other way around.

In practice this means: the host creates **one shared history instance**, and a remote, when it needs its own internal routing, reuses that instance instead of creating a new `<BrowserRouter>`.

```ts
// host: one shared history instance for the whole application
import { createBrowserHistory } from 'history';
export const sharedHistory = createBrowserHistory();
```

```tsx
// remote (CheckoutApp): reuses the SHARED history instance from the host,
// instead of creating its own <BrowserRouter>
import { Router } from 'react-router-dom';
import { sharedHistory } from 'host/sharedHistory'; // exposed via Module Federation

export function CheckoutApp() {
  return (
    <Router location={sharedHistory.location} navigator={sharedHistory}>
      <Routes>
        <Route path="/checkout/cart" element={<Cart />} />
        <Route path="/checkout/payment" element={<Payment />} />
      </Routes>
    </Router>
  );
}
```

single-spa solves the same problem differently — but toward the same end: it patches `history.pushState`/`replaceState` globally and broadcasts a custom event on every navigation, so every registered application (each with its own router inside) sees the same navigation event and reconciles against it, instead of independently fighting for control of `window.history`.

## Lazy-loading a remote at route-match time

The combination of `React.lazy` + `Suspense` with routing is the natural way to guarantee that `remoteEntry.js` is only fetched **when** the user actually navigates to that route — not on the host's initial load:

```tsx
const CheckoutApp = React.lazy(() => import('checkout/CheckoutApp'));

<Routes>
  <Route
    path="/checkout/*"
    element={
      <Suspense fallback={<PageSkeleton />}>
        <CheckoutApp />
      </Suspense>
    }
  />
</Routes>
```

Until the user visits `/checkout/*`, neither the checkout remote's `remoteEntry.js` nor its chunks go over the wire — the same savings as ordinary route-based code splitting in an SPA, except the thing being loaded isn't a local chunk but an entire independently deployed remote.

## What to do when a remote fails to load

There are two distinct kinds of failure to handle here.

**A network-level failure** — `remoteEntry.js` is unreachable (the CDN is down, a timeout, a 404 after a version rollback). Without explicit handling, `import()` simply hangs or rejects without a meaningful fallback. The fix is to wrap the load in a timeout so a rejected promise reaches `React.lazy`/`Suspense`/`ErrorBoundary` predictably, rather than after an indeterminate wait:

```ts
function loadRemoteWithTimeout<T>(importPromise: Promise<T>, ms = 5000): Promise<T> {
  return Promise.race([
    importPromise,
    new Promise<T>((_, reject) =>
      setTimeout(() => reject(new Error('Remote load timed out')), ms),
    ),
  ]);
}

const CheckoutApp = React.lazy(() =>
  loadRemoteWithTimeout(import('checkout/CheckoutApp')),
);
```

**A render-level failure** — the remote loaded fine but crashed at runtime (a bug shipped by the checkout team). Without isolation, an uncaught error inside one remote's tree propagates up through React's tree, by default, to the nearest error boundary — and if none is placed **at each remote's mount point**, the nearest one turns out to be the shell's own top-level boundary, meaning one team's bug takes down **the entire product** for every user, including parts entirely unrelated to the broken remote.

```tsx
class RemoteErrorBoundary extends React.Component<
  { fallback: React.ReactNode; children: React.ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    logToObservability('remote-mount-failed', error); // see article 07 on cross-MFE observability
  }

  render() {
    return this.state.hasError ? this.props.fallback : this.props.children;
  }
}
```

```tsx
<Route
  path="/checkout/*"
  element={
    <RemoteErrorBoundary fallback={<CheckoutUnavailableBanner />}>
      <Suspense fallback={<PageSkeleton />}>
        <CheckoutApp />
      </Suspense>
    </RemoteErrorBoundary>
  }
/>
```

This is the technical delivery of the "deploy-level fault isolation" promise made in article 01. Module Federation by itself only provides the mechanism for independent deployment — it does **not** automatically provide runtime fault isolation. If the host hasn't placed an error boundary at every remote's mount point, one team's failure can still take down the entire application — the promised benefit stays purely theoretical until the host team deliberately builds it.

## Common interview traps

- **"A single router across the whole app means micro-frontends can't have their own nested routes"** — wrong. The pattern that dominates in practice is a hybrid: the host owns only top-level segmentation (`/checkout/*`), and everything happening within that prefix belongs entirely to the remote.

- **"Every remote can freely create its own `<BrowserRouter>`"** — if two independent router instances both try to control the same `window.history` at once, the back button and navigation start behaving unpredictably. What you need is one shared history instance (or a global sync mechanism, as in single-spa), not independent routers each convinced it owns the URL.

- **"Since Module Federation gives independent deployment, one remote's failure automatically doesn't affect the others"** — deployment independence does not equal runtime fault isolation. Without an explicit error boundary at every remote's mount point, one team's unhandled error propagates up to the nearest boundary — usually the shell itself — and takes down the whole product.

- **"Route-based lazy loading happens automatically, `React.lazy` is enough"** — `React.lazy` without a `Suspense` fallback wrapped around it, and without handling a timeout on the network request for `remoteEntry.js`, leaves the user either with an indefinite hang or an unhandled exception when the remote's CDN is unreachable.

- **"Routing between micro-frontends is a purely technical detail, unrelated to organizational autonomy"** — a route boundary (`/checkout/*` belonging entirely to one team) is exactly the same separation of responsibility discussed in article 01: a clear route boundary is the public contract between host and remote, and it's precisely what lets the checkout team change its internal pages without coordinating with anyone else.
