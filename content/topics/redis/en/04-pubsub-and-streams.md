# Redis Pub/Sub and Streams

## Pub/Sub — fire-and-forget messaging

Redis Pub/Sub: a publisher publishes to a channel, all active subscribers receive a copy. Ephemeral — no storage, no history. If a subscriber is disconnected at publish time — the message is lost.

```typescript
import { createClient } from 'redis';

// Publisher
const publisher = createClient({ url: process.env.REDIS_URL });
await publisher.connect();

await publisher.publish('notifications', JSON.stringify({
  type: 'ORDER_CREATED',
  userId: 'user-123',
  orderId: 'order-456',
}));

// Subscriber (separate connection — subscribe mode blocks the connection for commands)
const subscriber = createClient({ url: process.env.REDIS_URL });
await subscriber.connect();

// Pattern subscribe (glob patterns)
await subscriber.pSubscribe('notifications*', (message, channel) => {
  const event = JSON.parse(message);
  console.log(`Event on ${channel}:`, event);
});

// Subscribe to a specific channel
await subscriber.subscribe('notifications', (message) => {
  const event = JSON.parse(message);
  handleNotification(event);
});

// Important: a subscriber connection cannot be used for SET/GET
// Create separate connections: one for subscribe, one for publish/commands
```

```txt
Pub/Sub: when it fits and when it doesn't

Fits:
  ✓ WebSocket broadcasting: server A → Redis Pub/Sub → server B → client
  ✓ Live dashboard updates (missing one update is acceptable)
  ✓ Cache invalidation between multiple instances of a service
  ✓ Real-time notifications (duplicate if offline → OK)

Does NOT fit:
  ✗ Critical business events (order, payment) — loss is unacceptable
  ✗ Background jobs — retry logic is needed
  ✗ Multiple independent consumers — each receives everything (not load balancing)
  ✗ Event replay — no history
```

## Redis Streams — persistent append-only log

Streams (Redis 5+) — a lightweight Kafka analogue: append-only log with unique IDs, consumer groups, and acknowledgement. Messages are stored until explicitly deleted or trimmed.

```typescript
// XADD — append a record to the stream
// ID format: <milliseconds>-<sequence> or * for auto-generation
const messageId = await redis.xAdd('orders', '*', {
  event: 'ORDER_CREATED',
  userId: 'user-123',
  orderId: 'order-456',
  amount: '99.99',
  timestamp: Date.now().toString(),
});
// → '1700000000000-0' (auto-generated ID)

// XLEN — stream size
const len = await redis.xLen('orders');

// XRANGE — read a range
const messages = await redis.xRange('orders', '-', '+'); // all messages
const recent = await redis.xRange('orders', '1700000000000-0', '+'); // from a specific ID

// XREAD — read new messages (polling)
const newMessages = await redis.xRead([
  { key: 'orders', id: '$' }, // $ = only new messages (since connection)
], { COUNT: 10, BLOCK: 5000 }); // BLOCK: wait up to 5 sec if no messages

// XTRIM — cap the stream size
await redis.xTrim('orders', 'MAXLEN', '~', 10000); // ~ = approximate (faster)
```

## Consumer Groups — reliable parallel processing

```typescript
// Consumer Group: multiple workers share the stream (each message → one worker)
// + Acknowledgement: message stays pending until XACK

// Create the group ($ = start from new messages, 0 = from the beginning)
try {
  await redis.xGroupCreate('orders', 'order-processors', '$', { MKSTREAM: true });
} catch (err) {
  if (!err.message.includes('BUSYGROUP')) throw err; // group already exists
}

// Worker reads messages from the group
async function processOrderWorker(workerId: string) {
  while (true) {
    // XREADGROUP: read up to 10 messages for this worker
    const messages = await redis.xReadGroup(
      'order-processors',
      workerId,           // consumer ID within the group
      [{ key: 'orders', id: '>' }], // > = new unread messages
      { COUNT: 10, BLOCK: 5000 }
    );

    if (!messages) continue; // timeout, no new messages

    for (const { name: stream, messages: msgs } of messages) {
      for (const { id, message } of msgs) {
        try {
          await handleOrderEvent(message);
          // ACK: confirm successful processing
          await redis.xAck('orders', 'order-processors', id);
        } catch (err) {
          console.error(`Failed to process message ${id}:`, err);
          // No XACK → message stays pending → retry is possible
        }
      }
    }
  }
}

// Check pending messages (not yet acknowledged)
const pending = await redis.xPending('orders', 'order-processors', '-', '+', 10);
// If a message has been pending too long → worker may have crashed → XCLAIM for another worker

// XCLAIM: reassign a pending message to another worker
const claimed = await redis.xClaim('orders', 'order-processors', 'worker-2', 30000, [messageId]);
// 30000ms = idle time after which XCLAIM is allowed
```

## Pub/Sub vs Streams vs List (Queue) — decision matrix

```txt
                    Pub/Sub         List (Queue)      Streams
Storage:            None            Yes (in-memory)   Yes (persistent)
Delivery:           At-most-once    At-least-once*    At-least-once
Multiple consumers: Fan-out         Point-to-point    Groups (sharding) + Fan-out
ACK:                No              No (RPOP=delete)  Yes (XACK)
History/Replay:     No              No                Yes
Ordering:           Per channel     FIFO              Yes (by ID)
Backpressure:       No              BLPOP blocks      BLOCK option

*List: BLPOP receives and deletes atomically, but no ACK → if worker crashes after RPOP

Pub/Sub: real-time broadcasting, cache invalidation, WebSocket relay
List:    simple job queue (with BullMQ on top)
Streams: reliable event log, event sourcing, audit trail

Streams vs Kafka:
  Streams: Redis already in infrastructure → zero extra cost, low throughput (~100k/sec)
  Kafka:   dedicated streaming, millions of events/sec, days/weeks retention, ecosystem
```

## Practical example: WebSocket + Pub/Sub for scaling

```typescript
// Problem: 2 NestJS instances, client connected to instance A
// Event fires on instance B → client won't receive it
// Solution: Redis Pub/Sub as a message bus between instances

// On instance B (when event fires):
await redis.publish(`user:${userId}:events`, JSON.stringify({
  type: 'NEW_MESSAGE',
  chatId,
  message: { id, text, timestamp },
}));

// On each instance (at startup):
await subscriber.subscribe(`user:${userId}:events`, (message) => {
  const event = JSON.parse(message);
  // Find the WebSocket connection of this user ON THIS instance
  const socket = socketManager.getSocket(userId);
  if (socket) socket.emit('event', event);
});

// Scaling: Socket.IO has an official Redis adapter for this pattern
// @socket.io/redis-adapter uses exactly this Pub/Sub pattern under the hood
```

## Common interview mistakes

- **"Redis Pub/Sub is a reliable message broker like RabbitMQ"** — Pub/Sub is ephemeral: no storage, no retry, no acknowledgement. Subscriber offline → message lost forever. For reliable delivery: Redis Streams with Consumer Groups, or SQS/RabbitMQ.

- **"A subscriber connection can be used for other commands"** — no. After `SUBSCRIBE`/`PSUBSCRIBE` the connection enters subscribe mode: only `SUBSCRIBE`, `UNSUBSCRIBE`, `PSUBSCRIBE`, `PUNSUBSCRIBE`, `PING`, `QUIT` are allowed. A separate connection is required for other commands.

- **"Redis Streams is a full replacement for Kafka"** — no. Streams: in-memory (with optional persistence), throughput ~100k-500k/sec, retention limited by RAM. Kafka: disk-based, millions of events/sec, days/weeks/forever retention, built-in partitioning, rich ecosystem (Kafka Connect, Kafka Streams). Streams is lightweight Kafka for lower-volume workloads.

- **"XACK is not needed if processing succeeded"** — without XACK, the message stays in the pending list forever. When the pending list overflows → memory leak. Always call XACK after successful processing, and implement logic to retry/claim pending messages.

- **"Consumer Groups do the same thing as multiple SUBSCRIBE calls"** — the difference: multiple `SUBSCRIBE` on a channel — each receives all messages (fan-out). Consumer Group — each message goes to exactly one consumer (load balancing). For parallel processing without duplication → Consumer Groups.
