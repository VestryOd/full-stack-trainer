# Architecture Decision Records (ADRs)

> **Scope note:** ADRs are a documentation practice, not a code pattern. They apply at any scope — a single service, a platform, an entire organization. They're included in this series because architectural decisions are only half the work; capturing *why* they were made is what makes a codebase navigable for the next engineer.

## The problem ADRs solve

Six months after building a system, a new engineer joins and finds something puzzling in the codebase:

- The service uses PostgreSQL and Redis for what seems to be overlapping purposes
- Authentication is handled by a custom JWT implementation instead of Passport.js
- The monorepo has a `shared/` package that only two of seven services actually use
- Prisma is used for reads, but raw SQL for writes

They have two options: accept these as facts and work around them, or spend time reconstructing the reasoning. Often the original engineers have left. The Slack thread where the decision was made is buried under 50,000 other messages. The PR description says "add Redis caching" but not "we chose Redis over Memcached because..."

The codebase captures *what was decided*. Nothing captures *why*.

An **ADR (Architecture Decision Record)** is a short, structured document that records one architectural decision alongside its context and consequences. Its purpose is to answer "why is this like this?" for future readers — including your future self six months from now.

## The Nygard format — the most widely used structure

Michael Nygard proposed this format in 2011. It's been adopted by teams at GitHub, Spotify, ThoughtWorks, and many others because it's minimal and forces the author to think through the consequences.

```markdown
# ADR-0003: Use PostgreSQL as the primary data store

## Status
Accepted

## Context
We need a persistent data store for user accounts, orders, and inventory.
The data is relational (users have orders, orders have line items, line items reference products).
The team has deep experience with SQL; nobody has production MongoDB experience.
We expect strong consistency requirements for financial transactions.
We're targeting AWS; RDS for PostgreSQL is available with managed backups and failover.

## Decision
We will use PostgreSQL as the primary relational database.
We will use AWS RDS in the production environment and a Docker container locally.
We will use Prisma as the ORM for schema management and type-safe queries.

## Consequences
**Positive:**
- Relational model fits the data well; no impedance mismatch
- ACID transactions work out of the box across related tables
- Team already knows SQL; no learning curve
- Prisma provides type safety and auto-generated migrations

**Negative:**
- Horizontal write scaling is harder than with NoSQL databases
  (acceptable given current projected load of <10k req/day)
- Schema migrations require careful handling in production;
  Prisma's migration workflow requires discipline with deploy pipelines

**Neutral:**
- We accept that switching to a different database later would require
  significant migration effort. This is an intentional trade-off for
  the consistency and team-familiarity benefits.
```

The four sections:

- **Status** — one of: `Proposed` (under discussion), `Accepted` (decided), `Deprecated` (no longer applies), `Superseded by ADR-XXXX` (replaced by a later decision). Status lets readers know whether this decision is active.
- **Context** — what was the situation when this decision was made? What constraints existed? What options were considered? This section ages the ADR: a reader in 2 years can tell whether the context still applies.
- **Decision** — the actual decision. One specific, affirmative statement. "We will use X" not "X seems like a good choice."
- **Consequences** — what becomes easier, harder, or different as a result of this decision? Include both positive and negative. This section is what makes an ADR more valuable than a simple "we chose X" note.

## A second example — architectural pattern decision

ADRs aren't only for technology choices. They're just as useful for pattern decisions:

```markdown
# ADR-0007: Use modular monolith instead of microservices for initial launch

## Status
Accepted

## Context
We are building an e-commerce platform for launch in Q3. Team size is 4 engineers.
We've discussed splitting into microservices (Orders, Users, Inventory, Notifications).

Key constraints:
- 4 engineers cannot maintain 4+ separate deployment pipelines, monitoring setups,
  and service contracts simultaneously while shipping features
- Business requirements are still being refined; service boundaries are not stable
- Target load at launch is <500 concurrent users; horizontal scaling of a single
  service will be sufficient for 12+ months
- We don't have Kubernetes or container orchestration set up

Options considered:
1. Microservices from the start
2. Modular monolith with explicit module boundaries (chosen)
3. Unstructured monolith

## Decision
We will build a modular monolith. Each business domain (Orders, Users, Inventory,
Notifications) will be a separate module with an explicit public API (index.ts exports).
Cross-module imports are only allowed through the public API. No direct database
access across module boundaries.

We will revisit this decision when any of these conditions is met:
- Team grows beyond 8 engineers
- A module's scaling requirements diverge significantly from others
- Independent deployment of a module would meaningfully reduce coordination overhead

## Consequences
**Positive:**
- One deployment pipeline, one monitoring setup, one local dev environment
- ACID transactions work across module boundaries (same database)
- Refactoring module boundaries is a file-move, not a distributed migration
- New engineers onboard to one codebase

**Negative:**
- Cannot scale modules independently (acceptable given load projections)
- A bug in one module can affect others (mitigated by module-level test isolation)

**Neutral:**
- If we later extract a module into a microservice, the explicit boundary in the
  modular monolith makes this straightforward: the module's public API becomes
  the service's API contract; its data access layer becomes the service's repository
```

## Where to store ADRs

The universal convention: a `docs/adr/` directory in the repository, with sequentially numbered files.

```txt
docs/
└── adr/
    ├── 0001-use-nodejs-and-typescript.md
    ├── 0002-use-nestjs-as-framework.md
    ├── 0003-use-postgresql-as-primary-data-store.md
    ├── 0004-use-redis-for-session-caching.md
    ├── 0005-use-jest-for-testing.md
    ├── 0006-use-github-actions-for-ci.md
    └── 0007-modular-monolith-instead-of-microservices.md
```

Why in the repository (not Confluence, not Notion):

1. **ADRs live next to the code they describe** — when you read the code, the ADR is one `git log` away
2. **ADRs are version-controlled** — you can see when a decision changed and link commits to ADRs
3. **ADRs are reviewed in PRs** — the pull request for "migrate from Passport.js to custom JWT" can include a new ADR as part of the change

The numbering is intentionally padded (`0001` not `1`) so files sort correctly in filesystems that sort lexicographically.

## When to write an ADR

Not every decision needs an ADR. The test is:

> "Would a competent engineer who joins this project in 6 months be confused about why this decision was made, or be tempted to reverse it without knowing the full context?"

If yes — write an ADR.

**Write an ADR for:**
- Technology choices (database, framework, ORM, queue, cache)
- Architectural pattern choices (layered vs clean vs hexagonal, monolith vs microservices)
- Decisions that involve explicit trade-offs that aren't obvious from the code
- Decisions to *not* use something that would otherwise be an obvious choice ("we evaluated GraphQL but chose REST because...")
- Anything that was debated in the team and resolved in a specific direction

**Don't write an ADR for:**
- Implementation details that can be understood by reading the code
- Decisions that are trivially reversible (which logging library to use for a prototype)
- Coding style conventions (use a `.eslintrc` and `README` section instead)
- Decisions driven entirely by "it was the default" with no meaningful alternatives considered

## Updating and superseding ADRs

ADRs are **immutable by default** — you don't edit an old ADR to change the decision. You write a new ADR that supersedes it.

```markdown
# ADR-0011: Replace Passport.js with custom JWT middleware

## Status
Accepted — supersedes ADR-0004

## Context
ADR-0004 chose Passport.js for authentication. Since then:
- We added multi-tenant support requiring per-tenant JWT secrets
- Passport.js's strategy system added complexity that didn't fit our multi-tenant model
- A security audit flagged that Passport's session serialization was not needed for
  our stateless API (we don't use sessions)

## Decision
Replace Passport.js with a custom JWT verification middleware using the `jsonwebtoken`
library directly. The middleware validates the token, attaches `req.user`, and handles
per-tenant key lookup.

## Consequences
...
```

And update the old ADR:

```markdown
# ADR-0004: Use Passport.js for authentication

## Status
Superseded by ADR-0011
```

This way the full history is preserved. A reader can trace the evolution: why was Passport.js chosen originally? Why was it replaced? Both answers are available without reading git blame.

## Lightweight variant — the Y-statement

For teams that find the Nygard format too heavy, a single-sentence **Y-statement** captures the essentials:

```
In the context of <situation>,
facing <concern>,
we decided <option>,
to achieve <quality>,
accepting <downside>.
```

Example:
```
In the context of needing a caching layer for expensive database queries,
facing high read latency on the orders summary endpoint,
we decided to use Redis with a 60-second TTL,
to achieve sub-100ms response times for the dashboard,
accepting that cached data may be up to 60 seconds stale.
```

Y-statements work well as inline comments in code, or as a first pass before writing a full ADR:

```ts
// ADR-0009 (Y-statement): In the context of order status webhooks,
// facing unreliable delivery from payment providers,
// we decided to use idempotency keys on the handler,
// to achieve exactly-once processing,
// accepting the extra Redis lookup per webhook.
export async function handlePaymentWebhook(req: Request): Promise<void> {
  const idempotencyKey = req.headers['x-idempotency-key'] as string;
  const alreadyProcessed = await redis.set(idempotencyKey, '1', 'NX', 'EX', 86400);
  if (!alreadyProcessed) return; // already handled
  // ...
}
```

## Common interview traps

- **"ADRs are only for big architecture decisions like choosing a database"** — ADRs are for any decision that would cause a future engineer to ask "why?". "Why do we have a custom retry wrapper instead of using axios-retry?" is a valid ADR. "Why does the Orders module not call the Users service directly but instead reads user data from a denormalized column?" is a valid ADR. The scope is any non-obvious decision, not just the ones that appear on architecture diagrams.

- **"We document decisions in Confluence / Notion"** — the problem isn't the tool, it's the distance from the code. Documentation that lives in a separate system gradually diverges from the code as the code changes and nobody updates the doc. ADRs stored in the repository are read when the code is being changed (because the engineer is already in the repo), and updated in the same PR that makes the change. This is the key property, not the markdown format.

- **"An ADR becomes outdated when the decision changes, so it's maintenance overhead"** — an outdated ADR (with `Status: Superseded by ADR-XXXX`) is not useless. It's historical context: it tells you what was decided, when, and why it was later changed. This is exactly what you can't recover from Slack history or commit messages. The maintenance cost of writing "Superseded by ADR-XXXX" in the status field is negligible compared to the value of the preserved context.

- **"ADRs slow down fast-moving teams"** — writing an ADR after an architectural discussion takes 20–30 minutes. Reconstructing the reasoning behind a decision 12 months later (new engineer, migration, debugging a weird constraint) can take hours or days — and may be impossible if people have left. The investment is highly asymmetric.

- **"If the code is clean, you don't need ADRs"** — clean code explains *what* it does. Clean Architecture explains *how* it's structured. Neither explains *why* a specific technology or pattern was chosen over alternatives that were also reasonable. "We use Redis for caching" is obvious from the code. "We chose Redis over Memcached because we also needed pub/sub for invalidation, and Memcached doesn't support pub/sub" is not visible anywhere except an ADR.
