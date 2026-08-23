# Hexagonal Architecture (Ports and Adapters)

> **Scope note:** Like Clean Architecture, Hexagonal Architecture is about isolating the core of a single application from external dependencies. It is not about how services communicate with each other.

## The mental model — a hexagon with pluggable sides

Hexagonal Architecture (also called **Ports and Adapters**) was described by Alistair Cockburn in 2005. *Ports and Adapters* is the more descriptive name, and it is the one worth remembering. The word "hexagonal" carries no meaning. Cockburn used a hexagon because it has more sides than a rectangle, which makes it easier to draw multiple ports around it.

The central idea: the application has a **core** (its business logic) and a **boundary**. Everything outside the boundary is an external system: a database, an HTTP client, a message queue, a command-line interface (CLI), a test harness. The application talks to every external system through one of two things:

- A **Port** — an interface (a contract) defined by the application itself
- An **Adapter** — a concrete implementation of that interface that connects to a specific external system

```txt
             ┌───────────────────────────────┐
HTTP client ─│ Adapter (Express Controller)  │
             │               ↓               │
   REST API ─│ ──────────►  PORT             │
             │ (IOrderService)               │
             │               ↓               │
             │          APPLICATION          │
             │              CORE             │
             │               ↓               │
             │              PORT             │
             │ (IOrderRepository)  ◄──────── │── Adapter (Prisma)
             │               ↓               │
             │              PORT             │
             │ (INotificationService) ◄───── │── Adapter (Sendgrid)
             └───────────────────────────────┘
```

The core knows nothing about Express, Prisma, or Sendgrid. It only knows about the ports it defined. Swapping Sendgrid for Mailgun is a matter of writing a new adapter — the core is untouched.

## Ports — two kinds

Ports come in two directions, and understanding the direction is important:

### Driving ports (left side / primary ports)

A driving port is an interface through which an **external actor drives the application**. The actor (an HTTP client, a CLI, a test) calls into the application through this port. The adapter on the left side adapts the external actor's format to the port's interface.

```ts
// A driving port — the application says "here's how you can use me"
// Defined inside the application core; implemented by the application itself
export interface IPlaceOrderUseCase {
  execute(input: PlaceOrderInput): Promise<Order>;
}

// The driving adapter — translates HTTP request into the port's language
// Lives outside the core
export class HttpOrderAdapter {
  constructor(private useCase: IPlaceOrderUseCase) {}

  async handlePost(req: Request, res: Response): Promise<void> {
    const order = await this.useCase.execute({
      userId: req.user!.id,
      total: Number(req.body.total),
    });
    res.status(201).json(order);
  }
}
```

### Driven ports (right side / secondary ports)

A driven port is an interface through which **the application drives an external system**. The application says "I need something from the outside — here's the contract." The adapter on the right side implements that contract using a specific technology.

```ts
// A driven port — the application says "here's what I need from the outside"
// Defined inside the application core
export interface IOrderRepository {
  findById(id: string): Promise<Order | null>;
  save(order: Order): Promise<Order>;
}

export interface IEmailNotifier {
  sendConfirmation(email: string, orderId: string): Promise<void>;
}

// A driven adapter — implements the port using a specific technology
// Lives outside the core
export class PrismaOrderRepository implements IOrderRepository {
  constructor(private prisma: PrismaClient) {}

  async findById(id: string): Promise<Order | null> {
    const row = await this.prisma.order.findUnique({ where: { id } });
    return row ? mapToOrder(row) : null;
  }

  async save(order: Order): Promise<Order> {
    const row = await this.prisma.order.upsert({
      where: { id: order.id },
      create: mapToDb(order),
      update: mapToDb(order),
    });
    return mapToOrder(row);
  }
}
```

## The complete structure

```txt
src/
├── core/                          ← the hexagon itself
│   ├── domain/                    ← entities and business rules
│   │   └── order.ts
│   ├── ports/                     ← all port interfaces
│   │   ├── driving/               ← driving ports (inbound)
│   │   │   └── place-order.port.ts
│   │   └── driven/                ← driven ports (outbound)
│   │       ├── order-repository.port.ts
│   │       └── email-notifier.port.ts
│   └── use-cases/                 ← application logic
│       └── place-order.use-case.ts
│
└── adapters/                      ← everything outside the hexagon
    ├── driving/                   ← driving adapters (inbound)
    │   ├── http/
    │   │   └── orders.controller.ts
    │   └── cli/
    │       └── place-order.command.ts
    └── driven/                    ← driven adapters (outbound)
        ├── persistence/
        │   └── prisma-order.repository.ts
        ├── notification/
        │   └── sendgrid-email.notifier.ts
        └── in-memory/             ← test adapters, no I/O
            ├── in-memory-order.repository.ts
            └── fake-email.notifier.ts
```

The `in-memory/` adapters under `driven/` are a key insight: for tests, you don't mock — you provide a real (but in-memory) implementation of the driven port. This is cleaner than mocking because it forces the in-memory adapter to respect the interface contract.

```ts
// adapters/driven/in-memory/in-memory-order.repository.ts
// A real implementation of IOrderRepository using a Map — for tests
import type { IOrderRepository } from '../../../core/ports/driven/order-repository.port';
import type { Order } from '../../../core/domain/order';

export class InMemoryOrderRepository implements IOrderRepository {
  private store = new Map<string, Order>();

  async findById(id: string): Promise<Order | null> {
    return this.store.get(id) ?? null;
  }

  async save(order: Order): Promise<Order> {
    this.store.set(order.id, order);
    return order;
  }

  // Test helper — inspect state without going through the interface
  getAll(): Order[] {
    return Array.from(this.store.values());
  }
}
```

```ts
// use-cases/place-order.use-case.test.ts
// Uses in-memory adapters — no mocks, no stubs, real implementations
import { PlaceOrderUseCase } from '../core/use-cases/place-order.use-case';
import { InMemoryOrderRepository }
  from '../adapters/driven/in-memory/in-memory-order.repository';
import { FakeEmailNotifier } from '../adapters/driven/in-memory/fake-email.notifier';

const orderRepo = new InMemoryOrderRepository();
const emailNotifier = new FakeEmailNotifier();
const useCase = new PlaceOrderUseCase(orderRepo, emailNotifier);

test('saves order and sends confirmation', async () => {
  const order = await useCase.execute({ userId: 'u1', total: 150 });

  expect(orderRepo.getAll()).toHaveLength(1);
  expect(emailNotifier.getSentEmails()).toContainEqual(
    expect.objectContaining({ orderId: order.id })
  );
});
```

## The Anti-Corruption Layer (ACL)

The **Anti-Corruption Layer** (ACL) is a pattern that often appears alongside Hexagonal Architecture. It's a driven adapter with an extra job. It does not just translate the data format: it **protects your domain model from the terminology and concepts of an external system**.

The problem it solves: external APIs have their own vocabulary, data shapes, and concepts. Those may differ from your domain model, or actively harm it. Without an ACL, that external vocabulary leaks into your core.

```ts
// External payment API returns this shape — its own vocabulary, not yours
interface StripePaymentIntent {
  id: string;
  amount: number;          // in cents
  currency: string;
  status: 'requires_payment_method' | 'requires_confirmation' | 'succeeded' | 'canceled';
  metadata: Record<string, string>;
  created: number;         // Unix timestamp
}

// Your domain model — your vocabulary
export interface Payment {
  id: string;
  orderId: string;
  amountInCents: number;
  currency: string;
  status: 'pending' | 'completed' | 'failed';
  processedAt: Date;
}

// The ACL adapter — translates between the two worlds
// Protects the domain from Stripe's vocabulary leaking in
export class StripePaymentAdapter implements IPaymentGateway {
  constructor(private stripe: Stripe) {}

  async charge(orderId: string, amountInCents: number, currency: string): Promise<Payment> {
    const intent = await this.stripe.paymentIntents.create({
      amount: amountInCents,
      currency,
      metadata: { orderId },
    });

    // Anti-corruption: translate Stripe's status vocabulary → domain vocabulary
    return {
      id: intent.id,
      orderId,
      amountInCents: intent.amount,
      currency: intent.currency,
      status: this.mapStripeStatus(intent.status),
      processedAt: new Date(intent.created * 1000),
    };
  }

  private mapStripeStatus(stripeStatus: StripePaymentIntent['status']): Payment['status'] {
    switch (stripeStatus) {
      case 'succeeded': return 'completed';
      case 'canceled': return 'failed';
      default: return 'pending';
    }
  }
}
```

Without the ACL, your domain code might end up with `if (payment.status === 'requires_payment_method')` — a Stripe-specific string inside business logic. If you ever switch payment providers, that string must be hunted down across the entire codebase.

The ACL ensures that Stripe's concepts exist **only** inside the adapter. The rest of the application uses `'pending' | 'completed' | 'failed'` — its own, stable vocabulary.

## Hexagonal Architecture vs Clean Architecture — same problem, different vocabulary

These two architectures are frequently conflated, and for good reason: they solve the same core problem using the same mechanism (Dependency Inversion). The vocabulary is different, but the structure maps directly:

```txt
Clean Architecture         Hexagonal Architecture
─────────────────────────────────────────────────
Entities                ↔  Domain / Core
Use Cases               ↔  Application Core + driving ports
Interface Adapters      ↔  Adapters (both driving and driven)
Frameworks & Drivers    ↔  External systems that adapters connect to

Dependency Rule         ↔  Core knows only its own ports
                           Adapters know the core and the
                           external systems
```

The most meaningful practical difference is emphasis:

- **Clean Architecture** emphasizes the **rings and their direction** — the "don't cross this boundary" rule is about which ring a piece of code lives in
- **Hexagonal Architecture** emphasizes the **symmetry of ports**. Both sides of the application, inbound and outbound, are treated the same way: through interfaces defined by the core

In a real TypeScript project, applying either one results in nearly identical code. An interviewer may ask which one you use. The honest answer: you apply the Dependency Rule from Clean Architecture and organize it with the Ports and Adapters vocabulary from Hexagonal Architecture. The two reinforce each other.

## When to reach for Hexagonal Architecture specifically

The "ports and adapters" framing is particularly useful when:

1. **Multiple driving adapters exist** — the same application core is called by an HTTP server, a CLI tool, a test suite, and a background job runner. Each is a separate driving adapter on the left side of the hexagon.

2. **Multiple driven adapters exist** — the application needs a production Postgres repository and a fast in-memory repository for tests. It may also need a repository over CSV (comma-separated values) files for a data import script.

3. **External APIs need insulation** — you're calling a third-party API whose data model you don't control. An ACL adapter prevents their vocabulary from spreading through your domain.

4. **You need to swap infrastructure.** Migrating from Sendgrid to Amazon SES (Simple Email Service), or from PostgreSQL to DynamoDB, means writing a new driven adapter. The core doesn't change.

## Common interview traps

- **"Ports are the same as interfaces"** — a port is a specific *kind* of interface. It marks the boundary between the application core and the outside world, and the core itself defines it, not the external system. A `UserRepository` interface used internally within the service layer is just an interface. A `IOrderRepository` interface that the use case defines — expecting an outer adapter to implement — is a port.

- **"The ACL is just a data mapper"** — a data mapper translates field names and types. An ACL translates *concepts*: `'requires_payment_method'` → `'pending'` is not field renaming, it's a semantic translation between two domain vocabularies. The purpose of an ACL is to keep the external system's model of the world out of your own.

- **"Hexagonal and Clean Architecture are different and you should pick one"** — they're more like two descriptions of the same insight. Most production codebases that apply one will look identical to codebases applying the other, because both enforce the Dependency Rule through interface abstractions.

- **"Driving and driven ports work the same way"** — they don't. A driving port is an interface that the application core *implements*. The use case class is the one implementing it. A driven port is an interface *defined* by the application core but *implemented* by an outer adapter. The direction is reversed. Getting this wrong in an interview signals a superficial understanding of the pattern.

- **"I'll add the hexagonal structure later when the project gets bigger"** — the cost of adding it later is high. Every place that violated the boundary needs to be untangled. The structure is cheapest to add at the start when the codebase is small. That said, applying it to a 5-file CRUD (create, read, update, delete) app is genuinely overkill. Apply the pattern in proportion to the problem, rather than "always" or "never".
