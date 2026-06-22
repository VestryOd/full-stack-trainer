# Context and State Management

## What Context actually is — and what it is not

Context is React's built-in mechanism for making a value available to any component in a subtree without passing it as a prop through every intermediate component. It is a **dependency injection** system, not a state manager.

```txt
WHAT CONTEXT PROVIDES:
  ✓ A way to pass values down a component tree without prop drilling
  ✓ Any consumer in the subtree re-renders when the value changes
  ✓ Multiple independent contexts can coexist

WHAT CONTEXT IS NOT:
  ✗ A replacement for Redux / Zustand / Jotai
  ✗ Optimized for frequent, fine-grained updates
  ✗ A cache (no built-in request deduplication or server-state sync)
```

The "Context is slow" reputation comes from a specific and avoidable pattern. Understanding the re-render mechanics tells you exactly when that reputation is deserved.

---

## Re-render mechanics — the core rule

**Every component that calls `useContext(MyContext)` re-renders whenever the context value changes** — regardless of whether the specific part of the value that component uses has changed.

```tsx
const ThemeContext = React.createContext({ color: 'blue', fontSize: 14 });

function App() {
  const [theme, setTheme] = useState({ color: 'blue', fontSize: 14 });
  return (
    <ThemeContext.Provider value={theme}>
      <Toolbar />
      <Sidebar />
    </ThemeContext.Provider>
  );
}

function Button() {
  const theme = useContext(ThemeContext);
  // Button only uses theme.color. But if theme.fontSize changes,
  // Button STILL re-renders because the context value object reference changed.
  return <button style={{ color: theme.color }}>Click</button>;
}
```

The comparison React uses: `Object.is(previousValue, nextValue)`. When state changes, a new object is created (`setTheme(prev => ({ ...prev, fontSize: 16 }))`), the reference changes, `Object.is` returns false, and **every consumer re-renders** — even ones that don't use `fontSize`.

### Why wrapping in React.memo doesn't help (usually)

```tsx
// ❌ Memo does not help against context changes:
const Button = React.memo(function Button() {
  const theme = useContext(ThemeContext); // subscribes to the context
  return <button style={{ color: theme.color }}>Click</button>;
});
```

`React.memo` skips re-renders when **props** haven't changed. Context changes bypass `React.memo` entirely — the component subscribed to the context directly and will re-render on any context update regardless of memo.

The only way to prevent a context consumer from re-rendering when unrelated parts of the context change is to **split the context**.

---

## Splitting contexts for performance

The rule: put values that change together into one context; put values that change at different rates into separate contexts.

```tsx
// ❌ One monolithic context — any change re-renders ALL consumers:
const AppContext = React.createContext<{
  user: User;
  theme: Theme;
  notifications: Notification[];
  cart: CartItem[];
}>(null!);

// ✅ Separate contexts — each consumer only subscribes to what it needs:
const UserContext = React.createContext<User>(null!);
const ThemeContext = React.createContext<Theme>(null!);
const NotificationsContext = React.createContext<Notification[]>([]);
const CartContext = React.createContext<CartItem[]>([]);

function App() {
  const [user, setUser] = useState<User>(...);
  const [theme, setTheme] = useState<Theme>(...);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);

  return (
    <UserContext.Provider value={user}>
      <ThemeContext.Provider value={theme}>
        <NotificationsContext.Provider value={notifications}>
          <CartContext.Provider value={cart}>
            <App />
          </CartContext.Provider>
        </NotificationsContext.Provider>
      </ThemeContext.Provider>
    </UserContext.Provider>
  );
}
```

Now adding a notification only re-renders `NotificationsContext` consumers. The `CartContext` consumers, `ThemeContext` consumers, and `UserContext` consumers are unaffected.

### Separating state from dispatch

A specific splitting pattern that matters for forms and reducers: put the state and its setter/dispatch in separate contexts.

```tsx
type Action = { type: 'increment' } | { type: 'decrement' } | { type: 'reset' };

const CountStateContext = React.createContext<number>(0);
const CountDispatchContext = React.createContext<React.Dispatch<Action>>(() => {});

function CountProvider({ children }: { children: React.ReactNode }) {
  const [count, dispatch] = useReducer(reducer, 0);

  return (
    <CountDispatchContext.Provider value={dispatch}>
      <CountStateContext.Provider value={count}>
        {children}
      </CountStateContext.Provider>
    </CountDispatchContext.Provider>
  );
}

// A component that only dispatches actions never needs to subscribe to state.
// It will NOT re-render when count changes.
function ResetButton() {
  const dispatch = useContext(CountDispatchContext); // stable reference — dispatch never changes
  return <button onClick={() => dispatch({ type: 'reset' })}>Reset</button>;
}

// A component that only displays state.
function Counter() {
  const count = useContext(CountStateContext);
  return <div>{count}</div>;
}
```

`dispatch` from `useReducer` is **referentially stable** (same object across all renders) — identical to how `setState` from `useState` is stable. Putting it in a separate context means components that only dispatch never re-render due to state changes.

---

## Memoizing the context value

When context value is constructed inline in JSX, it is a new object on every render of the Provider's parent — even if the actual data hasn't changed:

```tsx
// ❌ New object on every render → all consumers re-render on every render:
function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  return (
    <AuthContext.Provider value={{ user, setUser }}> {/* new object every render */}
      {children}
    </AuthContext.Provider>
  );
}

// ✅ Memoized — consumers only re-render when user actually changes:
function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const value = useMemo(() => ({ user, setUser }), [user]);
  // setUser is stable (from useState) → only user changing invalidates the memo
  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}
```

---

## useContext + useReducer — the built-in state management pattern

For medium-complexity state that needs to be shared across many components, `useReducer` + Context is idiomatic React without external dependencies:

```tsx
// 1. Define state shape and actions with discriminated union
type CartState = { items: CartItem[]; total: number };
type CartAction =
  | { type: 'add'; item: CartItem }
  | { type: 'remove'; id: string }
  | { type: 'clear' };

function cartReducer(state: CartState, action: CartAction): CartState {
  switch (action.type) {
    case 'add':
      return {
        items: [...state.items, action.item],
        total: state.total + action.item.price,
      };
    case 'remove': {
      const item = state.items.find(i => i.id === action.id)!;
      return {
        items: state.items.filter(i => i.id !== action.id),
        total: state.total - item.price,
      };
    }
    case 'clear':
      return { items: [], total: 0 };
  }
}

// 2. Split state and dispatch into separate contexts
const CartStateCtx = React.createContext<CartState>(null!);
const CartDispatchCtx = React.createContext<React.Dispatch<CartAction>>(null!);

// 3. Provider encapsulates the reducer
export function CartProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(cartReducer, { items: [], total: 0 });
  return (
    <CartDispatchCtx.Provider value={dispatch}>
      <CartStateCtx.Provider value={state}>
        {children}
      </CartStateCtx.Provider>
    </CartDispatchCtx.Provider>
  );
}

// 4. Custom hooks encapsulate consumption — no raw useContext in components
export function useCartState() {
  const ctx = useContext(CartStateCtx);
  if (ctx === null) throw new Error('useCartState must be used inside CartProvider');
  return ctx;
}

export function useCartDispatch() {
  const ctx = useContext(CartDispatchCtx);
  if (ctx === null) throw new Error('useCartDispatch must be used inside CartProvider');
  return ctx;
}

// 5. Convenience hook for common action
export function useAddToCart() {
  const dispatch = useCartDispatch();
  return useCallback((item: CartItem) => dispatch({ type: 'add', item }), [dispatch]);
}
```

The custom hook wrapper (`useCartState`, `useCartDispatch`) serves two purposes:
1. Throws a descriptive error if the consumer is outside the Provider (far better than the cryptic `null` default value crashing later)
2. Hides the Context API detail — callers don't need to import the context object itself

---

## Context vs prop drilling vs external state managers

```txt
PROP DRILLING
  When: 2-3 levels, few components need the value
  Pro:  explicit, colocated, TypeScript traces the data flow
  Con:  noisy when deeply nested; adding a new prop requires
        updating every intermediate component

CONTEXT
  When: genuinely shared value (auth user, theme, locale, feature flags)
        needed by many components at various depths
  Pro:  no intermediate prop passing; built-in; zero dependencies
  Con:  all consumers re-render on value change;
        not optimized for high-frequency updates;
        no devtools, time-travel, or middleware out of the box

ZUSTAND / JOTAI / REDUX
  When: high-frequency updates (frames, real-time data);
        complex cross-cutting update logic;
        need devtools, middleware, or persistence;
        global server state (use React Query / SWR instead)
  Pro:  fine-grained subscriptions (only components using the
        changed slice re-render); devtools; middleware
  Con:  external dependency; learning curve; overkill for simple cases
```

### When Context is the wrong tool

**High-frequency updates (don't use Context):**
```tsx
// ❌ Context for mouse position — every mousemove re-renders ALL consumers:
const MouseContext = React.createContext({ x: 0, y: 0 });
// Even with React 18 batching, this generates many re-renders per second.
// Use Zustand with subscriptions, or pass mouse position directly to the
// components that need it.
```

**Derived data (don't use Context):**
```tsx
// ❌ Don't put computed/derived values in Context:
const value = useMemo(() => ({
  items,
  sortedItems: [...items].sort(...),   // derived
  totalCount: items.length,             // derived
  expensiveItems: items.filter(...),   // derived
}), [items]);

// ✅ Put only the source data in Context; derive in the consumer:
// Context: items
// Consumer: const sortedItems = useMemo(() => [...items].sort(...), [items]);
```

**Per-component state (don't use Context):**
State that belongs to one component and its direct children should stay local (`useState`). Lifting state unnecessarily to Context makes the component less reusable and harder to test.

---

## createContext default value — a deliberate safety net

```tsx
// The default value is used ONLY when a component calls useContext
// outside of any Provider:
const ThemeContext = React.createContext<Theme>({
  color: 'blue',     // sensible default for components used outside a Provider
  fontSize: 14,
});

// null! as default value — forces consumers to be inside a Provider:
const AuthContext = React.createContext<AuthState>(null!);
// If a component calls useContext(AuthContext) outside AuthProvider,
// it gets null, which will crash immediately — preferable to silent wrong behavior.
// The custom hook wrapper (useAuth) should check for null and throw a clear error.
```

---

## The Provider placement principle

Providers should be placed as **low in the tree as possible** while still covering all consumers. A Provider at the root of the app means every re-render of that Provider (even from unrelated state changes in the Provider's component) will trigger context change checks for all consumers.

```tsx
// ❌ UserProvider at root re-renders whenever the root component re-renders:
function App() {
  const [globalTheme, setGlobalTheme] = useState(...);

  return (
    <UserProvider>  {/* re-renders the Provider on every globalTheme change */}
      <ThemeContext.Provider value={globalTheme}>
        <Routes />
      </ThemeContext.Provider>
    </UserProvider>
  );
}

// ✅ Each Provider is isolated:
function App() {
  return (
    <UserProvider>
      <ThemeProvider>
        <Routes />
      </ThemeProvider>
    </UserProvider>
  );
}
// UserProvider and ThemeProvider each manage their own state internally.
// Changes inside one don't trigger re-renders of the other Provider.
```

---

## Common interview traps

**"Does Context cause unnecessary re-renders?"**
It can, if misused. Context re-renders all consumers when the value changes. The fixes: split contexts by update frequency, memoize the value object, and separate state from dispatch. If those fixes aren't enough, move to a library with fine-grained subscriptions (Zustand, Jotai).

**"Can React.memo prevent re-renders from Context?"**
No. `React.memo` compares props — context changes bypass it entirely. A `React.memo`'d component that calls `useContext` will still re-render when the context value changes.

**"What's the difference between useReducer + Context and Redux?"**
The mechanism is similar (a reducer, a dispatch function, subscriptions). The differences: Redux has devtools (time-travel debugging), middleware (thunks, sagas, logging), a global singleton store, and fine-grained subscriptions (via `useSelector`). Context with `useReducer` has none of these, but also has no external dependency. For an app with 5 contexts, `useReducer` + Context is often sufficient. For complex cross-cutting update logic, async flows, or when devtools are a requirement, Redux Toolkit or Zustand is the better fit.

**"Is the Context API good for server state (API data)?"**
No. Server state has a different lifecycle: it can go stale, needs background refetching, deduplication of concurrent requests, caching with invalidation, and optimistic updates. Context manages local UI state. React Query and SWR are purpose-built for server state and solve all of those problems. Using Context for server state means reinventing the wheel, badly.

**"When would you choose Zustand over Context?"**
When: (1) updates are high-frequency (animations, WebSocket events, real-time collaboration); (2) fine-grained subscriptions are needed — only the slice that changed should trigger re-renders, not all consumers; (3) you need middleware (logging, persistence, devtools); (4) the state is genuinely global and accessed from many unrelated parts of the tree.
