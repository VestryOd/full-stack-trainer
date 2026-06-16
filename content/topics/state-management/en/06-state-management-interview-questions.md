# State Management — Interview Questions (Middle → Senior)

## How to use this cheat sheet

Each answer is a compressed version of what's covered in depth in the topic articles. In a senior interview, almost every question here is an opener, not the final question. The interviewer expects "why", "what are the trade-offs", and "show me a real scenario." Each group ends with **"Typical follow-ups"** to show where the conversation usually goes.

---

## Group 1: MobX — Reactivity Model

**1. How does MobX know which component to re-render when an observable changes?**

Runtime dependency tracking. When an `observer` component renders, MobX starts a "tracking context." Every read of an `observable` during that render is recorded as a dependency of this component. When any of those observables change, MobX schedules a re-render for exactly that component — and no other. This is why granularity is automatic: a component that only reads `store.total` will not re-render when `store.isLoading` changes, even if both are on the same store object.

---

**2. What is the difference between `makeObservable` and `makeAutoObservable`, and when does each fail?**

`makeObservable` requires you to list every field and its annotation explicitly. `makeAutoObservable` infers by convention: fields → `observable`, getters → `computed`, methods → `action`. `makeAutoObservable` fails with class inheritance — it cannot safely walk the prototype chain to collect annotations, so subclassing a `makeAutoObservable` class throws at runtime. For inheritance, use `makeObservable` in each class explicitly.

---

**3. Why does destructuring an observable object outside `observer` break reactivity?**

Because MobX registers a dependency only at the moment the property is *read inside a tracking context*. Destructuring extracts plain JavaScript values before the JSX is rendered — those reads happen outside the reactive render scope, so MobX never records the dependency. The resulting variables are snapshots, not live references.

```tsx
// ❌ reads happen before JSX — no dependency registered
const MyComponent = observer(({ store }: { store: CartStore }) => {
  const { total, itemCount } = store; // plain numbers, not reactive
  return <span>{total}</span>;        // re-render will NOT trigger on change
});

// ✅ reads happen inside JSX — inside the tracking context
const MyComponent = observer(({ store }: { store: CartStore }) => {
  return <span>{store.total} ({store.itemCount} items)</span>;
});
```

---

**4. What is `computed` — how does it differ from a regular getter, and when does it NOT recompute?**

A `computed` value is a memoized, lazily-evaluated derivation. It differs from a plain getter in three ways: (1) its result is cached until dependencies change; (2) if it has no observers (no component or reaction reads it), it goes "cold" and is not recomputed at all; (3) if its dependencies change but the *result* is the same value (e.g., a count that went from 3 to 3 after an add + remove), MobX does not notify observers — unlike a plain getter, which re-executes every time it is called.

---

**5. `autorun` vs `reaction` vs `when` — how do you choose?**

| | `autorun` | `reaction` | `when` |
|---|---|---|---|
| Runs immediately | ✅ yes | ❌ no | ❌ no |
| Gets previous value | ❌ no | ✅ yes | ❌ no |
| Self-disposes | ❌ no | ❌ no | ✅ yes |
| Returns Promise | ❌ no | ❌ no | ✅ yes |

Rule: `autorun` for side effects that must fire once immediately and on every change (sync document.title, localStorage). `reaction` for analytics or debounced saves where you need the previous value and don't want an initial fire. `when` for one-shot conditions: "wait until user is loaded, then do X."

---

**6. Why does `async/await` break MobX strict mode, and what are the two solutions?**

`async/await` compiles to a state machine where code after `await` runs in a new microtask tick — outside the original `action` context. In `enforceActions: 'always'` mode, any observable mutation outside an action throws. Solutions: (1) `runInAction(() => { ... })` — wrap each post-`await` mutation block manually; (2) `flow` — uses a generator with `yield` instead of `await`, and MobX automatically wraps each step after `yield` in an action. `flow` is idiomatic; it also supports cancellation via the returned `cancel()` function.

---

## Typical follow-ups (Group 1)

```txt
"What happens if you call a computed outside any observer?" →
  It calculates and returns a value — but without caching. It behaves
  like a plain getter: no memoization, no subscription, no auto-update.
  With computedRequiresReaction: true this throws, which catches bugs early.

"If two observer components read the same computed, how many
times does it recompute when the dependency changes?" →
  Once. computed is global to the store, not per-component.
  Both components receive the new cached value. This is a key
  performance advantage over useMemo (which is per-component instance).

"What memory leak does forgetting dispose() cause?" →
  MobX holds a reference from the observable's dependency list to the
  reaction. After component unmount, if dispose() is not called, the
  reaction keeps the component alive in the GC — it cannot be collected.
  In React Strict Mode this manifests as "Can't perform a state update
  on an unmounted component" warnings.
```

---

## Group 2: Redux / RTK — Data Flow

**7. Describe the complete Redux data flow from a button click to a DOM update.**

```txt
User clicks button
  → dispatch(action)          dispatches a plain object
  → Middleware chain          thunk, logger, etc. — each calls next(action)
  → Reducer(state, action)    pure function → returns new state object
  → Store.setState(newState)  store replaces its internal state reference
  → useSelector re-runs       for every subscribed component
  → React compares results    if selector result changed (by ===) → re-render
  → Component re-renders      with new data from the store
```

Every step is synchronous (except middleware like thunk that adds async). This deterministic, traceable flow is why Redux DevTools can replay any sequence of actions.

---

**8. What does `createSlice` generate, and why does mutating `state` inside it work?**

`createSlice` generates: (1) action type strings (`'cart/addItem'`); (2) action creator functions; (3) a reducer function. It wraps the reducer with Immer. Inside an Immer-wrapped reducer, `state` is a Proxy — any mutation you write (`state.items.push(item)`) is intercepted and produces a new immutable object. The actual Redux state object is never mutated. You can also return a new state value explicitly (for resets) — but not both mutate and return.

---

**9. `createAsyncThunk` — what is the difference between `rejectWithValue` and `throw`?**

Both cause the `rejected` case to fire, but they put data in different places:

```ts
// throw → action.error.message (SerializedError, limited type info)
// rejectWithValue(data) → action.payload (your typed data)

const fetchUser = createAsyncThunk<User, string, { rejectValue: string }>(
  'user/fetch',
  async (id, { rejectWithValue }) => {
    try {
      return await api.getUser(id);
    } catch (e) {
      // Use rejectWithValue for controlled, typed error payloads
      return rejectWithValue((e as Error).message);
    }
  }
);

// In extraReducers:
.addCase(fetchUser.rejected, (state, action) => {
  // action.payload is typed as string (your rejectValue type)
  state.error = action.payload ?? action.error.message;
})
```

---

**10. Why do selectors without `createSelector` cause unnecessary re-renders?**

`useSelector` compares the returned value with the previous by strict equality (`===`). If the selector creates a new object or array on every call (via `.filter()`, `.map()`, object literal), the reference is always different — the component re-renders on every Redux dispatch, even dispatches completely unrelated to its data.

```ts
// ❌ New array on every call → re-renders on every dispatch
const selectActiveUsers = (state: RootState) =>
  state.users.filter(u => u.isActive);

// ✅ Memoized — only recalculates when state.users changes
export const selectActiveUsers = createSelector(
  [(state: RootState) => state.users],
  (users) => users.filter(u => u.isActive)
);
```

---

**11. What does RTK Query's tag invalidation system do, and why is it better than manual cache management?**

Tags are labels that link queries (data providers) to mutations (data invalidators). When a mutation completes successfully, RTK Query automatically refetches all active queries that provided the invalidated tags. This eliminates the pattern of manually dispatching "refresh" actions after mutations — the cache is always consistent without coordination code.

```ts
endpoints: (builder) => ({
  getUsers: builder.query<User[], void>({
    providesTags: ['User'],         // this query's cache is tagged 'User'
  }),
  deleteUser: builder.mutation<void, string>({
    query: (id) => ({ url: `/users/${id}`, method: 'DELETE' }),
    invalidatesTags: ['User'],      // after delete, re-fetch all 'User' queries
  }),
}),
// No manual dispatch needed — getUsers refetches automatically after deleteUser
```

---

## Typical follow-ups (Group 2)

```txt
"Can you have two Redux stores in one app?" →
  Yes, technically. But the entire ecosystem (DevTools, react-redux
  hooks, RTK Query) assumes one store. Multiple stores means losing
  cross-store selectors, combined DevTools, and RTK Query cache.
  The real answer: use separate slices, not separate stores.

"What is Immer's limitation in RTK reducers?" →
  You cannot both mutate state AND return a value in the same case.
  If you return something, Immer ignores mutations. If you mutate,
  don't return (or return undefined). The common mistake is writing
  return state.items.push(item) — push returns the new length, not
  the state, so RTK replaces the entire state with a number.

"When would you NOT use RTK Query?" →
  When the backend uses WebSockets/SSE for real-time updates (RTK Query
  has experimental WebSocket support but it's not first-class).
  When you need fine-grained optimistic update logic that RTK Query's
  onQueryStarted doesn't model well. When the project already uses
  React Query and migration cost exceeds the benefit.
```

---

## Group 3: Zustand — API and Patterns

**12. What makes Zustand's re-render model different from React Context?**

Context re-renders every consumer when any value in the context object changes — there's no built-in selector. Zustand uses a subscription model with per-component selectors: each `useStore(selector)` call re-renders only when `selector(newState) !== selector(prevState)` (by `===`). Components are independent subscribers, not consumers of a shared context object.

```tsx
// Context: CartSummary re-renders when ANY field in CartContext changes
const CartSummary = () => {
  const ctx = useContext(CartContext); // subscribes to the whole context
  return <span>{ctx.items.length}</span>;
};

// Zustand: CartSummary re-renders ONLY when items.length changes
const CartSummary = () => {
  const count = useCartStore(state => state.items.length);
  return <span>{count}</span>;
};
```

---

**13. Why are action functions in Zustand stable references, and why does this matter for React?**

Functions defined inside the `create` callback are created once when the store is initialized and never re-created on state updates. This means they are safe to extract and pass as props or deps without `useCallback`, and they will not cause unnecessary re-renders in child components that receive them as props.

```tsx
// ✅ addItem is stable — won't cause ProductCard to re-render
const addItem = useCartStore(state => state.addItem);
<ProductCard onAdd={addItem} /> // no useMemo/useCallback needed
```

---

**14. What is the slices pattern in Zustand and when should you use it?**

The slices pattern splits a large store into `StateCreator` functions, each managing a domain slice, which are then spread into a single `create` call. It mirrors Redux's `combineReducers` without the boilerplate. Use it when: (1) the store exceeds ~5 actions/fields and becomes hard to navigate; (2) different team members own different domains; (3) cross-slice access is needed (each slice gets `get()` which reads the full store state). For small apps, a single flat `create` is simpler.

---

**15. What does the `persist` middleware do, and what is `partialize` for?**

`persist` wraps the store and synchronizes state with a storage backend (localStorage by default) on every update, and hydrates it on initialization. `partialize` is a function that selects *which* state fields to persist — it prevents sensitive data (auth tokens, passwords) or ephemeral UI state (isLoading, error) from being written to localStorage.

```ts
persist(
  (set) => ({ theme: 'light', token: null, isLoading: false }),
  {
    name: 'app-store',
    partialize: (state) => ({ theme: state.theme }), // only persist theme
    // token and isLoading are NOT written to localStorage
  }
)
```

---

## Typical follow-ups (Group 3)

```txt
"Can Zustand replace RTK Query?" →
  No — Zustand is client-state management (UI state, local data).
  RTK Query is server-state management (cache, deduplication, background
  refetch, invalidation). You can manage server data in Zustand
  (fetch + set) but you re-implement caching, deduplication, and
  invalidation manually. The right combo: Zustand + React Query/SWR.

"How do you test a Zustand store?" →
  Direct store API: const { getState, setState } = useMyStore.
  Reset between tests: setState(initialState, true) (replace: true).
  Test actions: getState().addItem(item); expect(getState().items).toHaveLength(1).
  No React, no render — store is a plain object.

"What does useShallow do and when is it needed?" →
  When you return an object from a selector: useStore(s => ({ a: s.a, b: s.b })).
  Without useShallow, a new object {} !== {} causes a re-render on every
  state update. useShallow does a shallow comparison of the object's keys,
  so re-render happens only when a or b actually changes.
```

---

## Group 4: Comparison and Trade-offs

**16. MobX uses mutable state. Redux uses immutable state. What are the practical consequences of each?**

**Mutable (MobX):** you write natural object mutations (`this.items.push(item)`); no need to spread deeply nested structures; easier to reason about for OOP developers. Consequence: you must use `action` to get batching; without strict mode, mutations can sneak in anywhere; time-travel debugging is harder because past states are not preserved.

**Immutable (Redux):** every change produces a new state object; the previous state is always preserved; time-travel is trivial (re-apply actions to initial state). Consequence: updating deeply nested objects requires spread chains or Immer; conceptually harder for developers from OOP backgrounds.

---

**17. How does each library handle derived/computed data?**

**MobX:** `computed` is a first-class citizen — lazy, cached globally, automatically subscribed. No manual memoization needed; if the inputs don't change, the result doesn't recompute, for all consumers simultaneously.

**Redux:** `createSelector` (Reselect) memoizes selectors. Memoization is per-selector-instance, not per-component. Must be created explicitly; if forgotten, each `useSelector` call with a new object/array causes re-renders.

**Zustand:** no built-in derived/computed concept. You write functions in the store (`getTotal: () => get().items.reduce(...)`) — they recalculate on every call. For memoization, combine with `createSelector` from Reselect or compute inline in the component with `useMemo`.

---

**18. A senior engineer says "we should use Redux for everything." How do you respond?**

Acknowledge the strengths Redux brings: audit trail, time-travel debugging, explicit data flow, large ecosystem. Then ask: "What specifically are we trying to solve?" If the answer is "we need predictable state management" — that's valid. If it's "we have complex server data" — RTK Query addresses that, but React Query might be simpler. If the team is small and the domain is not complex, the overhead of Redux's boilerplate (even with RTK) is a real cost with no payoff. The right answer is not "Redux everywhere" or "Redux never" — it's "Redux for problems Redux solves well."

---

**19. What is "server state" vs "client state" and why does it matter for choosing a library?**

**Server state:** data that lives on the server, is fetched asynchronously, can become stale, needs caching, deduplication, and background refresh. Examples: user list, product catalog, order history. Best managed by React Query, SWR, or RTK Query — libraries purpose-built for this.

**Client state:** data that lives only in the browser and has no server representation. Examples: modal open/closed, active tab, form draft, shopping cart (if not persisted). Best managed by Zustand, MobX, or even `useState` for local state.

Most apps need both. The mistake is managing server data in MobX/Zustand without a cache strategy — you re-implement React Query by hand, poorly.

---

**20. A React app has serious re-render performance issues. How do you diagnose and fix them depending on the state management library?**

**Diagnosis (always first):** React DevTools Profiler — find which components re-render, how often, and why. React Scan or `why-did-you-render` library for automatic annotations.

**Redux fix:** check selectors — are they returning new references? Add `createSelector`. Check `useSelector` usage — is it selecting the whole state? Split into field-specific selectors. Use `shallowEqual` for object selectors.

**MobX fix:** check if `observer` is wrapping the right component (the one that reads the data, not just the parent). Check for destructuring outside observer. Move `computed` closer to where derived data is calculated.

**Zustand fix:** check if components subscribe to the whole store vs. specific fields. Add granular selectors. Use `useShallow` for multi-field selectors.

---

## Typical follow-ups (Group 4)

```txt
"Which library has the best TypeScript support?" →
  Zustand — create<State>() infers everything from the type parameter.
  RTK is close — createSlice and createAsyncThunk are well-typed.
  MobX is good for classes but flow generators lose typing at yield.

"Can you use MobX and Redux in the same project?" →
  Technically yes. Practically: you've doubled the mental overhead
  and the bundle size. It might make sense during a migration, but
  as a steady state it's almost always a mistake.

"React Context is built-in — why use any library at all?" →
  Context + useReducer works for small apps with infrequent updates.
  It breaks down when: (1) many consumers re-render on unrelated changes
  (no selector granularity); (2) you need middleware, persistence, or
  DevTools; (3) the store needs to be accessed outside the React tree.
  Libraries solve these without you re-implementing them.
```

---

## Group 5: Advanced and Scenario-Based

**21. You have a shopping cart that must survive page refresh. How do you implement this in each library?**

**Zustand:** add `persist` middleware — one line, zero extra code. Optionally `partialize` to exclude transient fields. Hydration is automatic on store initialization.

**Redux/RTK:** use `redux-persist` library. Configure `persistConfig` with storage, whitelist/blacklist. Wrap the store with `persistStore`, wrap the app with `PersistGate`. More setup, but more control (nested persist, migrations).

**MobX:** implement manually — `autorun` that writes `JSON.stringify(store.serializableState)` to localStorage on every change; read and apply on store construction. Or use `mobx-persist` library.

Zustand wins on simplicity for this specific use case.

---

**22. Two async actions race-condition each other — how do you handle this in each library?**

**Redux/RTK:** `createAsyncThunk` with `signal` — pass `signal` to `fetch`, call `promise.abort()` on the previous dispatch before starting a new one. Or in `extraReducers`, check `action.meta.requestId` against `state.currentRequestId` and discard stale results.

**MobX flow:** `flow` returns a cancellable object. Call `cancel()` on the previous run before starting a new one:

```ts
class SearchStore {
  private cancelPrev?: () => void;
  *search(q: string) { /* ... */ }

  startSearch(q: string) {
    this.cancelPrev?.();
    const run = this.search(q);
    this.cancelPrev = run.cancel;
  }
}
```

**Zustand:** no built-in mechanism. Use an `AbortController` in the async action, abort on the next call, or track a `requestId` counter and discard stale results.

---

**23. How would you implement undo/redo for a text editor's state in each library?**

The core mechanism: maintain a history array of states (or commands) and a pointer.

**Redux:** ideal fit — reducers are pure functions, state is immutable. Store a `past: State[]`, `present: State`, `future: State[]`. On every action, push present to past. `UNDO` action: pop from past, push present to future. Redux DevTools time-travel does this for free during development.

**Zustand with Immer:** use the `temporal` middleware (`zundo` library) — wraps the store and automatically maintains undo/redo history. `useTemporalStore().undo()` and `.redo()`.

**MobX:** MobX actions are not serializable by default — undo/redo requires explicit snapshots (`getSnapshot`/`applySnapshot` from `mobx-state-tree`) or manually maintaining an action history and re-applying them.

---

**24. What is the "stale closure" problem in Zustand, and how does `get()` solve it?**

When an async action closes over `state` from the `set` callback, that `state` snapshot is stale by the time the async operation completes — other synchronous updates may have happened in between:

```ts
// ❌ Stale closure — state captured at the time addItem was called
addItem: (item) => {
  set((state) => {
    fetch('/api/cart').then(() => {
      // state here is stale — it was captured before the async call
      console.log(state.items); // may not reflect concurrent updates
    });
    return { items: [...state.items, item] };
  });
},

// ✅ get() reads the CURRENT state at the moment of the call
addItem: (item) => {
  set((state) => ({ items: [...state.items, item] }));
  fetch('/api/cart').then(() => {
    console.log(get().items); // always the current state
  });
},
```

---

**25. When is it worth migrating from one library to another, and what's the process?**

Migration is worth it when: (1) the current library's limitations are causing real, measurable pain (not just "I prefer X"); (2) the team is growing and boilerplate becomes a coordination burden; (3) a new capability is genuinely needed (e.g., time-travel debugging, RTK Query's caching).

Process: (1) identify the pain point precisely; (2) run both libraries in parallel — new features in the new library, existing code untouched; (3) migrate domain by domain, not a big-bang rewrite; (4) remove the old library only when no references remain. The most dangerous migration mistake: rewriting working code for architectural reasons while also delivering features — context switches multiply risk.

---

## Typical follow-ups (Group 5)

```txt
"React Server Components are becoming mainstream. How do they
change state management?" →
  RSC removes much of the server data fetching from the client.
  Data that previously lived in Redux/Zustand (user, products) now
  comes as props from the server component — no client store needed.
  Client state becomes: UI interactions only (modal, form, animation).
  Zustand/MobX fit RSC better than Redux — no Provider wrapper
  needed, no hydration mismatch issues.

"Is Zustand production-ready for a large enterprise app?" →
  Yes — it's used in production by large companies. "Large" doesn't
  mean "needs Redux." The question is whether the team needs
  Redux-level audit trail and tooling. If not, Zustand with slices
  scales fine. The misconception is equating bundle size or line count
  with production readiness.
```
