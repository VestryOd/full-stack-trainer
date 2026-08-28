# Routing and Navigation Across Micro-Frontends

## Who owns the router

There are two poles, and almost every real system is a hybrid of the two.

**The host owns the router entirely.** A single router instance (e.g., React Router in the shell app) knows every top-level route and decides which micro-frontend to mount for which path. The micro-frontend takes over control only once it's already inside its own segment.

**Each micro-frontend owns its own router.** The host knows nothing about the internal route structure of a given micro-frontend. It only knows which path prefix activates that micro-frontend. In single-spa that prefix rule is called `activeWhen`.

In practice, the hybrid dominates: **the host owns top-level segmentation; each remote owns its own subtree.**

| Host route | Mounts | Everything past this belongs to |
|---|---|---|
| `/catalog/*` | `CatalogApp` | the catalog team |
| `/checkout/*` | `CheckoutApp` | the checkout team |
| `/account/*` | `AccountApp` | the account team |

```txt
Inside CheckoutApp — a separate remote, its own repository:
  /checkout/cart
  /checkout/payment
  /checkout/confirmation
```

Those three paths are fully owned by the checkout team, and the host knows nothing about them. This gives real independence: the checkout team can add, remove, or rename any of its internal routes without a single change in the host. The host only knows the `/checkout/*` prefix — that's the minimal public contract.

## Keeping browser history in sync across micro-frontends

The browser has exactly **one** `window.history`. Two independent history stacks at once are physically impossible.

Now suppose the host and a remote each create their own router instance — say, each its own `<BrowserRouter>`. Both listen to `popstate`, and both call `pushState` on their own. The back button then behaves unpredictably, because one router overwrites the other's decision.

**The rule:** for any given transition, only one entity calls `history.pushState` or `replaceState`. Everyone else derives internal state from `window.location`, never the other way around.

In practice the host creates **one shared history instance**. A remote that needs its own internal routing reuses that instance. It does not create a new `<BrowserRouter>`.

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

single-spa reaches the same end by a different route. It patches `history.pushState` and `replaceState` globally, then broadcasts a custom event on every navigation. Every registered application keeps its own router inside, but all of them see that one event and reconcile against it. Nobody has to fight for control of `window.history`.

## Lazy-loading a remote at route-match time

Pair `React.lazy` with `Suspense` inside the route. That guarantees `remoteEntry.js` is fetched **only when** the user actually navigates to that route. It stays off the host's initial load:

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

Until the user visits `/checkout/*`, neither the checkout remote's `remoteEntry.js` nor its chunks go over the wire. The saving is the same as ordinary route-based code splitting in a single-page application. Only the thing being loaded differs: not a local chunk, but an entire independently deployed remote.

## What to do when a remote fails to load

There are two distinct kinds of failure to handle here.

**A network-level failure** — `remoteEntry.js` is unreachable. The cause can be a CDN (content delivery network) outage, a timeout, or a 404 after a version rollback. Without explicit handling, `import()` simply hangs or rejects with no meaningful fallback.

The fix is to wrap the load in a timeout. A rejected promise then reaches `React.lazy`, `Suspense` and `ErrorBoundary` predictably, instead of after an indeterminate wait:

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

**A render-level failure** — the remote loaded fine but crashed at runtime. One bug shipped by the checkout team is enough.

By default an uncaught error propagates up React's tree to the nearest error boundary. If no boundary sits **at each remote's mount point**, the nearest one is the shell's own top-level boundary. One team's bug then takes down **the entire product** for every user, including parts unrelated to the broken remote.

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
    // cross-remote observability — see the deployment article
    logToObservability('remote-mount-failed', error);
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

This is how the "deploy-level fault isolation" promise from [Micro-Frontends Fundamentals](./01-microfrontends-fundamentals.md) is actually delivered. Module Federation on its own only provides the mechanism for independent deployment. It does **not** hand you runtime fault isolation for free.

Miss one mount point, and one team's failure can still take down the entire application. The promised benefit stays theoretical until the host team deliberately builds it.

## Common interview traps

- **"A single router across the whole app means micro-frontends can't have their own nested routes"** — wrong. The dominant pattern in practice is a hybrid. The host owns only top-level segmentation (`/checkout/*`); everything inside that prefix belongs entirely to the remote.

- **"Every remote can freely create its own `<BrowserRouter>`"** — no. Two router instances controlling the same `window.history` at once make the back button and navigation unpredictable. What you need is one shared history instance, or a global sync mechanism as in single-spa. Independent routers, each convinced it owns the URL, do not work.

- **"Since Module Federation gives independent deployment, one remote's failure automatically doesn't affect the others"** — deployment independence does not equal runtime fault isolation. Without an explicit error boundary at every remote's mount point, one team's unhandled error propagates to the nearest boundary. That boundary is usually the shell itself, and the whole product goes down with it.

- **"Route-based lazy loading happens automatically, `React.lazy` is enough"** — it is not. `React.lazy` needs a `Suspense` fallback wrapped around it and a timeout on the network request for `remoteEntry.js`. Without both, the user gets an indefinite hang or an unhandled exception whenever the remote's CDN is unreachable.

- **"Routing between micro-frontends is a purely technical detail, unrelated to organizational autonomy"** — it *is* the autonomy. A route boundary such as `/checkout/*`, owned entirely by one team, is the same separation of responsibility described in [Micro-Frontends Fundamentals](./01-microfrontends-fundamentals.md). That boundary is the public contract between host and remote. It is what lets the checkout team change its internal pages without coordinating with anyone else.
