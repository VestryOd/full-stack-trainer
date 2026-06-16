# Creational Patterns

## Why isolate object creation into a pattern

Creational patterns solve one question: **how to create objects so that the code using an object does not depend on the details of its creation**. This is the direct consequence of DIP from SOLID: if `new ConcreteClass(arg1, arg2, arg3)` is scattered throughout the codebase — changing the implementation means touching every occurrence.

```txt
Without a creational pattern:
  const db = new PostgresDatabase(host, port, user, password, poolSize);
  // this line in 40 places → switching to MongoDB requires 40 edits

With a factory / DI container:
  const db = DatabaseFactory.create(config);
  // changing the implementation — in one place
```

Not every `new` needs a pattern. The rule of thumb: **a pattern is needed when creation is complex, variable, or must be isolated from the consumer**.

---

## Singleton

> Ensures a class has only one instance, and provides a global access point to it.

### Basic TypeScript implementation

```ts
class DatabaseConnection {
  private static instance: DatabaseConnection | null = null;
  private connection: Connection;

  private constructor(config: DbConfig) {
    // private constructor — cannot call new from outside
    this.connection = createConnection(config);
  }

  static getInstance(config: DbConfig): DatabaseConnection {
    if (!DatabaseConnection.instance) {
      DatabaseConnection.instance = new DatabaseConnection(config);
    }
    return DatabaseConnection.instance;
  }

  query<T>(sql: string, params?: unknown[]): Promise<T[]> {
    return this.connection.query(sql, params);
  }
}

// First call — creates the connection
const db1 = DatabaseConnection.getInstance(config);
// Second call — returns the same instance
const db2 = DatabaseConnection.getInstance(config);
console.log(db1 === db2); // true
```

### Why Singleton is often an anti-pattern

Singleton solves a real problem (one instance of an expensive resource), but creates three systemic problems:

```txt
1. Hidden dependency (DIP violation):
   Code calling DatabaseConnection.getInstance() depends directly
   on a concrete class without injection.
   → impossible to swap in tests without monkey-patching

2. Global mutable state:
   Any part of the code can change the Singleton's state —
   exactly what makes code unpredictable and hard to test
   ("test A modified Singleton, test B failed unexpectedly")

3. SRP violation:
   Singleton manages both its business logic and its own lifecycle
   (when to create itself, how to store the instance)
```

```ts
// ❌ Hidden dependency — how do you test UserService
// without a real database connection?

class UserService {
  async findUser(id: string) {
    const db = DatabaseConnection.getInstance(config); // hidden dependency
    return db.query(`SELECT * FROM users WHERE id = $1`, [id]);
  }
}

// In a test there's no way to swap DatabaseConnection without mocking the module

// ✅ DI instead of Singleton — same "one instance" effect,
// but without global state and with full testability

class UserService {
  constructor(private readonly db: IDatabase) {} // dependency is explicit and swappable

  async findUser(id: string) {
    return this.db.query(`SELECT * FROM users WHERE id = $1`, [id]);
  }
}

// In a test:
const service = new UserService(new InMemoryDatabase());
// In production (via DI container or manually):
const service = new UserService(DatabaseConnection.getInstance(config));
```

### When Singleton is justified

```txt
Justified:
  - Logger (one process → one output stream)
  - Configuration loaded once from env
  - In-memory cache (Map/LRU) when a single shared cache is needed
  - The DI container itself (an IoC container is a Singleton)

NOT justified:
  - Database connection (use a connection pool via DI)
  - HTTP client (inject with the needed configuration via DI)
  - Any class you want to mock in tests
```

### Singleton in Node.js via modules (more practical than a class)

```ts
// config.ts — the module is cached by Node.js require/import,
// so the object is created exactly once without the pattern

const config = {
  db: {
    host: process.env.DB_HOST ?? 'localhost',
    port: Number(process.env.DB_PORT ?? 5432),
  },
  jwt: {
    secret: process.env.JWT_SECRET!,
    expiresIn: '7d',
  },
} as const;

export { config };

// Anywhere configuration is needed — import the same object:
import { config } from './config';
// This is the idiomatic "Singleton" in Node.js — no class, no getInstance
```

---

## Factory Method

> Defines an interface for creating an object, but lets subclasses (or specific functions) decide which class to instantiate.

Factory Method is not necessarily a method in a subclass (as in GoF). In TypeScript/JavaScript it more commonly appears as a **function or static method** that hides the details of creation.

### Example: logger with different transports

```ts
// Without Factory Method — the consumer knows the configuration details of each transport
const logger = new WinstonLogger({
  transports: [
    new winston.transports.Console({ format: winston.format.colorize() }),
    new winston.transports.File({ filename: 'error.log', level: 'error' }),
  ],
});
```

```ts
// ✅ Factory Method hides configuration details

interface Logger {
  info(message: string, meta?: object): void;
  error(message: string, error?: Error): void;
}

function createLogger(env: 'development' | 'production' | 'test'): Logger {
  if (env === 'test') {
    return new SilentLogger(); // doesn't write to stdout during tests
  }

  if (env === 'development') {
    return new ConsoleLogger({ colors: true, prettyPrint: true });
  }

  // production
  return new StructuredLogger({
    destination: process.env.LOG_DESTINATION ?? 'stdout',
    level: 'info',
  });
}

// The consumer doesn't know which specific Logger was created
const logger = createLogger(process.env.NODE_ENV as 'development');
logger.info('Server started');
```

### Real-world context (NestJS)

```ts
// NestJS useFactory — this is Factory Method inside the DI container:
// the module describes HOW to create a provider, not creating it itself

@Module({
  providers: [
    {
      provide: 'DATABASE',
      useFactory: async (config: ConfigService): Promise<DataSource> => {
        const dataSource = new DataSource({
          type: 'postgres',
          host: config.get('DB_HOST'),
          // ...
        });
        await dataSource.initialize();
        return dataSource;
      },
      inject: [ConfigService],
    },
  ],
})
export class DatabaseModule {}
```

### Real-world context (React)

```tsx
// Factory for creating notification components by type
type NotificationType = 'success' | 'error' | 'warning' | 'info';

function createNotification(type: NotificationType, message: string): React.ReactElement {
  const components: Record<NotificationType, React.FC<{ message: string }>> = {
    success: SuccessToast,
    error: ErrorToast,
    warning: WarningToast,
    info: InfoToast,
  };
  const Component = components[type];
  return <Component message={message} />;
}
```

---

## Abstract Factory

> Provides an interface for creating **families** of related objects without specifying their concrete classes.

The key word is **family**: when you need to create multiple objects that must be consistent with each other (one UI theme, one payment system, one cloud provider).

### Example: UI components for different themes

```ts
// Interfaces for each component type
interface Button {
  render(): string;
}

interface Input {
  render(): string;
}

// Abstract factory — contract for the family
interface UIComponentFactory {
  createButton(label: string): Button;
  createInput(placeholder: string): Input;
}

// Concrete factory for Material UI
class MaterialUIFactory implements UIComponentFactory {
  createButton(label: string): Button {
    return { render: () => `<MuiButton variant="contained">${label}</MuiButton>` };
  }
  createInput(placeholder: string): Input {
    return { render: () => `<MuiTextField placeholder="${placeholder}" />` };
  }
}

// Concrete factory for Ant Design
class AntDesignFactory implements UIComponentFactory {
  createButton(label: string): Button {
    return { render: () => `<AntButton type="primary">${label}</AntButton>` };
  }
  createInput(placeholder: string): Input {
    return { render: () => `<AntInput placeholder="${placeholder}" />` };
  }
}

// The consumer only works with the abstract factory
function renderLoginForm(factory: UIComponentFactory): string {
  const button = factory.createButton('Sign In');
  const input = factory.createInput('Enter email');
  return `<form>${input.render()}${button.render()}</form>`;
}

// Changing the theme — change the factory in one place:
const form = renderLoginForm(new MaterialUIFactory());
```

### Real-world context: cloud providers

```ts
// Abstract Factory for cloud operations — one interface, two providers

interface StorageService {
  upload(key: string, data: Buffer): Promise<string>;
  download(key: string): Promise<Buffer>;
}

interface QueueService {
  publish(topic: string, message: unknown): Promise<void>;
  subscribe(topic: string, handler: (msg: unknown) => void): void;
}

interface CloudFactory {
  createStorage(): StorageService;
  createQueue(): QueueService;
}

class AwsFactory implements CloudFactory {
  createStorage(): StorageService { return new S3StorageService(); }
  createQueue(): QueueService { return new SqsQueueService(); }
}

class GcpFactory implements CloudFactory {
  createStorage(): StorageService { return new GcsStorageService(); }
  createQueue(): QueueService { return new PubSubQueueService(); }
}

// Migrating from AWS to GCP — change one line:
const cloud: CloudFactory = process.env.CLOUD === 'gcp'
  ? new GcpFactory()
  : new AwsFactory();
```

### Factory Method vs Abstract Factory

```txt
Factory Method:
  - Creates ONE type of object
  - Often — a function or static method
  - Hides configuration details of a single object

Abstract Factory:
  - Creates a FAMILY of related objects
  - Groups several Factory Methods
  - Guarantees consistency between objects of the same family
```

---

## Builder

> Separates the construction of a complex object into a step-by-step process, allowing different representations of the same object to be created.

Builder is needed when an object's constructor takes many parameters, some of which are optional, and parameter combinations are variable.

### The "telescoping constructor" problem

```ts
// ❌ Constructor with 8 parameters — the call is unreadable,
// easy to mix up the order of arguments

const query = new DatabaseQuery(
  'users',           // tableName
  ['id', 'email'],   // columns
  { role: 'admin' }, // where
  'created_at',      // orderBy
  'DESC',            // orderDirection
  10,                // limit
  0,                 // offset
  true               // includeDeleted
);
// What does true mean? Why is 'DESC' the third argument?
```

```ts
// ✅ Builder — readable chainable API, each step is named

class DatabaseQueryBuilder {
  private tableName = '';
  private columns: string[] = ['*'];
  private conditions: Record<string, unknown> = {};
  private orderByColumn = 'id';
  private orderDirection: 'ASC' | 'DESC' = 'ASC';
  private limitValue = 100;
  private offsetValue = 0;
  private withDeleted = false;

  from(table: string): this {
    this.tableName = table;
    return this;
  }

  select(...columns: string[]): this {
    this.columns = columns;
    return this;
  }

  where(conditions: Record<string, unknown>): this {
    this.conditions = conditions;
    return this;
  }

  orderBy(column: string, direction: 'ASC' | 'DESC' = 'ASC'): this {
    this.orderByColumn = column;
    this.orderDirection = direction;
    return this;
  }

  limit(n: number): this {
    this.limitValue = n;
    return this;
  }

  offset(n: number): this {
    this.offsetValue = n;
    return this;
  }

  includeSoftDeleted(): this {
    this.withDeleted = true;
    return this;
  }

  build(): CompiledQuery {
    if (!this.tableName) throw new Error('Table name is required');
    return {
      sql: this.compile(),
      params: Object.values(this.conditions),
    };
  }

  private compile(): string {
    const cols = this.columns.join(', ');
    let sql = `SELECT ${cols} FROM ${this.tableName}`;
    if (!this.withDeleted) sql += ` WHERE deleted_at IS NULL`;
    const keys = Object.keys(this.conditions);
    if (keys.length) {
      const whereClauses = keys.map((k, i) => `${k} = $${i + 1}`).join(' AND ');
      sql += ` AND ${whereClauses}`;
    }
    sql += ` ORDER BY ${this.orderByColumn} ${this.orderDirection}`;
    sql += ` LIMIT ${this.limitValue} OFFSET ${this.offsetValue}`;
    return sql;
  }
}

// Readable, each step is self-documenting:
const query = new DatabaseQueryBuilder()
  .from('users')
  .select('id', 'email')
  .where({ role: 'admin' })
  .orderBy('created_at', 'DESC')
  .limit(10)
  .offset(0)
  .build();
```

### Builder in real libraries

```ts
// Knex.js — a typical Builder for SQL queries:
const users = await knex('users')
  .select('id', 'email')
  .where({ role: 'admin' })
  .orderBy('created_at', 'desc')
  .limit(10);

// Zod — a Builder for validation schemas:
const UserSchema = z.object({
  email: z.string().email().toLowerCase(),
  age: z.number().int().min(18).max(120),
  role: z.enum(['admin', 'user']).default('user'),
});

// TypeORM QueryBuilder:
const users = await userRepository
  .createQueryBuilder('user')
  .where('user.role = :role', { role: 'admin' })
  .orderBy('user.createdAt', 'DESC')
  .take(10)
  .getMany();
```

### Director — the optional part of Builder

```ts
// Director encapsulates typical object construction scenarios.
// Useful when the same set of steps repeats across multiple places.

class QueryDirector {
  constructor(private readonly builder: DatabaseQueryBuilder) {}

  buildAdminListQuery(page: number, pageSize: number): CompiledQuery {
    return this.builder
      .from('users')
      .select('id', 'email', 'role', 'created_at')
      .where({ role: 'admin' })
      .orderBy('created_at', 'DESC')
      .limit(pageSize)
      .offset(page * pageSize)
      .build();
  }
}
```

---

## Prototype

> Creates new objects by copying (cloning) an existing prototype object.

Prototype is needed when object creation is expensive (requires complex initialization) and the needed objects differ only slightly.

### Basic implementation

```ts
interface Cloneable<T> {
  clone(): T;
}

class EmailTemplate implements Cloneable<EmailTemplate> {
  constructor(
    public subject: string,
    public body: string,
    public from: string,
    private readonly compiledRegex: RegExp, // expensive to create each time
  ) {}

  clone(): EmailTemplate {
    // shallow copy is sufficient — compiledRegex is immutable
    return new EmailTemplate(
      this.subject,
      this.body,
      this.from,
      this.compiledRegex,
    );
  }

  withSubject(subject: string): EmailTemplate {
    const copy = this.clone();
    copy.subject = subject;
    return copy;
  }

  withBody(body: string): EmailTemplate {
    const copy = this.clone();
    copy.body = body;
    return copy;
  }
}

// Base template created once (expensive initialization):
const baseTemplate = new EmailTemplate(
  'Notification',
  'Hello {{name}}',
  'noreply@example.com',
  /\{\{(\w+)\}\}/g,
);

// Variations — cheap, via cloning:
const welcomeTemplate = baseTemplate.withSubject('Welcome!').withBody('Hi {{name}}, welcome!');
const resetTemplate = baseTemplate.withSubject('Password Reset').withBody('Reset link: {{link}}');
```

### Prototype in JavaScript/TypeScript — built-in tools

```ts
// In JS/TS, Prototype is often implemented via Object.assign / spread,
// without an explicit clone() method:

// Shallow clone via spread:
const original = { user: { id: 1, name: 'Alice' }, role: 'admin' };
const copy = { ...original }; // shallow — original.user === copy.user

// Deep clone (Node.js 17+, modern browsers):
const deepCopy = structuredClone(original); // full copy, no shared references

// The "immutable update" pattern in Redux/Zustand is Prototype:
const nextState = { ...state, count: state.count + 1 };

// Immer implements Prototype under the hood (copy-on-write):
const nextState = produce(state, draft => {
  draft.user.name = 'Bob'; // immer clones only the changed branches
});
```

### Real-world context (testing)

```ts
// Prototype as "test fixture" — base object + targeted changes for each test

const baseUser: User = {
  id: '1',
  email: 'test@example.com',
  role: 'user',
  isActive: true,
  createdAt: new Date('2024-01-01'),
};

// Each test — a clone with minimal changes:
const adminUser = { ...baseUser, role: 'admin' as const };
const inactiveUser = { ...baseUser, isActive: false };
const newUser = { ...baseUser, createdAt: new Date() };
```

### When Prototype is needed and when it is not

```txt
Needed:
  - Object creation requires complex initialization (regex compilation,
    schema parsing, connection establishment)
  - Many similar objects with small differences are needed
  - Immutable updates (Redux, Immer)

Not needed (just use new):
  - Objects are lightweight, initialization is cheap
  - No variability — all objects are identical
```

---

## Comparison of creational patterns

```txt
Pattern          Problem solved                 When to use
────────────────────────────────────────────────────────────────────
Singleton        One instance for the           Logger, config, cache
                 entire application             (but prefer DI)

Factory Method   Creating one object            Logger by env,
                 with variable implementation   component by type

Abstract Factory Creating a family of           UI theme, cloud
                 consistent objects             provider

Builder          Step-by-step construction      SQL query, HTTP request,
                 of a complex object            config with >4 params

Prototype        Cloning an object              Expensive initialization,
                 as the basis for variations   test fixtures, immutability
```

## Common interview traps

- **"Singleton is a good pattern for shared resources"** — without mentioning the problems: hidden dependencies, global state, testability issues. The correct answer includes "but prefer DI + one instance in the container."

- **Confusing Factory Method and Abstract Factory** — Factory Method creates one object, Abstract Factory creates a family of related ones. The key phrase for Abstract Factory is "family consistency."

- **Builder always == "GoF Builder pattern"** — in TypeScript, Builder more commonly appears as a chainable API (Knex, Zod, TypeORM), not the classical GoF version with a separate Director. Both are valid; understanding the goal matters more than the specific form.

- **"Prototype is the JavaScript prototype chain"** — these are different things. The Prototype pattern is about cloning objects. JavaScript's prototype chain is about delegating property lookup along `__proto__`. Make this distinction explicit in an interview.

- **Not mentioning DI as a Singleton alternative** — Singleton solves "one instance," but a DI container solves the same problem without global state. Knowing this alternative signals understanding of practice, not just theory.

- **Builder without validation in `build()`** — a proper Builder should validate required parameters and invariants in the `build()` method, not in each setter. This is commonly missed when implementing on the spot in an interview.
