# State Management Comparison

## Different mental models — not different solutions to the same problem

The key mistake when choosing between MobX, Redux, and Zustand is treating them as interchangeable. They solve a similar problem but from fundamentally different worldviews.

### MobX — reactive graph: "declare data, the UI will follow"

```ts
// MobX: you describe DATA STRUCTURE and RELATIONSHIPS between values
// The framework tracks who read what and notifies subscribers automatically

class OrderStore {
  items: OrderItem[] = [];
  taxRate = 0.2;

  constructor() { makeAutoObservable(this); }

  get subtotal() { return this.items.reduce((s, i) => s + i.price * i.qty, 0); }
  get tax()      { return this.subtotal * this.taxRate; }
  get total()    { return this.subtotal + this.tax; }

  addItem(item: OrderItem) { this.items.push(item); }
}

// The dependency graph is built automatically:
// items → subtotal → tax → total
// Changing items → MobX recomputes subtotal, then tax and total
// and re-renders ONLY components that actually read the changed values
```

**Paradigm**: imperative OOP. Data is objects with methods. Changes happen through mutations (inside actions). Reactivity is hidden infrastructure.

### Redux/RTK — state machine: "explicit event flow → deterministic state"

```ts
// Redux: you describe EVENTS (actions) and STATE TRANSITIONS (reducers)
// State is a tree of immutable values. Only changeable through dispatch.

// Any state change is a response to a specific event
const orderSlice = createSlice({
  name: 'order',
  initialState: { items: [], taxRate: 0.2 } as OrderState,
  reducers: {
    itemAdded(state, action: PayloadAction<OrderItem>) {
      state.items.push(action.payload); // Immer — immutable under the hood
    },
    taxRateChanged(state, action: PayloadAction<number>) {
      state.taxRate = action.payload;
    },
  },
});

// Derived values live in selectors, outside the store
const selectSubtotal = createSelector(
  [(s: RootState) => s.order.items],
  (items) => items.reduce((s, i) => s + i.price * i.qty, 0)
);
const selectTotal = createSelector(
  [selectSubtotal, (s: RootState) => s.order.taxRate],
  (subtotal, taxRate) => subtotal * (1 + taxRate)
);
```

**Paradigm**: functional. State is an immutable snapshot. Reducer is a pure transition function. The entire data flow is explicit and linear.

### Zustand — minimalist atomic store: "fewer abstractions, more control"

```ts
// Zustand: you simply describe state and functions that change it
// No events, no reducers, no reactive graph —
// just a store as an object and explicit subscriptions via selectors

const useOrderStore = create<OrderState>()((set, get) => ({
  items: [],
  taxRate: 0.2,

  // Derived values — regular methods (no built-in computed)
  getSubtotal: () => get().items.reduce((s, i) => s + i.price * i.qty, 0),
  getTotal: () => {
    const { taxRate } = get();
    return get().getSubtotal() * (1 + taxRate);
  },

  addItem: (item) => set(state => ({ items: [...state.items, item] })),
}));

// Component subscribes explicitly, choosing what to track
const total = useOrderStore(state => state.getTotal());
```

**Paradigm**: minimalist. The store is just an object in a closure. All power comes from explicit selector subscriptions. No hidden mechanisms.

---

## Performance and re-render behavior

Different tools give different re-render guarantees — this matters in large applications:

### MobX — automatic granularity

```tsx
// MobX: component re-renders ONLY when read observables change
// Granularity is automatic, with no developer effort

const OrderTotal = observer(({ store }: { store: OrderStore }) => {
  // During render, MobX tracks: store.total and store.items.length were read
  // Re-render happens ONLY when total or items.length changes
  // Changing taxRate without adding items → total changes → re-render
  // Changing another store field (e.g., isLoading) → NO re-render
  return <div>{store.items.length} items — ${store.total}</div>;
});

// Key: if a component has a conditional read —
// MobX only tracks what was read in THIS render
const ConditionalComponent = observer(({ store }: { store: OrderStore }) => {
  if (!store.isReady) return <Spinner />; // if false — total is not read
  return <div>${store.total}</div>;       // and not tracked!
});
```

### Redux — re-renders controlled by selectors

```tsx
// Redux: useSelector runs on EVERY dispatch of any action
// Re-renders only if the selector result changed (by ===)

const OrderTotal = () => {
  // selectTotal runs on every Redux action
  // Re-render only if result !== previous result
  const total = useAppSelector(selectTotal);
  return <div>${total}</div>;
};

// Problem without memoization — new object/array on every call:
const BadSelector = (state: RootState) => ({
  total: selectTotal(state),
  count: state.order.items.length,
}); // ❌ new object every time → re-renders on every dispatch

// ✅ shallowEqual as second argument:
import { shallowEqual } from 'react-redux';
const OrderSummary = () => {
  const { total, count } = useAppSelector(
    state => ({ total: selectTotal(state), count: state.order.items.length }),
    shallowEqual // compare fields, not the object reference
  );
  return <div>{count} items — ${total}</div>;
};
```

### Zustand — re-renders by selector result

```tsx
// Zustand: same as Redux, but you write the selector inline
// useStore subscribes and re-renders when the selector result changes

const OrderTotal = () => {
  // If getTotal() returns a primitive — === comparison, works fine
  const total = useOrderStore(state => state.getTotal());
  return <div>${total}</div>;
};

// For multiple values — use useShallow:
import { useShallow } from 'zustand/react/shallow';

const OrderSummary = () => {
  const { total, count } = useOrderStore(
    useShallow(state => ({
      total: state.getTotal(),
      count: state.items.length,
    }))
  );
  return <div>{count} items — ${total}</div>;
};
```

**Re-render summary:**

```txt
MobX:    Automatic granularity. Re-renders only when specific
         observables read during render change. Works "magically"
         but requires understanding the mechanism to avoid losing
         reactivity (destructuring outside observer, reading outside
         reactive context).

Redux:   Explicit control through selectors. Re-renders when the
         selector result changes. Requires memoization (createSelector)
         for objects/arrays. Predictable but verbose.

Zustand: Explicit control through inline selectors. Same as Redux
         but without a separate selector layer — write directly in
         the hook. For objects — useShallow. The most transparent
         mechanism.
```

---

## Boilerplate and Developer Experience

```txt
Scenario: add a new "Reviews" domain with async loading and CRUD

MobX (~40 lines):
  - ReviewStore class with fields and methods
  - makeAutoObservable in constructor
  - async methods with runInAction or flow
  - Add to RootStore, create useReviewStore hook

Redux/RTK (~70 lines):
  - reviewSlice with createSlice (initialState + reducers)
  - createAsyncThunk for each async action
  - extraReducers for pending/fulfilled/rejected
  - Selectors (at least basic ones)
  - Add reducer to configureStore

Zustand (~20 lines):
  - create<ReviewState>() with fields and async methods
  - Export the hook
  - Done
```

**TypeScript experience:**

```ts
// MobX: classes + TypeScript — natural
// Problem: flow generators lose typing at the yield point
class ReviewStore {
  reviews: Review[] = []; // TypeScript sees the type

  *fetchReviews() { // return type — FlowReturn, not Promise
    const data: Review[] = yield api.getReviews(); // yield is untyped
    this.reviews = data;
  }
}

// Redux/RTK: requires explicit generics, but results in strict typing
const fetchReviews = createAsyncThunk<Review[], void, { rejectValue: string }>(
  'reviews/fetch',
  async (_, { rejectWithValue }) => {
    // ...
  }
);
// createSlice automatically types action.payload from PayloadAction<T>

// Zustand: create<State>() — best TypeScript experience of the three
const useReviewStore = create<ReviewState>()((set, get) => ({
  reviews: [] as Review[], // TypeScript fully infers all types
  fetchReviews: async () => {
    const reviews = await api.getReviews(); // reviews: Review[]
    set({ reviews });
  },
}));
```

---

## Bundle size and dependencies

```txt
Library                   Size (min+gzip)   Dependencies
──────────────────────────────────────────────────────────
zustand                   ~1 KB             0
mobx + mobx-react-lite    ~18 KB            0 (peer: react)
@reduxjs/toolkit          ~14 KB            immer, reselect
react-redux               ~3 KB             0 (peer: react, redux)
redux (without RTK)       ~2 KB             0

RTK Query (inside RTK)    ~0 KB (included)  —
React Query (equivalent)  ~13 KB            0

Total for a typical project:
  Zustand                ~1 KB
  MobX stack             ~18 KB
  RTK + react-redux      ~17 KB
```

The difference matters for mobile web. For enterprise SPAs — not really. Bundle size should not be the primary selection criterion.

---

## Testing complexity

### MobX

```ts
// Pro: classes test in isolation, without React
const store = new ReviewStore(new RootStore());
store.addReview({ id: '1', text: 'Great!', rating: 5 });
expect(store.averageRating).toBe(5); // computed tested directly

// Con: need to track disposers in tests
// Con: flow generators need wrappers or await for async tests
```

### Redux/RTK

```ts
// Pro: reducer is a pure function — tests perfectly
const nextState = cartReducer(initialState, addItem({ id: '1', price: 10, qty: 1 }));
expect(nextState.items).toHaveLength(1);

// Pro: selectors test as regular functions
expect(selectTotal({ order: nextState })).toBe(10);

// Con: async thunks need mock dispatch + getState
const mockDispatch = jest.fn();
const mockGetState = jest.fn(() => ({ user: { id: '1' } }));
await addToCart('product-1')(mockDispatch, mockGetState, undefined);
expect(mockDispatch).toHaveBeenCalledWith(
  expect.objectContaining({ type: 'cart/addItem/fulfilled' })
);
```

### Zustand

```ts
// Pro: getState/setState — direct access without React
const { getState, setState } = useCartStore;

// Reset state between tests
beforeEach(() => setState({ items: [], discount: 0 }, true));

test('addItem works', () => {
  getState().addItem({ id: '1', price: 20, qty: 1 });
  expect(getState().items).toHaveLength(1);
});

// Async — just await
test('fetchProducts populates store', async () => {
  (api.getProducts as jest.Mock).mockResolvedValue([{ id: '1' }]);
  await getState().fetchProducts({});
  expect(getState().products).toHaveLength(1);
});
```

---

## Migration paths

### MobX → Zustand (incrementally)

```ts
// Strategy: create a Zustand wrapper store on top of MobX
// Migrate components one at a time, leave the MobX store untouched

// Temporary adapter:
const useLegacyCartStore = create<CartState>()((set) => {
  // Sync from MobX to Zustand
  const dispose = autorun(() => {
    set({
      items: mobxCartStore.items.slice(), // .slice() — observable to plain array
      total: mobxCartStore.total,
    });
  });

  return {
    items: [],
    total: 0,
    addItem: (item) => mobxCartStore.addItem(item), // delegate to MobX
  };
});
// After all components are migrated — delete the MobX store
```

### Redux → Zustand (domain by domain)

```ts
// Zustand and Redux can coexist in one app
// New features — in Zustand, old ones — stay in Redux

// If Redux state is needed from Zustand:
const useHybridStore = create<HybridState>()((set, get) => ({
  localData: [],

  syncWithRedux: () => {
    const reduxState = reduxStore.getState();
    set({ localData: reduxState.someSlice.data });
  },
}));

// Subscribe to Redux from outside React:
reduxStore.subscribe(() => {
  useHybridStore.getState().syncWithRedux();
});
```

### Redux → RTK (within Redux)

```ts
// RTK is backward-compatible with vanilla Redux
// Migrate one reducer at a time:

// Step 1: replace reducer with a slice
// Step 2: replace action creators with slice.actions
// Step 3: replace thunks with createAsyncThunk
// Step 4: add createSelector for selector memoization
// configureStore works with existing reducers
```

### Zustand → RTK (when the project grows)

```ts
// Most painful migration — different paradigms
// Strategy: RTK Query for server-state, Zustand for client-state

// The hybrid works well:
// - RTK Query manages server data (cache, requests, mutations)
// - Zustand manages UI state and client-only data

export const store = configureStore({
  reducer: {
    [productsApi.reducerPath]: productsApi.reducer,
  },
  middleware: (gdm) => gdm().concat(productsApi.middleware),
});

// Zustand for UI state:
const useUIStore = create<UIState>()((set) => ({
  sidebarOpen: false,
  activeTab: 'overview',
  toggleSidebar: () => set(s => ({ sidebarOpen: !s.sidebarOpen })),
}));
```

---

## When to choose what — practical guide

```txt
Choose Zustand if:
  ✓ New project, team < 10 developers
  ✓ No complex audit trail requirements
  ✓ Speed of start and minimal boilerplate matter
  ✓ Server-state is managed by React Query or SWR
  ✓ Team knows React hooks — they'll learn Zustand in a day

Choose Redux/RTK if:
  ✓ Large team with clear separation of concerns
  ✓ Full audit trail and time-travel debugging required
  ✓ Lots of CRUD with caching → add RTK Query
  ✓ Already in use (don't migrate just to migrate)
  ✓ Complex business logic with many state transitions

Choose MobX if:
  ✓ Team has OOP background (backend devs, .NET/Java)
  ✓ Complex reactive computations (derived from derived)
  ✓ Large volumes of mutable data (financial tables, real-time data)
  ✓ Minimal configuration with maximum reactivity is the goal

Choose none of the three if:
  - Simple UI state: modal/tab/accordion → useState or useReducer
  - Server-state without client cache: React Query / SWR handle
    loading/error/caching better than any of the three
```

---

## The big comparison table

```txt
┌─────────────────────────┬─────────────────┬─────────────────┬─────────────────┐
│ Criterion               │ MobX            │ Redux/RTK       │ Zustand         │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Paradigm                │ Reactive OOP    │ Functional      │ Minimalist      │
│                         │                 │ (event-driven)  │ (explicit subs) │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Mutability              │ Mutable         │ Immutable       │ Immutable       │
│                         │ (inside action) │ (Immer in RTK)  │ (set returns    │
│                         │                 │                 │ new object)     │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Re-renders              │ Automatic       │ Explicit via    │ Explicit via    │
│                         │ (reactive graph)│ selector        │ selector        │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Derived data            │ computed (lazy, │ createSelector  │ Functions in    │
│                         │ cached, auto)   │ (manual, memo)  │ store (no cache)│
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Async                   │ flow / action + │ createAsync-    │ async functions │
│                         │ runInAction     │ Thunk           │ (native)        │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Provider required       │ Optional        │ Yes             │ No              │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Boilerplate             │ Medium          │ High (RTK       │ Minimal         │
│                         │                 │ reduces it)     │                 │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Bundle (min+gz)         │ ~18 KB          │ ~17 KB          │ ~1 KB           │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ TypeScript              │ Good            │ Good            │ Excellent        │
│                         │ (flow — worse)  │                 │                 │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ DevTools                │ MobX DevTools   │ Redux DevTools  │ Redux DevTools  │
│                         │ (limited)       │ (time-travel,   │ (devtools       │
│                         │                 │ export/import)  │ middleware)     │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Testing                 │ Classes without │ Reducer = pure  │ getState /      │
│                         │ React (need     │ fn (perfect);   │ setState without│
│                         │ dispose)        │ thunks harder   │ React           │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Learning curve          │ 1-2 days        │ 2-4 days (RTK)  │ 30 minutes      │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Server state            │ Custom impl.    │ RTK Query       │ React Query /   │
│                         │ (no built-in)   │ (built-in)      │ SWR (external)  │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Inter-store             │ Via RootStore   │ getState() in   │ get() in store  │
│ communication           │ (DI via root)   │ thunk           │ methods         │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ SSR support             │ Yes (with       │ Yes             │ Yes (out of     │
│                         │ caveats)        │                 │ the box)        │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Enforcement             │ enforceActions  │ Enforced by     │ No built-in     │
│                         │ (optional)      │ reducer pattern │ enforcement     │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Best fit for            │ Complex reactive │ Large teams,    │ New projects,   │
│                         │ computations,   │ audit trail,    │ fast start,     │
│                         │ OOP teams       │ legacy projects │ small teams     │
└─────────────────────────┴─────────────────┴─────────────────┴─────────────────┘
```

---

## Common interview traps

- **"I like X, so I always use X"** — a red flag. A good answer always starts with requirements: team size, business logic complexity, audit trail needs, what is already in the project. The tool is chosen for the task, not the task for the favorite tool.

- **"Redux is outdated, everyone is moving to Zustand/MobX"** — incorrect. Redux (especially with RTK) is actively developed and remains the right choice for specific scenarios. Zustand and MobX solve certain problems better — but they do not replace Redux entirely.

- **Not distinguishing client-state from server-state** — managing server state (loading, cache, refetch, mutations) is a separate concern. React Query, SWR, and RTK Query are purpose-built for this. Using MobX/Zustand to store API data without a caching strategy is reinventing the wheel. A strong candidate understands: MobX/Zustand/Redux — for client-state, React Query/RTK Query — for server-state, and often both are needed together.

- **Thinking MobX is "magic" and unpredictable** — the MobX reactive graph is predictable once you understand the mechanism. Problems arise only when you don't know when the reactive context breaks (destructuring, async without flow, reading outside observer). With strict mode, most mistakes surface during development.

- **"Zustand is small, so it must be primitive"** — bundle size does not correlate with maturity or functionality. Zustand is deliberate minimalism, not limitation. Complexity in Zustand moves from infrastructure (Redux boilerplate) to explicit structures (slices, selectors in hooks).

- **Not knowing about Server Components and the future of state management** — with React Server Components, most server-state is not needed on the client at all. Server data arrives as props of server components, without useEffect and without a store. A strong candidate understands that RSC shifts the distribution: "server state" is URL + server components, client-state is user interaction (forms, filters, UI). Zustand and MobX fit this world better (no Provider, no serialization issues), Redux requires adaptation.
