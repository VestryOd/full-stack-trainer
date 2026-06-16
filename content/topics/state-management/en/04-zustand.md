# Zustand

## Minimal API — the idea in one line

Zustand is built on one principle: a store is a hook. No providers, no actions, no reducers. Call `create` with an initializer function — get a hook:

```ts
import { create } from 'zustand';

interface CartState {
  items: CartItem[];
  discount: number;
  addItem: (item: CartItem) => void;
  removeItem: (id: string) => void;
  applyDiscount: (percent: number) => void;
  total: () => number;
}

export const useCartStore = create<CartState>((set, get) => ({
  items: [],
  discount: 0,

  addItem: (item) =>
    set((state) => {
      const existing = state.items.find(i => i.id === item.id);
      if (existing) {
        return {
          items: state.items.map(i =>
            i.id === item.id ? { ...i, qty: i.qty + item.qty } : i
          ),
        };
      }
      return { items: [...state.items, item] };
    }),

  removeItem: (id) =>
    set((state) => ({
      items: state.items.filter(i => i.id !== id),
    })),

  applyDiscount: (percent) => set({ discount: percent / 100 }),

  // get() — synchronous access to current state from any method
  total: () => {
    const { items, discount } = get();
    return items.reduce((sum, i) => sum + i.price * i.qty, 0) * (1 - discount);
  },
}));
```

```tsx
// Usage — just a hook, no provider needed
const CartSummary = () => {
  // Subscribe to specific fields — re-renders only when they change
  const items = useCartStore(state => state.items);
  const total = useCartStore(state => state.total());
  const addItem = useCartStore(state => state.addItem);

  return (
    <div>
      <span>{items.length} items — ${total.toFixed(2)}</span>
      <button onClick={() => addItem({ id: '1', name: 'Book', price: 20, qty: 1 })}>
        Add
      </button>
    </div>
  );
};
```

**Three factory parameters:**

```ts
create<State>((set, get, api) => ({
  //  set  — update state (like React's setState, but for the whole store)
  //  get  — read current state synchronously
  //  api  — store object: { getState, setState, subscribe, destroy }
}))
```

## set and get — the update mechanics

```ts
export const useCounterStore = create<{
  count: number;
  multiplier: number;
  increment: () => void;
  incrementBy: (n: number) => void;
  reset: () => void;
  computedDouble: () => number;
}>((set, get) => ({
  count: 0,
  multiplier: 2,

  // set with a function — receives previous state, returns partial update
  increment: () => set((state) => ({ count: state.count + 1 })),

  // set with an object — shortcut when previous state is not needed
  incrementBy: (n) => set((state) => ({ count: state.count + n })),

  // Zustand does shallow merge by default —
  // no need to spread the entire state
  reset: () => set({ count: 0 }), // multiplier stays untouched

  // get() — reads current state without subscribing
  // Used inside methods, not in components
  computedDouble: () => get().count * get().multiplier,
}));

// Full state replacement (replace = true) — rarely needed
useCounterStore.setState({ count: 0, multiplier: 1 }, true); // replace!
```

**Granular subscriptions — the key to performance:**

```tsx
const Counter = () => {
  // ✅ Subscribe only to count — re-render only when count changes
  const count = useCounterStore(state => state.count);
  return <span>{count}</span>;
};

const Controls = () => {
  // ✅ Actions are stable references, never change — no re-renders at all
  const increment = useCounterStore(state => state.increment);
  const reset = useCounterStore(state => state.reset);
  return (
    <>
      <button onClick={increment}>+</button>
      <button onClick={reset}>Reset</button>
    </>
  );
};

// ❌ Subscribing to the whole store — re-renders on ANY change
const BadComponent = () => {
  const store = useCounterStore(); // re-renders even when multiplier changes
  return <span>{store.count}</span>;
};
```

**subscribe — subscribing outside components:**

```ts
// subscribe works outside React — useful for syncing with external systems
const unsubscribe = useCartStore.subscribe(
  (state) => state.total(),
  (total, prevTotal) => {
    // Fires only when total changes (second argument is a selector)
    analytics.track('cart_total_changed', { total, prevTotal });
  }
);

// Unsubscribe when no longer needed
unsubscribe();
```

## Slices pattern — organizing large stores

Zustand doesn't enforce structure, but for large stores the slices pattern is recommended — analogous to Redux's `combineReducers`:

```ts
// store/slices/cartSlice.ts
import type { StateCreator } from 'zustand';
import type { RootStore } from '../index';

export interface CartSlice {
  cart: {
    items: CartItem[];
    discount: number;
  };
  addToCart: (item: CartItem) => void;
  removeFromCart: (id: string) => void;
  getCartTotal: () => number;
}

export const createCartSlice: StateCreator<
  RootStore,            // full store type — for cross-slice access
  [],
  [],
  CartSlice
> = (set, get) => ({
  cart: {
    items: [],
    discount: 0,
  },

  addToCart: (item) =>
    set((state) => ({
      cart: {
        ...state.cart,
        items: [...state.cart.items, item],
      },
    })),

  removeFromCart: (id) =>
    set((state) => ({
      cart: {
        ...state.cart,
        items: state.cart.items.filter(i => i.id !== id),
      },
    })),

  // Cross-slice access via get()
  getCartTotal: () => {
    const { cart, user } = get();
    const base = cart.items.reduce((s, i) => s + i.price * i.qty, 0);
    // user.isPremium — from userSlice, get() provides full store access
    return user.isPremium ? base * 0.9 : base;
  },
});

// store/slices/userSlice.ts
export interface UserSlice {
  user: {
    data: User | null;
    isPremium: boolean;
  };
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
}

export const createUserSlice: StateCreator<RootStore, [], [], UserSlice> =
  (set) => ({
    user: { data: null, isPremium: false },

    login: async (credentials) => {
      const user = await authApi.login(credentials);
      set({ user: { data: user, isPremium: user.subscription === 'premium' } });
    },

    logout: () =>
      set({ user: { data: null, isPremium: false } }),
  });

// store/index.ts — combining slices
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { createCartSlice, CartSlice } from './slices/cartSlice';
import { createUserSlice, UserSlice } from './slices/userSlice';

export type RootStore = CartSlice & UserSlice;

export const useStore = create<RootStore>()(
  devtools(
    (...args) => ({
      ...createCartSlice(...args),
      ...createUserSlice(...args),
    }),
    { name: 'AppStore' }
  )
);

// Convenience hooks per domain:
export const useCartStore = () => useStore(state => ({
  items: state.cart.items,
  total: state.getCartTotal(),
  addToCart: state.addToCart,
  removeFromCart: state.removeFromCart,
}));
```

## Middleware — persist, devtools, immer

Zustand's middleware system works through functional composition:

```ts
import { create } from 'zustand';
import { persist, devtools, subscribeWithSelector } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';

// persist — automatic save to localStorage/sessionStorage
export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      theme: 'light',
      language: 'en',
      notifications: true,
      setTheme: (theme) => set({ theme }),
      setLanguage: (lang) => set({ language: lang }),
    }),
    {
      name: 'app-settings',        // localStorage key
      partialize: (state) => ({    // persist only these fields
        theme: state.theme,
        language: state.language,
        // notifications — not persisted (session-only)
      }),
      // Custom storage (e.g., AsyncStorage for React Native):
      // storage: createJSONStorage(() => AsyncStorage),
    }
  )
);

// devtools — Redux DevTools integration
export const useCartStore = create<CartState>()(
  devtools(
    (set, get) => ({
      items: [],
      addItem: (item) => {
        set(
          (state) => ({ items: [...state.items, item] }),
          false,               // replace? false = merge
          'cart/addItem'       // action name in DevTools
        );
      },
    }),
    { name: 'CartStore', enabled: process.env.NODE_ENV === 'development' }
  )
);

// immer middleware — mutable updates like in RTK
export const useTaskStore = create<TaskState>()(
  immer((set) => ({
    tasks: [] as Task[],

    addTask: (task: Task) =>
      set((state) => {
        state.tasks.push(task); // mutation — OK with immer
      }),

    toggleTask: (id: string) =>
      set((state) => {
        const task = state.tasks.find(t => t.id === id);
        if (task) task.completed = !task.completed; // nested mutation
      }),

    deleteTask: (id: string) =>
      set((state) => {
        const index = state.tasks.findIndex(t => t.id === id);
        if (index !== -1) state.tasks.splice(index, 1);
      }),
  }))
);

// Combining middleware — order matters (outer → inner)
export const useComplexStore = create<ComplexState>()(
  devtools(           // outermost — first in chain
    persist(          // second
      immer(          // closest to create — applied first
        (set) => ({
          // ...
        })
      ),
      { name: 'complex-store' }
    ),
    { name: 'ComplexStore' }
  )
);
```

**subscribeWithSelector** — extended subscription with a selector (built into middleware):

```ts
import { subscribeWithSelector } from 'zustand/middleware';

const useStore = create<State>()(
  subscribeWithSelector((set) => ({
    count: 0,
    increment: () => set(state => ({ count: state.count + 1 })),
  }))
);

// Subscription with selector — fires only when selected value changes
const unsubscribe = useStore.subscribe(
  state => state.count,            // selector
  (count, prevCount) => {          // listener
    if (count > 10) {
      console.log('Count exceeded 10!', { count, prevCount });
    }
  },
  { equalityFn: (a, b) => a === b, fireImmediately: true }
);
```

## Async in Zustand — no ceremony

Zustand needs no special wrappers for async — they are just regular async functions:

```ts
export const useProductStore = create<ProductState>()((set, get) => ({
  products: [],
  isLoading: false,
  error: null,

  fetchProducts: async (filters: ProductFilters) => {
    set({ isLoading: true, error: null });
    try {
      const products = await productsApi.getAll(filters);
      set({ products, isLoading: false });
    } catch (e) {
      set({ isLoading: false, error: (e as Error).message });
    }
  },

  // Access to current state via get() in async methods
  refreshIfStale: async () => {
    const { products, fetchProducts } = get();
    if (products.length === 0) {
      await fetchProducts({});
    }
  },
}));
```

No `runInAction`, `flow`, or `createAsyncThunk` — just async/await. This is the main reason Zustand gets picked up so quickly by teams.

## Zustand vs Context + useReducer

Context + useReducer is the built-in alternative people often reach for to "avoid adding a dependency":

```tsx
// Context + useReducer — looks familiar, but with problems:
type Action =
  | { type: 'ADD_ITEM'; payload: CartItem }
  | { type: 'REMOVE_ITEM'; payload: string };

function cartReducer(state: CartState, action: Action): CartState {
  switch (action.type) {
    case 'ADD_ITEM':
      return { ...state, items: [...state.items, action.payload] };
    case 'REMOVE_ITEM':
      return { ...state, items: state.items.filter(i => i.id !== action.payload) };
    default:
      return state;
  }
}

const CartContext = createContext<{
  state: CartState;
  dispatch: React.Dispatch<Action>;
} | null>(null);

// Problem 1: requires a Provider — changes the component tree topology
function App() {
  const [state, dispatch] = useReducer(cartReducer, { items: [], discount: 0 });
  return (
    <CartContext.Provider value={{ state, dispatch }}>
      <CartPage />
    </CartContext.Provider>
  );
}

// Problem 2: ALL consumers re-render on ANY change
// A component showing only item count re-renders
// when discount changes — because the whole context object changes
function CartBadge() {
  const { state } = useContext(CartContext)!;
  return <span>{state.items.length}</span>;
  // re-renders on ANY state field change
}
```

```tsx
// ✅ Zustand — same goals, without Context's problems
function CartBadge() {
  // Subscribe only to items.length — re-renders only when it changes
  const count = useCartStore(state => state.items.length);
  return <span>{count}</span>;
}

// No Provider — store is accessible from any component anywhere in the tree
// No action type boilerplate or dispatch
// Granular subscriptions out of the box
```

**When Context + useReducer is still justified:**

```txt
- Pure UI state: modal open/closed, wizard step — not needed
  outside a specific component subtree
- Intentional isolation: separate state for each component instance
  (e.g., multiple independent forms on one page)
- No client-side navigation: SSR pages without React hydration,
  where a global store is unnecessary
```

## Why Zustand often beats Redux and MobX in new projects

```txt
Comparison by pain points:

Boilerplate:
  Redux/RTK   — createSlice + createAsyncThunk + selectors + Provider
                + typed hooks — at least 50 lines per domain
  MobX        — class + makeAutoObservable + observer + Context/Provider
                + hooks — 30-40 lines per domain
  Zustand     — create() — 10-15 lines, everything in one place

Learning curve:
  Redux/RTK   — middleware pipeline, Immer internals, RTK Query lifecycle,
                createSelector, action matching — 2-3 days to confident use
  MobX        — reactive system, Proxy, classes, strict mode, flow —
                1-2 days
  Zustand     — create + set + get — 30 minutes

TypeScript:
  Redux/RTK   — RTK has good types, but needs AppDispatch,
                RootState, TypedUseSelectorHook — template code
  MobX        — classes + TypeScript work naturally, but flow
                generators lose typing at the yield point
  Zustand     — create<State>() — full type inference, nothing extra

Bundle size (minified+gzip):
  Redux + RTK              — ~14KB
  MobX + mobx-react-lite  — ~18KB
  Zustand                 — ~1KB

Testability:
  Redux/RTK   — reducers are pure functions, test perfectly;
                async thunks need a mock dispatch
  MobX        — classes test without React; reactions need dispose
  Zustand     — store.getState() and store.setState() in tests — simple
```

**The main argument for Zustand in a new project**: it imposes no architectural constraints. If in six months you decide you need stricter structure — you can add devtools, immer, or persist one by one, or migrate to RTK. Starting minimal and adding as needed is better than starting with a full Redux configuration and not using 70% of it.

## Common interview traps

- **"Zustand is just useState for multiple components"** — an understatement. Zustand has a middleware system, DevTools integration, `subscribe` outside React, persist, slices support, and SSR. The key difference from `useState` — the store lives outside the React tree and does not cause a provider re-render.

- **Subscribing to the whole store instead of specific fields** — the most common performance mistake:
  ```tsx
  // ❌
  const { items, discount, total, addItem } = useCartStore();
  // ↑ re-renders on ANY field change

  // ✅
  const items = useCartStore(state => state.items);
  const addItem = useCartStore(state => state.addItem);
  ```

- **Not knowing that actions in Zustand are stable references** — functions defined inside `create` are created once and do not change when state updates. This means they are safe to pass to `useEffect` without adding to the deps array and do not need `useCallback` memoization.

- **Accidentally using `set` with full state replacement (`replace: true`)** — calling `set({ count: 0 }, true)` the second argument `true` means full replacement of the entire state, not a merge. If you forget this — you lose all other store fields without a single error.

- **"Zustand doesn't scale to large apps"** — incorrect. Zustand is used in large projects via the slices pattern. The limitation is not app size but requirements: if you need a strict audit trail of changes or full time-travel debugging at the Redux DevTools level — Zustand provides this only with devtools middleware, but less flexibly than Redux.

- **Comparing Zustand with MobX incorrectly** — they solve different problems differently: MobX is built on a reactive dependency graph (you declare data, MobX finds subscribers automatically), Zustand is built on explicit subscriptions (you choose the selector yourself). Both are minimal in boilerplate compared to Redux, but their mental models are fundamentally different.
