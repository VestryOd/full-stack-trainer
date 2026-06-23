# Repository and Service Patterns

> **Scope note:** These are code organization patterns for a single application. The Repository pattern abstracts data access; the Service Layer pattern abstracts business operations. They appear in virtually every layered or clean-architecture Node.js/NestJS project.

## Why these patterns exist — the problem they solve

Without explicit patterns, business logic and data access end up in the same place:

```ts
// ❌ A controller doing everything — no separation
app.post('/orders', async (req, res) => {
  const user = await prisma.user.findUnique({ where: { id: req.user.id } });
  if (!user || user.creditLimit < req.body.total) {
    return res.status(400).json({ error: 'Insufficient credit' });
  }
  const order = await prisma.order.create({
    data: { userId: user.id, total: req.body.total, status: 'pending' },
  });
  await sendgrid.send({
    to: user.email,
    subject: 'Order confirmed',
    text: `Order ${order.id} placed for $${order.total}`,
  });
  res.status(201).json(order);
});
```

Three problems:
1. **Untestable business rule** — "user can't exceed credit limit" can only be tested via HTTP + real database
2. **Scattered data access** — changing `prisma.order.create` to a raw SQL query means touching every controller
3. **Tangled responsibilities** — credit check, order creation, email sending, HTTP response — all in one function

The Repository and Service patterns give each concern its own place.

## The Repository Pattern

A **Repository** provides a collection-like interface to a domain entity. From the caller's perspective, it looks like a typed in-memory collection — you call `findById`, `save`, `delete`. The repository handles all the SQL, ORM queries, or API calls internally.

```txt
Controller / Use Case
        │
        │ calls (domain language: findById, save, findByUserId)
        ▼
  ┌─────────────┐
  │  Repository │  ← the interface, defined in the domain/service layer
  └──────┬──────┘
         │ implements
         ▼
  ┌────────────────────┐
  │  PrismaRepository  │  ← the implementation, knows about Prisma
  └────────────────────┘
         │
         ▼
     PostgreSQL
```

### Defining the interface

The interface lives in the business layer. It speaks domain language — no Prisma types, no SQL, no pagination cursor types from a specific ORM:

```ts
// repositories/order.repository.interface.ts
// This interface lives in the domain/service layer
// It speaks the language of the domain, not the database
export interface IOrderRepository {
  findById(id: string): Promise<Order | null>;
  findByUserId(userId: string): Promise<Order[]>;
  findPending(): Promise<Order[]>;
  save(order: Order): Promise<Order>;
  delete(id: string): Promise<void>;
}
```

### The concrete implementation

The Prisma implementation lives in the infrastructure/adapter layer. It translates between the domain model and the ORM's model:

```ts
// repositories/prisma-order.repository.ts
import type { IOrderRepository } from './order.repository.interface';
import type { Order } from '../domain/order';
import { PrismaClient } from '@prisma/client';

export class PrismaOrderRepository implements IOrderRepository {
  constructor(private prisma: PrismaClient) {}

  async findById(id: string): Promise<Order | null> {
    const row = await this.prisma.order.findUnique({ where: { id } });
    return row ? this.mapToDomain(row) : null;
  }

  async findByUserId(userId: string): Promise<Order[]> {
    const rows = await this.prisma.order.findMany({ where: { userId } });
    return rows.map(this.mapToDomain);
  }

  async findPending(): Promise<Order[]> {
    const rows = await this.prisma.order.findMany({
      where: { status: 'pending' },
    });
    return rows.map(this.mapToDomain);
  }

  async save(order: Order): Promise<Order> {
    const row = await this.prisma.order.upsert({
      where: { id: order.id },
      create: this.mapToDb(order),
      update: this.mapToDb(order),
    });
    return this.mapToDomain(row);
  }

  async delete(id: string): Promise<void> {
    await this.prisma.order.delete({ where: { id } });
  }

  // Private mappers keep Prisma's shape out of the domain
  private mapToDomain(row: PrismaOrder): Order {
    return {
      id: row.id,
      userId: row.userId,
      total: row.total,
      status: row.status as Order['status'],
      createdAt: row.createdAt,
    };
  }

  private mapToDb(order: Order): Omit<PrismaOrder, 'id'> {
    return {
      userId: order.userId,
      total: order.total,
      status: order.status,
      createdAt: order.createdAt,
    };
  }
}

// Prisma's generated type — lives only inside this file
type PrismaOrder = {
  id: string;
  userId: string;
  total: number;
  status: string;
  createdAt: Date;
};
```

### Generic repository — use with caution

A generic repository is tempting to reduce boilerplate:

```ts
// A generic base — abstracts the common CRUD operations
export interface IRepository<T, ID = string> {
  findById(id: ID): Promise<T | null>;
  save(entity: T): Promise<T>;
  delete(id: ID): Promise<void>;
}

// IOrderRepository extends the generic and adds order-specific queries
export interface IOrderRepository extends IRepository<Order> {
  findByUserId(userId: string): Promise<Order[]>;
  findPending(): Promise<Order[]>;
}
```

The risk: a generic `IRepository<T>` often leads to `findAll()` methods with complex filter/sort parameters that turn into a query builder — effectively re-implementing the ORM on top of the ORM. Keep the generic base thin (only `findById`, `save`, `delete`) and put all domain-specific queries on the concrete interface.

## The Service Layer Pattern

A **Service** (or **Service Layer**) is the place where business operations live. It orchestrates repositories and other dependencies to carry out a use case — without knowing about HTTP, WebSockets, or CLI.

```txt
Controller (HTTP)  CLI Command  Background Job
       │               │              │
       └───────────────┴──────────────┘
                       │ calls (business language: placeOrder, cancelOrder)
                       ▼
              ┌─────────────────┐
              │  OrdersService  │  ← contains business logic and orchestration
              └────────┬────────┘
                       │ uses
              ┌────────┴────────────────┐
              │                         │
    ┌─────────────────┐      ┌─────────────────────┐
    │ IOrderRepository│      │ INotificationService │
    └─────────────────┘      └─────────────────────┘
```

```ts
// services/orders.service.ts
// The Service Layer — orchestrates business logic
// Knows about repositories and other services; knows nothing about HTTP
import type { IOrderRepository } from '../repositories/order.repository.interface';
import type { IUserRepository } from '../repositories/user.repository.interface';
import type { INotificationService } from '../services/notification.service.interface';
import type { Order } from '../domain/order';

export class InsufficientCreditError extends Error {
  constructor(available: number, required: number) {
    super(`Credit limit ${available} is insufficient for order total ${required}`);
    this.name = 'InsufficientCreditError';
  }
}

export class OrderNotFoundError extends Error {
  constructor(id: string) {
    super(`Order ${id} not found`);
    this.name = 'OrderNotFoundError';
  }
}

export class OrdersService {
  constructor(
    private orderRepository: IOrderRepository,
    private userRepository: IUserRepository,
    private notificationService: INotificationService,
  ) {}

  async placeOrder(userId: string, total: number): Promise<Order> {
    const user = await this.userRepository.findById(userId);
    if (!user) throw new Error(`User ${userId} not found`);

    if (user.creditLimit < total) {
      throw new InsufficientCreditError(user.creditLimit, total);
    }

    const order = await this.orderRepository.save({
      id: crypto.randomUUID(),
      userId,
      total,
      status: 'pending',
      createdAt: new Date(),
    });

    await this.notificationService.sendOrderConfirmation(user.email, order.id);
    return order;
  }

  async cancelOrder(orderId: string, requestingUserId: string): Promise<Order> {
    const order = await this.orderRepository.findById(orderId);
    if (!order) throw new OrderNotFoundError(orderId);

    // Business rule: only the order owner can cancel
    if (order.userId !== requestingUserId) {
      throw new Error('Not authorized to cancel this order');
    }

    // Business rule: can only cancel pending orders
    if (order.status !== 'pending') {
      throw new Error(`Cannot cancel an order with status '${order.status}'`);
    }

    const cancelled = await this.orderRepository.save({ ...order, status: 'cancelled' });
    return cancelled;
  }

  async getOrdersByUser(userId: string): Promise<Order[]> {
    return this.orderRepository.findByUserId(userId);
  }
}
```

The controller now becomes thin — it handles HTTP-level concerns only:

```ts
// controllers/orders.controller.ts
// Thin: parses request, calls service, maps response
export class OrdersController {
  constructor(private ordersService: OrdersService) {}

  async create(req: Request, res: Response): Promise<void> {
    try {
      const order = await this.ordersService.placeOrder(
        req.user!.id,
        Number(req.body.total),
      );
      res.status(201).json(order);
    } catch (err) {
      if (err instanceof InsufficientCreditError) {
        res.status(400).json({ error: err.message });
        return;
      }
      throw err;
    }
  }

  async cancel(req: Request, res: Response): Promise<void> {
    try {
      const order = await this.ordersService.cancelOrder(
        req.params.id,
        req.user!.id,
      );
      res.json(order);
    } catch (err) {
      if (err instanceof OrderNotFoundError) {
        res.status(404).json({ error: err.message });
        return;
      }
      throw err;
    }
  }
}
```

## The complete file structure

```txt
src/
├── domain/
│   └── order.ts                    ← pure types and business rules
│
├── repositories/
│   ├── order.repository.interface.ts     ← IOrderRepository (interface)
│   ├── user.repository.interface.ts      ← IUserRepository (interface)
│   ├── prisma-order.repository.ts        ← implementation
│   └── prisma-user.repository.ts         ← implementation
│
├── services/
│   ├── notification.service.interface.ts ← INotificationService (interface)
│   ├── orders.service.ts                 ← business logic
│   └── sendgrid-notification.service.ts  ← implementation
│
├── controllers/
│   └── orders.controller.ts              ← HTTP translation layer
│
└── main.ts                               ← wiring (Composition Root)
```

## Testing each layer independently

The pattern pays off immediately in tests. Each layer is testable without its outer dependencies:

```ts
// services/orders.service.test.ts
// No HTTP, no Prisma, no Sendgrid — pure business logic test
import { OrdersService, InsufficientCreditError } from './orders.service';

const mockOrderRepo = {
  findById: jest.fn(),
  findByUserId: jest.fn(),
  findPending: jest.fn(),
  save: jest.fn(),
  delete: jest.fn(),
};

const mockUserRepo = {
  findById: jest.fn(),
  save: jest.fn(),
  delete: jest.fn(),
};

const mockNotifier = {
  sendOrderConfirmation: jest.fn(),
};

const service = new OrdersService(mockOrderRepo, mockUserRepo, mockNotifier);

beforeEach(() => jest.clearAllMocks());

test('places an order when credit is sufficient', async () => {
  mockUserRepo.findById.mockResolvedValue({ id: 'u1', email: 'user@test.com', creditLimit: 500 });
  mockOrderRepo.save.mockResolvedValue({ id: 'o1', userId: 'u1', total: 100, status: 'pending', createdAt: new Date() });
  mockNotifier.sendOrderConfirmation.mockResolvedValue(undefined);

  const order = await service.placeOrder('u1', 100);

  expect(order.status).toBe('pending');
  expect(mockNotifier.sendOrderConfirmation).toHaveBeenCalledWith('user@test.com', 'o1');
});

test('throws InsufficientCreditError when credit is exceeded', async () => {
  mockUserRepo.findById.mockResolvedValue({ id: 'u1', email: 'user@test.com', creditLimit: 50 });

  await expect(service.placeOrder('u1', 100)).rejects.toBeInstanceOf(InsufficientCreditError);
  expect(mockOrderRepo.save).not.toHaveBeenCalled();
});

test('throws when cancelling an order that belongs to another user', async () => {
  mockOrderRepo.findById.mockResolvedValue({
    id: 'o1', userId: 'u2', total: 100, status: 'pending', createdAt: new Date(),
  });

  await expect(service.cancelOrder('o1', 'u1')).rejects.toThrow('Not authorized');
});
```

## NestJS mapping — providers and dependency injection

In NestJS, services and repositories are **providers** decorated with `@Injectable()`. NestJS's IoC (Inversion of Control) container handles the construction and injection automatically:

```ts
// orders.module.ts
@Module({
  imports: [PrismaModule],
  controllers: [OrdersController],
  providers: [
    OrdersService,
    // Bind the interface token to the concrete implementation
    { provide: 'IOrderRepository', useClass: PrismaOrderRepository },
    { provide: 'IUserRepository', useClass: PrismaUserRepository },
    { provide: 'INotificationService', useClass: SendgridNotificationService },
  ],
})
export class OrdersModule {}

// orders.service.ts — NestJS style
@Injectable()
export class OrdersService {
  constructor(
    @Inject('IOrderRepository') private orderRepository: IOrderRepository,
    @Inject('IUserRepository') private userRepository: IUserRepository,
    @Inject('INotificationService') private notificationService: INotificationService,
  ) {}
  // ... same business logic
}
```

In smaller NestJS projects without Clean Architecture strictness, it's common to inject `PrismaOrderRepository` directly (without the interface abstraction). This is simpler and valid when you don't need to swap implementations or test without the database.

## Unit of Work — when multiple repositories must act together

A common problem: placing an order requires saving to `orders` and decrementing `users.creditLimit` atomically. If `orderRepository.save` succeeds but `userRepository.save` fails, the database is inconsistent.

The **Unit of Work (UoW)** pattern wraps multiple repository operations in a single transaction:

```ts
// unit-of-work.interface.ts
export interface IUnitOfWork {
  orderRepository: IOrderRepository;
  userRepository: IUserRepository;
  // Executes everything inside a single database transaction
  executeInTransaction<T>(work: (uow: IUnitOfWork) => Promise<T>): Promise<T>;
}

// prisma-unit-of-work.ts
export class PrismaUnitOfWork implements IUnitOfWork {
  constructor(private prisma: PrismaClient) {
    this.orderRepository = new PrismaOrderRepository(prisma);
    this.userRepository = new PrismaUserRepository(prisma);
  }

  orderRepository: IOrderRepository;
  userRepository: IUserRepository;

  async executeInTransaction<T>(work: (uow: IUnitOfWork) => Promise<T>): Promise<T> {
    return this.prisma.$transaction(async (tx) => {
      const txUow = new PrismaUnitOfWork(tx as PrismaClient);
      return work(txUow);
    });
  }
}

// Usage in the service
async placeOrder(userId: string, total: number): Promise<Order> {
  return this.uow.executeInTransaction(async (uow) => {
    const user = await uow.userRepository.findById(userId);
    if (!user || user.creditLimit < total) throw new InsufficientCreditError(...);

    const order = await uow.orderRepository.save({ ... });
    await uow.userRepository.save({ ...user, creditLimit: user.creditLimit - total });

    return order;
  });
}
```

Unit of Work is useful when you need transactional consistency across multiple aggregates. For simple cases where one repository's operations are self-contained, it's overkill.

## Common interview traps

- **"The repository is just a wrapper around Prisma"** — a repository that does `return prisma.order.findMany(filter)` and leaks Prisma's `WhereInput` types up to the service layer is not a proper repository — it's a thin proxy. The repository's value is in the abstraction: the service asks "give me all pending orders" in domain language; the repository translates that into however the data happens to be stored. If Prisma types appear in the service, the repository layer doesn't exist in any meaningful sense.

- **"Services should be stateless, so no fields allowed"** — it's not about fields vs no fields; it's about instance state that varies between calls. Constructor-injected dependencies (repositories, other services) are fine as fields — they're consistent across calls. Mutable state that tracks partial computation across calls (like `this.currentTransaction`) would be a problem in a singleton service.

- **"One service per entity"** — this leads to `UserService`, `OrderService`, `ProductService` each trying to own all operations on their entity, and then cross-cutting operations (place an order, which involves users AND orders AND inventory) not having a clear home. A better mental model: one service per business capability or use case group. `OrdersService` handles placing, cancelling, refunding orders — it can call `userRepository` directly. The entity boundary doesn't have to match the service boundary.

- **"Repositories should have a `findAll()` method"** — `findAll()` on a large table is a performance hazard. If the service needs to filter data, put a domain-meaningful method on the repository: `findPendingOlderThan(date: Date)` is better than returning everything and filtering in memory. If a generic filter is genuinely needed, pass a typed filter object rather than letting Prisma's `WhereInput` leak into the interface.

- **"The service layer is where you put everything that isn't routing"** — this describes what the service layer often becomes, not what it should be. Transaction management, caching, retry logic, rate limiting all tend to creep into services. When a service is doing business logic AND managing cache invalidation AND handling retry backoff, the next step is extracting those into separate concerns (a caching decorator, a retry middleware). The service's job is pure business orchestration.
