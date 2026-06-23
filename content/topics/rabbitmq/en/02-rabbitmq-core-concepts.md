# RabbitMQ Core Concepts

## AMQP — the protocol RabbitMQ speaks

RabbitMQ implements **AMQP** (Advanced Message Queuing Protocol) — an open wire-level protocol for message-oriented middleware. "Wire-level" means the protocol defines the exact bytes that travel over the network, so any client library in any language that implements AMQP can talk to RabbitMQ without vendor lock-in.

AMQP 0-9-1 is the version RabbitMQ uses (there's also AMQP 1.0, a different and incompatible standard — RabbitMQ supports it via a plugin, but 0-9-1 is the native one). When you use `amqplib` in Node.js, you're speaking AMQP 0-9-1.

The key insight about AMQP that separates RabbitMQ from simpler systems: **producers never publish directly to queues**. They publish to an **exchange**, which decides where to route the message. This indirection is what makes RabbitMQ's routing model so flexible.

## The four building blocks

```txt
┌──────────────────────────────────────────────────────────────────┐
│                         RabbitMQ Broker                          │
│                                                                  │
│  Producer ──► Exchange ──(binding)──► Queue ──► Consumer        │
│                  │                                               │
│                  └──(binding)──► Queue ──► Consumer             │
└──────────────────────────────────────────────────────────────────┘
```

### Exchange

An exchange receives messages from producers and routes them to queues based on rules. The exchange itself does **not** store messages — it only routes them. If a message arrives at an exchange and no queue matches, the message is either dropped or returned to the producer (depending on the `mandatory` flag).

Every RabbitMQ instance has several pre-declared exchanges:
- `""` (empty string) — the **default exchange**, routes directly to the queue whose name matches the routing key
- `amq.direct`, `amq.topic`, `amq.fanout`, `amq.headers` — default exchanges for each type

### Queue

A queue is where messages actually wait until a consumer is ready to process them. Queues have properties that control their behavior:

```ts
await channel.assertQueue('my-queue', {
  durable: true,      // survives broker restart
  exclusive: false,   // other connections can use it (true = delete on disconnect)
  autoDelete: false,  // don't delete when last consumer disconnects
  arguments: {
    'x-message-ttl': 60000,            // messages expire after 60s if not consumed
    'x-dead-letter-exchange': 'dlx',   // where expired/rejected messages go
    'x-max-length': 10000,             // max messages in the queue
  },
});
```

### Binding

A binding is a link between an exchange and a queue, with an optional **binding key**. It tells the exchange: "send matching messages to this queue." One queue can have multiple bindings from multiple exchanges; one exchange can have multiple bindings to multiple queues.

```ts
// Link exchange 'orders' to queue 'email-notifications' with routing key 'order.placed'
await channel.bindQueue('email-notifications', 'orders', 'order.placed');
```

### Routing Key

A routing key is a string that the producer attaches to a message when publishing. The exchange uses it (together with its own type-specific algorithm) to decide which queues receive the message.

```ts
channel.publish(
  'orders',           // exchange name
  'order.placed',     // routing key — used by exchange to route the message
  Buffer.from(JSON.stringify(payload)),
  { persistent: true },
);
```

## The four exchange types

This is the core of RabbitMQ's power — and the thing most commonly tested in interviews.

### 1. Direct exchange

Routes a message to a queue if the binding key **exactly matches** the routing key.

```txt
Exchange: 'notifications' (type: direct)

Bindings:
  'notifications' ──[email]──► queue: 'email-queue'
  'notifications' ──[sms]────► queue: 'sms-queue'
  'notifications' ──[push]───► queue: 'push-queue'

Message with routing key 'email' → goes to 'email-queue' only
Message with routing key 'sms'   → goes to 'sms-queue' only
```

```ts
import amqplib from 'amqplib';

const connection = await amqplib.connect('amqp://localhost');
const channel = await connection.createChannel();

// Setup
await channel.assertExchange('notifications', 'direct', { durable: true });
await channel.assertQueue('email-queue', { durable: true });
await channel.assertQueue('sms-queue', { durable: true });
await channel.bindQueue('email-queue', 'notifications', 'email');
await channel.bindQueue('sms-queue', 'notifications', 'sms');

// Publish — only email-queue receives this
channel.publish(
  'notifications',
  'email',
  Buffer.from(JSON.stringify({ userId: 42, message: 'Your order was placed' })),
  { persistent: true },
);
```

**Use case:** Routing different types of notifications, task routing to specific worker pools, per-tenant message routing.

### 2. Topic exchange

Routes a message to queues whose binding key **matches a pattern** using wildcards:
- `*` matches exactly one word (one dot-separated segment)
- `#` matches zero or more words

```txt
Exchange: 'events' (type: topic)

Bindings:
  'events' ──[order.*]────────► queue: 'order-service'       → matches order.placed, order.cancelled
  'events' ──[*.placed]───────► queue: 'analytics'           → matches order.placed, payment.placed
  'events' ──[payment.#]──────► queue: 'billing-service'     → matches payment.processed, payment.refund.initiated
  'events' ──[#]──────────────► queue: 'audit-log'           → matches everything

Routing key 'order.placed':
  → order-service  ✓ (order.*)
  → analytics      ✓ (*.placed)
  → audit-log      ✓ (#)
  → billing-service ✗ (payment.# doesn't match)
```

```ts
await channel.assertExchange('events', 'topic', { durable: true });
await channel.assertQueue('order-service', { durable: true });
await channel.assertQueue('analytics', { durable: true });

await channel.bindQueue('order-service', 'events', 'order.*');
await channel.bindQueue('analytics', 'events', '*.placed');

// This message goes to BOTH queues
channel.publish(
  'events',
  'order.placed',
  Buffer.from(JSON.stringify({ orderId: '123' })),
  { persistent: true },
);

// This message goes to order-service only (doesn't match *.placed because
// 'order.cancelled' — 'cancelled' ≠ 'placed')
channel.publish(
  'events',
  'order.cancelled',
  Buffer.from(JSON.stringify({ orderId: '123' })),
  { persistent: true },
);
```

**Use case:** Event-driven microservices where different services care about different subsets of events. This is the most flexible exchange type and the one most commonly used in production systems.

### 3. Fanout exchange

Ignores the routing key entirely and routes the message to **all queues bound to the exchange**.

```txt
Exchange: 'order-events' (type: fanout)

Bindings (routing key is irrelevant — ignored):
  'order-events' ──► queue: 'email-service'
  'order-events' ──► queue: 'inventory-service'
  'order-events' ──► queue: 'analytics-service'

Any message to 'order-events' → ALL three queues get a copy
```

```ts
await channel.assertExchange('order-events', 'fanout', { durable: true });
await channel.assertQueue('email-service', { durable: true });
await channel.assertQueue('inventory-service', { durable: true });
await channel.assertQueue('analytics-service', { durable: true });

// Bind all queues — routing key '' is convention for fanout (it's ignored anyway)
await channel.bindQueue('email-service', 'order-events', '');
await channel.bindQueue('inventory-service', 'order-events', '');
await channel.bindQueue('analytics-service', 'order-events', '');

// All three queues receive this
channel.publish(
  'order-events',
  '',  // routing key is ignored
  Buffer.from(JSON.stringify({ orderId: '123', total: 99.99 })),
  { persistent: true },
);
```

**Use case:** Broadcasting events to all interested parties. Classic example: an e-commerce "order placed" event that must reach the email service, inventory, billing, and analytics — all at once, all independently.

**Note:** Fanout effectively implements Pub/Sub: each service has its own queue (so it gets its own copy and processes independently), and the exchange delivers to all of them.

### 4. Headers exchange

Routes based on **message headers** (key-value metadata attached to the message) rather than the routing key. The binding specifies which headers must match.

```ts
await channel.assertExchange('reports', 'headers', { durable: true });
await channel.assertQueue('pdf-reports', { durable: true });
await channel.assertQueue('csv-reports', { durable: true });

// Bind with header matching rules
await channel.bindQueue('pdf-reports', 'reports', '', {
  'x-match': 'all',   // ALL headers must match
  format: 'pdf',
  region: 'eu',
});
await channel.bindQueue('csv-reports', 'reports', '', {
  'x-match': 'any',   // ANY header must match
  format: 'csv',
});

// This goes to pdf-reports (format=pdf AND region=eu — both match)
channel.publish('reports', '', Buffer.from('...'), {
  headers: { format: 'pdf', region: 'eu', requestId: 'abc123' },
});

// This goes to csv-reports (format=csv matches)
channel.publish('reports', '', Buffer.from('...'), {
  headers: { format: 'csv', region: 'us' },
});
```

**Use case:** Routing based on message metadata without encoding routing information in the routing key string. Rarely used in practice — topic exchange covers most routing needs more readably.

## Exchange type comparison

```txt
┌──────────────┬──────────────────────────┬──────────────────────────────────────────┐
│ Exchange     │ Routes based on          │ Typical use case                         │
├──────────────┼──────────────────────────┼──────────────────────────────────────────┤
│ Direct       │ Exact routing key match  │ Task routing, specific notification types│
│ Topic        │ Wildcard pattern match   │ Event-driven microservices               │
│ Fanout       │ Nothing (ignores key)    │ Broadcasting, Pub/Sub                    │
│ Headers      │ Message header values    │ Complex attribute-based routing          │
└──────────────┴──────────────────────────┴──────────────────────────────────────────┘
```

## The default exchange — a shortcut worth knowing

The default exchange (empty string `""`) is a pre-declared direct exchange with a special rule: **every queue is automatically bound to it with its own name as the routing key**.

This is why you can do this without ever declaring an exchange:

```ts
// No exchange declaration needed — uses the default exchange
await channel.assertQueue('my-tasks', { durable: true });

// This routes to 'my-tasks' via the default exchange
channel.sendToQueue(
  'my-tasks',
  Buffer.from(JSON.stringify({ task: 'process-image', imageId: '456' })),
  { persistent: true },
);
```

`sendToQueue` is syntactic sugar for `publish('', queueName, ...)` — it publishes to the default exchange with the queue name as the routing key. This is fine for simple cases, but as your system grows, explicit exchanges give you more flexibility (you can add a new consumer to a topic exchange without changing the producer at all).

## Virtual hosts (vhosts)

RabbitMQ uses **virtual hosts** (vhosts) to provide logical isolation — similar to how different databases in Postgres are isolated from each other. Each vhost has its own set of exchanges, queues, bindings, and user permissions.

```ts
// Connect to a specific vhost
const connection = await amqplib.connect('amqp://user:password@localhost:5672/my-app');
//                                                                               ^^^^^^^^
//                                                                               vhost name
```

The default vhost is `/`. In production, it's good practice to give each application its own vhost rather than sharing the default one.

## Channels — connections without the overhead

A RabbitMQ connection is a TCP connection — expensive to open. A **channel** is a lightweight virtual connection multiplexed over a single TCP connection. In practice: open one connection per process, create channels as needed (per thread, per operation, or per consumer).

```ts
const connection = await amqplib.connect('amqp://localhost');

// One connection, multiple channels
const publisherChannel = await connection.createChannel();
const consumerChannel = await connection.createChannel();

// Channels are not thread-safe in amqplib — don't share one channel
// between concurrent async operations
```

A common mistake with amqplib: reusing one channel for both publishing and consuming in a high-throughput app. Best practice is separate channels for publishing and consuming, and never call channel methods concurrently from two async operations on the same channel.

## Common interview traps

- **"Producers publish to queues"** — no. Producers publish to exchanges. The exchange routes to queues via bindings. This is a fundamental AMQP design decision, and getting it wrong immediately signals unfamiliarity with the protocol.

- **"Topic exchange routing key * matches zero or more words"** — no, `*` matches exactly one word. `#` matches zero or more. This distinction matters: `order.*` matches `order.placed` but NOT `order.payment.processed` and NOT `order` (zero segments). Use `order.#` if you want all sub-events.

- **"Fanout is the same as broadcasting to all consumers of one queue"** — no. Fanout broadcasts to all **queues** bound to the exchange. Each queue then independently delivers to its own set of consumers. If you want competing consumers (load balancing), put multiple consumers on one queue. If you want all of them to get the message, put each consumer on its own queue, all bound to the same fanout exchange.

- **"I can have multiple consumers on one queue and each gets every message"** — no, that's not how queues work. Multiple consumers on one queue means competing consumers (round-robin load balancing) — each message goes to exactly one consumer. For "all consumers get the message", you need Pub/Sub: one fanout/topic exchange, one queue per consumer.

- **"Bindings are just configuration — they don't affect performance"** — not entirely true. Every published message must be checked against all bindings of the exchange. For topic exchanges with thousands of bindings, the pattern matching has a cost. In practice it's rarely a bottleneck, but it's the honest answer.

- **"The default exchange is special — it's different from other direct exchanges"** — it IS special in one way: every queue is auto-bound to it with the queue name as binding key. You can't manually bind other queues to it (you can't replicate its auto-binding behavior on a custom exchange). Otherwise it behaves like any direct exchange.
