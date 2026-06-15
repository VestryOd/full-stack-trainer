# Database Scaling

## Why the database is so often the bottleneck

App servers are stateless and easy to scale horizontally — add instances behind a load balancer, done. A database is, by definition, a **stateful** component: data physically lives in one place, and "just add another DB" doesn't work as simply as it does for an app server, because you have to decide **where** specific data lives and how to keep copies consistent.

The path to scaling a database almost always follows this order, and each step is harder than the last:

```txt
1. Vertical scaling (more RAM/CPU/disk for the DB)
2. Indexes and query optimization (often solves 80% of problems with no infra changes)
3. Read Replicas (scaling reads)
4. Caching layer (covered separately)
5. Sharding / Partitioning (scaling writes and data volume)
6. Database per service / CQRS (architectural separation)
```

A senior answer doesn't start with sharding — it starts by noting that **most "database problems" in practice are solved by indexes, query tuning, and caching**. Moving to sharding is a significant architectural investment with long-term costs, and it's worth doing only once the simpler steps are exhausted.

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

This works because in typical read-heavy systems, the read:write ratio is often 10:1 to 1000:1 (see [System Design Fundamentals]) — a handful of read replicas absorb most of the load, leaving the primary to handle only writes.

**Synchronous replication**: the primary waits for acknowledgment from the replica(s) before considering the write successful.

```txt
Pros: a replica is guaranteed to have the latest data (zero data loss on failover)
Cons: write latency = the latency of the slowest synchronous replica;
      if a replica is unreachable, writes may block
```

**Asynchronous replication**: the primary acknowledges the write to the client immediately, and replicas apply changes "whenever they can."

```txt
Pros: writes are fast, independent of replica state
Cons: Replication Lag — a replica is temporarily behind the primary
      (usually ms, but can be seconds under load)
```

### Replication lag and the "read-your-own-writes" problem

A classic scenario that almost always comes up in interviews:

```txt
1. A user updates their profile → the write goes to Primary
2. Immediately after, they GET their profile → the request goes to a Replica
3. Replication lag = 200ms, the Replica hasn't applied the change yet
4. The user sees OLD data right after saving
```

Fixes, each with its own trade-off:

```txt
- Read from Primary immediately after a write, for that same user
  (often implemented as "read-your-writes" routing: for N seconds
  after a write, route reads for this user/session to the primary)

- Read-after-write via session affinity to a specific replica
  guaranteed to have the update (hard to track)

- Versioning: the client passes a "minimum acceptable data version,"
  and a replica that's too far behind isn't used for this request

- Accept staleness as part of the UX (fine for most data —
  a "like" doesn't have to appear instantly to its own author)
```

This isn't a "theoretical" problem — it shows up in production as the bug "I saved it and the old data came back," and is a frequent source of support tickets.

## Sharding (Partitioning) — splitting data across nodes

When even with replicas, **write volume** or **data volume** exceeds what a single node can handle, data is physically split across independent DB nodes (shards), each holding its own slice of the data.

```txt
Range-based sharding:
  Users A-M  → Shard 1
  Users N-Z  → Shard 2

  Pros: simple, easy to run range queries within a single shard
  Cons: uneven distribution (hot shard if, e.g., many users
        have last names starting with the same letter)

Hash-based sharding:
  shard = hash(user_id) % N

  Pros: even distribution
  Cons: range queries ("all users with ID 1000-2000") require
        hitting ALL shards; resharding when N changes —
        massive data movement (see consistent hashing
        in the Load Balancing topic)

Geo-based sharding:
  EU users → Shard EU, US users → Shard US

  Pros: meets data residency requirements (GDPR etc.),
        low latency (data is close to the user)
  Cons: cross-region queries (e.g., friends across regions)
        become complex
```

### The core problem with sharding: operations that used to be "free" become expensive

```txt
Before sharding (one DB):           After sharding:

JOIN users, orders                   JOIN across shards — impossible
  → a single SQL query                at the DB level, must be done
                                       at the app level (multiple
                                       queries + merge in code)

Transaction: debit account A,        Distributed transaction —
credit account B (one shard)         A and B may live on different shards
  → ACID guarantees atomicity         → needs 2-Phase Commit or Saga
                                       (with their own complexity and latency)

SELECT COUNT(*) WHERE status = X     The result must be aggregated
  → a single query                    across all shards and summed
                                       in the application
```

**Choosing the shard key is the most important sharding decision**, and it's nearly impossible to change without a full data migration. A good shard key:

- distributes load evenly (avoids hot shards — e.g., don't shard by `tenant_id` if one tenant generates 90% of traffic);
- covers most queries (if 95% of queries come in by `user_id`, sharding by `user_id` keeps those requests within one shard; but queries "by `order_id`" now require hitting all shards unless `order_id` predictably maps to `user_id`).

## SQL vs NoSQL — not "which is better," but "which guarantees do you need"

```txt
SQL (PostgreSQL, MySQL):
  + strict schema, ACID transactions, JOINs, mature ecosystem
  - horizontal scaling (sharding) is harder and less "out of the box"

NoSQL — Document (MongoDB):
  + flexible schema, good for denormalized/nested data
  - no DB-level JOINs, ACID usually only within a single document

NoSQL — Key-Value (DynamoDB, Redis):
  + predictable latency at large scale, built-in sharding
  - queries only by key (or limited indexes)

NoSQL — Wide-Column (Cassandra):
  + write-heavy workloads, built-in multi-region replication
  - eventual consistency by default, data model is tailored
    to specific query patterns (denormalization is mandatory)
```

A senior answer to "SQL or NoSQL?" is about **data access patterns and consistency requirements**, not "NoSQL scales better" — modern PostgreSQL with replicas and partitioning handles enormous loads just fine (Instagram ran on sharded PostgreSQL for years).

## CQRS and Database per Service

**CQRS (Command Query Responsibility Segregation)** — separating the data model used for writes from the one used for reads:

```txt
Write Model (normalized, optimized for data integrity)
  ↓ events/sync
Read Model (denormalized, optimized for specific UI queries,
            possibly a different DB — e.g., Elasticsearch for search)
```

This lets you scale and optimize read and write paths independently, but adds a synchronization delay between the write and read models (typically via an event queue) — i.e., a deliberate move to eventual consistency for reads.

**Database per Service** (a microservices practice) — each service owns its own database; nobody reaches into another service's DB directly. This gives isolation (a schema change in one service doesn't break others) and independent scaling, but creates a classic problem: a request needing data from multiple services requires **either** multiple requests merged at the API Gateway/BFF level, **or** a denormalized copy of the data (kept in sync via events) in the service that needs it.

## Common interview mistakes

- **Proposing sharding as the first step in scaling a database** — without mentioning indexes, read replicas, and caching, which solve a much larger share of real problems with far less complexity.

- **Not mentioning replication lag and read-your-writes** when adding read replicas — this is one of the most expected follow-ups, and its absence stands out immediately.

- **Treating sharding as "free" scaling** — without acknowledging that JOINs, transactions, and aggregations become dramatically harder.

- **Picking a shard key without justification** — especially not mentioning the hot-shard risk and the migration cost of changing the sharding scheme later.

- **"NoSQL scales, SQL doesn't"** — an oversimplification that ignores how far modern PostgreSQL with partitioning and replicas can scale; the choice should be driven by access patterns and consistency requirements.

- **CQRS as "just split reads and writes" without mentioning eventual consistency** between the write and read models — that's the central trade-off of the pattern.
