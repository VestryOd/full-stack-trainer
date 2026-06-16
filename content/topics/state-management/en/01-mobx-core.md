# MobX — Reactivity Fundamentals

## Why MobX — and what its core idea actually is

React on its own requires explicit re-render management: `useState`, `useReducer`, `useMemo`, `useCallback` — all of it is manual control over *what* recalculates and *when*. MobX proposes a different contract: **declare data as observable, and everything that depends on it will update automatically**.

```txt
Manual model (React without MobX):
  state changed → you explicitly call setState → React
  re-renders the component → component itself decides what
  to recalculate via memo/useMemo

MobX model:
  observable data changed → MobX automatically finds
  everything that read it (computed, reactions, observer
  components) → updates only those, nothing else
```

This is not magic — it is **explicit runtime dependency tracking**. Every time a `computed` or an `observer` component reads an observable value, MobX registers: "this reader depends on this value." When the value changes — MobX knows exactly who to notify.

## The four reactivity primitives

### observable — observable state

```ts
import { observable, makeObservable } from 'mobx';

class CartStore {
  items: CartItem[] = [];
  discount = 0;

  constructor() {
    makeObservable(this, {
      items: observable,
      discount: observable,
    });
  }
}
```

`observable` makes a value "trackable." MobX wraps it in a Proxy (MobX 6+) that intercepts every read and every write. A read during a `computed` or `observer` execution registers a dependency. A write notifies all subscribers.

**What becomes observable:** primitives (number, string, boolean) are tracked directly; arrays and objects are wrapped in a Proxy version that tracks mutations (push, pop, key assignment). Map and Set are supported via `observable.map()` and `observable.set()`.

### computed — derived values

```ts
import { observable, computed, makeObservable } from 'mobx';

class CartStore {
  items: CartItem[] = [];
  discount = 0;

  constructor() {
    makeObservable(this, {
      items: observable,
      discount: observable,
      total: computed,
      itemCount: computed,
    });
  }

  get total() {
    return this.items.reduce((sum, item) => sum + item.price * item.qty, 0)
      * (1 - this.discount);
  }

  get itemCount() {
    return this.items.reduce((sum, item) => sum + item.qty, 0);
  }
}
```

`computed` is a **memoized derivation**. Key properties:

- Computed **lazily** (only when something reads it).
- **Cached** — if `items` and `discount` haven't changed, re-reading `total` returns the cache without recalculation.
- Automatically **recomputes** only when its dependencies change.
- If a `computed` has no observers — it "sleeps" and does not recompute at all.

This is fundamentally different from `useMemo`: `useMemo` recomputes on every re-render if dependencies changed; `computed` recomputes globally, once, and stays cached until its next dependency change.

### action — state mutations

```ts
import { observable, computed, action, makeObservable } from 'mobx';

class CartStore {
  items: CartItem[] = [];
  discount = 0;

  constructor() {
    makeObservable(this, {
      items: observable,
      discount: observable,
      total: computed,
      addItem: action,
      removeItem: action,
      applyDiscount: action,
    });
  }

  addItem(item: CartItem) {
    const existing = this.items.find(i => i.id === item.id);
    if (existing) {
      existing.qty += item.qty; // mutation inside action — OK
    } else {
      this.items.push(item);
    }
  }

  removeItem(id: string) {
    const index = this.items.findIndex(i => i.id === id);
    if (index !== -1) this.items.splice(index, 1);
  }

  applyDiscount(percent: number) {
    this.discount = percent / 100;
  }
}
```

`action` does two important things:

1. **Notification batching**: all observable changes inside an action accumulate, and reactions (computed, observer components) fire **once after the action completes**, not after each individual line. This is critical for performance.

2. **Strict mode enforcement**: with `configure({ enforceActions: 'always' })`, changing an observable **outside** an action is an error. Actions explicitly mark where mutations are allowed.

### reaction — side effects

```ts
import { reaction, autorun, when } from 'mobx';

const store = new CartStore();

// autorun: runs immediately, then on every dependency change
const disposer = autorun(() => {
  console.log('Cart total:', store.total);
  // MobX recorded that we read store.total
  // next time total changes — this block will re-run
});

// reaction: explicitly separates "what to track" from "what to do"
const disposer2 = reaction(
  () => store.itemCount,                    // tracked expression
  (count, prevCount) => {                   // effect
    analytics.track('cart_items_changed', { count, prevCount });
  }
);

// when: one-shot, fires when the predicate becomes true
when(
  () => store.total > 1000,
  () => store.applyDiscount(10) // auto-discount at threshold
);

// IMPORTANT: always save and call disposer on component unmount
// or store destruction to avoid memory leaks
disposer();
disposer2();
```

## makeObservable vs makeAutoObservable

```ts
// makeObservable — explicit declaration of every field
class UserStore {
  name = '';
  age = 0;
  isAdmin = false;

  constructor() {
    makeObservable(this, {
      name: observable,
      age: observable,
      isAdmin: observable,
      displayName: computed,
      rename: action,
    });
  }

  get displayName() {
    return `${this.name} (${this.age})`;
  }

  rename(newName: string) {
    this.name = newName;
  }
}

// makeAutoObservable — infers types by convention:
// fields → observable, getters → computed, methods → action
class UserStore2 {
  name = '';
  age = 0;
  isAdmin = false;

  constructor() {
    makeAutoObservable(this);
    // equivalent to the explicit declarations above
  }

  get displayName() {
    return `${this.name} (${this.age})`;
  }

  rename(newName: string) {
    this.name = newName;
  }
}
```

**When to use which:**

- `makeAutoObservable` — for most store classes: less code, fewer bugs from missed fields.
- `makeObservable` — when fine-grained control is needed (e.g., some fields observable, some not) or when the class uses inheritance (`makeAutoObservable` has limitations with inheritance).

```ts
// Limitation of makeAutoObservable: does not work with inheritance
class BaseStore {
  isLoading = false;
  constructor() {
    makeAutoObservable(this); // ❌ throws if this class is subclassed
  }
}

class DerivedStore extends BaseStore {
  // MobX cannot correctly initialize the prototype chain
}

// ✅ For inheritance — use makeObservable in each class
class BaseStore2 {
  isLoading = false;
  constructor() {
    makeObservable(this, { isLoading: observable });
  }
}
```

## observer HOC and useObserver — when a React component re-renders

```tsx
import { observer } from 'mobx-react-lite';
import { useLocalObservable } from 'mobx-react-lite';

// observer wraps the component, making it reactive
const CartSummary = observer(({ store }: { store: CartStore }) => {
  // During render, MobX tracks every observable read
  // This component depends on store.total and store.itemCount
  return (
    <div>
      <span>{store.itemCount} items</span>
      <span>Total: ${store.total.toFixed(2)}</span>
    </div>
  );
});

// If store.items changed → store.total recomputed →
// CartSummary re-renders. And only CartSummary.
// The parent component does NOT re-render.
```

**Under the hood**: `observer` wraps the component's render function in a `reaction`. During render, MobX starts tracking dependencies. When render completes — MobX knows which observables were read. When any of them change — React is forced to re-render via `forceUpdate` (or `setState`).

```tsx
// useLocalObservable — local observable state inside a component
const LocalCounter = observer(() => {
  const state = useLocalObservable(() => ({
    count: 0,
    get doubled() { return this.count * 2; },
    increment() { this.count++; },
  }));

  return (
    <div>
      <button onClick={state.increment}>+</button>
      <span>{state.count} (doubled: {state.doubled})</span>
    </div>
  );
});
```

**Re-render granularity** — MobX's key advantage over Context:

```tsx
// ❌ Context: any context field change re-renders ALL consumers
const AppContext = createContext(store);
const PriceTag = () => {
  const { cartStore } = useContext(AppContext);
  return <span>{cartStore.total}</span>;
  // Re-renders on ANY cartStore field change,
  // even if total did not change
};

// ✅ MobX: component re-renders ONLY when the observables
// it actually read during render change
const PriceTag2 = observer(({ store }: { store: CartStore }) => {
  return <span>{store.total}</span>;
  // Re-renders ONLY when store.total changes
  // (or its dependencies: items, discount)
});
```

## Strict mode and enforceActions

```ts
import { configure } from 'mobx';

// Recommended to enable during development
configure({
  enforceActions: 'always',       // observable changes ONLY through actions
  computedRequiresReaction: true,  // computed cannot be read outside reactive context
  reactionRequiresObservable: true, // reaction must read at least one observable
  observableRequiresReaction: true, // observable cannot be read outside reactive context
});

// ❌ Throws in strict mode:
const store = new CartStore();
store.items.push(newItem); // MobX error: not wrapped in action

// ✅ Correct:
store.addItem(newItem); // through the declared action

// ❌ Throws with computedRequiresReaction:
console.log(store.total); // reading computed outside observer/reaction/action

// ✅ Correct: read computed only inside an observer component or reaction
```

Strict mode helps catch patterns early that would lead to hard-to-debug issues in production.

## Common interview traps

- **"MobX automatically makes the whole class reactive"** — no. Only what is explicitly declared via `makeObservable`/`makeAutoObservable`. Fields added dynamically after initialization are not observable (in Proxy-mode MobX 6 dynamic fields work only if originally observable via `observable.object`).

- **Mutating observable outside an action** — the most common mistake. `store.items.push(item)` directly in a component works without strict mode, but breaks notification batching: each line triggers a separate reaction. This hurts both performance and debuggability.

- **Not calling the disposer on reaction/autorun** — classic memory leak. MobX holds a reference to the reaction until explicit `dispose()`. If a reaction was created in a component, it keeps living after unmount and keeps reacting to changes.

- **Reading computed outside reactive context** — `computed` will calculate, but won't be cached and won't update automatically. It behaves like a regular method, not a reactive computation.

- **Destructuring observable objects outside observer** — loses reactivity:
  ```tsx
  const MyComponent = observer(({ store }: { store: CartStore }) => {
    const { total, itemCount } = store; // ❌ destructuring before render
    // total and itemCount are plain numbers now, MobX won't track reads
    return <span>{total}</span>; // no re-render on change
  });

  // ✅ Read directly in JSX:
  const MyComponent2 = observer(({ store }: { store: CartStore }) => {
    return <span>{store.total}</span>; // read inside reactive context
  });
  ```

- **"MobX is like Redux but with less code"** — they are fundamentally different paradigms. Redux: explicit data flow (dispatch → reducer → selector), immutable state, predictability through constraints. MobX: reactive dependency graph, mutable state, predictability through strict mode. They solve different problems and should be compared through the lens of specific project requirements.
