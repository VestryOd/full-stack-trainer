# Reliability Patterns

## Delivery guarantees — what the terms actually mean

Three terms come up in every message queue interview. They're often recited as a list without a real understanding of what each requires from your code.

### At-most-once delivery

The broker delivers the message once, possibly not at all. If the consumer crashes before processing, the message is gone.

```txt
Producer ──► Broker ──► Consumer
                         ↓
                    (crashes before processing)
                         ↓
                    Message is lost forever
```

This happens in RabbitMQ when you use `noAck: true`. The broker removes the message from the queue the moment it's delivered — before the consumer has done anything with it.

**When it's acceptable:** Fire-and-forget telemetry, metrics, log shipping — where dropping 0.1% of events is preferable to the complexity of guaranteed delivery.

### At-least-once delivery

The broker delivers the message and waits for an ack. If the consumer crashes or nacks, the message is redelivered. The consumer may process the same message more than once.

```txt
Producer ──► Broker ──► Consumer (processes successfully) ──► ack ──► Broker removes
Producer ──► Broker ──► Consumer (crashes mid-processing)
                              ↓
                    Broker redelivers to another consumer
                         (message processed twice)
```

This is what RabbitMQ gives you with `noAck: false` (the default) and `nack` with `requeue: true` on failure. **This is the guarantee you actually get** — and it means your consumers must be designed to handle duplicates.

### Exactly-once delivery

Each message is processed exactly once, even across crashes and network failures. This sounds ideal but is extremely hard to achieve in distributed systems — it requires coordination between the broker, the consumer, and the storage layer.

```txt
True exactly-once requires:
  - Broker: message must be deduplicated at ingestion
  - Consumer: processing must be atomic with the ack
  - Storage: writes must be idempotent or transactional with the ack
```

**RabbitMQ does not provide exactly-once delivery natively.** Kafka transactions + exactly-once semantics (EOS) bring you closer, but even then, exactly-once is typically achieved at the application level through idempotent consumers — not as a guarantee from the broker itself.

**Practical takeaway:** Design your systems for at-least-once and make your consumers idempotent. This gets you the safety of exactly-once without the complexity.

## Idempotent consumers — the practical path to safety

An **idempotent** consumer produces the same result whether it processes a message once or ten times. This is the standard answer to at-least-once delivery.

### Idempotency via unique messageId

```ts
import { type Channel, type ConsumeMessage } from 'amqplib';
import { redis } from './redis';
import { db } from './db';

async function processOrderPlaced(
  channel: Channel,
  msg: ConsumeMessage,
): Promise<void> {
  const messageId = msg.properties.messageId;
  const event = JSON.parse(msg.content.toString());

  if (!messageId) {
    // No ID to deduplicate on — process and hope for the best,
    // or dead-letter it as malformed
    channel.nack(msg, false, false);
    return;
  }

  // Check if we've already processed this exact message
  const alreadyProcessed = await redis.set(
    `processed:${messageId}`,
    '1',
    'NX',         // only set if Not eXists
    'EX', 86400,  // expire after 24 hours
  );

  if (alreadyProcessed === null) {
    // Redis returned null → key already existed → duplicate
    console.log(`Duplicate message ${messageId}, skipping`);
    channel.ack(msg); // ack it so it leaves the queue
    return;
  }

  // First time we've seen this message — process it
  try {
    await db.orders.updateStatus(event.orderId, 'confirmed');
    await emailService.sendConfirmation(event.customerEmail, event.orderId);
    channel.ack(msg);
  } catch (err) {
    // Processing failed — delete the Redis key so we can retry
    await redis.del(`processed:${messageId}`);
    channel.nack(msg, false, false); // dead-letter after retries exhausted
  }
}
```

### Idempotency via upsert semantics in the DB

For operations that write to a database, design the write itself to be idempotent:

```ts
// ❌ Not idempotent — running twice creates two rows or increments twice
await db.query(
  'INSERT INTO notifications (order_id, sent_at) VALUES ($1, NOW())',
  [orderId],
);

// ✅ Idempotent — ON CONFLICT makes it a no-op if already processed
await db.query(
  `INSERT INTO notifications (order_id, message_id, sent_at)
   VALUES ($1, $2, NOW())
   ON CONFLICT (message_id) DO NOTHING`,
  [orderId, messageId],
);

// ✅ Also idempotent — UPDATE with a guard condition
await db.query(
  `UPDATE orders SET status = 'confirmed'
   WHERE id = $1 AND status = 'pending'`,
  [orderId],
);
```

The database's unique constraint becomes your deduplication mechanism — no Redis required.

## Retry with exponential backoff

`nack` with `requeue: true` retries immediately — the message goes back to the front of the queue and the consumer picks it up again milliseconds later. For transient errors (a downstream service temporarily down, a network blip), you want to wait before retrying.

RabbitMQ doesn't have a built-in retry delay, but you can implement it with a **delayed queue pattern** using TTL + DLQ:

```txt
Main Queue ──(failure)──► Retry Exchange ──► Retry Queue (TTL: 30s)
                                                    │
                                              (TTL expires)
                                                    │
                                                    ▼
                                         Dead Letter → Main Exchange → Main Queue
```

```ts
async function setupRetryTopology(channel: Channel): Promise<void> {
  // Main exchange and queue
  await channel.assertExchange('orders', 'topic', { durable: true });
  await channel.assertQueue('order-processing', {
    durable: true,
    arguments: {
      'x-dead-letter-exchange': 'orders.retry',  // on nack → retry exchange
    },
  });
  await channel.bindQueue('order-processing', 'orders', 'order.placed');

  // Retry exchange and queue — messages sit here for 30s, then go back
  await channel.assertExchange('orders.retry', 'direct', { durable: true });
  await channel.assertQueue('order-processing.retry', {
    durable: true,
    arguments: {
      'x-message-ttl': 30_000,                    // wait 30s
      'x-dead-letter-exchange': 'orders',          // then go back to main exchange
      'x-dead-letter-routing-key': 'order.placed', // with the original routing key
    },
  });
  await channel.bindQueue('order-processing.retry', 'orders.retry', 'order.placed');

  // Final DLQ — after all retries are exhausted
  await channel.assertExchange('orders.dlx', 'direct', { durable: true });
  await channel.assertQueue('orders.dead-letters', { durable: true });
  await channel.bindQueue('orders.dead-letters', 'orders.dlx', 'order.placed');
}
```

```ts
const MAX_RETRIES = 3;

async function processWithRetry(channel: Channel, msg: ConsumeMessage): Promise<void> {
  const retryCount = getRetryCount(msg); // reads x-death[0].count from headers

  try {
    await processOrder(JSON.parse(msg.content.toString()));
    channel.ack(msg);
  } catch (err) {
    if (retryCount >= MAX_RETRIES) {
      // Exhausted retries — send to final DLQ, not back to retry queue
      await republishToDLQ(channel, msg);
      channel.ack(msg); // ack the original so retry queue doesn't re-DLQ it
    } else {
      // nack without requeue → goes to retry exchange (via x-dead-letter-exchange)
      // → sits in retry queue for 30s → returns to main queue
      channel.nack(msg, false, false);
    }
  }
}

function getRetryCount(msg: ConsumeMessage): number {
  const deaths = msg.properties.headers['x-death'] as Array<{ count: number }> | undefined;
  return deaths?.[0]?.count ?? 0;
}

async function republishToDLQ(channel: Channel, msg: ConsumeMessage): Promise<void> {
  channel.publish(
    'orders.dlx',
    'order.placed',
    msg.content,
    { ...msg.properties, headers: { ...msg.properties.headers, 'x-final-failure': true } },
  );
}
```

### Exponential backoff with multiple retry queues

For more granular control, use multiple retry queues with increasing TTLs:

```ts
const RETRY_DELAYS_MS = [5_000, 30_000, 300_000]; // 5s, 30s, 5min

async function setupExponentialRetry(channel: Channel): Promise<void> {
  for (let attempt = 0; attempt < RETRY_DELAYS_MS.length; attempt++) {
    await channel.assertQueue(`order-processing.retry.${attempt}`, {
      durable: true,
      arguments: {
        'x-message-ttl': RETRY_DELAYS_MS[attempt],
        'x-dead-letter-exchange': 'orders',
        'x-dead-letter-routing-key': 'order.placed',
      },
    });
  }
}

// In the consumer: route to the correct retry queue based on attempt number
function getRetryQueueName(retryCount: number): string {
  const idx = Math.min(retryCount, RETRY_DELAYS_MS.length - 1);
  return `order-processing.retry.${idx}`;
}
```

## Publisher confirms — knowing the broker received the message

By default, `channel.publish()` is fire-and-forget at the TCP level — the broker might not have received the message if the connection drops before the buffer flushes. **Publisher confirms** (also called "confirm mode") make the channel wait for an explicit ack from the broker for each published message.

```ts
async function publishWithConfirm(
  channel: Channel,
  exchange: string,
  routingKey: string,
  payload: Buffer,
): Promise<void> {
  // Enable confirm mode — must be done before any publishes on this channel
  await channel.confirmSelect();

  const confirmed = await new Promise<boolean>((resolve) => {
    channel.publish(exchange, routingKey, payload, { persistent: true });

    // waitForConfirms resolves when the broker acks all pending messages
    channel.waitForConfirms()
      .then(() => resolve(true))
      .catch(() => resolve(false));
  });

  if (!confirmed) {
    throw new Error(`Broker rejected message to ${exchange}/${routingKey}`);
  }
}
```

A channel in confirm mode has a performance cost (each message requires a round trip for the ack). For high throughput, batch confirms: publish N messages, then `waitForConfirms()` once.

```ts
// Batch publish with confirm
async function batchPublishWithConfirm(
  channel: Channel,
  messages: Array<{ exchange: string; routingKey: string; payload: Buffer }>,
): Promise<void> {
  await channel.confirmSelect();

  for (const { exchange, routingKey, payload } of messages) {
    channel.publish(exchange, routingKey, payload, { persistent: true });
  }

  // One confirm wait for the whole batch
  await channel.waitForConfirms();
}
```

## The Transactional Outbox Pattern

The most common reliability gap in event-driven systems: you save data to your DB and publish a message in two separate operations. If the process crashes between them, either the DB write happened without the message, or the message was published without the DB write.

```ts
// ❌ Classic race condition — these two operations are NOT atomic
async function placeOrder(orderData: OrderData): Promise<void> {
  await db.orders.create(orderData);         // ← crash here?
  await rabbitmq.publish('order.placed', orderData); // ← or here?
}
```

The **Transactional Outbox** solves this by writing the message to an `outbox` table in the same DB transaction as the business data. A separate relay process reads the outbox and publishes to RabbitMQ.

```sql
-- Migration: create the outbox table
CREATE TABLE outbox (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type  TEXT NOT NULL,
  payload     JSONB NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  published_at TIMESTAMPTZ  -- NULL = not yet published
);
```

```ts
// Step 1: atomic write — business data + outbox entry in one transaction
async function placeOrder(orderData: OrderData): Promise<void> {
  await db.transaction(async (trx) => {
    const order = await trx.orders.create(orderData);

    // Write the event to the outbox — same transaction as the order
    await trx.query(
      `INSERT INTO outbox (event_type, payload) VALUES ($1, $2)`,
      ['order.placed', JSON.stringify({ orderId: order.id, ...orderData })],
    );
  });
  // If either write fails, the whole transaction rolls back — no orphan events
}
```

```ts
// Step 2: relay process — reads outbox and publishes to RabbitMQ
async function relayOutboxMessages(
  db: DatabaseClient,
  channel: Channel,
): Promise<void> {
  await channel.confirmSelect();

  // SELECT FOR UPDATE SKIP LOCKED prevents two relay instances from processing the same row
  const pending = await db.query<OutboxRow>(
    `SELECT * FROM outbox
     WHERE published_at IS NULL
     ORDER BY created_at
     LIMIT 100
     FOR UPDATE SKIP LOCKED`,
  );

  for (const row of pending.rows) {
    channel.publish(
      'orders',
      row.event_type,
      Buffer.from(row.payload),
      { persistent: true, messageId: row.id },
    );
  }

  await channel.waitForConfirms();

  // Mark as published only after broker confirms
  const ids = pending.rows.map((r) => r.id);
  await db.query(
    `UPDATE outbox SET published_at = NOW() WHERE id = ANY($1)`,
    [ids],
  );
}

// Run the relay on an interval
setInterval(() => relayOutboxMessages(db, channel), 1000);
```

The Outbox pattern gives you **exactly-once publishing** (at-least-once to the broker, but the `message_id` on the consumer side handles deduplication) without distributed transactions.

## Poison messages — detecting and handling them

A **poison message** is one that causes the consumer to crash every time it tries to process it — a malformed payload, an unexpected schema version, a bug triggered by specific data. Without a guard, the consumer enters an infinite crash-redeliver cycle.

Detection: `x-death` headers accumulate with each redelivery. When `count` exceeds your threshold, the message is a poison pill.

```ts
async function safeConsume(channel: Channel, msg: ConsumeMessage): Promise<void> {
  const deathCount = getDeathCount(msg);

  if (deathCount >= MAX_RETRIES) {
    // This message has been retried too many times — quarantine it
    await quarantineMessage(msg);
    channel.ack(msg); // remove from queue without requeuing
    return;
  }

  try {
    await processMessage(msg);
    channel.ack(msg);
  } catch (err) {
    const isPoison = isPoisonError(err); // e.g. JSON parse error, schema validation fail

    if (isPoison) {
      // Don't retry a structurally broken message — quarantine immediately
      await quarantineMessage(msg);
      channel.ack(msg);
    } else {
      channel.nack(msg, false, false); // → retry queue
    }
  }
}

async function quarantineMessage(msg: ConsumeMessage): Promise<void> {
  // Store to DB for manual inspection
  await db.query(
    `INSERT INTO quarantined_messages (message_id, queue, payload, headers, quarantined_at)
     VALUES ($1, $2, $3, $4, NOW())`,
    [
      msg.properties.messageId,
      msg.fields.routingKey,
      msg.content.toString(),
      JSON.stringify(msg.properties.headers),
    ],
  );

  // Alert the team
  await alerting.send(`Poison message quarantined: ${msg.properties.messageId}`);
}
```

## Common interview traps

- **"RabbitMQ provides exactly-once delivery"** — it doesn't. RabbitMQ provides at-most-once (with `noAck`) or at-least-once (with acks and nack/requeue). Exactly-once is an application-level concern achieved through idempotent consumers.

- **"I can make a consumer idempotent by checking `if processed then skip` before doing any work"** — the check and the work are two separate operations. If the consumer crashes between the check and the work, the check succeeds next time and the work is skipped. The check must be part of the same atomic operation as the write (DB unique constraint, Redis SET NX + cleanup on failure).

- **"`nack` with `requeue: true` is a safe retry mechanism"** — it retries immediately, with no delay, indefinitely. On a permanent error (bad payload, missing dependency) this creates a tight loop that can saturate the consumer and the broker. Always retry with delay and a maximum retry count.

- **"The Transactional Outbox is overcomplicated — just use a try/catch around the publish"** — a try/catch around the publish doesn't help if the process crashes after the DB write and before the publish runs. The Outbox pattern is the only way to guarantee atomicity between a DB write and a message publish without distributed transactions.

- **"Publisher confirms mean the consumer has processed the message"** — no. Publisher confirms mean the **broker** has received and stored the message. Whether the consumer has processed it is a completely separate concern (that's what consumer acks are for).

- **"Poison messages will eventually be processed if I just retry enough times"** — if a message causes a crash every time, retrying more won't help. Retries are for transient failures; a poison message has a permanent failure cause (usually a bug or a schema mismatch). Detect it early, quarantine it, and fix the root cause.
