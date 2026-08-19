# System Design Fundamentals

## What System Design is, and why it's a separate skill

System Design is the process of architecting a system. Four questions define it: what components the system has, how they interact, where data lives, and how it behaves under load and during failures.

In an interview, System Design isn't a test of knowing specific technologies ("name a caching tool"). It is a test of **thinking process**: how you turn a vague prompt ("design Instagram") into a set of concrete, discussable decisions with explicit trade-offs.

Almost every system starts from the same four boxes, and the whole discipline is about when to add a fifth one:

```txt
Client → Load Balancer → App Servers (stateless) → Database
```

The interviewer cares less about the final architecture, which is almost always incomplete after 45 minutes. What matters is **how you got there**: what questions you asked, what requirements you surfaced, what alternatives you considered, and why you picked these.

The core idea to internalize: **there's no such thing as a perfect architecture, only trade-offs given specific requirements**. A strong answer always has the same shape. "Given these requirements I'd choose X, because it gives us A at the cost of B, and here A matters more". Every architectural decision trades one system property for another:

- consistency for availability;
- latency for cost;
- simplicity for scalability.

## Step 1: Requirements Clarification — never start with a diagram

The most common mistake junior and mid candidates make is jumping straight to a diagram. A typical opener: "okay, we'll have a load balancer, then servers, then a database". That's a signal the candidate is solving the problem "from memory" rather than understanding what actually needs solving. A senior candidate spends the first 5-10 minutes clarifying requirements, and interviewers explicitly expect this.

### Functional Requirements (FR)

Functional requirements (FR) are what the system needs to **do** — the list of user or client actions. For a chat app, this might be:

```txt
- send text messages 1:1 and in groups
- deliver messages to online users in real time
- store message history
- "delivered/read" indicators
- (optional, clarify) attachments, voice messages, history search
```

Important: for a large system (Instagram, YouTube), you can't design everything. You need to explicitly **narrow the scope**. Pick 2-3 core features to build the rest of the discussion around, and mark the rest as "out of scope for this discussion."

### Non-Functional Requirements (NFR)

Non-functional requirements (NFR) are how the system needs to **behave**. They drive architectural decisions more than functional requirements do. The key ones:

```txt
- Latency: e.g., p99 < 200ms for sending a message
- Availability: 99.9% / 99.99% / 99.999%
- Consistency: how critical is it that everyone
  sees the same data at the same time
- Durability: can we afford to lose data?
  A message or a payment — no. A "like" — probably fine.
- Scalability: current and expected load, growth pattern
```

Non-functional requirements drive four decisions at once: the database choice, whether a cache is needed, the replication pattern, and whether a queue is needed. The database choice is usually framed as SQL versus NoSQL. SQL means structured query language, so a relational database; NoSQL (a non-relational store) covers document, key-value and wide-column engines.

If a candidate doesn't clarify these requirements, every later decision looks arbitrary. It reads as "I picked this technology because I've heard of it", not as "I picked it because it satisfies the requirements".

## Step 2: Scale Estimation (Back-of-the-envelope)

A rough scale estimate isn't about precision. It's about the **order of magnitude**. That single number decides whether you need sharding, a cache or a CDN (content delivery network) at all. Or whether "one database with a replica" is already enough.

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
  + media (photos/videos) — calculated separately,
    usually orders of magnitude larger
```

The practical conclusion from these numbers is blunt. At **2,300 requests per second (RPS) for reads** you already need a cache and read replicas. A single Postgres instance will not do.

The 200:1 read:write ratio says where to spend effort: all optimization should target the read path. That makes this a read-heavy system, covered at the end of this article.

You don't need mathematical precision. Round numbers (100M, 10%, 1KB) are deliberately chosen for easy mental math. What matters is showing you can **connect business metrics to technical load**.

## Core building blocks

Almost any system is a combination of this set of components. The interview often turns into a discussion of **which of these are needed in this specific case, and why**:

| Component | Role | When it's required |
|---|---|---|
| **Load Balancer** | Distributes requests across instances | As soon as you have > 1 app instance |
| **Application servers** | Business logic, stateless | Always |
| **Database (primary)** | Source of truth | Always |
| **Read replicas** | Offload read traffic from primary | Read-heavy systems under meaningful load |
| **Cache (Redis/Memcached)** | Reduces latency and database load | Hot data, repeated queries |
| **Message Queue** | Async processing, service decoupling | Long-running operations, traffic spikes, event-driven architecture |
| **CDN / Object Storage** | Static assets, media, geo-distribution | Any user-generated content (images/video/files) |

The base starting architecture is almost always the four boxes from the top of this article:

```txt
Client → Load Balancer → App Servers (stateless) → Database
```

Every additional component — cache, queue, CDN, read replicas, sharding — is added **in response to a specific constraint** you identified in earlier steps. Not "because it's standard practice".

That is what "design" actually means: eliminating bottlenecks one at a time, and explaining exactly which problem each next component solves.

## Vertical vs Horizontal Scaling

**Vertical scaling** means increasing the resources of a single server: more memory (from 8 to 32 gigabytes), more processor cores (CPU), faster disks. **Horizontal scaling** means adding more servers instead of growing the existing ones.

| Aspect | Vertical scaling | Horizontal scaling |
|---|---|---|
| Complexity | Simple: no architectural changes needed | Needs a load balancer, and services must be **stateless** (the next section) |
| Ceiling | A physical limit — even the most powerful server is finite | Near-unlimited growth |
| Failures | The single point of failure remains | Natural redundancy: one instance failing doesn't kill the system |
| Consistency | No consistency issues between instances | Data consistency across instances becomes its own problem |
| Cost | Grows non-linearly — top-tier hardware is disproportionately expensive | — |

Senior nuance: for a **database**, horizontal scaling (sharding) is far harder and more expensive than for stateless app servers. The reason is that data has to be physically distributed while consistency and joins across shards keep working.

So the typical strategy is to scale the database vertically first and offload traffic with caches and replicas. Sharding comes only once that hits a ceiling.

## Stateless Services — why this matters for horizontal scaling

**Stateless** means an app server holds no user-specific or session-specific state in memory between requests. Any user's request can be handled by **any** instance. That is a prerequisite for a load balancer to distribute traffic freely, and for instances to be added or removed without losing data.

The problem statelessness solves — the classic example:

```txt
❌ Session in memory:
  User → LB → Server A (session stored in RAM)

  The user's next request lands on Server B
  → Server B doesn't know about the session
  → the user appears "logged out"
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

Sticky sessions pin a user to a specific server, usually via a cookie set by the load balancer. Technically this does allow in-memory state, but it is a workaround. It breaks even load distribution and complicates deployments: restarting an instance means losing sessions for everyone pinned to it. Mentioning sticky sessions as "the solution" without noting these downsides is a weak answer.

## Availability, Reliability, and Single Point of Failure (SPOF)

**SPOF** stands for single point of failure. It is any component with no redundancy, so its failure brings down the whole system — or a significant part of it. The classic example is a single database with no replicas: if it goes down, everything depending on it goes down.

Eliminating a SPOF isn't "add another server". It is **replication plus a failover mechanism**. A replica must be ready to take traffic. And there must be a way to detect the primary's failure and switch over, automatically or manually.

**Availability** is measured in "nines" — the fraction of time the system responds correctly. The number a team commits to is written into an SLA (service level agreement):

| SLA | Allowed downtime/year | Allowed downtime/month |
|---|---|---|
| 99% | ~3.65 days | ~7.3 hours |
| 99.9% ("three nines") | ~8.76 hours | ~43.8 minutes |
| 99.99% ("four nines") | ~52.6 minutes | ~4.4 minutes |
| 99.999% ("five nines") | ~5.26 minutes | ~26 seconds |

Senior nuance: each additional "nine" costs **an order of magnitude more** in engineering effort — multi-region setups, active failover, chaos engineering, on-call processes.

So the first question isn't "how do we hit 99.999%". The real question is whether we **need** 99.999% for this product, and what downtime actually costs us.

For an internal dashboard, 99.9% might be overkill. For a payment gateway, 99.9% might not be enough.

## Latency vs Throughput

These are two different performance dimensions, and they are often conflated:

| Metric | What it measures | Why you care |
|---|---|---|
| **Latency** | Time to complete **one** request — 50ms, 100ms, 300ms | The experience of a single user (UX) |
| **Throughput** | Number of operations **per unit of time**: RPS (requests per second), also written QPS (queries per second) | How much resource the whole system needs |

These metrics don't always correlate directly. You can increase throughput via batching, but that increases each individual request's latency, because the request waits for the batch to fill. This is the classic latency versus throughput trade-off.

Senior nuance on latency: **never say "100ms latency" without specifying a percentile**. Average latency can be low while p99 — the 99th percentile, the worst 1% of requests — is ten times higher.

It is p99 that determines how many users actually get a bad experience. At high scale, 1% of 1M requests is 10,000 unhappy users a day.

## CAP Theorem: Availability vs Consistency

CAP stands for consistency, availability and partition tolerance. The theorem says a distributed system can't guarantee all three at once once a **network partition** happens — a break in connectivity between nodes:

```txt
C — Consistency: all nodes see the same data at any given moment
A — Availability: every request gets a response
    (no guarantee the data is current)
P — Partition Tolerance: the system keeps working
    despite a network split between nodes
```

Partition tolerance isn't optional in real distributed systems, because networks eventually fail. So the real choice is between two behaviours during a partition: CP (consistency over availability) and AP (availability over consistency).

- **CP** — during a network split, the system refuses to respond rather than return stale or conflicting data. Example: a bank account balance, limited-stock warehouse inventory.
- **AP** — the system keeps responding even if different nodes temporarily see different data (eventual consistency). Example: a social feed, a like counter, "online/offline" status in chat.

Senior nuance: CAP describes behaviour **during a network partition**. It is not a 24/7 characterization of a system, because in normal operation most systems provide both consistency and availability.

A more practical model is **PACELC** (an extension of CAP). It reads: if Partitioned — Availability or Consistency; Else, in normal operation — Latency or Consistency. PACELC accounts explicitly for the latency/consistency trade-off even when nothing is broken, for example synchronous versus asynchronous replication.

## Read-Heavy vs Write-Heavy systems

The read-to-write ratio drives almost the entire technology stack:

| | Read-heavy | Write-heavy |
|---|---|---|
| Examples | Instagram, YouTube, news sites | Analytics, IoT (internet of things) telemetry, logs, event billing |
| Ratio | reads:writes is often 100:1 or higher | writes and reads are comparable, or writes dominate |
| Storage | Read replicas; data denormalized for read patterns | Write-optimized engines — LSM trees (log structured merge trees), as in Cassandra or RocksDB; often time-series databases |
| Traffic shaping | Aggressive caching, a CDN for static assets | Write batching, queues to smooth out spikes |

Practical takeaway: if you propose PostgreSQL with standard B-tree indexes for a write-heavy system handling millions of writes per second, that's an immediate red flag. Traditional relational databases with B-trees are optimized for reads, not for high-frequency writes.

## Common interview mistakes

- **Jumping straight to a diagram** without clarifying functional and non-functional requirements, and without narrowing scope. This is the most common reason a knowledgeable candidate gets a low System Design score. The interviewer is evaluating the process, not the final picture.

- **Skipping non-functional requirements and scale estimation.** Without numbers you can't justify whether you need a cache, sharding or a queue. "We need Redis because it's fast" is weak. "At 7,000 RPS for reads with a 200:1 read:write ratio, we need a cache in front of the database because..." is strong.

- **Confusing latency and throughput**, or talking about latency without percentiles (p50/p99).

- **Treating CAP as a binary, system-wide choice.** A strong answer shows that the CP/AP choice depends on the **specific type of data**. The same system can be CP for payments and AP for a like counter.

- **Proposing a solution with no alternatives.** A strong answer almost always includes "we could do A (pros/cons) or B (pros/cons); given our requirements, I'd pick...". That demonstrates understanding of trade-offs rather than memorized "correct" architectures.

- **Trying to solve everything at once** — designing a system "with every feature, at any scale". The alternative is iterating: base architecture → identify bottleneck → targeted fix → next bottleneck.
