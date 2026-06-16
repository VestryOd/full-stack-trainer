# SOLID Principles

## Why SOLID — reframed as "cost of change"

SOLID principles are not about "beautiful code" or academic purity. They are about one thing: **making it so that adding new functionality does not break what already works**.

```txt
Symptoms of code that violates SOLID:
  - "I changed one class and tests failed in five unrelated places"
  - "To add a new user type I need to change 12 files"
  - "I can't write a unit test for this class without spinning up a database"
  - "This class can't be reused — it drags the entire application with it"

Each of these symptoms is a violation of one or more SOLID principles.
```

An important warning up front: SOLID is a **tool**, not a religion. At the end of each principle there is a "when strict adherence hurts" section — because blindly following principles creates over-engineered code that is just as hard to maintain as code without principles.

## S — Single Responsibility Principle (SRP)

> "A class should have only one reason to change."

A more practical formulation: **a class should answer to only one "actor"** (a group of people or a process that demands changes). "One responsibility" is not about the number of methods, but about **whose requirements can force the class to change**.

### SRP Violation

```ts
// ❌ UserService changes for three different reasons:
//    1. Business logic change (different hashing algorithm)
//    2. Email format change (marketing changed the template)
//    3. Storage change (migrating from SQL to NoSQL)
class UserService {
  async register(email: string, password: string) {
    // Hashing logic — the security team's domain
    const hashedPassword = await bcrypt.hash(password, 10);

    // SQL query — the data team's domain
    const user = await db.query(
      'INSERT INTO users (email, password) VALUES ($1, $2) RETURNING *',
      [email, hashedPassword]
    );

    // Email template — the marketing team's domain
    await sendEmail({
      to: email,
      subject: 'Welcome to our platform!',
      body: `Hi! You've successfully registered. Click here to confirm...`,
    });

    return user.rows[0];
  }
}
```

```ts
// ✅ Each class knows only its own domain:
// UserRepository — storage only
// EmailService — email sending only
// UserService — orchestration only (coordinates the others)

class UserRepository {
  async create(email: string, hashedPassword: string) {
    const result = await db.query(
      'INSERT INTO users (email, password) VALUES ($1, $2) RETURNING *',
      [email, hashedPassword]
    );
    return result.rows[0];
  }
}

class EmailService {
  async sendWelcome(email: string) {
    await sendEmail({
      to: email,
      subject: 'Welcome to our platform!',
      body: `Hi! You've successfully registered. Click here to confirm...`,
    });
  }
}

class UserService {
  constructor(
    private readonly userRepository: UserRepository,
    private readonly emailService: EmailService,
  ) {}

  async register(email: string, password: string) {
    const hashedPassword = await bcrypt.hash(password, 10);
    const user = await this.userRepository.create(email, hashedPassword);
    await this.emailService.sendWelcome(email);
    return user;
  }
}
```

### Real-world context (NestJS)

In NestJS, an SRP violation is a service that makes HTTP requests, writes to the database, formats responses, and sends metrics. Each of these layers should be a separate injectable provider. A `UserService` test should not require a running mail server.

### When strict SRP hurts

If the application is small and responsibilities NEVER change independently — artificial splitting creates cognitive overhead with no real benefit. A "user registration" feature in a 200-line MVP does not need four classes.

---

## O — Open/Closed Principle (OCP)

> "Software entities should be open for extension, but closed for modification."

Practically: **adding new behavior should not require changing already-working code**. This is achieved through abstractions — polymorphism, strategies, plugins.

### OCP Violation

```ts
// ❌ Every new notification type requires modifying NotificationService.
// Add SMS → open this file, add a branch to switch.
// This violates OCP: the class is not closed for modification.
class NotificationService {
  send(type: 'email' | 'sms' | 'push', message: string, recipient: string) {
    switch (type) {
      case 'email':
        emailClient.send({ to: recipient, body: message });
        break;
      case 'sms':
        smsClient.send({ phone: recipient, text: message });
        break;
      case 'push':
        pushClient.notify({ userId: recipient, message });
        break;
      // Adding 'slack' → open this file → risk of breaking email/sms/push
    }
  }
}
```

```ts
// ✅ New notification type = new class, existing code is untouched

interface NotificationChannel {
  send(message: string, recipient: string): Promise<void>;
}

class EmailChannel implements NotificationChannel {
  async send(message: string, recipient: string) {
    await emailClient.send({ to: recipient, body: message });
  }
}

class SmsChannel implements NotificationChannel {
  async send(message: string, recipient: string) {
    await smsClient.send({ phone: recipient, text: message });
  }
}

// Adding Slack — new class, no existing files modified
class SlackChannel implements NotificationChannel {
  async send(message: string, recipient: string) {
    await slackClient.postMessage({ channel: recipient, text: message });
  }
}

class NotificationService {
  constructor(private readonly channels: NotificationChannel[]) {}

  async sendAll(message: string, recipient: string) {
    await Promise.all(this.channels.map(ch => ch.send(message, recipient)));
  }
}
```

### Real-world context (React)

In React, OCP is the difference between a component with hardcoded behavior and one that accepts `renderItem` / `onAction` / `children`. A `<Table>` component that doesn't allow passing a custom cell renderer violates OCP — every new cell type requires modifying `Table`.

### When strict OCP hurts

Premature abstraction is worse than its absence. If you have two channel types and there will never be a third — an interface + switch is more honest than a complex plugin registration system. **YAGNI until the second or third variation, OCP after.**

---

## L — Liskov Substitution Principle (LSP)

> "Objects of a subclass should be substitutable for objects of the parent class without altering the correctness of the program."

Practically: **code working with a base type must work with any subtype without surprises**. LSP is violated when a subclass "tightens" preconditions, "weakens" postconditions, or throws exceptions not present in the base class.

### LSP Violation

```ts
// ❌ Classic example: Rectangle and Square
// Mathematically a square is a special case of a rectangle.
// In programming — it's an LSP violation.

class Rectangle {
  constructor(protected width: number, protected height: number) {}

  setWidth(w: number)  { this.width = w; }
  setHeight(h: number) { this.height = h; }
  area() { return this.width * this.height; }
}

class Square extends Rectangle {
  setWidth(w: number)  { this.width = w; this.height = w; }  // surprise!
  setHeight(h: number) { this.width = h; this.height = h; }  // surprise!
}

function assertRectangleArea(rect: Rectangle) {
  rect.setWidth(5);
  rect.setHeight(3);
  // Expects 15, but if rect is a Square, gets 9
  console.assert(rect.area() === 15, `Expected 15, got ${rect.area()}`);
}

assertRectangleArea(new Rectangle(0, 0)); // ✅ 15
assertRectangleArea(new Square(0));        // ❌ 9 — LSP violated
```

```ts
// ✅ Don't inherit where the subtype cannot fully fulfill the base contract

interface Shape {
  area(): number;
}

class Rectangle implements Shape {
  constructor(private width: number, private height: number) {}
  area() { return this.width * this.height; }
}

class Square implements Shape {
  constructor(private side: number) {}
  area() { return this.side * this.side; }
}

// Shared code works with Shape — both Rectangle and Square, no surprises
function printArea(shape: Shape) {
  console.log(`Area: ${shape.area()}`);
}
```

### Real-world context (Node.js)

```ts
// ❌ ReadOnlyRepository "inherits" Repository but cannot fulfill its contract

class Repository<T> {
  async findById(id: string): Promise<T> { ... }
  async save(entity: T): Promise<void> { ... }
  async delete(id: string): Promise<void> { ... }
}

class ReadOnlyRepository<T> extends Repository<T> {
  async save(entity: T): Promise<void> {
    throw new Error('Not supported'); // ← LSP violation: code using Repository doesn't expect this
  }
  async delete(id: string): Promise<void> {
    throw new Error('Not supported');
  }
}

// A function working with Repository doesn't expect Error from save/delete:
async function archiveUser(repo: Repository<User>, user: User) {
  user.archivedAt = new Date();
  await repo.save(user); // ← blows up if repo is ReadOnlyRepository
}
```

```ts
// ✅ Separate interfaces — ISP + LSP work together

interface ReadableRepository<T> {
  findById(id: string): Promise<T>;
  findAll(): Promise<T[]>;
}

interface WritableRepository<T> extends ReadableRepository<T> {
  save(entity: T): Promise<void>;
  delete(id: string): Promise<void>;
}

class ReadOnlyUserRepository implements ReadableRepository<User> {
  async findById(id: string) { ... }
  async findAll() { ... }
}

// archiveUser now explicitly requires WritableRepository — type-safe
async function archiveUser(repo: WritableRepository<User>, user: User) {
  user.archivedAt = new Date();
  await repo.save(user);
}
```

### When strict LSP hurts

LSP is more often violated accidentally than intentionally, so there is less "harm from strict adherence" here. The only counter-argument: sometimes a "throw in an unimplemented method" is an honest solution during a transitional refactoring period. But that is technical debt, not an architectural decision.

---

## I — Interface Segregation Principle (ISP)

> "Clients should not be forced to depend on methods they do not use."

Practically: **"fat" interfaces should be split into smaller, specialized ones**. A class that implements a 15-method interface and throws `NotImplemented` in 10 of them is a signal of an ISP violation.

### ISP Violation

```ts
// ❌ One "fat" interface for all storage types

interface Storage {
  upload(key: string, data: Buffer): Promise<string>;
  download(key: string): Promise<Buffer>;
  delete(key: string): Promise<void>;
  generateSignedUrl(key: string, expiresIn: number): Promise<string>;
  listObjects(prefix: string): Promise<string[]>;
  copyObject(source: string, dest: string): Promise<void>;
}

// LocalStorage cannot generate signed URLs (that's an S3 concept),
// but is forced to implement the method:
class LocalStorage implements Storage {
  async upload(key: string, data: Buffer) { ... }
  async download(key: string) { ... }
  async delete(key: string) { ... }
  async generateSignedUrl(): Promise<string> {
    throw new Error('Local storage does not support signed URLs'); // ❌ ISP
  }
  async listObjects(prefix: string) { ... }
  async copyObject(source: string, dest: string) { ... }
}
```

```ts
// ✅ Split into focused interfaces — each class implements only what it supports

interface ObjectStore {
  upload(key: string, data: Buffer): Promise<string>;
  download(key: string): Promise<Buffer>;
  delete(key: string): Promise<void>;
}

interface SignedUrlProvider {
  generateSignedUrl(key: string, expiresIn: number): Promise<string>;
}

interface ObjectLister {
  listObjects(prefix: string): Promise<string[]>;
}

class LocalStorage implements ObjectStore {
  async upload(key: string, data: Buffer) { ... }
  async download(key: string) { ... }
  async delete(key: string) { ... }
  // No generateSignedUrl — and that's fine, LocalStorage doesn't support it
}

class S3Storage implements ObjectStore, SignedUrlProvider, ObjectLister {
  async upload(key: string, data: Buffer) { ... }
  async download(key: string) { ... }
  async delete(key: string) { ... }
  async generateSignedUrl(key: string, expiresIn: number) { ... }
  async listObjects(prefix: string) { ... }
}

// A function that only needs upload/download doesn't depend on SignedUrl
function processUserAvatar(store: ObjectStore, userId: string, data: Buffer) {
  return store.upload(`avatars/${userId}`, data);
}
```

### Real-world context (React)

```tsx
// ❌ Component receives a "fat" object — depends on fields it doesn't use

interface User {
  id: string;
  email: string;
  password: string;  // why does a UI component need this?
  createdAt: Date;
  role: 'admin' | 'user';
  subscriptionTier: string;
  lastLoginIp: string;
}

function UserAvatar({ user }: { user: User }) {
  // Only uses user.id and user.email, but depends on the entire User
  return <img src={`/avatars/${user.id}`} alt={user.email} />;
}

// ✅ Component depends only on the fields it needs
interface UserAvatarProps {
  userId: string;
  email: string;
}

function UserAvatar({ userId, email }: UserAvatarProps) {
  return <img src={`/avatars/${userId}`} alt={email} />;
}
```

### When strict ISP hurts

Too granular interfaces create excessive composition. If you have 8 single-method interfaces — that's also a problem: code becomes hard to read, and TypeScript intersection types (`A & B & C & D`) lose their meaning. The guideline: **an interface should correspond to one "role"** (Readable, Writable, Searchable), not one method.

---

## D — Dependency Inversion Principle (DIP)

> "High-level modules should not depend on low-level modules. Both should depend on abstractions."
> "Abstractions should not depend on details. Details should depend on abstractions."

Practically: **business logic should not know which database, HTTP client, or email provider is being used**. It works with interfaces. Concrete implementations are supplied from outside (Dependency Injection).

```txt
❌ Downward dependency (DIP violation):
  UserService → PostgresRepository (concrete class)
  
  Problem: to replace Postgres with MongoDB or write a test
  without a real database — you must change UserService.

✅ Inverted dependency (DIP):
  UserService → IUserRepository (interface/abstraction)
       ↑                ↑
  PostgresUserRepository   InMemoryUserRepository (for tests)
  
  UserService doesn't know what is behind IUserRepository.
  Swapping the implementation — without changing business logic.
```

### DIP Violation

```ts
// ❌ OrderService is hard-coupled to concrete implementations.
// Cannot test without a real Postgres and a real Stripe account.

import { PostgresOrderRepository } from './postgres-order-repository';
import { StripePaymentService } from './stripe-payment-service';

class OrderService {
  private orderRepo = new PostgresOrderRepository();   // concrete class
  private paymentService = new StripePaymentService(); // concrete class

  async placeOrder(userId: string, items: CartItem[]) {
    const total = calculateTotal(items);
    await this.paymentService.charge(userId, total);    // coupled to Stripe
    return this.orderRepo.save({ userId, items, total }); // coupled to Postgres
  }
}
```

```ts
// ✅ DIP + DI: dependencies injected via constructor, dependency is on the interface

interface OrderRepository {
  save(order: Order): Promise<Order>;
  findByUserId(userId: string): Promise<Order[]>;
}

interface PaymentGateway {
  charge(userId: string, amount: number): Promise<PaymentResult>;
}

class OrderService {
  constructor(
    private readonly orderRepo: OrderRepository,
    private readonly paymentGateway: PaymentGateway,
  ) {}

  async placeOrder(userId: string, items: CartItem[]) {
    const total = calculateTotal(items);
    const payment = await this.paymentGateway.charge(userId, total);
    return this.orderRepo.save({ userId, items, total, paymentId: payment.id });
  }
}

// For production:
const service = new OrderService(
  new PostgresOrderRepository(db),
  new StripePaymentGateway(stripeClient),
);

// For tests — no real dependencies:
const service = new OrderService(
  new InMemoryOrderRepository(),
  new MockPaymentGateway(),
);
```

### Real-world context (NestJS)

NestJS builds its entire system around DIP: `@Injectable()` providers are registered in the module, and classes receive dependencies through the constructor. The `IUserRepository` token in `provide` and `useClass: PostgresUserRepository` — that is DIP in action. This is exactly why testing NestJS services via `Test.createTestingModule` is so convenient: concrete implementations are swapped for mocks without changing the tested code.

### When strict DIP hurts

For small utilities (helper functions, formatters, validators) — introducing abstractions for their own sake creates bloat. If `formatPrice(amount: number): string` will never change its implementation and doesn't need to be mocked in tests — it doesn't need an interface. DIP is critical for **dependencies with side effects** (IO, network, time) and for **variable behavior** (multiple email providers).

---

## SOLID as a system: principles reinforce each other

```txt
SRP → one "actor" changes the class → easier to comply with OCP
OCP → extension via new classes → requires ISP (no "fat" interfaces)
ISP → small interfaces → simplifies DIP (inject only what's needed)
DIP → dependency on abstractions → simplifies testing (swap implementations)
LSP → correct hierarchy → polymorphism works predictably (no surprises)
```

Violating one principle often violates others: a class with three responsibilities (SRP) is usually also tightly coupled to concrete dependencies (DIP), and adding new behavior requires modifying it (OCP).

## Common interview traps

- **"SOLID is five rules that must always be followed"** — without understanding trade-offs. The correct answer: these are principles that reduce the cost of change, not an end in themselves. Premature abstraction in the name of SOLID is as much a problem as its absence.

- **SRP as "one method = one class"** — SRP is about the reason for change ("one actor"), not the number of methods. A class with 10 methods serving one business domain respects SRP.

- **OCP through inheritance instead of composition** — candidates often explain OCP via `extends`, but the modern idiomatic approach is interfaces + strategies. Inheritance is one way, not the only way.

- **LSP only as "rectangle and square"** — this is the canonical example, but in practice LSP is more often violated via `throw new Error('Not implemented')` in interface methods. Being able to recognize this form of violation matters more than knowing the canonical example.

- **Confusing ISP and DIP** — ISP is about interfaces from the client's perspective ("don't force extra methods"), DIP is about the direction of dependency ("depend on abstraction, not on concreteness"). These are different axes.

- **DIP = Dependency Injection** — DIP is the principle (direction of dependency), DI is the pattern (mechanism of delivering the dependency). DI implements DIP, but DIP is broader: you can invert dependencies via Service Locator or factories — that is also DIP, though not classical DI.
