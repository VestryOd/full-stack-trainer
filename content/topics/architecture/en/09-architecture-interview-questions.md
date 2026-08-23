# Architecture Patterns — Interview Questions

## Middle

**What is layered architecture and what is the strict layering rule?**

Layered architecture organizes code into horizontal tiers. The usual three are Presentation (controllers and routes), Business Logic (services), and Data Access (repositories).

The **strict layering rule**: each layer may only call the layer immediately below it. A controller can call a service; a service can call a repository. A controller may not reach directly into a repository, and a repository may not call a service.

The rule keeps the direction of dependencies predictable. It also keeps each layer testable in isolation: you replace the layer below it with a fake.

---

**What should a controller do, and what should it not do?**

A controller handles HTTP-level concerns only. Its job is three steps:

- Parse the incoming request: path params, query params, body.
- Call a service with clean domain inputs.
- Map the service result or error to an HTTP response: status code, headers, JSON shape.

It should not contain business logic, direct database access, or decisions about what to do with the data beyond routing it. Take a controller that does `if (order.userId !== req.user.id) return res.status(403)...`. That is authorization logic leaking out of the service, and the service is where it can be tested without an HTTP stack.

---

**What is a DTO (Data Transfer Object)?**

A DTO (Data Transfer Object) is a plain object whose only purpose is to carry data between layers or across a boundary. It has no behaviour, no methods, and no business logic.

In NestJS, request DTOs (`CreateOrderDto`) are validated at the controller boundary and carry HTTP input into the service. Response DTOs (or view models) control what goes back to the client. The point is that the service doesn't hand a Prisma entity directly to `res.json()`. Internal data shapes are not automatically safe for external exposure.

---

**What is the Repository pattern? Where should the interface be defined?**

The Repository pattern provides a collection-like interface to a domain entity — `findById`, `findByUserId`, `save`, `delete` — hiding the underlying storage technology.

The key design detail: the interface (`IOrderRepository`) must be defined in the business/service layer, not in the infrastructure layer. If the interface lives next to the Prisma implementation, the service still depends on the infrastructure.

Defining the interface in the service layer reverses that direction: now the implementation depends on the business layer. This is what lets you substitute a different database, or an in-memory fake in tests, without touching the service.

---

**What is a Service Layer? What belongs in it and what does not?**

The Service Layer is where business operations live. It orchestrates repositories and external services to execute a use case: enforcing business rules, throwing typed errors, calling notifications. It knows nothing about HTTP (no `Request`, `Response`), WebSockets, or a CLI (command-line interface).

What does not belong in the service layer:

- HTTP status codes, JSON formatting and routing logic.
- Transaction retries — infrastructure decorators or middleware should handle those.
- Cache invalidation logic, which is a cross-cutting concern worth separating.

The test: if you can't call the service method from a unit test without spinning up an HTTP server, the service has leaked framework concerns.

---

**What is the Dependency Inversion Principle (DIP)?**

DIP is the Dependency Inversion Principle, the "D" in SOLID — Single Responsibility, Open-Closed, Liskov Substitution, Interface Segregation, Dependency Inversion. It states: high-level modules should not depend on low-level modules; both should depend on abstractions.

In practice, the `OrdersService` (high-level) should not import `PrismaOrderRepository` (low-level). It should import `IOrderRepository`, the abstraction. The concrete `PrismaOrderRepository` implements that interface.

DIP is the mechanism that makes Clean Architecture and Hexagonal Architecture work. Without it, inner layers would import outer layers and the Dependency Rule would break. Note that DIP is the principle; Dependency Injection is one technique for achieving it, through constructor injection or an IoC (inversion of control) container.

---

**What is the difference between MVC, MVP, and MVVM?**

All three separate business logic (the Model) from presentation (the View) by putting a mediator between them. MVC is Model-View-Controller, MVP is Model-View-Presenter, and MVVM is Model-View-ViewModel. What differs is the mediator's role and what it knows:

- **MVC**: the Controller knows both the Model and the View. It picks which view to render after updating the model. In server-side NestJS or Express, the "View" is JSON serialization.
- **MVP**: the View is passive. It exposes an interface (`IOrderView`), and the Presenter calls methods on it (`view.showError()`). The Presenter knows only that interface, never the concrete View.
- **MVVM**: the ViewModel holds observable state, and the View re-renders automatically when that state changes (data binding). This maps to React hooks: the hook is the ViewModel, the component is the View.

---

**What is Conway's Law and why does it matter when choosing between monolith and microservices?**

Conway's Law was formulated by Melvin Conway in 1967. "Organizations which design systems are constrained to produce designs which are copies of the communication structures of those organizations."

If three teams own a system, it will have three major components. If one team owns everything, the system will be a monolith — not because anyone decided so, but because the team's communication structure produces that shape.

The practical implication: microservices make sense when multiple independent teams need to deploy without coordinating. For a single team, microservices add coordination overhead with no corresponding autonomy benefit. The **Inverse Conway Maneuver** — deliberately structuring teams to match the desired architecture — is the proactive version of this principle.

---

**What is a Modular Monolith and how does it differ from an unstructured monolith?**

A Modular Monolith is a single deployable unit where internal modules are explicitly isolated. Each module has a public API — an `index.ts` that exports only what other modules should use. No direct access to another module's internals is allowed.

Compared to an unstructured (layered) monolith, both are one deployable. The difference is that the unstructured monolith has no explicit module boundary: any file can import any other file. In a Modular Monolith, cross-module access goes through `someModule/index.ts`, enforced by convention or by tooling such as ESLint import rules.

The practical benefit shows up later. If you need to extract a module as a microservice, the boundary already exists. You add a network call and a separate deployment, instead of untangling implicit dependencies.

---

**What is an ADR (Architecture Decision Record) and why should it live in the repository?**

An ADR (Architecture Decision Record) is a short document that records one architectural decision, its context at the time, and its consequences (positive, negative, neutral). The most common format, from Michael Nygard, has four sections: Status, Context, Decision, Consequences.

ADRs should live in `docs/adr/` in the repository, for three reasons:

- They're read when engineers work in the codebase, not when they're browsing Confluence.
- They're version-controlled alongside the code they describe.
- They're included in pull request reviews, at the moment the decision they document is being made.

The alternative — decision docs in a wiki — gradually diverges from the code, because neither is read at the same time.

---

**What does "separation of concerns" mean in practice?**

Separation of concerns means each unit of code has one reason to change. A controller changes when the HTTP API changes. A service changes when business rules change. A repository changes when the data access technology changes.

Concerns are mixed when changing the database forces you to touch the service, or when changing a business rule forces you to touch the controller. The test: list what could cause this file to change. If the list has items from more than one domain (HTTP, business logic, database), the file has mixed concerns.

---

## Senior

**What is Clean Architecture? How does its Dependency Rule differ from just having layers?**

Clean Architecture (Robert C. Martin) organizes code into concentric rings: Entities (innermost) → Use Cases → Interface Adapters → Frameworks & Drivers (outermost). The **Dependency Rule**: source code dependencies must point inward only. An inner ring may not import from an outer ring — ever.

This is stricter than layered architecture. In a layered monolith, nothing prevents a developer from adding `import { PrismaClient } from '@prisma/client'` into a service "just this once". Clean Architecture enforces the boundary structurally. Use cases define `IOrderRepository` and depend only on that interface. The Prisma implementation lives in an outer ring and implements it.

A use case in the inner ring literally cannot import Prisma, because Prisma is not in its ring. Layered architecture tells you what layers to have. Clean Architecture tells you that inner layers must never know outer layers exist, and enforces that through interface abstractions.

---

**What is the difference between Clean Architecture and Hexagonal Architecture?**

They solve the same problem with the same mechanism (Dependency Inversion), but they use different vocabulary.

- **Clean Architecture** uses **rings**: Entities, Use Cases, Interface Adapters, Frameworks. It emphasizes the direction in which the rings depend on each other.
- **Hexagonal Architecture** uses **ports** (interfaces defined by the core) and **adapters** (implementations). It emphasizes the symmetry between the two sides. On the inbound side, actors call into the application through driving ports. On the outbound side, the application calls infrastructure through driven ports.

The vocabulary maps directly: Use Cases ↔ Application Core + driving ports; Interface Adapters ↔ Adapters; Frameworks ↔ External systems. In practice, applying either one produces nearly identical TypeScript code.

The Hexagonal framing is more useful when there are multiple driving adapters — HTTP, a CLI and tests all calling the same core. The symmetry makes that explicit.

---

**What are primary and secondary ports in Hexagonal Architecture?**

A **port** is an interface defined by the application core. It is the contract for communicating across the hexagon's boundary.

**Primary (driving) ports** are how external actors call *into* the application. An HTTP controller calls `IPlaceOrderUseCase.execute()`, and a CLI command calls the same interface. The use case class *implements* this port.

**Secondary (driven) ports** are how the application calls *outward*: `IOrderRepository`, `IEmailNotifier`. These are defined in the core but *implemented* by outer adapters — a Prisma repository, a Sendgrid notifier.

The direction reverses between the two. For driving ports, the core implements the interface. For driven ports, the outer adapter implements the interface the core defined. A common interview mistake is treating them as symmetric — they're not.

---

**What is an ACL (Anti-Corruption Layer) and when do you need one?**

An ACL (Anti-Corruption Layer) is a driven adapter that does more than translate data format: it protects the domain model from an external system's vocabulary.

Without an ACL, Stripe's `'requires_payment_method'` status — or a legacy system's 10-character status codes — leaks into business logic. The domain then becomes littered with external-system concepts that don't match its own language.

An ACL translates concepts at the boundary: Stripe's `'succeeded'` → domain's `'completed'`, `'canceled'` → `'failed'`, everything else → `'pending'`. The domain only ever sees its own vocabulary.

You need an ACL in two cases:

- The external system's data model differs conceptually from your own, not just syntactically.
- Switching providers would otherwise mean hunting down external-system strings throughout business logic.

---

**What is the Unit of Work pattern and when do you actually need it?**

The Unit of Work (UoW) pattern wraps multiple repository operations in a single database transaction. Without it, if `orderRepository.save` succeeds but `userRepository.save` fails, the database is left inconsistent.

The UoW provides a shared transaction context to all repositories involved in one business operation. In Prisma that is `prisma.$transaction(async (tx) => { ... })`, where both repository instances receive the `tx` client.

You need a UoW when two or more aggregates (users, orders, inventory) must change atomically. You do not need it when a service method only writes to one table, or when Prisma's sequential transaction (`$transaction([op1, op2])`) suffices. The over-engineering case: creating a UoW abstraction before you have a cross-aggregate transaction use case.

---

**What is the Strangler Fig Pattern? When do you use it?**

The Strangler Fig Pattern is a strategy for migrating an existing monolith incrementally, without a big-bang rewrite. The target is usually microservices or a cleaner monolith.

An API Gateway or reverse proxy is placed in front of the monolith. New capabilities are implemented in the new target architecture and routed through the gateway. The monolith gradually shrinks as capabilities are extracted; the new system grows. The pattern is named after the fig tree that grows around a host tree and eventually replaces it.

Key property: the client API never changes, because the gateway handles routing transparently. Use it when migrating a large production system where a full rewrite would be too risky or take too long.

---

**What are the signs that microservices were introduced too early?**

Five concrete signs:

- **Chatty synchronous calls** — Service A calls B, B calls C, C calls D synchronously for a single user request. Services that must always be called together belong together.
- **Coordinated deployments** — every feature requires deploying 3+ services simultaneously, meaning the services aren't actually independent.
- **Shared database** — multiple services read and write the same tables. They're not microservices; they're a distributed monolith.
- **Local dev requires running 5+ services** — developers spend more time managing services than writing code.
- **Business rules spread across service boundaries** — the credit limit check lives in three services because nobody owns it. A monolith would have it in one place.

---

**How do ACID transactions work in a monolith vs microservices?**

In a monolith with one database, ACID (Atomicity, Consistency, Isolation, Durability) transactions are available natively. `BEGIN; UPDATE users ...; INSERT INTO orders ...; COMMIT` — either both succeed or both are rolled back.

In microservices, each service owns its database. No shared transaction coordinator spans two separate databases without significant overhead. 2PC (Two-Phase Commit) exists, but it is avoided because of its locking behaviour and its failure modes.

Two practical alternatives:

- **Saga pattern** — each service does its part. If a step fails, compensating transactions undo the previous steps.
- **Eventual consistency** — accept that data across services may be temporarily out of sync.

This is the biggest operational trade-off of microservices. You lose ACID across service boundaries and take on the complexity of distributed consistency.

---

**What is the Composition Root and why should there be exactly one?**

The Composition Root is the single place in the application where all dependencies are wired together — where concrete classes are instantiated and injected. In a plain Node.js app this is `main.ts`; in NestJS it's the module system.

Having exactly one Composition Root matters for three reasons:

- It's the only place where outer-layer types (Prisma, Sendgrid) are allowed to reference inner-layer types (use cases). All other code only knows about interfaces.
- Changing a dependency — swapping `PrismaOrderRepository` for a different implementation — means editing one file, not hunting through the codebase.
- The wiring is explicit and auditable.

A common antipattern is constructing dependencies inside business logic, such as `new PrismaClient()` inside a service constructor. That distributes the Composition Root across the codebase and makes testing and swapping impossible.

---

**When is it correct to skip the Repository interface abstraction?**

When all three of these are true:

- You will never swap the database implementation.
- You don't need to run tests without the database — integration tests against a real test database are acceptable.
- The project is small enough that the indirection adds friction without payback.

Take a NestJS CRUD (create, read, update, delete) API with Prisma, where the team has decided to always use Postgres and always run integration tests. Injecting `PrismaOrderRepository` directly into the service is legitimate there.

The interface abstraction pays back when you need in-memory fakes for fast unit tests, or when there's a realistic chance of changing the storage backend. The honest answer is: "it depends on the test strategy and the stability of the storage decision.""

---

**What is an anemic domain model?**

An anemic domain model is one where domain entities are plain data bags: structs with getters and setters but no behaviour. All the business logic lives in the service layer instead.

Example: `Order { id, userId, total, status }` with no methods, while `canPlaceOrder()`, `cancelOrder()` and `calculateDiscount()` all live in `OrdersService`. Martin Fowler called this an antipattern, because it inverts object-oriented design: behaviour that naturally belongs to the entity is stripped out of it.

The alternative is a rich domain model, where the entity has methods that enforce invariants — `order.cancel()` validates the status transition internally.

In practice, TypeScript and Node.js projects often default to anemic models. They are simpler with Prisma, whose entities are plain objects with no methods. The trade-off is acceptable for simple CRUD. For complex domain logic, rich models reduce the risk of an invariant being violated because someone forgot to call the validation in the service.

---

**How do you decide which layer should handle which errors?**

Layer-specific rule: each layer should throw errors in its own language, and the layer above should translate.

- Repositories throw storage errors: `EntityNotFoundError`, `UniqueConstraintError`, mapped from Prisma or database specifics.
- Services throw domain errors: `InsufficientCreditError`, `OrderAlreadyCancelledError`. These represent business rule violations.
- Controllers catch domain errors and map them to HTTP responses: `InsufficientCreditError` → 400, `EntityNotFoundError` → 404.

The goal: the service never uses HTTP status codes, and the controller never contains business logic. A `try/catch` in the service that catches a database error and re-throws a domain error is the translation layer. Uncaught exceptions bubble to a global error handler, which maps everything unknown to 500.

---

## Advanced

**A junior asks: "We always use Prisma, so why do we need the IOrderRepository interface?" What do you say?**

Three reasons, in increasing importance:

- **Testability without infrastructure.** With the interface, you can pass an `InMemoryOrderRepository` in unit tests, and they run in milliseconds without a running database. Without it, your use case constructor takes `PrismaOrderRepository`, which needs a real Prisma client, which needs a running database.
- **The interface is the design decision made visible.** Writing `IOrderRepository` forces you to define what the service actually needs from storage: `findById`, `save`. Without it, the service may call `prisma.order.findMany({ include: { user: true, ... } })` directly. That couples the service to Prisma's query shape.
- **The likelihood argument is about the present, not the future.** "We'll never swap the database" is an assumption, not a guarantee. The Dependency Rule is not primarily about protecting against a future migration. It is about keeping framework concepts out of business logic right now.

---

**An interviewer insists your design needs microservices. What do you argue?**

Start with questions, not objections:

- "What's the team size?"
- "How many independent deployment pipelines does the team currently manage?"
- "Are there components with dramatically different scaling requirements?"

Then make the cost explicit. Microservices require container orchestration, distributed tracing, centralized logging, service discovery, an API gateway, a separate build-and-deploy pipeline per service, and cross-service integration tests. This is a non-trivial platform investment, and it pays off when multiple teams need autonomous deployment.

If none of those conditions apply, the answer is that you would start with a well-structured modular monolith. It gives clear module boundaries that can later be extracted into services, when the team size and the scaling requirements justify it. Starting with microservices before the bounded contexts are stable is one of the most expensive architectural mistakes a team can make.

---

**Can you violate the Dependency Rule within a single layer? Under what circumstances?**

The Dependency Rule prohibits inner layers from importing outer layers. It says nothing about lateral dependencies within the same layer. Two services that orchestrate different use cases may still need to call each other. That is a lateral dependency inside the service layer, and it is generally acceptable as long as cycles are avoided.

In NestJS, `OrdersService` importing `UsersService` to look up a user is a lateral service-layer dependency, not a Dependency Rule violation.

Two problems to avoid within a layer:

- Circular dependencies: A imports B, and B imports A.
- Hidden coupling, where one module reaches into another module's internals instead of its public API.

For lateral calls inside a layer that would create tight coupling, consider extracting a shared lower-level service, or using events.

---

**Your modular monolith has a module causing memory issues. You need to extract it as a service. Walk through the approach.**

This is the Strangler Fig Pattern applied at the module level. Five steps:

- **Verify the boundary.** Confirm that the module's `index.ts` really exposes a clean API, and that no other module imports its internals. If internals are leaked, fix that first.
- **Wrap the module in an interface.** If other modules call `OrdersService.placeOrder()` directly, create an `IOrdersModule` interface for them to call instead.
- **Create the new service** with the extracted module's logic, and deploy it independently.
- **Replace the direct calls with HTTP or queue calls.** The other modules keep calling through the interface. The implementation switches from a direct import to an HTTP client adapter.
- **Remove the module from the monolith** once the new service is stable.

The key property: because the module boundary was explicit in the monolith, steps 1 and 2 are quick. The hard work is in the infrastructure — deployment, monitoring and distributed tracing for the new service.

---

**Your service has 300 methods. What does that tell you and what do you do?**

A service with 300 methods is a God object. It violates the SRP (Single Responsibility Principle): a class should have exactly one reason to change, that is, it should serve one actor. It also tells you that "service" was treated as "everything that isn't a controller".

The path forward: identify cohesive groups of methods.

- `placeOrder`, `cancelOrder`, `refundOrder` → `OrderLifecycleService`
- `getOrdersByUser`, `searchOrders`, `exportOrders` → `OrderQueryService`
- `calculateOrderTotal`, `applyDiscount` → `OrderPricingService`

If some methods are just CRUD wrappers with no business logic, those may belong on the repository directly. Don't do this as a pure refactor sprint. Do it alongside feature work: when you next touch `placeOrder`, move the group it belongs to into its new home.

---

**How do you test a Clean Architecture use case without mocking everything?**

Two approaches, and the distinction matters.

- **Mock-based.** Create Jest mocks for all dependencies (`jest.fn()`), set return values, assert calls. Fast but brittle: the tests verify that the use case called the right method, not that the logic is correct.
- **Fake-based**, preferred for use cases. Create a real in-memory implementation of each driven port. An `InMemoryOrderRepository` stores in a `Map`; a `FakeEmailNotifier` stores sent emails in an array. The use case runs with real logic, and the ports behave like real implementations.

Tests then assert outcomes ("the order was saved", "the email was sent to this address") rather than implementation details ("repository.save was called once"). Fakes are more work to write, but they produce tests that survive refactoring. The Hexagonal Architecture `in-memory/` adapter folder exists precisely for this purpose.

---

**You need to update two tables atomically, but each is owned by a different microservice. What are your options?**

There is no perfect solution — this is the distributed consistency problem. Four options, in increasing complexity:

- **Rethink the service split.** If two services must update atomically often enough to be a recurring pattern, they may belong in the same service. Forced transactions across services are often a signal of a wrong service boundary.
- **Saga pattern (choreography).** Service A completes its update and emits an event; Service B receives the event and does its own update. If B fails, B emits a failure event, and A then runs a compensating transaction to undo its change. The result is eventual consistency: briefly inconsistent, but each service handles its own rollback.
- **Saga pattern (orchestration).** A dedicated Saga Orchestrator calls each service, tracks state, and issues compensating calls on failure. More explicit, but it introduces a new component.
- **Two-Phase Commit (2PC).** A distributed transaction coordinator locks rows in both databases before committing. Technically correct, but widely avoided: it holds locks across two databases over the network, which causes deadlocks and availability problems. It is almost never used in practice.

---

**What is the difference between Dependency Injection (DI) and Dependency Inversion (DIP)?**

**Dependency Inversion Principle (DIP)** is the "D" in SOLID, a design principle: high-level modules should not depend on low-level modules; both should depend on abstractions. It dictates the *direction* of dependencies. `OrdersService` depends on `IOrderRepository` (the abstraction), not on `PrismaOrderRepository` (the concrete class).

**Dependency Injection (DI)** is a *technique* for supplying dependencies from outside a class rather than creating them inside. Constructor injection looks like `constructor(private repo: IOrderRepository)`.

DI is one way to achieve DIP, but not the only one. You can have DI without DIP, by injecting a concrete class. You can have DIP without DI, by using a factory function or a service locator instead of constructor injection.

In a NestJS context, `@Injectable()` plus `@Inject()` is the DI mechanism, and the `IOrderRepository` interface is what makes it follow DIP.

---

**An ADR from 2022 says "use PostgreSQL." The team now wants MongoDB. What's the process?**

ADRs are immutable — you don't edit the old one. The process has four steps:

- **Read ADR-0003** to understand the context. What were the constraints in 2022? Are they still valid? For example: "team has no MongoDB experience" — is that still true?
- **Write a new ADR**, say ADR-0019. Its Context section explains what has changed since 2022. The data model needs are different, the scaling requirements changed, and the team has gained NoSQL (non-relational database) experience. Its Decision section states the new direction. Its Consequences section covers the migration path and the trade-offs.
- **Update ADR-0003** status to `Superseded by ADR-0019`.
- **Open the pull request** that starts the migration, and include both ADRs in it.

This preserves history. A reader three years from now can understand the full evolution: why Postgres was chosen, and why it was later replaced.

---

**You're designing a new Node.js service from scratch. Walk through your architectural decisions.**

A concrete decision sequence:

- **Scope the domain.** What business capabilities does this service own? What does it not own? Write this down as a proto-ADR.
- **Choose the layering approach.** For a simple CRUD service: layered architecture (controller → service → repository). For complex business logic that needs independent testing: Clean Architecture or Hexagonal.
- **Define the domain types** first — pure TypeScript interfaces, no decorators from an ORM (object-relational mapper), no framework imports.
- **Design the ports** (if using Hexagonal) or the service interfaces, before writing any implementation.
- **Wire dependencies in `main.ts` or in a module** — one Composition Root.
- **Write the first use case test** before the implementation. It validates that the architecture supports testing without infrastructure.
- **Write an ADR** for each significant decision as it's made: framework choice, database choice, architecture pattern choice.

The sequence matters: domain types → interfaces → implementations → wiring → tests, not the reverse.

---

**A service calls 8 other services synchronously per request. What problems does this cause and how do you fix it?**

**Problems**

- **Latency multiplication** — if each downstream call takes 50ms and the calls are sequential, the request takes 400ms at minimum. Parallel calls help, but don't eliminate the problem.
- **Cascading failures** — if any of the 8 services goes down or is slow, the orchestrating service degrades or fails completely, unless it has circuit breakers.
- **Tight coupling** — the orchestrating service must be deployed after all 8 of its dependencies. Changes in any downstream service's API require coordinated updates.
- **Distributed monolith symptom** — 8 synchronous dependencies on a single request path suggest these services don't have properly isolated bounded contexts.

**Fixes, in increasing scope**

- **Parallelize independent calls** with `Promise.all` to reduce latency.
- **Add circuit breakers and timeouts** — the `opossum` library, for example — to prevent cascading failures.
- **Replace some synchronous calls with async events.** If the orchestrating service doesn't need the result immediately, emit an event and let downstream services react independently.
- **Reconsider service boundaries** — services that must always call each other synchronously probably belong together.
