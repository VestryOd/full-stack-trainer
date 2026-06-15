# Message Queues and Event-Driven Architecture

## The core idea: decoupling in time and availability

Without a queue, a synchronous call ties together the lifetime and availability of two services:

```txt
API → Email Service (synchronous HTTP call)

If Email Service is slow → API is slow
If Email Service is down → API fails (or returns an error to the client)
```

With a queue, the producer and consumer are decoupled:

```txt
API → Queue → Email Worker

The API wrote a message to the queue and immediately returned 200 OK.
The Email Worker processes it whenever it can — even if it's
currently down, the message just waits in the queue.
```

This gives four concrete benefits, and in an interview it's important not just to list them but to tie them to a specific scenario:

```txt
Asynchrony       — the client doesn't wait for a long operation's result
Buffering        — a spike of 10,000 requests is "smoothed out" over time
                    for a consumer processing at a constant rate
Failure isolation — a consumer crashing doesn't crash the producer
Independent scaling — you can add more workers
                    without changing the API
```

## Queue vs Pub/Sub vs Event Streaming — different models, not synonyms

This distinction is the most commonly confused, and it fundamentally shapes the architecture:

| | Point-to-Point Queue (SQS, RabbitMQ) | Pub/Sub (SNS, Redis Pub/Sub) | Event Streaming (Kafka, Kinesis) |
|---|---|---|---|
| Who receives the message | **One** consumer (from a group) takes and deletes it | **All** subscribers get a copy | All consumer groups read independently, the message **isn't deleted** after reading |
| Storage after processing | Deleted | Not retained (if no subscriber, it's lost) | Retained for N days/hours (retention), can be "replayed" |
| Ordering | Usually not guaranteed (or FIFO queues with throughput limits) | Not guaranteed | Guaranteed **within a partition** |
| Typical use case | Background tasks (send an email, generate a report) | Notify multiple services about an event | Event sourcing, real-time analytics, event replay |

Senior nuance: an SQS-style "queue" is a **task queue** (a task is processed by exactly one worker and disappears), while Kafka is an **event log** that many consumers can read independently and "replay from the start." Confusing the two is a common design mistake: if multiple services need to know about "UserCreated," a regular queue (where the message disappears after one consumer processes it) doesn't fit — you need Pub/Sub or an event log.

## Fan-Out: one event → many subscribers

```txt
User Service
   │ publishes "UserCreated"
   ▼
 Event Bus / Topic
   ├──→ Email Service     (send a welcome email)
   ├──→ Analytics Service (record analytics)
   └──→ CRM Service        (create a customer record)
```

The key architectural benefit: **the User Service doesn't know** how many subscribers "UserCreated" has or why they need it. Adding a new subscriber (e.g., a Fraud Detection Service) requires no changes to the User Service — this reduces coupling between teams/services far more than direct "just in case" HTTP calls.

## Delivery Guarantees — at-most-once, at-least-once, exactly-once

```txt
At-most-once:  a message is delivered 0 or 1 times.
               Can be lost, but never duplicated.
               (e.g., UDP-like "fire and forget" delivery)

At-least-once: a message is delivered 1 or more times.
               Never lost, but can be duplicated.
               (standard for most queues — SQS, Kafka by default)

Exactly-once:  a message is delivered exactly 1 time.
```

Senior nuance on exactly-once: in distributed systems, **true network-level exactly-once is practically unattainable** — what's marketed as "exactly-once" (e.g., Kafka transactions) is in practice implemented as **at-least-once delivery + idempotent consumer-side processing**, which produces the *effect* of exactly-once. A good answer to "how do you ensure exactly-once" isn't "turn on the exactly-once flag" — it's "design the consumer to be idempotent, because redelivery is inevitable."

### Idempotency — a practical implementation

```ts
// ❌ Not idempotent: reprocessing the same message
// charges the card twice
async function processPayment(message: PaymentMessage): Promise<void> {
  await chargeCard(message.userId, message.amount);
}

// ✅ Idempotent: the idempotency key is checked before the side effect
async function processPaymentIdempotent(message: PaymentMessage): Promise<void> {
  const alreadyProcessed = await db.processedMessages.findUnique({
    where: { messageId: message.id },
  });
  if (alreadyProcessed) {
    return; // already processed — safe no-op
  }

  await db.$transaction(async (tx) => {
    await chargeCard(message.userId, message.amount);
    await tx.processedMessages.create({ data: { messageId: message.id } });
  });
}
```

The key detail: writing to `processedMessages` and the side effect (`chargeCard`) must be atomic (in one transaction, or with compensating logic) — otherwise a new window for duplication opens up between "performed the operation" and "recorded that it was performed."

## Ordering — guarantees that cost something

By default, most queues **don't guarantee ordering** under parallel processing by multiple consumers — two messages about the same user could be processed "out of order" if different workers pick them up.

```txt
Kafka: guarantees ordering ONLY within a single partition.

  Partition key = user_id
  → all events for user_id=42 always land in the same partition
  → processed by one consumer, strictly in order

  But: events for different user_ids can be processed
  in parallel across partitions — ordering between them isn't
  guaranteed (and usually isn't needed)
```

Practical takeaway: if ordering matters ("UserUpdated" must be processed after "UserCreated" for the same user), choose a partition key that ensures related events **always** land in the same partition — usually the entity ID.

## Dead Letter Queue and retry with backoff

```txt
Message → Worker → processing fails
                       ↓
                  Retry with exponential backoff
                  (1s, 2s, 4s, 8s, ...)
                       ↓
              After N failed attempts
                       ↓
                 Dead Letter Queue (DLQ)
```

The DLQ solves a specific problem: a "poison message" — a message that **cannot** be processed due to a data bug (e.g., invalid JSON) — without a DLQ, such a message would retry forever (a retry loop), consuming the consumer's resources and blocking other messages (if the queue is FIFO).

Senior nuance: a DLQ isn't "the end of the story" — it's a signal for **a human or alerting**. Messages in the DLQ need to be monitored — a growing DLQ often means a bug in the consumer code or an incompatible event schema change from the producer.

## Backpressure — what happens when the producer is faster than the consumer

```txt
Producer publishes 10,000 msg/sec
Consumer processes 1,000 msg/sec

→ the queue grows without bound
→ processing latency grows (a message at the back of the queue
  waits longer and longer)
→ in the extreme, the queue exhausts the broker's memory/disk
```

Fixes: add more consumers (horizontal scaling of workers — the "scaling" mentioned at the start), cap the queue size with explicit dropping/error responses back to the producer (backpressure "outward"), or apply rate limiting on the producer side.

## When a queue is the wrong choice

```txt
✅ Good fit:
  - sending email/push notifications
  - generating reports, video processing (long-running operations)
  - syncing data between services (event-driven)
  - smoothing out load spikes (batch order processing)

❌ Bad fit:
  - requests that need an immediate response in the same HTTP cycle
    (e.g., "check item availability before showing the price")
  - real-time chat/gaming — these need WebSocket/direct connections,
    a queue adds latency unacceptable for interactivity
  - operations where ordering and atomicity are critical "out of the box" —
    a synchronous transaction in a single DB is simpler
    than building distributed logic around a queue
```

The main red flag for "don't use a queue here" is when the response to the user **depends** on the operation's result in real time. A queue fits when you can say "got it, we'll process it" (202 Accepted), not when you need "here's the result right now" (200 OK with data).

## Common interview mistakes

- **Confusing a queue with pub/sub** — proposing an SQS-style queue for "multiple services need to know about an event," missing that a point-to-point queue delivers the message to only one consumer.

- **Calling "exactly-once delivery" a solved problem** — without mentioning that in practice it's always at-least-once + idempotency.

- **Not mentioning consumer idempotency at all** — once a queue is on the table, idempotency is a mandatory part of the answer, not an "optional nice-to-have."

- **Assuming Kafka guarantees global ordering** — ordering is only guaranteed within a partition; the partition key choice is a decision that directly affects ordering.

- **Treating the DLQ as "a trash can, and forget about it"** — without monitoring, the DLQ means messages are being silently lost from the team's view.

- **Proposing a queue for synchronous operations** — "check stock before payment via a queue" adds latency and complexity where a direct synchronous request is needed.

- **Not discussing backpressure** — what happens if the producer is consistently faster than the consumer, and how the system degrades (growing latency, queue overflow).
