# Structural Patterns

## Why structural patterns exist

Structural patterns describe **how to compose classes and objects into larger structures** while keeping flexibility. Where creational patterns answer "how to create an object," structural patterns answer "how to connect objects so the system interface stays simple and internal complexity stays encapsulated."

```txt
Creational  → "who creates, and how"
Structural  → "how objects and classes connect to each other"
Behavioral  → "how objects interact and distribute responsibility"
```

---

## Adapter — "bridge between incompatible interfaces"

> Converts a class's interface into another interface the client expects. Allows classes with incompatible interfaces to work together.

Adapter is one of the most common patterns in real code: almost every time you connect a third-party library to your own architecture, you need an adapter.

### Example: adapting a third-party email client

```ts
// Internal application interface:
interface EmailService {
  send(to: string, subject: string, body: string): Promise<void>;
}

// Third-party library — Sendgrid SDK with a DIFFERENT interface:
class SendgridClient {
  async sendMail(params: {
    personalizations: Array<{ to: Array<{ email: string }> }>;
    from: { email: string };
    subject: string;
    content: Array<{ type: string; value: string }>;
  }): Promise<void> {
    // ... real HTTP request to Sendgrid API
  }
}

// ❌ Without adapter — the entire codebase knows about the Sendgrid-specific format:
async function notifyUser(userId: string, message: string) {
  await sendgridClient.sendMail({
    personalizations: [{ to: [{ email: user.email }] }],
    from: { email: 'noreply@app.com' },
    subject: 'Notification',
    content: [{ type: 'text/plain', value: message }],
  });
  // Switching Sendgrid for Mailgun → edits throughout the entire codebase
}

// ✅ Adapter: wraps Sendgrid in our EmailService interface

class SendgridAdapter implements EmailService {
  constructor(
    private readonly client: SendgridClient,
    private readonly fromEmail: string,
  ) {}

  async send(to: string, subject: string, body: string): Promise<void> {
    await this.client.sendMail({
      personalizations: [{ to: [{ email: to }] }],
      from: { email: this.fromEmail },
      subject,
      content: [{ type: 'text/plain', value: body }],
    });
  }
}

// All code works with EmailService — replacing Sendgrid with Mailgun:
// create a new MailgunAdapter, swap it in the DI container, nothing else changes
async function notifyUser(emailService: EmailService, userEmail: string, message: string) {
  await emailService.send(userEmail, 'Notification', message);
}
```

### Real-world context (React)

```tsx
// Adapter in React — a wrapper around a third-party UI library
// aligned to the application's internal component interface

// External library react-select has its own API:
import ReactSelect from 'react-select';

// Internal application interface:
interface SelectProps {
  options: Array<{ value: string; label: string }>;
  value: string;
  onChange: (value: string) => void;
}

// Adapter: translates the internal interface to the react-select API
function AppSelect({ options, value, onChange }: SelectProps) {
  return (
    <ReactSelect
      options={options}
      value={options.find(o => o.value === value)}
      onChange={(opt) => opt && onChange(opt.value)}
    />
  );
}

// All code uses <AppSelect> with a simple API.
// Switching react-select for another library — only change AppSelect.
```

---

## Bridge — "separate abstraction from implementation"

> Decouples an abstraction from its implementation so that the two can vary independently.

Bridge solves the "subclass explosion" problem when combining two axes of variation. Without Bridge: N abstractions × M implementations = N×M classes. With Bridge: N + M classes.

```txt
Without Bridge (subclass explosion):
  LightThemeButton, DarkThemeButton
  LightThemeInput, DarkThemeInput
  LightThemeModal, DarkThemeModal
  ... adding SystemTheme → 3 more classes

With Bridge (N + M):
  Button(theme), Input(theme), Modal(theme)
  LightTheme, DarkTheme, SystemTheme
  → add a theme = 1 new class
  → add a component = 1 new class
```

### Example: renderer + theme

```ts
// "Implementation" — visual theme (axis 1)
interface Theme {
  buttonStyle(): string;
  inputStyle(): string;
  backgroundColor(): string;
}

class LightTheme implements Theme {
  buttonStyle() { return 'bg-white text-black border border-gray-300'; }
  inputStyle() { return 'bg-white border border-gray-200'; }
  backgroundColor() { return '#ffffff'; }
}

class DarkTheme implements Theme {
  buttonStyle() { return 'bg-gray-800 text-white border border-gray-600'; }
  inputStyle() { return 'bg-gray-700 border border-gray-600 text-white'; }
  backgroundColor() { return '#1a1a1a'; }
}

// "Abstraction" — UI component (axis 2)
// Bridge: abstraction holds a reference to the implementation (theme)
abstract class UIComponent {
  constructor(protected readonly theme: Theme) {}
  abstract render(): string;
}

class Button extends UIComponent {
  constructor(theme: Theme, private readonly label: string) {
    super(theme);
  }
  render(): string {
    return `<button class="${this.theme.buttonStyle()}">${this.label}</button>`;
  }
}

class TextInput extends UIComponent {
  constructor(theme: Theme, private readonly placeholder: string) {
    super(theme);
  }
  render(): string {
    return `<input class="${this.theme.inputStyle()}" placeholder="${this.placeholder}" />`;
  }
}

// Add SystemTheme → 1 new Theme class, Button and TextInput unchanged
// Add Checkbox → 1 new UIComponent class, themes unchanged
const darkButton = new Button(new DarkTheme(), 'Submit');
const lightInput = new TextInput(new LightTheme(), 'Enter email');
```

### Bridge vs Strategy

```txt
Bridge — structural pattern: implementation is chosen at object creation time
  and usually doesn't change (an architectural decision about how the object is built)

Strategy — behavioral pattern: algorithm can be swapped at runtime
  (a decision about how the object behaves at a specific moment)

The boundary is blurry — often the same thing is implemented via both.
Key question: "Is this a permanent structure or switchable behavior?"
```

---

## Composite — "tree of objects, single interface"

> Composes objects into tree structures to represent part-whole hierarchies. Lets clients treat individual objects and compositions of objects uniformly.

Composite is needed whenever a data structure is recursive: file systems, DOM trees, organizational hierarchies, product categories.

### Example: file system

```ts
// Single interface for files and directories
interface FileSystemItem {
  name: string;
  size(): number;
  print(indent?: string): void;
}

// Leaf — a file, cannot contain children
class File implements FileSystemItem {
  constructor(
    public readonly name: string,
    private readonly sizeInBytes: number,
  ) {}

  size(): number { return this.sizeInBytes; }

  print(indent = ''): void {
    console.log(`${indent}📄 ${this.name} (${this.sizeInBytes}B)`);
  }
}

// Composite — a directory
class Directory implements FileSystemItem {
  private children: FileSystemItem[] = [];

  constructor(public readonly name: string) {}

  add(item: FileSystemItem): void { this.children.push(item); }
  remove(item: FileSystemItem): void {
    this.children = this.children.filter(c => c !== item);
  }

  // Recursively sums the sizes of all children
  size(): number {
    return this.children.reduce((total, child) => total + child.size(), 0);
  }

  print(indent = ''): void {
    console.log(`${indent}📁 ${this.name}/`);
    this.children.forEach(child => child.print(indent + '  '));
  }
}

// Client code works with FileSystemItem — doesn't know if it's a file or directory:
const root = new Directory('project');
const src = new Directory('src');
src.add(new File('index.ts', 1024));
src.add(new File('app.ts', 2048));

const node_modules = new Directory('node_modules');
node_modules.add(new File('express.js', 51200));

root.add(src);
root.add(node_modules);
root.add(new File('package.json', 512));

root.print();
// 📁 project/
//   📁 src/
//     📄 index.ts (1024B)
//     📄 app.ts (2048B)
//   📁 node_modules/
//     📄 express.js (51200B)
//   📄 package.json (512B)

console.log(`Total: ${root.size()}B`); // recursively sums the entire tree
```

### Real-world context (React)

```tsx
// A React component tree is Composite:
// each component can contain other components or be a leaf

// Composite component:
function Layout({ children }: { children: React.ReactNode }) {
  return <div className="layout">{children}</div>;
}

// Usage — uniform children interface for any nesting depth:
<Layout>
  <Header />           {/* leaf */}
  <Layout>             {/* composite */}
    <Sidebar />        {/* leaf */}
    <MainContent />    {/* leaf */}
  </Layout>
  <Footer />           {/* leaf */}
</Layout>
```

---

## Decorator — "add behavior without changing the class"

> Dynamically attaches additional responsibilities to an object. Provides a flexible alternative to subclassing for extending functionality.

Decorator wraps an object in another object with the same interface, adding behavior before or after the original operation.

### Example: HTTP client with decorators

```ts
interface HttpClient {
  get<T>(url: string): Promise<T>;
  post<T>(url: string, body: unknown): Promise<T>;
}

// Base implementation
class FetchHttpClient implements HttpClient {
  async get<T>(url: string): Promise<T> {
    const res = await fetch(url);
    return res.json() as Promise<T>;
  }
  async post<T>(url: string, body: unknown): Promise<T> {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return res.json() as Promise<T>;
  }
}

// Logging decorator — doesn't touch the base client
class LoggingHttpClient implements HttpClient {
  constructor(
    private readonly client: HttpClient,
    private readonly logger: Logger,
  ) {}

  async get<T>(url: string): Promise<T> {
    this.logger.info(`GET ${url}`);
    const result = await this.client.get<T>(url);
    this.logger.info(`GET ${url} → OK`);
    return result;
  }

  async post<T>(url: string, body: unknown): Promise<T> {
    this.logger.info(`POST ${url}`, { body });
    const result = await this.client.post<T>(url, body);
    this.logger.info(`POST ${url} → OK`);
    return result;
  }
}

// Retry decorator — wraps any HttpClient (including already-decorated ones)
class RetryHttpClient implements HttpClient {
  constructor(
    private readonly client: HttpClient,
    private readonly maxRetries: number = 3,
  ) {}

  async get<T>(url: string): Promise<T> {
    return this.withRetry(() => this.client.get<T>(url));
  }

  async post<T>(url: string, body: unknown): Promise<T> {
    return this.withRetry(() => this.client.post<T>(url, body));
  }

  private async withRetry<T>(operation: () => Promise<T>): Promise<T> {
    let lastError: Error;
    for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
      try {
        return await operation();
      } catch (err) {
        lastError = err as Error;
        if (attempt < this.maxRetries) {
          await new Promise(r => setTimeout(r, 2 ** attempt * 100)); // exponential backoff
        }
      }
    }
    throw lastError!;
  }
}

// Decorator stack — wrap one at a time:
const client: HttpClient = new RetryHttpClient(
  new LoggingHttpClient(
    new FetchHttpClient(),
    logger,
  ),
  3,
);

// Interface unchanged — consumer doesn't know about the decorators:
const user = await client.get<User>('/api/users/1');
```

### HOC (Higher-Order Component) as Decorator in React

```tsx
// HOC is the classic Decorator example in React:
// wraps a component, adding behavior (authentication, logging, accessibility)

function withAuth<P extends object>(Component: React.FC<P>): React.FC<P> {
  return function AuthGuard(props: P) {
    const { isAuthenticated } = useAuth();
    if (!isAuthenticated) return <Navigate to="/login" />;
    return <Component {...props} />;
  };
}

function withErrorBoundary<P extends object>(Component: React.FC<P>): React.FC<P> {
  return function WithBoundary(props: P) {
    return (
      <ErrorBoundary fallback={<ErrorPage />}>
        <Component {...props} />
      </ErrorBoundary>
    );
  };
}

// Decorator stack — composed HOCs:
const ProtectedDashboard = withAuth(withErrorBoundary(Dashboard));
```

### Are TypeScript `@Decorator` annotations the Decorator pattern?

```ts
// TypeScript decorators (@Injectable, @Controller, @Get) —
// these are class-level metadata and transformations at compile time.
// Structurally they resemble the Decorator pattern (wrap/modify a class),
// but they work via Reflect.metadata, not via a wrapper with the same interface.

@Injectable()
class UserService {
  // @Injectable adds metadata for the NestJS DI container —
  // this is the Decorator pattern in spirit, but not in classical GoF structure
}
```

---

## Facade — "simple face for a complex subsystem"

> Provides a unified interface to a set of interfaces in a subsystem. Makes the subsystem easier to use.

Facade is the most "humane" structural pattern: it adds no new behavior, it simply hides complexity.

### Example: order checkout

```ts
// Subsystems with their own complex interfaces:
class InventoryService {
  async checkStock(productId: string, qty: number): Promise<boolean> { ... }
  async reserveStock(productId: string, qty: number): Promise<string> { ... }
  async releaseReservation(reservationId: string): Promise<void> { ... }
}

class PaymentService {
  async createPaymentIntent(amount: number, currency: string): Promise<string> { ... }
  async confirmPayment(intentId: string, methodId: string): Promise<Receipt> { ... }
  async refund(intentId: string): Promise<void> { ... }
}

class ShippingService {
  async calculateRate(address: Address, weight: number): Promise<number> { ... }
  async createShipment(orderId: string, address: Address): Promise<TrackingNumber> { ... }
  async cancelShipment(trackingNumber: string): Promise<void> { ... }
}

class NotificationService {
  async sendOrderConfirmation(email: string, orderId: string): Promise<void> { ... }
  async sendShippingUpdate(email: string, trackingNumber: string): Promise<void> { ... }
}

// ❌ Without facade — the controller coordinates all subsystems manually,
// knows their details and their sequence:

@Post('/orders')
async checkout(dto: CheckoutDto) {
  const inStock = await this.inventoryService.checkStock(dto.productId, dto.qty);
  if (!inStock) throw new BadRequestException('Out of stock');
  const reservationId = await this.inventoryService.reserveStock(dto.productId, dto.qty);
  const intentId = await this.paymentService.createPaymentIntent(dto.amount, 'usd');
  let receipt: Receipt;
  try {
    receipt = await this.paymentService.confirmPayment(intentId, dto.paymentMethodId);
  } catch (e) {
    await this.inventoryService.releaseReservation(reservationId);
    throw e;
  }
  const tracking = await this.shippingService.createShipment(dto.orderId, dto.address);
  await this.notificationService.sendOrderConfirmation(dto.email, dto.orderId);
  return { receipt, tracking };
}

// ✅ Facade: OrderFacade hides orchestration — controller makes one call

class OrderFacade {
  constructor(
    private readonly inventory: InventoryService,
    private readonly payment: PaymentService,
    private readonly shipping: ShippingService,
    private readonly notification: NotificationService,
  ) {}

  async placeOrder(dto: CheckoutDto): Promise<OrderResult> {
    const inStock = await this.inventory.checkStock(dto.productId, dto.qty);
    if (!inStock) throw new Error('Out of stock');

    const reservationId = await this.inventory.reserveStock(dto.productId, dto.qty);
    const intentId = await this.payment.createPaymentIntent(dto.amount, 'usd');

    let receipt: Receipt;
    try {
      receipt = await this.payment.confirmPayment(intentId, dto.paymentMethodId);
    } catch (e) {
      await this.inventory.releaseReservation(reservationId);
      throw e;
    }

    const tracking = await this.shipping.createShipment(dto.orderId, dto.address);
    await this.notification.sendOrderConfirmation(dto.email, dto.orderId);

    return { receipt, tracking };
  }
}

// Controller — one call, unaware of subsystem details:
@Post('/orders')
async checkout(dto: CheckoutDto) {
  return this.orderFacade.placeOrder(dto);
}
```

### Facade vs Controller (GRASP)

```txt
Controller (GRASP) — thin layer between HTTP and business logic, contains no logic itself.
Facade — contains orchestration logic between subsystems, hides them from the client.

Common NestJS structure: Controller → Facade → individual Services.
Facade is not a Controller; it's the layer between the controller and the domain.
```

---

## Flyweight — "share common state across many objects"

> Uses sharing to efficiently support a large number of fine-grained objects.

Flyweight is needed when a huge number of objects are created with shared, immutable state. Instead of storing that state in every object — store it once and share it.

```txt
Intrinsic state (shared, internal):
  Immutable data common to many objects.
  Stored in the Flyweight object.

Extrinsic state (unique, contextual):
  Data unique to each usage.
  Passed in when a method is called, not stored in the Flyweight.
```

### Example: rendering characters in a text editor

```ts
// Flyweight — immutable character data (font, size, style)
class CharacterGlyph {
  constructor(
    public readonly font: string,
    public readonly size: number,
    public readonly bold: boolean,
    public readonly italic: boolean,
  ) {}

  render(char: string, x: number, y: number): void {
    // Expensive rendering operation — but one glyph per style across all characters
    console.log(`Render '${char}' at (${x},${y}) in ${this.font} ${this.size}px`);
  }
}

// Flyweight Factory — returns an existing glyph or creates a new one
class GlyphFactory {
  private readonly glyphs = new Map<string, CharacterGlyph>();

  getGlyph(font: string, size: number, bold: boolean, italic: boolean): CharacterGlyph {
    const key = `${font}-${size}-${bold}-${italic}`;
    if (!this.glyphs.has(key)) {
      this.glyphs.set(key, new CharacterGlyph(font, size, bold, italic));
    }
    return this.glyphs.get(key)!;
  }

  get glyphCount(): number { return this.glyphs.size; }
}

// Character in document — only extrinsic state (position, the character itself) + flyweight reference
class Character {
  constructor(
    private readonly char: string,
    private readonly x: number,
    private readonly y: number,
    private readonly glyph: CharacterGlyph, // shared flyweight
  ) {}

  render(): void { this.glyph.render(this.char, this.x, this.y); }
}

// 100 000 document characters — but only a handful of unique glyphs:
const factory = new GlyphFactory();
const document: Character[] = [];

for (let i = 0; i < 100_000; i++) {
  const glyph = factory.getGlyph('Arial', 14, false, false); // same object returned
  document.push(new Character('A', i * 10, 0, glyph));
}

console.log(factory.glyphCount); // 1, not 100 000
```

### Flyweight in real systems

```txt
Real Flyweight examples:
  - String interning: identical strings stored as one object in memory
  - Database connection pool: connections shared across requests
  - Icons and sprites in UI: one image object used in thousands of DOM places
  - React Virtual DOM: React reuses DOM nodes when rendering lists (key prop)
```

---

## Proxy — "surrogate with additional control"

> Provides a surrogate object that controls access to another object.

Proxy has the same interface as the target object, but intercepts calls to add: lazy initialization, caching, access control, logging.

```txt
Proxy types:
  Virtual Proxy    — lazy initialization (object created on first access)
  Protection Proxy — access control (permission check before delegating)
  Caching Proxy    — caches results of expensive operations
  Remote Proxy     — represents a remote object (RPC, microservices)
  Logging Proxy    — logs accesses (like Decorator, but via Proxy)
```

### Example: Caching Proxy for a repository

```ts
interface UserRepository {
  findById(id: string): Promise<User | null>;
  findByEmail(email: string): Promise<User | null>;
  save(user: User): Promise<User>;
}

class PostgresUserRepository implements UserRepository {
  async findById(id: string): Promise<User | null> {
    return db.query('SELECT * FROM users WHERE id = $1', [id]);
  }
  async findByEmail(email: string): Promise<User | null> {
    return db.query('SELECT * FROM users WHERE email = $1', [email]);
  }
  async save(user: User): Promise<User> {
    return db.query('...');
  }
}

// Caching Proxy — same interface, adds caching
class CachedUserRepository implements UserRepository {
  private readonly cache = new Map<string, User>();

  constructor(private readonly repository: UserRepository) {}

  async findById(id: string): Promise<User | null> {
    if (this.cache.has(id)) {
      return this.cache.get(id)!; // cache hit — no database call
    }
    const user = await this.repository.findById(id);
    if (user) this.cache.set(id, user);
    return user;
  }

  async findByEmail(email: string): Promise<User | null> {
    return this.repository.findByEmail(email); // not cached by email
  }

  async save(user: User): Promise<User> {
    const saved = await this.repository.save(user);
    this.cache.set(saved.id, saved); // invalidate and update cache
    return saved;
  }
}

// Consumer is unaware of the cache — just receives UserRepository:
const userRepo: UserRepository = new CachedUserRepository(
  new PostgresUserRepository(),
);
```

### Proxy via JavaScript `Proxy`

```ts
// ES6 Proxy — built-in mechanism for intercepting operations on an object

function createValidationProxy<T extends object>(target: T, schema: Schema<T>): T {
  return new Proxy(target, {
    set(obj, prop, value) {
      const fieldSchema = schema[prop as keyof T];
      if (fieldSchema && !fieldSchema.validate(value)) {
        throw new Error(`Invalid value for ${String(prop)}: ${value}`);
      }
      obj[prop as keyof T] = value;
      return true;
    },
  });
}

const user = createValidationProxy({ name: '', age: 0 }, {
  name: { validate: (v: string) => v.length > 0 },
  age: { validate: (v: number) => v >= 0 && v <= 150 },
});

user.name = 'Alice';  // OK
user.age = -1;        // throws: Invalid value for age: -1
```

### Express middleware as a chain of Proxy/Decorator

```ts
// Express middleware is the functional analogue of a Decorator/Proxy chain:
// each middleware wraps request handling, adding behavior

app.use(cors());             // Decorator: adds CORS headers
app.use(helmet());           // Decorator: adds security headers
app.use(rateLimiter());      // Proxy: controls access (rate limiting)
app.use(authenticate());     // Protection Proxy: validates token
app.use(requestLogger());    // Logging Proxy: logs requests
app.use('/api', router);     // finally — the real handler
```

---

## Comparison of structural patterns

```txt
Pattern    Core idea                                  Real-world example
────────────────────────────────────────────────────────────────────────
Adapter    Translates a foreign interface to yours    Sendgrid SDK → EmailService
Bridge     Separates abstraction from implementation  Component × Theme
Composite  Object tree with a single interface        React tree, file system
Decorator  Wraps an object, adding behavior           HOC, HTTP client with retry+logging
Facade     Simplified interface to a subsystem        OrderFacade, BFF layer
Flyweight  Shares common state                        String pool, connection pool
Proxy      Surrogate with additional control          Cache, auth guard, ES6 Proxy
```

## Common interview traps

- **Confusing Adapter and Facade** — Adapter changes the interface of one object. Facade creates a simplified interface over several objects/subsystems. Key difference: Adapter works with one object, Facade works with a group.

- **Confusing Decorator and Proxy** — both wrap an object. Decorator **adds** new behavior/functionality. Proxy **controls access** to existing behavior. In practice the boundary is blurry, but in an interview be clear: "Decorator = extension, Proxy = access control."

- **"HOC is not a pattern, it's just a React feature"** — HOC is a direct implementation of the Decorator pattern in functional style. Naming the pattern behind a concrete technique signals systems thinking.

- **Flyweight without separating intrinsic/extrinsic state** — without clearly defining what is shared (immutable) and what is contextual (unique), Flyweight becomes just a regular cache. The state separation is the essence of the pattern.

- **Composite only for file systems** — this is the best-known example, but Composite appears anywhere there is a recursive structure: DOM, AST, organizational hierarchies, menu/submenu, categories with subcategories.

- **Proxy and ES6 `new Proxy()`** — ES6 Proxy implements the Proxy pattern, but they are not the same thing. The Proxy pattern is the architectural idea of a surrogate object. ES6 Proxy is a language mechanism conveniently used to implement the pattern, but it doesn't exhaust it.

- **Not recognizing that Express middleware is a structural pattern** — the middleware chain via `app.use()` can and should be described in terms of patterns: Decorator (adds behavior) and Chain of Responsibility (passes control via `next()`). This shows understanding of patterns in real code, not just in textbooks.
