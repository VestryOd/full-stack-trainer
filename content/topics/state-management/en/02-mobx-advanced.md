# MobX — Advanced Patterns

## Async actions: flow vs async/await

Async code in MobX is a common source of confusion. The problem is that `async/await` breaks the action context: code after the first `await` executes **outside** the original action.

```ts
import { action, makeObservable, observable, runInAction } from 'mobx';

class UserStore {
  user: User | null = null;
  isLoading = false;
  error: string | null = null;

  constructor() {
    makeObservable(this, {
      user: observable,
      isLoading: observable,
      error: observable,
      fetchUser: action,  // only the start of the method is an action
    });
  }

  // ❌ Problem: mutations after await are outside the action
  async fetchUser_BROKEN(id: string) {
    this.isLoading = true; // OK — synchronous part, inside action
    try {
      const user = await api.getUser(id); // await breaks out of action
      this.user = user;       // ❌ MobX warning in strict mode:
      this.isLoading = false; //    mutation outside action
    } catch (e) {
      this.error = String(e); // ❌ also outside action
      this.isLoading = false;
    }
  }

  // ✅ Option 1: runInAction for each "mutation block after await"
  async fetchUser(id: string) {
    this.isLoading = true;
    try {
      const user = await api.getUser(id);
      runInAction(() => {
        this.user = user;
        this.isLoading = false;
      });
    } catch (e) {
      runInAction(() => {
        this.error = String(e);
        this.isLoading = false;
      });
    }
  }
}
```

### flow — the idiomatic MobX solution for async

`flow` uses generators instead of async/await. Inside it, `yield` does the same as `await`, but MobX automatically wraps each "step" after yield in an action:

```ts
import { flow, makeObservable, observable } from 'mobx';

class UserStore {
  user: User | null = null;
  isLoading = false;
  error: string | null = null;

  constructor() {
    makeObservable(this, {
      user: observable,
      isLoading: observable,
      error: observable,
      fetchUser: flow, // not action — flow
    });
  }

  // ✅ flow: generator, yield instead of await
  // All mutations are automatically in action context
  *fetchUser(id: string) {
    this.isLoading = true;
    try {
      const user: User = yield api.getUser(id); // yield = await
      this.user = user;       // automatically in action — OK
      this.isLoading = false;
    } catch (e) {
      this.error = String(e); // also OK
      this.isLoading = false;
    }
  }
}

// Usage is identical to an async method:
const store = new UserStore();
await store.fetchUser('123');
```

**Extra advantage of flow — cancellation:**

```ts
class SearchStore {
  results: SearchResult[] = [];
  isLoading = false;

  constructor() {
    makeObservable(this, {
      results: observable,
      isLoading: observable,
      search: flow,
    });
  }

  *search(query: string) {
    this.isLoading = true;
    this.results = yield api.search(query);
    this.isLoading = false;
  }
}

const store = new SearchStore();
const cancel = store.search('react'); // flow returns an object with cancel
// ...user changed the query before the response arrived
cancel(); // cancel the previous search
store.search('redux'); // start a new one
```

**When to use which:**

```txt
runInAction  — when you need to quickly fix an existing async method
               or the logic is simple (one request, one mutation block)

flow         — the idiomatic MobX approach, preferred for:
               - complex async scenarios with multiple awaits
               - when cancellation is needed
               - new stores (makes it clearer this is a "MobX async action")
```

## reaction / autorun / when — when to use each

All three create a reaction to observable changes, but with different contracts:

```ts
import { autorun, reaction, when } from 'mobx';

const store = new CartStore();

// autorun:
// - runs IMMEDIATELY on creation (side effect on initialization)
// - tracks dependencies dynamically (what it reads — it tracks)
// - runs on ANY change to read observables
const dispose1 = autorun(() => {
  // Runs now, and then on every change to
  // store.total or store.itemCount
  document.title = `Cart (${store.itemCount}) — $${store.total}`;
});

// reaction:
// - does NOT run on creation (only on changes)
// - explicitly separates "what to track" from "what to do"
// - receives previous and current value
const dispose2 = reaction(
  () => store.total,           // tracked expression — MobX watches this
  (total, prevTotal) => {      // effect — runs when it changes
    if (total > prevTotal) {
      analytics.track('cart_value_increased', { total, prevTotal });
    }
  },
  { fireImmediately: false }   // default — but can be set to behave like autorun
);

// when:
// - one-shot: fires when the predicate becomes true and self-disposes
// - returns a Promise (can be awaited)
// - with timeout: auto-rejects if condition wasn't met in time
const dispose3 = when(
  () => store.total > 500,
  () => {
    notification.show('You qualify for free shipping!');
  }
);

// await variant of when:
async function waitForCartReady() {
  await when(() => store.isLoaded);
  // code after this line runs only when isLoaded becomes true
  return store.total;
}
```

**Practical selection rules:**

```txt
autorun  — logging, syncing with external systems
           (document.title, localStorage), that should
           fire immediately and on every change

reaction — analytics, triggering requests on filter change,
           debounced form saving — when you need the previous
           value or don't want an immediate initial run

when     — waiting for a condition: "when data loads",
           "when user is authenticated" — one-shot trigger
```

## RootStore — the store composition pattern

The most common way to organize MobX in medium and large applications is RootStore, which creates all stores and passes them a reference to itself:

```ts
// stores/CartStore.ts
import type { RootStore } from './RootStore';

export class CartStore {
  items: CartItem[] = [];

  constructor(private root: RootStore) {
    makeAutoObservable(this);
  }

  get total() {
    return this.items.reduce((sum, item) => sum + item.price * item.qty, 0);
  }

  // Access to another store via root — no direct dependency
  get isEligibleForDiscount() {
    return this.root.userStore.isPremium && this.total > 100;
  }

  addItem(item: CartItem) {
    this.items.push(item);
    this.root.analyticsStore.track('item_added', { item });
  }
}

// stores/UserStore.ts
import type { RootStore } from './RootStore';

export class UserStore {
  currentUser: User | null = null;
  isPremium = false;

  constructor(private root: RootStore) {
    makeAutoObservable(this);
  }

  *login(credentials: LoginCredentials) {
    const user: User = yield authApi.login(credentials);
    this.currentUser = user;
    this.isPremium = user.subscription === 'premium';
    yield this.root.cartStore.loadSavedCart(user.id);
  }
}

// stores/RootStore.ts
import { CartStore } from './CartStore';
import { UserStore } from './UserStore';
import { AnalyticsStore } from './AnalyticsStore';

export class RootStore {
  cartStore: CartStore;
  userStore: UserStore;
  analyticsStore: AnalyticsStore;

  constructor() {
    // Each store receives a reference to root
    this.cartStore = new CartStore(this);
    this.userStore = new UserStore(this);
    this.analyticsStore = new AnalyticsStore(this);
  }
}

export const rootStore = new RootStore();
```

**Connecting to React via Context:**

```tsx
// stores/StoreContext.tsx
import React, { createContext, useContext } from 'react';
import { RootStore } from './RootStore';

const StoreContext = createContext<RootStore | null>(null);

export const StoreProvider: React.FC<{
  store: RootStore;
  children: React.ReactNode;
}> = ({ store, children }) => (
  <StoreContext.Provider value={store}>
    {children}
  </StoreContext.Provider>
);

// Typed hooks for each store
export const useCartStore = () => {
  const root = useContext(StoreContext);
  if (!root) throw new Error('StoreContext not provided');
  return root.cartStore;
};

export const useUserStore = () => {
  const root = useContext(StoreContext);
  if (!root) throw new Error('StoreContext not provided');
  return root.userStore;
};

// App.tsx
const store = new RootStore();

function App() {
  return (
    <StoreProvider store={store}>
      <Router />
    </StoreProvider>
  );
}

// In a component:
const CartPage = observer(() => {
  const cartStore = useCartStore();
  return <div>{cartStore.total}</div>;
});
```

**Why RootStore instead of direct store imports:**

```ts
// ❌ Direct imports — problems:
import { cartStore } from './CartStore'; // singleton — hard to test
import { userStore } from './UserStore'; // circular deps when cross-store refs
//  (UserStore imports CartStore and vice versa)

// ✅ RootStore solves both:
// - In tests, create a new RootStore for each test (no global state)
// - Stores don't import each other — they communicate via root (no cycles)
```

## MobX 6: Proxy-based vs decorators

In MobX 5 and earlier, decorators were the primary way to declare observable:

```ts
// MobX 4/5 — decorators (legacy)
import { observable, computed, action } from 'mobx';

class CartStore {
  @observable items: CartItem[] = [];
  @observable discount = 0;

  @computed get total() {
    return this.items.reduce(
      (sum, item) => sum + item.price * item.qty, 0
    ) * (1 - this.discount);
  }

  @action addItem(item: CartItem) {
    this.items.push(item);
  }
}
```

```ts
// MobX 6 — makeObservable/makeAutoObservable (current standard)
class CartStore {
  items: CartItem[] = [];
  discount = 0;

  constructor() {
    makeAutoObservable(this);
  }

  get total() {
    return this.items.reduce(
      (sum, item) => sum + item.price * item.qty, 0
    ) * (1 - this.discount);
  }

  addItem(item: CartItem) {
    this.items.push(item);
  }
}
```

**Why MobX 6 moved to Proxy:**

1. **Standard**: JavaScript decorators stayed in proposal-stage for years, and different implementations (Babel, TypeScript) had divergent behavior. Proxy is a stable part of ES2015+.

2. **No code transformation**: The Proxy version works without Babel plugins or special tsconfig flags.

3. **Decorators still work in MobX 6** — via separate import + `"experimentalDecorators": true` in tsconfig. But for new projects `makeAutoObservable` is preferred.

```ts
// MobX 6 with decorators (legacy compatibility)
import { observable, computed, action, makeObservable } from 'mobx';

class CartStore {
  @observable items: CartItem[] = [];

  constructor() {
    makeObservable(this); // in MobX 6, explicit call required even with decorators
  }

  @computed get total() { /* ... */ }
  @action addItem(item: CartItem) { /* ... */ }
}
```

## Testing MobX stores

MobX stores are plain classes — easy to test without React mocks or component rendering:

```ts
// stores/__tests__/CartStore.test.ts
import { CartStore } from '../CartStore';
import { RootStore } from '../RootStore';

describe('CartStore', () => {
  let rootStore: RootStore;
  let cartStore: CartStore;

  beforeEach(() => {
    // Fresh RootStore for each test — isolated state
    rootStore = new RootStore();
    cartStore = rootStore.cartStore;
  });

  test('addItem increases itemCount', () => {
    cartStore.addItem({ id: '1', name: 'Book', price: 20, qty: 1 });
    expect(cartStore.itemCount).toBe(1);
  });

  test('addItem to existing increments qty', () => {
    cartStore.addItem({ id: '1', name: 'Book', price: 20, qty: 1 });
    cartStore.addItem({ id: '1', name: 'Book', price: 20, qty: 2 });
    expect(cartStore.items[0].qty).toBe(3);
    expect(cartStore.itemCount).toBe(3);
  });

  test('total applies discount', () => {
    cartStore.addItem({ id: '1', name: 'Book', price: 100, qty: 1 });
    cartStore.applyDiscount(20); // 20%
    expect(cartStore.total).toBeCloseTo(80);
  });

  test('computed total is memoized', () => {
    cartStore.addItem({ id: '1', name: 'Book', price: 50, qty: 2 });
    const total1 = cartStore.total;
    const total2 = cartStore.total; // not recalculated
    expect(total1).toBe(total2);
    expect(total1).toBe(100);
  });
});
```

**Testing async flow:**

```ts
// stores/__tests__/UserStore.test.ts
jest.mock('../../api/authApi', () => ({
  login: jest.fn(),
}));
import { login } from '../../api/authApi';

describe('UserStore.login', () => {
  test('sets currentUser on successful login', async () => {
    const mockUser = { id: '1', name: 'Alice', subscription: 'premium' };
    (login as jest.Mock).mockResolvedValue(mockUser);

    const rootStore = new RootStore();
    await rootStore.userStore.login({ email: 'a@b.com', password: '123' });

    expect(rootStore.userStore.currentUser).toEqual(mockUser);
    expect(rootStore.userStore.isPremium).toBe(true);
  });

  test('handles login failure', async () => {
    (login as jest.Mock).mockRejectedValue(new Error('Invalid credentials'));

    const rootStore = new RootStore();
    await expect(
      rootStore.userStore.login({ email: 'a@b.com', password: 'wrong' })
    ).rejects.toThrow('Invalid credentials');

    expect(rootStore.userStore.currentUser).toBeNull();
  });
});
```

**Testing reactions:**

```ts
import { autorun } from 'mobx';

test('reaction fires when total changes', () => {
  const rootStore = new RootStore();
  const { cartStore } = rootStore;

  const observed: number[] = [];
  const dispose = autorun(() => {
    observed.push(cartStore.total);
  });

  cartStore.addItem({ id: '1', name: 'A', price: 10, qty: 1 });
  cartStore.addItem({ id: '2', name: 'B', price: 20, qty: 1 });

  expect(observed).toEqual([0, 10, 30]); // initial + two reactions

  dispose();
});
```

**Testing observer components** (when React integration specifically needs verification):

```tsx
import { render, screen, act } from '@testing-library/react';
import { observer } from 'mobx-react-lite';

const CartTotal = observer(({ store }: { store: CartStore }) => (
  <span data-testid="total">{store.total}</span>
));

test('CartTotal re-renders when total changes', () => {
  const rootStore = new RootStore();

  render(
    <StoreProvider store={rootStore}>
      <CartTotal store={rootStore.cartStore} />
    </StoreProvider>
  );

  expect(screen.getByTestId('total').textContent).toBe('0');

  act(() => {
    rootStore.cartStore.addItem({ id: '1', name: 'A', price: 42, qty: 1 });
  });

  expect(screen.getByTestId('total').textContent).toBe('42');
});
```

## Common interview traps

- **"flow is just syntactic sugar over async/await"** — not quite. `flow` uses generators, which enables cancellation via `cancel()`. With async/await, cancellation requires AbortController or manual flags. This is a real technical difference that matters in UI (race conditions on fast input).

- **"You can just write async methods without flow/runInAction"** — works without strict mode, but breaks batching. Each assignment after `await` is a separate synchronous notification, meaning the component may re-render between `this.isLoading = false` and `this.user = user`, showing an intermediate state.

- **Not understanding the difference between autorun and reaction** — key distinction: `autorun` runs immediately, `reaction` does not. `reaction` receives the previous value, `autorun` does not. Interviewers frequently ask when to use which.

- **Circular dependencies between stores via direct imports** — a classic scaling mistake. `UserStore` imports `CartStore`, `CartStore` imports `UserStore` → Node.js resolves one of them as `undefined` at startup. RootStore via `root` reference eliminates all cross-store imports.

- **Not disposing reactions in components** — if `autorun`/`reaction` is created in `useEffect` without returning a disposer function, MobX keeps the component alive in memory after unmount and continues triggering re-renders (or React strict mode throws a warning):
  ```ts
  useEffect(() => {
    const dispose = autorun(() => {
      document.title = store.cartStore.itemCount.toString();
    });
    return dispose; // ← required
  }, []);
  ```
