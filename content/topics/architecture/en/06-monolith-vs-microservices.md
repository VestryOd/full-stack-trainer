# Monolith vs Microservices

> **Scope note:** This article sits at the boundary between application architecture (articles 01–05) and system design. Unlike the previous articles, it covers decisions about how many deployable units to have — which is a system-level decision. It's included here because it directly follows from modular application design: understanding module boundaries prepares you to decide when (or whether) to split those modules into separate services.

## The spectrum — from one to many deployable units

"Monolith vs microservices" is often framed as a binary choice. It's actually a spectrum:

```txt
Big Ball of Mud → Layered Monolith → Modular Monolith → Service-Oriented → Microservices
                                                                  ↑
                                                  Most teams should aim here
                                                  before considering the right side
```

The decision isn't just about splitting services — it's about where your application sits on this spectrum and whether moving right is worth the cost at this point in the project's life.

## Monolith types

Not all monoliths are equal. The term "monolith" describes the deployment model (one deployable unit), not the internal quality.

### Big Ball of Mud

No intentional structure. Business logic, data access, HTTP handling — all mixed together. Fast to start, painful to maintain, impossible to test properly. This is what the patterns in articles 01–05 exist to prevent.

### Layered Monolith

A single deployable unit organized into layers (Presentation → Service → Repository). This is the most common production architecture for small-to-medium applications. It's what every NestJS or Express project becomes if you apply the patterns from this series.

```txt
One deployable: my-app.js / dist/
├── controllers/ (HTTP layer)
├── services/ (business logic)
├── repositories/ (data access)
└── domain/ (types and rules)

One database, one deployment pipeline, one log stream.
```

**Strengths:** simple to develop, simple to deploy, simple to debug. Transactions are easy — everything runs in the same process. Shared code is a direct import. No network latency between "services."

**Weaknesses:** cannot scale individual parts independently. The entire application must be deployed to change one route. A memory leak in one module crashes the whole app.

### Modular Monolith

A single deployable unit where internal modules are explicitly isolated — each module has a defined public API, and other modules cannot reach into its internals. This is the ideal stopping point for most applications before (if ever) going to microservices.

```txt
my-app/
├── modules/
│   ├── orders/
│   │   ├── index.ts          ← public API: what other modules CAN import
│   │   ├── orders.service.ts
│   │   ├── orders.repository.ts
│   │   └── domain/
│   ├── users/
│   │   ├── index.ts          ← public API
│   │   ├── users.service.ts
│   │   └── domain/
│   └── notifications/
│       ├── index.ts          ← public API
│       └── ...
└── main.ts
```

The key discipline: other modules can only import from `orders/index.ts`, never from `orders/orders.service.ts` directly. This mirrors the interface boundary a microservice would enforce — but without the operational cost.

```ts
// modules/orders/index.ts — explicit public API
export type { Order, OrderStatus } from './domain/order';
export { OrdersService } from './orders.service';
export { ORDER_REPOSITORY_TOKEN } from './orders.repository';
// NOT exported: internal implementation details

// modules/users/users.service.ts
// ✅ Allowed: import from the orders module's public API
import type { Order } from '../orders'; // resolves to orders/index.ts

// ❌ Forbidden: reaching into the module's internals
// import { PrismaOrderRepository } from '../orders/orders.repository';
```

A modular monolith is easier to test, easier to refactor, and — critically — easier to extract into a microservice later if you genuinely need to. The module boundary is already there; you're just adding a network call and separate deployment.

## Microservices

A **microservice** is an independently deployable service that owns one bounded context (a coherent set of business capabilities) and its own database.

```txt
API Gateway / Load Balancer
       │
       ├──► Orders Service (port 3001, owns orders_db)
       ├──► Users Service (port 3002, owns users_db)
       ├──► Notifications Service (port 3003, no persistent DB)
       └──► Inventory Service (port 3004, owns inventory_db)
```

The "owns its own database" rule is non-negotiable in a proper microservices architecture. If two services share a database, they're not independent — a schema migration in one breaks the other. In practice, services communicate by:

1. **Synchronous calls** — REST or gRPC. One service calls another and waits for a response.
2. **Asynchronous messaging** — Kafka, RabbitMQ, SQS. One service publishes an event; others subscribe.

### Synchronous example — HTTP between services

```ts
// orders-service: calls the users service to check credit
// src/services/orders.service.ts (inside the Orders microservice)
export class OrdersService {
  constructor(
    private orderRepository: IOrderRepository,
    private usersClient: IUsersServiceClient, // HTTP client to the Users service
  ) {}

  async placeOrder(userId: string, total: number): Promise<Order> {
    // Network call — can fail, can be slow, has latency
    const user = await this.usersClient.getUserById(userId);
    if (!user) throw new Error(`User ${userId} not found`);
    if (user.creditLimit < total) throw new InsufficientCreditError(user.creditLimit, total);

    return this.orderRepository.save({ ... });
  }
}
```

```ts
// The HTTP client wraps the network call and provides a typed interface
// src/clients/users-service.client.ts
export class UsersServiceClient implements IUsersServiceClient {
  private baseUrl = process.env.USERS_SERVICE_URL!;

  async getUserById(id: string): Promise<User | null> {
    const res = await fetch(`${this.baseUrl}/users/${id}`);
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`Users service error: ${res.status}`);
    return res.json();
  }
}
```

### Asynchronous example — event-driven communication

```ts
// orders-service: publishes an event after placing an order
// orders.service.ts (inside the Orders microservice)
async placeOrder(userId: string, total: number): Promise<Order> {
  const order = await this.orderRepository.save({ ... });

  // Fire-and-forget: publish event; notifications service will pick it up
  await this.eventBus.publish('order.placed', {
    orderId: order.id,
    userId,
    total,
  });

  return order;
}

// notifications-service: subscribes to the event independently
// handlers/order-placed.handler.ts (inside the Notifications microservice)
export class OrderPlacedHandler {
  async handle(event: OrderPlacedEvent): Promise<void> {
    const user = await this.usersClient.getUserById(event.userId);
    await this.emailService.sendConfirmation(user.email, event.orderId);
  }
}
```

## The trade-offs — honest comparison

```txt
┌───────────────────────┬──────────────────────────────┬────────────────────────────────────┐
│                       │      Monolith                │       Microservices                │
├───────────────────────┼──────────────────────────────┼────────────────────────────────────┤
│ Development speed     │ Fast — direct imports,       │ Slow — separate repos, contracts,  │
│                       │ one repo, one test suite     │ versioned APIs, integration tests  │
├───────────────────────┼──────────────────────────────┼────────────────────────────────────┤
│ Deployment            │ One pipeline, one artifact   │ N pipelines, N artifacts,          │
│                       │                              │ container orchestration (K8s)       │
├───────────────────────┼──────────────────────────────┼────────────────────────────────────┤
│ Operational           │ One log stream, one          │ Distributed tracing, centralized   │
│ complexity            │ metrics dashboard            │ logging, service mesh, N dashboards │
├───────────────────────┼──────────────────────────────┼────────────────────────────────────┤
│ Scaling               │ Scale the whole app          │ Scale only the bottleneck service  │
├───────────────────────┼──────────────────────────────┼────────────────────────────────────┤
│ Transactions          │ ACID — same DB, same process │ No ACID across services;           │
│                       │                              │ Saga pattern or eventual consistency│
├───────────────────────┼──────────────────────────────┼────────────────────────────────────┤
│ Fault isolation       │ One failure can crash all    │ Failures contained to one service  │
├───────────────────────┼──────────────────────────────┼────────────────────────────────────┤
│ Technology choice     │ One language, one runtime    │ Each service can use different     │
│                       │                              │ language/database (rarely worth it)│
├───────────────────────┼──────────────────────────────┼────────────────────────────────────┤
│ Team autonomy         │ Everyone works in same repo; │ Teams deploy independently;        │
│                       │ coordination needed          │ less cross-team coordination       │
└───────────────────────┴──────────────────────────────┴────────────────────────────────────┘
```

The technology-choice freedom ("each service can use a different language") is frequently cited as a microservices benefit. In practice, heterogeneous tech stacks multiply operational burden with little return. Most companies standardize on 1–2 languages regardless.

## Conway's Law — why org structure drives architecture

**Conway's Law** (Melvin Conway, 1967):
> "Organizations which design systems are constrained to produce designs which are copies of the communication structures of those organizations."

In plain terms: if three teams own the system, the system will have three major components. If one team owns everything, the system will be a monolith. The architecture follows the team boundary, not the other way around.

This has a practical implication: microservices make sense when you have multiple independent teams that should be able to deploy without coordinating with each other. For a single team (or a small startup), microservices add coordination overhead without providing the autonomy benefit — there's nothing to be autonomous from.

The **Inverse Conway Maneuver** — deliberately structuring your teams to match the desired architecture — is a real strategy: if you want microservices, first organize teams around service boundaries, then let the architecture follow.

## The Strangler Fig Pattern — migrating from monolith to microservices

The **Strangler Fig Pattern** (named after a type of fig tree that grows around a host tree and eventually replaces it) is the recommended way to migrate an existing monolith to microservices incrementally.

```txt
Phase 1: Monolith handles everything
         [Client] → [Monolith]

Phase 2: Proxy/Gateway introduced, one capability extracted
         [Client] → [Gateway] → [Monolith] (most traffic)
                              → [New Service] (extracted capability)

Phase 3: More capabilities extracted
         [Client] → [Gateway] → [Users Service]
                              → [Orders Service]
                              → [Monolith] (shrinking — remaining capabilities)

Phase 4: Monolith is gone (or so small it's just a legacy adapter)
         [Client] → [Gateway] → [Users Service]
                              → [Orders Service]
                              → [Notifications Service]
```

The key: the client never changes its API. The gateway routes requests to wherever each capability now lives. The monolith shrinks gradually; the new services grow.

```ts
// Example: gateway routing during transition
// api-gateway/src/routes.ts
app.use('/users', proxy({ target: process.env.USERS_SERVICE_URL })); // extracted
app.use('/orders', proxy({ target: process.env.ORDERS_SERVICE_URL })); // extracted
app.use('/', proxy({ target: process.env.MONOLITH_URL })); // everything else still in monolith
```

## When to use what

**Start with a modular monolith when:**
- Team is fewer than ~15 engineers
- The bounded contexts (business domains) are not yet clear — requirements are still being discovered
- You don't have the operational infrastructure for multiple deployables (Kubernetes, monitoring, distributed tracing)
- The application is new — the cost of getting service boundaries wrong is enormous and changes in a monolith are cheap

**Consider microservices when:**
- Multiple independent teams need to deploy without blocking each other
- One specific part of the system has dramatically different scaling needs (e.g., a video processing service vs a user profile service)
- Regulatory or security requirements mandate data isolation at the infrastructure level
- You have a well-understood domain with clear, stable bounded contexts
- You have (or are willing to build) the platform: container orchestration, distributed tracing, centralized logging, API gateway, CI/CD per service

**Signs you've gone microservices too early:**
- Services constantly call each other synchronously (they belong together)
- Changes require deploying 3+ services simultaneously (you split along the wrong boundary)
- Every developer has to run 5+ services locally to test anything
- Transactions span multiple services and require saga patterns for operations that used to be a single DB transaction

## Common interview traps

- **"Microservices are always better for scalability"** — you can scale a modular monolith horizontally (run multiple instances behind a load balancer). Microservices let you scale *parts* independently — valuable only when parts have significantly different load profiles. Horizontal scaling of a monolith is often sufficient and vastly simpler.

- **"The difference between a modular monolith and microservices is just deployment"** — the deployment difference is real but secondary. The deeper difference is data ownership: modules in a monolith share a database (and therefore share the ability to do ACID transactions across modules). Microservices own their databases exclusively — you lose ACID guarantees across service boundaries. This changes how you handle consistency (eventual consistency, sagas, outbox pattern) and is a fundamental trade-off, not just a deployment detail.

- **"Start with microservices and avoid the migration pain later"** — this is the most expensive mistake in system design. Microservices require stable bounded contexts (knowing exactly what each service should own). At the start of a project, those boundaries are unknown. Getting them wrong in a microservices architecture is catastrophic — you've built a distributed monolith where changing one feature requires changing 4 services and 4 database schemas. Getting them wrong in a monolith means refactoring some files. Start with a well-structured monolith; extract services when the boundaries become clear and the pain of coordination becomes real.

- **"Conway's Law means you should structure code to match your team"** — Conway's Law is descriptive, not prescriptive. It describes what happens without intentional effort. The Inverse Conway Maneuver is the prescriptive response: if you want a certain architecture, deliberately structure teams to match it. But for small teams (under ~10 engineers), there's no team boundary to mirror in the architecture — the law doesn't apply.

- **"Microservices have better fault isolation"** — true in theory; complicated in practice. Yes, a crash in the Notifications service won't bring down the Orders service. But: synchronous calls between services create cascading failures (Orders calls Users synchronously; Users goes down; Orders now times out on every request). You need circuit breakers, timeouts, retries, and bulkheads (patterns from the resilience engineering toolkit) to actually achieve fault isolation. A monolith with proper error handling often has simpler fault characteristics than a microservices architecture with unhandled synchronous dependency failures.
