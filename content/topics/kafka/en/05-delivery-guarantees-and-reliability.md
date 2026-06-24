# Delivery Guarantees and Reliability

## Three Delivery Semantics — What They Actually Mean

In Kafka (and distributed systems broadly), three delivery guarantee levels are discussed. It's important to understand that each describes not just the producer or the consumer, but **the entire message journey**: write → storage → read → processing.

### At-Most-Once

A message will be processed **zero or one time**. No duplicates, but loss is possible.

```txt
Producer                Broker              Consumer
   │                       │                    │
   │── send(msg) ─────────►│                    │
   │◄─ ack ───────────────│                    │
   │                       │── deliver(msg) ───►│
   │                       │                    │── processing...
   │                       │                    │   CRASH 💥
   │                       │                    │
   │                       │                    │── restart
   │                       │                    │   reads from offset AFTER msg
   │                       │                    │   → msg is lost permanently
```

When this occurs in Kafka:
- **Producer**: `acks: 0` — doesn't wait for broker acknowledgment
- **Consumer**: `autoCommit: true` + commit fires BEFORE processing finishes
- Consumer reads a message, advances the offset, then crashes — message unprocessed, offset already saved

When appropriate: metrics, click analytics, high-volume logs — where small data loss is acceptable and retry latency is unacceptable.

### At-Least-Once

A message will be processed **one or more times**. No loss, but duplicates are possible.

```txt
Producer                Broker              Consumer
   │                       │                    │
   │── send(msg) ─────────►│                    │
   │                       │── deliver(msg) ───►│
   │                       │                    │── processing success ✓
   │                       │                    │── commit(offset) → CRASH 💥
   │                       │                    │
   │                       │                    │── restart
   │                       │                    │   reads from THE SAME offset
   │                       │                    │── processing again ✓ (duplicate!)
```

When this occurs in Kafka:
- **Producer**: `acks: 1` or `acks: -1` without idempotent — retries can write duplicates
- **Consumer**: `autoCommit: false` + manual commit after processing — crash before commit means the message is re-read

When appropriate: most real-world systems operate on at-least-once, compensating for duplicates with idempotent consumers (see below).

### Exactly-Once

A message will be processed **exactly one time** — no loss and no duplicates.

```txt
In theory:
  Producer ──► Broker ──► Consumer
  Guarantee: every message is written and processed exactly once

  In practice: two mechanisms in combination:
  1. Idempotent Producer + Transactions (on the write side)
  2. Idempotent Consumer (on the read side)
```

Exactly-once is the most complex and costly mode. Kafka implements it through two mechanisms.

## Idempotent Producer — Exactly-Once Writes

An **idempotent producer** can safely retry writes without creating duplicates.

**The problem without an idempotent producer**:

```txt
t=0  Producer sends msg[seq=5]
t=1  Broker writes msg[seq=5], sends ACK
t=2  ACK lost in transit (network blip)
t=3  Producer timeout → retry → sends msg[seq=5] again
t=4  Broker writes msg[seq=5] A SECOND TIME → duplicate in the log
```

**The fix — idempotent producer**:

Kafka assigns each producer a unique **Producer ID (PID)**. Each message gets a monotonically increasing **sequence number** scoped to PID + partition. The broker tracks the last sequence number from each PID and **discards duplicates**:

```txt
t=0  Producer (PID=42) sends msg[seq=5]
t=1  Broker writes msg[PID=42, seq=5], sends ACK
t=2  ACK lost
t=3  Producer retry → sends msg[PID=42, seq=5] again
t=4  Broker sees PID=42, seq=5 — already written → discards, sends ACK
     → no duplicate
```

In kafkajs:

```ts
const producer = kafka.producer({
  idempotent: true,   // enables idempotent producer
  // automatically sets:
  // acks: -1 (all ISRs must confirm)
  // maxInFlightRequests: 5 (no more than 5 unacknowledged requests)
  // retries: Number.MAX_SAFE_INTEGER (unlimited retries)
});
```

**What idempotent producer gives you**: exactly-once writes **to a single partition of a single topic**. Duplicates from retries are eliminated.

**What it does NOT give you**: it doesn't protect against duplicates from consumer processing — that's only half the journey.

## Kafka Transactions — Exactly-Once Across Topics

An idempotent producer eliminates duplicates within a single write operation. But what if you need to atomically write to multiple topics, or atomically process a message and write the result?

**Kafka Transactions** allow you to atomically:
- Read from topic A
- Process the data
- Write the result to topic B
- Commit the offset (mark as processed)

All or nothing — if something goes wrong, the transaction is rolled back.

```txt
Kafka Transactions — conceptually:

  beginTransaction()
    ├── consume(topic: "orders", offset=10)     ← read the order
    ├── produce(topic: "payments", msg=payReq)  ← create the payment request
    └── commitTransaction()                      ← atomically finalize everything

  If crash between produce and commit:
    → transaction is rolled back
    → offset is NOT committed
    → consumer re-reads orders[offset=10]
    → payments never receives a partial result
```

In kafkajs:

```ts
const producer = kafka.producer({
  idempotent: true,
  transactionalId: 'order-payment-processor',  // unique ID for transactions
});

const transaction = await producer.transaction();
try {
  // Write to the result topic
  await transaction.send({
    topic: 'payment-requests',
    messages: [{ key: orderId, value: JSON.stringify(paymentRequest) }],
  });

  // Atomically commit the offset from the input topic
  await transaction.sendOffsets({
    consumerGroupId: 'order-processor',
    topics: [{
      topic: 'order-events',
      partitions: [{ partition, offset: (Number(offset) + 1).toString() }],
    }],
  });

  await transaction.commit();
} catch (err) {
  await transaction.abort();
  throw err;
}
```

**An honest caveat**: Kafka Transactions work at the Kafka → Kafka level. If the result is written to a database or external service, the exactly-once guarantee breaks — the database is not part of the Kafka transaction. In most real-world systems, idempotent consumers are used instead of transactions.

## Idempotent Consumer — The Practical Solution

An **idempotent consumer** is one that, when processing the same message a second time, produces the same result as the first time.

This is the most common approach in real-world systems because:
1. It doesn't require Kafka Transactions (complex to configure)
2. It works even when the result is written to a database or calls an external API
3. It handles at-least-once semantics without duplicate side effects

```ts
// Idempotent handling via PostgreSQL
async function handleOrderPlaced(event: { orderId: string; userId: string; amount: number }) {
  // INSERT OR IGNORE — if orderId already exists, do nothing
  await db.query(`
    INSERT INTO orders (id, user_id, amount, status, created_at)
    VALUES ($1, $2, $3, 'pending', NOW())
    ON CONFLICT (id) DO NOTHING
  `, [event.orderId, event.userId, event.amount]);
  // Calling again with the same orderId → no error, no duplicate
}
```

```ts
// Idempotency via versioning (optimistic locking)
async function handlePaymentCompleted(event: { orderId: string; version: number }) {
  const updated = await db.query(`
    UPDATE orders
    SET status = 'paid', version = $2
    WHERE id = $1 AND version = $2 - 1
  `, [event.orderId, event.version]);

  if (updated.rowCount === 0) {
    // Either already updated (duplicate) or version conflict
    // In both cases — safe to ignore
    return;
  }
}
```

```ts
// Idempotency via a processed_events table
async function processMessageIdempotently(
  messageId: string,
  handler: () => Promise<void>,
) {
  const alreadyProcessed = await db.query(
    'INSERT INTO processed_events (id) VALUES ($1) ON CONFLICT DO NOTHING RETURNING id',
    [messageId],
  );

  if (alreadyProcessed.rowCount === 0) {
    return; // already processed
  }

  await handler();
}

// Usage:
const messageId = `${topic}-${partition}-${offset}`;
await processMessageIdempotently(messageId, () => handleOrderEvent(event));
```

## Poison Message — Handling Messages That Can't Be Processed

A **poison message** is a message the consumer cannot successfully process. Examples: invalid JSON, incompatible schema, an exception in business logic, a dependency on an unavailable service.

**The problem is specific to Kafka**: unlike RabbitMQ, Kafka does not remove a message from the partition. If the consumer crashes during processing and doesn't commit the offset, it will receive the exact same message again on restart. An infinite loop.

```txt
Without poison message handling:

  offset=42: [invalid message]

  Attempt 1: consumer receives offset=42 → exception → restart
  Attempt 2: consumer receives offset=42 → exception → restart
  ...
  Attempt N: same

  → Consumer is stuck at offset=42. The entire partition is frozen.
    Lag grows. New messages don't get processed.
```

### Pattern: Dead Letter Topic (DLT)

A **Dead Letter Topic** is a separate topic where messages that failed processing after N retries are sent. After sending to the DLT, the offset is committed and normal processing continues.

```txt
Normal path:
  [order-events] ──► Consumer ──► processing ──► commit offset

Path for a poison message:
  [order-events] ──► Consumer ──► 3 attempts → failure
                                  │
                                  ▼
                         [order-events.DLT] ──► separate consumer
                                  │              (alerting, manual inspection,
                         commit offset          reprocessing)
```

```ts
// kafka/dead-letter-topic.ts
import { kafka } from './client';

const dlProducer = kafka.producer();
await dlProducer.connect();

export async function sendToDeadLetterTopic(
  originalTopic: string,
  message: { key: Buffer | null; value: Buffer | null; headers?: Record<string, Buffer> },
  error: Error,
  metadata: { partition: number; offset: string },
): Promise<void> {
  await dlProducer.send({
    topic: `${originalTopic}.DLT`,
    messages: [{
      key: message.key,
      value: message.value,
      headers: {
        ...message.headers,
        'dlt-original-topic': Buffer.from(originalTopic),
        'dlt-original-partition': Buffer.from(String(metadata.partition)),
        'dlt-original-offset': Buffer.from(metadata.offset),
        'dlt-error-message': Buffer.from(error.message),
        'dlt-error-type': Buffer.from(error.constructor.name),
        'dlt-failed-at': Buffer.from(new Date().toISOString()),
      },
    }],
  });
}
```

```ts
// Integrating DLT into a consumer with retries
const MAX_RETRIES = 3;

await consumer.run({
  autoCommit: false,
  eachMessage: async ({ topic, partition, message }) => {
    let lastError: Error | undefined;

    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
      try {
        const event = JSON.parse(message.value!.toString());
        await handleOrderEvent(event);

        await consumer.commitOffsets([{
          topic,
          partition,
          offset: (Number(message.offset) + 1).toString(),
        }]);
        return; // success — exit
      } catch (err) {
        lastError = err instanceof Error ? err : new Error(String(err));
        console.warn(`Attempt ${attempt}/${MAX_RETRIES} failed:`, lastError.message);

        if (attempt < MAX_RETRIES) {
          // Exponential backoff before retry
          await new Promise((resolve) => setTimeout(resolve, 100 * 2 ** attempt));
        }
      }
    }

    // All retries exhausted — send to DLT
    console.error('Sending message to DLT after all retries failed');
    await sendToDeadLetterTopic(topic, message, lastError!, { partition, offset: message.offset });

    // Commit offset — so we don't get stuck on this message forever
    await consumer.commitOffsets([{
      topic,
      partition,
      offset: (Number(message.offset) + 1).toString(),
    }]);
  },
});
```

### DLT Consumer — Monitoring and Manual Inspection

```ts
// Separate consumer for the DLT — for alerting and analysis
const dltConsumer = kafka.consumer({ groupId: 'order-events-dlt-monitor' });

await dltConsumer.connect();
await dltConsumer.subscribe({ topics: ['order-events.DLT'], fromBeginning: true });

await dltConsumer.run({
  eachMessage: async ({ message }) => {
    const originalTopic = message.headers?.['dlt-original-topic']?.toString();
    const errorMessage = message.headers?.['dlt-error-message']?.toString();
    const failedAt = message.headers?.['dlt-failed-at']?.toString();

    // Send alert to Slack/PagerDuty
    await alerting.send({
      severity: 'high',
      title: `Poison message in ${originalTopic}`,
      message: `Error: ${errorMessage} at ${failedAt}`,
      payload: message.value?.toString(),
    });
  },
});
```

## Summary: Which Semantics to Use When

```txt
┌──────────────────┬───────────────┬─────────────┬──────────────────────────────────┐
│ Semantics        │ Data Loss     │ Duplicates  │ How to achieve in Kafka          │
├──────────────────┼───────────────┼─────────────┼──────────────────────────────────┤
│ At-most-once     │ Possible      │ No          │ acks:0 or auto-commit            │
│                  │               │             │ before processing                │
├──────────────────┼───────────────┼─────────────┼──────────────────────────────────┤
│ At-least-once    │ No            │ Possible    │ acks:-1 + manual commit          │
│                  │               │             │ after processing (the standard)  │
├──────────────────┼───────────────┼─────────────┼──────────────────────────────────┤
│ Exactly-once     │ No            │ No          │ Idempotent producer +            │
│                  │               │             │ Kafka Transactions (Kafka→Kafka) │
│                  │               │             │ OR at-least-once +               │
│                  │               │             │ idempotent consumer              │
└──────────────────┴───────────────┴─────────────┴──────────────────────────────────┘
```

## Common Interview Traps

**"Exactly-once is just enabling a flag in Kafka"**

No. Exactly-once in Kafka requires a combination: idempotent producer (`idempotent: true`) + transactions (for Kafka→Kafka scenarios). But this only covers writes into Kafka. If the consumer writes results to a database or calls an external API, the database isn't part of the Kafka transaction, and exactly-once is no longer guaranteed. Most teams choose at-least-once + idempotent consumer over Kafka Transactions.

**"At-least-once is unacceptable in production"**

No. At-least-once is the standard in most production systems. With a properly implemented idempotent consumer (ON CONFLICT DO NOTHING, versioning, processed_events table), duplicates don't cause problems. Kafka Transactions add complexity that's only justified in specific scenarios (financial processing, Kafka Streams streaming pipelines).

**"A poison message will just throw an exception and Kafka will handle it"**

No. Kafka has no built-in dead-letter mechanism at the broker level (unlike RabbitMQ). Without explicit handling, a consumer will loop on the same message forever. The DLT pattern is the developer's responsibility, not the broker's.

**"Retry with exponential backoff solves the poison message problem"**

Partially. Retries help with transient failures (network, unavailable services). But if the message contains structurally invalid data, no number of retries will fix it. A DLT is needed precisely for these cases: detect, isolate, investigate manually, without blocking the stream.

**"Idempotent producer eliminates all duplicates"**

No. An idempotent producer eliminates write-side duplicates within a single partition on retry. It does not protect against duplicates during consumer processing — if a consumer processes a message and crashes before committing, it will re-read and re-process it. Consumer idempotency is a separate concern.
