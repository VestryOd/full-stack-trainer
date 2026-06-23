# RabbitMQ in Node.js

## Setting up amqplib

`amqplib` is the standard Node.js AMQP 0-9-1 client. It has two APIs: a callback-based one (`amqplib/callbacks`) and a Promise-based one (`amqplib`). Always use the Promise-based API with `async/await`.

```bash
npm install amqplib
npm install --save-dev @types/amqplib
```

A production-ready connection setup requires handling reconnection and errors — the naive approach of one `connect()` call will crash your process on network interruption:

```ts
import amqplib, { type Connection, type Channel } from 'amqplib';

interface RabbitMQClient {
  connection: Connection;
  channel: Channel;
}

async function createRabbitMQClient(url: string): Promise<RabbitMQClient> {
  const connection = await amqplib.connect(url);
  const channel = await connection.createChannel();

  // Surface errors — without these, silent failures crash the process
  connection.on('error', (err) => console.error('RabbitMQ connection error:', err));
  connection.on('close', () => console.warn('RabbitMQ connection closed'));

  return { connection, channel };
}
```

In production apps (especially NestJS or Express services), you'd wrap this in a singleton service with reconnection logic. Libraries like `amqp-connection-manager` handle reconnection automatically — we'll cover that in article 04.

## Declaring topology: assertExchange, assertQueue, bindQueue

Before publishing or consuming, you must declare the topology (exchanges, queues, bindings). The key method is `assert*` — it creates the resource if it doesn't exist, or verifies it matches if it does. Using the wrong settings on an existing queue throws a channel-level error.

```ts
async function setupTopology(channel: Channel): Promise<void> {
  // Declare exchange
  await channel.assertExchange('orders', 'topic', {
    durable: true,      // survives restart
    autoDelete: false,  // don't delete when no queues are bound
  });

  // Declare queue
  await channel.assertQueue('order-email-notifications', {
    durable: true,
    arguments: {
      'x-dead-letter-exchange': 'orders.dlx',  // dead-letter destination
      'x-message-ttl': 300_000,                // 5-minute TTL
    },
  });

  // Bind: route 'order.*' events to this queue
  await channel.bindQueue('order-email-notifications', 'orders', 'order.*');
}
```

A key nuance: both the producer service and the consumer service should call `assertExchange` and `assertQueue`. The calls are idempotent — if the topology already exists with identical settings, the call is a no-op. This way either service can start first without errors.

## Publishing messages

```ts
interface OrderPlacedEvent {
  orderId: string;
  customerEmail: string;
  items: Array<{ sku: string; quantity: number; price: number }>;
  totalAmount: number;
  createdAt: string;
}

function publishOrderPlaced(channel: Channel, event: OrderPlacedEvent): boolean {
  const payload = Buffer.from(JSON.stringify(event));

  return channel.publish(
    'orders',           // exchange
    'order.placed',     // routing key
    payload,
    {
      persistent: true,                    // write to disk — survives restart
      contentType: 'application/json',     // convention, not enforced by RabbitMQ
      messageId: crypto.randomUUID(),      // useful for deduplication
      timestamp: Math.floor(Date.now() / 1000),
      headers: {
        'x-service': 'order-service',     // custom headers for tracing/routing
      },
    },
  );
  // Returns false if the internal write buffer is full (backpressure signal)
  // When false: stop publishing until the 'drain' event fires on the channel
}
```

`channel.publish()` returns `false` when the channel's internal write buffer is full. This is RabbitMQ's backpressure signal — if you ignore it and keep publishing, you'll exhaust memory. The correct response:

```ts
async function publishWithBackpressure(
  channel: Channel,
  exchange: string,
  routingKey: string,
  payload: Buffer,
  options: amqplib.Options.Publish,
): Promise<void> {
  const canSend = channel.publish(exchange, routingKey, payload, options);

  if (!canSend) {
    // Wait for the channel to drain before continuing
    await new Promise<void>((resolve) => channel.once('drain', resolve));
  }
}
```

## Consuming messages and acknowledgements

This is where most of the complexity lives. A consumer subscribes to a queue and receives messages via a callback. The critical decision after processing each message: **acknowledge** (tell RabbitMQ "done, remove it") or **reject** (tell RabbitMQ "failed, what should you do with it").

```ts
async function startEmailConsumer(channel: Channel): Promise<void> {
  // Set prefetch BEFORE consuming — critical for performance and fairness
  await channel.prefetch(10); // max 10 unacknowledged messages at a time

  await channel.consume('order-email-notifications', async (msg) => {
    if (msg === null) {
      // null means the consumer was cancelled (e.g., queue deleted)
      console.warn('Consumer cancelled by broker');
      return;
    }

    const event = JSON.parse(msg.content.toString()) as OrderPlacedEvent;

    try {
      await emailService.sendOrderConfirmation(event.customerEmail, event.orderId);

      // ✅ Success: remove from queue
      channel.ack(msg);
    } catch (err) {
      console.error('Failed to send email:', err);

      const isRetryable = isTransientError(err);
      const retryCount = (msg.properties.headers['x-retry-count'] as number) ?? 0;

      if (isRetryable && retryCount < 3) {
        // ❌ Reject and requeue — RabbitMQ will redeliver
        // WARNING: without a delay this creates a tight loop
        channel.nack(msg, false, true);  // (msg, multiple, requeue)
      } else {
        // ❌ Reject without requeue — goes to dead-letter queue (if configured)
        channel.nack(msg, false, false);
      }
    }
  }, {
    noAck: false,  // NEVER set to true in production — you'll lose messages on crash
  });
}
```

### The three acknowledgement methods

```ts
// ACK — success, remove the message from the queue
channel.ack(msg);
channel.ack(msg, true);  // allUpTo: true — ack this AND all previously delivered messages

// NACK — failure, with a choice
channel.nack(msg, false, true);   // requeue: true  — redeliver to this queue
channel.nack(msg, false, false);  // requeue: false — discard or dead-letter

// REJECT — same as nack but only for a single message (no allUpTo)
channel.reject(msg, true);   // requeue
channel.reject(msg, false);  // dead-letter or discard
```

`nack` with `requeue: true` is dangerous without a delay — the message immediately goes back to the front of the queue and gets redelivered, potentially thousands of times per second. The right pattern for retries with backoff is covered in article 04.

### noAck mode — when it's appropriate

```ts
// noAck: true — RabbitMQ removes the message the moment it delivers it
// The consumer never sends an ack
channel.consume('analytics-events', (msg) => {
  if (msg) analyticsService.record(msg.content.toString());
}, { noAck: true });
```

`noAck: true` makes sense **only** when losing messages is acceptable — for fire-and-forget analytics, metrics, or logging where you'd rather have throughput than guaranteed delivery. Never use it for business-critical operations.

## Prefetch count — the most important tuning knob

Without prefetch, RabbitMQ delivers all queued messages to the consumer as fast as possible. If the queue has 50,000 messages and the consumer processes them slowly, all 50,000 land in the consumer's memory at once — you've effectively moved the queue from RabbitMQ's managed storage to your application's heap.

```ts
// Without prefetch: broker sends ALL messages at once
// With prefetch: broker holds messages until consumer acks and has capacity
await channel.prefetch(10);

// Per-consumer vs per-channel prefetch
await channel.prefetch(10);          // per-consumer (default)
await channel.prefetch(100, true);   // per-channel (across all consumers on this channel)
```

How to choose the prefetch value:

```txt
Prefetch = 1:
  ✓ Perfectly fair — each consumer processes one message at a time
  ✗ High latency: consumer must ack before getting the next message
  ✗ Low throughput: no pipeline parallelism
  Good for: heavy, slow tasks where you want strict ordering per consumer

Prefetch = 10–50:
  ✓ Good balance for most workloads
  ✓ Allows pipeline parallelism within the consumer
  ✓ Still limits memory impact
  Good for: typical background job processing

Prefetch = 100+:
  ✓ High throughput when processing is fast
  ✗ More messages buffered in consumer memory
  ✗ On consumer crash, more messages need redelivery
  Good for: fast, I/O-light consumers
```

## Dead Letter Queues (DLQ)

A Dead Letter Queue (DLQ) is where messages go when they can't be processed. A message becomes a "dead letter" in three cases:
1. It's rejected with `requeue: false` (`nack` or `reject`)
2. Its TTL (time-to-live) expires before a consumer processes it
3. The queue reaches its `x-max-length` limit and the message is dropped

```ts
async function setupWithDeadLetter(channel: Channel): Promise<void> {
  // 1. Declare the dead letter exchange
  await channel.assertExchange('orders.dlx', 'direct', { durable: true });

  // 2. Declare the dead letter queue
  await channel.assertQueue('orders.dead-letters', { durable: true });

  // 3. Bind DLQ to DLX
  await channel.bindQueue('orders.dead-letters', 'orders.dlx', 'order-emails');

  // 4. Declare the main queue with DLX configured
  await channel.assertQueue('order-email-notifications', {
    durable: true,
    arguments: {
      'x-dead-letter-exchange': 'orders.dlx',       // where dead letters go
      'x-dead-letter-routing-key': 'order-emails',   // routing key in the DLX
      'x-message-ttl': 300_000,                      // 5 min TTL
    },
  });
}
```

When a message lands in the DLQ, RabbitMQ adds headers automatically:

```ts
// In the DLQ consumer, these headers tell you WHY the message died
channel.consume('orders.dead-letters', (msg) => {
  if (!msg) return;

  const deathInfo = msg.properties.headers['x-death'] as Array<{
    queue: string;
    reason: 'rejected' | 'expired' | 'maxlen';
    count: number;
    time: Date;
    exchange: string;
    'routing-keys': string[];
  }>;

  console.error('Dead letter received:', {
    reason: deathInfo[0].reason,
    originalQueue: deathInfo[0].queue,
    retryCount: deathInfo[0].count,
    payload: msg.content.toString(),
  });

  // Common DLQ strategies:
  // 1. Alert + manual inspection
  // 2. Store to DB for analysis
  // 3. Retry with exponential backoff (re-publish to original queue with delay)
  channel.ack(msg);
});
```

## A complete producer + consumer example

This ties together everything above into a pattern you'd actually use in a Node.js microservice:

```ts
// rabbitmq.ts — shared setup
import amqplib, { type Channel, type Connection } from 'amqplib';

const RABBITMQ_URL = process.env.RABBITMQ_URL ?? 'amqp://localhost';

let connection: Connection | null = null;
let publisherChannel: Channel | null = null;

export async function getPublisherChannel(): Promise<Channel> {
  if (!connection) {
    connection = await amqplib.connect(RABBITMQ_URL);
  }
  if (!publisherChannel) {
    publisherChannel = await connection.createChannel();
  }
  return publisherChannel;
}

export async function setupTopology(channel: Channel): Promise<void> {
  await channel.assertExchange('orders', 'topic', { durable: true });
  await channel.assertExchange('orders.dlx', 'direct', { durable: true });

  await channel.assertQueue('orders.dead-letters', { durable: true });
  await channel.bindQueue('orders.dead-letters', 'orders.dlx', 'order-emails');

  await channel.assertQueue('order-email-notifications', {
    durable: true,
    arguments: {
      'x-dead-letter-exchange': 'orders.dlx',
      'x-dead-letter-routing-key': 'order-emails',
    },
  });
  await channel.bindQueue('order-email-notifications', 'orders', 'order.placed');
}
```

```ts
// order-service/producer.ts
import { getPublisherChannel, setupTopology } from './rabbitmq';

export async function publishOrderPlaced(orderId: string, email: string): Promise<void> {
  const channel = await getPublisherChannel();
  await setupTopology(channel);

  const event = { orderId, customerEmail: email, createdAt: new Date().toISOString() };

  channel.publish(
    'orders',
    'order.placed',
    Buffer.from(JSON.stringify(event)),
    { persistent: true, messageId: crypto.randomUUID() },
  );
}
```

```ts
// email-service/consumer.ts
import amqplib from 'amqplib';
import { setupTopology } from './rabbitmq';

async function startConsumer(): Promise<void> {
  const connection = await amqplib.connect(process.env.RABBITMQ_URL ?? 'amqp://localhost');
  const channel = await connection.createChannel();

  await setupTopology(channel);
  await channel.prefetch(5);

  console.log('Email consumer started');

  await channel.consume('order-email-notifications', async (msg) => {
    if (!msg) return;

    try {
      const event = JSON.parse(msg.content.toString());
      await sendEmail(event.customerEmail, `Order ${event.orderId} confirmed`);
      channel.ack(msg);
    } catch (err) {
      // Non-retryable: dead-letter it
      channel.nack(msg, false, false);
    }
  });
}

startConsumer().catch(console.error);
```

## Graceful shutdown

A consumer that exits without acking in-flight messages causes those messages to be redelivered — which is fine. But abruptly killing the connection while mid-processing can leave messages in a half-processed state depending on your business logic. The clean pattern:

```ts
async function startWithGracefulShutdown(): Promise<void> {
  const connection = await amqplib.connect('amqp://localhost');
  const channel = await connection.createChannel();
  let isShuttingDown = false;

  const shutdown = async () => {
    if (isShuttingDown) return;
    isShuttingDown = true;

    console.log('Shutting down consumer...');

    // Cancel the consumer — broker stops delivering new messages
    await channel.cancel('my-consumer-tag');

    // Wait a moment for in-flight messages to finish
    await new Promise((resolve) => setTimeout(resolve, 2000));

    await channel.close();
    await connection.close();
    process.exit(0);
  };

  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);

  await channel.consume('my-queue', async (msg) => {
    if (msg && !isShuttingDown) {
      await processMessage(msg);
      channel.ack(msg);
    }
  }, { consumerTag: 'my-consumer-tag' });
}
```

## Common interview traps

- **`noAck: true` for everything because acks add overhead"** — this loses messages permanently when the consumer crashes mid-processing. The overhead of acknowledgements is negligible compared to your actual processing work. Only skip acks for truly disposable data.

- **"Prefetch doesn't matter, it's a minor optimization"** — it's not optional in production. Without it, a queue with a backlog delivers everything to the first consumer that connects, overwhelming it. Prefetch is what makes competing consumers actually share load fairly.

- **"I should always `nack` with `requeue: true` on failure"** — this creates an infinite redelivery loop when the message itself is malformed (a "poison message"). The right pattern is: track retry count in headers, `nack` with requeue for transient errors up to a limit, then dead-letter it. Never blind-retry forever.

- **"I can use one channel for publishing in multiple goroutines/async operations simultaneously"** — channels in amqplib are not concurrency-safe. Concurrent `channel.publish()` calls from multiple async operations can interleave, causing protocol errors. Use one channel per async context, or serialize access.

- **"Dead letter queue is the same as retry queue"** — they serve different purposes. DLQ is a final destination for messages that have exhausted all processing attempts; a retry queue is a temporary stop with a delay before redelivery. Some retry patterns use both (retry queue → after N retries → DLQ).

- **Not awaiting `channel.assertQueue` / `channel.assertExchange`** — these return Promises. If you don't `await` them, the queue might not exist yet when the first message is published, silently dropping it (or throwing an error that crashes the channel).
