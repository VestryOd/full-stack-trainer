# Message Queues — Fundamentals

## The problem that message queues solve

Imagine two microservices talking directly over HTTP:

```txt
[Order Service] ──── POST /api/notify ────► [Email Service]
```

This works fine until it doesn't. Let's list what can go wrong in production:

- **Email Service is down** → Order Service gets a 503 → the order fails, even though the order itself was saved correctly
- **Email Service is slow** (queuing up a lot of emails during a flash sale) → Order Service request times out → customer sees an error while their order is actually being processed
- **Traffic spike** → 10,000 orders/minute → Email Service gets hammered with 10,000 concurrent HTTP requests → it falls over entirely
- **Deployment** → you deploy a new version of Email Service → for 5-10 seconds it's unavailable → Order Service requests fail

In all four cases, **the availability and latency of one service directly impacts another**. This tight coupling is the core problem.

A message queue breaks that direct dependency:

```txt
[Order Service] ──► [Queue] ──► [Email Service]
      ↑                               ↑
 "I published               "I'll process these
  a message,                 when I'm ready"
  my job is done"
```

Order Service publishes a message and moves on — it doesn't wait for Email Service to finish, and it doesn't care if Email Service is temporarily down. Email Service picks up messages from the queue at its own pace, recovering from downtime by simply resuming from where it left off.

## Synchronous vs asynchronous communication

This is the fundamental distinction to internalize before anything else:

```txt
Synchronous (HTTP/REST, gRPC):
  Caller ──► Callee
  Caller WAITS for response
  If callee is slow/unavailable → caller is affected

Asynchronous (message queues):
  Publisher ──► Queue ◄── Consumer
  Publisher does NOT wait
  Consumer processes when it can
  Decoupled in time AND in failure
```

Synchronous isn't "bad" — it's the right choice for:
- Queries where you need the result immediately ("get this user's profile")
- Operations that must be atomic ("check payment + reserve seat + confirm booking" in a single transaction)
- Simple request/response where two services are naturally coupled (e.g., an API Gateway calling its own backend)

Asynchronous (message queues) is the right choice for:
- Work that can happen in the background ("send a welcome email after signup")
- Work that could overwhelm a downstream service if done synchronously at peak load ("resize 10,000 uploaded images")
- Decoupling services that don't need to know about each other ("when an order is placed, notify inventory, billing, and analytics — independently")
- Guaranteed delivery even if a consumer is temporarily down

## Core vocabulary: producer, consumer, broker

These three terms show up in every message queue system, whether it's RabbitMQ, Kafka, AWS SQS, or Redis Streams:

```txt
Producer  — the service that creates and sends a message
Consumer  — the service that receives and processes a message
Broker    — the intermediary that stores and routes messages between producers and consumers
```

In code terms for a Node.js app:

```ts
// Producer — Order Service creates a message when an order is placed
async function placeOrder(orderData: OrderData): Promise<void> {
  await db.orders.create(orderData);

  // After saving to DB, publish an event — don't call Email Service directly
  await messageQueue.publish('order.placed', {
    orderId: orderData.id,
    customerEmail: orderData.email,
    items: orderData.items,
  });
}

// Consumer — Email Service listens for that event
messageQueue.subscribe('order.placed', async (message: OrderPlacedMessage) => {
  await emailService.sendOrderConfirmation(message.customerEmail, message.orderId);
});
```

The broker (RabbitMQ, in our case) sits in the middle: it receives the message from the producer, stores it durably, and delivers it to the consumer when the consumer is ready. Neither service knows the other's network address — they only know the name of the queue or topic.

## Queue vs topic — two fundamental models

Most message queuing systems support two delivery patterns:

```txt
Queue (Point-to-Point):
  Producer ──► [Queue] ──► Consumer A
                            (one consumer gets each message)
  
  Use case: background jobs, task queues
  Example: "process this image upload" — one worker should do it, not three

Topic (Publish/Subscribe or Pub/Sub):
  Producer ──► [Topic] ──► Consumer A (gets a copy)
                       ──► Consumer B (gets a copy)
                       ──► Consumer C (gets a copy)
  
  Use case: event broadcasting, fan-out
  Example: "order placed" → notify email service AND inventory service AND analytics
```

In RabbitMQ specifically, both patterns are implemented through its **exchange** system — but that's covered in detail in the next article. The mental model above is what matters for now.

## Push vs pull — how messages reach consumers

This is a distinction that trips up a lot of engineers (and comes up on senior interviews):

```txt
Push model:
  Broker actively delivers messages TO the consumer as soon as they arrive
  Consumer must be ready to receive
  
  Pros: lower latency (message arrives immediately)
  Cons: broker doesn't know if consumer can handle the load

Pull model:
  Consumer actively fetches messages FROM the broker when it's ready
  Consumer controls the rate
  
  Pros: natural backpressure — consumer only takes what it can handle
  Cons: adds polling latency (consumer might be waiting when new messages arrive)
```

**RabbitMQ uses a push model** — it pushes messages to consumers via the AMQP (Advanced Message Queuing Protocol) channel. However, RabbitMQ gives consumers a way to control the flow through **prefetch count** (covered in article 03): a consumer can tell the broker "don't give me more than N unacknowledged messages at a time", which effectively implements backpressure within the push model.

**Kafka uses a pull model** — consumers explicitly poll for new messages. This is one of the key architectural differences between the two systems (covered in article 05).

AWS SQS also uses a pull model (consumers call `ReceiveMessage` to fetch).

## What "durable" and "persistent" mean in this context

Two terms that are often conflated but mean different things:

```txt
Durable queue:
  The queue definition survives a broker restart
  (its configuration — name, bindings, settings — is persisted to disk)
  
  Note: a durable queue does NOT automatically persist the messages inside it

Persistent message:
  The message content itself is written to disk
  (survives a broker restart even if the consumer hasn't processed it yet)
```

For production systems you typically want **both** — a durable queue that holds persistent messages. Losing a queue definition on restart means you've lost the "pipe" entirely; losing the messages means the queue exists but is empty after a crash.

In amqplib (the standard Node.js AMQP client), this looks like:

```ts
import amqplib from 'amqplib';

const connection = await amqplib.connect('amqp://localhost');
const channel = await connection.createChannel();

// Declare a durable queue — survives broker restart
await channel.assertQueue('order-confirmations', { durable: true });

// Publish a persistent message — survives broker restart
channel.sendToQueue(
  'order-confirmations',
  Buffer.from(JSON.stringify({ orderId: '123', email: 'user@example.com' })),
  { persistent: true }, // delivery mode 2 — written to disk
);
```

Without `persistent: true`, messages are held in memory only. If RabbitMQ restarts before a consumer processes them, they're gone.

## Why not just use a database as a queue?

A common "why not" question in interviews. The short answer: you *can*, and teams do — but it comes with real tradeoffs:

```txt
Database-as-queue (polling pattern):
  ✓ No new infrastructure to manage
  ✓ Messages are transactional — you can atomically save data AND enqueue in one DB transaction
  ✓ Easy to inspect queue state with SQL
  
  ✗ Polling is inefficient: you're constantly querying for new rows
  ✗ At scale, the "dequeue" query (SELECT ... FOR UPDATE SKIP LOCKED) adds contention
  ✗ No built-in fan-out (sending to multiple consumers)
  ✗ Message routing, dead-letter handling, retry policies — you have to build all of this yourself
  ✗ The DB table grows without bound unless you regularly delete processed rows
```

PostgreSQL's `SKIP LOCKED` combined with a jobs table is a perfectly valid pattern for low-to-medium volume background jobs (it's what libraries like pgBoss and Que use). But once you need fan-out, multiple consumer groups, complex routing, or high throughput (100k+ messages/second), a dedicated broker pays for itself.

The Transactional Outbox Pattern — saving messages to a DB table atomically with business data, then having a separate process relay them to the real queue — actually combines both: you get transactional safety AND the routing/fanout capabilities of a real broker. It's a senior-level pattern worth knowing and will come up again in article 04.

## Common interview traps

- **"Message queues are just for email and notifications"** — this misses the broader role: decoupling services, rate limiting downstream systems, event sourcing, distributed task processing, microservice choreography. Emails/notifications are the entry-level use case; the real value is in reliability and decoupling.

- **"Async communication is always better than sync"** — wrong. If you need the result immediately (checking if a username is available), async adds complexity with no benefit. Use sync (HTTP) when you need the answer now; use async when you can fire-and-forget or tolerate eventual consistency.

- **Confusing "durable queue" with "persistent messages"** — these are independent settings. A durable queue definition without `persistent: true` messages will empty itself after a broker restart. You need both in production.

- **"If the message queue goes down, everything stops"** — in theory yes, but this misses the architectural response: the broker is a single piece of infrastructure that you run clustered with replication. RabbitMQ clustering + quorum queues give you the same HA guarantees as a clustered database. Replacing one complex failure mode (N direct dependencies) with one hardened infrastructure component is a net win.

- **"The producer should wait for confirmation that the consumer processed the message"** — this re-introduces the synchronous coupling you were trying to eliminate. Producers should only wait for the broker to confirm it received the message (publisher confirms), not for consumer processing to complete.
