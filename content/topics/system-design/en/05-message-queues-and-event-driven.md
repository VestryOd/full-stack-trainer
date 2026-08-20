# Message Queues and Event-Driven Architecture

## The core idea: decoupling in time and availability

Without a queue, a synchronous call ties together the lifetime and availability of two services:

```txt
API → Email Service (synchronous HTTP call)

If Email Service is slow → API is slow
If Email Service is down → API fails
  (or returns an error to the client)
```

With a queue, the producer and consumer are decoupled:

```txt
API → Queue → Email Worker

The API wrote a message to the queue
and immediately returned 200 OK.
The Email Worker processes it whenever it can — even if
it's currently down, the message just waits in the queue.
```

This gives four concrete benefits. In an interview it's important not just to list them, but to tie each one to a specific scenario:

- **Asynchrony** — the client doesn't wait for a long operation's result.
- **Buffering** — a spike of 10,000 requests is "smoothed out" over time, for a consumer that processes at a constant rate.
- **Failure isolation** — a consumer crashing doesn't crash the producer.
- **Independent scaling** — you can add more workers without changing the API.

## Queue vs Pub/Sub vs Event Streaming — different models, not synonyms

This distinction is the one most commonly confused, and it fundamentally shapes the architecture. The examples below use Amazon's SQS (Simple Queue Service) and SNS (Simple Notification Service):

| | Point-to-Point Queue (SQS, RabbitMQ) | Pub/Sub (SNS, Redis Pub/Sub) | Event Streaming (Kafka, Kinesis) |
|---|---|---|---|
| Who receives the message | **One** consumer (from a group) takes and deletes it | **All** subscribers get a copy | All consumer groups read independently; the message stays after reading |
| Storage after processing | Deleted | Not retained (if no subscriber, it's lost) | Retained for N days or hours (retention), and can be "replayed" |
| Ordering | Usually not guaranteed, or first-in-first-out (FIFO) queues with throughput limits | Not guaranteed | Guaranteed **within a partition** |
| Typical use case | Background tasks (send an email, generate a report) | Notify multiple services about an event | Event sourcing, real-time analytics, event replay |

Senior nuance: an SQS-style "queue" is a **task queue** — a task is processed by exactly one worker and disappears. Kafka is an **event log** that many consumers can read independently and replay from the start.

Confusing the two is a common design mistake. If several services need to know about "UserCreated", a regular queue doesn't fit, because the message disappears after one consumer processes it. You need Pub/Sub or an event log.

## Fan-Out: one event → many subscribers

One event can feed an email service, an analytics pipeline and a CRM (customer relationship management) system at once:

```txt
User Service
   │ publishes "UserCreated"
   ▼
 Event Bus / Topic
   ├──→ Email Service     (send a welcome email)
   ├──→ Analytics Service (record analytics)
   └──→ CRM Service        (create a customer record)
```

The key architectural benefit: **the User Service doesn't know** how many subscribers "UserCreated" has, or why they need it. Adding a new subscriber — say a fraud detection service — requires no changes to the User Service. That reduces coupling between teams and services far more than direct "just in case" HTTP calls.

## Delivery Guarantees — at-most-once, at-least-once, exactly-once

| Guarantee | What it means | Typical example |
|---|---|---|
| **At-most-once** | Delivered 0 or 1 times: can be lost, but never duplicated | "Fire and forget", like UDP (user datagram protocol) |
| **At-least-once** | Delivered 1 or more times: never lost, but can be duplicated | The standard for most queues — SQS, and Kafka by default |
| **Exactly-once** | Delivered exactly 1 time | Not really achievable — see below |

Senior nuance on exactly-once: in distributed systems, **true network-level exactly-once is practically unattainable**. What is marketed as "exactly-once" — Kafka transactions, for example — is in practice **at-least-once delivery plus idempotent processing on the consumer side**. That combination produces the *effect* of exactly-once.

So a good answer to "how do you ensure exactly-once" isn't "turn on the exactly-once flag". It is "design the consumer to be idempotent, because redelivery is inevitable."

### Idempotency — a practical implementation

```ts
import { db } from './db'; // an already created PrismaClient

interface PaymentMessage { id: string; userId: string; amount: number }

declare function chargeCard(userId: string, amount: number): Promise<void>;

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

The key detail: writing to `processedMessages` and the side effect (`chargeCard`) must be atomic — in one transaction, or with compensating logic. Otherwise a new window for duplication opens between "performed the operation" and "recorded that it was performed".

## Ordering — the guarantee you pay for

By default most queues **don't guarantee ordering** when several consumers process in parallel. Two messages about the same user could be processed out of order if different workers pick them up.

```txt
Kafka guarantees ordering only within a single partition.

  Partition key = user_id
  → all events for user_id=42 always land
    in the same partition
  → processed by one consumer, strictly in order

  But: events for different user_ids can be processed
  in parallel across partitions — ordering between them
  isn't guaranteed (and usually isn't needed)
```

Practical takeaway: sometimes ordering matters. "UserUpdated" must be processed after "UserCreated" for the same user, for instance. Then choose a partition key that makes related events **always** land in the same partition — usually the entity id.

## Dead Letter Queue and retry with backoff

A dead letter queue (DLQ) is where a message ends up once retries have failed:

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

The DLQ solves a specific problem: a "poison message" that **cannot** be processed because of a data bug, for example invalid JSON. Without a DLQ such a message would retry forever, consuming the consumer's resources and blocking other messages if the queue is FIFO.

Senior nuance: a DLQ isn't "the end of the story". It is a signal for **a human or for alerting**. Messages in the DLQ need to be monitored. A growing DLQ often means a bug in the consumer code, or an incompatible event schema change from the producer.

## Backpressure — what happens when the producer is faster than the consumer

```txt
Producer publishes 10,000 msg/sec
Consumer processes 1,000 msg/sec

→ the queue grows without bound
→ processing latency grows (a message at the back
  of the queue waits longer and longer)
→ in the extreme, the queue exhausts
  the broker's memory or disk
```

There are three fixes:

- add more consumers — the horizontal scaling of workers mentioned at the start;
- cap the queue size, with explicit dropping or error responses back to the producer (backpressure "outward");
- apply rate limiting on the producer side.

## When a queue is the wrong choice

```txt
✅ Good fit:
  - sending email/push notifications
  - generating reports, video processing
    (long-running operations)
  - syncing data between services (event-driven)
  - smoothing out load spikes (batch order processing)

❌ Bad fit:
  - requests that need an immediate response in the same
    HTTP cycle (e.g., "check item availability
    before showing the price")
  - real-time chat/gaming — these need WebSocket or direct
    connections, and a queue adds latency unacceptable
    for interactivity
  - operations where ordering and atomicity are critical
    "out of the box" — a synchronous transaction in a
    single database is simpler than building distributed
    logic around a queue
```

The main red flag for "don't use a queue here" is when the response to the user **depends** on the operation's result in real time. A queue fits when you can say "got it, we'll process it" (202 Accepted). It doesn't fit when you need "here's the result right now" (200 OK with data).

## Common interview mistakes

- **Confusing a queue with pub/sub.** A point-to-point queue delivers the message to only one consumer. So proposing an SQS-style queue for "multiple services need to know about an event" is wrong.

- **Calling "exactly-once delivery" a solved problem**, without mentioning that in practice it is always at-least-once plus idempotency.

- **Not mentioning consumer idempotency at all.** Once a queue is on the table, idempotency is a mandatory part of the answer, not an optional extra.

- **Assuming Kafka guarantees global ordering.** Ordering is only guaranteed within a partition, and the partition key choice directly affects it.

- **Treating the DLQ as "a trash can you forget about".** Without monitoring, the DLQ means messages are being silently lost from the team's view.

- **Proposing a queue for synchronous operations** — "check stock before payment via a queue" adds latency and complexity where a direct synchronous request is needed.

- **Not discussing backpressure** — what happens if the producer is consistently faster than the consumer, and how the system degrades (growing latency, queue overflow).
