# Patterns in Practice

## From theory to real code

Patterns rarely appear in isolation. In real projects, one architectural problem is solved by combining several patterns, and the ability to recognize those combinations is a sign of engineering maturity.

```txt
Learn a pattern from a book → recognize a pattern in existing code →
  recognize a pattern in "unfinished" code (an anti-pattern) →
    independently choose the right pattern for a new problem

This article covers the third and fourth levels.
```

---

## Anti-patterns — what to spot in code review

An anti-pattern is a solution that seems reasonable, is applied frequently, but systematically creates problems. Knowing anti-patterns is just as important as knowing patterns.

### God Object

A class that knows too much and does too much. Violates SRP, High Cohesion, and Low Coupling simultaneously.

```ts
// ❌ UserManager — God Object: registration, auth, avatars,
// payments, email, analytics, roles — all in one class

class UserManager {
  private db: Database;
  private emailClient: EmailClient;
  private s3: S3Client;
  private stripeClient: StripeClient;
  private redisClient: RedisClient;

  async register(email: string, password: string) { ... }
  async login(email: string, password: string) { ... }
  async logout(userId: string) { ... }
  async uploadAvatar(userId: string, file: Buffer) { ... }
  async deleteAvatar(userId: string) { ... }
  async createSubscription(userId: string, planId: string) { ... }
  async cancelSubscription(userId: string) { ... }
  async sendWelcomeEmail(userId: string) { ... }
  async sendPasswordResetEmail(email: string) { ... }
  async getUserStats(userId: string) { ... }
  async assignRole(userId: string, role: string) { ... }
  async revokeRole(userId: string, role: string) { ... }
  async banUser(userId: string, reason: string) { ... }
  async unbanUser(userId: string) { ... }
  // ... 20 more methods
}

// ✅ Decomposed by responsibility:
class AuthService { /* login, logout, tokens */ }
class UserRegistrationService { /* register, confirm email */ }
class AvatarService { /* upload, delete, resize */ }
class BillingService { /* subscriptions, payments */ }
class NotificationService { /* emails, push */ }
class UserAdminService { /* roles, bans */ }
```

**God Object warning signs:**
- Class name ends with `Manager`, `Handler`, `Controller`, `Processor` — without domain specificity
- Constructor injects 5+ dependencies
- File is longer than 300-500 lines
- A class method doesn't use most of the class's fields

### Spaghetti Code — hidden dependencies and state

```ts
// ❌ Spaghetti code: functions depend on global mutable state,
// call order is non-obvious, side effects are hidden

let currentUser: User | null = null;
let isProcessing = false;
let lastError: Error | null = null;

async function processOrder(orderId: string) {
  if (!currentUser) throw new Error('No user'); // hidden global dependency
  if (isProcessing) return;                      // hidden state
  isProcessing = true;
  try {
    await doPayment(orderId);   // modifies globals internally
    await sendEmail(orderId);   // depends on doPayment's state
    isProcessing = false;
  } catch (e) {
    lastError = e as Error;     // saved to global — when will this be read?
    isProcessing = false;
  }
}

// ✅ Explicit dependencies, no global state:
class OrderProcessor {
  constructor(
    private readonly paymentService: PaymentService,
    private readonly notificationService: NotificationService,
  ) {}

  async process(orderId: string, userId: string): Promise<OrderResult> {
    const payment = await this.paymentService.charge(orderId, userId);
    await this.notificationService.sendConfirmation(userId, orderId);
    return { orderId, paymentId: payment.id };
  }
}
```

### Golden Hammer — "if all you have is a hammer, everything looks like a nail"

```txt
Golden Hammer manifestations:
  - "We use Redux for all state" → even for local UI state in a single
    component that's not needed anywhere else
  - "We use microservices" → for an application built by 2 people
  - "We use a job queue" → for a synchronous 10ms operation
  - "We use Singleton" → for every service

Antidote: explicitly state the problem BEFORE choosing a solution.
A pattern is the answer to "why?", not "what should we use next?"
```

### Primitive Obsession — values without behavior

```ts
// ❌ Primitives everywhere: string as email, string as userId, number as money
function sendInvoice(userId: string, email: string, amount: number) {
  // userId and email are both strings — easy to swap arguments on the call site
  // amount is a number, but is 10.005 a valid amount?
}

sendInvoice(user.email, user.id, 99.99); // swapped — TypeScript won't catch it

// ✅ Value Objects with validation and behavior:
class Email {
  private constructor(private readonly value: string) {}

  static create(raw: string): Email {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(raw)) {
      throw new Error(`Invalid email: ${raw}`);
    }
    return new Email(raw.toLowerCase());
  }

  toString(): string { return this.value; }
}

class Money {
  private constructor(
    private readonly amount: number, // in cents (integer)
    private readonly currency: string,
  ) {}

  static fromDollars(dollars: number, currency = 'USD'): Money {
    return new Money(Math.round(dollars * 100), currency);
  }

  add(other: Money): Money {
    if (this.currency !== other.currency) throw new Error('Currency mismatch');
    return new Money(this.amount + other.amount, this.currency);
  }

  toDisplay(): string { return `$${(this.amount / 100).toFixed(2)}`; }
}

// TypeScript now physically prevents confusing Email and UserId:
function sendInvoice(userId: UserId, email: Email, amount: Money) { ... }
```

### Anemic Domain Model

```ts
// ❌ "Anemic model": data classes without behavior,
// all logic in procedural services

class Order {
  id: string = '';
  items: OrderItem[] = [];
  status: string = 'pending';
  total: number = 0;
  discountPercent: number = 0;
  // Only data, no logic
}

// All business logic scattered across services:
class OrderService {
  calculateTotal(order: Order): number { // computes what Order should know about itself
    return order.items.reduce((s, i) => s + i.price * i.quantity, 0)
      * (1 - order.discountPercent / 100);
  }

  canCancel(order: Order): boolean { // Order could know this itself
    return order.status === 'pending' || order.status === 'paid';
  }
}

// ✅ Rich Domain Model: logic lives where the data lives
class Order {
  private status: OrderStatus = 'pending';
  private items: OrderItem[] = [];
  private discountPercent: number = 0;

  get total(): number {
    return this.items.reduce((s, i) => s + i.price * i.quantity, 0)
      * (1 - this.discountPercent / 100);
  }

  canCancel(): boolean {
    return this.status === 'pending' || this.status === 'paid';
  }

  cancel(): void {
    if (!this.canCancel()) throw new Error(`Cannot cancel order in status: ${this.status}`);
    this.status = 'cancelled';
  }
}
```

---

## Pattern combinations in real projects

### Repository + Proxy (cache) + Decorator (logging)

```ts
// Three patterns, one goal: transparent query caching with logging

interface UserRepository {
  findById(id: string): Promise<User | null>;
  save(user: User): Promise<User>;
}

// Layer 1: real storage (concrete implementation)
class PostgresUserRepository implements UserRepository {
  async findById(id: string) { ... }
  async save(user: User) { ... }
}

// Layer 2: Proxy with caching
class CachedUserRepository implements UserRepository {
  private cache = new Map<string, User>();

  constructor(private readonly inner: UserRepository) {}

  async findById(id: string) {
    return this.cache.get(id) ?? this.inner.findById(id).then(u => {
      if (u) this.cache.set(id, u);
      return u;
    });
  }

  async save(user: User) {
    const saved = await this.inner.save(user);
    this.cache.set(saved.id, saved);
    return saved;
  }
}

// Layer 3: Decorator with logging (wrapping the cache)
class LoggedUserRepository implements UserRepository {
  constructor(
    private readonly inner: UserRepository,
    private readonly logger: Logger,
  ) {}

  async findById(id: string) {
    const start = Date.now();
    const result = await this.inner.findById(id);
    this.logger.debug('findById', { id, found: !!result, ms: Date.now() - start });
    return result;
  }

  async save(user: User) {
    const result = await this.inner.save(user);
    this.logger.info('user.saved', { id: result.id });
    return result;
  }
}

// Assembling the stack in the DI container (NestJS):
{
  provide: UserRepository,
  useFactory: (db: Database, logger: Logger) =>
    new LoggedUserRepository(
      new CachedUserRepository(
        new PostgresUserRepository(db),
      ),
      logger,
    ),
  inject: [DATABASE, LOGGER],
}
```

### Factory + Strategy + Observer: payment processing

```ts
// Factory creates the right Strategy, Observer notifies about the result

interface PaymentStrategy {
  pay(amount: Money, metadata: PaymentMetadata): Promise<PaymentResult>;
}

class StripeStrategy implements PaymentStrategy { ... }
class PaypalStrategy implements PaymentStrategy { ... }
class CryptoStrategy implements PaymentStrategy { ... }

// Factory selects the strategy
function createPaymentStrategy(method: string): PaymentStrategy {
  const strategies: Record<string, () => PaymentStrategy> = {
    stripe: () => new StripeStrategy(stripeClient),
    paypal: () => new PaypalStrategy(paypalClient),
    crypto: () => new CryptoStrategy(cryptoClient),
  };
  const factory = strategies[method];
  if (!factory) throw new Error(`Unknown payment method: ${method}`);
  return factory();
}

// Observer notifies subscribers about the event
class PaymentService extends EventEmitter {
  async processPayment(method: string, amount: Money, meta: PaymentMetadata) {
    const strategy = createPaymentStrategy(method); // Factory
    const result = await strategy.pay(amount, meta); // Strategy
    this.emit('payment:completed', result);           // Observer
    return result;
  }
}

// Subscribers — independent of PaymentService:
paymentService.on('payment:completed', (result) => analytics.track(result));
paymentService.on('payment:completed', (result) => emailService.sendReceipt(result));
paymentService.on('payment:completed', (result) => webhookService.notify(result));
```

---

## Patterns in React

### Compound Components — "component as an API"

Compound Components is when several components work together through a shared context, giving the user compositional flexibility without prop drilling.

```tsx
// ❌ Monolithic component — everything via props, rigid structure:
<Select
  label="Country"
  options={countries}
  placeholder="Choose country"
  renderOption={(opt) => <Flag code={opt.value} />}
  footer={<Button>Add country</Button>}
/>

// ✅ Compound Components — flexible composition:
// Context (Mediator) shares state between components

interface SelectContextValue {
  selected: string | null;
  onSelect: (value: string) => void;
}

const SelectContext = createContext<SelectContextValue | null>(null);

function useSelectContext() {
  const ctx = useContext(SelectContext);
  if (!ctx) throw new Error('Must be used within <Select>');
  return ctx;
}

// Root component — holds state and provides context
function Select({ children, onChange }: { children: React.ReactNode; onChange?: (v: string) => void }) {
  const [selected, setSelected] = useState<string | null>(null);

  const onSelect = useCallback((value: string) => {
    setSelected(value);
    onChange?.(value);
  }, [onChange]);

  return (
    <SelectContext.Provider value={{ selected, onSelect }}>
      <div className="select">{children}</div>
    </SelectContext.Provider>
  );
}

// Sub-components — use context, unaware of each other
function SelectOption({ value, children }: { value: string; children: React.ReactNode }) {
  const { selected, onSelect } = useSelectContext();
  return (
    <div
      className={selected === value ? 'option selected' : 'option'}
      onClick={() => onSelect(value)}
    >
      {children}
    </div>
  );
}

function SelectTrigger({ children }: { children: React.ReactNode }) {
  const { selected } = useSelectContext();
  return <button>{selected ?? children}</button>;
}

// Usage — full structural flexibility:
<Select onChange={setCountry}>
  <SelectTrigger>Choose country</SelectTrigger>
  {countries.map(c => (
    <SelectOption key={c.code} value={c.code}>
      <Flag code={c.code} /> {c.name}
    </SelectOption>
  ))}
  <Button onClick={openAddCountryModal}>Add country</Button>
</Select>
```

**Patterns inside Compound Components:**
- Context → Mediator (shares state without prop drilling)
- SelectContext → Information Expert (component knows its own state)
- Composite (nested SelectOption inside Select)

### Render Props

```tsx
// Render Prop — a component delegates rendering via a function prop.
// Structurally close to Strategy (rendering strategy is supplied from outside).

interface DataFetcherProps<T> {
  url: string;
  render: (data: T | null, loading: boolean, error: Error | null) => React.ReactNode;
}

function DataFetcher<T>({ url, render }: DataFetcherProps<T>) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    setLoading(true);
    fetch(url)
      .then(r => r.json())
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [url]);

  return <>{render(data, loading, error)}</>;
}

// Usage — rendering defined by the consumer (Strategy):
<DataFetcher<User[]>
  url="/api/users"
  render={(users, loading, error) => {
    if (loading) return <Spinner />;
    if (error) return <ErrorMessage error={error} />;
    return <UserList users={users ?? []} />;
  }}
/>

// Modern alternative to Render Props — custom hooks:
// (preferred in 2024+ over Render Props)
function useData<T>(url: string) {
  const [state, setState] = useState<{ data: T | null; loading: boolean; error: Error | null }>({
    data: null, loading: true, error: null,
  });

  useEffect(() => {
    fetch(url).then(r => r.json())
      .then(data => setState({ data, loading: false, error: null }))
      .catch(error => setState({ data: null, loading: false, error }));
  }, [url]);

  return state;
}
```

### HOC (Higher-Order Component) — Decorator in React

```tsx
// HOC — a function taking a component and returning a new component.
// Decorator pattern: adds behavior without modifying the original.

// HOC for render logging (debugging):
function withRenderLogger<P extends object>(
  Component: React.FC<P>,
  componentName: string,
): React.FC<P> {
  return function LoggedComponent(props: P) {
    useEffect(() => {
      console.log(`[${componentName}] rendered`, props);
    });
    return <Component {...props} />;
  };
}

// HOC for retry on data load failure:
function withRetry<P extends { onRetry?: () => void }>(
  Component: React.FC<P>,
  maxRetries = 3,
): React.FC<P> {
  return function WithRetry(props: P) {
    const [retryCount, setRetryCount] = useState(0);

    const handleRetry = useCallback(() => {
      if (retryCount < maxRetries) {
        setRetryCount(c => c + 1);
        props.onRetry?.();
      }
    }, [retryCount, props]);

    return <Component {...props} onRetry={handleRetry} />;
  };
}

// HOC vs custom hooks — when to use which:
// HOC: need to wrap JSX (ErrorBoundary, Theme Provider)
// Custom hook: need to reuse logic (fetch, timer, event listener)
```

---

## Patterns in Node.js/NestJS

### Repository Pattern — abstraction over storage

```ts
// Repository — Pure Fabrication (GRASP): doesn't exist in the domain model,
// but isolates business logic from storage details

interface UserRepository {
  findById(id: string): Promise<User | null>;
  findByEmail(email: string): Promise<User | null>;
  findAll(filters: UserFilters): Promise<User[]>;
  save(user: User): Promise<User>;
  delete(id: string): Promise<void>;
}

// For production: real implementation via TypeORM/Prisma
@Injectable()
class TypeOrmUserRepository implements UserRepository {
  constructor(
    @InjectRepository(UserEntity)
    private readonly repo: Repository<UserEntity>,
  ) {}

  async findById(id: string): Promise<User | null> {
    const entity = await this.repo.findOne({ where: { id } });
    return entity ? UserMapper.toDomain(entity) : null;
  }

  async save(user: User): Promise<User> {
    const entity = UserMapper.toEntity(user);
    const saved = await this.repo.save(entity);
    return UserMapper.toDomain(saved);
  }
  // ...
}

// For tests: in-memory implementation without a database
class InMemoryUserRepository implements UserRepository {
  private store = new Map<string, User>();

  async findById(id: string) { return this.store.get(id) ?? null; }
  async findByEmail(email: string) {
    return [...this.store.values()].find(u => u.email === email) ?? null;
  }
  async findAll(filters: UserFilters) { return [...this.store.values()]; }
  async save(user: User) { this.store.set(user.id, user); return user; }
  async delete(id: string) { this.store.delete(id); }
}
```

### Middleware Pipeline (Chain of Responsibility) in NestJS

```ts
// NestJS Guards, Interceptors, Pipes, Filters — Chain of Responsibility,
// implemented via decorators (metadata).
// Execution order is fixed by the framework:

// Guards → Interceptors (before) → Pipes → Handler → Interceptors (after) → Filters

@Injectable()
class AuthGuard implements CanActivate {
  // Chain of Responsibility: can break the chain (return false)
  canActivate(context: ExecutionContext): boolean {
    const request = context.switchToHttp().getRequest();
    return this.validateToken(request.headers.authorization);
  }
}

@Injectable()
class LoggingInterceptor implements NestInterceptor {
  // Decorator: wraps the handler, adds logging
  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const start = Date.now();
    return next.handle().pipe(
      tap(() => console.log(`Request took ${Date.now() - start}ms`)),
    );
  }
}

@Injectable()
class ParseBodyPipe implements PipeTransform {
  // Chain of Responsibility + Strategy: transforms and validates input
  transform(value: unknown, metadata: ArgumentMetadata) {
    return plainToInstance(metadata.metatype as Type, value);
  }
}
```

### Unit of Work + Repository — domain-level transactions

```ts
// Unit of Work tracks all changes within one operation
// and applies them atomically (one commit)

interface UnitOfWork {
  users: UserRepository;
  orders: OrderRepository;
  commit(): Promise<void>;
  rollback(): Promise<void>;
}

class PostgresUnitOfWork implements UnitOfWork {
  private readonly client: PoolClient;

  private constructor(client: PoolClient) {
    this.client = client;
  }

  static async create(pool: Pool): Promise<PostgresUnitOfWork> {
    const client = await pool.connect();
    await client.query('BEGIN');
    return new PostgresUnitOfWork(client);
  }

  // All repositories work within the same transaction:
  get users(): UserRepository { return new PostgresUserRepository(this.client); }
  get orders(): OrderRepository { return new PostgresOrderRepository(this.client); }

  async commit(): Promise<void> {
    await this.client.query('COMMIT');
    this.client.release();
  }

  async rollback(): Promise<void> {
    await this.client.query('ROLLBACK');
    this.client.release();
  }
}

// Usage:
async function transferOrder(pool: Pool, orderId: string, newUserId: string) {
  const uow = await PostgresUnitOfWork.create(pool);
  try {
    const order = await uow.orders.findById(orderId);
    const newUser = await uow.users.findById(newUserId);
    order.transferTo(newUser);
    await uow.orders.save(order);
    await uow.commit(); // one commit for all changes
  } catch (err) {
    await uow.rollback();
    throw err;
  }
}
```

---

## When NOT to apply a pattern

This is the most important skill: knowing when a pattern is needed is almost as important as knowing how to implement it.

```txt
Situation                         Pattern?         Solution
────────────────────────────────────────────────────────────────
One notification type             Observer         No — just call a function
Two types, third will never       Strategy         No — if/else is more honest
come
Simple CRUD without business      Repository       Maybe not — ORM queries
logic                                              directly in the service are fine
Single "algorithm" step           Template Method  No — just a method
Simple config with 2-3 fields     Builder          No — object literal is clearer
```

**Rule of three:** a pattern is justified when there are (or will almost certainly be) three or more different cases. Until then — YAGNI.

---

## Common interview traps

- **"I use patterns everywhere"** — a red flag. The correct answer includes an understanding of trade-offs and YAGNI. A pattern is a tool for a specific problem, not a default coding style.

- **Not seeing patterns in familiar tools** — Redux is Command+Observer. Express middleware is Chain of Responsibility. React Context is Mediator. Passport.js is Strategy. Inability to name the pattern behind a known library signals that pattern knowledge is book-based, not practical.

- **"Anemic Domain Model is fine"** — it depends. For a CRUD service with no business logic — acceptable. For domain-rich systems (finance, e-commerce, logistics) — technical debt that grows with every iteration.

- **Compound Components only for complex components** — Compound Components is worth applying when a component has several interdependent sub-components. For simple cases — regular props. Criterion: "does the component's user need control over the structure?"

- **Repository as "just a wrapper over ORM"** — Repository solves a different problem: isolating business logic from storage details. If Repository methods mirror the ORM API one-to-one without adding domain semantics — it's just a wrapper and the pattern is being used mindlessly.

- **God Object → immediate refactor** — in legacy code, God Objects are a fact of life. The right approach: don't rewrite everything at once (that's risky), but gradually displace it — extract new services following the Open/Closed principle, keeping the God Object as a facade during the transition period.

- **Not distinguishing patterns from principles** — SOLID and GRASP are principles (guidance on how to think about architecture). GoF patterns are concrete solutions for concrete problems. A pattern may implement several principles. A principle may be realized through several patterns.
