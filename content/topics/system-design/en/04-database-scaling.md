# Database Scaling

## Why the database is so often the bottleneck

App servers are stateless and easy to scale horizontally: add instances behind a load balancer, done. A database is, by definition, a **stateful** component. Its data physically lives in one place, so "just add another database" doesn't work as simply as it does for an app server. You have to decide **where** specific data lives, and how to keep the copies consistent.

The path to scaling a database almost always follows this order, and each step is harder than the last:

```txt
1. Vertical scaling (more RAM/CPU/disk for the database)
2. Indexes and query optimization
   (often solves 80% of problems with no infra changes)
3. Read Replicas (scaling reads)
4. Caching layer (covered separately)
5. Sharding / Partitioning (scaling writes and data volume)
6. Database per service / CQRS (architectural separation)
```

A senior answer doesn't start with sharding. It starts by noting that **most "database problems" in practice are solved by indexes, query tuning and caching**. Moving to sharding is a significant architectural investment with long-term costs, and it's worth doing only once the simpler steps are exhausted.

## Read Replicas — synchronous vs asynchronous replication

```txt
Write
 ↓
Primary DB ──replication──→ Replica 1
                ──────────→ Replica 2
                ──────────→ Replica 3

App: writes → Primary
     reads  → Replicas (round-robin / least-lag)
```

This works because in typical read-heavy systems the read:write ratio is often 10:1 to 1000:1, as the System Design Fundamentals article shows. A handful of read replicas absorb most of the load, leaving the primary to handle only writes.

**Synchronous replication**: the primary waits for acknowledgment from the replica or replicas before it treats the write as successful.

```txt
Pros: a replica is guaranteed to have the latest data
      (zero data loss on failover)
Cons: write latency = the latency of the slowest
      synchronous replica; if a replica is unreachable,
      writes may block
```

**Asynchronous replication**: the primary acknowledges the write to the client immediately, and replicas apply changes "whenever they can."

```txt
Pros: writes are fast, independent of replica state
Cons: replication lag — a replica is temporarily behind
      the primary (usually milliseconds, but it can be
      seconds under load)
```

### Replication lag and the "read-your-own-writes" problem

A classic scenario that almost always comes up in interviews:

```txt
1. A user updates their profile → the write goes to Primary
2. Immediately after, they GET their profile
   → the request goes to a Replica
3. Replication lag = 200ms,
   the Replica hasn't applied the change yet
4. The user sees old data right after saving
```

Fixes, each with its own trade-off:

- **Read from the primary right after a write**, for that same user. This is often implemented as "read-your-writes" routing: for N seconds after a write, reads for this user or session go to the primary.
- **Session affinity to a specific replica** that is guaranteed to have the update. Hard to track.
- **Versioning**: the client passes a "minimum acceptable data version", and a replica that is too far behind isn't used for this request.
- **Accept staleness as part of the UX** (user experience). That is fine for most data — a "like" doesn't have to appear instantly to its own author.

This isn't a "theoretical" problem. In production it shows up as the bug "I saved it and the old data came back". It is a frequent source of support tickets.

## Sharding (Partitioning) — splitting data across nodes

Sometimes replicas aren't enough: the **write volume** or the **data volume** exceeds what a single node can handle. Then data is physically split across independent database nodes called shards. Each shard holds its own slice of the data.

There are three common ways to decide which shard a row belongs to. The choice decides whether load is even and whether range queries stay cheap. It also decides whether you can satisfy data-residency law such as GDPR (General Data Protection Regulation):

```txt
Range-based sharding:
  Users A-M  → Shard 1
  Users N-Z  → Shard 2

  Pros: simple, easy to run range queries within one shard
  Cons: uneven distribution (a hot shard if, e.g., many
        users have last names starting with the same letter)

Hash-based sharding:
  shard = hash(user_id) % N

  Pros: even distribution
  Cons: range queries ("all users with id 1000-2000")
        have to hit every shard; resharding when N changes
        means massive data movement (see consistent hashing
        in the Load Balancing article)

Geo-based sharding:
  EU users → Shard EU, US users → Shard US

  Pros: meets data residency requirements, low latency
        (data is close to the user)
  Cons: cross-region queries (e.g., friends across
        regions) become complex
```

### The core problem with sharding: operations that used to be "free" become expensive

Sharding turns three everyday operations into hard problems. On a single node each of them is cheap: a JOIN is one SQL (structured query language) statement, and an aggregation is one query. A transaction gets ACID (atomicity, consistency, isolation, durability) for free.

| Operation | Before sharding (one database) | After sharding |
|---|---|---|
| `JOIN users, orders` | One SQL query | Impossible at the database level; do it in the app — several queries plus a merge in code |
| Transaction: debit A, credit B | One shard, so ACID guarantees atomicity | A and B may live on different shards; needs 2-Phase Commit or a Saga |
| `SELECT COUNT(*) WHERE status = X` | One query | The result must be aggregated across all shards and summed in the application |

A cross-shard transfer becomes a distributed transaction. Both ways of doing one — 2-Phase Commit and Saga — bring their own complexity and latency.

**Choosing the shard key is the most important sharding decision**, and it's nearly impossible to change without a full data migration. A good shard key:

- distributes load evenly, avoiding hot shards — don't shard by `tenant_id` if one tenant generates 90% of traffic;
- covers most queries. If 95% of queries come in by `user_id`, sharding by `user_id` keeps those requests inside one shard. But queries by `order_id` now have to hit every shard, unless `order_id` maps predictably to `user_id`.

## SQL vs NoSQL — not "which is better," but "which guarantees do you need"

The question isn't which family is better. It is which guarantees you need. SQL means a relational database with a fixed schema; NoSQL (not-only-SQL) covers several very different non-relational families:

```txt
SQL (PostgreSQL, MySQL):
  + strict schema, ACID transactions, JOINs,
    mature ecosystem
  - horizontal scaling (sharding) is harder
    and less "out of the box"

NoSQL — Document (MongoDB):
  + flexible schema, good for denormalized/nested data
  - no database-level JOINs, ACID usually only
    within a single document

NoSQL — Key-Value (DynamoDB, Redis):
  + predictable latency at large scale, built-in sharding
  - queries only by key (or limited indexes)

NoSQL — Wide-Column (Cassandra):
  + write-heavy workloads, built-in multi-region replication
  - eventual consistency by default, and the data model is
    tailored to specific query patterns
    (denormalization is mandatory)
```

A senior answer to "SQL or NoSQL?" is about **data access patterns and consistency requirements**, not "NoSQL scales better". Modern PostgreSQL with replicas and partitioning handles enormous loads just fine — Instagram ran on sharded PostgreSQL for years.

## CQRS and Database per Service

**CQRS (Command Query Responsibility Segregation)** separates the data model used for writes from the one used for reads:

```txt
Write Model (normalized, optimized for data integrity)
  ↓ events/sync
Read Model (denormalized, optimized for specific UI queries,
            possibly a different database —
            e.g., Elasticsearch for search)
```

This lets you scale and optimize the read and write paths independently. The cost is a synchronization delay between the write and read models, usually via an event queue. That is a deliberate move to eventual consistency for reads.

**Database per Service** is a microservices practice: each service owns its own database, and nobody reaches into another service's database directly. This gives you isolation — a schema change in one service doesn't break the others — and it lets each service scale independently.

But it creates a classic problem: what about a request that needs data from several services? You have two options. Either send several requests and merge the results at the API Gateway or BFF (Backend For Frontend) layer. Or keep a denormalized copy of the data inside the service that needs it, kept in sync via events.

## Common interview mistakes

- **Proposing sharding as the first step in scaling a database**, without mentioning indexes, read replicas and caching. Those solve a much larger share of real problems with far less complexity.

- **Not mentioning replication lag and read-your-writes** when adding read replicas. This is one of the most expected follow-ups, and its absence stands out immediately.

- **Treating sharding as "free" scaling** — without acknowledging that joins, transactions and aggregations become dramatically harder.

- **Picking a shard key without justification** — especially not mentioning the hot-shard risk and the migration cost of changing the sharding scheme later.

- **"NoSQL scales, SQL doesn't".** That ignores how far modern PostgreSQL with partitioning and replicas can scale. The choice should be driven by access patterns and consistency requirements.

- **CQRS as "just split reads and writes"**, without mentioning eventual consistency between the write and read models. That is the central trade-off of the pattern.
