# Kafka in Node.js — Practical Guide (kafkajs)

## Installation and Connection

**kafkajs** is the most mature Kafka client for Node.js with built-in TypeScript support.

```bash
npm install kafkajs
```

The `Kafka` object is the entry point from which producers and consumers are created. Create it once and reuse it:

```ts
// kafka/client.ts
import { Kafka, logLevel } from 'kafkajs';

export const kafka = new Kafka({
  clientId: 'order-service',       // identifies the app — visible in broker logs
  brokers: ['localhost:9092'],      // broker list; in prod, list multiple addresses
  logLevel: logLevel.WARN,
});
```

`clientId` is not authentication — it's an observability label visible in broker metrics that helps identify which service is causing issues.

In production, list multiple brokers — the client uses them for cluster discovery (connecting to any single one is enough to learn about the rest):

```ts
brokers: [
  'kafka-1.internal:9092',
  'kafka-2.internal:9092',
  'kafka-3.internal:9092',
],
```

## Producer: Sending Messages

### Basic Initialization

```ts
// kafka/producer.ts
import { kafka } from './client';

const producer = kafka.producer();

export async function startProducer() {
  await producer.connect();
  console.log('Producer connected');
}

export async function stopProducer() {
  await producer.disconnect();
}
```

`producer.connect()` establishes TCP connections to the brokers. Call it once at service startup — creating a producer per request is expensive.

### Sending Without a Key (Round-Robin)

```ts
await producer.send({
  topic: 'user-events',
  messages: [
    { value: JSON.stringify({ type: 'PAGE_VIEW', path: '/home', userId: null }) },
    { value: JSON.stringify({ type: 'PAGE_VIEW', path: '/about', userId: null }) },
  ],
});
```

Appropriate for events where relative ordering doesn't matter: logs, click analytics, metrics.

### Sending With a Key (Ordering Guarantee)

```ts
// kafka/order-producer.ts
import { kafka } from './client';

const producer = kafka.producer();

export async function publishOrderEvent(
  orderId: string,
  event: { type: string; payload: Record<string, unknown> },
) {
  await producer.send({
    topic: 'order-events',
    messages: [
      {
        key: orderId,          // all events for the same order → same partition
        value: JSON.stringify({
          ...event,
          occurredAt: new Date().toISOString(),
        }),
        headers: {
          'content-type': 'application/json',
          'schema-version': '1',
        },
      },
    ],
  });
}

// Usage:
await publishOrderEvent('order-101', { type: 'ORDER_PLACED', payload: { amount: 1500 } });
await publishOrderEvent('order-101', { type: 'PAYMENT_COMPLETED', payload: { method: 'card' } });
await publishOrderEvent('order-101', { type: 'ORDER_SHIPPED', payload: { trackingId: 'TRK-99' } });
```

### Batching: Sending Multiple Messages at Once

A single `send` call can contain an array of messages. Kafka sends them as one batch — far more efficient than N separate calls:

```ts
const events = orders.map((order) => ({
  key: order.id,
  value: JSON.stringify({ type: 'ORDER_PLACED', payload: order }),
}));

await producer.send({ topic: 'order-events', messages: events });
```

### Producer Reliability Settings

```ts
const producer = kafka.producer({
  // acks — how many brokers must confirm the write:
  // 0 = fire-and-forget (fast, but messages can be lost)
  // 1 = leader confirmed (default)
  // -1 / 'all' = leader + all in-sync replicas confirmed (maximum durability)
});

await producer.send({
  topic: 'order-events',
  acks: -1,   // override per individual send
  messages: [{ key: 'order-101', value: '...' }],
});
```

`acks: -1` combined with `idempotent: true` (broker-side setting) provides exactly-once write semantics. Covered in depth in the delivery guarantees article.

## Consumer: Reading Messages

### Basic Initialization

```ts
// kafka/consumer.ts
import { kafka } from './client';

const consumer = kafka.consumer({
  groupId: 'order-processor',   // consumer group name — the critical parameter
});

export async function startConsumer() {
  await consumer.connect();
  await consumer.subscribe({ topics: ['order-events'], fromBeginning: false });
  // fromBeginning: true  → read from the start of the log (replay)
  // fromBeginning: false → read only new messages (default)
}

export async function stopConsumer() {
  await consumer.disconnect();
}
```

`fromBeginning` only applies when the given `groupId` has no saved offset yet. If the group has read the topic before, Kafka resumes from the saved offset regardless of this setting.

### Processing Messages — Basic Pattern

```ts
await consumer.run({
  eachMessage: async ({ topic, partition, message }) => {
    const key = message.key?.toString();
    const value = message.value?.toString();

    if (!value) return;

    const event = JSON.parse(value) as { type: string; payload: unknown };

    console.log({
      topic,
      partition,
      offset: message.offset,   // it's a string, not a number
      key,
      event,
    });

    await handleOrderEvent(event);
    // offset is automatically committed after this function returns
    // (default behavior when autoCommit: true)
  },
});
```

Note: `message.offset` is a **string**, not a number — that's how kafkajs works. Convert when comparing or doing arithmetic: `Number(message.offset)`.

## Auto Commit vs Manual Commit — The Most Important Trade-off

This is the key question for understanding delivery guarantees. Let's break down both modes and their consequences.

### Auto Commit (default)

```ts
const consumer = kafka.consumer({
  groupId: 'order-processor',
});

await consumer.run({
  autoCommit: true,                          // default value
  autoCommitInterval: 5000,                  // commit every 5 seconds
  autoCommitThreshold: 100,                  // or every 100 messages
  eachMessage: async ({ message }) => {
    await handleOrderEvent(JSON.parse(message.value!.toString()));
  },
});
```

**How it works**: kafkajs periodically commits the current offset automatically (by timer or message count), independent of whether processing succeeded.

```txt
Auto Commit — message loss scenario:

t=0s   Consumer receives msg[offset=10]
t=1s   Consumer receives msg[offset=11]
t=2s   Consumer receives msg[offset=12]
t=3s   Consumer receives msg[offset=13]
t=4s   Consumer receives msg[offset=14]
t=5s   AUTO COMMIT → offset=14 saved in Kafka
t=5.5s Consumer receives msg[offset=15]
t=5.8s AUTO COMMIT → offset=15 saved (committed BEFORE processing finishes!)
t=6s   Consumer crashes mid-processing of offset=15

→ Consumer restarts, reads from offset=16 ✗ (offset=15 is LOST!)
```

Auto commit gives **at-most-once** semantics: a message can be lost if the commit happens before processing completes. Acceptable for non-critical data (analytics, metrics) where occasional loss is tolerable.

### Manual Commit — At-Least-Once Semantics

```ts
const consumer = kafka.consumer({ groupId: 'order-processor' });

await consumer.run({
  autoCommit: false,   // disable auto-commit
  eachMessage: async ({ topic, partition, message }) => {
    const event = JSON.parse(message.value!.toString());

    try {
      await handleOrderEvent(event);

      // Commit AFTER successful processing
      await consumer.commitOffsets([{
        topic,
        partition,
        offset: (Number(message.offset) + 1).toString(),
        // +1: offset means "the next message to read"
      }]);
    } catch (err) {
      // Don't commit — message will be re-read after restart
      console.error('Failed to process message, will retry:', err);
      throw err; // kafkajs stops processing
    }
  },
});
```

```txt
Manual Commit — at-least-once:

t=0s   Consumer receives msg[offset=15]
t=1s   handleOrderEvent() completes successfully
t=1s   commitOffsets([offset=16]) → offset saved
t=2s   Consumer receives msg[offset=16]
t=2.5s Consumer crashes mid-way through handleOrderEvent()

→ Restart: reads from offset=16 (15 was committed, 16 was not)
→ offset=16 will be processed again ✓ (at-least-once)
→ No loss, but duplicate processing is possible
```

**Why offset + 1?** In Kafka, "committing offset X" means "the next message for me is X" — i.e., X-1 has already been processed. A common mistake is committing the current offset, which causes one message to always be re-read on restart.

### eachBatch — Manual Commit for Batches

```ts
await consumer.run({
  autoCommit: false,
  eachBatch: async ({ batch, resolveOffset, heartbeat, commitOffsetsIfNecessary }) => {
    for (const message of batch.messages) {
      const event = JSON.parse(message.value!.toString());
      await handleOrderEvent(event);

      resolveOffset(message.offset);    // mark this offset as processed
      await heartbeat();                 // prevent the broker from considering
                                         // the consumer dead during long batch processing
    }

    await commitOffsetsIfNecessary();   // commit all resolveOffset'd offsets
  },
});
```

`eachBatch` gives more control: commit in chunks, call `heartbeat()` during long processing (important if batch processing exceeds `session.timeout.ms`).

## Consumer Group Configuration

```ts
const consumer = kafka.consumer({
  groupId: 'order-processor',

  sessionTimeout: 30000,          // ms: no heartbeat within this → consumer is dead (default: 30000)
  heartbeatInterval: 3000,        // ms: how often to send heartbeat (default: 3000)
  maxBytesPerPartition: 1048576,  // bytes: max data per fetch from one partition (1MB)
  minBytes: 1,                    // wait for at least 1 byte before broker responds
  maxBytes: 10485760,             // total fetch limit (10MB)
  maxWaitTimeInMs: 5000,          // wait up to 5s if data is less than minBytes
  retry: {
    initialRetryTime: 100,        // initial retry pause (ms)
    retries: 8,                   // number of retry attempts
  },
});
```

The critical parameter is `sessionTimeout`. If processing a single message (or batch) takes longer than `sessionTimeout` without calling `heartbeat()`, the broker considers the consumer dead and triggers a rebalance. In `eachBatch`, always call `heartbeat()` inside the loop.

## Consumer Lag — Tracking Backlog

**Consumer lag** is the difference between the latest offset in a partition (end of the log) and the group's current committed offset. Lag = 0 means the consumer is keeping up in real time.

```txt
Topic "order-events", Partition 0:
  Latest offset in partition: 1050 (written by producer)
  Group's current offset:      980 (processed up to here)
  
  Consumer Lag = 1050 - 980 = 70 messages
```

High and growing lag signals the consumer can't keep up with the load.

### Monitoring Lag in Code

```ts
// kafka/lag-monitor.ts
import { kafka } from './client';

const admin = kafka.admin();

export async function getConsumerLag(
  groupId: string,
  topic: string,
): Promise<{ partition: number; lag: number }[]> {
  await admin.connect();

  const [offsets, groupOffsets] = await Promise.all([
    admin.fetchTopicOffsets(topic),
    admin.fetchOffsets({ groupId, topics: [topic] }),
  ]);

  const groupTopic = groupOffsets.find((t) => t.topic === topic);
  if (!groupTopic) return [];

  const result = offsets.map(({ partition, offset: latestOffset }) => {
    const groupPartition = groupTopic.partitions.find((p) => p.partition === partition);
    const committedOffset = Number(groupPartition?.offset ?? '0');
    const latest = Number(latestOffset);
    return { partition, lag: Math.max(0, latest - committedOffset) };
  });

  await admin.disconnect();
  return result;
}

// Usage:
const lag = await getConsumerLag('order-processor', 'order-events');
console.log(lag);
// [{ partition: 0, lag: 12 }, { partition: 1, lag: 0 }, { partition: 2, lag: 45 }]
```

In production, lag is typically monitored via Prometheus + kafkajs built-in events, or external tools: Kafka UI, Redpanda Console, Burrow, Datadog.

### Built-in kafkajs Events

```ts
consumer.on(consumer.events.FETCH, (event) => {
  // Called after each poll — contains number of messages fetched
  console.log(`Fetched ${event.payload.numberOfBatches} batches`);
});

consumer.on(consumer.events.COMMIT_OFFSETS, (event) => {
  // Track commits
  console.log('Offsets committed:', event.payload.offsetsCommitted);
});
```

## Complete Example: Order Processing Service

```ts
// services/order-consumer.service.ts
import { kafka } from '../kafka/client';
import { OrderRepository } from '../repositories/order.repository';
import { NotificationService } from './notification.service';

type OrderEvent =
  | { type: 'ORDER_PLACED'; payload: { orderId: string; userId: string; amount: number } }
  | { type: 'PAYMENT_COMPLETED'; payload: { orderId: string; method: string } }
  | { type: 'ORDER_SHIPPED'; payload: { orderId: string; trackingId: string } };

const consumer = kafka.consumer({ groupId: 'order-processor' });

async function handleEvent(event: OrderEvent): Promise<void> {
  switch (event.type) {
    case 'ORDER_PLACED':
      await OrderRepository.create(event.payload);
      await NotificationService.sendOrderConfirmation(event.payload.userId);
      break;
    case 'PAYMENT_COMPLETED':
      await OrderRepository.markPaid(event.payload.orderId);
      break;
    case 'ORDER_SHIPPED':
      await OrderRepository.updateTracking(event.payload.orderId, event.payload.trackingId);
      await NotificationService.sendShippingNotification(event.payload.orderId);
      break;
    default:
      // unknown type — log, don't crash
      console.warn('Unknown event type:', (event as { type: string }).type);
  }
}

export async function startOrderConsumer(): Promise<void> {
  await consumer.connect();
  await consumer.subscribe({ topics: ['order-events'], fromBeginning: false });

  await consumer.run({
    autoCommit: false,
    eachMessage: async ({ topic, partition, message }) => {
      const raw = message.value?.toString();
      if (!raw) return;

      let event: OrderEvent;
      try {
        event = JSON.parse(raw) as OrderEvent;
      } catch {
        // invalid JSON — log and skip (poison message)
        console.error('Invalid JSON in message, skipping:', { topic, partition, offset: message.offset });
        await consumer.commitOffsets([{
          topic,
          partition,
          offset: (Number(message.offset) + 1).toString(),
        }]);
        return;
      }

      await handleEvent(event);

      await consumer.commitOffsets([{
        topic,
        partition,
        offset: (Number(message.offset) + 1).toString(),
      }]);
    },
  });
}

export async function stopOrderConsumer(): Promise<void> {
  await consumer.disconnect();
}
```

## Graceful Shutdown

Without a graceful shutdown, the consumer doesn't commit the last offset in time, and the next startup re-reads already-processed messages:

```ts
// main.ts
import { startOrderConsumer, stopOrderConsumer } from './services/order-consumer.service';

async function main() {
  await startOrderConsumer();
  console.log('Order consumer started');

  const shutdown = async (signal: string) => {
    console.log(`Received ${signal}, shutting down gracefully...`);
    await stopOrderConsumer();   // disconnect commits pending offsets
    process.exit(0);
  };

  process.on('SIGTERM', () => shutdown('SIGTERM'));  // Kubernetes pod stop
  process.on('SIGINT', () => shutdown('SIGINT'));    // Ctrl+C
}

main().catch(console.error);
```

## Common Interview Traps

**"Auto commit is the same as at-least-once"**

No. Auto commit by default gives **at-most-once**: if the commit fires before processing finishes and the consumer crashes, the message is lost. At-least-once requires manual commit AFTER successful processing.

**"Manual commit prevents duplicates"**

No. Manual commit gives at-least-once — if the consumer crashes after processing but before committing, the message will be re-read. Duplication is possible. Exactly-once requires idempotent processing on the consumer side (e.g., `ON CONFLICT DO NOTHING` in PostgreSQL) or Kafka transactions.

**"`commitOffsets([{ offset: message.offset }])` is correct"**

Almost. You need offset + 1: `{ offset: (Number(message.offset) + 1).toString() }`. Committing offset X tells Kafka "the next message for me is X," meaning X-1 has been processed. A common bug: committing the current offset causes one message to always be re-read on restart.

**"You can create a new producer or consumer per HTTP request"**

No. `connect()` establishes TCP connections to brokers — an expensive operation. Create producers and consumers once at service startup and reuse them.

**"`fromBeginning: true` always reads from the start"**

No. `fromBeginning` only applies when the given `groupId` has no saved offset (new group or new topic). If an offset is already committed, Kafka resumes from it — `fromBeginning` is ignored. To force a replay, reset the offset via the Admin API.
