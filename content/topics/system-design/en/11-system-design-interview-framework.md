# Universal System Design Interview Framework

## What's actually being evaluated

System design is a deliberately open-ended format. There's no "correct" solution, and the interviewer isn't comparing your architecture against some reference diagram in their head. What's evaluated is the **process**: how you turn a vague prompt ("design a chat") into concrete technical decisions, and how you justify each choice along the way.

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

The single biggest mistake that can close the door to a senior signal in the first 2 minutes — a candidate immediately starts drawing components ("okay, we'll need Redis, Kafka, a Load Balancer, sharded Postgres...") **before understanding the problem**. This tells the interviewer: "I have a bag of buzzwords and I'll apply them regardless of context." Confidently naming Kafka for a system doing 10 req/sec isn't a plus — it's a minus: it shows the candidate skipped Step 2 (Scale Estimation) and picks tools by name recognition rather than necessity.

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

This sequence was covered in detail for steps 1-2 in [System Design Fundamentals]. Here the focus is on steps 3-8 and on HOW to apply the framework, not just list the steps: time allocation, typical forks in each step, and why this particular order.

### Time allocation (for a 45-minute interview)

```txt
Requirements + Scale:        5-7 minutes  — do NOT rush this
API + Data Model:            5-8 minutes
High-Level Design:           8-10 minutes
Deep Dive (1-2 components):  15-20 minutes — this decides the outcome
Trade-offs / Q&A:            5 minutes
```

Senior nuance: weaker candidates spend 25 minutes on the high-level diagram and 5 minutes on the deep dive — "wide but shallow." Strong candidates move through the high-level part quickly (these are standard blocks the interviewer has seen a hundred times) and spend the bulk of their time where real expertise shows — the deep dive into a specific problem (as in the case studies: [URL Shortener], [Chat System], [Notification System]).

## Step 1: Requirements Clarification — why this decides half the interview

### Functional Requirements: narrowing scope is part of the task, not a formality

"Design a chat like Slack" doesn't have a single solution, because Slack is dozens of subsystems (messaging, threads, search, integrations, video calls, permissions...). If you DON'T narrow the scope, you simply won't have time to meaningfully cover even one part.

```txt
Weak: "Sure, let's design a chat."
      → immediately starts drawing a diagram "for chat in general"

Strong: "Let me narrow the scope: we'll focus on 1:1 and small-group
        message sending/receiving, including history and online
        status. Search across messages, video calls, and bot
        integrations — I'll put those out of scope unless you
        object. Does that work?"
```

The strong version does two things at once: (1) it demonstrates that the candidate understands the real scale of the system (not attempting to "solve all of Slack in 45 minutes"), and (2) it **hands control back to the interviewer** — if they have a specific deep dive in mind (say, fan-out in groups), they'll adjust the scope right away, not at minute 30 when you've already drawn a diagram for a different problem.

### Non-Functional Requirements: not a checklist of "Latency, Availability, Consistency"

A weak answer lists generic terms. A strong answer ties a specific NFR to a specific architectural consequence for THIS problem:

```txt
Chat:
  - Message durability is critical → persist BEFORE ack (see [Chat System])
  - Latency matters, but "a few hundred ms" is not the same
    as "a financial transaction must be atomic"
  - Ordering within a chat matters → affects message ID choice

Payment system:
  - Consistency is critical → NOT "eventual consistency everywhere",
    specifically: debiting an account must be atomic
    (see CAP/PACELC in [System Design Fundamentals])
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

Many candidates think: "the interviewer said exact math isn't important, so I can skip this step entirely." That's wrong — exact **numbers** don't matter, but **order of magnitude** matters critically, because it shapes the rest of the conversation.

```txt
Example: "how many users are online in chat at once?"

  100 users       → a single server, everything in-memory, no Redis needed
  100,000 users   → need Redis Pub/Sub for cross-server
                    delivery (see [WebSockets])
  100,000,000 users → need WebSocket server sharding,
                    geo-distribution, and presence is no longer
                    "just a Redis SET" — it's its own subsystem
```

The same functional requirement ("show online status") leads to completely different architectures depending on the order of magnitude. If you didn't estimate scale, your high-level diagram isn't anchored to anything — and the interviewer can't verify whether you understand WHY you chose these particular components.

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
    partitioning, see [Database Scaling])
```

The key point — you can now **reference this estimate** in step 5: "given 10K+ req/sec at peak and 70+ TB of data, a single PostgreSQL instance won't keep up — we need at least read replicas, and partitioning by `chat_id` for the larger volumes." Without the estimate, this would be an unjustified architecture "because that's what the textbooks say."

## Step 3: API Design — you don't need full CRUD, you need the key contracts

```http
POST /chats/{chatId}/messages
  Body: { content, clientMessageId }  -- clientMessageId for idempotency!
  Response: { messageId, serverTimestamp, status }

GET /chats/{chatId}/messages?before={messageId}&limit=50
  -- cursor-based pagination (messageId), NOT offset — why this matters below

WS /chats/{chatId}/subscribe
  -- realtime delivery, see [WebSockets]
```

Senior-level details worth calling out:

```txt
- clientMessageId (idempotency key) in the send request —
  otherwise a retried request on timeout creates a duplicate
  message (see idempotency in [Message Queues] / [Notification System])

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

A weak answer lists tables without explaining the **access patterns** these tables need to serve. A strong answer derives the schema FROM access patterns:

```txt
Access pattern: "get the last 50 messages of chat X"
  → this is a range scan
  → needs an index on (chat_id, message_id) or
    (chat_id, created_at)
  → this DIRECTLY influences the partition key choice (chat_id),
    see [Chat System] and [Database Scaling]

Access pattern: "find all chats for a user"
  → needs a separate chat_members (user_id, chat_id) table
    with an index on user_id — a JOIN against messages
    would be expensive
```

```sql
-- NOT just "here are the tables", but tables derived from the
-- access patterns above
messages (
  id BIGINT PRIMARY KEY,       -- snowflake-like, see [Chat System]
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

The framework for this choice was covered in detail in [Database Scaling] (a comparison table by guarantees/access patterns); the key point here is: in an interview, it's wrong to say "I'll choose MongoDB because NoSQL scales better" without identifying WHICH property of the data (does the schema change often? do you need JOINs? does some specific operation need strong consistency?) drove that choice.

## Step 5: High-Level Design — start simple, and say so explicitly

```txt
Baseline template (a starting point for MANY problems):

  Client → Load Balancer → API Servers (stateless) → Database
                                ↓
                              Cache
```

This isn't a "too simple" answer — it's a **deliberate starting point** from which you'll explicitly add complexity, justifying each addition through a bottleneck from step 2 or an NFR from step 1. Saying out loud "I'll start with a simple architecture and add complexity as I identify bottlenecks" is itself a senior signal — it shows that added complexity is NOT automatic, it's justified.

```txt
Examples of explicit "simple → more complex" transitions:

  "We have 73 TB of messages over 5 years (from step 2) →
   a single Postgres won't handle that → partition by chat_id"

  "A heavy operation (report generation) inside a synchronous
   API request would block the thread → move it to a Queue +
   Workers" (see [Message Queues])

  "Realtime message delivery requires a persistent connection →
   add a WebSocket Gateway + Redis Pub/Sub for cross-server
   delivery" (see [WebSockets])
```

The basic building blocks — Redis (cache/sessions/presence/rate limiting), Queue (async work), S3+CDN (static/media), WebSocket (realtime) — were covered in detail in their respective topics ([Caching], [Message Queues], [File Storage and CDN], [WebSockets]). At this step, their role isn't "list everything I know" — it's to **wire in exactly what's justified by the requirements from step 1 and the numbers from step 2**.

## Step 6: Deep Dive — this is where senior vs. mid gets decided

The interviewer almost always steers the deep dive into a specific area — either with an explicit question ("how would you handle duplicate messages on retry?") or non-verbally (lingering on a specific component of the diagram). The candidate's job is to **notice** this signal and go there, rather than continuing to narrate the rest of the diagram.

Typical deep-dive directions and what's expected (covered in depth in the case studies):

```txt
"What if two users do X at the same time?" → race conditions,
  idempotency, distributed locks (see [Caching] — cache
  stampede, [Notification System] — idempotency)

"What if a server crashes mid-operation?" → durability,
  persist/ack ordering (see [Chat System])

"What if the group has 100,000 members?" → fan-out on write
  vs fan-out on read (see [Chat System])

"How do you scale DB reads/writes?" → read replicas →
  cache → sharding, in that order (see [Database Scaling])
```

The most common mistake here is **answering the interviewer's question abstractly** ("well, we could use a distributed lock") without specifics (what kind of lock, on what, what happens if the lock isn't released because of a crash — a TTL on the lock). Specificity is exactly what separates "I've heard this term" from "I understand how this works."

## Step 7: Bottlenecks & Scaling — the order of solutions matters

```txt
"What breaks first if load increases 10x?"
```

A strong answer names a SPECIFIC component from your own diagram (not an abstract "the database" in general, but "this PostgreSQL instance, which handles both reads and writes") and proposes solutions **in order of increasing complexity** — this ordering itself is a senior signal:

```txt
For the DB (see [Database Scaling] for the full breakdown):
  1. Vertical scaling (quick, but has a ceiling)
  2. Indexes (often solves the problem with no architectural change)
  3. Read replicas (for read-heavy workloads)
  4. Cache (Redis) — but careful with invalidation (see [Caching])
  5. Sharding (complex, last resort)

For the API:
  Horizontal scaling — but only if the service is stateless
  (sessions in Redis/JWT, not in-memory)
```

Saying this ordering out loud matters because it demonstrates understanding of the trade-off "the complexity of the solution should match the size of the problem" — proposing sharding for a problem that an index would solve is the same sin as proposing Kafka for 10 req/sec.

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

  Consistency vs Availability (CAP/PACELC) — [System Design Fundamentals]
  Latency vs Consistency (synchronous replication is more expensive)
  Read optimization (denormalization, caching) vs Write complexity
    (invalidation, multiple writes)
  Simplicity (monolith) vs Scalability (microservices) —
    and microservices are NOT a "more correct" architecture,
    just a different set of trade-offs
```

## The final formula for "which architecture would you choose?"

If, at the end, the interviewer asks something like "so what would you pick — SQL or NoSQL / monolith or microservices / synchronous or asynchronous" — a universally strong answer has this structure:

```txt
"It depends on [a specific, measurable requirement].
 If [condition A] — I'd choose [solution 1], because
 [specific trade-off]. If [condition B] — [solution 2].
 Given what we've discussed (the numbers from step 2, the NFRs
 from step 1), I'd lean toward [solution], but I'd revisit that
 if [specific assumption] turns out to be wrong."
```

This isn't "dodging the question" — it's demonstrating that architectural decisions are made based on context, not "best practices in a vacuum." A categorical answer ("always microservices", "NoSQL always scales better") is almost a guaranteed signal of insufficient depth.

## Common interview mistakes

- **Drawing components before clarifying requirements** — Kafka/Redis/Sharding named in the first 2 minutes with no context reads as "a bag of buzzwords," not as a solution to a specific problem.

- **Skipping or rushing Scale Estimation** — without an order of magnitude, you can't justify any later architectural decision, and the interviewer can't verify your calibration.

- **Spending 80% of the time on the high-level diagram** — the interviewer has seen these standard blocks hundreds of times; the value of the answer is in the deep dive, which often ends up with no time left.

- **Ignoring the interviewer's deep-dive signals** — continuing to narrate the whole diagram instead of going where the interviewer is explicitly or implicitly pointing.

- **Abstract answers to deep-dive questions** — "we could use a distributed lock" without details (on what, TTL, what happens on a crash) is indistinguishable from "I've heard of this term."

- **Proposing complex solutions for the wrong scale** — sharding for a system with terabytes when the actual problem is petabytes, microservices for a 3-person team.

- **Categorical answers with no trade-off** — "SQL is better than NoSQL" / "microservices are the modern standard" — without tying it to the specific properties of the problem, this reads as reciting an article rather than engineering reasoning.
