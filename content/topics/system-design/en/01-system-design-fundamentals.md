# System Design Fundamentals

## What System Design is, and why it's a separate skill

System Design is the process of architecting a system: what components it has, how they interact, where data lives, and how the system behaves under load and during failures.

In an interview, System Design isn't a test of knowing specific technologies ("name a caching tool") — it's a test of **thinking process**: how you turn a vague prompt ("design Instagram") into a set of concrete, discussable decisions with explicit trade-offs. The interviewer cares less about the final architecture (it's almost always incomplete after 45 minutes) than about **how you got there**: what questions you asked, what requirements you surfaced, what alternatives you considered, and why you picked these.

The core idea to internalize: **there's no such thing as a perfect architecture, only trade-offs given specific requirements**. Every architectural decision trades one system property for another: consistency for availability, latency for cost, simplicity for scalability. A strong answer is always phrased as "given these requirements, I'd choose X, which gives us A at the cost of B, and in our case A matters more."

## Step 1: Requirements Clarification — never start with a diagram

The most common mistake junior/mid candidates make is jumping straight to a diagram ("okay, we'll have a load balancer, then servers, then a database..."). That's a signal the candidate is solving the problem "from memory" rather than understanding what actually needs solving. A senior candidate spends the first 5-10 minutes clarifying requirements — and interviewers explicitly expect this.

### Functional Requirements (FR)

What the system needs to **do** — the list of user/client actions. For a chat app, this might be:

```txt
- send text messages 1:1 and in groups
- deliver messages to online users in real time
- store message history
- "delivered/read" indicators
- (optional, clarify) attachments, voice messages, history search
```

Important: for a large system (Instagram, YouTube), you can't design everything. You need to explicitly **narrow the scope** — pick 2-3 core features to build the rest of the discussion around, and explicitly mark the rest as "out of scope for this discussion."

### Non-Functional Requirements (NFR)

How the system needs to **behave** — these drive architectural decisions more than FRs do. Key NFRs:

```txt
- Latency: e.g., p99 < 200ms for sending a message
- Availability: 99.9% / 99.99% / 99.999%
- Consistency: how critical is it that everyone sees the same data at the same time
- Durability: can we afford to lose data (a message, a payment — no; a "like" — probably fine)
- Scalability: current and expected load, growth pattern
```

NFRs determine the database choice (SQL vs NoSQL), whether a cache is needed, the replication pattern, whether a queue is needed. If a candidate doesn't clarify NFRs, every subsequent decision looks like "I picked this technology because I've heard of it," not "I picked this technology because it satisfies the requirements."

## Step 2: Scale Estimation (Back-of-the-envelope)

A rough scale estimate isn't about precision — it's about understanding the **order of magnitude**, which determines whether you even need sharding, a cache, a CDN, or whether "one DB with a replica" is enough.

A typical set of calculations for something like a Twitter-style feed:

```txt
Given:
  100M DAU (daily active users)
  each user reads the feed ~2 times per day
  10% of DAU post once per day

Traffic:
  Reads/day  = 100M * 2 = 200M
  Writes/day = 100M * 0.1 = 10M

  Reads QPS  = 200M / 86,400 ≈ 2,300 RPS (average)
  Writes QPS = 10M / 86,400 ≈ 115 RPS (average)

  Peak (typically 3-5x average) ≈ 7,000-11,500 RPS for reads

Storage (per year):
  10M posts/day * 365 days * ~1 KB (text + metadata) ≈ 3.65 TB/year
  + media (photos/videos) — calculated separately, usually orders of magnitude larger
```

The practical conclusion from these numbers: **2,300 RPS for reads already firmly means "you need a cache and read replicas," not "a single Postgres instance will do."** And a 200:1 read:write ratio tells you all optimization effort should target the read path (a read-heavy system — see below).

You don't need mathematical precision — round numbers (100M, 10%, 1KB) are deliberately chosen for easy mental math. What matters is showing you can **connect business metrics to technical load**.

## Core building blocks

Almost any system is a combination of this set of components, and the interview often turns into a discussion of **which of these are needed in this specific case, and why**:

| Component | Role | When it's required |
|---|---|---|
| **Load Balancer** | Distributes requests across instances | As soon as you have > 1 app instance |
| **Application servers** | Business logic, stateless | Always |
| **Database (primary)** | Source of truth | Always |
| **Read replicas** | Offload read traffic from primary | Read-heavy systems under meaningful load |
| **Cache (Redis/Memcached)** | Reduces latency and DB load | Hot data, repeated queries |
| **Message Queue** | Async processing, service decoupling | Long-running operations, traffic spikes, event-driven architecture |
| **CDN / Object Storage** | Static assets, media, geo-distribution | Any user-generated content (images/video/files) |

The base starting architecture is almost always:

```txt
Client → Load Balancer → App Servers (stateless) → Database
```

Every additional component (cache, queue, CDN, read replicas, sharding) is added **in response to a specific constraint** you've identified in earlier steps — not "because it's standard practice." That's what "design" actually is: iteratively eliminating bottlenecks one at a time, explaining exactly which problem each next component solves.

## Vertical vs Horizontal Scaling

**Vertical scaling** — increasing the resources of a single server (8 GB → 32 GB RAM, more CPU).

- Pros: simple, requires no architectural changes, no consistency issues between instances.
- Cons: there's a physical ceiling (even the most powerful server is finite), single point of failure remains, cost grows non-linearly (top-tier hardware is disproportionately expensive).

**Horizontal scaling** — adding more servers instead of growing existing ones.

- Pros: near-unlimited growth, natural redundancy (one instance failing doesn't kill the system).
- Cons: adds complexity — you need a load balancer, services must be **stateless** (see below), and data consistency across instances becomes its own problem.

Senior nuance: for a **database**, horizontal scaling (sharding) is a significantly harder and more expensive operation than for stateless app servers, because data must be physically distributed while maintaining consistency/joins across shards. So the typical strategy is to scale the DB vertically first and offload load with caches/replicas, and only go to sharding once that hits a ceiling.

## Stateless Services — why this matters for horizontal scaling

**Stateless** means an app server holds no user/session-specific state in memory between requests. Any user's request can be handled by **any** instance — this is a prerequisite for a load balancer to freely distribute traffic and for instances to be added/removed without losing data.

The problem statelessness solves — the classic example:

```txt
❌ Session in memory:
  User → LB → Server A (session stored in RAM)

  The user's next request lands on Server B
  → Server B doesn't know about the session → user appears "logged out"
```

Ways to store state outside the app server:

```ts
// Option 1: JWT — state is serialized into the token itself,
// the server stores nothing, any instance can verify the signature
function verifyToken(token: string): UserPayload {
  return jwt.verify(token, JWT_SECRET) as UserPayload;
  // Downside: can't instantly revoke a token before it expires
  // without an additional denylist in Redis
}

// Option 2: Redis as a centralized session store —
// any instance can read/write the shared store
async function getSession(sessionId: string): Promise<Session | null> {
  const raw = await redis.get(`session:${sessionId}`);
  return raw ? JSON.parse(raw) : null;
}
```

Sticky sessions (the LB pins a user to a specific server via a cookie) is a "workaround" that technically allows in-memory state, but breaks even load distribution and complicates deployments (restarting an instance = losing sessions for everyone pinned to it). Mentioning sticky sessions as "the solution" without noting these downsides is a weak answer.

## Availability, Reliability, and Single Point of Failure (SPOF)

**SPOF** — any component whose failure brings down the whole system (or a significant part of it) because it has no redundancy. The classic example is a single database with no replicas: if it goes down, everything depending on it goes down.

Eliminating a SPOF isn't "add another server" — it's **replication + a failover mechanism**: a replica must be ready to take traffic, and there must be a way to detect the primary's failure and switch over (automatically or manually).

**Availability** is measured in "nines" — the fraction of time the system responds correctly:

| SLA | Allowed downtime/year | Allowed downtime/month |
|---|---|---|
| 99% | ~3.65 days | ~7.3 hours |
| 99.9% ("three nines") | ~8.76 hours | ~43.8 minutes |
| 99.99% ("four nines") | ~52.6 minutes | ~4.4 minutes |
| 99.999% ("five nines") | ~5.26 minutes | ~26 seconds |

Senior nuance: each additional "nine" costs **an order of magnitude more** in engineering effort (multi-region, active failover, chaos engineering, on-call processes) — so the first question isn't "how do we hit 99.999%" but "do we even **need** 99.999% for this product, and what's the actual cost of downtime." For an internal dashboard, 99.9% might be overkill; for a payment gateway, 99.9% might not be enough.

## Latency vs Throughput

These are two different performance dimensions and are often conflated:

- **Latency** — time to complete **one** request (e.g., 50ms, 100ms, 300ms). Matters for a single user's UX.
- **Throughput** — number of operations **per unit time** (RPS — requests per second, or QPS). Matters for understanding overall system resource needs.

These metrics don't always correlate directly: you can increase throughput via batching, but that increases each individual request's latency (it waits for the batch to fill). This is the classic latency vs throughput trade-off.

Senior nuance on latency: **never say "100ms latency" without specifying a percentile**. Average latency can be low while p99 (99th percentile — the worst 1% of requests) is 10x higher — and it's p99 that determines how many users actually get a bad experience. At high scale, 1% of 1M requests is 10,000 unhappy users a day.

## CAP Theorem: Availability vs Consistency

The CAP theorem states that a distributed system can't simultaneously guarantee all three properties in the presence of a **network partition** (a break in connectivity between nodes):

```txt
C — Consistency: all nodes see the same data at any given moment
A — Availability: every request gets a response (no guarantee the data is current)
P — Partition Tolerance: the system keeps working despite a network split between nodes
```

Since partition tolerance isn't optional in real distributed systems (networks eventually fail), in practice the choice is always between **CP** and **AP** specifically during a partition:

- **CP** (Consistency over Availability) — during a network split, the system refuses to respond rather than return stale/conflicting data. Example: bank account balance, limited-stock warehouse inventory.
- **AP** (Availability over Consistency) — the system keeps responding even if different nodes temporarily see different data (eventual consistency). Example: a social feed, a like counter, "online/offline" status in chat.

Senior nuance: CAP is about behavior **during a network partition**, not a 24/7 characterization of a system. In normal operation (no partition), most systems provide both consistency and availability. A more practical model is **PACELC**: "if Partitioned — Availability or Consistency; Else (normal operation) — Latency or Consistency" — it explicitly accounts for the latency/consistency trade-off even without failures (e.g., synchronous vs asynchronous replication).

## Read-Heavy vs Write-Heavy systems

The read-to-write ratio drives almost the entire technology stack:

```txt
Read-heavy (Instagram, YouTube, news sites):
  reads:writes is often 100:1 or higher
  → aggressive caching, read replicas, CDN for static assets,
    denormalizing data for read patterns

Write-heavy (analytics, IoT telemetry, logs, event billing):
  writes:reads can be comparable, or writes dominate
  → write-optimized storage (LSM-trees: Cassandra, RocksDB),
    write batching, queues to smooth out spikes,
    often time-series databases
```

Practical takeaway: if you propose PostgreSQL with standard B-tree indexes for a write-heavy system handling millions of writes per second, that's an immediate red flag — traditional relational databases with B-trees are optimized for reads, not high-frequency writes.

## Common interview mistakes

- **Jumping straight to a diagram** without clarifying FR/NFR and scope. This is the most common reason a candidate strong on knowledge gets a low System Design score — the interviewer is evaluating the process, not the final picture.

- **Skipping NFRs and scale estimation** — without numbers, you can't justify whether you need a cache, sharding, or a queue. "We need Redis because it's fast" is weak; "at 7,000 RPS for reads with a 200:1 read:write ratio, we need a cache in front of the DB because..." is strong.

- **Confusing latency and throughput**, or talking about latency without percentiles (p50/p99).

- **Treating CAP as a binary, system-wide choice** — a strong answer shows that the CP/AP choice depends on the **specific type of data**, and the same system can be CP for payments and AP for a like counter.

- **Proposing a solution with no alternatives** — a strong answer almost always includes "we could do A (pros/cons) or B (pros/cons); given our requirements, I'd pick..." — this demonstrates understanding of trade-offs rather than memorized "correct" architectures.

- **Trying to solve everything at once** — designing a system "with every feature, at any scale" instead of iterating: base architecture → identify bottleneck → targeted fix → next bottleneck.
