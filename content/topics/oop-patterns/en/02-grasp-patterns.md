# GRASP Patterns

## What GRASP is and why it's not "another pattern list"

GRASP (General Responsibility Assignment Software Patterns) are not implementation patterns like Singleton or Observer. They are **responsibility assignment principles**: answers to the question "which object should own this behavior or knowledge?"

```txt
GoF patterns (Creational/Structural/Behavioral) answer:
  "How do I implement X?"

GRASP answers:
  "Who should be responsible for X?"

These are different levels of abstraction. GRASP is closer to SOLID
in level than to GoF in character. They complement each other.
```

GRASP was formulated by Craig Larman in "Applying UML and Patterns" (1997). Unlike GoF patterns, GRASP is less well-known in interviews — which is exactly why knowing GRASP distinguishes a candidate who thinks about architecture from one who simply memorized patterns.

---

## 1. Information Expert — "own the data? own the behavior"

> Assign a responsibility to the class that has the information needed to fulfill it.

This is the most fundamental GRASP principle and simultaneously the most commonly violated. The violation looks like "a service that takes an object's data and computes something from the outside" instead of delegating the computation to the object itself.

### Information Expert Violation

```ts
// ❌ OrderController knows Order's structure (items, discount) and computes total externally.
// If Order's structure changes — OrderController and every other place
// that computes total manually must also change.

class OrderController {
  getOrderTotal(order: Order): number {
    let subtotal = 0;
    for (const item of order.items) {
      subtotal += item.price * item.quantity;
    }
    // Knowledge of how discount is applied is scattered across the controller
    if (order.discountPercent) {
      subtotal *= (1 - order.discountPercent / 100);
    }
    return subtotal;
  }
}
```

```ts
// ✅ Order knows its own items and discount — it computes total itself.
// OrderController simply calls the method.

class Order {
  constructor(
    public readonly items: OrderItem[],
    public readonly discountPercent: number = 0,
  ) {}

  get total(): number {
    const subtotal = this.items.reduce(
      (sum, item) => sum + item.price * item.quantity,
      0
    );
    return subtotal * (1 - this.discountPercent / 100);
  }
}

class OrderController {
  getOrderTotal(order: Order): number {
    return order.total; // responsibility delegated to the expert
  }
}
```

### Relation to SOLID

Information Expert is the practical realization of SRP at the data level. The class that owns the data has one reason to change in this context: a change in the data itself or the rules for processing it. If the logic is extracted outside — the external class gains an additional reason to change.

### Real-world context (React)

```tsx
// ❌ Parent component knows CartItem structure and computes total externally
function CartSummary({ items }: { items: CartItem[] }) {
  const total = items.reduce((s, i) => s + i.price * i.quantity, 0);
  return <div>Total: ${total}</div>;
}

// ✅ The Cart model is the Information Expert — it computes total
class Cart {
  constructor(public readonly items: CartItem[]) {}
  get total() {
    return this.items.reduce((s, i) => s + i.price * i.quantity, 0);
  }
}

function CartSummary({ cart }: { cart: Cart }) {
  return <div>Total: ${cart.total}</div>;
}
```

---

## 2. Creator — "create where you contain or use"

> Class B should create instances of class A if B contains A, aggregates A, is the initializer for A, or has the data needed to create A.

Creator answers the question "where should `new` be written?" without always having to extract creation into a factory.

### Creator Violation

```ts
// ❌ An external service creates OrderItem — even though OrderItem
// only exists in the context of Order

class OrderService {
  createOrder(data: CreateOrderDto): Order {
    // OrderService doesn't "own" OrderItem — why should it create them?
    const items = data.items.map(
      itemData => new OrderItem(itemData.productId, itemData.price, itemData.quantity)
    );
    return new Order(items);
  }
}
```

```ts
// ✅ Order aggregates OrderItem — it knows how to create them

class Order {
  private items: OrderItem[] = [];

  addItem(productId: string, price: number, quantity: number): void {
    // Order is the Creator of OrderItem, because it contains them
    this.items.push(new OrderItem(productId, price, quantity));
  }

  static fromDto(dto: CreateOrderDto): Order {
    const order = new Order();
    for (const item of dto.items) {
      order.addItem(item.productId, item.price, item.quantity);
    }
    return order;
  }
}

class OrderService {
  createOrder(data: CreateOrderDto): Order {
    return Order.fromDto(data); // creation encapsulated inside Order
  }
}
```

### Relation to SOLID

Creator relates to SRP: if a class creates objects that don't "belong" to it, that adds an extra responsibility. Creator also echoes the Factory pattern (see [Creational Patterns]) — Factory is needed when the "contains or uses" condition is not met and a dedicated creation point is required.

---

## 3. Controller — "one entry facade for a system event"

> Assign responsibility for handling a system event to a controller class representing either the overall system or a use-case scenario.

Controller is the intermediary between the UI/API layer and business logic. It contains no logic itself — it delegates to domain objects or services.

### Controller Violation

```ts
// ❌ The controller contains business logic —
// it simultaneously parses the request, validates, computes a discount,
// generates a receipt, and sends an email

@Post('/orders')
async createOrder(@Body() dto: CreateOrderDto, @Req() req: Request) {
  // Discount logic — in the controller!
  const discount = req.user.isPremium ? 0.15 : 0;

  let total = 0;
  for (const item of dto.items) {
    total += item.price * item.quantity;
  }
  total *= (1 - discount);

  const order = await this.db.orders.insert({ ...dto, total, userId: req.user.id });

  // Email — also in the controller!
  await this.emailClient.send({
    to: req.user.email,
    subject: 'Order confirmed',
    body: `Your order #${order.id} total is $${total}`,
  });

  return order;
}
```

```ts
// ✅ Thin controller: receive request, delegate, return response

@Post('/orders')
async createOrder(
  @Body() dto: CreateOrderDto,
  @CurrentUser() user: User,
): Promise<OrderResponseDto> {
  // All logic in OrderService — controller only orchestrates
  const order = await this.orderService.createOrder(user, dto);
  return OrderResponseDto.fromDomain(order);
}
```

### Relation to SOLID

A "thin controller" is the direct consequence of SRP (the controller changes only when the HTTP interface changes) and DIP (the controller depends on the service abstraction, not on concrete logic). In NestJS this manifests as the controller injecting a service rather than instantiating it.

---

## 4. Low Coupling — "minimal dependencies, maximum independence"

> Strive for low coupling between classes so that changes to one class don't require changes to others.

Low Coupling is not the goal of "having no dependencies at all" — it's the goal of **depending only on what is stable**. Depending on an interface = low coupling. Depending on a concrete class that changes frequently = high coupling.

```txt
Types of coupling (from least to most problematic):
  Data coupling    — classes exchange only simple data (good)
  Stamp coupling   — pass entire object when only one field is needed (neutral)
  Control coupling — one class controls another's behavior via a flag (bad)
  Content coupling — one class reads/writes another's internal data (very bad)
```

### Low Coupling Violation

```ts
// ❌ UserService directly imports concrete classes —
// any change to EmailClient or AvatarService potentially breaks UserService

import { SendgridEmailClient } from '../infrastructure/sendgrid-email-client';
import { CloudinaryAvatarService } from '../infrastructure/cloudinary-avatar-service';
import { PostgresUserRepository } from '../infrastructure/postgres-user-repository';

class UserService {
  private emailClient = new SendgridEmailClient(process.env.SENDGRID_KEY!);
  private avatarService = new CloudinaryAvatarService(process.env.CLOUDINARY_URL!);
  private userRepo = new PostgresUserRepository(process.env.DATABASE_URL!);

  // Testing this class requires real Sendgrid, Cloudinary, Postgres
}
```

```ts
// ✅ UserService depends on interfaces — concrete implementations supplied from outside

interface IEmailClient {
  sendWelcome(email: string): Promise<void>;
}

interface IAvatarService {
  upload(userId: string, file: Buffer): Promise<string>;
}

interface IUserRepository {
  save(user: User): Promise<User>;
}

class UserService {
  constructor(
    private readonly emailClient: IEmailClient,
    private readonly avatarService: IAvatarService,
    private readonly userRepo: IUserRepository,
  ) {}
}
```

### Low Coupling in React

```tsx
// ❌ Component directly calls fetch — coupled to a concrete API
function UserProfile({ userId }: { userId: string }) {
  const [user, setUser] = useState<User | null>(null);
  useEffect(() => {
    fetch(`/api/users/${userId}`).then(r => r.json()).then(setUser);
  }, [userId]);
  return <div>{user?.name}</div>;
}

// ✅ Component depends on an abstraction hook — implementation is swappable
function UserProfile({ userId }: { userId: string }) {
  const { user } = useUser(userId); // hook hides the data source
  return <div>{user?.name}</div>;
}
```

---

## 5. High Cohesion — "do one thing, do it well"

> A class's responsibilities should be closely related and focused on one area. Low cohesion produces "god classes" that are hard to understand and change.

High Cohesion is the functional sibling of Low Coupling: Low Coupling says "don't depend on unnecessary things from outside," High Cohesion says "don't do unnecessary things inside."

```txt
Signs of low cohesion:
  - Class is named XxxManager, XxxHelper, XxxUtil — generic names
    often signal an absence of clear responsibility
  - Class methods barely use each other's fields — they simply
    coexist in one file without internal relationship
  - Changing one function requires understanding the entire class
```

### High Cohesion Violation

```ts
// ❌ UserManager does everything: auth, avatars, payments, analytics.
// This is a low-cohesion class — its methods are unrelated to each other.

class UserManager {
  async loginUser(email: string, password: string) { ... }
  async logoutUser(userId: string) { ... }
  async uploadAvatar(userId: string, file: Buffer) { ... }
  async processPayment(userId: string, amount: number) { ... }
  async getUserStats(userId: string) { ... }
  async sendNewsletterToAll() { ... }
  async generateUserReport(from: Date, to: Date) { ... }
}
```

```ts
// ✅ Each class is highly cohesive: its methods work with the same data

class AuthService {
  async login(email: string, password: string): Promise<AuthToken> { ... }
  async logout(userId: string): Promise<void> { ... }
  async refreshToken(token: string): Promise<AuthToken> { ... }
}

class AvatarService {
  async upload(userId: string, file: Buffer): Promise<string> { ... }
  async delete(userId: string): Promise<void> { ... }
  async resize(userId: string, size: number): Promise<string> { ... }
}

class BillingService {
  async charge(userId: string, amount: number): Promise<Receipt> { ... }
  async refund(paymentId: string): Promise<void> { ... }
}
```

### High Cohesion vs SRP

They are often confused in practice. The difference:

```txt
SRP — about the reason for change (one actor):
  "This class changes only when the security team demands it"

High Cohesion — about internal method relatedness:
  "All methods in this class work with the same data
   and belong to the same area of knowledge"

A class can violate SRP (two actors may demand changes)
while still having high cohesion. And vice versa. But in practice
a violation of one usually accompanies a violation of the other.
```

---

## 6. Polymorphism — "object type determines behavior, not branching if/switch"

> When behavior varies by type, use polymorphism instead of conditional constructs.

This is one of the foundational OOP principles, but GRASP frames it as a responsibility assignment guideline: **responsibility for variable behavior should lie with the object itself**, not with external code that inspects its type.

### Violation — "type-checking antipattern"

```ts
// ❌ Business logic is scattered across conditionals.
// Add a new notification type → find and change ALL such switch blocks.

function renderNotification(notification: Notification) {
  switch (notification.type) {
    case 'info':
      return `ℹ️ ${notification.message}`;
    case 'warning':
      return `⚠️ ${notification.message}`;
    case 'error':
      return `❌ ${notification.message} (code: ${notification.errorCode})`;
    case 'success':
      return `✅ ${notification.message}`;
  }
}
```

```ts
// ✅ Each type knows how to render itself

interface Notification {
  render(): string;
}

class InfoNotification implements Notification {
  constructor(private message: string) {}
  render() { return `ℹ️ ${this.message}`; }
}

class WarningNotification implements Notification {
  constructor(private message: string) {}
  render() { return `⚠️ ${this.message}`; }
}

class ErrorNotification implements Notification {
  constructor(private message: string, private errorCode: string) {}
  render() { return `❌ ${this.message} (code: ${this.errorCode})`; }
}

// Calling code doesn't know about types — just calls render()
function displayNotification(notification: Notification) {
  console.log(notification.render());
}
```

### Real-world context (Node.js + NestJS)

```ts
// ❌ ExportService with if-blocks per format type
class ExportService {
  async export(data: ReportData, format: string): Promise<Buffer> {
    if (format === 'pdf') {
      return generatePdf(data);
    } else if (format === 'csv') {
      return generateCsv(data);
    } else if (format === 'xlsx') {
      return generateXlsx(data);
    }
    throw new Error(`Unknown format: ${format}`);
  }
}

// ✅ Polymorphism: each formatter is a separate class
interface ReportFormatter {
  format(data: ReportData): Promise<Buffer>;
  readonly contentType: string;
}

class PdfFormatter implements ReportFormatter {
  readonly contentType = 'application/pdf';
  async format(data: ReportData) { return generatePdf(data); }
}

class CsvFormatter implements ReportFormatter {
  readonly contentType = 'text/csv';
  async format(data: ReportData) { return generateCsv(data); }
}

class ExportService {
  constructor(private readonly formatters: Map<string, ReportFormatter>) {}

  async export(data: ReportData, format: string): Promise<Buffer> {
    const formatter = this.formatters.get(format);
    if (!formatter) throw new Error(`Unknown format: ${format}`);
    return formatter.format(data);
  }
}
```

### Relation to OCP

Polymorphism is the mechanism that makes OCP work in practice. "Open for extension, closed for modification" is achieved precisely through polymorphism: new behavior = new class implementing an interface.

---

## 7. Pure Fabrication — "sometimes you need a class without a real-world counterpart"

> If no domain class is a suitable candidate for a responsibility (and assigning it would violate High Cohesion or Low Coupling), create an artificial service class.

Pure Fabrication is "permission to create a class without a domain meaning." Most services in layered architecture (Repository, Mapper, Formatter, Gateway) are Pure Fabrications: "UserRepository" doesn't exist in the real world — it's a technical abstraction.

### Example: when Pure Fabrication is needed

```ts
// Situation: every order change must be logged.
// Where does this responsibility go?

// ❌ Into Order? — Order starts depending on logging infrastructure → Low Coupling violated
class Order {
  async updateStatus(status: OrderStatus) {
    this.status = status;
    await logger.log(`Order ${this.id} status changed to ${status}`); // ← bad
  }
}

// ❌ Into OrderService? — OrderService already has its own responsibility (business ops)
// Logging is a different responsibility → SRP violated

// ✅ Pure Fabrication: OrderAuditLogger — an artificial class with no domain counterpart,
// whose sole responsibility is auditing changes

class OrderAuditLogger {
  constructor(private readonly logger: Logger) {}

  async logStatusChange(orderId: string, oldStatus: OrderStatus, newStatus: OrderStatus) {
    await this.logger.info('order.status_changed', {
      orderId,
      from: oldStatus,
      to: newStatus,
      timestamp: new Date().toISOString(),
    });
  }
}

// Order and OrderService stay clean — Pure Fabrication takes on
// the infrastructural responsibility
```

### Real-world context

In layered architecture, Pure Fabrications form the entire infrastructure layer: `UserRepository`, `EmailGateway`, `S3FileStorage`, `JwtTokenService`. None of them correspond to a real domain object, but each takes on a specific infrastructural responsibility, freeing domain classes from it.

### When Pure Fabrication becomes an anti-pattern

If **all** classes in a project are Pure Fabrications (services, managers, helpers with no domain objects) — this is called an "Anemic Domain Model": procedural code disguised as OOP. Domain classes — `Order`, `User`, `Product` — should contain domain-specific logic (discount calculation, invariant validation). Pure Fabrication supplements them, it does not replace them.

---

## GRASP and SOLID — correspondence table

```txt
GRASP principle      Corresponding SOLID principle
──────────────────────────────────────────────────
Information Expert → SRP (data and its processing in one place)
Creator            → SRP (creation is the aggregate's responsibility)
Controller         → SRP (thin layer without business logic)
Low Coupling       → DIP (depend on abstractions, not concretions)
High Cohesion      → SRP (focus on one area of knowledge)
Polymorphism       → OCP (extension without modification)
Pure Fabrication   → SRP + ISP (extract infrastructural responsibility)
```

GRASP does not contradict SOLID — they are two lenses on the same question: how to structure code so it can be changed without fear.

## Common interview traps

- **"GRASP is the same as GoF patterns"** — confusing levels. GoF are concrete implementation patterns (Singleton, Observer). GRASP are principles of responsibility distribution. These are different tools at different levels of abstraction.

- **Not knowing GRASP at all** — everyone knows SOLID, very few know GRASP. Mentioning GRASP with a correct explanation immediately distinguishes a candidate in an architecture discussion.

- **Information Expert == "put all logic in the model"** — this is a swing toward a "fat model." Information Expert says: put computation that directly depends on an object's data into the object. But business operations with side effects (saving, sending) stay in services.

- **Creator as "always use new inside a class"** — Creator describes who is the logical creator (whoever contains or uses the object). It's not a ban on factories — Factory is needed when creation is complex or variable.

- **Low Coupling as "no dependencies at all"** — zero coupling is impossible and undesirable. The goal is to depend only on stable abstractions, not to avoid dependencies entirely.

- **Not distinguishing High Cohesion from SRP** — both are about "do one thing" but from different angles: SRP is about the reason for change (an external actor), High Cohesion is about internal method relatedness (do they use shared data and knowledge). You can violate one without violating the other.

- **Pure Fabrication as justification for "a service for everything"** — Pure Fabrication is legitimate when no domain object fits. But if the entire application consists of manager-services with no domain objects containing logic — that's an Anemic Domain Model, and that's a problem.
