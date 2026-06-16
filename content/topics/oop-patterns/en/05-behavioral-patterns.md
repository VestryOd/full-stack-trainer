# Behavioral Patterns

## Why behavioral patterns exist

Behavioral patterns describe **how objects interact and distribute responsibility** at runtime. Where structural patterns answer "how to connect objects," behavioral patterns answer "how do they communicate with each other."

```txt
Structural  → "static relationships between classes and objects"
Behavioral  → "dynamic interaction protocols between objects"
```

Behavioral patterns are the largest GoF group. They address: how to avoid tight coupling between a message sender and receiver, how to encapsulate an algorithm, how to react to state changes.

---

## Observer — "subscribe to events"

> Defines a one-to-many dependency between objects so that when one object changes state, all its dependents are notified and updated automatically.

Observer is one of the most fundamental patterns in frontend and Node.js development. EventEmitter, DOM events, React state, RxJS — all are implementations of Observer.

### Basic implementation

```ts
interface Observer<T> {
  update(data: T): void;
}

interface Observable<T> {
  subscribe(observer: Observer<T>): void;
  unsubscribe(observer: Observer<T>): void;
  notify(data: T): void;
}

class EventBus<T> implements Observable<T> {
  private observers = new Set<Observer<T>>();

  subscribe(observer: Observer<T>): void {
    this.observers.add(observer);
  }

  unsubscribe(observer: Observer<T>): void {
    this.observers.delete(observer);
  }

  notify(data: T): void {
    this.observers.forEach(observer => observer.update(data));
  }
}

// Usage:
interface UserCreatedEvent {
  userId: string;
  email: string;
}

const userEvents = new EventBus<UserCreatedEvent>();

// Subscribers — independent from each other, unaware of UserService
const emailObserver: Observer<UserCreatedEvent> = {
  update: ({ email }) => emailService.sendWelcome(email),
};
const analyticsObserver: Observer<UserCreatedEvent> = {
  update: ({ userId }) => analytics.track('user_created', { userId }),
};

userEvents.subscribe(emailObserver);
userEvents.subscribe(analyticsObserver);

// UserService only publishes the event, doesn't know about subscribers:
class UserService {
  async register(email: string, password: string) {
    const user = await this.userRepo.create(email, password);
    userEvents.notify({ userId: user.id, email });
    return user;
  }
}
```

### Node.js EventEmitter — Observer in the standard library

```ts
import { EventEmitter } from 'node:events';

// EventEmitter is Node.js's built-in Observer implementation
class OrderService extends EventEmitter {
  async placeOrder(dto: CreateOrderDto): Promise<Order> {
    const order = await this.orderRepo.save(dto);
    // Observer pattern: emit instead of calling subscribers directly
    this.emit('order:placed', order);
    return order;
  }
}

const orderService = new OrderService();

// Subscribers register from outside — OrderService doesn't know about them
orderService.on('order:placed', async (order: Order) => {
  await notificationService.sendConfirmation(order);
});

orderService.on('order:placed', async (order: Order) => {
  await inventoryService.reserveStock(order.items);
});

// Always subscribe to 'error' — an unhandled emit('error') crashes the process
// (see [Node.js Fundamentals])
orderService.on('error', (err) => logger.error('OrderService error', err));
```

### Observer in React — useEffect and custom hooks

```tsx
// React state is Observable: when it changes, all subscribing components
// (those using that state) re-render

// A custom hook as Observable — subscribes to an external event:
function useWindowSize() {
  const [size, setSize] = useState({ width: window.innerWidth, height: window.innerHeight });

  useEffect(() => {
    const handler = () => setSize({ width: window.innerWidth, height: window.innerHeight });
    // Subscribe:
    window.addEventListener('resize', handler);
    // Unsubscribe on unmount — critical!
    return () => window.removeEventListener('resize', handler);
  }, []);

  return size;
}
```

### When Observer becomes a problem

```txt
Observer problems in large applications:
  - "Reaction chains": event A → event B → event C → ...
    hard to trace what happens when a user takes a specific action
  - Memory leaks: subscriber lives longer than Observable — didn't unsubscribe → leak
  - Execution order: subscribers are called in registration order,
    but there is no explicit guarantee — if one subscriber depends
    on another's result, that's hidden coupling
```

---

## Strategy — "encapsulate an algorithm"

> Defines a family of algorithms, encapsulates each one, and makes them interchangeable. Lets the algorithm vary independently from clients that use it.

Strategy is the pattern for "swappable behavior." If you have a place in the code where the algorithm needs to vary based on context (sorting, validation, pricing, authentication), Strategy is the right choice.

### Example: pricing strategies

```ts
interface PricingStrategy {
  calculate(basePrice: number, context: PricingContext): number;
}

interface PricingContext {
  userId: string;
  isPremium: boolean;
  couponCode?: string;
  quantity: number;
}

class StandardPricing implements PricingStrategy {
  calculate(basePrice: number, context: PricingContext): number {
    return basePrice * context.quantity;
  }
}

class PremiumPricing implements PricingStrategy {
  calculate(basePrice: number, context: PricingContext): number {
    return basePrice * context.quantity * 0.85; // 15% discount for premium
  }
}

class BulkPricing implements PricingStrategy {
  calculate(basePrice: number, context: PricingContext): number {
    const discount = context.quantity >= 100 ? 0.30 : context.quantity >= 10 ? 0.15 : 0;
    return basePrice * context.quantity * (1 - discount);
  }
}

class CouponPricing implements PricingStrategy {
  constructor(private readonly coupons: Map<string, number>) {}

  calculate(basePrice: number, context: PricingContext): number {
    const discount = context.couponCode
      ? this.coupons.get(context.couponCode) ?? 0
      : 0;
    return basePrice * context.quantity * (1 - discount);
  }
}

class PriceCalculator {
  constructor(private strategy: PricingStrategy) {}

  // Strategy can change at runtime
  setStrategy(strategy: PricingStrategy): void {
    this.strategy = strategy;
  }

  calculatePrice(basePrice: number, context: PricingContext): number {
    return this.strategy.calculate(basePrice, context);
  }
}

// Strategy selection — a business rule, separated from the calculation itself:
function selectStrategy(context: PricingContext): PricingStrategy {
  if (context.couponCode) return new CouponPricing(couponsMap);
  if (context.isPremium) return new PremiumPricing();
  if (context.quantity >= 10) return new BulkPricing();
  return new StandardPricing();
}
```

### Strategy in real libraries

```ts
// Passport.js — a classic Strategy pattern for authentication:
passport.use(new LocalStrategy(async (username, password, done) => {
  const user = await User.findOne({ username });
  if (!user || !await bcrypt.compare(password, user.password)) {
    return done(null, false);
  }
  return done(null, user);
}));

passport.use(new JwtStrategy(opts, async (payload, done) => {
  const user = await User.findById(payload.sub);
  return user ? done(null, user) : done(null, false);
}));

// Add Google OAuth? Add another strategy — no changes to existing code.

// Array.prototype.sort — strategy as a comparator function:
const users = [...].sort((a, b) => a.name.localeCompare(b.name)); // strategy: by name
const users2 = [...].sort((a, b) => b.createdAt - a.createdAt);   // strategy: by date
```

---

## Command — "encapsulate an action as an object"

> Encapsulates a request as an object, thereby letting you parameterize clients with different requests, queue or log requests, and support undoable operations.

Command turns a "method call" into an object. This unlocks capabilities: command queues, undo/redo, transactions, logging.

### Example: text editor with undo/redo

```ts
interface Command {
  execute(): void;
  undo(): void;
}

class TextEditor {
  private content = '';

  insert(text: string, position: number): void {
    this.content = this.content.slice(0, position) + text + this.content.slice(position);
  }

  delete(start: number, length: number): void {
    this.content = this.content.slice(0, start) + this.content.slice(start + length);
  }

  getContent(): string { return this.content; }
}

class InsertCommand implements Command {
  constructor(
    private readonly editor: TextEditor,
    private readonly text: string,
    private readonly position: number,
  ) {}

  execute(): void { this.editor.insert(this.text, this.position); }
  undo(): void { this.editor.delete(this.position, this.text.length); }
}

class DeleteCommand implements Command {
  private deletedText = '';

  constructor(
    private readonly editor: TextEditor,
    private readonly start: number,
    private readonly length: number,
  ) {}

  execute(): void {
    this.deletedText = this.editor.getContent().slice(this.start, this.start + this.length);
    this.editor.delete(this.start, this.length);
  }

  undo(): void { this.editor.insert(this.deletedText, this.start); }
}

// CommandHistory — stores history for undo/redo
class CommandHistory {
  private readonly history: Command[] = [];
  private pointer = -1;

  execute(command: Command): void {
    // Executing a new command — truncate the "future" (redo stack)
    this.history.splice(this.pointer + 1);
    command.execute();
    this.history.push(command);
    this.pointer++;
  }

  undo(): void {
    if (this.pointer < 0) return;
    this.history[this.pointer].undo();
    this.pointer--;
  }

  redo(): void {
    if (this.pointer >= this.history.length - 1) return;
    this.pointer++;
    this.history[this.pointer].execute();
  }
}
```

### Redux as Command + Observer

```ts
// Redux is an implementation of Command + Observer:
//
// Action (command): { type: 'INCREMENT', payload: 1 }
//   — an object describing the intent (like Command.execute())
//
// Reducer (command handler): (state, action) => newState
//   — a pure function applying the command to state
//
// dispatch() — sends the command to the store
//
// store.subscribe() — Observer: components subscribe to changes
//
// Redux DevTools: inspect and replay actions — only possible because
// every action is a serializable object (Command)

const increment = (amount: number) => ({ type: 'INCREMENT' as const, payload: amount });

function counterReducer(state = 0, action: ReturnType<typeof increment>) {
  switch (action.type) {
    case 'INCREMENT': return state + action.payload;
    default: return state;
  }
}

store.dispatch(increment(1));
store.subscribe(() => console.log(store.getState()));
```

### Command in task queues (Node.js)

```ts
// BullMQ / pg-boss: each task in the queue is a Command object
interface JobCommand {
  type: string;
  payload: unknown;
}

// Enqueuing — deferred Command execution:
await queue.add('send-email', { to: user.email, template: 'welcome' });
await queue.add('resize-image', { fileId: 'abc123', sizes: [100, 200, 400] });

// Worker — the "invoker" from the Command pattern, executes commands:
worker.process(async (job) => {
  const handlers: Record<string, (payload: unknown) => Promise<void>> = {
    'send-email': (p) => emailService.send(p as EmailPayload),
    'resize-image': (p) => imageService.resize(p as ResizePayload),
  };
  await handlers[job.name]?.(job.data);
});
```

---

## Iterator — "sequential traversal without exposing structure"

> Provides a way to sequentially access elements of a composite object without exposing its underlying representation.

In TypeScript, Iterator is built into the language via the `Symbol.iterator` protocol and generators.

### Example: pagination via a custom Iterator

```ts
// Without Iterator — the consumer must know about offset/limit and make requests manually

// ✅ With Iterator — the consumer just iterates, unaware of pagination details
class PaginatedUserIterator implements AsyncIterable<User[]> {
  constructor(
    private readonly repo: UserRepository,
    private readonly pageSize: number = 50,
  ) {}

  async *[Symbol.asyncIterator](): AsyncGenerator<User[]> {
    let page = 0;
    let hasMore = true;

    while (hasMore) {
      const batch = await this.repo.findAll({
        skip: page * this.pageSize,
        take: this.pageSize,
      });
      if (batch.length === 0) {
        hasMore = false;
      } else {
        yield batch;
        page++;
        hasMore = batch.length === this.pageSize;
      }
    }
  }
}

// Consumer is unaware of offset/limit:
async function exportAllUsers(repo: UserRepository) {
  const iterator = new PaginatedUserIterator(repo, 100);

  for await (const batch of iterator) {
    await csvWriter.write(batch);
  }
}
```

### Generator as Iterator

```ts
// Generators are the most idiomatic way to implement Iterator in TypeScript

function* range(start: number, end: number, step = 1): Generator<number> {
  for (let i = start; i < end; i += step) {
    yield i;
  }
}

for (const n of range(0, 10, 2)) {
  console.log(n); // 0, 2, 4, 6, 8
}

// Infinite Iterator — without a generator would require special handling:
function* fibonacci(): Generator<number> {
  let [a, b] = [0, 1];
  while (true) {
    yield a;
    [a, b] = [b, a + b];
  }
}

const fib = fibonacci();
console.log(fib.next().value); // 0
console.log(fib.next().value); // 1
console.log(fib.next().value); // 1
```

### Node.js Streams as Iterator

```ts
// A Readable stream in Node.js implements AsyncIterable — it's an Iterator:
import { createReadStream } from 'node:fs';
import * as readline from 'node:readline';

async function processLargeFile(path: string) {
  const fileStream = createReadStream(path);
  const rl = readline.createInterface({ input: fileStream });

  // AsyncIterator: read line by line without loading the entire file into memory
  for await (const line of rl) {
    await processLine(line);
  }
}
```

---

## Template Method — "algorithm skeleton with overridable steps"

> Defines the skeleton of an algorithm in a base class, letting subclasses override specific steps without changing the algorithm's structure.

Template Method is one of the patterns where inheritance is architecturally justified. The base class fixes the order of steps; subclasses can change details without breaking the "recipe."

### Example: data importer

```ts
// Base class fixes the algorithm:
abstract class DataImporter {
  // Template Method — final, step order cannot be changed
  async import(source: string): Promise<ImportResult> {
    const rawData = await this.readData(source);
    const parsedData = this.parseData(rawData);
    const validData = this.validateData(parsedData);
    const transformedData = this.transformData(validData);
    return this.saveData(transformedData);
  }

  // Required steps — subclasses MUST implement
  protected abstract readData(source: string): Promise<string>;
  protected abstract parseData(raw: string): Record<string, unknown>[];

  // Optional hooks — subclass may override
  protected validateData(data: Record<string, unknown>[]): Record<string, unknown>[] {
    return data.filter(row => Object.keys(row).length > 0);
  }

  protected transformData(data: Record<string, unknown>[]): Record<string, unknown>[] {
    return data; // default — no transformation
  }

  protected abstract saveData(data: Record<string, unknown>[]): Promise<ImportResult>;
}

class CsvImporter extends DataImporter {
  protected async readData(source: string): Promise<string> {
    return fs.readFile(source, 'utf-8');
  }

  protected parseData(raw: string): Record<string, unknown>[] {
    const [headerLine, ...rows] = raw.split('\n');
    const headers = headerLine.split(',');
    return rows.map(row => {
      const values = row.split(',');
      return Object.fromEntries(headers.map((h, i) => [h, values[i]]));
    });
  }

  protected async saveData(data: Record<string, unknown>[]): Promise<ImportResult> {
    await db.batchInsert('imports', data);
    return { count: data.length, status: 'success' };
  }
}

class JsonApiImporter extends DataImporter {
  constructor(private readonly apiUrl: string) { super(); }

  protected async readData(_source: string): Promise<string> {
    const response = await fetch(this.apiUrl);
    return response.text();
  }

  protected parseData(raw: string): Record<string, unknown>[] {
    return JSON.parse(raw).data; // API-specific structure
  }

  protected transformData(data: Record<string, unknown>[]): Record<string, unknown>[] {
    // Extra normalization — JSON API only
    return data.map(row => ({ ...row, importedAt: new Date().toISOString() }));
  }

  protected async saveData(data: Record<string, unknown>[]): Promise<ImportResult> {
    await db.batchInsert('imports', data);
    return { count: data.length, status: 'success' };
  }
}
```

### Template Method vs Strategy

```txt
Template Method (inheritance):
  - Algorithm fixed in the base class
  - Subclasses override individual steps
  - "Variation" selection — static (determined by the object's type)

Strategy (composition):
  - Algorithm fully encapsulated in the strategy
  - Strategies are interchangeable at runtime
  - "Variation" selection — dynamic (can be changed at any moment)

Rule: prefer Strategy over Template Method —
"prefer composition over inheritance."
Template Method is justified when the algorithm skeleton itself
is the valuable abstraction (not the step details, but the order).
```

---

## State — "behavior depends on state"

> Allows an object to alter its behavior when its internal state changes. The object will appear to change its class.

State is the alternative to a growing `if/switch` chain on a `status` or `state` field. Each state is a separate class with its own behavior.

### Example: order with states

```ts
interface OrderState {
  pay(): void;
  ship(): void;
  cancel(): void;
  getStatus(): string;
}

class Order {
  private state: OrderState;

  constructor() {
    this.state = new PendingState(this);
  }

  setState(state: OrderState): void { this.state = state; }

  pay(): void { this.state.pay(); }
  ship(): void { this.state.ship(); }
  cancel(): void { this.state.cancel(); }
  getStatus(): string { return this.state.getStatus(); }
}

class PendingState implements OrderState {
  constructor(private readonly order: Order) {}

  pay(): void {
    console.log('Payment received');
    this.order.setState(new PaidState(this.order));
  }
  ship(): void { throw new Error('Cannot ship unpaid order'); }
  cancel(): void {
    console.log('Order cancelled');
    this.order.setState(new CancelledState(this.order));
  }
  getStatus(): string { return 'pending'; }
}

class PaidState implements OrderState {
  constructor(private readonly order: Order) {}

  pay(): void { throw new Error('Order already paid'); }
  ship(): void {
    console.log('Order shipped');
    this.order.setState(new ShippedState(this.order));
  }
  cancel(): void {
    console.log('Order cancelled, refund initiated');
    this.order.setState(new CancelledState(this.order));
  }
  getStatus(): string { return 'paid'; }
}

class ShippedState implements OrderState {
  constructor(private readonly order: Order) {}

  pay(): void { throw new Error('Order already paid'); }
  ship(): void { throw new Error('Order already shipped'); }
  cancel(): void { throw new Error('Cannot cancel shipped order'); }
  getStatus(): string { return 'shipped'; }
}

class CancelledState implements OrderState {
  constructor(private readonly order: Order) {}

  pay(): void { throw new Error('Order is cancelled'); }
  ship(): void { throw new Error('Order is cancelled'); }
  cancel(): void { throw new Error('Order already cancelled'); }
  getStatus(): string { return 'cancelled'; }
}

const order = new Order();
order.pay();    // "Payment received"
order.ship();   // "Order shipped"
order.cancel(); // throws: Cannot cancel shipped order
```

### XState — State Machine as a library

```ts
// XState formalizes the State pattern in TypeScript applications:
import { createMachine, interpret } from 'xstate';

const orderMachine = createMachine({
  id: 'order',
  initial: 'pending',
  states: {
    pending: {
      on: {
        PAY: 'paid',
        CANCEL: 'cancelled',
      },
    },
    paid: {
      on: {
        SHIP: 'shipped',
        CANCEL: 'cancelled',
      },
    },
    shipped: { type: 'final' },
    cancelled: { type: 'final' },
  },
});

const service = interpret(orderMachine).start();
service.send('PAY');   // pending → paid
service.send('SHIP');  // paid → shipped
```

---

## Mediator — "intermediary instead of direct connections"

> Defines an object that encapsulates how a set of objects interact. Mediator promotes loose coupling by keeping objects from referring to each other explicitly.

Without Mediator: N objects, each knowing about all others → O(N²) connections. With Mediator: each object knows only the Mediator → O(N) connections.

### Example: chat room

```ts
interface ChatMediator {
  sendMessage(message: string, sender: ChatUser): void;
  addUser(user: ChatUser): void;
}

class ChatRoom implements ChatMediator {
  private users: ChatUser[] = [];

  addUser(user: ChatUser): void {
    this.users.push(user);
  }

  sendMessage(message: string, sender: ChatUser): void {
    // Mediator knows all users; users know only the mediator
    this.users
      .filter(user => user !== sender)
      .forEach(user => user.receive(message, sender.name));
  }
}

class ChatUser {
  constructor(
    public readonly name: string,
    private readonly mediator: ChatMediator,
  ) {
    mediator.addUser(this);
  }

  send(message: string): void {
    console.log(`${this.name} sends: "${message}"`);
    this.mediator.sendMessage(message, this);
  }

  receive(message: string, from: string): void {
    console.log(`${this.name} receives from ${from}: "${message}"`);
  }
}

const room = new ChatRoom();
const alice = new ChatUser('Alice', room);
const bob = new ChatUser('Bob', room);
const charlie = new ChatUser('Charlie', room);

alice.send('Hello everyone!');
// Bob receives from Alice: "Hello everyone!"
// Charlie receives from Alice: "Hello everyone!"
```

### Mediator in React — Redux Store, Context

```tsx
// Redux Store — Mediator for components:
// components don't know about each other, they communicate through the store

// Without Mediator: UserProfile → directly notifies Header, Sidebar, CartCount
// With Redux (Mediator):
dispatch(updateUser(userData));    // publishes to store
// Header, Sidebar, CartCount — subscribers via useSelector, unaware of each other

// React Context — a lighter Mediator:
const ThemeContext = createContext<Theme>(defaultTheme);

// Provider — Mediator: components read the theme directly from context
// without prop drilling through multiple levels
function App() {
  return (
    <ThemeContext.Provider value={currentTheme}>
      <Layout />
    </ThemeContext.Provider>
  );
}
```

---

## Chain of Responsibility — "chain of handlers"

> Lets you pass requests along a chain of handlers. Each handler decides either to process the request itself or to pass it to the next handler.

Chain of Responsibility is the pattern that Express/Koa middleware literally implements. Each handler in the chain is independent and unaware of the others.

### Example: request validation and authorization

```ts
interface RequestContext {
  method: string;
  path: string;
  headers: Record<string, string>;
  userId?: string;
  body?: unknown;
}

interface Handler {
  setNext(handler: Handler): Handler;
  handle(ctx: RequestContext): Promise<void>;
}

abstract class BaseHandler implements Handler {
  private nextHandler: Handler | null = null;

  setNext(handler: Handler): Handler {
    this.nextHandler = handler;
    return handler; // return handler for chaining: a.setNext(b).setNext(c)
  }

  protected async passToNext(ctx: RequestContext): Promise<void> {
    if (this.nextHandler) {
      await this.nextHandler.handle(ctx);
    }
  }

  abstract handle(ctx: RequestContext): Promise<void>;
}

class RateLimitHandler extends BaseHandler {
  private readonly requestCounts = new Map<string, number>();

  async handle(ctx: RequestContext): Promise<void> {
    const ip = ctx.headers['x-forwarded-for'] ?? 'unknown';
    const count = (this.requestCounts.get(ip) ?? 0) + 1;
    this.requestCounts.set(ip, count);

    if (count > 100) {
      throw new Error('Rate limit exceeded');
    }
    await this.passToNext(ctx);
  }
}

class AuthHandler extends BaseHandler {
  async handle(ctx: RequestContext): Promise<void> {
    const token = ctx.headers['authorization']?.replace('Bearer ', '');
    if (!token) throw new Error('Unauthorized');

    const payload = jwtService.verify(token);
    ctx.userId = payload.sub; // enrich the context
    await this.passToNext(ctx);
  }
}

class ValidationHandler extends BaseHandler {
  async handle(ctx: RequestContext): Promise<void> {
    if (ctx.method === 'POST' && !ctx.body) {
      throw new Error('Request body is required');
    }
    await this.passToNext(ctx);
  }
}

class BusinessLogicHandler extends BaseHandler {
  async handle(ctx: RequestContext): Promise<void> {
    // Real business logic — only reached if all previous handlers passed
    console.log(`Processing request for user ${ctx.userId}`);
  }
}

// Assembling the chain:
const rateLimiter = new RateLimitHandler();
const auth = new AuthHandler();
const validation = new ValidationHandler();
const business = new BusinessLogicHandler();

rateLimiter.setNext(auth).setNext(validation).setNext(business);

// Request travels through the entire chain:
await rateLimiter.handle(requestContext);
```

### Express middleware as Chain of Responsibility

```ts
// Express middleware is exactly Chain of Responsibility.
// next() is passToNext() from the example above.

app.use(async (req, res, next) => {
  // RateLimitHandler
  if (await isRateLimited(req.ip)) return res.status(429).send('Too many requests');
  next();
});

app.use(async (req, res, next) => {
  // AuthHandler
  try {
    req.user = await verifyToken(req.headers.authorization);
    next();
  } catch {
    res.status(401).send('Unauthorized');
  }
});

app.post('/orders', async (req, res) => {
  // BusinessLogicHandler — end of the chain
  const order = await orderService.create(req.user.id, req.body);
  res.json(order);
});
```

### Chain of Responsibility vs Decorator

```txt
Decorator:
  - ALWAYS wraps (adds behavior on every call)
  - The wrapped object is ALWAYS called
  - Goal: extend functionality

Chain of Responsibility:
  - Can BREAK the chain (each handler decides: continue or stop)
  - Next handler is called only if current one decides to pass
  - Goal: find the right handler among candidates

Express middleware is both patterns at once:
  - cors(), helmet() → Decorator (add behavior, always call next)
  - authenticate() → Chain of Responsibility (may return 401 and not call next)
```

---

## Comparison of behavioral patterns

```txt
Pattern                  Core idea                              Real-world example
──────────────────────────────────────────────────────────────────────────────────
Observer                 Subscribe and notify                   EventEmitter, Redux store
Strategy                 Interchangeable algorithm              Passport.js strategies, Array.sort
Command                  Action as an object                    Redux actions, BullMQ jobs
Iterator                 Traversal without exposing structure   Generators, Streams, for-await-of
Template Method          Algorithm skeleton with hooks          DataImporter, React lifecycle
State                    Behavior depends on state              XState, Order states
Mediator                 Intermediary instead of direct links   Redux Store, EventBus, Socket.IO room
Chain of Responsibility  Handler chain, breakable               Express middleware, NestJS Guards
```

## Common interview traps

- **"Observer = EventEmitter"** — EventEmitter is Node.js's implementation of Observer, but the pattern is broader. Pub/Sub systems (Redis pub/sub, Kafka, WebSocket broadcast) are also Observer. Understanding the pattern matters more than knowing one implementation.

- **Confusing Strategy and State** — both change an object's behavior. Strategy — the external client selects the algorithm (sorting, pricing). State — the object changes its own behavior when it transitions to another state (order: pending → paid → shipped). Key: **who initiates the switch** — the client (Strategy) or the object itself (State).

- **"Redux is just Flux"** — Redux implements Command (action objects), Observer (store.subscribe), and Singleton (one store). Naming patterns in the Redux context demonstrates depth of understanding.

- **Template Method is always better than Strategy** — the opposite: GoF itself recommends preferring composition (Strategy) over inheritance (Template Method). Template Method is justified when the "algorithm skeleton" is itself an important architectural concept.

- **Chain of Responsibility == Decorator** — a common confusion. Decorator ALWAYS wraps; Chain of Responsibility may break the chain. Express middleware is both patterns simultaneously, depending on the specific handler.

- **Iterator only as a "class with hasNext/next"** — in TypeScript/JavaScript, Iterator is built into the language: `Symbol.iterator`, generators, `for-of`, `for-await-of`. Not knowing the built-in iteration protocol when discussing the Iterator pattern is a weak spot.

- **Mediator = "God Object"** — a real risk. Mediator becomes an anti-pattern when it knows too much about each participant. A good Mediator coordinates interactions without containing the participants' business logic. Redux is a good example: the store doesn't know why a component subscribes to specific data.
