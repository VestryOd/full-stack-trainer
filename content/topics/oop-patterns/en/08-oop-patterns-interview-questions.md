# OOP, SOLID & Design Patterns — Interview Questions (Middle → Senior)

## How to use this cheat sheet

Each answer is a compressed version of what's covered in depth in the topic articles. In a senior interview, almost every question here is an opener — not the final question. The interviewer expects you to go deeper on "why", "when would you not use it", and "show me a real example". Each group ends with **"Typical follow-ups"** to show where the conversation usually goes next.

---

## Group 1: SOLID Principles

**1. What does SRP actually mean — and how is it misunderstood?**

SRP says a class should have one *reason to change*, not one *method*. Misunderstanding: splitting every class into tiny pieces with one method each. Correct reading: "who are the stakeholders that could request a change?" A `UserService` that both sends emails and manages DB records has two stakeholders (marketing team vs. DB team) → two reasons to change → violates SRP. A class with 10 methods all related to user persistence has one reason to change (schema/query changes) → SRP is fine.

---

**2. Explain OCP with a real example, not just "open for extension, closed for modification."**

OCP: add behaviour without editing existing code. Classic violation — a `switch` on type that grows every time a new type is added. Fix: extract a `Notification` interface, add an `EmailNotification`, `SmsNotification`, `PushNotification` class. Adding a new channel = adding a class, zero edits to existing code. In TypeScript:

```ts
interface Notifier { send(message: string): Promise<void>; }

class EmailNotifier implements Notifier { /* ... */ }
class SmsNotifier  implements Notifier { /* ... */ }

// NotificationService never changes when a new channel is added
class NotificationService {
  constructor(private notifiers: Notifier[]) {}
  async notify(msg: string) {
    await Promise.all(this.notifiers.map(n => n.send(msg)));
  }
}
```

---

**3. What is LSP and what does it mean in practice?**

LSP: a subtype must be substitutable for its base type without breaking the program's correctness. Classic violation: `Square extends Rectangle` — setting width changes height (to keep it square), which breaks code that expects independent dimensions. The test: if you need an `instanceof` check or a try/catch around a method of the base class when calling a subclass — LSP is violated.

```ts
// ❌ Violation: Square breaks the Rectangle contract
class Rectangle {
  setWidth(w: number)  { this.width = w; }
  setHeight(h: number) { this.height = h; }
  area() { return this.width * this.height; }
}
class Square extends Rectangle {
  setWidth(w: number)  { this.width = this.height = w; } // breaks expectation
}

// ✅ Fix: separate abstractions
interface Shape { area(): number; }
class Rectangle implements Shape { /* independent width, height */ }
class Square    implements Shape { /* single side */ }
```

---

**4. ISP — when does a "fat interface" cause real problems?**

ISP: clients should not be forced to depend on methods they do not use. Real problem: a `IRepository` with `findOne`, `findAll`, `create`, `update`, `delete`, `bulkInsert`, `runReport`. A read-only reporting module that only needs `findAll` and `runReport` must still depend on mutation methods — any change to `create` forces a recompile/retest of the report module. Fix: split into `IReadRepository`, `IWriteRepository`, `IReportRepository`.

---

**5. DIP — what is the difference between Dependency Inversion and Dependency Injection?**

DIP is a *principle*: high-level modules should not depend on low-level modules — both should depend on abstractions. DI is a *mechanism* for implementing DIP: instead of `new EmailService()` inside a class, the dependency is injected via constructor. You can have DI without DIP (inject a concrete class → still tightly coupled). DIP without DI is possible but awkward. In NestJS, the `@Injectable()` + `@Module` system gives DI; depending on an interface token (not a class) gives DIP.

```ts
// ❌ DIP violation — high-level depends on low-level concrete class
class OrderService {
  private mailer = new SendGridMailer(); // hardcoded
}

// ✅ DIP via DI — depends on abstraction
interface IMailer { sendEmail(to: string, body: string): Promise<void>; }

class OrderService {
  constructor(private mailer: IMailer) {} // injected, not instantiated
}
```

---

## Typical follow-ups (Group 1)

```txt
"Which SOLID principle is hardest to apply and why?" →
  OCP — you can't predict all future extension points; applying OCP
  everywhere leads to over-abstraction. The answer should mention
  "apply when you see the 3rd variation, not the 1st"

"Can you violate SOLID intentionally?" →
  Yes. A script, a test helper, a one-off migration — strict SOLID
  in throw-away code is waste. Principles apply to code that evolves.

"Which principle does NestJS enforce by design?" →
  DIP via its DI container; OCP via interceptors, guards, pipes
  (add behaviour without touching controllers)
```

---

## Group 2: Creational Patterns

**6. What problem does Factory Method solve that a simple `new` does not?**

`new ConcreteClass()` couples the caller to a specific implementation. Factory Method decouples: the caller works with the base type, and subclasses or factory functions decide what to instantiate. In Node.js, `http.createServer()` and `https.createServer()` are factory methods returning different server implementations through the same interface — calling code doesn't know or care which transport is used.

---

**7. When does Builder make more sense than a constructor with optional parameters?**

When an object needs more than 3-4 optional parameters, or when construction involves validation across fields (you can't have both `oauth` and `password` set). Builder also enforces a specific order of steps (Director pattern), and allows creating different "configurations" of the same object from the same builder.

```ts
class QueryBuilder {
  private table = '';
  private conditions: string[] = [];
  private limitVal?: number;

  from(table: string)   { this.table = table; return this; }
  where(cond: string)   { this.conditions.push(cond); return this; }
  limit(n: number)      { this.limitVal = n; return this; }

  build(): string {
    let q = `SELECT * FROM ${this.table}`;
    if (this.conditions.length) q += ` WHERE ${this.conditions.join(' AND ')}`;
    if (this.limitVal)          q += ` LIMIT ${this.limitVal}`;
    return q;
  }
}

const query = new QueryBuilder().from('users').where('age > 18').limit(10).build();
```

---

**8. Singleton — what problems does it cause in a Node.js context, and how do you mitigate them?**

Singletons in Node.js are module-level singletons (the module cache keeps one instance). Problems: (1) hidden global state — hard to test (tests pollute each other); (2) module-level singleton is per-process, not per-request — stateful singletons are a concurrency bug. Mitigation: dependency injection instead of `module.exports = new Service()` — each test creates its own instance; the DI container manages lifetime.

---

## Typical follow-ups (Group 2)

```txt
"Is PrismaClient a Singleton? Should it be?" →
  Yes — one PrismaClient per process manages the connection pool.
  Multiple instances = multiple pools = "too many connections" in prod.
  But in tests, a new instance per test suite avoids state leakage.

"What's the difference between Abstract Factory and Factory Method?" →
  Factory Method: one product, subclasses decide the implementation.
  Abstract Factory: family of related products (Button + Checkbox for
  Windows vs. macOS), always consistent with each other.
```

---

## Group 3: Structural Patterns

**9. Adapter vs Decorator — explain with a concrete TypeScript example.**

Adapter converts an *incompatible* interface into an expected one (you can't change either side). Decorator adds *behaviour* to an existing compatible interface without changing the class.

```ts
// Adapter — legacy logger has a different signature
interface ILogger { log(level: string, msg: string): void; }
class LegacyLogger { write(msg: string) { console.log(msg); } }

class LoggerAdapter implements ILogger {
  constructor(private legacy: LegacyLogger) {}
  log(level: string, msg: string) {
    this.legacy.write(`[${level}] ${msg}`);
  }
}

// Decorator — add timestamp without modifying the original
class TimestampLogger implements ILogger {
  constructor(private inner: ILogger) {}
  log(level: string, msg: string) {
    this.inner.log(level, `${new Date().toISOString()} ${msg}`);
  }
}
```

---

**10. What does Facade do and where does it appear in React/Node.js codebases?**

Facade provides a simplified interface over a complex subsystem. In React: a custom hook (`useAuth`) that hides token refresh logic, redirect handling, and permission checking behind `{ user, login, logout }`. In Node.js: a `PaymentService` that coordinates `StripeClient`, `InvoiceRepository`, `EmailService`, and `AuditLogger` behind a single `charge(orderId, amount)` method.

---

**11. Proxy pattern — what are the three main use cases?**

(1) **Virtual proxy** — lazy loading (instantiate the real object only on first use). (2) **Protection proxy** — access control (check permissions before delegating). (3) **Logging/caching proxy** — intercept calls to add cross-cutting behaviour. JavaScript's native `Proxy` object is the pattern implemented at language level. MobX uses JS Proxy as a virtual proxy over observable objects to intercept reads and writes for reactive tracking.

```ts
function withCache<T extends object>(target: T, ttlMs: number): T {
  const cache = new Map<string | symbol, { value: unknown; expiresAt: number }>();
  return new Proxy(target, {
    get(obj, key) {
      const cached = cache.get(key);
      if (cached && Date.now() < cached.expiresAt) return cached.value;
      const value = (obj as any)[key];
      cache.set(key, { value, expiresAt: Date.now() + ttlMs });
      return value;
    },
  });
}
```

---

## Typical follow-ups (Group 3)

```txt
"How does NestJS use the Decorator pattern?" →
  @Injectable, @Controller, @Get, etc. are TypeScript decorators —
  they add metadata to classes/methods. NestJS's DI reads this
  metadata at runtime via reflect-metadata. Structurally it's the
  Decorator pattern applied to metadata, not runtime behaviour.

"Is Express middleware a pattern? Which one?" →
  Chain of Responsibility — each middleware decides to pass the
  request to next() or short-circuit with res.send(). The chain
  is built at startup, not hardcoded.
```

---

## Group 4: Behavioral Patterns

**12. Observer vs EventEmitter vs Pub/Sub — what's the difference?**

Observer: subject holds direct references to observers, calls them synchronously. EventEmitter (Node.js): named events, synchronous by default, loose coupling (emitter doesn't know who listens). Pub/Sub: a broker in between (Redis, RabbitMQ), publisher and subscriber are in different processes, fully decoupled, asynchronous. Each step adds more decoupling and more infrastructure.

---

**13. Strategy pattern — give a real use case beyond the textbook sorting example.**

Authentication strategies: a `PassportStrategy` interface with `validate(token)`. `JwtStrategy`, `GoogleOAuthStrategy`, `ApiKeyStrategy` implement it. The `AuthGuard` doesn't know which strategy it uses — it's injected. Adding a new auth method = adding a class, no changes to the guard. This is exactly how `passport.js` works internally.

```ts
interface AuthStrategy {
  validate(token: string): Promise<User | null>;
}

class JwtStrategy implements AuthStrategy {
  async validate(token: string) { /* verify JWT */ }
}

class ApiKeyStrategy implements AuthStrategy {
  async validate(token: string) { /* look up API key in DB */ }
}

class AuthGuard {
  constructor(private strategy: AuthStrategy) {}
  async authenticate(token: string) {
    const user = await this.strategy.validate(token);
    if (!user) throw new UnauthorizedException();
    return user;
  }
}
```

---

**14. Command pattern — why does it enable undo/redo, and where is it used in frontend?**

Command encapsulates an action as an object with `execute()` and optionally `undo()`. Because the command object knows how to reverse itself, a history stack gives you undo/redo for free. In frontend: Redux action objects are Commands — they are serializable, dispatchable, replayable. Redux DevTools time-travel works because every state change is a Command stored in an array.

---

**15. Template Method vs Strategy — when to use each?**

Template Method: define the *skeleton* of an algorithm in a base class, let subclasses override specific steps. Coupling is via inheritance. Strategy: encapsulate the *whole* algorithm as a replaceable object. Coupling is via composition. Rule: if the steps are invariant and you only customise a few — Template Method. If the whole algorithm needs to swap at runtime or per-instance — Strategy. Template Method violates OCP when a new variant requires touching the base class; Strategy does not.

---

**16. What is the Chain of Responsibility pattern and where does it appear in backend code?**

A request passes through a chain of handlers; each handler either processes it or passes it to the next. Appears in: Express/Koa middleware, NestJS guards + interceptors + pipes + exception filters (each is a link in the chain), and AWS Lambda handler chains. Key property: the sender doesn't know which handler will process the request, and handlers can be added/removed without touching the sender.

---

## Typical follow-ups (Group 4)

```txt
"If Redux actions are Commands, what is the Reducer?" →
  Pure function that applies a Command to produce a new state —
  it's closest to an Interpreter or a state machine transition function.

"How would you implement an undo stack for a form?" →
  Command pattern: each field change is a Command with execute()
  (apply new value) and undo() (restore previous value).
  History array + pointer. Push on change, pop on ctrl+Z.

"NestJS has guards, interceptors, pipes, and exception filters —
which pattern are they?" →
  Chain of Responsibility for the request pipeline.
  The order is fixed: guards → interceptors (before) → pipes →
  handler → interceptors (after) → exception filters.
```

---

## Group 5: Pattern Recognition in Real Code

**17. You see this code — name the pattern(s) and explain what's wrong:**

```ts
class ReportGenerator {
  generate(type: string, data: unknown[]) {
    if (type === 'pdf')   return this.generatePdf(data);
    if (type === 'excel') return this.generateExcel(data);
    if (type === 'csv')   return this.generateCsv(data);
    throw new Error('Unknown type');
  }
  private generatePdf(data: unknown[])   { /* ... */ }
  private generateExcel(data: unknown[]) { /* ... */ }
  private generateCsv(data: unknown[])   { /* ... */ }
}
```

This is a violation of OCP and a missed Strategy / Factory Method opportunity. Every new report type requires editing this class. Fix: extract a `ReportStrategy` interface, move each format to its own class, inject or look up by type. The `ReportGenerator` then has zero `if` statements and never needs to change.

---

**18. Where are design patterns used in React itself (not userland)?**

- **Composite**: the React element tree — every node is either a leaf (`<span>`) or a composite (`<div>` containing children). `React.Children` utilities operate on both uniformly.
- **Observer**: `useContext` + `createContext` — React propagates context changes to all consumers (observers) automatically.
- **Proxy**: Synthetic Event system — React wraps native DOM events in a uniform proxy object.
- **Template Method**: `React.Component` lifecycle — `render()` is abstract (must be overridden), lifecycle hooks (`componentDidMount`, etc.) are optional steps.
- **HOC (Higher-Order Component)**: Decorator pattern — wraps a component to add behaviour without modifying it.

---

## Group 6: Anti-Patterns

**19. What is "God Object" and what SOLID principle does it violate?**

A God Object knows too much and does too much — it accumulates business logic, data access, and presentation concerns. Violates SRP (many reasons to change) and usually OCP (can't extend without modifying). In Node.js: a 1000-line `UserController` that validates input, queries the DB, sends emails, writes audit logs, and formats responses. Fix: split by responsibility into services, each with a single concern.

---

**20. What is "Shotgun Surgery" and how does it relate to SRP?**

Shotgun Surgery: one logical change requires edits to many different classes simultaneously. Usually caused by a responsibility being scattered across many places (inverse of God Object). Adding a new field to an API response means editing the controller, the DTO, the mapper, the test fixture, and the API docs independently. Fix: identify the scattered responsibility and colocate it in one place.

---

**21. What is "Primitive Obsession" and how do you fix it?**

Using raw primitives (string, number) where a domain concept deserves its own type. Classic example: email as `string` everywhere — validation is duplicated, typos are invisible. Fix: a `Email` value object that validates on construction and is passed by type:

```ts
// ❌ Primitive obsession
function sendWelcome(email: string) { /* email might be "" or "not-an-email" */ }

// ✅ Value object
class Email {
  readonly value: string;
  constructor(raw: string) {
    if (!/.+@.+\..+/.test(raw)) throw new Error(`Invalid email: ${raw}`);
    this.value = raw.toLowerCase();
  }
}
function sendWelcome(email: Email) { /* always valid by construction */ }
```

---

**22. What is "Anemic Domain Model" and when is it actually acceptable?**

Anemic Domain Model: classes that are data bags (getters/setters) with no behaviour; all logic lives in service classes. Violates the OOP principle that objects should have both state and behaviour. However, it's *acceptable* in: CRUD-heavy apps where business logic is minimal, DTOs (they are intentionally data containers), and functional-style code where data and functions are deliberately separate. The anti-pattern label applies when an anemic model is used in a rich-domain context and the logic scatters across services.

---

## Typical follow-ups (Group 5 & 6)

```txt
"If you see a 500-line service class in a PR, what's your review comment?" →
  Ask "what are the reasons this class would change?" If there are
  more than one — suggest extracting responsibilities. Avoid "it's
  too long" without a principle behind it.

"Is a React component with 10 useState calls a God Object?" →
  It's a signal, not proof. The question is: are those states
  related to one concern (e.g., a complex form) or multiple
  unrelated concerns? Unrelated → extract custom hooks by concern.

"Give an example of a pattern that's almost always an anti-pattern
in modern JS/TS" →
  Singleton with global mutable state — module caching creates
  implicit singletons; if they're stateful, tests pollute each other.
  Better: DI container manages lifetime explicitly.
```

---

## Group 7: Patterns in React and Node.js

**23. What is the Compound Component pattern in React and which GoF pattern does it resemble?**

Compound Components: a parent component manages state and shares it via Context; child components are separate exports that consume that context implicitly. The user composes them:

```tsx
<Select value={val} onChange={setVal}>
  <Select.Trigger />
  <Select.Options>
    <Select.Option value="a">Option A</Select.Option>
  </Select.Options>
</Select>
```

Resembles **Composite** (parent + child are composed freely) and **Mediator** (parent mediates communication between children without them knowing about each other).

---

**24. How does NestJS's module system implement Dependency Inversion?**

NestJS modules declare `providers` (what they create) and `exports` (what they share). Other modules declare `imports` to consume what was exported. The DI container resolves the dependency graph at startup. The key DIP part: you can register a provider as an interface token (`{ provide: IMailer, useClass: SendGridMailer }`) — the consumer depends on the token (abstraction), not the concrete class. Swapping `SendGridMailer` for `ResendMailer` in tests or for a different environment requires zero changes to the consuming class.

---

**25. Where does the Repository pattern appear in a Prisma + NestJS codebase, and why is it controversial?**

Repository: an abstraction over data access that looks like an in-memory collection from the domain's point of view. In NestJS + Prisma: a `UserRepository` class wraps `prisma.user.*` and exposes `findById`, `save`, `delete`. Why controversial: Prisma's client is already a well-typed data-access abstraction — adding a Repository layer can be redundant boilerplate with no real benefit for simple cases. The pattern *is* justified when: (1) the Repository interface enables test doubles without a real DB; (2) the domain is complex and you want to hide Prisma details from domain logic; (3) you need to support multiple data sources behind one interface.

---

## Typical follow-ups (Group 7)

```txt
"Render Props vs HOC vs Custom Hooks — which pattern wins in 2025?" →
  Custom Hooks — they compose without wrapper hell, work with
  TypeScript naturally, and don't add nodes to the component tree.
  HOCs are still useful for class components (legacy) and for
  wrapping third-party components you can't modify. Render Props
  are mostly replaced by hooks.

"Is useReducer a pattern?" →
  Yes — it's the Command pattern (actions are commands) combined
  with a state machine (reducer is a transition function).
  For complex local state, useReducer is preferable to useState
  because state transitions are explicit and testable as pure functions.
```
