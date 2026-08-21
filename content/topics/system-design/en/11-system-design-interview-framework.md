# Universal System Design Interview Framework

## What's actually being evaluated

System design is a deliberately open-ended format. There's no "correct" solution, and the interviewer isn't comparing your architecture against some reference diagram in their head. What's evaluated is the **process**: how you turn a vague prompt ("design a chat") into concrete technical decisions. And how you justify each choice along the way.

Concretely, the interviewer is trying to assess three things:

```txt
1. Structured thinking — you don't "shoot" solutions at random,
   you move from requirements to details in a deliberate order

2. Trade-off awareness — for every non-trivial decision you can
   name what you're GIVING UP by choosing it

3. Scale calibration — solutions for a system with 1,000 users
   and a system with 100M users are DIFFERENT, and you choose
   based on real numbers, not "because Kafka sounds impressive"
```

The single biggest mistake can cost the senior signal in the first 2 minutes: the candidate starts drawing components **before understanding the problem**. It sounds like "okay, we'll need Redis, Kafka, a Load Balancer, sharded Postgres...". This tells the interviewer one thing: "I know a list of fashionable tools, and I'll apply them regardless of context."

Confidently naming Kafka for a system doing 10 req/sec isn't a plus — it's a minus. It shows the candidate skipped Step 2 (Scale Estimation). It also shows that tools are picked by name recognition rather than by necessity.

## Overall structure of the answer

```txt
1. Requirements Clarification (Functional + Non-Functional)
        ↓
2. Scale Estimation (back-of-envelope)
        ↓
3. API Design
        ↓
4. Data Model
        ↓
5. High-Level Design (start simple, then add complexity)
        ↓
6. Deep Dive into 1-2 components (wherever the interviewer steers)
        ↓
7. Bottlenecks & Scaling
        ↓
8. Trade-offs (throughout)
```

This article focuses on steps 3-8 and on **how** to apply the framework, not just how to list the steps. That means time allocation, the typical forks inside each step, and why this particular order. Steps 1-2 are covered in detail in the System Design Fundamentals article.

### Time allocation (for a 45-minute interview)

```txt
Requirements + Scale:        5-7 minutes  — do NOT rush this
API + Data Model:            5-8 minutes
High-Level Design:           8-10 minutes
Deep Dive (1-2 components):  15-20 minutes — this decides the outcome
Trade-offs / Q&A:            5 minutes
```

Senior nuance: weaker candidates spend 25 minutes on the high-level diagram and 5 minutes on the deep dive. Such an answer covers a lot of ground, but nothing in any depth.

Strong candidates move through the high-level part quickly, because these are standard blocks the interviewer has seen a hundred times. They spend most of the time where real expertise shows: the deep dive into one specific problem. Three case studies in this topic do exactly that — URL Shortener, Chat System, and Notification System.

## Step 1: Requirements Clarification — why this decides half the interview

### Functional Requirements: narrowing scope is part of the task, not a formality

"Design a chat like Slack" doesn't have a single solution, because Slack is dozens of subsystems (messaging, threads, search, integrations, video calls, permissions...). If you **don't** narrow the scope, you simply won't have time to meaningfully cover even one part.

```txt
Weak: "Sure, let's design a chat."
      → immediately starts drawing a diagram "for chat in general"

Strong: "Let me narrow the scope: we'll focus on 1:1 and small-group
        message sending/receiving, including history and online
        status. Search across messages, video calls, and bot
        integrations — I'll put those out of scope unless you
        object. Does that work?"
```

The strong version does two things at once:

1. It shows that the candidate understands the real scale of the system, and is not trying to "solve all of Slack in 45 minutes".
2. It **hands control back to the interviewer**. If they have a specific deep dive in mind, say fan-out in groups, they will adjust the scope right away. Not at minute 30, when you have already drawn a diagram for a different problem.

### Non-Functional Requirements: not a checklist of "Latency, Availability, Consistency"

A weak answer lists generic terms. A strong answer ties a specific NFR to a specific architectural consequence for **this** problem. NFR is short for non-functional requirement: latency, availability, durability, consistency and the like.

```txt
Chat:
  - Message durability is critical → persist BEFORE ack (see Chat System)
  - Latency matters, but "a few hundred ms" is not the same
    as "a financial transaction must be atomic"
  - Ordering within a chat matters → affects message ID choice

Payment system:
  - Consistency is critical → NOT "eventual consistency everywhere",
    specifically: debiting an account must be atomic
    (see CAP/PACELC in System Design Fundamentals)
  - Availability is secondary to Consistency for this specific
    operation — this is an explicit trade-off worth stating out loud

News Feed:
  - Availability matters more than Consistency — if the feed lags
    by a few seconds, that's not a disaster (unlike "my account
    was debited but the balance didn't update")
```

Each NFR should map to a specific decision later in the conversation — otherwise it's just words. If you said "consistency is critical" and then proposed eventually-consistent replication without discussing the trade-off, the interviewer will notice.

### Common mistake: skipping clarifying questions entirely

A candidate who jumps straight to solving risks solving the wrong problem. But the opposite mistake — asking clarifying questions for 10 minutes without moving forward — is also bad. The balance: 3-5 precise clarifying questions that actually affect the architecture (not "what will the app's logo look like").

## Step 2: Scale Estimation — why numbers matter even when "exact math doesn't matter"

Many candidates think: "the interviewer said exact math isn't important, so I can skip this step entirely." That is wrong. Exact **numbers** don't matter, but the **order of magnitude** matters critically, because it shapes the rest of the conversation.

```txt
Example: "how many users are online in chat at once?"

  100 users       → a single server, everything in-memory, no Redis needed
  100,000 users   → need Redis Pub/Sub for cross-server
                    delivery (see WebSockets and Realtime Systems)
  100,000,000 users → need WebSocket server sharding,
                    geo-distribution, and presence is no longer
                    "just a Redis SET" — it's its own subsystem
```

The same functional requirement ("show online status") leads to completely different architectures depending on the order of magnitude. If you didn't estimate scale, your high-level diagram isn't anchored to anything. And the interviewer can't verify whether you understand **why** you chose these particular components.

### A concrete estimation example (without excessive precision)

```txt
Given (from the interviewer, or a stated assumption):
  10M DAU (daily active users)
  Each user sends ~20 messages per day

Write requests:
  10M * 20 = 200M messages/day
  200M / 86,400 sec ≈ 2,300 req/sec (average)
  Peak (typically 3-5x average) ≈ 10,000 req/sec

Read requests (read:write for chat is often close to 1:1,
unlike social feeds where read:write = 100:1):
  ~10,000-20,000 req/sec read at peak

Storage:
  200M messages/day * ~200 bytes (text + metadata) * 365 * 5 years
  ≈ 200M * 200B * 1825 ≈ 73 TB over 5 years

  → this is already BEYOND the comfort zone of a single
    PostgreSQL node (tens of TB — a reason to discuss
    partitioning, see Database Scaling)
```

TB is short for terabytes. The key point is that you can now **reference the estimate** in step 5. It sounds like this:

> "Given 10K+ req/sec at peak and 70+ TB of data, a single PostgreSQL instance won't keep up. We need at least read replicas, and partitioning by `chat_id` for the larger volumes."

Without the estimate, the same architecture would be unjustified — chosen "because that's what the textbooks say".

## Step 3: API Design — you don't need full CRUD, you need the key contracts

CRUD stands for create, read, update, delete — the four basic operations on a resource.

```http
POST /chats/{chatId}/messages
  Body: { content, clientMessageId }  -- clientMessageId for idempotency!
  Response: { messageId, serverTimestamp, status }

GET /chats/{chatId}/messages?before={messageId}&limit=50
  -- cursor-based pagination (messageId), NOT offset — why this matters below

WS /chats/{chatId}/subscribe
  -- realtime delivery, see WebSockets and Realtime Systems
```

Senior-level details worth calling out:

```txt
- clientMessageId (idempotency key) in the send request —
  otherwise a retried request on timeout creates a duplicate
  message (see idempotency in Message Queues / Notification System)

- Cursor-based pagination (before=messageId), not offset/limit —
  with offset pagination on dynamic data (new messages constantly
  being added), items "shift" between requests and the user sees
  duplicates or gaps

- Explicit fields for the client's consistency expectations:
  status: 'sent' | 'delivered' | 'read' is returned to the client
  so the UI can show the correct icon without an extra request
```

You don't need to design 15 endpoints — 2-4 key ones that reflect the main use cases from the Functional Requirements are enough. The goal of this step is to fix the contract between client and system, which will then drive the Data Model.

## Step 4: Data Model — the main architectural fork often hides here

A weak answer lists tables without explaining the **access patterns** these tables need to serve. A strong answer derives the schema **from** the access patterns:

```txt
Access pattern: "get the last 50 messages of chat X"
  → this is a range scan
  → needs an index on (chat_id, message_id) or
    (chat_id, created_at)
  → this DIRECTLY influences the partition key choice (chat_id),
    see Chat System and Database Scaling

Access pattern: "find all chats for a user"
  → needs a separate chat_members (user_id, chat_id) table
    with an index on user_id — a JOIN against messages
    would be expensive
```

```sql
-- NOT just "here are the tables", but tables derived from the
-- access patterns above
messages (
  id BIGINT PRIMARY KEY,       -- snowflake-like, see Chat System
  chat_id BIGINT NOT NULL,
  sender_id BIGINT NOT NULL,
  content TEXT,
  created_at TIMESTAMP,
  INDEX (chat_id, id)          -- serves access pattern #1
)

chat_members (
  chat_id BIGINT,
  user_id BIGINT,
  PRIMARY KEY (chat_id, user_id),
  INDEX (user_id)               -- serves access pattern #2
)
```

### SQL vs NoSQL — decided on specific properties, not fashion

In an interview it is wrong to say "I'll choose MongoDB because NoSQL scales better". You have to name **which** property of the data drove that choice. Does the schema change often? Do you need JOINs? Does one specific operation need strong consistency? The full framework for this choice, with a comparison table by guarantees and access patterns, is in the Database Scaling article.

## Step 5: High-Level Design — start simple, and say so explicitly

```txt
Baseline template (a starting point for MANY problems):

  Client → Load Balancer → API Servers (stateless) → Database
                                ↓
                              Cache
```

This isn't a "too simple" answer. It is a **deliberate starting point**, from which you add complexity explicitly. Each addition is justified by a bottleneck from step 2 or an NFR from step 1.

Saying out loud "I'll start with a simple architecture and add complexity as I find bottlenecks" is itself a senior signal. It shows that complexity is **not** automatic here — every piece of it is justified.

```txt
Examples of explicit "simple → more complex" transitions:

  "We have 73 TB of messages over 5 years (from step 2) →
   a single Postgres won't handle that → partition by chat_id"

  "A heavy operation (report generation) inside a synchronous
   API request would block the thread → move it to a Queue +
   Workers" (see Message Queues)

  "Realtime message delivery requires a persistent connection →
   add a WebSocket Gateway + Redis Pub/Sub for cross-server
   delivery" (see WebSockets and Realtime Systems)
```

Each basic building block has its own article in this topic:

- Redis — cache, sessions, presence, rate limiting. See Caching.
- A queue — asynchronous work. See Message Queues.
- S3 plus a CDN — static files and media. See File Storage and CDN. S3 is Amazon's object storage, and CDN means content delivery network: a global set of caches sitting close to users.
- WebSocket — realtime delivery. See WebSockets and Realtime Systems.

At this step their role isn't "list everything I know". It is to **wire in exactly what's justified** by the requirements from step 1 and the numbers from step 2.

## Step 6: Deep Dive — this is where senior vs. mid gets decided

The interviewer almost always steers the deep dive into a specific area. Sometimes with an explicit question: "how would you handle duplicate messages on retry?" Sometimes without words, by lingering on one component of the diagram. The candidate's job is to **notice** that signal and go there, instead of narrating the rest of the diagram.

Typical deep-dive directions and what's expected (covered in depth in the case studies):

```txt
"What if two users do X at the same time?" → race conditions,
  idempotency, distributed locks (see Caching — cache
  stampede, Notification System — idempotency)

"What if a server crashes mid-operation?" → durability,
  persist/ack ordering (see Chat System)

"What if the group has 100,000 members?" → fan-out on write
  vs fan-out on read (see Chat System)

"How do you scale DB reads/writes?" → read replicas →
  cache → sharding, in that order (see Database Scaling)
```

The most common mistake here is **answering the interviewer's question abstractly**: "well, we could use a distributed lock." The specifics are missing. What kind of lock, on what key, and what happens if the lock is never released because the holder crashed?

The answer to that last one is a TTL on the lock — a time to live, after which the lock expires by itself. Specificity is exactly what separates "I've heard this term" from "I understand how this works".

## Step 7: Bottlenecks & Scaling — the order of solutions matters

```txt
"What breaks first if load increases 10x?"
```

A strong answer names a **specific** component from your own diagram. Not an abstract "the database" in general, but "this PostgreSQL instance, which handles both reads and writes". Then it proposes solutions **in order of increasing complexity**, and that ordering is itself a senior signal:

```txt
For the DB (see Database Scaling for the full breakdown):
  1. Vertical scaling (quick, but has a ceiling)
  2. Indexes (often solves the problem with no architectural change)
  3. Read replicas (for read-heavy workloads)
  4. Cache (Redis) — but careful with invalidation (see Caching)
  5. Sharding (complex, last resort)

For the API:
  Horizontal scaling — but only if the service is stateless
  (sessions in Redis/JWT, not in-memory)
```

Saying this ordering out loud matters, because it shows one trade-off clearly: the complexity of the solution should match the size of the problem. Proposing sharding for a problem an index would solve is the same mistake as proposing Kafka for 10 req/sec.

## Step 8: Trade-offs — the finishing touch you can't skip

```txt
Weak: "Redis is fast, so we'll use it for caching."

Strong: "Redis gives us low latency for hot data, but introduces
  the cache invalidation problem — if the data changes but the
  cache doesn't update, the user sees stale data. For this
  system that's acceptable, because [specific reason from the NFRs]."
```

Every architectural decision trades one property for another. Stating what you're paying for it isn't "admitting the solution is weak" — it's demonstrating that the choice was deliberate, not the only one you know.

```txt
Common trade-off pairs worth being able to articulate:

  Consistency vs Availability (CAP/PACELC) — System Design Fundamentals
  Latency vs Consistency (synchronous replication is more expensive)
  Read optimization (denormalization, caching) vs Write complexity
    (invalidation, multiple writes)
  Simplicity (monolith) vs Scalability (microservices) —
    and microservices are NOT a "more correct" architecture,
    just a different set of trade-offs
```

## The final formula for "which architecture would you choose?"

At the end the interviewer often asks a direct question. "So what would you pick — SQL or NoSQL? Monolith or microservices? Synchronous or asynchronous?" A universally strong answer has this structure:

```txt
"It depends on [a specific, measurable requirement].
 If [condition A] — I'd choose [solution 1], because
 [specific trade-off]. If [condition B] — [solution 2].
 Given what we've discussed (the numbers from step 2, the NFRs
 from step 1), I'd lean toward [solution], but I'd revisit that
 if [specific assumption] turns out to be wrong."
```

This isn't "dodging the question". It shows that architectural decisions are made from context, not from "best practices in a vacuum". A categorical answer — "always microservices", "NoSQL always scales better" — is almost a guaranteed signal of insufficient depth.

## Common interview mistakes

- **Drawing components before clarifying requirements.** Kafka, Redis and sharding named in the first 2 minutes, with no context, sound like a list of fashionable tools. Not like a solution to a specific problem.

- **Skipping or rushing Scale Estimation.** Without an order of magnitude you can't justify any later architectural decision, and the interviewer can't check your calibration.

- **Spending 80% of the time on the high-level diagram.** The interviewer has seen these standard blocks hundreds of times. The value of the answer is in the deep dive, and there is often no time left for it.

- **Ignoring the interviewer's deep-dive signals** — narrating the whole diagram instead of going where the interviewer points, in words or without them.

- **Abstract answers to deep-dive questions.** "We could use a distributed lock", with no details on what key, what TTL, and what happens on a crash. That is the same as "I've heard of this term".

- **Proposing complex solutions for the wrong scale.** Sharding for a system with terabytes, when the real problem starts at petabytes. Or microservices for a 3-person team.

- **Categorical answers with no trade-off.** "SQL is better than NoSQL", or "microservices are the modern standard". With no tie to the specific properties of the problem, this sounds like reciting an article rather than engineering reasoning.
