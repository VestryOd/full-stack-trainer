# Clean Architecture

> **Scope note:** Clean Architecture is about organizing code within a single service so that the core business logic is independent of frameworks, databases, and delivery mechanisms. How multiple services coordinate with each other is a System Design concern.

## The problem Clean Architecture solves — more precisely than layered architecture

Layered architecture (article 01) tells you *what layers to have*. Clean Architecture tells you *which direction dependencies must point* between those layers — and makes that rule explicit and non-negotiable.

The problem it's specifically solving: **your business logic depends on things that change for external reasons**.

```ts
// ❌ This service "knows" it's running on Express and using Prisma
// If you switch to Fastify, or Prisma → raw SQL, you must touch business logic

import { Request, Response } from 'express';     // framework import
import { PrismaClient } from '@prisma/client';   // database import

const prisma = new PrismaClient();

export async function createOrder(req: Request, res: Response) {
  const user = await prisma.user.findUnique({ where: { id: req.user.id } });
  if (!user || user.creditLimit < req.body.total) {
    return res.status(400).json({ error: 'Insufficient credit' });
  }
  const order = await prisma.order.create({ data: { userId: user.id, total: req.body.total } });
  res.status(201).json(order);
}
```

The business rule ("user can't exceed their credit limit") is buried inside a function that imports `express` and `prisma`. You can't test that rule without spinning up HTTP and a database. You can't reuse it from a CLI tool or a cron job. Every time Prisma releases a breaking change, you're hunting for business logic inside framework-coupled files.

Clean Architecture's answer: **the core business logic must not import from, or know about, anything that lives in an outer layer**.

## The four rings — and the Dependency Rule

Robert C. Martin (known as "Uncle Bob") described Clean Architecture as concentric rings. The defining rule — the **Dependency Rule** — is:

> **Source code dependencies must point inward only. Nothing in an inner ring can know about anything in an outer ring.**

```txt
┌─────────────────────────────────────────────────────────┐
│                   4. Frameworks & Drivers                │
│         (Express, NestJS, Prisma, HTTP, CLI,            │
│          databases, external services, UI)              │
│  ┌──────────────────────────────────────────────────┐   │
│  │              3. Interface Adapters                │   │
│  │     (Controllers, Presenters, Gateways,          │   │
│  │      Repository implementations, DTO mappers)    │   │
│  │  ┌───────────────────────────────────────────┐   │   │
│  │  │           2. Use Cases                     │   │   │
│  │  │   (Application business rules,             │   │   │
│  │  │    orchestration logic)                    │   │   │
│  │  │  ┌──────────────────────────────────────┐  │   │   │
│  │  │  │          1. Entities                  │  │   │   │
│  │  │  │   (Enterprise business rules,         │  │   │   │
│  │  │  │    domain objects, core types)        │  │   │   │
│  │  │  └──────────────────────────────────────┘  │   │   │
│  │  └───────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘

Dependencies: always point ──► inward
              NEVER point outward
```

### Ring 1: Entities

The innermost ring. Pure business objects and rules that exist regardless of any application context. No framework imports. No database imports. No HTTP concepts.

```ts
// entities/order.ts — pure TypeScript, zero dependencies
export interface Order {
  id: string;
  userId: string;
  total: number;
  status: 'pending' | 'confirmed' | 'cancelled';
  createdAt: Date;
}

// A business rule as a pure function — testable with no setup at all
export function canPlaceOrder(userCreditLimit: number, orderTotal: number): boolean {
  return userCreditLimit >= orderTotal;
}

export class InsufficientCreditError extends Error {
  constructor(available: number, required: number) {
    super(`Credit limit ${available} is insufficient for order total ${required}`);
    this.name = 'InsufficientCreditError';
  }
}
```

### Ring 2: Use Cases

Application-specific business rules. A Use Case (also called "Interactor") orchestrates Entities to carry out one specific business operation. It knows about Entities, but it does NOT know about HTTP, databases, or frameworks.

Crucially: Use Cases define **interfaces** for the data they need from the outside world — the repositories, external services, notifiers. These interfaces live *inside* the use case ring (inner layer), but their *implementations* live in the outer rings.

```ts
// use-cases/place-order.use-case.ts
// This file has ZERO imports from Express, Prisma, or any framework
import type { Order } from '../entities/order';
import { canPlaceOrder, InsufficientCreditError } from '../entities/order';

// The Use Case defines what it NEEDS — but not HOW it gets it
// These interfaces stay in the inner layer; implementations are in ring 3/4
export interface IUserRepository {
  findById(id: string): Promise<{ id: string; email: string; creditLimit: number } | null>;
}

export interface IOrderRepository {
  create(input: { userId: string; total: number }): Promise<Order>;
}

export interface INotificationService {
  sendOrderConfirmation(email: string, orderId: string): Promise<void>;
}

export interface PlaceOrderInput {
  userId: string;
  total: number;
}

// The Use Case class — pure orchestration, no framework, no DB
export class PlaceOrderUseCase {
  constructor(
    private userRepo: IUserRepository,
    private orderRepo: IOrderRepository,
    private notifier: INotificationService,
  ) {}

  async execute(input: PlaceOrderInput): Promise<Order> {
    const user = await this.userRepo.findById(input.userId);
    if (!user) throw new Error(`User ${input.userId} not found`);

    // Uses the entity-level business rule
    if (!canPlaceOrder(user.creditLimit, input.total)) {
      throw new InsufficientCreditError(user.creditLimit, input.total);
    }

    const order = await this.orderRepo.create({ userId: user.id, total: input.total });
    await this.notifier.sendOrderConfirmation(user.email, order.id);

    return order;
  }
}
```

Notice what's absent: no `import from 'express'`, no `import from '@prisma/client'`. The use case talks to *interfaces* it defines itself. It doesn't know — and doesn't care — whether the data comes from PostgreSQL, SQLite, or an in-memory map.

### Ring 3: Interface Adapters

This ring contains the code that translates between the use cases and the external world. Controllers, presenters, repository implementations, DTO (Data Transfer Object — a plain object used to pass data between layers) mappers.

```ts
// adapters/repositories/prisma-user.repository.ts
// Implements the interface defined in ring 2 — using Prisma (ring 4)
import type { IUserRepository } from '../../use-cases/place-order.use-case';
import { PrismaClient } from '@prisma/client';

export class PrismaUserRepository implements IUserRepository {
  constructor(private prisma: PrismaClient) {}

  async findById(id: string) {
    const user = await this.prisma.user.findUnique({ where: { id } });
    if (!user) return null;
    return { id: user.id, email: user.email, creditLimit: user.creditLimit };
  }
}
```

```ts
// adapters/repositories/prisma-order.repository.ts
import type { IOrderRepository } from '../../use-cases/place-order.use-case';
import type { Order } from '../../entities/order';
import { PrismaClient } from '@prisma/client';

export class PrismaOrderRepository implements IOrderRepository {
  constructor(private prisma: PrismaClient) {}

  async create(input: { userId: string; total: number }): Promise<Order> {
    const order = await this.prisma.order.create({
      data: { userId: input.userId, total: input.total, status: 'pending' },
    });
    return {
      id: order.id,
      userId: order.userId,
      total: order.total,
      status: order.status as Order['status'],
      createdAt: order.createdAt,
    };
  }
}
```

```ts
// adapters/controllers/orders.controller.ts
// Translates HTTP → use case input, use case output → HTTP response
import type { Request, Response } from 'express';
import type { PlaceOrderUseCase } from '../../use-cases/place-order.use-case';
import { InsufficientCreditError } from '../../entities/order';

export class OrdersController {
  constructor(private placeOrderUseCase: PlaceOrderUseCase) {}

  async create(req: Request, res: Response): Promise<void> {
    try {
      const order = await this.placeOrderUseCase.execute({
        userId: req.user!.id,
        total: Number(req.body.total),
      });
      res.status(201).json(order);
    } catch (err) {
      if (err instanceof InsufficientCreditError) {
        res.status(400).json({ error: err.message });
        return;
      }
      throw err;
    }
  }
}
```

### Ring 4: Frameworks & Drivers

The outermost ring. Express, NestJS, Prisma, Redis clients, external APIs, email providers. This ring changes most often (framework upgrades, database migrations, third-party API changes). The Dependency Rule ensures these changes never reach the inner rings.

```ts
// main.ts — wiring everything together (the Composition Root)
import express from 'express';
import { PrismaClient } from '@prisma/client';
import { PrismaUserRepository } from './adapters/repositories/prisma-user.repository';
import { PrismaOrderRepository } from './adapters/repositories/prisma-order.repository';
import { SendgridNotificationService } from './adapters/services/sendgrid-notification.service';
import { PlaceOrderUseCase } from './use-cases/place-order.use-case';
import { OrdersController } from './adapters/controllers/orders.controller';

const prisma = new PrismaClient();
const app = express();
app.use(express.json());

// Dependency injection — manually assembled here at the composition root
const userRepo = new PrismaUserRepository(prisma);
const orderRepo = new PrismaOrderRepository(prisma);
const notifier = new SendgridNotificationService(process.env.SENDGRID_KEY!);
const placeOrderUseCase = new PlaceOrderUseCase(userRepo, orderRepo, notifier);
const ordersController = new OrdersController(placeOrderUseCase);

app.post('/orders', (req, res) => ordersController.create(req, res));

app.listen(3000);
```

## The resulting file structure

```txt
src/
├── entities/                      ← ring 1: pure business objects
│   └── order.ts
├── use-cases/                     ← ring 2: use cases + their interfaces
│   └── place-order.use-case.ts
├── adapters/                      ← ring 3: translators
│   ├── controllers/
│   │   └── orders.controller.ts
│   ├── repositories/
│   │   ├── prisma-user.repository.ts
│   │   └── prisma-order.repository.ts
│   └── services/
│       └── sendgrid-notification.service.ts
└── main.ts                        ← ring 4: framework wiring
```

## Testing without a database or HTTP server

The Dependency Rule pays off immediately in tests:

```ts
// use-cases/place-order.use-case.test.ts
// No Prisma. No Express. No network. Runs in milliseconds.
import { PlaceOrderUseCase, InsufficientCreditError } from './place-order.use-case';

const mockUserRepo = {
  findById: jest.fn(),
};
const mockOrderRepo = {
  create: jest.fn(),
};
const mockNotifier = {
  sendOrderConfirmation: jest.fn(),
};

const useCase = new PlaceOrderUseCase(mockUserRepo, mockOrderRepo, mockNotifier);

beforeEach(() => jest.clearAllMocks());

test('places an order when credit is sufficient', async () => {
  mockUserRepo.findById.mockResolvedValue({ id: '1', email: 'a@b.com', creditLimit: 500 });
  mockOrderRepo.create.mockResolvedValue({ id: 'o1', userId: '1', total: 100, status: 'pending', createdAt: new Date() });
  mockNotifier.sendOrderConfirmation.mockResolvedValue(undefined);

  const order = await useCase.execute({ userId: '1', total: 100 });

  expect(order.status).toBe('pending');
  expect(mockNotifier.sendOrderConfirmation).toHaveBeenCalledWith('a@b.com', 'o1');
});

test('throws InsufficientCreditError when credit is exceeded', async () => {
  mockUserRepo.findById.mockResolvedValue({ id: '1', email: 'a@b.com', creditLimit: 50 });

  await expect(useCase.execute({ userId: '1', total: 100 }))
    .rejects.toBeInstanceOf(InsufficientCreditError);

  expect(mockOrderRepo.create).not.toHaveBeenCalled();
  expect(mockNotifier.sendOrderConfirmation).not.toHaveBeenCalled();
});
```

## Clean Architecture vs Layered Architecture — the key difference

Both organize code into layers. The crucial difference is what the Dependency Rule adds:

```txt
Layered Architecture:
  Presentation → Service → Repository
  Dependency direction: typically top-down
  But: the service CAN import from Express if the developer isn't careful
       ("just this once")

Clean Architecture:
  Outer rings (frameworks) → Inner rings (use cases, entities)
  Dependency direction: always inward, enforced by the interface abstraction
  Use Case defines an IRepository interface — it imports an interface, not a class
  The repository implementation (which imports Prisma) lives in an outer ring
  The use case cannot accidentally import Prisma — Prisma is not in its ring
```

The Dependency Rule is enforced through **Dependency Inversion**: the inner layer defines the interface (the "port"), the outer layer provides the implementation (the "adapter"). This is the same idea as Hexagonal Architecture (article 04) — different vocabulary, same principle.

## When Clean Architecture is worth the overhead

Clean Architecture has real costs: more files, more interfaces, more indirection. It's overkill for:
- A simple CRUD API with minimal business logic
- Prototype or MVP-stage projects where requirements change daily
- A team of one or two where the extra structure adds friction without payback

It pays off when:
- Business logic is complex and needs to be testable in isolation
- The team needs to swap infrastructure (e.g. migrate from PostgreSQL to MongoDB, or from REST to GraphQL) without touching business logic
- Multiple delivery mechanisms exist (HTTP API + CLI + background jobs that share the same use cases)
- The codebase is expected to live for years and be worked on by multiple teams

## Common interview traps

- **"Clean Architecture and Layered Architecture are the same thing"** — layered architecture gives you layers; Clean Architecture gives you the Dependency Rule: inner layers must never import from outer layers. You can have a three-layer app where the service imports from Express (violating the Dependency Rule) — that's layered architecture without the clean part.

- **"The use case layer is the same as the service layer"** — in practice they often overlap, but a "service" in layered architecture typically allows framework imports; a Use Case in Clean Architecture explicitly forbids them. The strict enforcement is the difference.

- **"Clean Architecture means I have to write an interface for every class"** — you write interfaces where the Dependency Rule would be violated without them: wherever an inner layer needs to talk to something in an outer layer (database, email, external API). Two classes in the same ring that are tightly coupled don't necessarily need an interface between them.

- **"Dependency Inversion means injecting dependencies through the constructor"** — that's Dependency Injection, which is a technique. Dependency Inversion (the "D" in SOLID) is a principle: high-level modules should not depend on low-level modules; both should depend on abstractions. Constructor injection is one way to achieve this, but the principle is about the direction of the abstraction, not the injection mechanism.

- **"Entities are database models"** — in Clean Architecture, entities are pure business objects with no ORM decorators, no `@Column`, no `@Entity`. The ORM model lives in the outermost ring (ring 4) or the adapter ring. The entity is what the business cares about; the ORM model is how data happens to be stored.

- **"Clean Architecture is always worth doing"** — Uncle Bob himself says you apply it where it brings value. A 200-line script doesn't need four rings. The pattern addresses the pain of large codebases where business logic gets entangled with framework details over time. Apply it proportionally.
