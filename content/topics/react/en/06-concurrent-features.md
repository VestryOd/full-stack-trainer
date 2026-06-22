# Concurrent Features

## What "concurrent rendering" actually changes

"Concurrent mode" is not a mode you opt into — it is the default behavior in React 18 when you use `createRoot`. The term means React can work on multiple renders simultaneously and can interrupt, pause, and resume work as priorities shift.

```txt
BEFORE REACT 18 (legacy mode):
  Every setState → synchronous render → DOM update.
  Once started, the render runs to completion.
  The browser is blocked for the entire duration.

REACT 18 (concurrent mode):
  setState → schedules work with a priority (lane)
  High-priority work interrupts low-priority renders.
  The browser gets control between Fiber chunks.
  Multiple versions of the UI can be "in flight" simultaneously.
```

For most day-to-day code the change is invisible — `useState`, `useEffect`, event handlers all work as before. Concurrent rendering becomes observable through the new APIs: `useTransition`, `useDeferredValue`, and `Suspense` for data.

---

## startTransition and useTransition

### The problem they solve

User input must be instantaneous. List filtering, search results, and navigation — these can lag slightly before the user notices. Before React 18 there was no way to express this distinction: every `setState` had the same urgency.

`startTransition` marks a state update as non-urgent (a *transition*). React renders the transition in the background without blocking the UI. If a higher-priority update arrives while the transition is rendering, React interrupts the transition, processes the high-priority update, then resumes or restarts the transition.

```tsx
import { startTransition, useTransition } from 'react';

// startTransition — standalone function, no hook needed:
function SearchBox({ onSearch }: { onSearch: (q: string) => void }) {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // Urgent: update the input field immediately
    setInputValue(e.target.value);

    // Non-urgent: the search results can lag behind
    startTransition(() => {
      onSearch(e.target.value);
    });
  };
  return <input onChange={handleChange} />;
}
```

`useTransition` is the hook version that also provides an `isPending` flag:

```tsx
function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Result[]>([]);
  const [isPending, startTransition] = useTransition();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setQuery(value);                       // urgent — updates immediately

    startTransition(() => {
      const filtered = heavyFilter(allData, value);
      setResults(filtered);                // non-urgent — can be interrupted
    });
  };

  return (
    <>
      <input value={query} onChange={handleChange} />
      {isPending && <Spinner />}           {/* shows while transition is pending */}
      <ResultList results={results} />
    </>
  );
}
```

`isPending` is `true` from the moment `startTransition` is called until the transition render commits. Use it to show a loading indicator on the *current* content (not a blank screen) while the new version renders in the background.

### What startTransition does NOT do

```tsx
// ❌ startTransition is NOT for async operations:
startTransition(async () => {
  const data = await fetchData(); // WRONG — the async part runs outside the transition
  setData(data);
});

// The transition ends when the synchronous part of the callback finishes.
// Awaited operations are NOT part of the transition.
// For async data, use Suspense + a data library (React Query, SWR) or React 19 Actions.
```

`startTransition` only affects synchronous state updates inside the callback. It marks them as low-priority — the computation still runs on the main thread, it can just be interrupted and restarted. It does not offload work to a web worker.

---

## useDeferredValue

`useDeferredValue` is the "consumer-side" alternative to `startTransition`. Instead of wrapping the state setter, you wrap the value that should be allowed to lag:

```tsx
function SearchResults({ query }: { query: string }) {
  const deferredQuery = useDeferredValue(query);
  // deferredQuery lags behind query.
  // During the lag, the previous deferredQuery value is used,
  // so the previous results are shown rather than a blank screen.

  const isStale = query !== deferredQuery; // true while the deferred render is pending

  return (
    <div style={{ opacity: isStale ? 0.5 : 1 }}>
      <ExpensiveList query={deferredQuery} />
    </div>
  );
}
```

### startTransition vs useDeferredValue — which to use

```txt
startTransition:
  Use when you CONTROL the state update (you own the setter).
  The setter is called inside startTransition.
  The transition starts the moment you call it.

useDeferredValue:
  Use when you DO NOT control the state update
  (the value comes from props, or a library, or parent state).
  You receive the value and defer it locally.
  React renders two versions: one with the current value (shown),
  one with the deferred value (computed in the background).
```

```tsx
// If you control the setter → startTransition:
const [results, setResults] = useState([]);
startTransition(() => setResults(filter(data, query)));

// If you receive the value from outside → useDeferredValue:
function Child({ query }: { query: string }) {
  const deferredQuery = useDeferredValue(query);
  return <ExpensiveList query={deferredQuery} />;
}
```

---

## Suspense — the full picture

Suspense was introduced for code splitting (`React.lazy`). React 18 expanded it to data fetching. The fundamental mechanic is the same:

```txt
A component "suspends" by throwing a Promise.
React catches the thrown Promise.
React shows the nearest Suspense boundary's fallback.
When the Promise resolves, React retries rendering the suspended component.
```

### Suspense with React.lazy (code splitting)

```tsx
const HeavyChart = React.lazy(() => import('./HeavyChart'));

function Dashboard() {
  return (
    <Suspense fallback={<Skeleton />}>
      <HeavyChart />  {/* suspends until the JS chunk is loaded */}
    </Suspense>
  );
}
```

`React.lazy` wraps a dynamic import. The first time `HeavyChart` renders, it throws a Promise. React shows `<Skeleton />`. When the import resolves, React re-renders `HeavyChart` — this time it doesn't throw, so React commits the result and the `<Skeleton />` disappears.

### Suspense with data libraries

React itself does not have a built-in data fetching mechanism that integrates with Suspense (outside of Server Components). Libraries like React Query and SWR implement the throw-a-Promise protocol:

```tsx
// With React Query (Suspense mode):
function UserProfile({ userId }: { userId: string }) {
  // If data is not yet available, this throws a Promise.
  // React shows the nearest Suspense fallback.
  // When the query resolves, React re-renders this component.
  const { data: user } = useSuspenseQuery({
    queryKey: ['user', userId],
    queryFn: () => fetchUser(userId),
  });

  return <div>{user.name}</div>; // always has data — no loading check needed
}

function Page() {
  return (
    <Suspense fallback={<ProfileSkeleton />}>
      <UserProfile userId="42" />
    </Suspense>
  );
}
```

The component's code becomes dramatically simpler: no `if (isLoading)`, no `if (error)` — the loading and error states are handled at the boundary level.

### Suspense boundary behavior

```tsx
// Multiple Suspense boundaries — fine-grained loading states:
function Dashboard() {
  return (
    <div>
      <Suspense fallback={<HeaderSkeleton />}>
        <Header />        {/* can suspend independently */}
      </Suspense>

      <Suspense fallback={<ChartSkeleton />}>
        <RevenueChart />  {/* can suspend independently */}
      </Suspense>

      <Suspense fallback={<TableSkeleton />}>
        <DataTable />     {/* can suspend independently */}
      </Suspense>
    </div>
  );
}
// Header, RevenueChart, DataTable all load in parallel.
// Each shows its own skeleton while loading.
// They reveal independently as their data arrives.
```

Without wrapping each in its own boundary, a single Suspense wrapper would show one fallback for the whole dashboard until ALL data is ready.

### SuspenseList (React 18 experimental)

`SuspenseList` coordinates the reveal order of multiple Suspense boundaries:

```tsx
import { SuspenseList } from 'react';

<SuspenseList revealOrder="forwards" tail="collapsed">
  <Suspense fallback={<Skeleton />}><Article id={1} /></Suspense>
  <Suspense fallback={<Skeleton />}><Article id={2} /></Suspense>
  <Suspense fallback={<Skeleton />}><Article id={3} /></Suspense>
</SuspenseList>
// revealOrder="forwards": articles reveal top-to-bottom, even if later ones load first.
// tail="collapsed": only show one skeleton at a time (for the next-to-reveal item).
```

---

## Transitions + Suspense together

The most powerful combination: navigate between pages without a jarring loading flash.

```tsx
function App() {
  const [page, setPage] = useState('home');
  const [isPending, startTransition] = useTransition();

  function navigate(to: string) {
    startTransition(() => setPage(to));
    // The new page might suspend (load data).
    // With startTransition: React keeps the current page visible
    // (with isPending=true) while the new page loads in the background.
    // Without startTransition: React would immediately show the Suspense fallback.
  }

  return (
    <>
      <nav>
        <button onClick={() => navigate('home')}>Home</button>
        <button onClick={() => navigate('profile')}>Profile</button>
        {isPending && <Spinner />}
      </nav>
      <Suspense fallback={<PageSkeleton />}>
        {page === 'home' ? <HomePage /> : <ProfilePage />}
      </Suspense>
    </>
  );
}
```

Without `startTransition`: clicking "Profile" immediately hides the current page and shows `<PageSkeleton />` — even if data loads in 50 ms, there's a visible flash.

With `startTransition`: the current page stays visible (Home) while Profile loads in the background. `isPending` is `true` so you can show a subtle indicator. When Profile is ready, it replaces Home in a single commit — no intermediate blank screen.

---

## useDeferredValue for avoiding Suspense fallbacks during updates

When a Suspense boundary's content is already showing (not the first load), and a state update causes it to suspend again, React has a choice: show the fallback again, or keep the stale content visible. The default behavior (without transitions) is to show the fallback:

```tsx
function ProductPage({ categoryId }: { categoryId: number }) {
  // When categoryId changes, ProductList suspends again.
  // Without deferring: immediate switch to fallback.
  // With deferred: keep showing previous category while new one loads.
  const deferredId = useDeferredValue(categoryId);

  return (
    <Suspense fallback={<ProductSkeleton />}>
      <ProductList categoryId={deferredId} />
    </Suspense>
  );
}
```

The `deferredId` lags behind `categoryId`. While `deferredId !== categoryId` (the deferred render is in progress), the Suspense boundary shows the previous `ProductList` — stale but visible — instead of the skeleton. When the new data arrives, `deferredId` catches up and the new products are shown.

---

## Common interview traps

**"Does useTransition make rendering faster?"**
No. `startTransition` does not speed up computation — the same work still runs on the main thread. It changes the *priority* of the work so the browser can handle higher-priority events (typing, clicking) without waiting for the transition render to complete. The total CPU time is the same or slightly higher (due to potential interrupts and restarts). The perceived performance improves because input is never blocked.

**"When does React show a Suspense fallback vs keep the existing content?"**
During the initial render (no content yet) → always shows fallback. During an update that causes a suspend: if the update is inside `startTransition` → React keeps existing content visible while the new version loads (no fallback shown). If the update is NOT wrapped in `startTransition` → React immediately switches to the fallback (because it treats the update as urgent and cannot show stale content for urgent updates).

**"Can you use Suspense without a data library?"**
Yes, but you have to implement the throw-a-Promise protocol manually. A data fetching function must throw a Promise on the first call, return the resolved value on subsequent calls (after the Promise resolved), and throw an Error if the request failed. In practice, everyone uses React Query, SWR, or Relay, because implementing a correct cache that integrates with Suspense is non-trivial.

**"What is the difference between isPending from useTransition and isLoading from React Query?"**
`isPending` (from `useTransition`) is true while React is computing the transition render — it reflects the render phase. It turns false the moment the transition commits. `isLoading` (from React Query) is true while the network request is in flight — it reflects the data fetching state. They can be true simultaneously (transition started, fetch in progress) or independently (transition done but fetch still running, or fetch done but React still rendering the result).

**"Is useDeferredValue the same as debouncing?"**
No. Debouncing delays the state update itself (the setter is not called until after a timeout). `useDeferredValue` receives the already-updated value and tells React to compute its render at a lower priority — the current render uses the previous deferred value while the new render completes in the background. `useDeferredValue` has no delay, no timer, and no dropped updates: React will always eventually render with the latest value.
