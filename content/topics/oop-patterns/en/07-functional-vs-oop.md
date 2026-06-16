# Functional Programming vs OOP in TypeScript

## A false dichotomy and the real choice

The first thing to understand: in JavaScript/TypeScript the question "FP or OOP?" is not a choice between two mutually exclusive paradigms. It is a choice of **tools for specific problems** in a language that supports both paradigms simultaneously.

```txt
JavaScript — a multi-paradigm language:
  - Classes (class, extends) → OOP tools
  - First-class functions, closures, map/filter/reduce → FP tools
  - Promises, async/await, generators → functional abstractions
  - Prototypal inheritance → a hybrid

React: components are functions, hooks are FP idioms,
  but state and lifecycle are OOP concepts

NestJS: classes, decorators, DI — explicit OOP style,
  but middleware, guards — functional concepts
```

The goal of this article is not to declare a winner, but to provide criteria for choosing.

---

## Core FP concepts and their TypeScript implementations

### Pure Functions

```ts
// Pure function: the same input always produces the same output,
// no side effects (doesn't mutate external state, doesn't read globals)

// ✅ Pure function:
function calculateTax(price: number, taxRate: number): number {
  return price * (1 + taxRate);
}
// calculateTax(100, 0.2) === 120 — always, without exception

// ❌ Impure function (external state dependency):
let taxRate = 0.2; // global state

function calculateTaxImpure(price: number): number {
  return price * (1 + taxRate); // depends on external state
}
// If taxRate changes externally — the result changes.
// The function is not isolated: it can't be tested without setting up the global.

// ❌ Impure function (side effect):
function addUser(users: User[], newUser: User): User[] {
  users.push(newUser); // mutates the input array — side effect!
  return users;
}

// ✅ Pure version — returns a new array:
function addUser(users: readonly User[], newUser: User): User[] {
  return [...users, newUser]; // original untouched
}
```

**Why pure functions matter:**
```txt
- Determinism: easy to test (no setup/teardown)
- Memoization: result can be cached by arguments
- Concurrency: no data races (no shared mutable state)
- Debugging: behavior is predictable without understanding call history
```

### Immutability

```ts
// Immutability: objects are not changed after creation — a new object is created

// ❌ Mutation:
function applyDiscount(order: Order, discountPercent: number): void {
  order.total = order.total * (1 - discountPercent / 100); // mutates the input
}
// Calling code doesn't know its object was changed

// ✅ Immutable update:
function applyDiscount(order: Order, discountPercent: number): Order {
  return {
    ...order,
    total: order.total * (1 - discountPercent / 100),
  };
}

// TypeScript: readonly for enforced immutability
interface OrderItem {
  readonly productId: string;
  readonly price: number;
  readonly quantity: number;
}

type ReadonlyOrder = Readonly<Order>;
type DeepReadonly<T> = { readonly [K in keyof T]: DeepReadonly<T[K]> };

// Immer: immutable updates with mutating syntax (copy-on-write)
import { produce } from 'immer';

const nextState = produce(state, draft => {
  draft.orders[orderId].status = 'shipped'; // looks like mutation, but it's not
});
// state is unchanged; nextState is a new object with the changed nested field
```

### Higher-Order Functions

```ts
// Higher-order function: takes a function as an argument or returns a function

// Functional composition — HOF:
const compose = <T>(...fns: Array<(x: T) => T>) => (x: T): T =>
  fns.reduceRight((acc, fn) => fn(acc), x);

const pipe = <T>(...fns: Array<(x: T) => T>) => (x: T): T =>
  fns.reduce((acc, fn) => fn(acc), x);

// Usage:
const processPrice = pipe(
  (price: number) => price * 1.2,                    // add VAT
  (price: number) => Math.round(price * 100) / 100,  // round
  (price: number) => Math.max(price, 0),             // not less than zero
);

processPrice(99.99); // 119.99

// Currying:
const multiply = (a: number) => (b: number): number => a * b;
const double = multiply(2);
const triple = multiply(3);

double(5); // 10
triple(5); // 15

// Real example: HOF for validation
type Validator<T> = (value: T) => string | null;

function required<T>(message = 'Required'): Validator<T> {
  return (value) => (value === null || value === undefined || value === '') ? message : null;
}

function minLength(min: number): Validator<string> {
  return (value) => value.length < min ? `Minimum ${min} characters` : null;
}

function composeValidators<T>(...validators: Validator<T>[]): Validator<T> {
  return (value) => validators.reduce<string | null>(
    (error, validator) => error ?? validator(value),
    null
  );
}

const validatePassword = composeValidators(
  required<string>('Password is required'),
  minLength(8),
);
```

### Monads and functional containers

```ts
// Option/Maybe — handling absent values without null checks:

class Option<T> {
  private constructor(private readonly value: T | null) {}

  static some<T>(value: T): Option<T> { return new Option(value); }
  static none<T>(): Option<T> { return new Option<T>(null); }

  map<U>(fn: (value: T) => U): Option<U> {
    return this.value !== null ? Option.some(fn(this.value)) : Option.none();
  }

  flatMap<U>(fn: (value: T) => Option<U>): Option<U> {
    return this.value !== null ? fn(this.value) : Option.none();
  }

  getOrElse(defaultValue: T): T {
    return this.value !== null ? this.value : defaultValue;
  }
}

// Without Option:
function findUserEmail(userId: string): string | null {
  const user = users.get(userId);
  if (!user) return null;
  if (!user.contacts) return null;
  return user.contacts.email ?? null;
}

// With Option — chain without null checks:
function findUserEmail(userId: string): Option<string> {
  return Option.some(userId)
    .flatMap(id => users.has(id) ? Option.some(users.get(id)!) : Option.none())
    .flatMap(user => user.contacts ? Option.some(user.contacts) : Option.none())
    .flatMap(contacts => contacts.email ? Option.some(contacts.email) : Option.none());
}

findUserEmail('123').getOrElse('unknown@example.com');

// Result<T, E> — functional error handling (alternative to try/catch):
type Result<T, E> = { ok: true; value: T } | { ok: false; error: E };

function parsePositiveInt(raw: string): Result<number, string> {
  const n = parseInt(raw, 10);
  if (isNaN(n)) return { ok: false, error: `Not a number: ${raw}` };
  if (n <= 0) return { ok: false, error: `Must be positive: ${n}` };
  return { ok: true, value: n };
}

const result = parsePositiveInt('-5');
if (!result.ok) console.error(result.error); // "Must be positive: -5"
```

---

## When a class, when a function

This is a practical question frequently asked in interviews. The answer is neither "always classes" nor "never classes."

### Use classes when:

```ts
// 1. You need to encapsulate STATE + BEHAVIOR together
class RateLimiter {
  private readonly timestamps: number[] = [];

  constructor(
    private readonly maxRequests: number,
    private readonly windowMs: number,
  ) {}

  isAllowed(): boolean {
    const now = Date.now();
    const windowStart = now - this.windowMs;
    while (this.timestamps.length > 0 && this.timestamps[0] < windowStart) {
      this.timestamps.shift();
    }
    if (this.timestamps.length >= this.maxRequests) return false;
    this.timestamps.push(now);
    return true;
  }
}
// Without a class: mutable state (timestamps) can't be expressed
// as a pure function without a closure or external storage

// 2. You need polymorphism (different implementations of one interface)
interface Cache<T> {
  get(key: string): T | undefined;
  set(key: string, value: T, ttlMs?: number): void;
}
class InMemoryCache<T> implements Cache<T> { ... }
class RedisCache<T> implements Cache<T> { ... }

// 3. A DI container requires classes (NestJS, InversifyJS)
@Injectable()
class UserService {
  constructor(private readonly repo: UserRepository) {}
}

// 4. The object has a complex lifecycle (connect, disconnect, dispose)
class DatabasePool {
  async connect() { ... }
  async disconnect() { ... }
  async [Symbol.asyncDispose]() { await this.disconnect(); }
}
```

### Use functions when:

```ts
// 1. No state — data transformation
function formatCurrency(amount: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);
}
// No state — a function is ideal

// 2. One specific operation, no polymorphism needed
async function sendWelcomeEmail(email: string, name: string): Promise<void> {
  await emailClient.send({ to: email, subject: `Welcome, ${name}!`, ... });
}

// 3. Pipeline / transformation chain
const processOrders = pipe(
  filterActiveOrders,
  sortByCreatedAt,
  groupByUser,
  calculateTotals,
);

// 4. React components (functional)
function UserCard({ user }: { user: User }) {
  return <div>{user.name}</div>;
}

// 5. Pure utilities without side effects
const isEmpty = (arr: unknown[]): boolean => arr.length === 0;
const clamp = (value: number, min: number, max: number): number =>
  Math.min(Math.max(value, min), max);
```

### Pattern: functions for logic + classes for state

```ts
// Best practice in TypeScript: write business logic as pure functions,
// encapsulate state and infrastructure in classes

// Pure functions — business rules, easy to test:
function calculateOrderTotal(items: readonly OrderItem[], discountPercent: number): number {
  const subtotal = items.reduce((s, i) => s + i.price * i.quantity, 0);
  return subtotal * (1 - discountPercent / 100);
}

function canApplyDiscount(user: User, order: Order): boolean {
  return user.isPremium && order.total > 100;
}

// Service class — orchestration with state (dependencies via DI):
class OrderService {
  constructor(
    private readonly orderRepo: OrderRepository,
    private readonly userRepo: UserRepository,
  ) {}

  async createOrder(userId: string, items: OrderItem[]): Promise<Order> {
    const user = await this.userRepo.findById(userId);
    if (!user) throw new Error('User not found');

    const discountPercent = user.isPremium ? 15 : 0;
    // Pure function — unaware of the DB, easily tested in isolation:
    const total = calculateOrderTotal(items, discountPercent);

    return this.orderRepo.save({ userId, items, total, discountPercent });
  }
}
```

---

## Composition vs Inheritance

"Prefer composition over inheritance" is one of the oldest OOP guidelines, but it's often misunderstood as "never use inheritance." That's wrong.

### Problems with inheritance

```ts
// ❌ Deep inheritance hierarchy — brittle and complex

class Animal {
  eat() { console.log('eating'); }
  sleep() { console.log('sleeping'); }
}

class Bird extends Animal {
  fly() { console.log('flying'); }
}

class Duck extends Bird {
  quack() { console.log('quacking'); }
}

class RubberDuck extends Duck {
  // A rubber duck shouldn't fly, but fly() is inherited
  fly() { throw new Error('Rubber ducks cannot fly'); } // LSP violated
}

// Problems:
// 1. Fragile base class: changing Animal breaks the entire hierarchy
// 2. "Banana-gorilla problem": you want a banana (quack),
//    you get a gorilla holding the entire jungle (Animal + Bird + Duck)
// 3. Single base class = single axis of variation, but ducks vary
//    on MULTIPLE axes (flying/non-flying, living/toy)
```

```ts
// ✅ Composition via interfaces + behaviors:

interface Eater { eat(): void; }
interface Sleeper { sleep(): void; }
interface Flyer { fly(): void; }
interface Quacker { quack(): void; }

// Implementations — small and independent:
const eatingBehavior: Eater = { eat: () => console.log('eating') };
const flyingBehavior: Flyer = { fly: () => console.log('flying') };

// Duck — composes the needed behaviors:
class Duck implements Eater, Sleeper, Flyer, Quacker {
  private readonly eater = eatingBehavior;
  private readonly flyer = flyingBehavior;

  eat() { this.eater.eat(); }
  sleep() { console.log('sleeping'); }
  fly() { this.flyer.fly(); }
  quack() { console.log('quacking'); }
}

// RubberDuck — composes only what it can do:
class RubberDuck implements Quacker {
  quack() { console.log('squeaking'); }
  // No fly() — and that's correct: RubberDuck simply doesn't implement Flyer
}
```

### When inheritance is justified

```ts
// Inheritance is justified in three cases:

// 1. The subtype IS genuinely a special case of the base type (IS-A)
//    — and LSP is respected
class HttpError extends Error {
  constructor(
    public readonly statusCode: number,
    message: string,
  ) {
    super(message);
    this.name = 'HttpError';
  }
}

class NotFoundError extends HttpError {
  constructor(resource: string) {
    super(404, `${resource} not found`);
    this.name = 'NotFoundError';
  }
}
// NotFoundError IS-A HttpError IS-A Error — LSP respected at every level

// 2. Template Method: base class fixes the algorithm, subclass provides details
abstract class BaseExporter {
  async export(data: unknown[]): Promise<void> { ... } // template
  protected abstract serialize(data: unknown[]): string; // overridden
}

// 3. Framework base classes (EventEmitter, React.Component)
class OrderService extends EventEmitter {
  // Inheriting from EventEmitter is reasonable: OrderService IS-AN EventEmitter
}
```

### Mixin pattern as an alternative to multiple inheritance

```ts
// TypeScript doesn't support multiple class inheritance,
// but supports mixins via typed functions:

type Constructor<T = object> = new (...args: unknown[]) => T;

function Timestamped<TBase extends Constructor>(Base: TBase) {
  return class extends Base {
    createdAt = new Date();
    updatedAt = new Date();

    touch() { this.updatedAt = new Date(); }
  };
}

function Activatable<TBase extends Constructor>(Base: TBase) {
  return class extends Base {
    isActive = true;

    activate() { this.isActive = true; }
    deactivate() { this.isActive = false; }
  };
}

class User {
  constructor(public name: string) {}
}

// Composing behaviors via mixins:
const TimestampedUser = Timestamped(User);
const ActivatableTimestampedUser = Activatable(Timestamped(User));

const user = new ActivatableTimestampedUser('Alice');
user.touch();       // Timestamped
user.deactivate();  // Activatable
```

---

## FP patterns in the React ecosystem

### Hooks as FP abstractions

```tsx
// Hooks are functional abstractions over state and effects.
// They allow composing behavior without component inheritance.

// A custom hook = a closure with built-in state:
function useDebounce<T>(value: T, delayMs: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delayMs);
    return () => clearTimeout(timer); // cleanup — functional pattern
  }, [value, delayMs]);

  return debouncedValue;
}

// Hooks compose like functions:
function useUserSearch(initialQuery = '') {
  const [query, setQuery] = useState(initialQuery);
  const debouncedQuery = useDebounce(query, 300); // composing hooks
  const { data: users, loading } = useData<User[]>(`/api/users?q=${debouncedQuery}`);

  return { query, setQuery, users, loading };
}

// Usage:
function UserSearch() {
  const { query, setQuery, users, loading } = useUserSearch();
  return (
    <>
      <input value={query} onChange={e => setQuery(e.target.value)} />
      {loading ? <Spinner /> : <UserList users={users ?? []} />}
    </>
  );
}
```

### Functional state updates

```tsx
// Functional updater in useState — a pure function of the previous state:

// ❌ Unsafe with React batching:
setCount(count + 1); // closes over a stale count

// ✅ Functional updater — always works with the current state:
setCount(prev => prev + 1);

// Application — accumulation:
function CartProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);

  const addItem = useCallback((item: CartItem) => {
    setItems(prev => {
      const existing = prev.find(i => i.productId === item.productId);
      if (existing) {
        // Immutable update:
        return prev.map(i =>
          i.productId === item.productId
            ? { ...i, quantity: i.quantity + item.quantity }
            : i
        );
      }
      return [...prev, item];
    });
  }, []);

  // ...
}
```

---

## Immutability in Node.js

### Object.freeze and as const

```ts
// Object.freeze — runtime immutability:
const DEFAULT_CONFIG = Object.freeze({
  timeout: 5000,
  retries: 3,
  baseUrl: 'https://api.example.com',
});
// DEFAULT_CONFIG.timeout = 1000; → TypeError at runtime

// as const — compile-time immutability (TypeScript):
const HTTP_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'] as const;
type HttpMethod = typeof HTTP_METHODS[number]; // 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
// HTTP_METHODS[0] has type 'GET', not string

const STATUS_CODES = {
  OK: 200,
  NOT_FOUND: 404,
  INTERNAL_ERROR: 500,
} as const;
type StatusCode = typeof STATUS_CODES[keyof typeof STATUS_CODES]; // 200 | 404 | 500
```

### Immutable data structures in performance-sensitive code

```ts
// Problem with naive immutability: spread creates a copy — O(n) per operation
// For large objects or frequent updates, this is a problem

// ❌ For a large array (10 000+ elements) every update is O(n):
const nextItems = [...items, newItem]; // copies the entire array

// ✅ Immer: structural sharing — only the changed branches of the tree are copied
import { produce, enableMapSet } from 'immer';

enableMapSet(); // enable Map/Set support

const nextState = produce(state, draft => {
  draft.users.set(newUser.id, newUser); // Map updated efficiently
  draft.orderIds.push(orderId);         // Array: only push — immer knows what to do
});

// Immer uses Proxy under the hood: tracks changes and clones
// only the changed parts of the tree (structural sharing)
```

---

## Practical guide: what to choose

```txt
Task                                Recommended approach
──────────────────────────────────────────────────────────────────────
Data transformation                 Pure functions
  (formatting, calculations)

Components with reusable logic      Custom hooks (functions)
  without state

Services with dependencies          Classes + DI
  (repositories, API clients)

Objects with invariants             Classes with private fields
  (Entity, Value Object)              and mutator methods

One of a set of algorithms          Strategy (class or function)

Reacting to events                  Observer/EventEmitter (classes)
  across layers

Flexible UI without prop drilling   Compound Components + Context

Complex finite state machines       XState (FP + State Machine)

Immutable updates of                Immer / spread / structuredClone
  nested state
```

---

## Common interview traps

- **"FP is better than OOP" or "OOP is better than FP"** — in JavaScript/TypeScript this is a false dichotomy. The correct answer: these are different tools. FP excels at data transformations and testable logic. OOP excels at state encapsulation and polymorphism. React uses both approaches.

- **"Classes = OOP, functions = FP"** — an oversimplification. FP is a paradigm with pure functions, immutability, and composition. A class can contain pure methods (FP style). A function can have side effects (not FP).

- **"Immutability is slow"** — for most cases, spread and structuredClone are fast enough. For performance-critical code — Immer with structural sharing. Premature optimization vs code readability: correct first, fast later.

- **"Inheritance is bad, always use composition"** — too categorical. Inheritance is justified for error hierarchies (`Error → HttpError → NotFoundError`), Template Method, and framework base classes. The problem is not inheritance itself, but deep hierarchies and LSP violations.

- **"Hooks replaced class components — so FP beats OOP"** — hooks solve a specific React problem (reusing stateful logic without HOC wrappers). That's not a manifesto for FP. Behind hooks lie State, Observer, and Mediator from OOP patterns.

- **Not knowing Result/Option** — TypeScript interviews increasingly ask about functional error handling. Knowing `Result<T, E>` as an alternative to exceptions, and understanding when to use which (exceptions — for genuinely exceptional situations, Result — for expected business-logic errors) is senior-level knowledge.

- **Confusing immutability and const-ness** — `const` in JavaScript prevents reassigning a variable, not mutating an object. Immutability is about the impossibility of mutating the object itself. `const arr = []` + `arr.push(1)` — a constant variable, a mutable object.
