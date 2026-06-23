# Layered Architecture

> **Scope note:** This article is about how to organize code *within* a single application or service. How multiple services talk to each other — service discovery, API gateways, load balancing — is a System Design concern, not covered here.

## The problem layered architecture solves

Imagine a codebase where an Express route handler queries the database directly, formats the response, applies business rules, and sends emails — all in the same function. This is not hypothetical; it's what unstructured codebases look like after a few months of moving fast.

```ts
// ❌ Everything mixed together — the reality of "just ship it" code
app.post('/orders', async (req, res) => {
  const user = await db.query('SELECT * FROM users WHERE id = $1', [req.user.id]);
  if (user.rows[0].creditLimit < req.body.total) {
    return res.status(400).json({ error: 'Insufficient credit' });
  }
  const order = await db.query(
    'INSERT INTO orders (user_id, total, status) VALUES ($1, $2, $3) RETURNING *',
    [req.user.id, req.body.total, 'pending'],
  );
  await sendgrid.send({ to: user.rows[0].email, subject: 'Order placed', text: '...' });
  res.json(order.rows[0]);
});
```

Problems with this approach:
- **Can't test the business rule** ("insufficient credit") without an HTTP request, a real database, and a real email service
- **Can't reuse the business rule** from a CLI script, a cron job, or a WebSocket handler — the logic is hardwired to HTTP
- **A database schema change** (renaming a column) requires hunting through route files to find all raw SQL
- **A new team member** can't understand where the "logic" is — it's everywhere

Layered architecture is the answer to all four problems at once.

## The three layers — and what belongs where

```txt
┌─────────────────────────────────────────────┐
│           Presentation Layer                 │  HTTP, WebSocket, CLI
│    (controllers, route handlers, DTOs)       │  Knows about req/res
└─────────────────────────┬───────────────────┘
                          │ calls
┌─────────────────────────▼───────────────────┐
│             Business Logic Layer             │  Pure logic, no HTTP
│    (services, domain objects, validators)    │  No framework imports
└─────────────────────────┬───────────────────┘
                          │ calls
┌─────────────────────────▼───────────────────┐
│           Data Access Layer (DAL)            │  DB, cache, external APIs
│    (repositories, ORM models, DB clients)    │  No business rules
└─────────────────────────────────────────────┘
```

**Presentation Layer** — translates between the outside world (HTTP requests, WebSocket messages, CLI arguments) and the application. It knows about `req`, `res`, HTTP status codes, headers. It does NOT contain business rules. Its job: validate input shape, call a service, format output.

**Business Logic Layer** — the heart of the application. Contains rules like "a user can't place an order if their credit limit is exceeded" or "an invoice must have at least one line item." It knows nothing about HTTP, databases, or email providers — it works with plain objects and interfaces.

**Data Access Layer (DAL)** — knows how to read and write data. SQL queries, ORM calls, Redis operations, calls to external APIs. It does NOT contain business rules. It translates between what the business layer asks for ("give me user 42") and how data is actually stored.

## The strict layering rule — and why it matters

The rule: **each layer may only call the layer directly below it.** The presentation layer calls the business layer. The business layer calls the data access layer. Nothing skips a layer or calls upward.

```txt
✅ Allowed:          ❌ Not allowed:
Presentation → Service   Presentation → Repository (skips service)
Service → Repository     Repository → Service (calls upward)
                         Service → req/res (leaks presentation)
```

Why strict? Because every violation reintroduces the original problem. A route handler that calls a repository directly means you have database logic in the presentation layer — you're back to testing business rules through HTTP.

## Practical file structure

```txt
src/
├── presentation/           (or: controllers/, routes/)
│   ├── orders.controller.ts
│   └── orders.dto.ts
├── services/               (business logic layer)
│   └── orders.service.ts
├── repositories/           (data access layer)
│   └── orders.repository.ts
└── domain/                 (optional: pure domain objects/types)
    └── order.ts
```

## The refactored example

```ts
// domain/order.ts — pure types, no framework
export interface Order {
  id: string;
  userId: string;
  total: number;
  status: 'pending' | 'confirmed' | 'cancelled';
  createdAt: Date;
}

export interface CreateOrderInput {
  userId: string;
  total: number;
}
```

```ts
// repositories/orders.repository.ts — data access only, no business rules
import { db } from '../db';
import type { Order, CreateOrderInput } from '../domain/order';

export class OrdersRepository {
  async findById(id: string): Promise<Order | null> {
    const row = await db.query('SELECT * FROM orders WHERE id = $1', [id]);
    return row.rows[0] ?? null;
  }

  async create(input: CreateOrderInput): Promise<Order> {
    const row = await db.query(
      'INSERT INTO orders (user_id, total, status) VALUES ($1, $2, $3) RETURNING *',
      [input.userId, input.total, 'pending'],
    );
    return row.rows[0];
  }
}
```

```ts
// repositories/users.repository.ts
import { db } from '../db';

export interface User {
  id: string;
  email: string;
  creditLimit: number;
}

export class UsersRepository {
  async findById(id: string): Promise<User | null> {
    const row = await db.query('SELECT * FROM users WHERE id = $1', [id]);
    return row.rows[0] ?? null;
  }
}
```

```ts
// services/orders.service.ts — business logic only
// Notice: no imports from express, no req/res, no raw SQL
import type { OrdersRepository } from '../repositories/orders.repository';
import type { UsersRepository } from '../repositories/users.repository';
import type { EmailService } from './email.service';
import type { Order, CreateOrderInput } from '../domain/order';

export class InsufficientCreditError extends Error {
  constructor(userId: string, required: number, available: number) {
    super(`User ${userId} needs ${required} credit but only has ${available}`);
    this.name = 'InsufficientCreditError';
  }
}

export class OrdersService {
  constructor(
    private ordersRepo: OrdersRepository,
    private usersRepo: UsersRepository,
    private emailService: EmailService,
  ) {}

  async createOrder(input: CreateOrderInput): Promise<Order> {
    const user = await this.usersRepo.findById(input.userId);
    if (!user) throw new Error(`User ${input.userId} not found`);

    // Business rule lives here — not in the route handler, not in the repository
    if (user.creditLimit < input.total) {
      throw new InsufficientCreditError(input.userId, input.total, user.creditLimit);
    }

    const order = await this.ordersRepo.create(input);

    // Notify — service calls another service, still no HTTP/framework
    await this.emailService.sendOrderConfirmation(user.email, order);

    return order;
  }
}
```

```ts
// presentation/orders.controller.ts — HTTP only, no business rules
import { Router, type Request, type Response } from 'express';
import { OrdersService, InsufficientCreditError } from '../services/orders.service';

export function createOrdersRouter(ordersService: OrdersService): Router {
  const router = Router();

  router.post('/', async (req: Request, res: Response) => {
    try {
      const order = await ordersService.createOrder({
        userId: req.user!.id,
        total: req.body.total,
      });
      res.status(201).json(order);
    } catch (err) {
      if (err instanceof InsufficientCreditError) {
        return res.status(400).json({ error: err.message });
      }
      throw err; // let the error middleware handle unexpected errors
    }
  });

  return router;
}
```

Now the business rule ("insufficient credit") is testable without HTTP:

```ts
// orders.service.test.ts — no HTTP, no database, no email sending
import { OrdersService, InsufficientCreditError } from './orders.service';

const mockOrdersRepo = { findById: jest.fn(), create: jest.fn() };
const mockUsersRepo = { findById: jest.fn() };
const mockEmailService = { sendOrderConfirmation: jest.fn() };

const service = new OrdersService(mockOrdersRepo, mockUsersRepo, mockEmailService);

test('throws InsufficientCreditError when credit limit is exceeded', async () => {
  mockUsersRepo.findById.mockResolvedValue({ id: '1', email: 'a@b.com', creditLimit: 50 });

  await expect(
    service.createOrder({ userId: '1', total: 100 })
  ).rejects.toBeInstanceOf(InsufficientCreditError);
});
```

## NestJS and layered architecture

NestJS enforces this structure by convention. The `@Controller` decorator marks the presentation layer; `@Injectable()` services are the business layer; repositories (often via TypeORM or Prisma service wrappers) are the data access layer.

```ts
// NestJS — the layering is enforced by the framework's DI container
@Controller('orders')
export class OrdersController {
  constructor(private readonly ordersService: OrdersService) {}

  @Post()
  create(@Body() dto: CreateOrderDto, @Request() req) {
    return this.ordersService.createOrder({ userId: req.user.id, total: dto.total });
  }
}

@Injectable()
export class OrdersService {
  constructor(private readonly ordersRepository: OrdersRepository) {}
  // business logic here
}

@Injectable()
export class OrdersRepository {
  constructor(private readonly prisma: PrismaService) {}
  // data access here
}
```

The NestJS `Module` acts as the wiring — it declares which providers exist and injects them.

## When layered architecture is the right choice

Layered architecture is the right default for most applications:
- Teams of 2–10 engineers on a single codebase
- Business logic that needs testing in isolation
- Applications that may need to swap out their database or delivery mechanism (HTTP → CLI → cron)

When it starts to show strain:
- Very complex domains where each "layer" becomes a fat class with dozens of methods — this is when Clean Architecture or Hexagonal Architecture (see articles 03 and 04) provide more granular organization
- Cross-cutting concerns (auditing, authorization, logging) that don't fit neatly into one layer

## Common interview traps

- **"The service layer is just a pass-through, it doesn't add value"** — this is the sign of under-extracted business logic. If your service literally does `return this.repo.findById(id)` for every method, your business rules have leaked into the repository or the controller. The service layer should contain decisions, validations, and orchestration.

- **"I put the database call directly in the controller to keep it simple"** — "simple now" means "painful to test and change later." The effort to extract a repository is minimal; the cost of bypassing it accumulates with every feature added.

- **"Repositories are only useful when you're planning to swap databases"** — this framing misses the main benefit: repositories make the service layer testable without a real database. The fact that you *could* swap PostgreSQL for MySQL is a side effect, not the primary reason.

- **"Business logic in the model/entity class is better than in a service"** — sometimes true (a `User.hasPermission()` method that checks properties is a good fit). The failure mode is when model methods start receiving database clients or HTTP objects as arguments — then you've dissolved the layer boundary inside the entity itself.

- **"Layered architecture is the same as Clean Architecture"** — layered architecture and Clean Architecture (article 03) solve related but distinct problems. Layered architecture organizes code into horizontal tiers; Clean Architecture adds the Dependency Rule (outer layers depend on inner layers, never the reverse) and defines which direction abstractions must point. You can have bad layered architecture where the service layer imports from Express directly; Clean Architecture explicitly forbids it.
