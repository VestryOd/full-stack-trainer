# Redux Toolkit

## Why vanilla Redux was painful — and what RTK fixes

Redux without tooling required enormous boilerplate. Here is a typical async flow in vanilla Redux:

```ts
// ❌ Vanilla Redux — action types, action creators, reducer, thunk — all manual

// actionTypes.ts
const FETCH_USER_REQUEST = 'FETCH_USER_REQUEST';
const FETCH_USER_SUCCESS = 'FETCH_USER_SUCCESS';
const FETCH_USER_FAILURE = 'FETCH_USER_FAILURE';

// actions.ts
const fetchUserRequest = () => ({ type: FETCH_USER_REQUEST });
const fetchUserSuccess = (user: User) => ({ type: FETCH_USER_SUCCESS, payload: user });
const fetchUserFailure = (error: string) => ({ type: FETCH_USER_FAILURE, payload: error });

// thunk.ts
const fetchUser = (id: string) => async (dispatch: Dispatch) => {
  dispatch(fetchUserRequest());
  try {
    const user = await api.getUser(id);
    dispatch(fetchUserSuccess(user));
  } catch (e) {
    dispatch(fetchUserFailure(String(e)));
  }
};

// reducer.ts — manual immutable updates (nested objects are painful)
interface UserState {
  data: User | null;
  isLoading: boolean;
  error: string | null;
}
const initialState: UserState = { data: null, isLoading: false, error: null };

function userReducer(state = initialState, action: AnyAction): UserState {
  switch (action.type) {
    case FETCH_USER_REQUEST:
      return { ...state, isLoading: true, error: null };
    case FETCH_USER_SUCCESS:
      return { ...state, isLoading: false, data: action.payload };
    case FETCH_USER_FAILURE:
      return { ...state, isLoading: false, error: action.payload };
    default:
      return state;
  }
}
```

**Vanilla Redux problems:**
1. Every async flow needs 3 action types + 3 action creators + reducer branches
2. Immutable updates for nested objects — multi-line spread hell
3. No async standard — redux-thunk, redux-saga, redux-observable — every team invented their own approach
4. TypeScript typing required separate effort

RTK is the **official** wrapper library written by the Redux team. It does not change Redux architecture — it eliminates the boilerplate:

```ts
// ✅ Same thing in Redux Toolkit — far less code
import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

const fetchUser = createAsyncThunk('user/fetch', async (id: string) => {
  return await api.getUser(id); // RTK generates pending/fulfilled/rejected automatically
});

interface UserState {
  data: User | null;
  isLoading: boolean;
  error: string | null;
}

const userSlice = createSlice({
  name: 'user',
  initialState: { data: null, isLoading: false, error: null } as UserState,
  reducers: {
    clearUser(state) {
      state.data = null; // Immer under the hood — mutations allowed!
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchUser.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchUser.fulfilled, (state, action: PayloadAction<User>) => {
        state.isLoading = false;
        state.data = action.payload;
      })
      .addCase(fetchUser.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.error.message ?? 'Unknown error';
      });
  },
});

export const { clearUser } = userSlice.actions;
export default userSlice.reducer;
```

## createSlice — the core of RTK

`createSlice` combines action types, action creators, and the reducer into a single object:

```ts
import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface CartState {
  items: CartItem[];
  discount: number;
  status: 'idle' | 'loading' | 'error';
}

const cartSlice = createSlice({
  name: 'cart',   // prefix for action types: 'cart/addItem', 'cart/removeItem'
  initialState: {
    items: [],
    discount: 0,
    status: 'idle',
  } as CartState,
  reducers: {
    // Immer lets you write "mutable" code — under the hood it's immutable
    addItem(state, action: PayloadAction<CartItem>) {
      const existing = state.items.find(i => i.id === action.payload.id);
      if (existing) {
        existing.qty += action.payload.qty;
      } else {
        state.items.push(action.payload); // push — OK thanks to Immer
      }
    },

    removeItem(state, action: PayloadAction<string>) {
      state.items = state.items.filter(i => i.id !== action.payload);
    },

    applyDiscount(state, action: PayloadAction<number>) {
      state.discount = action.payload;
    },

    // When you need to return a new state explicitly (e.g., reset):
    resetCart() {
      return { items: [], discount: 0, status: 'idle' };
      // Returning a new value — alternative to mutating state
    },
  },
});

export const { addItem, removeItem, applyDiscount, resetCart } = cartSlice.actions;
export default cartSlice.reducer;
```

**Immer under the hood** — the key detail: RTK uses the Immer library, which wraps `state` in a Proxy. You write mutable-looking code (`state.items.push(...)`), but Immer intercepts all changes and produces a new immutable object. Redux DevTools shows the correct immutable diff — everything works correctly.

**Store configuration:**

```ts
// store/index.ts
import { configureStore } from '@reduxjs/toolkit';
import cartReducer from './cartSlice';
import userReducer from './userSlice';

export const store = configureStore({
  reducer: {
    cart: cartReducer,
    user: userReducer,
  },
  // configureStore automatically adds:
  // - redux-thunk middleware
  // - Redux DevTools Extension (dev only)
  // - serializability check middleware (warns about Date/functions in state)
});

// TypeScript: derive types from the store itself
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

// Typed hooks
import { TypedUseSelectorHook, useDispatch, useSelector } from 'react-redux';
export const useAppDispatch = () => useDispatch<AppDispatch>();
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
```

## createAsyncThunk — the standard for async

```ts
import { createAsyncThunk } from '@reduxjs/toolkit';

// Simple case
export const fetchProducts = createAsyncThunk(
  'products/fetchAll',
  async (filters: ProductFilters) => {
    const data = await productsApi.getAll(filters);
    return data; // becomes action.payload in fulfilled
  }
);

// With state access and error handling
export const addToCart = createAsyncThunk(
  'cart/addItem',
  async (productId: string, { getState, rejectWithValue }) => {
    const state = getState() as RootState;
    const userId = state.user.data?.id;

    if (!userId) {
      // rejectWithValue — a controlled error (goes to action.payload)
      // unlike throw (goes to action.error)
      return rejectWithValue('User not authenticated');
    }

    try {
      const item = await cartApi.add({ userId, productId });
      return item;
    } catch (e) {
      return rejectWithValue((e as Error).message);
    }
  }
);

// In a component:
const ProductCard = ({ product }: { product: Product }) => {
  const dispatch = useAppDispatch();

  const handleAdd = async () => {
    const result = await dispatch(addToCart(product.id));

    // createAsyncThunk returns an object with .unwrap() —
    // lets you get the result or throw the error
    if (addToCart.fulfilled.match(result)) {
      toast.success('Added to cart!');
    } else {
      toast.error(result.payload as string);
    }
  };

  return <button onClick={handleAdd}>Add to cart</button>;
};
```

**Request cancellation via AbortController:**

```ts
export const searchProducts = createAsyncThunk(
  'products/search',
  async (query: string, { signal }) => {
    // signal — AbortSignal, automatically created by the thunk
    const response = await fetch(`/api/search?q=${query}`, { signal });
    return response.json();
  }
);

// In a component — cancel on unmount or new request:
useEffect(() => {
  const promise = dispatch(searchProducts(query));
  return () => promise.abort(); // cancels fetch via AbortController
}, [query]);
```

## RTK Query — caching and data fetching

RTK Query is a built-in RTK tool for server-state. For most projects it replaces the need to write async thunks for CRUD:

```ts
// store/api.ts
import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

export const productsApi = createApi({
  reducerPath: 'productsApi',
  baseQuery: fetchBaseQuery({ baseUrl: '/api' }),
  tagTypes: ['Product', 'Cart'],
  endpoints: (builder) => ({
    // Query — for reading data
    getProducts: builder.query<Product[], ProductFilters>({
      query: (filters) => ({
        url: '/products',
        params: filters,
      }),
      providesTags: ['Product'],
    }),

    getProduct: builder.query<Product, string>({
      query: (id) => `/products/${id}`,
      providesTags: (result, error, id) => [{ type: 'Product', id }],
    }),

    // Mutation — for changing data
    addProduct: builder.mutation<Product, Partial<Product>>({
      query: (body) => ({
        url: '/products',
        method: 'POST',
        body,
      }),
      invalidatesTags: ['Product'], // after success — invalidate cache
    }),

    updateProduct: builder.mutation<Product, { id: string } & Partial<Product>>({
      query: ({ id, ...patch }) => ({
        url: `/products/${id}`,
        method: 'PATCH',
        body: patch,
      }),
      invalidatesTags: (result, error, { id }) => [{ type: 'Product', id }],
    }),
  }),
});

// RTK Query auto-generates hooks:
export const {
  useGetProductsQuery,
  useGetProductQuery,
  useAddProductMutation,
  useUpdateProductMutation,
} = productsApi;

// Add to store:
export const store = configureStore({
  reducer: {
    [productsApi.reducerPath]: productsApi.reducer,
    cart: cartReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(productsApi.middleware),
});
```

```tsx
// Usage in components:
const ProductList = ({ filters }: { filters: ProductFilters }) => {
  const { data, isLoading, isError, isFetching } = useGetProductsQuery(filters);
  // RTK Query handles: caching, request deduplication, refetch on focus/reconnect

  if (isLoading) return <Spinner />;
  if (isError) return <Error />;

  return (
    <ul>
      {data?.map(product => (
        <ProductCard key={product.id} product={product} />
      ))}
      {isFetching && <Spinner size="small" />} {/* background refresh */}
    </ul>
  );
};

const AddProductForm = () => {
  const [addProduct, { isLoading }] = useAddProductMutation();

  const handleSubmit = async (data: Partial<Product>) => {
    await addProduct(data).unwrap(); // .unwrap() — throws on error
    // After success, RTK Query auto-invalidates 'Product' cache
    // and ProductList updates itself
  };

  return <form onSubmit={handleSubmit}>{/* ... */}</form>;
};
```

## Selector patterns and createSelector

Selectors are functions that compute derived data from Redux state. `createSelector` from Reselect (built into RTK) memoizes them:

```ts
import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '../store';

// Simple "input" selectors — no memoization, just reading
const selectCartItems = (state: RootState) => state.cart.items;
const selectDiscount = (state: RootState) => state.cart.discount;
const selectUserId = (state: RootState) => state.user.data?.id;

// Memoized derived selector
export const selectCartTotal = createSelector(
  [selectCartItems, selectDiscount],
  (items, discount) => {
    // This function is called ONLY if items or discount changed
    // Otherwise the cached result is returned
    return items.reduce((sum, item) => sum + item.price * item.qty, 0)
      * (1 - discount);
  }
);

export const selectCartItemCount = createSelector(
  [selectCartItems],
  (items) => items.reduce((sum, item) => sum + item.qty, 0)
);

// Parameterized selector — via factory
export const makeSelectItemById = (id: string) =>
  createSelector(
    [selectCartItems],
    (items) => items.find(item => item.id === id)
  );

// Usage in a component:
const CartSummary = () => {
  const total = useAppSelector(selectCartTotal);
  const count = useAppSelector(selectCartItemCount);
  // Re-renders ONLY if total or count changed —
  // intermediate computations are memoized

  return <div>{count} items — ${total.toFixed(2)}</div>;
};

// Parameterized:
const CartItemRow = ({ id }: { id: string }) => {
  // useMemo to avoid creating a new selector on each render
  const selectItem = useMemo(() => makeSelectItemById(id), [id]);
  const item = useAppSelector(selectItem);

  return <div>{item?.name}</div>;
};
```

**Why selector memoization matters:**

```ts
// ❌ Without memoization — recalculates on EVERY dispatch,
// even if cart.items didn't change
const selectExpensiveItems = (state: RootState) =>
  state.cart.items.filter(item => item.price > 100); // new array every time

// useSelector compares results by reference (===)
// New array [] !== [] → component re-renders on every action
const ExpensiveItems = () => {
  const items = useAppSelector(selectExpensiveItems); // re-renders on EVERY action
};

// ✅ With createSelector — recalculates only when items changes
export const selectExpensiveItems = createSelector(
  [selectCartItems],
  (items) => items.filter(item => item.price > 100) // called only if items changed
);
```

## Redux data flow and middleware

Redux is strictly unidirectional: `Action → Middleware → Reducer → Store → View`:

```txt
dispatch(action)
      ↓
  Middleware chain (thunk, logger, serializability check...)
      ↓
  Reducer (pure function: (state, action) → newState)
      ↓
  Store updates (new state)
      ↓
  Subscribed components (useSelector) receive notification
      ↓
  React re-renders components where selector result changed
```

Middleware intercepts dispatch. Redux-thunk, for example, checks: if a function is dispatched instead of an object — call it with `(dispatch, getState)`, otherwise pass it through:

```ts
// Custom middleware — action logging
import { Middleware } from '@reduxjs/toolkit';

const loggerMiddleware: Middleware = (store) => (next) => (action) => {
  console.group(action.type);
  console.log('dispatching:', action);
  const result = next(action); // pass along the chain
  console.log('next state:', store.getState());
  console.groupEnd();
  return result;
};

export const store = configureStore({
  reducer: rootReducer,
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(loggerMiddleware),
    // getDefaultMiddleware() includes: thunk + serializability + immutability
});
```

## Redux DevTools and time-travel debugging

Redux DevTools is one of Redux's key advantages. Because state is immutable and all flow goes through the reducer — every state change can be recorded and replayed:

```txt
DevTools capabilities:
  - Log of all dispatched actions with payload
  - State diff before and after each action
  - "Jump to" — jump to any past state without page reload
  - "Skip" — skip a specific action and see state without it
  - Import/export state — reproduce a bug with the exact user state
  - Test reducers inside DevTools (dispatch actions manually)
```

```ts
// configureStore automatically enables DevTools in development
// Optionally — advanced configuration:
export const store = configureStore({
  reducer: rootReducer,
  devTools: process.env.NODE_ENV !== 'production'
    ? {
        name: 'MyApp Store',
        trace: true,          // shows call stack for each action
        traceLimit: 25,
      }
    : false,
});
```

**Time-travel debugging in practice**: when a user reports a bug, you can export state from DevTools ("Export" button), send it to the developer, they import it — and see the application in exactly the state where the bug occurred. This is impossible with mutable state (MobX, Zustand without middleware).

## When Redux is still the right choice

Redux is often considered "outdated" — that is a mistake. It remains the right choice in specific scenarios:

```txt
✅ When Redux is the right choice:

1. Predictability as a requirement
   - fintech, medical, legal tools — where a full audit trail
     of all state changes is required
   - time-travel debugging is critical for bug reproduction

2. Large teams with clear separation of concerns
   - Redux enforces structure (actions/reducers/selectors
     in separate files) — reduces chaos with dozens of contributors

3. Complex business logic with many state transitions
   - reducers are state machines: each case explicitly defines
     a transition. Testable in isolation, without React

4. Server-state management via RTK Query
   - if the project has many CRUD operations with caching,
     invalidation, polling — RTK Query competes with
     React Query in features and is built into RTK

5. Already in use and working
   - migrating from Redux to MobX/Zustand without a clear
     problem is risk without benefit
```

```txt
❌ When Redux is overkill:

- Small app with <5 developers
- Simple UI state (modal open/closed, active tab)
- No audit trail or time-travel requirements
- Team unfamiliar with Redux — learning cost exceeds the benefit
```

## Common interview traps

- **"RTK is a new state management library"** — no. RTK is the official utility set on top of Redux. Architecturally it is the same Redux: unidirectional flow, immutable state, pure reducer. RTK eliminates boilerplate but does not change the principles.

- **Not understanding that Immer makes state look mutable** — code like `state.items.push(...)` in a reducer looks like a mutation, but it is an Immer proxy. The actual Redux state is still immutable, and DevTools shows the correct diff. The mistake is thinking RTK "abandoned immutability."

- **Confusing `rejectWithValue` and `throw`** in `createAsyncThunk`: `throw` → `action.error.message` (standard Error structure, not typed); `rejectWithValue(data)` → `action.payload` (your data, typed). This is a signal question in interviews — shows whether the candidate has written real error flows.

- **Not memoizing selectors** — `useSelector` compares results by reference. If a selector returns a new object/array on every call (e.g., via `.filter()`/`.map()`), the component re-renders on every Redux action, even unrelated ones. This is one of the most common performance problems in Redux projects.

- **"Redux DevTools is just a logger"** — a serious understatement. Time-travel (jumping to a past state), skip action, import/export state for bug reproduction — these are production tools that directly impact debugging speed in large teams. Knowing these capabilities distinguishes a candidate who has worked with Redux in production from one who only read the docs.

- **Using RTK Query and redux thunks for the same data** — RTK Query manages its own cache in `state[api.reducerPath]`. If you also dispatch thunks that write the same data to a different slice — you end up with two sources of truth and desynchronization. Pick one: either RTK Query owns server-state, or thunks — not both.
